"""Testes de contraste e legibilidade das cores (SPEC, teste T2)."""

import itertools

import pytest

from assistente import cores

# ---------- Formato da cor ----------


@pytest.mark.parametrize("cor", ["azul", "#12", "2563EB", "#GGGGGG", "#2563EB0", "", None])
def test_recusa_cor_em_formato_errado(cor):
    with pytest.raises(ValueError, match="#RRGGBB"):
        cores.validar_formato(cor)


def test_aceita_letras_minusculas_e_devolve_em_maiusculas():
    assert cores.validar_formato("#2563eb") == "#2563EB"


# ---------- Cálculo de contraste ----------


def test_contraste_de_casos_conhecidos():
    assert cores.contraste("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert cores.contraste("#FFFFFF", "#FFFFFF") == pytest.approx(1.0)


def test_contraste_nao_depende_da_ordem():
    assert cores.contraste("#2563EB", "#FFFFFF") == cores.contraste("#FFFFFF", "#2563EB")


def test_contraste_das_cores_citadas_na_spec():
    assert cores.contraste("#2563EB", "#FFFFFF") == pytest.approx(5.17, abs=0.01)
    assert cores.contraste("#047857", "#FFFFFF") == pytest.approx(5.48, abs=0.01)
    assert cores.contraste("#10B981", "#FFFFFF") == pytest.approx(2.54, abs=0.01)
    assert cores.contraste("#D97706", "#FFFFFF") == pytest.approx(3.19, abs=0.01)


# ---------- Cor do texto dos botões ----------


def test_botao_azul_escuro_tem_texto_branco():
    assert cores.cor_do_texto_do_botao("#2563EB") == "#FFFFFF"


def test_botao_amarelo_claro_tem_texto_preto():
    assert cores.cor_do_texto_do_botao("#FDE68A") == "#000000"


def test_botao_laranja_do_ca20_tem_texto_preto():
    assert cores.cor_do_texto_do_botao("#D97706") == "#000000"


def test_texto_do_botao_e_sempre_legivel():
    # Testa 4096 cores espalhadas por todo o espectro.
    niveis = range(0, 256, 17)
    for r, g, b in itertools.product(niveis, niveis, niveis):
        cor = f"#{r:02X}{g:02X}{b:02X}"
        texto = cores.cor_do_texto_do_botao(cor)
        assert cores.contraste(cor, texto) >= cores.MINIMO_TEXTO, cor


# ---------- Validação das cores no tema ----------


def test_cores_do_exemplo_da_spec_passam_no_tema_claro():
    assert cores.verificar_cores("#2563EB", "#047857", "claro") == []


def test_cores_do_ca18_e_ca20_passam_no_tema_claro():
    assert cores.verificar_cores("#E11D48", "#047857", "claro") == []
    assert cores.verificar_cores("#D97706", "#047857", "claro") == []


def test_secundaria_clara_demais_no_tema_claro_e_recusada():
    problemas = cores.verificar_cores("#2563EB", "#FFFF66", "claro")
    assert len(problemas) == 1
    assert "cor_secundaria" in problemas[0]
    assert "mais escura" in problemas[0]


def test_secundaria_antiga_do_exemplo_e_recusada():
    problemas = cores.verificar_cores("#2563EB", "#10B981", "claro")
    assert len(problemas) == 1
    # O valor exato é 2,5398; a mensagem arredonda para baixo.
    assert "contraste 2,53 : 1" in problemas[0]


def test_secundaria_escura_demais_no_tema_escuro_e_recusada():
    problemas = cores.verificar_cores("#2563EB", "#1E1E1E", "escuro")
    assert any("cor_secundaria" in p and "mais clara" in p for p in problemas)


def test_primaria_quase_igual_ao_fundo_e_recusada():
    problemas = cores.verificar_cores("#F5F5F5", "#047857", "claro")
    assert len(problemas) == 1
    assert "cor_primaria" in problemas[0]
    assert "bordas" in problemas[0]


def test_amarelo_claro_como_primaria_e_recusado_no_tema_claro():
    # Explica por que o CA20 não usa mais #FDE68A.
    problemas = cores.verificar_cores("#FDE68A", "#047857", "claro")
    assert any("cor_primaria" in p for p in problemas)


def test_cor_aprovada_no_claro_pode_ser_recusada_no_escuro():
    # #047857 passa no fundo branco (5,48), mas não no fundo escuro (3,49).
    assert cores.verificar_cores("#2563EB", "#047857", "claro") == []
    problemas = cores.verificar_cores("#2563EB", "#047857", "escuro")
    assert any("cor_secundaria" in p for p in problemas)


def test_tema_invalido_e_recusado():
    with pytest.raises(ValueError, match="tema inválido"):
        cores.verificar_cores("#2563EB", "#047857", "azul")


def test_formato_invalido_e_recusado_na_validacao():
    with pytest.raises(ValueError, match="#RRGGBB"):
        cores.verificar_cores("azul", "#047857", "claro")


# ---------- Sugestão de cor ----------


@pytest.mark.parametrize(
    ("cor", "tema", "minimo"),
    [
        ("#FFFF66", "claro", cores.MINIMO_TEXTO),
        ("#10B981", "claro", cores.MINIMO_TEXTO),
        ("#1E1E1E", "escuro", cores.MINIMO_TEXTO),
        ("#F5F5F5", "claro", cores.MINIMO_BORDA),
    ],
)
def test_cor_sugerida_passa_na_regra(cor, tema, minimo):
    fundo = cores.FUNDOS[tema]
    sugestao = cores.sugerir_cor(cor, fundo, minimo)
    assert cores.contraste(sugestao, fundo) >= minimo


def test_mensagem_traz_uma_sugestao_que_funciona():
    problema = cores.verificar_cores("#2563EB", "#FFFF66", "claro")[0]
    sugestao = problema.rsplit("por exemplo ", 1)[1].rstrip(".")
    assert cores.verificar_cores("#2563EB", sugestao, "claro") == []


def test_valor_proximo_do_minimo_nao_aparece_arredondado_para_cima():
    # Se o contraste for 4,497, a mensagem não pode dizer "4,50".
    assert cores._formatar(4.497) == "4,49"
