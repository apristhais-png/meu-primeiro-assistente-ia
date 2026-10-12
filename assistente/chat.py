"""Junta tudo: limites → histórico → instruções → fallback entre provedores.

Fluxo de cada pergunta (SPEC, seções 4.3 e 5):
    1. Pergunta vazia: pede para escrever algo (nenhuma IA é chamada).
    2. Limites de uso (limites.py): se bloquear, devolve o aviso e
       NENHUMA IA é chamada.
    3. Histórico: só as últimas mensagens da conversa desta pessoa,
       limpas e limitadas (veja preparar_historico).
    4. Fallback (provedores.py): tenta os provedores na ordem, com as
       instruções do config.yml.
    5. Se nenhum responder: mensagem amigável (RF7).

Isolamento das conversas:
    O Assistente não guarda conversa nenhuma. O histórico chega junto com
    cada pergunta (no Gradio, ele fica na sessão do navegador de cada
    pessoa) e é copiado antes de ser usado. Por isso, conversas de pessoas
    diferentes nunca se misturam.
"""

import logging
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from assistente.config import Configuracao
from assistente.limites import MENSAGENS, Limitador
from assistente.provedores import (
    MENSAGEM_DEMORA,
    MENSAGEM_MUITOS_PEDIDOS,
    MENSAGEM_SEM_RESPOSTA,
    Provedor,
    SemResposta,
    criar_provedores,
    id_da_pergunta,
    responder_com_fallback,
)

logger = logging.getLogger("assistente.chat")

MENSAGEM_PERGUNTA_VAZIA = "Escreva sua pergunta para começarmos."
MENSAGEM_AGUARDE = "Aguarde a resposta da pergunta anterior antes de enviar outra."

# Mensagens fixas do próprio assistente. Elas não são respostas da IA, então
# saem do histórico, junto com a pergunta que as gerou.
_MENSAGENS_DO_SISTEMA = {
    MENSAGEM_SEM_RESPOSTA,
    MENSAGEM_DEMORA,
    MENSAGEM_MUITOS_PEDIDOS,
    MENSAGEM_PERGUNTA_VAZIA,
    MENSAGEM_AGUARDE,
}
_INICIOS_DE_AVISOS = tuple(texto.split("{")[0] for texto in MENSAGENS.values())


@dataclass
class Resultado:
    """O que o chat devolve para a tela."""

    texto: str
    liberada: bool  # True se passou pelos limites e foi para o fallback
    motivo_do_bloqueio: str | None = None  # "pergunta_vazia", motivo do limite, ou None
    provedor: str | None = None  # quem respondeu, se alguém respondeu
    situacao: str = "bloqueada"  # para o log: "sucesso", "falha:<tipo>" ou "bloqueada"


# ---------- Histórico ----------

def _texto_do_conteudo(conteudo) -> str | None:
    """Extrai o texto de uma mensagem do Gradio (texto simples ou lista de partes)."""
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        partes = []
        for parte in conteudo:
            if isinstance(parte, str):
                partes.append(parte)
            elif isinstance(parte, Mapping) and isinstance(parte.get("text"), str):
                partes.append(parte["text"])
        return "\n".join(partes) if partes else None
    return None  # arquivos, imagens e outros componentes ficam de fora


def _e_aviso_do_sistema(texto: str) -> bool:
    return texto in _MENSAGENS_DO_SISTEMA or texto.startswith(_INICIOS_DE_AVISOS)


