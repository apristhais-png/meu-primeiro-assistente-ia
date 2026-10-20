"""Testes do dashboard "Brasil em Dados — Censo 2022" (Streamlit + Plotly).

DADOS DE TESTE FICTÍCIOS: os mesmos municípios "Cidade Teste ..." dos testes
do pipeline (não existem; só os códigos seguem o formato do IBGE). Nenhum
teste acessa a internet: a API do IBGE é sempre simulada.
"""

import json
import socket
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from dashboard import dados, graficos
from pipeline import extracao
from pipeline.extracao import ErroDeExtracao
from pipeline.indicadores import calcular
from pipeline.transformacao import agregar, maiores, montar_dataframe
from pipeline.validacao import validar
from tests.test_pipeline import MUNICIPIOS_FICTICIOS, resposta_ibge

RAIZ = Path(__file__).resolve().parents[1]
APP = str(RAIZ / "dashboard" / "app.py")


@pytest.fixture(autouse=True)
def sem_internet(monkeypatch):
    def proibido(*args, **kwargs):
        raise RuntimeError("Acesso à rede bloqueado nos testes")

    monkeypatch.setattr(socket.socket, "connect", proibido)
    monkeypatch.setattr(socket, "create_connection", proibido)


@pytest.fixture
def todos():
    return montar_dataframe(validar(resposta_ibge()).registros)


@pytest.fixture
def api_simulada(monkeypatch, tmp_path):
    """A "API" devolve os municípios fictícios; a cópia local vai para uma pasta temporária."""
    chamadas = []

    def extrair_falso(cache=None, **kwargs):
        chamadas.append(cache)
        return resposta_ibge()

    monkeypatch.setattr(dados, "CAMINHO_CACHE", tmp_path / "ibge.json")
    monkeypatch.setattr(dados, "extrair", extrair_falso)
    return chamadas


# =============================================================
# Carga dos dados (pipeline → dashboard)
# =============================================================


def test_carregar_base_usa_o_pipeline_e_traz_relatorio_de_qualidade(api_simulada):
    base = dados.carregar_base()
    assert len(base.municipios) == 5
    assert base.relatorio.municipios_recebidos == 5
    assert base.relatorio.municipios_validos == 5
    assert base.unidades["populacao"] == "Pessoas"
    assert base.densidades_inconsistentes == 0
    assert base.origem == "API do IBGE"


def test_carregar_base_reaproveita_a_copia_local_sem_baixar(tmp_path, monkeypatch):
    copia = tmp_path / "ibge.json"
    copia.write_text(json.dumps(resposta_ibge()), encoding="utf-8")
    monkeypatch.setattr(extracao, "_baixar", lambda *a: pytest.fail("não deveria baixar"))
    base = dados.carregar_base(cache=copia)
    assert base.origem == "cópia local"
    assert len(base.municipios) == 5


@pytest.mark.parametrize("conteudo", ["{isto não é json", json.dumps([{"formato": "errado"}])])
def test_copia_local_estragada_e_trocada_por_um_download_novo(tmp_path, monkeypatch, conteudo):
    copia = tmp_path / "ibge.json"
    copia.write_text(conteudo, encoding="utf-8")
    monkeypatch.setattr(extracao, "_baixar", lambda *a: resposta_ibge())
    base = dados.carregar_base(cache=copia)
    assert base.origem == "API do IBGE"
    assert json.loads(copia.read_text(encoding="utf-8")) == resposta_ibge()


@pytest.mark.parametrize(
    ("erro", "mensagem"),
    [
        (ErroDeExtracao("a API do IBGE demorou demais para responder", temporario=True), dados.MENSAGEM_SEM_CONEXAO),
        (
            ErroDeExtracao("a API do IBGE está com problemas (503)", temporario=True, status=503),
            dados.MENSAGEM_SEM_CONEXAO,
        ),
        (ErroDeExtracao("consulta não encontrada (404)", status=404), dados.MENSAGEM_RECUSADA),
        (ErroDeExtracao("a API do IBGE respondeu, mas não com um JSON válido"), dados.MENSAGEM_FALHA),
    ],
)
def test_erros_de_extracao_viram_mensagens_amigaveis(tmp_path, monkeypatch, erro, mensagem):
    def falha(*args):
        raise erro

    monkeypatch.setattr(extracao, "_baixar", falha)
    monkeypatch.setattr(extracao, "ESPERA_ENTRE_TENTATIVAS", 0)
    with pytest.raises(dados.ErroAoCarregar) as capturado:
        dados.carregar_base(cache=tmp_path / "ibge.json")
    assert str(capturado.value) == mensagem
    assert str(erro) not in str(capturado.value)  # o detalhe técnico vai só para o log


