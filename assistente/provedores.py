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

Segurança:
    - A chave nunca aparece em mensagens de erro nem nos logs.
    - A mensagem original do provedor também não é repassada, porque
      algumas incluem parte da chave.
    - O conteúdo das perguntas e respostas nunca vai para os logs.
"""

import json
import logging
import os
from collections.abc import Mapping
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


class SemResposta(Exception):
    """Nenhum provedor respondeu."""

    def __init__(self, tentativas: list[Tentativa], erro_de_configuracao: bool):
        self.tentativas = tentativas
        # True quando o fallback parou por chave, permissão, cobrança ou pedido inválido.
        self.erro_de_configuracao = erro_de_configuracao
        self.mensagem_para_pessoa = MENSAGEM_SEM_RESPOSTA
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

    def responder(self, mensagens: list[dict], instrucoes: str) -> str:
        """Envia a conversa e devolve o texto da resposta."""
        try:
            texto = self._chamar(mensagens, instrucoes)
        except FalhaDoProvedor:
            raise
        except Exception as erro:  # noqa: BLE001 - de propósito: todo erro vira uma falha segura
            # "from None": a mensagem original do provedor (que pode conter
            # parte da chave) não é anexada ao erro.
            raise classificar_erro(self.nome, erro) from None
        if not texto or not texto.strip():
            raise FalhaDoProvedor(self.nome, "resposta_vazia")
        return texto

    def _criar_cliente(self):
        raise NotImplementedError

    def _chamar(self, mensagens: list[dict], instrucoes: str) -> str:
        raise NotImplementedError


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

    def _chamar(self, mensagens: list[dict], instrucoes: str) -> str:
        resposta = self.cliente.chat.completions.create(
            model=self.modelo,
            messages=[{"role": "system", "content": instrucoes}, *mensagens],
            temperature=self.geracao.temperatura,
            **self._parametros_de_tamanho(),
        )
        if not resposta.choices:
            return ""
        return resposta.choices[0].message.content or ""


class ProvedorAnthropic(Provedor):
    """Anthropic (Claude)."""

    def _criar_cliente(self):
        return anthropic.Anthropic(
            api_key=self._chave,
            timeout=self.geracao.timeout_segundos,
            max_retries=0,  # quem decide tentar de novo é o fallback
        )

    def _chamar(self, mensagens: list[dict], instrucoes: str) -> str:
        # A temperatura NÃO é enviada: os modelos atuais do Claude recusam
        # esse parâmetro (erro 400).
        resposta = self.cliente.messages.create(
            model=self.modelo,
            max_tokens=self.geracao.max_tokens,
            system=instrucoes,
            messages=mensagens,
        )
        # A resposta pode ter vários blocos (ex.: raciocínio); só o texto interessa.
        return "".join(bloco.text for bloco in resposta.content if bloco.type == "text")


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

def responder_com_fallback(provedores: list[Provedor], mensagens: list[dict], instrucoes: str) -> Resposta:
    """Tenta os provedores em ordem até um responder.

    Lança SemResposta se nenhum responder. Erros de chave, permissão,
    cobrança ou pedido inválido interrompem a lista na hora.
    """
    tentativas: list[Tentativa] = []
    for provedor in provedores:
        if not provedor.disponivel:
            logger.info("Provedor %s pulado: chave não configurada.", provedor.nome)
            tentativas.append(Tentativa(provedor.nome, "sem_chave"))
            continue

        try:
            texto = provedor.responder(mensagens, instrucoes)
        except FalhaDoProvedor as falha:
            tentativas.append(Tentativa(provedor.nome, falha.tipo))
            if falha.temporaria:
                logger.warning("Falha temporária: %s. Tentando o próximo provedor.", falha)
                continue
            logger.error(
                "Erro de configuração: %s. Os outros provedores NÃO foram tentados; "
                "corrija o problema para o assistente voltar a funcionar.",
                falha,
            )
            raise SemResposta(tentativas, erro_de_configuracao=True) from None

        tentativas.append(Tentativa(provedor.nome, "respondeu"))
        logger.info("Provedor %s respondeu.", provedor.nome)
        return Resposta(texto, provedor.nome, tentativas)

    logger.error("Nenhum provedor respondeu (%s).", ", ".join(f"{t.provedor}={t.resultado}" for t in tentativas))
    raise SemResposta(tentativas, erro_de_configuracao=False)
