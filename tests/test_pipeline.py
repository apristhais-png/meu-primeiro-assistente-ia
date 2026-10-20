"""Testes do pipeline de dados (extração → validação → transformação → indicadores).

DADOS DE TESTE FICTÍCIOS: os municípios abaixo ("Cidade Teste ...") não
existem. Só os CÓDIGOS seguem o formato oficial do IBGE (7 dígitos, com o
código da UF no começo), e os números foram escolhidos para facilitar as
contas. Nenhum teste acessa a internet: a API é sempre simulada.
"""

import json
import socket
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
import requests

from pipeline import extracao, fonte
from pipeline.executar import formatar, main
from pipeline.extracao import ErroDeExtracao, extrair
from pipeline.indicadores import DEFINICOES, calcular, densidades_inconsistentes
from pipeline.transformacao import agregar, filtrar, maiores, montar_dataframe, para_csv
from pipeline.validacao import (
    ErroDeValidacao,
    converter_numero,
    separar_nome_e_uf,
    validar,
)


@pytest.fixture(autouse=True)
def sem_internet(monkeypatch):
    def proibido(*args, **kwargs):
        raise RuntimeError("Acesso à rede bloqueado nos testes")

    monkeypatch.setattr(socket.socket, "connect", proibido)
    monkeypatch.setattr(socket, "create_connection", proibido)


# ---------- Dados de teste FICTÍCIOS ----------

# (código IBGE, nome como a API devolve, população, área km², densidade)
MUNICIPIOS_FICTICIOS = [
    ("3500001", "Cidade Teste Grande - SP", "1000000", "500.00", "2000.00"),
    ("3300002", "Cidade Teste Média - RJ", "300000", "300.00", "1000.00"),
    ("4100003", "Cidade Teste Sul - PR", "100000", "1000.00", "100.00"),
    ("2900004", "Cidade Teste Nordeste - BA", "50000", "2500.00", "20.00"),
    ("1300005", "Cidade Teste Norte - AM", "10000", "10000.00", "1.00"),
]


def resposta_ibge(municipios=MUNICIPIOS_FICTICIOS, ano="2022", nivel="N6"):
    """Monta uma resposta no formato da API de agregados v3 (dados fictícios)."""
    variaveis = [("93", "População residente", "Pessoas", 2),
                 ("6318", "Área da unidade territorial", "Quilômetros quadrados", 3),
                 ("614", "Densidade demográfica", "Habitante por quilômetro quadrado", 4)]
    return [
        {
            "id": id_, "variavel": nome, "unidade": unidade,
            "resultados": [{
                "classificacoes": [],
                "series": [
                    {"localidade": {"id": m[0], "nivel": {"id": nivel, "nome": "Município"}, "nome": m[1]},
                     "serie": {ano: m[posicao]}}
                    for m in municipios
                ],
            }],
        }
        for id_, nome, unidade, posicao in variaveis
    ]


@pytest.fixture
def df():
    return montar_dataframe(validar(resposta_ibge()).registros)


# =============================================================
# Fonte
# =============================================================

def test_url_da_consulta_usa_tabela_4714_ano_2022_tres_variaveis_e_todos_os_municipios():
    url = fonte.url_da_consulta()
    assert url == "https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/variaveis/93|6318|614?localidades=N6[all]"


def test_tabela_de_ufs_tem_as_27_unidades_e_cinco_regioes():
    assert len(fonte.UFS) == 27
    assert {fonte.REGIOES[codigo[0]] for codigo in fonte.UFS} == set(fonte.REGIOES.values())
    assert len({sigla for sigla, _ in fonte.UFS.values()}) == 27


# =============================================================
# Extração (requests simulado)
# =============================================================

def resposta_http(status=200, corpo=b"", json_=None):
    resposta = requests.Response()
    resposta.status_code = status
    resposta._content = json.dumps(json_).encode() if json_ is not None else corpo
    resposta.headers["Content-Type"] = "application/json"
    return resposta