def test_resposta_fora_do_formato_vira_mensagem_amigavel(tmp_path, monkeypatch):
    monkeypatch.setattr(extracao, "_baixar", lambda *a: [{"formato": "errado"}])
    with pytest.raises(dados.ErroAoCarregar, match="formato diferente"):
        dados.carregar_base(cache=tmp_path / "ibge.json")


# =============================================================
# Filtros
# =============================================================


def test_filtros_recusam_valores_invalidos():
    with pytest.raises(ValueError, match="agrupamento"):
        dados.Filtros(agrupar_por="municipio")
    with pytest.raises(ValueError, match="ranking"):
        dados.Filtros(quantidade_ranking=dados.RANKING_MAXIMO + 1)
    assert not dados.Filtros().ativos
    assert dados.Filtros(ufs=("SP",)).ativos


def test_opcoes_de_regioes_seguem_a_ordem_oficial(todos):
    assert dados.opcoes_de_regioes(todos) == ["Norte", "Nordeste", "Sudeste", "Sul"]


def test_opcoes_de_ufs_dependem_da_regiao(todos):
    assert dados.opcoes_de_ufs(todos) == {
        "AM": "AM — Amazonas",
        "BA": "BA — Bahia",
        "PR": "PR — Paraná",
        "RJ": "RJ — Rio de Janeiro",
        "SP": "SP — São Paulo",
    }
    assert list(dados.opcoes_de_ufs(todos, ("Sudeste",))) == ["RJ", "SP"]


def test_opcoes_de_municipios_tem_codigo_ibge_e_nome_com_uf(todos):
    opcoes = dados.opcoes_de_municipios(todos, ufs=("SP", "RJ"))
    assert opcoes == {"3500001": "Cidade Teste Grande (SP)", "3300002": "Cidade Teste Média (RJ)"}
    assert len(dados.opcoes_de_municipios(todos)) == len(MUNICIPIOS_FICTICIOS)


def test_manter_validos_descarta_escolhas_que_sairam_das_opcoes():
    assert dados.manter_validos(["SP", "AM"], {"SP": "...", "RJ": "..."}) == ["SP"]
    assert dados.manter_validos(None, {"SP": "..."}) == []


def test_filtros_combinados_regiao_uf_e_municipio(todos):
    filtros = dados.Filtros(regioes=("Sudeste", "Sul"), ufs=("SP", "PR"), municipios=("4100003",))
    selecao = dados.montar_selecao(todos, filtros)
    assert selecao.municipios["codigo_ibge"].tolist() == ["4100003"]
    assert selecao.indicadores["populacao_total"].valor == 100000


def test_selecao_usa_os_indicadores_e_totais_do_pipeline(todos):
    filtros = dados.Filtros(regioes=("Sudeste",), agrupar_por="uf_sigla", quantidade_ranking=5)
    selecao = dados.montar_selecao(todos, filtros)
    sudeste = todos[todos["regiao"] == "Sudeste"].reset_index(drop=True)

    esperados = calcular(sudeste, todos)
    assert {k: i.valor for k, i in selecao.indicadores.items()} == {k: i.valor for k, i in esperados.items()}
    assert selecao.indicadores["populacao_total"].valor == 1_300_000
    assert selecao.indicadores["participacao_brasil"].valor == pytest.approx(1_300_000 / 1_460_000 * 100)
    pd.testing.assert_frame_equal(selecao.grupos, agregar(sudeste, "uf_sigla"))
    assert selecao.agrupar_por == "uf_sigla"
    assert selecao.densidade_brasil == pytest.approx(1_460_000 / 14_300)


def test_ranking_respeita_a_quantidade_e_a_ordem(todos):
    selecao = dados.montar_selecao(todos, dados.Filtros(quantidade_ranking=5))
    pd.testing.assert_frame_equal(selecao.ranking, maiores(todos, 5))
    assert selecao.ranking["populacao"].is_monotonic_decreasing


def test_selecao_vazia_nao_quebra_e_nao_inventa_numeros(todos):
    selecao = dados.montar_selecao(todos, dados.Filtros(regioes=("Norte",), ufs=("SP",)))
    assert selecao.vazia
    assert all(indicador.valor is None for indicador in selecao.indicadores.values())
    assert selecao.ranking.empty and selecao.grupos.empty


def test_descrever_filtros(todos):
    assert dados.descrever_filtros(dados.Filtros(), todos) == "Mostrando todo o Brasil."
    texto = dados.descrever_filtros(
        dados.Filtros(regioes=("Sudeste",), ufs=("SP",), municipios=("3500001", "3300002", "4100003", "2900004")),
        todos,
    )
    assert texto.startswith("Filtros: regiões: Sudeste; UFs: SP; municípios: ")
    assert "Cidade Teste Grande (SP)" in texto and "e mais 1" in texto


