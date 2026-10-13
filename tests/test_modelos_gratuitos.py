"""Testes da escolha de modelos GRATUITOS e de CONVERSA no OpenRouter.

Regressão real: a pergunta d59d051d foi para o classificador de segurança
"nvidia/nemotron-3.5-content-safety:free", que respondeu "User Safety: safe",
e o app tratou isso como sucesso.

Tudo simulado: catálogo falso, cliente falso, rede bloqueada, chave falsa.
"""

import logging
import socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from assistente import provedores as modulo
from assistente.chat import Assistente
from assistente.config import ErroDeConfiguracao, carregar_configuracao, validar_dados
from assistente.limites import Limitador
from assistente.modelos_gratuitos import (
    PRECO_MAXIMO_ZERO,
    CatalogoOpenRouter,
    Quarentena,
    motivo_para_recusar_id,
    motivo_para_recusar_no_catalogo,
    parece_classificacao,
)
from assistente.provedores import (
    MENSAGEM_SEM_MODELO,
    ProvedorOpenRouter,
    SemResposta,
    criar_provedores,
    responder_com_fallback,
)

CONFIG = carregar_configuracao()
CHAVE_FALSA = "chave-de-teste-nao-real-12345"
MENSAGENS = [{"role": "user", "content": "O que é um pipeline de dados?"}]
PRINCIPAL, RESERVA_1, RESERVA_2 = "exemplo/chat-grande:free", "exemplo/chat-medio:free", "exemplo/chat-pequeno:free"
CLASSIFICADOR = "nvidia/nemotron-3.5-content-safety:free"


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    def proibido(*args, **kwargs):
        raise RuntimeError("Acesso à rede bloqueado nos testes")

    monkeypatch.setattr(socket.socket, "connect", proibido)
    monkeypatch.setattr(socket, "create_connection", proibido)
    monkeypatch.setattr(modulo, "ESPERA_ANTES_DE_REPETIR", 0.01)
    monkeypatch.setattr(modulo, "TEMPO_MINIMO_POR_TENTATIVA", 0.1)


# ---------- Ajudantes ----------

def item_do_catalogo(modelo, prompt="0", completion="0", saidas=("text",), entradas=("text",), nome=None, **outros):
    return {
        "id": modelo,
        "name": nome or modelo,
        "pricing": {"prompt": prompt, "completion": completion, "request": "0", "image": "0", **outros},
        "architecture": {"input_modalities": list(entradas), "output_modalities": list(saidas)},
    }


def catalogo_com(*itens):
    return CatalogoOpenRouter(baixar=lambda tempo: list(itens))


CATALOGO_BOM = (item_do_catalogo(PRINCIPAL), item_do_catalogo(RESERVA_1), item_do_catalogo(RESERVA_2))


def resposta(texto, modelo=PRINCIPAL, fim="stop"):
    mensagem = SimpleNamespace(content=texto, reasoning=None)
    return SimpleNamespace(
        model=modelo, usage=SimpleNamespace(completion_tokens=7),
        choices=[SimpleNamespace(message=mensagem, finish_reason=fim)],
    )


def openrouter(*efeitos, catalogo=None, quarentena=None):
    cliente = MagicMock()
    cliente.chat.completions.create.side_effect = list(efeitos)
    provedor = ProvedorOpenRouter(
        "openrouter", PRINCIPAL, CHAVE_FALSA, CONFIG.geracao, cliente=cliente,
        modelos_reserva=[RESERVA_1, RESERVA_2],
        catalogo=catalogo or catalogo_com(*CATALOGO_BOM), quarentena=quarentena or Quarentena(),
    )
    provedor.criar = cliente.chat.completions.create
    return provedor


def com_prazo(provedores, vezes=2):
    return responder_com_fallback(
        provedores, MENSAGENS, "instruções", tempo_maximo_total=5, timeout_por_tentativa=5, tentativas_por_provedor=vezes,
    )


# =============================================================
# Nomes de modelo (config.yml)
# =============================================================

@pytest.mark.parametrize(
    "modelo",
    [
        "openrouter/free",  # roteador que sorteou o classificador
        "openrouter/auto",
        CLASSIFICADOR,
        "meta-llama/llama-guard-4-12b:free",
        "nvidia/nemotron-3-embed-1b:free",
        "exemplo/moderation-1:free",
        "google/gemma-4-31b-it",  # versão paga (sem :free)
    ],
)
def test_nomes_que_nao_servem_sao_recusados(modelo):
    assert motivo_para_recusar_id(modelo) is not None


