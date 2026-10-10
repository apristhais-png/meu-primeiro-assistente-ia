"""Limites de uso no servidor e identificação segura pelo IP (SPEC, seção 4.3).

Ordem da conferência, ANTES de chamar qualquer IA:
    1. Tamanho da pergunta.
    2. Limites GLOBAIS (minuto e dia), que valem sempre.
    3. Se identificar_por_ip for true e a pessoa for identificada com
       segurança: limites POR PESSOA (minuto e dia).
    4. Se tudo estiver dentro do limite, conta +1 e libera.

Identificação pelo IP (só quando identificar_por_ip: true):
    - Nunca usa o IP da conexão: no Hugging Face, ele é o do proxy.
    - Do X-Forwarded-For, usa SOMENTE o último item, que é o escrito pelo
      proxy do Hugging Face. O começo da lista pode ser inventado.
    - Só aceita IP válido e público. Caso contrário, a pessoa fica "não
      identificada" e valem só os limites globais.
    - O IP vira um identificador anônimo; contadores e logs nunca guardam o IP.

Os contadores ficam na memória: se o app reiniciar, voltam a zero.
"""

import hashlib
import hmac
import ipaddress
import logging
import secrets
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from assistente.config import Limites

logger = logging.getLogger("assistente.limites")

FUSO_DE_BRASILIA = ZoneInfo("America/Sao_Paulo")
JANELA_DE_UM_MINUTO = 60.0

MENSAGENS = {
    "pergunta_longa": "Sua pergunta ficou muito longa. Tente resumir em até {tamanho} caracteres.",
    "global_minuto": "O assistente está muito movimentado agora. Aguarde um minuto e tente de novo.",
    "global_dia": "O limite de uso de hoje foi atingido. Volte amanhã!",
    "pessoa_minuto": "Você fez muitas perguntas seguidas. Aguarde um minuto e tente de novo.",
    "pessoa_dia": "Você atingiu o limite de perguntas de hoje. Volte amanhã!",
}


@dataclass
class Decisao:
    """Resultado da conferência de uma pergunta."""

    permitido: bool
    motivo: str | None = None  # uma das chaves de MENSAGENS, quando bloqueia
    mensagem: str | None = None  # o que a pessoa vê, quando bloqueia
    pessoa: str | None = None  # identificador anônimo, ou None se não identificada
    itens_x_forwarded_for: int = 0


# ---------- Identificação ----------

def _valores_do_x_forwarded_for(cabecalhos) -> list[str]:
    """Lê todas as linhas X-Forwarded-For, na ordem em que chegaram.

    Se o pedido tiver mais de uma linha (uma inventada pela pessoa e outra
    escrita pelo proxy), juntamos todas: a última continua sendo a do proxy.
    """
    if cabecalhos is None:
        return []
    if hasattr(cabecalhos, "getlist"):  # cabeçalhos do Gradio/Starlette
        return list(cabecalhos.getlist("x-forwarded-for"))
    return [valor for nome, valor in cabecalhos.items() if nome.lower() == "x-forwarded-for"]


def ip_confiavel(cabecalhos) -> tuple[str | None, int]:
    """Devolve (IP confiável ou None, quantidade de itens no X-Forwarded-For)."""
    itens = [item.strip() for valor in _valores_do_x_forwarded_for(cabecalhos) for item in valor.split(",")]
    if not itens:
        return None, 0
    ultimo = itens[-1]  # o único item escrito pelo proxy do Hugging Face
    try:
        ip = ipaddress.ip_address(ultimo)
    except ValueError:
        return None, len(itens)
    if not ip.is_global:  # recusa IPs privados, locais e reservados
        return None, len(itens)
    return ip.compressed, len(itens)


# ---------- Limitador ----------