# =============================================================
# Tabelas e exportação
# =============================================================


def test_tabela_de_municipios_tem_codigo_oficial_e_numeros_no_padrao_brasileiro(todos):
    estilo = dados.tabela_de_municipios(todos)
    assert list(estilo.data.columns) == list(dados.COLUNAS_TABELA.values())
    assert estilo.data["Código IBGE"].iloc[0] == "3500001"
    html = estilo.to_html()
    assert "1.000.000" in html  # população com ponto no milhar
    assert "2.000,00" in html  # densidade com vírgula decimal
    # Só a aparência muda: os valores continuam numéricos (ordenação correta).
    assert estilo.data["População (pessoas)"].dtype == "int64"


def test_tabela_de_grupos(todos):
    estilo = dados.tabela_de_grupos(agregar(todos, "regiao"), "regiao")
    assert list(estilo.data.columns) == [
        "Região",
        "Municípios",
        "População (pessoas)",
        "Área (km²)",
        "Densidade (hab/km²)",
    ]
    assert "1.300.000" in estilo.to_html()


# =============================================================
# Gráficos
# =============================================================


def test_grafico_ranking(todos):
    figura = graficos.grafico_ranking(maiores(todos, 3))
    barras = figura.data[0]
    assert list(barras.y) == ["Cidade Teste Grande (SP)", "Cidade Teste Média (RJ)", "Cidade Teste Sul (PR)"]
    assert list(barras.x) == [1_000_000, 300_000, 100_000]
    assert barras.orientation == "h"
    assert figura.layout.title.text == "Os 3 municípios mais populosos"
    assert figura.layout.xaxis.title.text == "População residente (pessoas)"
    assert figura.layout.separators == ",."  # números no padrão brasileiro
    assert figura.layout.yaxis.autorange == "reversed"  # o maior fica em cima
    assert "pessoas" in barras.hovertemplate
    assert not figura.layout.showlegend


def test_grafico_populacao_por_uf(todos):
    figura = graficos.grafico_populacao(agregar(todos, "uf_sigla"), "uf_sigla")
    assert list(figura.data[0].y) == ["SP", "RJ", "PR", "BA", "AM"]
    assert figura.layout.title.text == "População por UF"


def test_grafico_densidade_com_referencia_do_brasil(todos):
    grupos = agregar(todos, "regiao")
    figura = graficos.grafico_densidade(grupos, "regiao", densidade_brasil=102.1)
    assert figura.layout.title.text == "Densidade demográfica por Região"
    assert figura.layout.xaxis.title.text == "Habitantes por km²"
    assert list(figura.data[0].y) == ["Sudeste", "Sul", "Nordeste", "Norte"]
    assert len(figura.layout.shapes) == 1 and figura.layout.shapes[0].x0 == 102.1
    assert "Brasil: 102,1 hab/km²" in figura.layout.title.subtitle.text


def test_grafico_densidade_sem_referencia_e_graficos_com_tabela_vazia(todos):
    figura = graficos.grafico_densidade(agregar(todos, "regiao"), "regiao", densidade_brasil=None)
    assert len(figura.layout.shapes) == 0
    vazio = graficos.grafico_ranking(todos.iloc[0:0])
    assert len(vazio.data[0].x) == 0
    assert vazio.layout.height == graficos.ALTURA_MINIMA


def test_altura_do_grafico_cresce_com_o_numero_de_barras():
    assert graficos._altura(1) == graficos.ALTURA_MINIMA
    assert graficos._altura(50) == 90 + graficos.ALTURA_POR_BARRA * 50


# =============================================================
# Tela (Streamlit AppTest, API simulada)
# =============================================================


@pytest.fixture
def app(api_simulada):
    st.cache_data.clear()
    tela = AppTest.from_file(APP, default_timeout=60)
    tela.run()
    yield tela
    st.cache_data.clear()


def _metricas(tela) -> dict[str, str]:
    return {m.label: m.value for m in tela.metric}


def test_tela_inicial_mostra_cabecalho_indicadores_graficos_tabela_e_qualidade(app):
    assert not app.exception
    assert app.title[0].value == "Brasil em Dados — Censo 2022"
    assert any("Censo de 2022" in c.value and "tabela 4714" in c.value for c in app.caption)
    metricas = _metricas(app)
    assert metricas["População total"] == "1.460.000 pessoas"
    assert metricas["Municípios"] == "5"
    assert metricas["Município mais populoso"] == "Cidade Teste Grande (SP)"
    assert metricas["População média"] == "292.000 pessoas"
    assert metricas["Densidade demográfica"] == "102,10 hab/km²"
    assert metricas["Participação no Brasil"] == "100%"
    assert metricas["Municípios recebidos da API"] == "5"
    assert metricas["Registros válidos"] == "5"
    assert metricas["Registros descartados"] == "0"
    assert len(app.get("plotly_chart")) == 3
    assert len(app.get("download_button")) == 1
    assert app.info[0].value == "Mostrando todo o Brasil."
    qualidade = app.markdown[-1].value
    assert "31/07/2022" in qualidade and "Valores ausentes:** nenhum" in qualidade