@pytest.mark.parametrize("modelo", ["google/gemma-4-31b-it:free", "nvidia/nemotron-3-super-120b-a12b:free"])
def test_modelos_de_conversa_gratuitos_sao_aceitos(modelo):
    assert motivo_para_recusar_id(modelo) is None


def dados_do_config(**openrouter):
    dados = CONFIG.model_dump()
    dados["provedores"][0] |= openrouter
    return dados


@pytest.mark.parametrize(
    ("campos", "trecho"),
    [
        ({"modelo": "openrouter/free"}, "roteadores"),
        ({"modelos_reserva": [CLASSIFICADOR]}, "não conversa"),
        ({"modelos_reserva": ["exemplo/pago"]}, ":free"),
        ({"modelos_reserva": ["google/gemma-4-31b-it:free"]}, "repetido"),
    ],
)
def test_config_recusa_modelos_inadequados_no_openrouter(campos, trecho):
    with pytest.raises(ErroDeConfiguracao) as erro:
        validar_dados(dados_do_config(**campos))
    assert trecho in str(erro.value)


def test_modelos_reserva_so_valem_no_openrouter():
    dados = CONFIG.model_dump()
    dados["provedores"][1]["modelos_reserva"] = ["x:free"]
    with pytest.raises(ErroDeConfiguracao) as erro:
        validar_dados(dados)
    assert "só vale para o provedor openrouter" in str(erro.value)


def test_config_atual_tem_lista_explicita_de_modelos_gratuitos_de_conversa():
    [item] = [p for p in CONFIG.provedores if p.nome == "openrouter"]
    todos = [item.modelo, *item.modelos_reserva]
    assert len(todos) >= 2  # há reserva
    assert all(motivo_para_recusar_id(m) is None for m in todos)


# =============================================================
# Respostas com cara de classificação
# =============================================================

@pytest.mark.parametrize(
    "texto",
    [
        "User Safety: safe",  # o caso real (d59d051d)
        "User Safety: safe\nResponse Safety: unsafe",
        "Prompt safety: unsafe",
        "safe",
        "Unsafe.",
        "Safety Categories: Violence, Hate",
        "Classification: benign",
    ],
)
def test_respostas_de_classificador_sao_detectadas(texto):
    assert parece_classificacao(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "Um pipeline de dados é uma sequência de etapas: extrair, transformar e carregar.",
        "É seguro (safe) usar parâmetros no SQL para evitar injeção.",
        "Sim! Em Python, use pandas.read_csv('arquivo.csv').",
        "x" * 400,
    ],
)
def test_explicacoes_normais_nao_sao_confundidas(texto):
    assert not parece_classificacao(texto)


# =============================================================
# Catálogo oficial (preço e tipo)
# =============================================================

@pytest.mark.parametrize(
    ("item", "trecho"),
    [
        (None, "não está no catálogo"),
        (item_do_catalogo("a:free", completion="0.0000002"), "não é gratuito"),
        (item_do_catalogo("a:free", request="0.01"), "não é gratuito"),
        (item_do_catalogo("a:free", saidas=("text", "image")), "não gera só texto"),
        (item_do_catalogo("a:free", saidas=("embeddings",)), "não gera só texto"),
        (item_do_catalogo("a:free", nome="NVIDIA: Nemotron 3.5 Content Safety (free)"), "não conversa"),
        ({"id": "a:free", "architecture": {}}, "não informa o preço"),
    ],
)
def test_catalogo_recusa_pagos_ausentes_e_nao_conversacionais(item, trecho):
    assert trecho in motivo_para_recusar_no_catalogo(item)


def test_catalogo_aprova_gratuito_de_texto_e_mantem_a_ordem():
    catalogo = catalogo_com(item_do_catalogo(RESERVA_1), item_do_catalogo(PRINCIPAL, completion="1"))
    aprovados, recusados = catalogo.avaliar([PRINCIPAL, RESERVA_1, RESERVA_2])
    assert aprovados == [RESERVA_1]
    assert set(recusados) == {PRINCIPAL, RESERVA_2}