class SessaoFalsa:
    """Substitui requests.Session: devolve (ou lança) um item por chamada."""

    def __init__(self, *efeitos):
        self.efeitos = list(efeitos)
        self.chamadas = []

    def get(self, url, timeout=None, headers=None):
        self.chamadas.append({"url": url, "timeout": timeout})
        efeito = self.efeitos.pop(0)
        if isinstance(efeito, Exception):
            raise efeito
        return efeito


def extrair_com(*efeitos):
    sessao = SessaoFalsa(*efeitos)
    return extrair(url="https://exemplo.invalid/api", sessao=sessao, dormir=lambda s: None), sessao


def test_extracao_bem_sucedida_com_timeout_explicito():
    dados, sessao = extrair_com(resposta_http(json_=resposta_ibge()))
    assert dados == resposta_ibge()
    assert sessao.chamadas[0]["timeout"] == extracao.TEMPO_LIMITE
    assert len(sessao.chamadas) == 1


@pytest.mark.parametrize(("status", "trecho"), [(400, "400"), (404, "404")])
def test_erros_400_e_404_param_sem_repetir(status, trecho):
    with pytest.raises(ErroDeExtracao) as erro:
        extrair_com(resposta_http(status), resposta_http(json_=resposta_ibge()))
    assert trecho in str(erro.value) and erro.value.temporario is False
    assert erro.value.status == status


@pytest.mark.parametrize("status", [429, 500, 503])
def test_erros_temporarios_429_e_5xx_repetem_uma_vez(status):
    dados, sessao = extrair_com(resposta_http(status), resposta_http(json_=resposta_ibge()))
    assert dados == resposta_ibge()
    assert len(sessao.chamadas) == 2


def test_erro_temporario_duas_vezes_desiste():
    with pytest.raises(ErroDeExtracao) as erro:
        extrair_com(resposta_http(500), resposta_http(502))
    assert erro.value.temporario is True


@pytest.mark.parametrize(
    ("falha", "trecho"),
    [(requests.Timeout(), "demorou demais"), (requests.ConnectionError(), "conectar")],
)
def test_timeout_e_falha_de_conexao(falha, trecho):
    with pytest.raises(ErroDeExtracao) as erro:
        extrair_com(falha, falha)
    assert trecho in str(erro.value)


def test_outro_erro_do_requests_nao_repete():
    with pytest.raises(ErroDeExtracao):
        extrair_com(requests.TooManyRedirects(), resposta_http(json_=[1]))


def test_status_inesperado():
    with pytest.raises(ErroDeExtracao) as erro:
        extrair_com(resposta_http(302))
    assert "302" in str(erro.value)


def test_json_invalido():
    with pytest.raises(ErroDeExtracao) as erro:
        extrair_com(resposta_http(corpo=b"<html>erro</html>"))
    assert "JSON" in str(erro.value)


@pytest.mark.parametrize("vazio", [[], {}])
def test_resposta_vazia(vazio):
    with pytest.raises(ErroDeExtracao) as erro:
        extrair_com(resposta_http(json_=vazio))
    assert "vazia" in str(erro.value)


def test_cache_evita_novo_download(tmp_path):
    cache = tmp_path / "dados" / "ibge.json"
    sessao = SessaoFalsa(resposta_http(json_=resposta_ibge()))
    primeiro = extrair(url="https://exemplo.invalid", sessao=sessao, cache=cache)
    segundo = extrair(url="https://exemplo.invalid", sessao=SessaoFalsa(), cache=cache)  # não chama a API
    assert primeiro == segundo == resposta_ibge()
    assert cache.is_file() and len(sessao.chamadas) == 1


# =============================================================
# Validação (Pydantic)
# =============================================================