class Limitador:
    """Confere e conta as perguntas. Seguro para vários pedidos ao mesmo tempo."""

    def __init__(
        self,
        limites: Limites,
        relogio: Callable[[], float] = time.time,
        tempero: bytes | None = None,
    ):
        self.limites = limites
        self._relogio = relogio  # nos testes, um relógio falso permite "adiantar o tempo"
        # "Tempero" aleatório, criado a cada início do app e guardado só na memória.
        self._tempero = tempero if tempero is not None else secrets.token_bytes(32)
        self._trava = threading.Lock()

        self._global_minuto: deque[float] = deque()
        self._pessoa_minuto: dict[str, deque[float]] = {}
        self._dia: date | None = None
        self._global_dia = 0
        self._pessoa_dia: dict[str, int] = {}

    def identificador_anonimo(self, ip: str) -> str:
        """Código embaralhado a partir do IP. Não dá para voltar ao IP sem o tempero."""
        return hmac.new(self._tempero, ip.encode(), hashlib.sha256).hexdigest()[:12]

    def verificar(self, pergunta: str, cabecalhos=None) -> Decisao:
        """Confere os limites. Se a pergunta for liberada, já conta +1."""
        itens = 0
        pessoa = None
        if self.limites.identificar_por_ip:
            ip, itens = ip_confiavel(cabecalhos)
            pessoa = self.identificador_anonimo(ip) if ip else None
        else:
            _, itens = ip_confiavel(cabecalhos)

        with self._trava:
            agora = self._relogio()
            self._virar_o_dia_se_preciso(agora)
            self._limpar_janelas(agora)
            motivo = self._motivo_do_bloqueio(pergunta, pessoa)
            if motivo is None:
                self._contar(agora, pessoa)

        decisao = Decisao(
            permitido=motivo is None,
            motivo=motivo,
            mensagem=self._mensagem(motivo),
            pessoa=pessoa,
            itens_x_forwarded_for=itens,
        )
        self._registrar(decisao)
        return decisao

    # ----- partes internas -----

    def _motivo_do_bloqueio(self, pergunta: str, pessoa: str | None) -> str | None:
        limites = self.limites
        if len(pergunta) > limites.tamanho_maximo_pergunta:
            return "pergunta_longa"
        if len(self._global_minuto) >= limites.perguntas_por_minuto_total:
            return "global_minuto"
        if self._global_dia >= limites.perguntas_por_dia_total:
            return "global_dia"
        if pessoa is not None:
            if len(self._pessoa_minuto.get(pessoa, ())) >= limites.perguntas_por_minuto_por_pessoa:
                return "pessoa_minuto"
            if self._pessoa_dia.get(pessoa, 0) >= limites.perguntas_por_dia_por_pessoa:
                return "pessoa_dia"
        return None

    def _contar(self, agora: float, pessoa: str | None) -> None:
        self._global_minuto.append(agora)
        self._global_dia += 1
        if pessoa is not None:
            self._pessoa_minuto.setdefault(pessoa, deque()).append(agora)
            self._pessoa_dia[pessoa] = self._pessoa_dia.get(pessoa, 0) + 1

    def _virar_o_dia_se_preciso(self, agora: float) -> None:
        hoje = datetime.fromtimestamp(agora, FUSO_DE_BRASILIA).date()
        if hoje != self._dia:
            self._dia = hoje
            self._global_dia = 0
            self._pessoa_dia.clear()

    def _limpar_janelas(self, agora: float) -> None:
        """Esquece as perguntas com mais de 1 minuto."""
        limite = agora - JANELA_DE_UM_MINUTO
        while self._global_minuto and self._global_minuto[0] <= limite:
            self._global_minuto.popleft()
        for pessoa in list(self._pessoa_minuto):
            janela = self._pessoa_minuto[pessoa]
            while janela and janela[0] <= limite:
                janela.popleft()
            if not janela:
                del self._pessoa_minuto[pessoa]  # não acumula memória à toa

    def _mensagem(self, motivo: str | None) -> str | None:
        if motivo is None:
            return None
        return MENSAGENS[motivo].format(tamanho=self.limites.tamanho_maximo_pergunta)

    @staticmethod
    def _registrar(decisao: Decisao) -> None:
        # Nunca registra o IP nem o texto da pergunta.
        quem = decisao.pessoa or "não identificada"
        if decisao.permitido:
            logger.info(
                "Pergunta liberada | pessoa=%s | itens_x_forwarded_for=%d",
                quem,
                decisao.itens_x_forwarded_for,
            )
        else:
            logger.info(
                "Limite atingido (%s) | pessoa=%s | itens_x_forwarded_for=%d | nenhuma IA chamada",
                decisao.motivo,
                quem,
                decisao.itens_x_forwarded_for,
            )