def test_catalogo_e_baixado_uma_vez_por_hora():
    agora = [0.0]
    baixar = MagicMock(return_value=list(CATALOGO_BOM))
    catalogo = CatalogoOpenRouter(baixar=baixar, relogio=lambda: agora[0])
    catalogo.avaliar([PRINCIPAL])
    agora[0] = 3599
    catalogo.avaliar([PRINCIPAL])
    assert baixar.call_count == 1
    agora[0] = 3601
    catalogo.avaliar([PRINCIPAL])
    assert baixar.call_count == 2


def test_sem_catalogo_avaliar_devolve_none_e_tenta_de_novo_depois():
    agora = [0.0]
    baixar = MagicMock(side_effect=[OSError("sem rede"), list(CATALOGO_BOM)])
    catalogo = CatalogoOpenRouter(baixar=baixar, relogio=lambda: agora[0])
    assert catalogo.avaliar([PRINCIPAL]) is None
    agora[0] = 30
    assert catalogo.avaliar([PRINCIPAL]) is None  # espera 60 s antes de tentar de novo
    assert baixar.call_count == 1
    agora[0] = 61
    assert catalogo.avaliar([PRINCIPAL]) == ([PRINCIPAL], {})


def test_falha_depois_de_um_sucesso_mantem_o_catalogo_anterior():
    agora = [0.0]
    baixar = MagicMock(side_effect=[list(CATALOGO_BOM), OSError("sem rede")])
    catalogo = CatalogoOpenRouter(baixar=baixar, relogio=lambda: agora[0])
    catalogo.avaliar([PRINCIPAL])
    agora[0] = 4000
    assert catalogo.avaliar([PRINCIPAL]) == ([PRINCIPAL], {})


# =============================================================
# Provedor OpenRouter
# =============================================================

def test_pedido_usa_o_primeiro_aprovado_a_reserva_e_preco_maximo_zero():
    provedor = openrouter(resposta("Explicação."))
    assert provedor.responder(MENSAGENS, "instruções") == "Explicação."
    argumentos = provedor.criar.call_args.kwargs
    assert argumentos["model"] == PRINCIPAL
    assert argumentos["extra_body"]["models"] == [PRINCIPAL, RESERVA_1, RESERVA_2]
    assert argumentos["extra_body"]["provider"]["max_price"] == PRECO_MAXIMO_ZERO
    assert all(valor == 0 for valor in PRECO_MAXIMO_ZERO.values())


def test_regressao_d59d051d_classificador_nao_e_sucesso_e_a_nova_tentativa_vai_para_outro_modelo(caplog):
    caplog.set_level(logging.INFO)
    provedor = openrouter(
        resposta("User Safety: safe", modelo=CLASSIFICADOR),
        resposta("Um pipeline de dados é uma sequência de etapas...", modelo=RESERVA_1),
    )
    resultado = com_prazo([provedor])
    assert resultado.texto.startswith("Um pipeline de dados")
    assert [t.resultado for t in resultado.tentativas] == ["resposta_inadequada", "respondeu"]
    # O modelo que respondeu mal ficou de quarentena; a 2ª tentativa começou pelo próximo.
    segunda = provedor.criar.call_args_list[1].kwargs
    assert segunda["model"] == PRINCIPAL  # o principal não foi quem respondeu mal
    assert CLASSIFICADOR in caplog.text and "quarentena" in caplog.text
    assert "User Safety" not in caplog.text  # o texto da resposta não vai para o log


def test_resposta_classificatoria_de_modelo_com_nome_normal_poe_ele_de_quarentena():
    provedor = openrouter(
        resposta("Safety Categories: none", modelo=PRINCIPAL),
        resposta("Explicação de verdade.", modelo=RESERVA_1),
    )
    assert com_prazo([provedor]).texto == "Explicação de verdade."
    segunda = provedor.criar.call_args_list[1].kwargs
    assert segunda["model"] == RESERVA_1  # o principal ficou de fora
    assert segunda["extra_body"]["models"] == [RESERVA_1, RESERVA_2]


