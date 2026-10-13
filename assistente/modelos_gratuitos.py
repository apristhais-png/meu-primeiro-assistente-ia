"""Escolha segura de modelos GRATUITOS e de CONVERSA no OpenRouter.

Por que existe: o roteador "openrouter/free" sorteia entre todos os modelos
gratuitos, inclusive classificadores de segurança. Num caso real, ele
mandou a pergunta para "nvidia/nemotron-3.5-content-safety:free", que
devolveu só "User Safety: safe".

Camadas de proteção (cada uma cobre uma falha diferente):
    1. config.yml: só aceita uma LISTA EXPLÍCITA de modelos ":free" e recusa
       roteadores ("openrouter/...") e nomes de modelos que não conversam
       (segurança, moderação, embeddings...). Veja motivo_para_recusar_id.
    2. Catálogo oficial (GET /api/v1/models, público, sem chave e sem custo):
       antes de usar, confere se o modelo existe, se TODOS os preços são
       zero e se ele gera texto. Veja CatalogoOpenRouter.
    3. Pedido ao OpenRouter com provider.max_price = 0: se algum modelo
       deixar de ser gratuito, o OpenRouter recusa em vez de cobrar.
    4. Resposta: um texto com cara de classificação ("User Safety: safe")
       não é aceito; o modelo fica de quarentena e a nova tentativa vai
       para o próximo da lista. Veja parece_classificacao e Quarentena.
"""

import json
import logging
import re
import threading
import time
import urllib.request
from collections.abc import Callable

logger = logging.getLogger("assistente.modelos_gratuitos")

CATALOGO_DO_OPENROUTER = "https://openrouter.ai/api/v1/models"
VALIDADE_DO_CATALOGO = 3600.0  # segundos: o catálogo é baixado de novo a cada hora
ESPERA_APOS_FALHA_NO_CATALOGO = 60.0  # sem acesso ao catálogo: tenta de novo depois disso
TEMPO_MAXIMO_DO_CATALOGO = 4.0  # segundos para baixar o catálogo (sai do prazo da pergunta)
TEMPO_DE_QUARENTENA = 900.0  # 15 min sem usar um modelo que respondeu mal

# Preço máximo aceito no OpenRouter: zero em tudo. Vai em cada pedido.
PRECO_MAXIMO_ZERO = {"prompt": 0, "completion": 0, "request": 0, "image": 0}

# Palavras que indicam um modelo que NÃO é assistente de conversa.
_NAO_CONVERSACIONAIS = re.compile(
    r"safety|guard|moderat|classif|embed|rerank|reward|transcri|whisper|speech|tts|lyria",
    re.IGNORECASE,
)

# Respostas típicas de classificadores (rótulo em vez de explicação).
_RESPOSTAS_DE_CLASSIFICADOR = [
    re.compile(r"\b(user|prompt|response)\s+safety\s*:\s*(safe|unsafe)\b", re.IGNORECASE),
    re.compile(r"^\s*(safe|unsafe)\s*[.!]?\s*$", re.IGNORECASE),
    re.compile(r"^\s*safety\s+categor(y|ies)\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*(label|category|classification)\s*:\s*[\w\- ]{1,40}\s*$", re.IGNORECASE),
]


def nao_conversa(modelo: str) -> bool:
    """True se o nome indica um modelo que não é assistente de conversa."""
    return bool(_NAO_CONVERSACIONAIS.search(modelo))


def motivo_para_recusar_id(modelo: str) -> str | None:
    """Por que este nome de modelo não serve para o Professor (ou None se serve)."""
    if modelo.startswith("openrouter/"):
        return (
            "roteadores como 'openrouter/free' sorteiam entre todos os modelos gratuitos, "
            "inclusive classificadores de segurança; use uma lista explícita de modelos ':free'"
        )
    if not modelo.endswith(":free"):
        return "só são aceitos modelos gratuitos (o nome precisa terminar em ':free')"
    if nao_conversa(modelo):
        return "parece um modelo que não conversa (segurança, moderação, embeddings, áudio...)"
    return None


def parece_classificacao(texto: str) -> bool:
    """True se o texto é um rótulo de classificador em vez de uma explicação."""
    texto = (texto or "").strip()
    if not texto or len(texto) > 300:
        return False  # explicações de verdade são mais longas
    return any(padrao.search(texto) for padrao in _RESPOSTAS_DE_CLASSIFICADOR)


