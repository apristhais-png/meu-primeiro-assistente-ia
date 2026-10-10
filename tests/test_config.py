"""Testes da configuração (SPEC, teste T1).

P4: testes básicos da leitura do config.yml real, da logo e das mensagens de erro.
P5: completa o grupo T1 com todos os casos de recusa listados na SPEC.
"""

import copy
import subprocess
import sys
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


# =============================================================
# P5: casos de recusa do grupo T1 (SPEC, seções 4.2 e 6)
# =============================================================

def problemas(dados) -> list[str]:
    """Valida os dados e devolve a lista de problemas (vazia se estiver tudo certo)."""
    try:
        validar_dados(dados)
    except ErroDeConfiguracao as erro:
        return erro.problemas
    return []


def um_problema_em(dados, campo: str) -> str:
    """Confere que há exatamente um problema e que ele aponta o campo esperado."""
    lista = problemas(dados)
    assert len(lista) == 1, lista
    assert lista[0].startswith(campo), lista
    return lista[0]


# ---------- Assistente ----------

@pytest.mark.parametrize("nome", ["", "   ", "A" * 61])
def test_recusa_nome_vazio_ou_longo_demais(dados_validos, nome):
    dados_validos["assistente"]["nome"] = nome
    um_problema_em(dados_validos, "assistente.nome")


def test_aceita_nome_com_60_caracteres(dados_validos):
    dados_validos["assistente"]["nome"] = "A" * 60
    assert problemas(dados_validos) == []


def test_recusa_logo_que_nao_existe(dados_validos):
    dados_validos["assistente"]["logo"] = "assets/nao-existe.svg"
    um_problema_em(dados_validos, "assistente.logo")


# ---------- Aparência ----------

@pytest.mark.parametrize("campo", ["cor_primaria", "cor_secundaria"])
@pytest.mark.parametrize("cor", ["azul", "#12", "2563EB", "#GGGGGG"])
def test_recusa_cor_em_formato_errado(dados_validos, campo, cor):
    dados_validos["aparencia"][campo] = cor
    assert "#RRGGBB" in um_problema_em(dados_validos, f"aparencia.{campo}")


def test_recusa_tema_inexistente(dados_validos):
    dados_validos["aparencia"]["tema"] = "azul"
    um_problema_em(dados_validos, "aparencia.tema")


def test_recusa_cor_que_fica_ilegivel_ao_trocar_o_tema(dados_validos):
    # #047857 passa no fundo claro, mas não no escuro (SPEC 4.4).
    dados_validos["aparencia"]["tema"] = "escuro"
    assert "mais clara" in um_problema_em(dados_validos, "aparencia.cor_secundaria")


# ---------- Instruções ----------

@pytest.mark.parametrize("instrucoes", ["", "   \n  "])
def test_recusa_instrucoes_vazias(dados_validos, instrucoes):
    dados_validos["instrucoes"] = instrucoes
    um_problema_em(dados_validos, "instrucoes")


# ---------- Geração ----------

@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("temperatura", -0.1),
        ("temperatura", 1.1),
        ("temperatura", 2),
        ("max_tokens", 0),
        ("max_tokens", 4001),
        ("timeout_segundos", 4),
        ("timeout_segundos", 121),
        ("max_mensagens_historico", 0),
    ],
)
def test_recusa_geracao_fora_da_faixa(dados_validos, campo, valor):
    dados_validos["geracao"][campo] = valor
    um_problema_em(dados_validos, f"geracao.{campo}")


@pytest.mark.parametrize("temperatura", [0, 1])
def test_aceita_temperatura_nos_extremos(dados_validos, temperatura):
    dados_validos["geracao"]["temperatura"] = temperatura
    assert problemas(dados_validos) == []


# ---------- Limites ----------

def test_recusa_configuracao_sem_limites(dados_validos):
    del dados_validos["limites"]
    um_problema_em(dados_validos, "limites")


def test_recusa_configuracao_sem_identificar_por_ip(dados_validos):
    del dados_validos["limites"]["identificar_por_ip"]
    um_problema_em(dados_validos, "limites.identificar_por_ip")


@pytest.mark.parametrize("valor", ["sim", "true", 1, None])
def test_identificar_por_ip_so_aceita_true_ou_false(dados_validos, valor):
    dados_validos["limites"]["identificar_por_ip"] = valor
    um_problema_em(dados_validos, "limites.identificar_por_ip")


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("perguntas_por_minuto_total", 0),
        ("perguntas_por_minuto_total", 121),
        ("perguntas_por_dia_total", 0),
        ("perguntas_por_dia_total", 1_000_000),
        ("tamanho_maximo_pergunta", 99),
        ("tamanho_maximo_pergunta", 10_001),
        ("perguntas_por_minuto_por_pessoa", 0),
        ("perguntas_por_minuto_por_pessoa", 31),
        ("perguntas_por_dia_por_pessoa", 0),
        ("perguntas_por_dia_por_pessoa", 501),
    ],
)
def test_recusa_limites_fora_da_faixa(dados_validos, campo, valor):
    dados_validos["limites"][campo] = valor
    um_problema_em(dados_validos, f"limites.{campo}")


