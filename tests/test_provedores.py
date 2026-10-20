"""Testes dos provedores e do fallback (SPEC, testes T3 e parte do T5).

Nenhum teste chama uma IA de verdade: os clientes da OpenAI e da Anthropic
são simulados (mocks), e a rede fica bloqueada durante os testes. As chaves
usadas são textos falsos, como "chave-de-teste-nao-real".
"""

import logging
import socket
from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx2
import openai
import pytest

from assistente.config import carregar_configuracao
from assistente.provedores import (
    ENDERECO_OPENROUTER,
    MENSAGEM_SEM_RESPOSTA,
    FalhaDoProvedor,
    ProvedorAnthropic,
    ProvedorCompativelComOpenAI,
    SemResposta,
    classificar_erro,
    criar_provedores,
    responder_com_fallback,
)

CONFIG = carregar_configuracao()
GERACAO = CONFIG.geracao
CHAVE_FALSA = "chave-de-teste-nao-real-12345"
INSTRUCOES = "Você é um professor paciente."
PERGUNTA_SECRETA = "pergunta-secreta-123"
MENSAGENS = [{"role": "user", "content": PERGUNTA_SECRETA}]
REQUISICAO = httpx2.Request("POST", "https://exemplo.invalid/v1")


@pytest.fixture(autouse=True)
def bloquear_rede(monkeypatch):
    """Garante que nenhum teste consiga acessar a internet."""

    def proibido(*args, **kwargs):
        raise RuntimeError("Acesso à rede bloqueado nos testes")

    monkeypatch.setattr(socket.socket, "connect", proibido)
    monkeypatch.setattr(socket, "create_connection", proibido)


# ---------- Ajudantes para montar respostas e erros simulados ----------


def resposta_openai(texto):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=texto))])


def resposta_anthropic(*blocos):
    return SimpleNamespace(content=list(blocos))


def bloco_texto(texto):
    return SimpleNamespace(type="text", text=texto)


def erro_http(sdk, status, corpo=None, mensagem="erro do provedor"):
    corpo = corpo if corpo is not None else {"error": {"message": mensagem}}
    resposta = httpx2.Response(status, request=REQUISICAO, json=corpo)
    return sdk.APIStatusError(mensagem, response=resposta, body=corpo)


def provedor_simulado(nome="openrouter", chave=CHAVE_FALSA, resposta="Olá!", erro=None):
    """Provedor real com cliente simulado: testa a classificação de erros de verdade."""
    cliente = MagicMock()
    if nome == "anthropic":
        criar = cliente.messages.create
        retorno = resposta_anthropic(bloco_texto(resposta))
        provedor = ProvedorAnthropic(nome, "modelo-teste", chave, GERACAO, cliente=cliente)
    else:
        criar = cliente.chat.completions.create
        retorno = resposta_openai(resposta)
        provedor = ProvedorCompativelComOpenAI(nome, "modelo-teste", chave, GERACAO, cliente=cliente)
    if erro is not None:
        criar.side_effect = erro
    else:
        criar.return_value = retorno
    provedor.criar = criar  # atalho para os testes conferirem as chamadas
    return provedor


# =============================================================
# T3 — Cada provedor monta a requisição certa
# =============================================================


def test_openrouter_envia_modelo_instrucoes_temperatura_e_max_tokens():
    provedor = provedor_simulado("openrouter", resposta="Resposta do OpenRouter")
    assert provedor.responder(MENSAGENS, INSTRUCOES) == "Resposta do OpenRouter"
    provedor.criar.assert_called_once_with(
        model="modelo-teste",
        messages=[{"role": "system", "content": INSTRUCOES}, *MENSAGENS],
        temperature=GERACAO.temperatura,
        max_tokens=GERACAO.max_tokens,
    )


def test_openai_usa_max_completion_tokens():
    provedor = provedor_simulado("openai")
    provedor.responder(MENSAGENS, INSTRUCOES)
    argumentos = provedor.criar.call_args.kwargs
    assert argumentos["max_completion_tokens"] == GERACAO.max_tokens
    assert "max_tokens" not in argumentos


