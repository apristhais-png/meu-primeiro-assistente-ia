"""Comunicação com os provedores de IA e troca automática entre eles (fallback).

Provedores: OpenRouter, Anthropic e OpenAI (SPEC, seções 2 e 5).

Regra do fallback (RF6):
    - Só uma falha TEMPORÁRIA permite tentar o próximo provedor:
      tempo esgotado, problema de conexão, excesso de pedidos (429),
      erro no servidor do provedor (5xx) ou resposta vazia.
    - Erro de AUTENTICAÇÃO (chave inválida), de PERMISSÃO ou de COBRANÇA
      (sem créditos) NÃO é temporário: o fallback para, para o problema
      não ficar escondido. Outros erros da requisição (ex.: modelo
      inexistente) também param.
    - Provedor sem chave configurada é pulado sem ser chamado.

Tempo e novas tentativas (otimização de confiabilidade):
    - Cada pergunta tem um TEMPO MÁXIMO TOTAL (geracao.tempo_maximo_total_segundos),
      somando todas as tentativas, esperas e o fallback. Cada tentativa
      também tem o próprio limite (geracao.timeout_segundos).
    - O limite de tempo da biblioteca HTTP vale só para "silêncio" entre
      pedaços da resposta, não para a chamada inteira. Por isso, cada
      chamada roda numa linha de execução separada e o app para de esperar
      quando o prazo acaba, mesmo que o provedor continue mandando sinais
      de "ainda estou processando".
    - Nova tentativa no MESMO provedor só acontece quando não sobra outro
      provedor com chave, só para falhas temporárias rápidas (conexão, erro
      5xx, resposta vazia), no máximo geracao.tentativas_por_provedor vezes
      e só se ainda houver tempo. Nunca para 429 (respeita o limite do
      plano gratuito), tempo esgotado, chave, cobrança ou modelo inválido.

Segurança:
    - A chave nunca aparece em mensagens de erro nem nos logs.
    - A mensagem original do provedor também não é repassada, porque
      algumas incluem parte da chave.
    - O conteúdo das perguntas e respostas nunca vai para os logs.
"""

import contextvars
import json
import logging
import os
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import anthropic
import openai

from assistente.config import Configuracao, Geracao

logger = logging.getLogger("assistente.provedores")