def motivo_para_recusar_no_catalogo(item: dict | None) -> str | None:
    """Confere o item do catálogo oficial: existe, é grátis em tudo e conversa."""
    if item is None:
        return "não está no catálogo do OpenRouter agora"
    precos = item.get("pricing")
    if not isinstance(precos, dict) or not precos:
        return "o catálogo não informa o preço"
    for campo, valor in precos.items():
        try:
            if float(valor) != 0:
                return f"não é gratuito ({campo}={valor})"
        except (TypeError, ValueError):
            return f"preço ilegível ({campo})"
    arquitetura = item.get("architecture") or {}
    saidas = arquitetura.get("output_modalities")
    entradas = arquitetura.get("input_modalities")
    if saidas is not None and list(saidas) != ["text"]:
        return f"não gera só texto ({', '.join(map(str, saidas))})"
    if entradas is not None and "text" not in entradas:
        return "não recebe texto"
    nome = f"{item.get('id', '')} {item.get('name', '')}"
    if _NAO_CONVERSACIONAIS.search(nome):
        return "o catálogo indica um modelo que não conversa"
    return None


def baixar_catalogo(tempo_maximo: float) -> list[dict]:
    """Lista pública de modelos do OpenRouter. Não envia chave nem pergunta."""
    pedido = urllib.request.Request(CATALOGO_DO_OPENROUTER, headers={"Accept": "application/json"})
    with urllib.request.urlopen(pedido, timeout=tempo_maximo) as resposta:  # endereço fixo, https
        return json.load(resposta).get("data", [])


class CatalogoOpenRouter:
    """Guarda o catálogo por uma hora. Seguro para várias perguntas ao mesmo tempo."""

    def __init__(
        self,
        baixar: Callable[[float], list[dict]] = baixar_catalogo,
        relogio: Callable[[], float] = time.monotonic,
    ):
        self._baixar = baixar
        self._relogio = relogio
        self._trava = threading.Lock()
        self._modelos: dict[str, dict] | None = None
        self._baixado_em = 0.0
        self._falhou_em: float | None = None

    def _atualizar_se_preciso(self, tempo_maximo: float) -> None:
        agora = self._relogio()
        if self._modelos is not None and agora - self._baixado_em < VALIDADE_DO_CATALOGO:
            return
        if self._falhou_em is not None and agora - self._falhou_em < ESPERA_APOS_FALHA_NO_CATALOGO:
            return
        try:
            itens = self._baixar(tempo_maximo)
        except Exception as erro:  # noqa: BLE001 - sem catálogo: usa o anterior (se houver)
            self._falhou_em = agora
            logger.warning("Catálogo do OpenRouter indisponível (%s).", type(erro).__name__)
            return
        self._modelos = {item.get("id"): item for item in itens if isinstance(item, dict)}
        self._baixado_em = agora
        self._falhou_em = None

    def avaliar(self, modelos: list[str], tempo_maximo: float = TEMPO_MAXIMO_DO_CATALOGO):
        """Devolve (aprovados, recusados) ou None se o catálogo nunca pôde ser lido.

        recusados: {modelo: motivo}. A ordem dos aprovados é a do config.yml.
        """
        with self._trava:
            self._atualizar_se_preciso(tempo_maximo)
            catalogo = self._modelos
        if catalogo is None:
            return None
        aprovados, recusados = [], {}
        for modelo in modelos:
            motivo = motivo_para_recusar_no_catalogo(catalogo.get(modelo))
            if motivo:
                recusados[modelo] = motivo
            else:
                aprovados.append(modelo)
        return aprovados, recusados


class Quarentena:
    """Modelos que responderam mal ficam um tempo fora da lista."""

    def __init__(self, relogio: Callable[[], float] = time.monotonic):
        self._relogio = relogio
        self._trava = threading.Lock()
        self._ate: dict[str, float] = {}

    def adicionar(self, modelo: str, segundos: float = TEMPO_DE_QUARENTENA) -> None:
        with self._trava:
            self._ate[modelo] = self._relogio() + segundos

    def filtrar(self, modelos: list[str]) -> list[str]:
        """Tira os modelos de quarentena. Se todos estiverem, devolve uma lista VAZIA.

        Um modelo bloqueado nunca volta antes do fim da quarentena: quem chama
        decide o que fazer quando não sobra nenhum.
        """
        agora = self._relogio()
        with self._trava:
            return [m for m in modelos if self._ate.get(m, 0) <= agora]