def test_anthropic_envia_instrucoes_como_system_e_nao_envia_temperatura():
    provedor = provedor_simulado("anthropic", resposta="Resposta do Claude")
    assert provedor.responder(MENSAGENS, INSTRUCOES) == "Resposta do Claude"
    provedor.criar.assert_called_once_with(
        model="modelo-teste",
        max_tokens=GERACAO.max_tokens,
        system=INSTRUCOES,
        messages=MENSAGENS,
    )


def test_anthropic_junta_so_os_blocos_de_texto():
    provedor = provedor_simulado("anthropic")
    provedor.criar.return_value = resposta_anthropic(
        SimpleNamespace(type="thinking", thinking="raciocínio interno"),
        bloco_texto("Parte 1. "),
        bloco_texto("Parte 2."),
    )
    assert provedor.responder(MENSAGENS, INSTRUCOES) == "Parte 1. Parte 2."


def test_cliente_real_do_openrouter_usa_o_endereco_certo_e_nao_repete_sozinho():
    # Criar o cliente não acessa a rede; só conferimos a configuração dele.
    provedor = ProvedorCompativelComOpenAI("openrouter", "m", CHAVE_FALSA, GERACAO, endereco=ENDERECO_OPENROUTER)
    assert str(provedor.cliente.base_url).rstrip("/") == "https://openrouter.ai/api/v1"
    assert provedor.cliente.max_retries == 0
    assert provedor.cliente.timeout == GERACAO.timeout_segundos


def test_cliente_real_da_openai_usa_o_endereco_padrao():
    provedor = ProvedorCompativelComOpenAI("openai", "m", CHAVE_FALSA, GERACAO)
    assert str(provedor.cliente.base_url).rstrip("/") == "https://api.openai.com/v1"
    assert provedor.cliente.max_retries == 0


def test_cliente_real_da_anthropic_nao_repete_sozinho():
    provedor = ProvedorAnthropic("anthropic", "m", CHAVE_FALSA, GERACAO)
    assert provedor.cliente.max_retries == 0
    assert provedor.cliente.timeout == GERACAO.timeout_segundos


# ---------- Chaves lidas do ambiente ----------


def test_criar_provedores_na_ordem_do_config_com_chaves_do_ambiente():
    ambiente = {
        "OPENROUTER_API_KEY": CHAVE_FALSA,
        "ANTHROPIC_API_KEY": CHAVE_FALSA,
        "OPENAI_API_KEY": CHAVE_FALSA,
    }
    provedores = criar_provedores(CONFIG, ambiente)
    assert [p.nome for p in provedores] == ["openrouter", "anthropic", "openai"]
    assert all(p.disponivel for p in provedores)
    assert provedores[0].endereco == ENDERECO_OPENROUTER
    assert [p.modelo for p in provedores] == [p.modelo for p in CONFIG.provedores]


def test_provedor_sem_chave_fica_indisponivel():
    provedores = criar_provedores(CONFIG, {"ANTHROPIC_API_KEY": CHAVE_FALSA, "OPENAI_API_KEY": "   "})
    assert [(p.nome, p.disponivel) for p in provedores] == [
        ("openrouter", False),
        ("anthropic", True),
        ("openai", False),  # só espaços conta como sem chave
    ]


def test_espacos_em_volta_da_chave_sao_removidos():
    provedor = ProvedorAnthropic("anthropic", "m", f"  {CHAVE_FALSA}\n", GERACAO)
    assert provedor._chave == CHAVE_FALSA


def test_provedor_desligado_no_config_nao_e_criado():
    dados = CONFIG.model_dump()
    dados["provedores"][0]["ativo"] = False
    config = type(CONFIG).model_validate(dados)
    assert [p.nome for p in criar_provedores(config, {})] == ["anthropic", "openai"]


# =============================================================
# T3 — Classificação dos erros: temporário x configuração
# =============================================================