# Nome da variável de ambiente com a chave de cada provedor (SPEC 4.5).
VARIAVEIS_DE_CHAVE = {
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

ENDERECO_OPENROUTER = "https://openrouter.ai/api/v1"

MENSAGEM_SEM_RESPOSTA = (
    "Desculpe, não consegui responder agora. Tente novamente em alguns minutos."
)
MENSAGEM_DEMORA = (
    "O modelo gratuito está demorando mais que o normal. Tente novamente em instantes."
)
MENSAGEM_MUITOS_PEDIDOS = (
    "O modelo gratuito recebeu muitas perguntas agora. Aguarde um minuto e tente novamente."
)
# Acrescentada ao fim de uma resposta cortada pelo limite de tamanho.
NOTA_RESPOSTA_INCOMPLETA = "\n\n_(A resposta ficou incompleta. Peça para eu continuar.)_"

# Falhas que justificam tentar de novo o MESMO provedor (são rápidas e,
# no openrouter/free, a nova tentativa costuma ir para outro modelo gratuito).
FALHAS_QUE_PERMITEM_REPETIR = {"conexao", "servidor", "resposta_vazia"}
ESPERA_ANTES_DE_REPETIR = 1.0  # segundos
TEMPO_MINIMO_POR_TENTATIVA = 5.0  # com menos que isso, não vale começar outra chamada

# Identificador curto de cada pergunta, só para ligar as linhas do log.
# Não tem relação com a pessoa nem com o conteúdo da conversa.
id_da_pergunta: contextvars.ContextVar[str] = contextvars.ContextVar("id_da_pergunta", default="-")

# Tipos de falha e se permitem tentar o próximo provedor.
FALHAS_TEMPORARIAS = {"tempo_esgotado", "conexao", "limite_de_uso", "servidor", "resposta_vazia"}
FALHAS_QUE_PARAM = {"autenticacao", "permissao", "cobranca", "requisicao_invalida", "inesperada"}

# Trechos que indicam problema de cobrança/créditos no corpo do erro.
# A OpenAI, por exemplo, avisa "sem créditos" com o código 429.
_SINAIS_DE_COBRANCA = (
    "insufficient_quota",
    "billing",
    "credit balance",
    "insufficient credit",
    "payment required",
    "exceeded your current quota",
)

_EXPLICACOES = {
    "tempo_esgotado": "o provedor demorou demais para responder",
    "conexao": "não foi possível conectar ao provedor",
    "limite_de_uso": "o provedor recebeu pedidos demais (429)",
    "servidor": "o servidor do provedor está com problemas",
    "resposta_vazia": "o provedor devolveu uma resposta vazia",
    "autenticacao": "a chave de API foi recusada. Confira se ela está certa e sem espaços",
    "permissao": "a chave não tem permissão para usar este modelo",
    "cobranca": "a conta do provedor está sem créditos ou atingiu o limite de gastos",
    "requisicao_invalida": "o provedor recusou o pedido. Confira o nome do modelo no config.yml",
    "inesperada": "aconteceu um erro inesperado",
}


class FalhaDoProvedor(Exception):
    """Um provedor não conseguiu responder. Nunca contém a chave."""

    def __init__(self, provedor: str, tipo: str, status: int | None = None):
        self.provedor = provedor
        self.tipo = tipo
        self.status = status
        self.temporaria = tipo in FALHAS_TEMPORARIAS
        codigo = f" (código {status})" if status else ""
        super().__init__(f"{provedor}: {_EXPLICACOES[tipo]}{codigo}")


@dataclass
class Tentativa:
    provedor: str
    resultado: str  # "respondeu", "sem_chave" ou o tipo da falha


@dataclass
class Resposta:
    texto: str
    provedor: str
    tentativas: list[Tentativa] = field(default_factory=list)


def _mensagem_para_pessoa(tentativas: list[Tentativa], erro_de_configuracao: bool) -> str:
    """Mensagem curta, sem detalhes técnicos. Específica só quando todas as falhas foram iguais."""
    tipos = {t.resultado for t in tentativas if t.resultado != "sem_chave"}
    if not erro_de_configuracao and tipos == {"tempo_esgotado"}:
        return MENSAGEM_DEMORA
    if not erro_de_configuracao and tipos == {"limite_de_uso"}:
        return MENSAGEM_MUITOS_PEDIDOS
    return MENSAGEM_SEM_RESPOSTA


class SemResposta(Exception):
    """Nenhum provedor respondeu."""

    def __init__(self, tentativas: list[Tentativa], erro_de_configuracao: bool):
        self.tentativas = tentativas
        # True quando o fallback parou por chave, permissão, cobrança ou pedido inválido.
        self.erro_de_configuracao = erro_de_configuracao
        self.mensagem_para_pessoa = _mensagem_para_pessoa(tentativas, erro_de_configuracao)
        resumo = ", ".join(f"{t.provedor}={t.resultado}" for t in tentativas) or "nenhum provedor"
        super().__init__(f"nenhum provedor respondeu ({resumo})")


# ---------- Classificação dos erros ----------

def _tem_sinal_de_cobranca(corpo: object) -> bool:
    try:
        texto = json.dumps(corpo, default=str).lower()
    except (TypeError, ValueError):
        texto = str(corpo).lower()
    return any(sinal in texto for sinal in _SINAIS_DE_COBRANCA)


def classificar_erro(provedor: str, erro: Exception) -> FalhaDoProvedor:
    """Transforma um erro das bibliotecas da OpenAI/Anthropic em FalhaDoProvedor."""
    # Tempo esgotado vem antes de conexão, porque é um tipo especial dela.
    if isinstance(erro, (openai.APITimeoutError, anthropic.APITimeoutError)):
        return FalhaDoProvedor(provedor, "tempo_esgotado")
    if isinstance(erro, (openai.APIConnectionError, anthropic.APIConnectionError)):
        return FalhaDoProvedor(provedor, "conexao")
    if isinstance(erro, (openai.APIStatusError, anthropic.APIStatusError)):
        status = erro.status_code
        # Cobrança primeiro: pode chegar como 402, 429 ou até 400.
        if status == 402 or _tem_sinal_de_cobranca(erro.body):
            return FalhaDoProvedor(provedor, "cobranca", status)
        if status == 401:
            return FalhaDoProvedor(provedor, "autenticacao", status)
        if status == 403:
            return FalhaDoProvedor(provedor, "permissao", status)
        if status == 429:
            return FalhaDoProvedor(provedor, "limite_de_uso", status)
        if status == 408:
            return FalhaDoProvedor(provedor, "tempo_esgotado", status)
        if status >= 500:
            return FalhaDoProvedor(provedor, "servidor", status)
        return FalhaDoProvedor(provedor, "requisicao_invalida", status)
    return FalhaDoProvedor(provedor, "inesperada")


# ---------- Provedores ----------

class Provedor:
    """Base comum: guarda nome, modelo, chave e ajustes; trata os erros."""

    def __init__(self, nome: str, modelo: str, chave: str | None, geracao: Geracao, cliente=None):
        self.nome = nome
        self.modelo = modelo
        self._chave = (chave or "").strip() or None
        self.geracao = geracao
        # "cliente" permite usar uma simulação (mock) nos testes.
        self._cliente = cliente

    def __repr__(self) -> str:
        # Nunca mostra a chave.
        return f"{type(self).__name__}(nome={self.nome!r}, modelo={self.modelo!r}, disponivel={self.disponivel})"

    @property
    def disponivel(self) -> bool:
        """True se a chave deste provedor está configurada."""
        return self._chave is not None

    @property
    def cliente(self):
        if self._cliente is None:
            self._cliente = self._criar_cliente()
        return self._cliente

    def responder(self, mensagens: list[dict], instrucoes: str, prazo: float | None = None) -> str:
        """Envia a conversa e devolve o texto da resposta.

        "prazo" (segundos) limita a espera desta chamada; sem ele, vale o
        timeout_segundos do config.yml.
        """
        opcoes = {"timeout": prazo} if prazo is not None else {}
        try:
            saida = self._chamar(mensagens, instrucoes, **opcoes)
        except FalhaDoProvedor:
            raise
        except Exception as erro:  # noqa: BLE001 - de propósito: todo erro vira uma falha segura
            # "from None": a mensagem original do provedor (que pode conter
            # parte da chave) não é anexada ao erro.
            raise classificar_erro(self.nome, erro) from None
        # Só dados técnicos no log: nunca o texto da pergunta ou da resposta.
        logger.info(
            "ia_detalhes id=%s provedor=%s modelo_servido=%s fim=%s tokens_saida=%s raciocinio=%s",
            id_da_pergunta.get(), self.nome, saida.modelo_servido or "-", saida.motivo_do_fim or "-",
            saida.tokens_saida if saida.tokens_saida is not None else "-",
            "sim" if saida.teve_raciocinio else "nao",
        )
        texto = saida.texto
        if not texto or not texto.strip():
            # Causa comum nos modelos gratuitos: um modelo de "raciocínio" gasta
            # todo o max_tokens pensando e não sobra nada para a resposta (fim=length).
            raise FalhaDoProvedor(self.nome, "resposta_vazia")
        if saida.motivo_do_fim in ("length", "max_tokens"):
            texto = texto.rstrip() + NOTA_RESPOSTA_INCOMPLETA
        return texto

    def _criar_cliente(self):
        raise NotImplementedError

    def _chamar(self, mensagens: list[dict], instrucoes: str, **opcoes) -> "Saida":
        raise NotImplementedError


@dataclass
class Saida:
    """O que voltou de uma chamada. Os campos além do texto vão só para o log."""

    texto: str
    modelo_servido: str | None = None  # no openrouter/free, qual modelo gratuito respondeu
    motivo_do_fim: str | None = None  # "stop", "length", ...
    tokens_saida: int | None = None
    teve_raciocinio: bool = False


class ProvedorCompativelComOpenAI(Provedor):
    """OpenAI e OpenRouter: o OpenRouter usa o mesmo "idioma" da OpenAI."""

    def __init__(self, *args, endereco: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.endereco = endereco

    def _criar_cliente(self):
        return openai.OpenAI(
            api_key=self._chave,
            base_url=self.endereco,
            timeout=self.geracao.timeout_segundos,
            max_retries=0,  # quem decide tentar de novo é o fallback
        )

    def _parametros_de_tamanho(self) -> dict:
        # O OpenRouter usa "max_tokens"; a OpenAI usa "max_completion_tokens".
        if self.nome == "openai":
            return {"max_completion_tokens": self.geracao.max_tokens}
        return {"max_tokens": self.geracao.max_tokens}

    def _chamar(self, mensagens: list[dict], instrucoes: str, **opcoes) -> Saida:
        resposta = self.cliente.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "system", "content": instrucoes}, *mensagens],
            temperature=self.geracao.temperatura,
            **self._parametros_de_tamanho(),
            **opcoes,
        )
        modelo = getattr(resposta, "model", None)
        uso = getattr(resposta, "usage", None)
        tokens = getattr(uso, "completion_tokens", None)
        if not resposta.choices:
            return Saida("", modelo, None, tokens)
        escolha = resposta.choices[0]
        mensagem = escolha.message
        return Saida(
            texto=mensagem.content or "",
            modelo_servido=modelo if isinstance(modelo, str) else None,
            motivo_do_fim=_texto_ou_none(getattr(escolha, "finish_reason", None)),
            tokens_saida=tokens if isinstance(tokens, int) else None,
            # O OpenRouter devolve o raciocínio num campo à parte ("reasoning").
            teve_raciocinio=bool(getattr(mensagem, "reasoning", None)),
        )