def preparar_historico(historico, maximo_de_mensagens: int, maximo_de_caracteres: int) -> list[dict]:
    """Limpa e limita o histórico que veio do navegador.

    - Só aceita os papéis "user" e "assistant". Um papel "system" enviado
      pelo navegador é descartado: só o config.yml dá instruções à IA.
    - Tira avisos do próprio assistente (limite atingido, falha) e a
      pergunta que os gerou, porque não foram respondidos pela IA.
    - Corta cada mensagem em maximo_de_caracteres, para um histórico
      adulterado não gastar créditos à toa.
    - Mantém só as últimas maximo_de_mensagens, começando por "user".
    - Devolve uma lista NOVA: o histórico original não é alterado.
    """
    limpas: list[dict] = []
    for item in historico or []:
        if not isinstance(item, Mapping):
            continue
        papel = item.get("role")
        texto = _texto_do_conteudo(item.get("content"))
        if papel not in ("user", "assistant") or not texto or not texto.strip():
            continue
        if papel == "assistant" and _e_aviso_do_sistema(texto):
            if limpas and limpas[-1]["role"] == "user":
                limpas.pop()  # a pergunta que não foi respondida pela IA
            continue
        limpas.append({"role": papel, "content": texto[:maximo_de_caracteres]})

    recentes = limpas[-maximo_de_mensagens:]
    while recentes and recentes[0]["role"] != "user":
        recentes = recentes[1:]  # a conversa enviada à IA começa pela pessoa
    return recentes


# ---------- Assistente ----------

class Assistente:
    """Responde perguntas usando o config.yml. Não guarda conversas."""

    def __init__(
        self,
        config: Configuracao,
        provedores: list[Provedor] | None = None,
        limitador: Limitador | None = None,
        ambiente: Mapping[str, str] | None = None,
    ):
        self.config = config
        self.provedores = provedores if provedores is not None else criar_provedores(config, ambiente)
        self.limitador = limitador or Limitador(config.limites)
        # Uma resposta tem no máximo max_tokens (~4 caracteres cada); a folga
        # cobre respostas longas sem deixar o histórico crescer sem limite.
        self.maximo_de_caracteres_por_mensagem = max(
            config.limites.tamanho_maximo_pergunta, config.geracao.max_tokens * 8
        )

    def responder(self, pergunta: str, historico=None, cabecalhos=None) -> Resultado:
        """Responde uma pergunta. "historico" é a conversa desta pessoa até agora.

        Registra no log uma linha de início e uma de fim, com tempos e
        resultado, ligadas por um id curto. Nunca registra o texto.
        """
        marca = id_da_pergunta.set(uuid.uuid4().hex[:8])
        inicio = time.monotonic()
        logger.info("pergunta_inicio id=%s", id_da_pergunta.get())
        try:
            resultado = self._responder(pergunta, historico, cabecalhos)
            logger.info(
                "pergunta_fim id=%s resultado=%s provedor=%s total_ms=%d",
                id_da_pergunta.get(), resultado.situacao, resultado.provedor or "-",
                round((time.monotonic() - inicio) * 1000),
            )
            return resultado
        finally:
            id_da_pergunta.reset(marca)

    def _responder(self, pergunta: str, historico, cabecalhos) -> Resultado:
        pergunta = (pergunta or "").strip()
        if not pergunta:
            return Resultado(MENSAGEM_PERGUNTA_VAZIA, liberada=False, motivo_do_bloqueio="pergunta_vazia")

        # 1. Limites: conferidos ANTES de qualquer IA ser chamada.
        decisao = self.limitador.verificar(pergunta, cabecalhos)
        if not decisao.permitido:
            return Resultado(decisao.mensagem, liberada=False, motivo_do_bloqueio=decisao.motivo)

        # 2. Histórico desta conversa + a pergunta nova.
        mensagens = preparar_historico(
            historico,
            self.config.geracao.max_mensagens_historico,
            self.maximo_de_caracteres_por_mensagem,
        )
        mensagens.append({"role": "user", "content": pergunta})

        # 3. Fallback entre os provedores, com as instruções do config.yml,
        #    dentro do tempo máximo total da pergunta.
        geracao = self.config.geracao
        try:
            resposta = responder_com_fallback(
                self.provedores, mensagens, self.config.instrucoes,
                tempo_maximo_total=geracao.tempo_maximo_total_segundos,
                timeout_por_tentativa=geracao.timeout_segundos,
                tentativas_por_provedor=geracao.tentativas_por_provedor,
            )
        except SemResposta as erro:
            ultima = next((t.resultado for t in reversed(erro.tentativas) if t.resultado != "sem_chave"), "sem_provedor")
            return Resultado(erro.mensagem_para_pessoa, liberada=True, situacao=f"falha:{ultima}")
        return Resultado(resposta.texto, liberada=True, provedor=resposta.provedor, situacao="sucesso")
