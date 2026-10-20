"""Brasil em Dados — Censo 2022: dashboard Streamlit (Produto B).

Como abrir (na pasta do projeto):
    streamlit run dashboard/app.py

Este arquivo só monta a TELA. Os dados vêm do pipeline (pasta pipeline/),
preparados em dashboard/dados.py, e os gráficos em dashboard/graficos.py.
É independente do chatbot: não importa nada de assistente/ nem do app.py.
"""

import sys
from datetime import timedelta
from pathlib import Path

# O "streamlit run" coloca só a pasta dashboard/ no caminho do Python; a raiz
# do projeto é necessária para importar o pipeline.
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st

from dashboard import dados, graficos
from pipeline.executar import formatar
from pipeline.fonte import DATA_REFERENCIA, FONTE_CITACAO, URL_TABELA
from pipeline.transformacao import para_csv

st.set_page_config(
    page_title="Brasil em Dados — Censo 2022",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",  # aberta no computador, fechada no celular,
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; max-width: 1200px; }
      [data-testid="stMetricValue"] { font-size: 1.6rem; }
      [data-testid="stMetricValue"] p { white-space: normal; overflow-wrap: anywhere; line-height: 1.25; }
      @media (max-width: 640px) {
        .block-container { padding-left: 1rem; padding-right: 1rem; }
        [data-testid="stMetricValue"] { font-size: 1.35rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

CONFIG_GRAFICOS = {"displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"], "locale": "pt-BR"}


# ---------- Dados (com cache) ----------

@st.cache_data(ttl=timedelta(hours=24), show_spinner="Buscando os dados do IBGE…")
def carregar() -> dados.Base:
    """Uma busca por dia, no máximo, por processo do Streamlit.

    Mexer nos filtros NÃO baixa nada de novo: só a primeira visita (ou a
    primeira depois de 24 h) chama o pipeline. E o pipeline ainda guarda uma
    cópia em dados/, então reabrir o dashboard também não baixa de novo.
    Erros não ficam no cache: "Tentar de novo" faz uma nova tentativa.
    """
    return dados.carregar_base()


def limpar_filtros():
    for chave in ("regioes", "ufs", "municipios"):
        st.session_state[chave] = []


# ---------- Cabeçalho ----------

st.title("Brasil em Dados — Censo 2022")
st.markdown(
    "Explore a **população**, a **área** e a **densidade demográfica** de todos os "
    "municípios brasileiros e compare regiões, UFs e municípios."
)
st.caption(
    f"Fonte: [{FONTE_CITACAO}]({URL_TABELA}). Todos os números se referem ao "
    f"**Censo de 2022** (data de referência: {DATA_REFERENCIA}). "
    "Há um único ano, por isso o painel não mostra tendências nem evolução no tempo."
)

try:
    base = carregar()
except dados.ErroAoCarregar as erro:
    st.error(str(erro), icon="⚠️")
    st.button("Tentar de novo", type="primary")
    st.stop()

todos = base.municipios


# ---------- Filtros (barra lateral) ----------

with st.sidebar:
    st.header("Filtros")
    st.caption("Os filtros funcionam juntos. Deixe vazio para ver tudo.")

    regioes = st.multiselect(
        "Região",
        dados.opcoes_de_regioes(todos),
        key="regioes",
        placeholder="Todas as regiões",
    )

    opcoes_ufs = dados.opcoes_de_ufs(todos, tuple(regioes))
    st.session_state["ufs"] = dados.manter_validos(st.session_state.get("ufs"), opcoes_ufs)
    ufs = st.multiselect(
        "Unidade da Federação",
        list(opcoes_ufs),
        format_func=opcoes_ufs.get,
        key="ufs",
        placeholder="Todas as UFs",
    )

    opcoes_municipios = dados.opcoes_de_municipios(todos, tuple(regioes), tuple(ufs))
    st.session_state["municipios"] = dados.manter_validos(st.session_state.get("municipios"), opcoes_municipios)
    municipios = st.multiselect(
        "Município",
        list(opcoes_municipios),
        format_func=opcoes_municipios.get,
        key="municipios",
        placeholder="Todos os municípios",
        help="Digite parte do nome para procurar.",
    )

    quantidade = st.slider(
        "Municípios no ranking",
        min_value=dados.RANKING_MINIMO,
        max_value=dados.RANKING_MAXIMO,
        value=dados.RANKING_PADRAO,
        step=5,
        key="ranking",
    )
    agrupar_por = st.segmented_control(
        "Comparar gráficos por",
        list(dados.AGRUPAMENTOS),
        format_func=dados.AGRUPAMENTOS.get,
        default="regiao",
        required=True,
        key="agrupar",
    )

    st.button("Limpar filtros", on_click=limpar_filtros, width="stretch")

filtros = dados.Filtros(
    regioes=tuple(regioes),
    ufs=tuple(ufs),
    municipios=tuple(municipios),
    quantidade_ranking=quantidade,
    agrupar_por=agrupar_por,
)
selecao = dados.montar_selecao(todos, filtros)

st.info(dados.descrever_filtros(filtros, todos), icon="🔎")

if selecao.vazia:
    st.warning(
        "Nenhum município corresponde a esta combinação de filtros. "
        "Remova algum filtro ou clique em **Limpar filtros**.",
        icon="🔍",
    )
    st.stop()


# ---------- Indicadores ----------

st.subheader("Indicadores da seleção")
ind = selecao.indicadores


def cartao(coluna, chave, rotulo, valor, complemento=None):
    """Um cartão de indicador; o "?" mostra a definição e a fórmula do pipeline."""
    definicao = ind[chave].definicao
    with coluna:
        st.metric(
            rotulo,
            valor,
            delta=complemento,
            delta_color="off",
            delta_arrow="off",
            help=f"{definicao.nome}: {definicao.definicao} Fórmula: {definicao.formula}. "
                 f"Unidade: {definicao.unidade}. Fonte: {definicao.fonte}.",
            border=True,
            height="stretch",
        )


linha1 = st.columns(3)
cartao(linha1[0], "populacao_total", "População total", f"{formatar(ind['populacao_total'].valor)} pessoas")
cartao(linha1[1], "municipios", "Municípios", formatar(ind["municipios"].valor))
cartao(linha1[2], "maior_populacao", "Município mais populoso", ind["maior_populacao"].detalhe,
       f"{formatar(ind['maior_populacao'].valor)} pessoas")
linha2 = st.columns(3)
cartao(linha2[0], "media_populacao", "População média", f"{formatar(round(ind['media_populacao'].valor))} pessoas",
       f"mediana: {formatar(round(ind['mediana_populacao'].valor))} pessoas")
cartao(linha2[1], "densidade_selecao", "Densidade demográfica", f"{formatar(ind['densidade_selecao'].valor)} hab/km²")
cartao(linha2[2], "participacao_brasil", "Participação no Brasil", f"{formatar(ind['participacao_brasil'].valor)}%",
       "da população do país")


# ---------- Gráficos ----------

st.subheader("Comparações")
st.plotly_chart(
    graficos.grafico_ranking(selecao.ranking),
    config=CONFIG_GRAFICOS,
    alt=f"Gráfico de barras com os {len(selecao.ranking)} municípios mais populosos da seleção.",
)

grupo = dados.AGRUPAMENTOS[selecao.agrupar_por]
esquerda, direita = st.columns(2)
with esquerda:
    st.plotly_chart(
        graficos.grafico_populacao(selecao.grupos, selecao.agrupar_por),
        config=CONFIG_GRAFICOS,
        alt=f"Gráfico de barras com a população por {grupo}.",
    )
with direita:
    st.plotly_chart(
        graficos.grafico_densidade(selecao.grupos, selecao.agrupar_por, selecao.densidade_brasil),
        config=CONFIG_GRAFICOS,
        alt=f"Gráfico de barras com a densidade demográfica por {grupo}, com a linha do Brasil como referência.",
    )
with st.expander(f"Ver os números dos gráficos por {grupo} em tabela"):
    st.dataframe(dados.tabela_de_grupos(selecao.grupos, selecao.agrupar_por), hide_index=True)


# ---------- Tabela e exportação ----------

st.subheader("Municípios da seleção")
st.caption(
    f"{formatar(len(selecao.municipios))} municípios. Clique no nome de uma coluna para ordenar. "
    "O código IBGE é o identificador oficial de cada município."
)
st.dataframe(
    dados.tabela_de_municipios(selecao.municipios),
    hide_index=True,
    height=420,
    alt="Tabela com código IBGE, município, UF, região, população, área e densidade dos municípios filtrados.",
)
st.download_button(
    "Baixar CSV dos dados filtrados",
    data=para_csv(selecao.municipios),
    file_name="censo2022_municipios_filtrados.csv",
    mime="text/csv",
    icon="⬇️",
    help="Separador ';' e vírgula decimal: abre direto no Excel em português.",
    on_click="ignore",
)


# ---------- Qualidade dos dados ----------

st.subheader("Qualidade dos dados")
relatorio = base.relatorio
q1, q2, q3 = st.columns(3)
q1.metric("Municípios recebidos da API", formatar(relatorio.municipios_recebidos), border=True)
q2.metric("Registros válidos", formatar(relatorio.municipios_validos), border=True)
q3.metric("Registros descartados", formatar(relatorio.municipios_descartados), border=True)

detalhes = [
    f"**Fonte oficial:** [{FONTE_CITACAO}]({URL_TABELA}).",
    f"**Data de referência:** {DATA_REFERENCIA} (Censo Demográfico 2022).",
    "**Unidades informadas pela API:** "
    + "; ".join(f"{dados.NOMES_VARIAVEIS.get(coluna, coluna)} em {unidade}" for coluna, unidade in base.unidades.items()) + ".",
    f"**Origem desta carga:** {base.origem}, em {base.carregado_em:%d/%m/%Y às %H:%M}.",
]
if relatorio.descartados:
    detalhes.append("**Motivos de descarte:** " + "; ".join(
        f"{motivo} ({quantidade})" for motivo, quantidade in sorted(relatorio.descartados.items())) + ".")
if relatorio.valores_ausentes:
    detalhes.append("**Valores ausentes:** " + "; ".join(
        f"{dados.NOMES_VARIAVEIS.get(coluna, coluna)} ({quantidade})"
        for coluna, quantidade in sorted(relatorio.valores_ausentes.items())) + ".")
else:
    detalhes.append("**Valores ausentes:** nenhum.")
if relatorio.duplicados_removidos:
    detalhes.append(f"**Duplicados removidos:** {relatorio.duplicados_removidos}.")
detalhes.append(
    "**Conferência da densidade** (valor do IBGE × população ÷ área): "
    + ("todas batem." if base.densidades_inconsistentes == 0
       else f"{base.densidades_inconsistentes} município(s) com diferença acima de 1%.")
)
st.markdown("\n".join(f"- {d}" for d in detalhes))