@pytest.mark.parametrize("sdk", [openai, anthropic], ids=["openai", "anthropic"])
@pytest.mark.parametrize(
    ("status", "corpo", "tipo_esperado"),
    [
        (429, {"error": {"type": "rate_limit_error", "message": "Rate limit reached"}}, "limite_de_uso"),
        (408, None, "tempo_esgotado"),
        (500, None, "servidor"),
        (502, None, "servidor"),
        (503, None, "servidor"),
        (529, {"error": {"type": "overloaded_error"}}, "servidor"),
    ],
)
def test_falhas_temporarias_permitem_o_fallback(sdk, status, corpo, tipo_esperado):
    falha = classificar_erro("x", erro_http(sdk, status, corpo))
    assert falha.tipo == tipo_esperado
    assert falha.temporaria is True


@pytest.mark.parametrize("sdk", [openai, anthropic], ids=["openai", "anthropic"])
@pytest.mark.parametrize(
    ("status", "corpo", "tipo_esperado"),
    [
        (401, None, "autenticacao"),
        (403, None, "permissao"),
        (402, None, "cobranca"),
        # OpenAI: "sem créditos" chega como 429, mas é cobrança, não excesso de pedidos.
        (429, {"error": {"code": "insufficient_quota", "message": "You exceeded your current quota"}}, "cobranca"),
        # Anthropic: saldo insuficiente chega como 400.
        (400, {"error": {"type": "invalid_request_error", "message": "Your credit balance is too low"}}, "cobranca"),
        (400, {"type": "error", "error": {"type": "billing_error"}}, "cobranca"),
        # OpenRouter: créditos insuficientes chegam como 402.
        (402, {"error": {"message": "Insufficient credits"}}, "cobranca"),
        (404, {"error": {"message": "model not found"}}, "requisicao_invalida"),
        (400, {"error": {"message": "invalid parameter"}}, "requisicao_invalida"),
        (422, None, "requisicao_invalida"),
    ],
)
def test_erros_de_chave_cobranca_e_pedido_nao_sao_temporarios(sdk, status, corpo, tipo_esperado):
    falha = classificar_erro("x", erro_http(sdk, status, corpo))
    assert falha.tipo == tipo_esperado
    assert falha.temporaria is False


@pytest.mark.parametrize("sdk", [openai, anthropic], ids=["openai", "anthropic"])
def test_classes_especificas_de_erro_tambem_sao_reconhecidas(sdk):
    resposta = httpx2.Response(401, request=REQUISICAO, json={})
    erro = sdk.AuthenticationError("chave inválida", response=resposta, body={})
    assert classificar_erro("x", erro).tipo == "autenticacao"


@pytest.mark.parametrize("sdk", [openai, anthropic], ids=["openai", "anthropic"])
def test_tempo_esgotado_e_conexao_sao_temporarios(sdk):
    tempo = classificar_erro("x", sdk.APITimeoutError(request=REQUISICAO))
    conexao = classificar_erro("x", sdk.APIConnectionError(request=REQUISICAO))
    assert (tempo.tipo, tempo.temporaria) == ("tempo_esgotado", True)
    assert (conexao.tipo, conexao.temporaria) == ("conexao", True)


def test_erro_inesperado_nao_e_temporario():
    falha = classificar_erro("x", ValueError("algo estranho"))
    assert (falha.tipo, falha.temporaria) == ("inesperada", False)


@pytest.mark.parametrize("nome", ["openrouter", "anthropic"])
def test_resposta_vazia_e_falha_temporaria(nome):
    provedor = provedor_simulado(nome, resposta="   ")
    with pytest.raises(FalhaDoProvedor) as falha:
        provedor.responder(MENSAGENS, INSTRUCOES)
    assert (falha.value.tipo, falha.value.temporaria) == ("resposta_vazia", True)


# ---------- A chave nunca aparece ----------