def test_duas_respostas_inadequadas_viram_mensagem_amigavel_sem_mostrar_o_rotulo():
    provedor = openrouter(resposta("User Safety: safe", modelo=CLASSIFICADOR), resposta("unsafe", modelo=CLASSIFICADOR))
    with pytest.raises(SemResposta) as erro:
        com_prazo([provedor])
    assert "Safety" not in erro.value.mensagem_para_pessoa
    assert [t.resultado for t in erro.value.tentativas] == ["resposta_inadequada", "resposta_inadequada"]


def test_resposta_vazia_poe_o_modelo_de_quarentena():
    quarentena = Quarentena()
    provedor = openrouter(resposta("", modelo=PRINCIPAL), resposta("Agora sim.", modelo=RESERVA_1), quarentena=quarentena)
    assert com_prazo([provedor]).texto == "Agora sim."
    assert quarentena.filtrar([PRINCIPAL, RESERVA_1]) == [RESERVA_1]


def test_modelo_que_ficou_pago_no_catalogo_e_pulado():
    catalogo = catalogo_com(item_do_catalogo(PRINCIPAL, prompt="0.0000001"), item_do_catalogo(RESERVA_1))
    provedor = openrouter(resposta("ok", modelo=RESERVA_1), catalogo=catalogo)
    provedor.responder(MENSAGENS, "instruções")
    argumentos = provedor.criar.call_args.kwargs
    assert argumentos["model"] == RESERVA_1
    assert "models" not in argumentos["extra_body"]  # só sobrou um modelo


def test_nenhum_modelo_adequado_no_catalogo_mostra_mensagem_clara_sem_chamar_a_ia():
    catalogo = catalogo_com(item_do_catalogo(PRINCIPAL, completion="2"))
    provedor = openrouter(resposta("não deveria ser chamado"), catalogo=catalogo)
    with pytest.raises(SemResposta) as erro:
        com_prazo([provedor])
    assert erro.value.mensagem_para_pessoa == MENSAGEM_SEM_MODELO
    provedor.criar.assert_not_called()


def test_sem_catalogo_usa_a_lista_do_config_com_preco_maximo_zero():
    catalogo = CatalogoOpenRouter(baixar=MagicMock(side_effect=OSError("sem rede")))
    provedor = openrouter(resposta("ok"), catalogo=catalogo)
    assert provedor.responder(MENSAGENS, "instruções") == "ok"
    argumentos = provedor.criar.call_args.kwargs
    assert argumentos["model"] == PRINCIPAL
    assert argumentos["extra_body"]["provider"]["max_price"] == PRECO_MAXIMO_ZERO


def test_provedor_recusa_modelos_inadequados_mesmo_fora_do_config():
    with pytest.raises(ValueError):
        ProvedorOpenRouter("openrouter", "openrouter/free", CHAVE_FALSA, CONFIG.geracao, cliente=MagicMock())


def test_criar_provedores_usa_o_openrouter_seguro_com_a_reserva_do_config():
    [openrouter_real] = [p for p in criar_provedores(CONFIG, {"OPENROUTER_API_KEY": CHAVE_FALSA}) if p.nome == "openrouter"]
    [item] = [p for p in CONFIG.provedores if p.nome == "openrouter"]
    assert isinstance(openrouter_real, ProvedorOpenRouter)
    assert openrouter_real.modelos == [item.modelo, *item.modelos_reserva]


# =============================================================
# Todos os modelos de quarentena
# =============================================================

def test_quarentena_com_todos_bloqueados_devolve_lista_vazia_ate_vencer():
    agora = [0.0]
    quarentena = Quarentena(relogio=lambda: agora[0])
    quarentena.adicionar(PRINCIPAL, segundos=100)
    quarentena.adicionar(RESERVA_1, segundos=200)
    assert quarentena.filtrar([PRINCIPAL, RESERVA_1]) == []  # nunca volta a usar os bloqueados
    agora[0] = 150
    assert quarentena.filtrar([PRINCIPAL, RESERVA_1]) == [PRINCIPAL]  # venceu a do principal
    agora[0] = 250
    assert quarentena.filtrar([PRINCIPAL, RESERVA_1]) == [PRINCIPAL, RESERVA_1]


def quarentena_com(*modelos):
    quarentena = Quarentena()
    for modelo in modelos:
        quarentena.adicionar(modelo)
    return quarentena