def test_validacao_normaliza_cada_municipio(df):
    validados = validar(resposta_ibge())
    primeiro = validados.registros[0]
    assert (primeiro.codigo_ibge, primeiro.municipio, primeiro.uf_sigla, primeiro.uf_nome, primeiro.regiao) == (
        "3500001", "Cidade Teste Grande", "SP", "São Paulo", "Sudeste")
    assert (primeiro.ano, primeiro.populacao, primeiro.area_km2) == (2022, 1_000_000, 500.0)
    assert validados.relatorio.municipios_validos == 5 and not validados.relatorio.descartados
    assert validados.unidades["populacao"] == "Pessoas"


@pytest.mark.parametrize(
    "estragar",
    [
        lambda r: r[0].pop("resultados"),  # campo obrigatório ausente
        lambda r: r[0]["resultados"][0].__setitem__("series", "não é lista"),  # tipo inválido
        lambda r: r[0]["resultados"][0]["series"][0]["localidade"].__setitem__("id", "123"),  # código inválido
        lambda r: r[0]["resultados"][0]["series"][0]["localidade"].pop("nome"),
        lambda r: r[0].__setitem__("resultados", []),
    ],
)
def test_estrutura_inesperada_impede_a_analise(estragar):
    resposta = resposta_ibge()
    estragar(resposta)
    with pytest.raises(ErroDeValidacao):
        validar(resposta)


def test_resposta_que_nao_e_lista():
    with pytest.raises(ErroDeValidacao):
        validar({"erro": "inesperado"})


def test_variavel_ausente_impede_a_analise():
    with pytest.raises(ErroDeValidacao) as erro:
        validar(resposta_ibge()[:2])  # sem a densidade (614)
    assert "614" in str(erro.value)


def test_nivel_que_nao_e_municipio_impede_a_analise():
    with pytest.raises(ErroDeValidacao):
        validar(resposta_ibge(nivel="N3"))


def test_ano_diferente_deixa_populacao_ausente_e_nada_valido():
    with pytest.raises(ErroDeValidacao) as erro:
        validar(resposta_ibge(ano="2010"))
    assert "nenhum município válido" in str(erro.value)


def test_municipio_duplicado_e_contado_e_removido():
    repetidos = [*MUNICIPIOS_FICTICIOS, MUNICIPIOS_FICTICIOS[0]]
    validados = validar(resposta_ibge(repetidos))
    assert validados.relatorio.municipios_validos == 5
    assert validados.relatorio.duplicados_removidos == 3  # uma vez em cada uma das 3 variáveis


@pytest.mark.parametrize(
    ("municipio", "motivo"),
    [
        (("3500009", "Cidade Teste Sigilo - SP", "X", "10.0", "1.0"), "população ausente"),
        (("3500010", "Cidade Teste Sem Dado - SP", "...", "10.0", "1.0"), "população ausente"),
        (("3500011", "Cidade Teste Fração - SP", "10.5", "10.0", "1.0"), "população não é um número inteiro"),
        (("3500012", "Cidade Teste Negativa - SP", "-5", "10.0", "1.0"), "valores fora do intervalo válido"),
        (("9900013", "Cidade Teste UF Inexistente - XX", "100", "10.0", "10.0"), "código de UF desconhecido"),
        (("3500014", "Cidade Teste UF Trocada - RJ", "100", "10.0", "10.0"), "UF do nome diferente da UF do código"),
    ],
)
def test_municipio_com_problema_e_descartado_com_motivo(municipio, motivo):
    validados = validar(resposta_ibge([*MUNICIPIOS_FICTICIOS, municipio]))
    assert validados.relatorio.municipios_validos == 5
    assert validados.relatorio.descartados == {motivo: 1}
    assert motivo in validados.relatorio.resumo()


def test_area_ausente_e_aceita_mas_registrada():
    sem_area = ("3500015", "Cidade Teste Sem Área - SP", "100", "...", "...")
    validados = validar(resposta_ibge([*MUNICIPIOS_FICTICIOS, sem_area]))
    assert validados.relatorio.municipios_validos == 6
    assert validados.relatorio.valores_ausentes == {"area_km2": 1, "densidade_hab_km2": 1}
    assert "valores ausentes" in validados.relatorio.resumo()