class ProvedorAnthropic(Provedor):
    """Anthropic (Claude)."""

    def _criar_cliente(self):
        return anthropic.Anthropic(
            api_key=self._chave,
            timeout=self.geracao.timeout_segundos,
            max_retries=0,  # quem decide tentar de novo é o fallback
        )

    def _chamar(self, mensagens: list[dict], instrucoes: str, **opcoes) -> Saida:
        # A temperatura NÃO é enviada: os modelos atuais do Claude recusam
        # esse parâmetro (erro 400).
        resposta = self.cliente.messages.create(
            model=self.modelo,
            max_tokens=self.geracao.max_tokens,
            system=instrucoes,
            messages=mensagens,
            **opcoes,
        )
        # A resposta pode ter vários blocos (ex.: raciocínio); só o texto interessa.
        texto = "".join(bloco.text for bloco in resposta.content if bloco.type == "text")
        uso = getattr(resposta, "usage", None)
        tokens = getattr(uso, "output_tokens", None)
        return Saida(
            texto=texto,
            modelo_servido=_texto_ou_none(getattr(resposta, "model", None)),
            motivo_do_fim=_texto_ou_none(getattr(resposta, "stop_reason", None)),
            tokens_saida=tokens if isinstance(tokens, int) else None,
            teve_raciocinio=any(bloco.type == "thinking" for bloco in resposta.content),
        )


