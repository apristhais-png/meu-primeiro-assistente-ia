"""INDICADORES: os números mostrados no dashboard, cada um com definição.

Todos vêm de UM ano (Censo 2022). Não há indicadores de variação ou
tendência, porque a fonte não tem uma série no tempo.

Dados de origem (da API): população, área e densidade de cada município.
Indicadores derivados (calculados aqui): somas, contagens, médias e
participações sobre uma seleção de municípios.
"""

from dataclasses import dataclass

import pandas as pd

from pipeline.fonte import FONTE_CITACAO, PERIODO


@dataclass(frozen=True)
class Definicao:
    chave: str
    nome: str
    definicao: str
    formula: str
    unidade: str
    fonte: str = FONTE_CITACAO
    periodo: str = PERIODO


@dataclass(frozen=True)
class Indicador:
    definicao: Definicao
    valor: float | int | None
    detalhe: str = ""  # ex.: qual município tem a maior população


DEFINICOES = {
    d.chave: d
    for d in [
        Definicao(
            "populacao_total",
            "População total da seleção",
            "Soma da população residente dos municípios selecionados.",
            "Σ população",
            "pessoas",
        ),
        Definicao(
            "municipios",
            "Municípios analisados",
            "Quantidade de municípios na seleção.",
            "contagem de municípios",
            "municípios",
        ),
        Definicao(
            "maior_populacao", "Maior população", "Município mais populoso da seleção.", "máx(população)", "pessoas"
        ),
        Definicao(
            "media_populacao",
            "População média por município",
            "Média aritmética da população dos municípios selecionados.",
            "Σ população ÷ nº de municípios",
            "pessoas",
        ),
        Definicao(
            "mediana_populacao",
            "População mediana por município",
            "Valor do meio: metade dos municípios tem menos e metade tem mais.",
            "mediana(população)",
            "pessoas",
        ),
        Definicao(
            "densidade_selecao",
            "Densidade demográfica da seleção",
            "População da seleção dividida pela área da seleção (só municípios com área informada).",
            "Σ população ÷ Σ área",
            "hab/km²",
        ),
        Definicao(
            "participacao_brasil",
            "Participação na população do Brasil",
            "Parte da população do Brasil que mora nos municípios selecionados.",
            "Σ população da seleção ÷ Σ população de todos os municípios × 100",
            "%",
        ),
    ]
}


def calcular(selecao: pd.DataFrame, todos: pd.DataFrame) -> dict[str, Indicador]:
    """Indicadores da seleção. "todos" é o Brasil inteiro (para a participação)."""

    def ind(chave, valor, detalhe=""):
        return Indicador(DEFINICOES[chave], valor, detalhe)

    if selecao.empty:
        return {chave: ind(chave, None) for chave in DEFINICOES}

    populacao = int(selecao["populacao"].sum())
    maior = selecao.loc[selecao["populacao"].idxmax()]
    com_area = selecao.dropna(subset=["area_km2"])
    area = float(com_area["area_km2"].sum())
    total_brasil = int(todos["populacao"].sum())
    return {
        "populacao_total": ind("populacao_total", populacao),
        "municipios": ind("municipios", len(selecao)),
        "maior_populacao": ind(
            "maior_populacao", int(maior["populacao"]), f"{maior['municipio']} ({maior['uf_sigla']})"
        ),
        "media_populacao": ind("media_populacao", float(selecao["populacao"].mean())),
        "mediana_populacao": ind("mediana_populacao", float(selecao["populacao"].median())),
        "densidade_selecao": ind("densidade_selecao", int(com_area["populacao"].sum()) / area if area > 0 else None),
        "participacao_brasil": ind("participacao_brasil", populacao / total_brasil * 100 if total_brasil else None),
    }


def densidades_inconsistentes(df: pd.DataFrame, tolerancia: float = 0.01) -> pd.DataFrame:
    """Municípios em que a densidade da API não bate com população ÷ área.

    Conferência de qualidade: a densidade publicada (arredondada) deve ficar
    a no máximo 1% (ou 0,01 hab/km²) do valor recalculado.
    """
    dados = df.dropna(subset=["area_km2", "densidade_hab_km2"])
    recalculada = dados["populacao"] / dados["area_km2"]
    diferenca = (dados["densidade_hab_km2"] - recalculada).abs()
    limite = (recalculada * tolerancia).clip(lower=0.01)
    return dados[diferenca > limite]