@pytest.mark.parametrize("sdk,nome", [(openai, "openai"), (anthropic, "anthropic")])
def test_chave_nunca_aparece_no_erro(sdk, nome):
    # Alguns provedores repetem parte da chave na mensagem de erro.
    erro = erro_http(sdk, 401, mensagem=f"Incorrect API key provided: {CHAVE_FALSA}")
    provedor = provedor_simulado(nome, erro=erro)
    with pytest.raises(FalhaDoProvedor) as falha:
        provedor.responder(MENSAGENS, INSTRUCOES)
    assert CHAVE_FALSA not in str(falha.value)
    assert CHAVE_FALSA not in repr(falha.value)
    assert falha.value.__cause__ is None
    assert falha.value.__suppress_context__ is True
    assert CHAVE_FALSA not in repr(provedor)


# =============================================================
# Fallback (RF5, RF6, RF7)
# =============================================================


def test_se_o_primeiro_responde_o_segundo_nao_e_chamado():
    primeiro = provedor_simulado("openrouter", resposta="do primeiro")
    segundo = provedor_simulado("anthropic")
    resposta = responder_com_fallback([primeiro, segundo], MENSAGENS, INSTRUCOES)
    assert (resposta.texto, resposta.provedor) == ("do primeiro", "openrouter")
    segundo.criar.assert_not_called()


def test_falha_temporaria_no_primeiro_usa_o_segundo():
    primeiro = provedor_simulado("openrouter", erro=openai.APITimeoutError(request=REQUISICAO))
    segundo = provedor_simulado("anthropic", resposta="do segundo")
    resposta = responder_com_fallback([primeiro, segundo], MENSAGENS, INSTRUCOES)
    assert (resposta.texto, resposta.provedor) == ("do segundo", "anthropic")
    assert [t.resultado for t in resposta.tentativas] == ["tempo_esgotado", "respondeu"]


def test_dois_falham_temporariamente_e_o_terceiro_responde():
    provedores = [
        provedor_simulado("openrouter", erro=erro_http(openai, 503)),
        provedor_simulado("anthropic", erro=erro_http(anthropic, 429)),
        provedor_simulado("openai", resposta="do terceiro"),
    ]
    resposta = responder_com_fallback(provedores, MENSAGENS, INSTRUCOES)
    assert resposta.provedor == "openai"


def test_todos_falham_temporariamente():
    provedores = [
        provedor_simulado("openrouter", erro=erro_http(openai, 500)),
        provedor_simulado("anthropic", erro=anthropic.APIConnectionError(request=REQUISICAO)),
        provedor_simulado("openai", erro=openai.APITimeoutError(request=REQUISICAO)),
    ]
    with pytest.raises(SemResposta) as erro:
        responder_com_fallback(provedores, MENSAGENS, INSTRUCOES)
    assert erro.value.erro_de_configuracao is False
    assert erro.value.mensagem_para_pessoa == MENSAGEM_SEM_RESPOSTA
    assert [t.resultado for t in erro.value.tentativas] == ["servidor", "conexao", "tempo_esgotado"]


@pytest.mark.parametrize(
    ("erro", "tipo"),
    [
        (erro_http(openai, 401), "autenticacao"),
        (erro_http(openai, 403), "permissao"),
        (erro_http(openai, 402), "cobranca"),
        (erro_http(openai, 429, {"error": {"code": "insufficient_quota"}}), "cobranca"),
        (erro_http(openai, 404), "requisicao_invalida"),
    ],
)
def test_erro_de_chave_ou_cobranca_para_o_fallback(erro, tipo):
    primeiro = provedor_simulado("openrouter", erro=erro)
    segundo = provedor_simulado("anthropic")
    terceiro = provedor_simulado("openai")
    with pytest.raises(SemResposta) as resultado:
        responder_com_fallback([primeiro, segundo, terceiro], MENSAGENS, INSTRUCOES)
    assert resultado.value.erro_de_configuracao is True
    assert [t.resultado for t in resultado.value.tentativas] == [tipo]
    segundo.criar.assert_not_called()
    terceiro.criar.assert_not_called()