def _texto_ou_none(valor) -> str | None:
    return valor if isinstance(valor, str) else None


def criar_provedores(config: Configuracao, ambiente: Mapping[str, str] | None = None) -> list[Provedor]:
    """Cria os provedores ativos, na ordem do config.yml, lendo as chaves do ambiente."""
    ambiente = os.environ if ambiente is None else ambiente
    provedores: list[Provedor] = []
    for item in config.provedores_ativos:
        chave = ambiente.get(VARIAVEIS_DE_CHAVE[item.nome])
        if item.nome == "anthropic":
            provedores.append(ProvedorAnthropic(item.nome, item.modelo, chave, config.geracao))
        else:
            endereco = ENDERECO_OPENROUTER if item.nome == "openrouter" else None
            provedores.append(
                ProvedorCompativelComOpenAI(
                    item.nome, item.modelo, chave, config.geracao, endereco=endereco
                )
            )
    return provedores


# ---------- Fallback ----------

class _PrazoEsgotado(Exception):
    pass


def _executar_com_prazo(funcao: Callable[[], str], prazo: float) -> str:
    """Roda "funcao" e para de ESPERAR quando o prazo acaba.

    A chamada abandonada termina sozinha em segundo plano (no máximo no
    timeout da biblioteca HTTP); o resultado dela é descartado. Ela não é
    repetida nem gera outra chamada.
    """
    resultado: dict = {}
    contexto = contextvars.copy_context()  # leva o id da pergunta para os logs

    def alvo():
        try:
            resultado["texto"] = contexto.run(funcao)
        except BaseException as erro:  # noqa: BLE001 - devolvido para quem chamou
            resultado["erro"] = erro

    linha = threading.Thread(target=alvo, name="chamada-ia", daemon=True)
    linha.start()
    linha.join(prazo)
    if linha.is_alive():
        raise _PrazoEsgotado
    if "erro" in resultado:
        raise resultado["erro"]
    return resultado["texto"]


def _chamar_provedor(provedor, mensagens, instrucoes, prazo):
    # Provedores reais recebem o prazo também na biblioteca HTTP; os
    # simulados dos testes só têm (mensagens, instrucoes).
    if isinstance(provedor, Provedor):
        return provedor.responder(mensagens, instrucoes, prazo=prazo)
    return provedor.responder(mensagens, instrucoes)