def test_todos_de_quarentena_nao_consulta_catalogo_nem_ia_e_mostra_mensagem_amigavel(caplog):
    caplog.set_level(logging.INFO)
    baixar = MagicMock(return_value=list(CATALOGO_BOM))
    provedor = openrouter(
        resposta("não deveria ser chamado"),
        catalogo=CatalogoOpenRouter(baixar=baixar),
        quarentena=quarentena_com(PRINCIPAL, RESERVA_1, RESERVA_2),
    )
    with pytest.raises(SemResposta) as erro:
        com_prazo([provedor])
    provedor.criar.assert_not_called()  # a IA não foi consultada
    baixar.assert_not_called()  # nem o catálogo
    assert erro.value.mensagem_para_pessoa == MENSAGEM_SEM_MODELO
    assert [t.resultado for t in erro.value.tentativas] == ["sem_modelo_adequado"]  # sem nova tentativa
    assert "todos_em_quarentena" in caplog.text


def test_o_ultimo_modelo_livre_responde_mal_e_a_nova_tentativa_nao_volta_aos_bloqueados():
    provedor = openrouter(
        resposta("User Safety: safe", modelo=RESERVA_2),
        resposta("não deveria ser chamado"),
        quarentena=quarentena_com(PRINCIPAL, RESERVA_1),
    )
    with pytest.raises(SemResposta) as erro:
        com_prazo([provedor])
    assert provedor.criar.call_count == 1  # só o último livre foi chamado
    assert provedor.criar.call_args.kwargs["model"] == RESERVA_2
    assert [t.resultado for t in erro.value.tentativas] == ["resposta_inadequada", "sem_modelo_adequado"]
    assert erro.value.mensagem_para_pessoa == MENSAGEM_SEM_MODELO


def test_todos_de_quarentena_pelo_chat_mostra_o_aviso_amigavel():
    provedor = openrouter(
        resposta("Resposta boa.", modelo=PRINCIPAL),
        quarentena=quarentena_com(PRINCIPAL, RESERVA_1, RESERVA_2),
    )
    chat = Assistente(CONFIG, provedores=[provedor], limitador=Limitador(CONFIG.limites))
    resultado = chat.responder("Pergunta 1", [])
    assert resultado.texto == MENSAGEM_SEM_MODELO
    assert resultado.situacao == "falha:sem_modelo_adequado"
    provedor.criar.assert_not_called()


# =============================================================
# Pela tela/chat: o rótulo nunca chega à pessoa nem ao histórico
# =============================================================

def test_chat_nunca_mostra_o_rotulo_e_o_aviso_fica_fora_do_historico():
    provedor = openrouter(
        resposta("User Safety: safe", modelo=CLASSIFICADOR), resposta("unsafe", modelo=CLASSIFICADOR),
        resposta("Resposta boa.", modelo=RESERVA_1),
    )
    chat = Assistente(CONFIG, provedores=[provedor], limitador=Limitador(CONFIG.limites))
    primeira = chat.responder("Pergunta 1", [])
    assert "Safety" not in primeira.texto and "safe" not in primeira.texto.lower()
    historico = [{"role": "user", "content": "Pergunta 1"}, {"role": "assistant", "content": primeira.texto}]
    assert chat.responder("Pergunta 2", historico).texto == "Resposta boa."
    enviadas = provedor.criar.call_args.kwargs["messages"]
    assert [m["content"] for m in enviadas if m["role"] != "system"] == ["Pergunta 2"]


def test_aviso_sem_modelo_fica_fora_do_historico():
    provedor = openrouter(resposta("ok"))
    chat = Assistente(CONFIG, provedores=[provedor], limitador=Limitador(CONFIG.limites))
    historico = [{"role": "user", "content": "Pergunta 1"}, {"role": "assistant", "content": MENSAGEM_SEM_MODELO}]
    chat.responder("Pergunta 2", historico)
    enviadas = provedor.criar.call_args.kwargs["messages"]
    assert [m["content"] for m in enviadas if m["role"] != "system"] == ["Pergunta 2"]


# =============================================================
# scripts/testar_openrouter.py (sem rede: só os casos que não chamam a IA)
# =============================================================

def test_validacao_real_sem_chave_para_sem_chamar_nada(capsys, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parent.parent / "scripts"))
    import testar_openrouter as teste_real

    assert teste_real.main(ambiente={}) == 1
    assert "OPENROUTER_API_KEY" in capsys.readouterr().out