@pytest.mark.parametrize(
    ("texto", "numero"),
    [("123", 123.0), ("1234.5", 1234.5), ("12,5", 12.5), ("-", 0.0), ("...", None), ("..", None),
     ("X", None), ("", None), (None, None), ("abc", None)],
)
def test_converter_valores_especiais_do_ibge(texto, numero):
    assert converter_numero(texto) == numero


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [("Rio de Janeiro - RJ", ("Rio de Janeiro", "RJ")), ("Embu-Guaçu - SP", ("Embu-Guaçu", "SP")), ("Sem UF", ("Sem UF", None))],
)
def test_separar_nome_e_uf(nome, esperado):
    assert separar_nome_e_uf(nome) == esperado


# =============================================================
# Transformação (Pandas)
# =============================================================

def test_dataframe_tem_colunas_tipos_e_ordem_padronizados(df):
    assert list(df.columns) == ["codigo_ibge", "municipio", "uf_sigla", "uf_nome", "regiao", "ano",
                                "populacao", "area_km2", "densidade_hab_km2"]
    assert df["populacao"].dtype == "int64" and df["area_km2"].dtype == "float64"
    assert df["codigo_ibge"].dtype == "string"
    assert df["populacao"].is_monotonic_decreasing


def test_montar_remove_duplicados():
    registros = validar(resposta_ibge()).registros
    assert len(montar_dataframe([*registros, registros[0]])) == 5


@pytest.mark.parametrize(
    ("filtros", "codigos"),
    [
        ({}, 5),
        ({"regioes": ["Sudeste"]}, 2),
        ({"ufs": ["BA", "AM"]}, 2),
        ({"regioes": ["Sudeste"], "ufs": ["RJ"]}, 1),
        ({"municipios": ["4100003"]}, 1),
        ({"regioes": ["Sul"], "ufs": ["SP"]}, 0),
    ],
)
def test_filtros(df, filtros, codigos):
    assert len(filtrar(df, **filtros)) == codigos


def test_maiores(df):
    assert list(maiores(df, 2)["codigo_ibge"]) == ["3500001", "3300002"]
    assert list(maiores(df, 1, "area_km2")["codigo_ibge"]) == ["1300005"]
    with pytest.raises(ValueError):
        maiores(df, 0)


def test_agregar_por_regiao_usa_densidade_ponderada(df):
    regioes = agregar(df, "regiao").set_index("regiao")
    sudeste = regioes.loc["Sudeste"]
    assert (sudeste["municipios"], sudeste["populacao"], sudeste["area_km2"]) == (2, 1_300_000, 800.0)
    assert sudeste["densidade_hab_km2"] == pytest.approx(1_300_000 / 800)  # não a média de 2000 e 1000
    assert list(regioes.index) == ["Sudeste", "Sul", "Nordeste", "Norte"]


def test_agregar_por_uf_e_por_coluna_invalida(df):
    assert len(agregar(df, "uf_sigla")) == 5
    with pytest.raises(ValueError):
        agregar(df, "municipio")


def test_csv_para_planilhas_brasileiras(df):
    conteudo = para_csv(df.head(1))
    assert conteudo.startswith("﻿".encode())  # BOM: o Excel reconhece os acentos
    texto = conteudo.decode("utf-8-sig")
    assert texto.splitlines()[0].startswith("codigo_ibge;municipio;uf_sigla")
    assert "500,0" in texto  # vírgula decimal
    assert "São Paulo" in texto


# =============================================================
# Indicadores
# =============================================================

def test_indicadores_do_brasil(df):
    ind = calcular(df, df)
    assert ind["populacao_total"].valor == 1_460_000
    assert ind["municipios"].valor == 5
    assert ind["maior_populacao"].valor == 1_000_000
    assert ind["maior_populacao"].detalhe == "Cidade Teste Grande (SP)"
    assert ind["media_populacao"].valor == pytest.approx(292_000)
    assert ind["mediana_populacao"].valor == 100_000
    assert ind["densidade_selecao"].valor == pytest.approx(1_460_000 / 14_300)
    assert ind["participacao_brasil"].valor == pytest.approx(100)