def responder_com_fallback(
    provedores: list[Provedor],
    mensagens: list[dict],
    instrucoes: str,
    *,
    tempo_maximo_total: float | None = None,
    timeout_por_tentativa: float | None = None,
    tentativas_por_provedor: int = 1,
    relogio: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
) -> Resposta:
    """Tenta os provedores em ordem até um responder.

    Lança SemResposta se nenhum responder. Erros de chave, permissão,
    cobrança ou pedido inválido interrompem a lista na hora.

    Com tempo_maximo_total, nenhuma pergunta espera mais que isso (somando
    tentativas, esperas e fallback). Sem ele, cada chamada espera o tempo
    da própria biblioteca (comportamento antigo, usado em testes diretos).
    """
    inicio = relogio()
    tentativas: list[Tentativa] = []

    def restante() -> float | None:
        if tempo_maximo_total is None:
            return None
        return tempo_maximo_total - (relogio() - inicio)

    disponiveis = [p for p in provedores if p.disponivel]
    for provedor in provedores:
        if not provedor.disponivel:
            logger.info("Provedor %s pulado: chave não configurada.", provedor.nome)
            tentativas.append(Tentativa(provedor.nome, "sem_chave"))
            continue

        e_o_ultimo = provedor is disponiveis[-1]
        limite_de_vezes = max(1, tentativas_por_provedor) if e_o_ultimo else 1
        vez = 0
        while True:
            vez += 1
            sobra = restante()
            if sobra is not None and sobra < TEMPO_MINIMO_POR_TENTATIVA:
                logger.warning("ia_chamada id=%s provedor=%s resultado=sem_tempo", id_da_pergunta.get(), provedor.nome)
                tentativas.append(Tentativa(provedor.nome, "tempo_esgotado"))
                raise SemResposta(tentativas, erro_de_configuracao=False)

            prazo = None
            if sobra is not None:
                prazo = min(sobra, timeout_por_tentativa or sobra)
            comeco = relogio()
            try:
                if prazo is None:
                    texto = _chamar_provedor(provedor, mensagens, instrucoes, None)
                else:
                    texto = _executar_com_prazo(
                        lambda p=provedor, s=prazo: _chamar_provedor(p, mensagens, instrucoes, s), prazo
                    )
            except _PrazoEsgotado:
                falha = FalhaDoProvedor(provedor.nome, "tempo_esgotado")
            except FalhaDoProvedor as erro:
                falha = erro
            else:
                falha = None
            duracao_ms = round((relogio() - comeco) * 1000)

            if falha is None:
                tentativas.append(Tentativa(provedor.nome, "respondeu"))
                logger.info(
                    "ia_chamada id=%s provedor=%s tentativa=%d resultado=sucesso duracao_ms=%d",
                    id_da_pergunta.get(), provedor.nome, vez, duracao_ms,
                )
                logger.info("Provedor %s respondeu.", provedor.nome)
                return Resposta(texto, provedor.nome, tentativas)

            tentativas.append(Tentativa(provedor.nome, falha.tipo))
            logger.warning(
                "ia_chamada id=%s provedor=%s tentativa=%d resultado=%s status=%s duracao_ms=%d",
                id_da_pergunta.get(), provedor.nome, vez, falha.tipo, falha.status or "-", duracao_ms,
            )
            if not falha.temporaria:
                logger.error(
                    "Erro de configuração: %s. Os outros provedores NÃO foram tentados; "
                    "corrija o problema para o assistente voltar a funcionar.",
                    falha,
                )
                raise SemResposta(tentativas, erro_de_configuracao=True) from None

            sobra = restante()
            pode_repetir = (
                vez < limite_de_vezes
                and falha.tipo in FALHAS_QUE_PERMITEM_REPETIR
                and (sobra is None or sobra > ESPERA_ANTES_DE_REPETIR + TEMPO_MINIMO_POR_TENTATIVA)
            )
            if pode_repetir:
                logger.warning("Falha temporária: %s. Tentando de novo em %.0f s.", falha, ESPERA_ANTES_DE_REPETIR)
                dormir(ESPERA_ANTES_DE_REPETIR)
                continue
            logger.warning("Falha temporária: %s. Tentando o próximo provedor.", falha)
            break

    logger.error("Nenhum provedor respondeu (%s).", ", ".join(f"{t.provedor}={t.resultado}" for t in tentativas))
    raise SemResposta(tentativas, erro_de_configuracao=False)