def test_filtro_de_regiao_atualiza_indicadores_e_opcoes(app):
    app.multiselect(key="regioes").set_value(["Sudeste"]).run()
    assert not app.exception
    assert _metricas(app)["Municípios"] == "2"
    assert _metricas(app)["População total"] == "1.300.000 pessoas"
    assert app.multiselect(key="ufs").options == ["RJ — Rio de Janeiro", "SP — São Paulo"]


def test_uf_que_sai_da_regiao_escolhida_e_removida_do_filtro(app):
    app.multiselect(key="ufs").set_value(["SP"]).run()
    assert _metricas(app)["Municípios"] == "1"
    app.multiselect(key="regioes").set_value(["Sul"]).run()
    assert not app.exception
    assert app.multiselect(key="ufs").value == []
    assert _metricas(app)["Município mais populoso"] == "Cidade Teste Sul (PR)"


def test_filtro_de_municipio_ranking_e_agrupamento(app):
    app.multiselect(key="municipios").set_value(["3500001", "3300002"]).run()
    app.slider(key="ranking").set_value(5).run()
    assert not app.exception
    assert _metricas(app)["Municípios"] == "2"
    assert "Cidade Teste Grande (SP)" in app.info[0].value


def test_limpar_filtros(app):
    app.multiselect(key="regioes").set_value(["Sul"]).run()
    app.button[0].click().run()
    assert app.multiselect(key="regioes").value == []
    assert _metricas(app)["Municípios"] == "5"


def test_estado_vazio(api_simulada, monkeypatch):
    original = dados.montar_selecao
    monkeypatch.setattr(
        dados, "montar_selecao", lambda todos, filtros: original(todos, dados.Filtros(municipios=("0000000",)))
    )
    st.cache_data.clear()
    tela = AppTest.from_file(APP, default_timeout=60).run()
    assert not tela.exception
    assert "Nenhum município corresponde" in tela.warning[0].value
    assert len(tela.get("plotly_chart")) == 0
    assert len(tela.metric) == 0


def test_erro_na_extracao_mostra_mensagem_amigavel_e_permite_tentar_de_novo(api_simulada, monkeypatch):
    def falha(**kwargs):
        raise ErroDeExtracao("detalhe técnico: ReadTimeout", temporario=True)

    monkeypatch.setattr(dados, "extrair", falha)
    st.cache_data.clear()
    tela = AppTest.from_file(APP, default_timeout=60).run()
    assert not tela.exception
    assert tela.error[0].value == dados.MENSAGEM_SEM_CONEXAO
    assert "ReadTimeout" not in tela.error[0].value
    assert tela.button[0].label == "Tentar de novo"
    assert len(tela.metric) == 0

    # O erro não fica no cache: quando a API volta, "Tentar de novo" funciona.
    monkeypatch.setattr(dados, "extrair", lambda **kwargs: resposta_ibge())
    tela.button[0].click().run()
    assert not tela.error
    assert _metricas(tela)["Municípios"] == "5"


def test_cache_evita_novo_download_quando_os_filtros_mudam(app, api_simulada):
    assert len(api_simulada) == 1
    app.multiselect(key="regioes").set_value(["Sul"]).run()
    app.slider(key="ranking").set_value(20).run()
    assert len(api_simulada) == 1


# =============================================================
# Independência do chatbot (Produto A)
# =============================================================


def test_dashboard_nao_importa_o_chatbot():
    codigo = (
        "import sys; import dashboard.dados, dashboard.graficos; "
        "proibidos = [m for m in sys.modules if m.split('.')[0] in ('assistente', 'gradio')]; "
        "print(proibidos); sys.exit(1 if proibidos else 0)"
    )
    resultado = subprocess.run([sys.executable, "-c", codigo], check=False, cwd=RAIZ, capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_chatbot_e_render_nao_dependem_do_dashboard():
    assert "dashboard" not in (RAIZ / "app.py").read_text(encoding="utf-8")
    for arquivo in (RAIZ / "assistente").glob("*.py"):
        assert "dashboard" not in arquivo.read_text(encoding="utf-8"), arquivo
    requisitos = (RAIZ / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "streamlit" not in requisitos and "plotly" not in requisitos
    assert "buildCommand: pip install -r requirements.txt\n" in (RAIZ / "render.yaml").read_text(encoding="utf-8")