def test_indicadores_de_uma_selecao(df):
    ind = calcular(filtrar(df, regioes=["Sudeste"]), df)
    assert ind["populacao_total"].valor == 1_300_000
    assert ind["participacao_brasil"].valor == pytest.approx(1_300_000 / 1_460_000 * 100)


def test_selecao_vazia_nao_inventa_numeros(df):
    ind = calcular(filtrar(df, ufs=["AC"]), df)
    assert all(i.valor is None for i in ind.values())


def test_densidade_ignora_municipios_sem_area():
    sem_area = ("3500015", "Cidade Teste Sem Área - SP", "100000", "...", "...")
    df = montar_dataframe(validar(resposta_ibge([MUNICIPIOS_FICTICIOS[0], sem_area])).registros)
    ind = calcular(df, df)
    assert ind["densidade_selecao"].valor == pytest.approx(1_000_000 / 500)
    assert ind["populacao_total"].valor == 1_100_000


def test_toda_definicao_tem_nome_formula_unidade_fonte_e_periodo():
    for definicao in DEFINICOES.values():
        assert definicao.nome and definicao.definicao and definicao.formula and definicao.unidade
        assert "IBGE" in definicao.fonte and definicao.periodo == "2022"


def test_densidades_inconsistentes(df):
    assert densidades_inconsistentes(df).empty
    errado = df.copy()
    errado.loc[0, "densidade_hab_km2"] = 1.0  # deveria ser 2000
    assert list(densidades_inconsistentes(errado)["codigo_ibge"]) == ["3500001"]


# =============================================================
# Execução completa (python -m pipeline)
# =============================================================

def test_pipeline_completo_mostra_resumo_e_salva_csv(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("pipeline.executar.extrair", lambda cache=None: resposta_ibge())
    destino = tmp_path / "saida" / "municipios.csv"
    assert main(["--csv", str(destino)]) == 0
    saida = capsys.readouterr().out
    assert "5 de 5 municípios válidos" in saida
    assert "População total da seleção: 1.460.000 pessoas" in saida
    assert "Sudeste: 1.300.000 pessoas em 2 municípios" in saida
    assert destino.read_bytes().startswith("﻿".encode())


@pytest.mark.parametrize("erro", [ErroDeExtracao("sem internet"), ErroDeValidacao("formato estranho")])
def test_pipeline_completo_com_erro_termina_com_codigo_1(monkeypatch, capsys, erro):
    def falhar(cache=None):
        raise erro

    monkeypatch.setattr("pipeline.executar.extrair", falhar)
    assert main([]) == 1
    assert "[ERRO]" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("valor", "texto"),
    [(None, "—"), (1460000, "1.460.000"), (2000.0, "2.000"), (1234.567, "1.234,57")],
)
def test_formatar_numeros_no_padrao_brasileiro(valor, texto):
    assert formatar(valor) == texto


def test_pipeline_nao_carrega_o_chatbot():
    # Os produtos são independentes: o pipeline não importa a pasta assistente/
    # (nem o Gradio). Roda num processo separado para não sofrer efeito de outros testes.
    codigo = (
        "import sys, pipeline.executar; "
        "print(any(m == 'assistente' or m.startswith(('assistente.', 'gradio')) for m in sys.modules))"
    )
    resultado = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, check=True,
                               cwd=Path(__file__).resolve().parent.parent)
    assert resultado.stdout.strip() == "False"


def test_dataframe_vazio_quando_nao_ha_registros():
    vazio = montar_dataframe([])
    assert vazio.empty and list(vazio.columns)[:2] == ["codigo_ibge", "municipio"]
    assert isinstance(vazio, pd.DataFrame)