@pytest.mark.parametrize(
    ("por_pessoa", "total"),
    [
        ("perguntas_por_minuto_por_pessoa", "perguntas_por_minuto_total"),
        ("perguntas_por_dia_por_pessoa", "perguntas_por_dia_total"),
    ],
)
def test_recusa_limite_por_pessoa_maior_que_o_global(dados_validos, por_pessoa, total):
    dados_validos["limites"][total] = 10
    dados_validos["limites"][por_pessoa] = 11
    assert "não pode ser maior" in um_problema_em(dados_validos, "limites")


def test_aceita_limite_por_pessoa_igual_ao_global(dados_validos):
    dados_validos["limites"]["perguntas_por_minuto_total"] = 5
    dados_validos["limites"]["perguntas_por_minuto_por_pessoa"] = 5
    assert problemas(dados_validos) == []


# ---------- Provedores ----------

def test_recusa_provedor_desconhecido(dados_validos):
    dados_validos["provedores"][0]["nome"] = "gemini"
    um_problema_em(dados_validos, "provedores[1].nome")


def test_recusa_lista_de_provedores_vazia(dados_validos):
    dados_validos["provedores"] = []
    um_problema_em(dados_validos, "provedores")


def test_recusa_nenhum_provedor_ativo(dados_validos):
    for provedor in dados_validos["provedores"]:
        provedor["ativo"] = False
    assert "pelo menos um" in um_problema_em(dados_validos, "provedores")


def test_recusa_provedor_repetido(dados_validos):
    dados_validos["provedores"].append({"nome": "openrouter", "modelo": "outro-modelo"})
    assert "repetido" in um_problema_em(dados_validos, "provedores")


def test_recusa_provedor_sem_modelo(dados_validos):
    dados_validos["provedores"][1]["modelo"] = ""
    um_problema_em(dados_validos, "provedores[2].modelo")


def test_provedor_desligado_fica_fora_da_lista_de_ativos(dados_validos):
    dados_validos["provedores"][0]["ativo"] = False
    config = validar_dados(dados_validos)
    assert [p.nome for p in config.provedores_ativos] == ["anthropic", "openai"]


# ---------- Campos desconhecidos (erros de digitação) ----------

@pytest.mark.parametrize(
    ("onde", "campo_esperado"),
    [
        (lambda d: d, "nomee"),
        (lambda d: d["assistente"], "assistente.nomee"),
        (lambda d: d["limites"], "limites.nomee"),
        (lambda d: d["provedores"][0], "provedores[1].nomee"),
    ],
)
def test_recusa_campo_desconhecido(dados_validos, onde, campo_esperado):
    onde(dados_validos)["nomee"] = "erro de digitação"
    assert "campo desconhecido" in um_problema_em(dados_validos, campo_esperado)


# =============================================================
# P5: comando scripts/validar_config.py (RF9)
# =============================================================

SCRIPT = RAIZ_DO_PROJETO / "scripts" / "validar_config.py"


def rodar_script(*argumentos, pasta=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, argumentos)],
        capture_output=True,
        text=True,
        cwd=pasta,
        check=False,  # o código de saída é conferido em cada teste
    )


def test_script_aprova_o_config_real(tmp_path):
    # Roda de outra pasta, para garantir que o script encontra o projeto sozinho.
    resultado = rodar_script(pasta=tmp_path)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "[OK] config.yml está correto." in resultado.stdout
    assert "Professor de Dados" in resultado.stdout


def test_script_reprova_config_com_erro(tmp_path, dados_validos):
    dados_validos["aparencia"]["cor_primaria"] = "azul"
    dados_validos["geracao"]["temperatura"] = 5
    arquivo = tmp_path / "config.yml"
    arquivo.write_text(yaml.safe_dump(dados_validos, allow_unicode=True), encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.svg").write_text("<svg/>", encoding="utf-8")

    resultado = rodar_script(arquivo)
    assert resultado.returncode == 1
    assert "[ERRO] O config.yml tem 2 problema(s)" in resultado.stdout
    assert "aparencia.cor_primaria" in resultado.stdout
    assert "geracao.temperatura" in resultado.stdout


def test_script_reprova_arquivo_inexistente(tmp_path):
    resultado = rodar_script(tmp_path / "nao-existe.yml")
    assert resultado.returncode == 1
    assert "arquivo não encontrado" in resultado.stdout