def test_falha_temporaria_e_depois_cobranca_para_no_segundo():
    primeiro = provedor_simulado("openrouter", erro=erro_http(openai, 503))
    segundo = provedor_simulado(
        "anthropic", erro=erro_http(anthropic, 400, {"error": {"message": "Your credit balance is too low"}})
    )
    terceiro = provedor_simulado("openai")
    with pytest.raises(SemResposta) as resultado:
        responder_com_fallback([primeiro, segundo, terceiro], MENSAGENS, INSTRUCOES)
    assert [t.resultado for t in resultado.value.tentativas] == ["servidor", "cobranca"]
    terceiro.criar.assert_not_called()


def test_provedor_sem_chave_e_pulado_sem_ser_chamado():
    # Critério CA3: sem a chave do OpenRouter, o próximo provedor responde.
    sem_chave = provedor_simulado("openrouter", chave=None)
    segundo = provedor_simulado("anthropic", resposta="do segundo")
    resposta = responder_com_fallback([sem_chave, segundo], MENSAGENS, INSTRUCOES)
    assert resposta.provedor == "anthropic"
    sem_chave.criar.assert_not_called()
    assert [t.resultado for t in resposta.tentativas] == ["sem_chave", "respondeu"]


def test_nenhuma_chave_configurada():
    # Critério CA4: sem nenhuma chave, a pessoa recebe a mensagem amigável.
    provedores = [provedor_simulado(n, chave=None) for n in ("openrouter", "anthropic", "openai")]
    with pytest.raises(SemResposta) as erro:
        responder_com_fallback(provedores, MENSAGENS, INSTRUCOES)
    assert erro.value.erro_de_configuracao is False
    assert erro.value.mensagem_para_pessoa == MENSAGEM_SEM_RESPOSTA
    for provedor in provedores:
        provedor.criar.assert_not_called()


def test_lista_vazia_de_provedores():
    with pytest.raises(SemResposta):
        responder_com_fallback([], MENSAGENS, INSTRUCOES)


# ---------- Logs (RF10) ----------


def test_logs_mostram_provedores_mas_nunca_chave_nem_conversa(caplog):
    caplog.set_level(logging.INFO, logger="assistente.provedores")
    erro = erro_http(openai, 503, mensagem=f"erro com a chave {CHAVE_FALSA}")
    provedores = [
        provedor_simulado("openrouter", erro=erro),
        provedor_simulado("anthropic", resposta="resposta-secreta-456"),
    ]
    responder_com_fallback(provedores, MENSAGENS, INSTRUCOES)
    logs = caplog.text
    assert "openrouter" in logs and "anthropic respondeu" in logs
    assert CHAVE_FALSA not in logs
    assert PERGUNTA_SECRETA not in logs
    assert "resposta-secreta-456" not in logs
    assert INSTRUCOES not in logs


def test_log_de_erro_de_configuracao_explica_o_que_fazer(caplog):
    caplog.set_level(logging.INFO, logger="assistente.provedores")
    provedor = provedor_simulado("openrouter", erro=erro_http(openai, 401, mensagem=CHAVE_FALSA))
    with pytest.raises(SemResposta):
        responder_com_fallback([provedor], MENSAGENS, INSTRUCOES)
    assert "chave de API foi recusada" in caplog.text
    assert "NÃO foram tentados" in caplog.text
    assert CHAVE_FALSA not in caplog.text


# ---------- A rede está mesmo bloqueada ----------


def test_rede_bloqueada_impede_chamada_real():
    # Se algum teste tentasse chamar a IA de verdade, falharia aqui (sem custo).
    provedor = ProvedorCompativelComOpenAI("openai", "m", CHAVE_FALSA, GERACAO)
    with pytest.raises(FalhaDoProvedor) as falha:
        provedor.responder(MENSAGENS, INSTRUCOES)
    assert falha.value.tipo in {"conexao", "inesperada"}
