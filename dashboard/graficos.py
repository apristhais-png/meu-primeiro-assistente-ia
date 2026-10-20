"""GRÁFICOS do dashboard (Plotly). Só desenham: recebem tabelas prontas.

Escolhas de visualização:
- Barras horizontais: os nomes de municípios e regiões ficam legíveis,
  inclusive no celular, e a comparação é feita pelo comprimento da barra.
- Uma cor só (cada gráfico tem uma única série): a cor não carrega
  informação extra, então não há legenda. O título diz o que é medido.
- Valor escrito na ponta de cada barra e no "passar o mouse", com números no
  padrão brasileiro (1.234.567 e 12,3).
- Nada de linhas no tempo: a fonte tem um único ano (Censo 2022).
"""

import pandas as pd
import plotly.graph_objects as go

COR_BARRA = "#2a78d6"  # azul com contraste suficiente nos temas claro e escuro
COR_REFERENCIA = "#898781"  # cinza neutro para a linha do Brasil
ALTURA_POR_BARRA = 30
ALTURA_MINIMA = 260
ROTULOS_GRUPO = {"regiao": "Região", "uf_sigla": "UF"}


def _altura(barras: int) -> int:
    return max(ALTURA_MINIMA, 90 + ALTURA_POR_BARRA * barras)


def _barras(
    nomes: pd.Series,
    valores: pd.Series,
    titulo: str,
    eixo_x: str,
    formato: str,
    unidade: str,
) -> go.Figure:
    """Barras horizontais, a maior em cima, com valor na ponta."""
    figura = go.Figure(
        go.Bar(
            x=valores,
            y=nomes,
            orientation="h",
            marker={"color": COR_BARRA, "cornerradius": 4},
            text=valores,
            texttemplate=f"%{{x:{formato}}}",
            textposition="outside",
            cliponaxis=False,
            hovertemplate=f"<b>%{{y}}</b><br>%{{x:{formato}}} {unidade}<extra></extra>",
        )
    )
    maior = float(valores.max()) if len(valores) else 0.0
    figura.update_layout(
        title={"text": titulo, "x": 0, "xanchor": "left"},
        separators=",.",  # vírgula decimal e ponto no milhar
        height=_altura(len(nomes)),
        margin={"l": 8, "r": 24, "t": 56, "b": 48},
        bargap=0.3,
        showlegend=False,
        xaxis={
            "title": {"text": eixo_x},
            "tickformat": ",~s" if maior >= 1_000_000 else ",.0f",
            "range": [0, maior * 1.22 if maior else 1],  # espaço para o valor na ponta
            "fixedrange": True,
        },
        yaxis={"autorange": "reversed", "automargin": True, "fixedrange": True},
        dragmode=False,
    )
    return figura


def grafico_ranking(ranking: pd.DataFrame) -> go.Figure:
    """Os municípios mais populosos da seleção."""
    nomes = ranking["municipio"] + " (" + ranking["uf_sigla"] + ")"
    return _barras(
        nomes,
        ranking["populacao"],
        titulo=f"Os {len(ranking)} municípios mais populosos",
        eixo_x="População residente (pessoas)",
        formato=",.0f",
        unidade="pessoas",
    )


def grafico_populacao(grupos: pd.DataFrame, agrupar_por: str) -> go.Figure:
    """População total de cada região ou UF da seleção."""
    dados = grupos.sort_values("populacao", ascending=False)
    rotulo = ROTULOS_GRUPO[agrupar_por]
    return _barras(
        dados[agrupar_por],
        dados["populacao"],
        titulo=f"População por {rotulo}",
        eixo_x="População residente (pessoas)",
        formato=",.0f",
        unidade="pessoas",
    )


def grafico_densidade(grupos: pd.DataFrame, agrupar_por: str, densidade_brasil: float | None) -> go.Figure:
    """Densidade de cada região ou UF (população ÷ área), com a do Brasil como referência."""
    dados = grupos.dropna(subset=["densidade_hab_km2"]).sort_values("densidade_hab_km2", ascending=False)
    rotulo = ROTULOS_GRUPO[agrupar_por]
    figura = _barras(
        dados[agrupar_por],
        dados["densidade_hab_km2"],
        titulo=f"Densidade demográfica por {rotulo}",
        eixo_x="Habitantes por km²",
        formato=",.1f",
        unidade="hab/km²",
    )
    figura.update_xaxes(tickformat=",.0f")
    if densidade_brasil:
        texto = f"Brasil: {densidade_brasil:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        figura.add_vline(
            x=densidade_brasil,
            line={"color": COR_REFERENCIA, "dash": "dash", "width": 1.5},
            layer="below",  # a linha passa por trás das barras e dos valores
        )
        figura.update_layout(title_subtitle_text=f"Linha tracejada: {texto} hab/km² (referência)", margin={"t": 76})
        limite = max(float(dados["densidade_hab_km2"].max()) if len(dados) else 0.0, densidade_brasil)
        figura.update_xaxes(range=[0, limite * 1.22])
    return figura
