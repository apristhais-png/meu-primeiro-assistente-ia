"""EXTRAÇÃO: busca os dados na API do IBGE com requests (HTTP GET).

- Timeout explícito (conexão e leitura).
- Confere o status HTTP e transforma cada falha numa mensagem clara.
- Repete UMA vez só em falhas temporárias (timeout, conexão, 429, 5xx).
- Confere se a resposta é um JSON válido e não vazio.
- Cache opcional em arquivo, para não baixar de novo a cada execução.
- Logs só com dados técnicos públicos (URL, status, tempo); a API é pública
  e não usa chave, então não há segredo para vazar.
"""

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path

import requests

from pipeline.fonte import url_da_consulta

logger = logging.getLogger("pipeline.extracao")

TEMPO_LIMITE = (10, 60)  # segundos: (para conectar, para receber a resposta)
TENTATIVAS = 2  # 1 tentativa + 1 repetição em falha temporária
ESPERA_ENTRE_TENTATIVAS = 2.0  # segundos

_MENSAGENS_POR_STATUS = {
    400: "a API do IBGE recusou o pedido (400): confira a URL e os parâmetros",
    404: "a tabela ou o recurso não foi encontrado na API do IBGE (404)",
    429: "a API do IBGE recebeu pedidos demais (429): tente novamente em alguns minutos",
}


class ErroDeExtracao(Exception):
    """Não foi possível obter os dados. "temporario" indica se vale tentar depois."""

    def __init__(self, mensagem: str, temporario: bool = False, status: int | None = None):
        super().__init__(mensagem)
        self.temporario = temporario
        self.status = status


def _baixar(url: str, sessao: requests.Session) -> object:
    """Uma requisição GET. Devolve o JSON já convertido ou lança ErroDeExtracao."""
    inicio = time.monotonic()
    try:
        resposta = sessao.get(url, timeout=TEMPO_LIMITE, headers={"Accept": "application/json"})
    except requests.Timeout:
        raise ErroDeExtracao("a API do IBGE demorou demais para responder", temporario=True) from None
    except requests.ConnectionError:
        raise ErroDeExtracao("não foi possível conectar à API do IBGE (sem internet?)", temporario=True) from None
    except requests.RequestException as erro:
        raise ErroDeExtracao(f"falha na requisição ({type(erro).__name__})") from None

    duracao_ms = round((time.monotonic() - inicio) * 1000)
    logger.info("ibge_get status=%s duracao_ms=%d tamanho=%d", resposta.status_code, duracao_ms, len(resposta.content))

    status = resposta.status_code
    if status >= 500:
        raise ErroDeExtracao(f"a API do IBGE está com problemas ({status})", temporario=True, status=status)
    if status in _MENSAGENS_POR_STATUS:
        raise ErroDeExtracao(_MENSAGENS_POR_STATUS[status], temporario=status == 429, status=status)
    if status != 200:
        raise ErroDeExtracao(f"resposta inesperada da API do IBGE ({status})", status=status)

    try:
        dados = resposta.json()
    except ValueError:
        raise ErroDeExtracao("a API do IBGE respondeu, mas não com um JSON válido") from None
    if not dados:
        raise ErroDeExtracao("a API do IBGE devolveu uma resposta vazia")
    return dados


def extrair(
    url: str | None = None,
    sessao: requests.Session | None = None,
    cache: Path | None = None,
    dormir: Callable[[float], None] = time.sleep,
) -> object:
    """Baixa o JSON bruto da fonte oficial.

    Com "cache", reaproveita um arquivo salvo antes (e salva depois de baixar).
    """
    if cache is not None and cache.is_file():
        logger.info("ibge_cache usando=%s", cache)
        return json.loads(cache.read_text(encoding="utf-8"))

    url = url or url_da_consulta()
    sessao = sessao or requests.Session()
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            dados = _baixar(url, sessao)
            break
        except ErroDeExtracao as erro:
            if not erro.temporario or tentativa == TENTATIVAS:
                raise
            logger.warning("ibge_get falha_temporaria=%s tentando_de_novo_em=%.0fs", erro, ESPERA_ENTRE_TENTATIVAS)
            dormir(ESPERA_ENTRE_TENTATIVAS)

    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return dados
