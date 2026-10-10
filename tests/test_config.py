"""Testes da configuração (SPEC, teste T1).

P4: testes básicos da leitura do config.yml real, da logo e das mensagens de erro.
P5: completa o grupo T1 com todos os casos de recusa listados na SPEC.
"""

import copy
import xml.etree.ElementTree as ET

import pytest
import yaml

from assistente.config import (
    CAMINHO_PADRAO,
    RAIZ_DO_PROJETO,
    ErroDeConfiguracao,
    carregar_configuracao,
    validar_dados,
)


@pytest.fixture
def dados_validos():
    """Uma cópia dos dados do config.yml real, para alterar nos testes."""
    return copy.deepcopy(yaml.safe_load(CAMINHO_PADRAO.read_text(encoding="utf-8")))


# ---------- O config.yml real ----------

def test_config_real_e_valido():
    config = carregar_configuracao()
    assert config.assistente.nome == "Professor de Dados"
    assert config.aparencia.tema == "claro"


def test_config_real_comeca_sem_identificacao_por_ip():
    # SPEC 4.3: a identificação só é ligada depois do teste no Space (P15).
    assert carregar_configuracao().limites.identificar_por_ip is False


def test_provedores_na_ordem_da_spec():
    config = carregar_configuracao()
    assert [p.nome for p in config.provedores_ativos] == ["openrouter", "anthropic", "openai"]


def test_config_real_nao_tem_chaves_de_api():
    texto = CAMINHO_PADRAO.read_text(encoding="utf-8").lower()
    for palavra in ("api_key", "sk-or-v1-", "sk-ant-", "hf_"):
        assert palavra not in texto


# ---------- A logo ----------

def test_logo_existe_e_e_um_svg_valido():
    config = carregar_configuracao()
    logo = RAIZ_DO_PROJETO / config.assistente.logo
    raiz_xml = ET.parse(logo).getroot()
    assert raiz_xml.tag.endswith("svg")


# ---------- Mensagens de erro claras ----------

def test_arquivo_inexistente(tmp_path):
    with pytest.raises(ErroDeConfiguracao, match="arquivo não encontrado"):
        carregar_configuracao(tmp_path / "config.yml")


def test_yaml_quebrado_mostra_a_linha(tmp_path):
    arquivo = tmp_path / "config.yml"
    arquivo.write_text("assistente:\n  nome: Professor\n\tdescricao: com TAB\n", encoding="utf-8")
    with pytest.raises(ErroDeConfiguracao, match=r"linha 3"):
        carregar_configuracao(arquivo)


def test_arquivo_vazio(tmp_path):
    arquivo = tmp_path / "config.yml"
    arquivo.write_text("", encoding="utf-8")
    with pytest.raises(ErroDeConfiguracao, match="vazio"):
        carregar_configuracao(arquivo)


def test_erro_diz_o_campo_e_esta_em_portugues(dados_validos):
    del dados_validos["assistente"]["nome"]
    with pytest.raises(ErroDeConfiguracao) as erro:
        validar_dados(dados_validos)
    assert erro.value.problemas == ["assistente.nome: campo obrigatório que está faltando"]


def test_varios_erros_sao_mostrados_de_uma_vez(dados_validos):
    dados_validos["geracao"]["temperatura"] = 2
    dados_validos["aparencia"]["tema"] = "azul"
    with pytest.raises(ErroDeConfiguracao) as erro:
        validar_dados(dados_validos)
    assert len(erro.value.problemas) == 2
    assert "'claro' ou 'escuro'" in "\n".join(erro.value.problemas)


def test_cor_ilegivel_usa_a_validacao_de_contraste(dados_validos):
    dados_validos["aparencia"]["cor_secundaria"] = "#FFFF66"
    with pytest.raises(ErroDeConfiguracao) as erro:
        validar_dados(dados_validos)
    [problema] = erro.value.problemas
    assert problema.startswith("aparencia.cor_secundaria = #FFFF66: contraste")
    assert "mais escura" in problema


def test_logo_relativa_a_pasta_do_config(tmp_path, dados_validos):
    # O caminho da logo é conferido a partir da pasta onde está o config.yml.
    arquivo = tmp_path / "config.yml"
    arquivo.write_text(yaml.safe_dump(dados_validos, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ErroDeConfiguracao, match="logo não foi encontrado"):
        carregar_configuracao(arquivo)
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.svg").write_text("<svg/>", encoding="utf-8")
    assert carregar_configuracao(arquivo).assistente.logo == "assets/logo.svg"
