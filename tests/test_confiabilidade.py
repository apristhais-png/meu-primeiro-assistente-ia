"""Testes de velocidade e confiabilidade: prazo total, novas tentativas,
respostas vazias ou incompletas, erros que não devem ser repetidos e
pergunta duplicada.

Tudo com provedores simulados: a rede fica bloqueada, as chaves são falsas
e nada gera custo. Os tempos aqui são de simulação (time.sleep), não
medições do OpenRouter de verdade.
"""

import logging
import socket
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx2
import openai
import pytest

from assistente import provedores as modulo
from assistente.chat import MENSAGEM_AGUARDE, Assistente
from assistente.config import ErroDeConfiguracao, carregar_configuracao, validar_dados
from assistente.interface import criar_funcao_de_resposta
from assistente.limites import Limitador
from assistente.provedores import (
    MENSAGEM_DEMORA,
    MENSAGEM_MUITOS_PEDIDOS,
    MENSAGEM_SEM_RESPOSTA,
    NOTA_RESPOSTA_INCOMPLETA,
    FalhaDoProvedor,
    ProvedorCompativelComOpenAI,
    SemResposta,
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
def rapido_e_sem_rede(monkeypatch):
    """Sem internet; esperas encurtadas para os testes rodarem em segundos."""

    def proibido(*args, **kwargs):
        raise RuntimeError("Acesso à rede bloqueado nos testes")

    monkeypatch.setattr(socket.socket, "connect", proibido)
    monkeypatch.setattr(socket, "create_connection", proibido)
    monkeypatch.setattr(modulo, "ESPERA_ANTES_DE_REPETIR", 0.05)
    monkeypatch.setattr(modulo, "TEMPO_MINIMO_POR_TENTATIVA", 0.2)


# ---------- Ajudantes ----------

def resposta_openrouter(texto, fim="stop", modelo="exemplo/modelo-gratis:free", raciocinio=None):
    mensagem = SimpleNamespace(content=texto, reasoning=raciocinio)
    return SimpleNamespace(
        model=modelo,
        usage=SimpleNamespace(completion_tokens=42),
        choices=[SimpleNamespace(message=mensagem, finish_reason=fim)],
    )


def erro_http(status, corpo=None):
    corpo = corpo if corpo is not None else {"error": {"message": "erro do provedor"}}
    resposta = httpx2.Response(status, request=REQUISICAO, json=corpo)
    return openai.APIStatusError("erro do provedor", response=resposta, body=corpo)


def openrouter(*efeitos, chave=CHAVE_FALSA, nome="openrouter"):
    """Provedor real (classificação de erros de verdade) com cliente simulado.

    Cada item de "efeitos" é o resultado de uma chamada: uma resposta ou um erro.
    """
    cliente = MagicMock()
    cliente.chat.completions.create.side_effect = list(efeitos)
    provedor = ProvedorCompativelComOpenAI(nome, "openrouter/free", chave, GERACAO, cliente=cliente)
    provedor.criar = cliente.chat.completions.create
    return provedor


class IALenta:
    """Provedor simulado que demora "segundos" para responder."""

    nome = "openrouter"
    disponivel = True

    def __init__(self, segundos, texto="Resposta lenta"):
        self.segundos = segundos
        self.texto = texto
        self.chamadas = 0

    def responder(self, mensagens, instrucoes):
        self.chamadas += 1
        time.sleep(self.segundos)
        return self.texto


def com_prazo(provedores, total=5.0, por_tentativa=None, vezes=2):
    return responder_com_fallback(
        provedores, MENSAGENS, INSTRUCOES,
        tempo_maximo_total=total, timeout_por_tentativa=por_tentativa, tentativas_por_provedor=vezes,
    )


# =============================================================
# 1. Resposta rápida
# =============================================================

def test_resposta_rapida_usa_uma_unica_chamada_com_prazo_na_biblioteca():
    provedor = openrouter(resposta_openrouter("Olá!"))
    resposta = com_prazo([provedor], total=60, por_tentativa=45)
    assert (resposta.texto, resposta.provedor) == ("Olá!", "openrouter")
    assert provedor.criar.call_count == 1
    # O prazo da tentativa também vai para a biblioteca HTTP.
    assert 0 < provedor.criar.call_args.kwargs["timeout"] <= 45


# =============================================================
# 2 e 12. Lentidão: tempo esgotado e prazo total respeitado
# =============================================================

def test_resposta_lenta_vira_tempo_esgotado_sem_esperar_o_provedor():
    lenta = IALenta(segundos=3)
    inicio = time.monotonic()
    with pytest.raises(SemResposta) as erro:
        com_prazo([lenta], total=5, por_tentativa=0.5)
    decorrido = time.monotonic() - inicio
    assert decorrido < 1.5  # parou de esperar no prazo da tentativa, não nos 3 s
    assert lenta.chamadas == 1  # tempo esgotado não é repetido
    assert [t.resultado for t in erro.value.tentativas] == ["tempo_esgotado"]
    assert erro.value.mensagem_para_pessoa == MENSAGEM_DEMORA


def test_prazo_total_vale_para_tentativas_esperas_e_fallback_juntos():
    # Três provedores lentos: cada um caberia no prazo da tentativa, mas
    # juntos estourariam o prazo total. A pergunta inteira respeita o total.
    lentos = [IALenta(segundos=2) for _ in range(3)]
    for nome, ia in zip(("openrouter", "anthropic", "openai"), lentos, strict=True):
        ia.nome = nome
    inicio = time.monotonic()
    with pytest.raises(SemResposta):
        com_prazo(lentos, total=1.5, por_tentativa=1.0)
    assert time.monotonic() - inicio < 1.5 + 0.5
    assert lentos[2].chamadas == 0  # não sobrou tempo para o terceiro


def test_sem_tempo_para_nova_tentativa_nao_repete(monkeypatch):
    # Relógio simulado: a 1ª tentativa falha depois de 50 s de um total de 60.
    instantes = iter([0.0, 0.0, 0.0, 50.0, 50.0, 50.0, 50.0])
    provedor = openrouter(erro_http(503), resposta_openrouter("não deveria chegar aqui"))
    monkeypatch.setattr(modulo, "TEMPO_MINIMO_POR_TENTATIVA", 15.0)
    with pytest.raises(SemResposta):
        responder_com_fallback(
            [provedor], MENSAGENS, INSTRUCOES, tempo_maximo_total=60, tentativas_por_provedor=2,
            relogio=lambda: next(instantes),
        )
    assert provedor.criar.call_count == 1  # sobram 10 s, menos que o mínimo de 15 s: não repete


# =============================================================
# 3. Resposta vazia e resposta incompleta
# =============================================================

def test_resposta_vazia_e_repetida_uma_vez_e_depois_desiste(caplog):
    caplog.set_level(logging.INFO, logger="assistente.provedores")
    provedor = openrouter(
        resposta_openrouter("", fim="length", raciocinio="pensando muito"),
        resposta_openrouter("   ", fim="stop"),
        resposta_openrouter("não deveria ser chamado"),
    )
    with pytest.raises(SemResposta) as erro:
        com_prazo([provedor])
    assert provedor.criar.call_count == 2  # tentativas_por_provedor = 2
    assert [t.resultado for t in erro.value.tentativas] == ["resposta_vazia", "resposta_vazia"]
    assert erro.value.mensagem_para_pessoa == MENSAGEM_SEM_RESPOSTA
    # O log mostra a provável causa (raciocínio gastou o max_tokens), sem o conteúdo.
    assert "fim=length" in caplog.text and "raciocinio=sim" in caplog.text
    assert "pensando muito" not in caplog.text


def test_resposta_vazia_seguida_de_resposta_boa():
    provedor = openrouter(resposta_openrouter(""), resposta_openrouter("Agora sim!"))
    resposta = com_prazo([provedor])
    assert resposta.texto == "Agora sim!"
    assert [t.resultado for t in resposta.tentativas] == ["resposta_vazia", "respondeu"]


def test_resposta_cortada_pelo_tamanho_avisa_a_pessoa():
    provedor = openrouter(resposta_openrouter("Começo da explicação", fim="length"))
    resposta = com_prazo([provedor])
    assert resposta.texto == "Começo da explicação" + NOTA_RESPOSTA_INCOMPLETA
    assert provedor.criar.call_count == 1  # resposta parcial não gera outra chamada


# =============================================================
# 4. Erro 429: sem nova tentativa
# =============================================================

def test_erro_429_nao_e_repetido_e_mostra_mensagem_propria():
    provedor = openrouter(erro_http(429), resposta_openrouter("não deveria ser chamado"))
    with pytest.raises(SemResposta) as erro:
        com_prazo([provedor])
    assert provedor.criar.call_count == 1  # respeita o limite do plano gratuito
    assert erro.value.mensagem_para_pessoa == MENSAGEM_MUITOS_PEDIDOS


# =============================================================
# 5 e 6. 404, chave e cobrança: param tudo, sem repetir
# =============================================================

@pytest.mark.parametrize(
    ("erro", "tipo"),
    [
        (erro_http(404), "requisicao_invalida"),
        (erro_http(401), "autenticacao"),
        (erro_http(403), "permissao"),
        (erro_http(402), "cobranca"),
        (erro_http(429, {"error": {"code": "insufficient_quota"}}), "cobranca"),
    ],
)
def test_erros_de_configuracao_nao_repetem_nem_fazem_fallback(erro, tipo):
    primeiro = openrouter(erro, resposta_openrouter("não deveria ser chamado"))
    segundo = openrouter(resposta_openrouter("nem este"), nome="anthropic")
    with pytest.raises(SemResposta) as resultado:
        com_prazo([primeiro, segundo])
    assert primeiro.criar.call_count == 1
    segundo.criar.assert_not_called()
    assert resultado.value.erro_de_configuracao is True
    assert [t.resultado for t in resultado.value.tentativas] == [tipo]
    assert resultado.value.mensagem_para_pessoa == MENSAGEM_SEM_RESPOSTA


# =============================================================
# 7 e 8. Falha temporária com recuperação; todas as tentativas falham
# =============================================================

@pytest.mark.parametrize(
    "falha", [erro_http(503), erro_http(500), openai.APIConnectionError(request=REQUISICAO)]
)
def test_falha_temporaria_seguida_de_recuperacao(falha):
    provedor = openrouter(falha, resposta_openrouter("Recuperado"))
    resposta = com_prazo([provedor])
    assert resposta.texto == "Recuperado"
    assert provedor.criar.call_count == 2


def test_todas_as_tentativas_gratuitas_falham_com_limite_de_chamadas():
    provedor = openrouter(erro_http(503), erro_http(502), erro_http(500))
    with pytest.raises(SemResposta) as erro:
        com_prazo([provedor], vezes=2)
    assert provedor.criar.call_count == 2  # nunca passa do limite
    assert erro.value.mensagem_para_pessoa == MENSAGEM_SEM_RESPOSTA


def test_com_outro_provedor_disponivel_faz_fallback_em_vez_de_repetir():
    primeiro = openrouter(erro_http(503), resposta_openrouter("não repetir"))
    segundo = openrouter(resposta_openrouter("do segundo"), nome="openai")
    resposta = com_prazo([primeiro, segundo])
    assert resposta.provedor == "openai"
    assert primeiro.criar.call_count == 1


# =============================================================
# 9. Provedores pagos nunca são chamados sem chave
# =============================================================

def test_so_com_a_chave_do_openrouter_nenhum_provedor_pago_e_chamado():
    lista = criar_provedores(CONFIG, {"OPENROUTER_API_KEY": CHAVE_FALSA})
    clientes = {}
    for provedor in lista:
        clientes[provedor.nome] = provedor._cliente = MagicMock()
    clientes["openrouter"].chat.completions.create.side_effect = [erro_http(503), erro_http(503)]

    with pytest.raises(SemResposta) as erro:
        com_prazo(lista)

    assert clientes["openrouter"].chat.completions.create.call_count == 2
    clientes["anthropic"].messages.create.assert_not_called()
    clientes["openai"].chat.completions.create.assert_not_called()
    assert [t.resultado for t in erro.value.tentativas] == ["servidor", "servidor", "sem_chave", "sem_chave"]


def test_modelo_do_openrouter_no_config_e_o_roteador_gratuito():
    [item] = [p for p in CONFIG.provedores_ativos if p.nome == "openrouter"]
    assert item.modelo == "openrouter/free"


# =============================================================
# 10. Histórico depois de sucesso e de falha
# =============================================================

class IAFalsa:
    nome = "openrouter"
    disponivel = True

    def __init__(self, *efeitos):
        self.efeitos = list(efeitos)
        self.recebido = []

    def responder(self, mensagens, instrucoes):
        self.recebido.append([dict(m) for m in mensagens])
        efeito = self.efeitos.pop(0)
        if isinstance(efeito, Exception):
            raise efeito
        return efeito


def test_historico_correto_depois_de_sucesso_e_de_falha():
    ia = IAFalsa("Resposta 1", FalhaDoProvedor("openrouter", "tempo_esgotado"), "Resposta 3")
    chat = Assistente(CONFIG, provedores=[ia], limitador=Limitador(CONFIG.limites))

    r1 = chat.responder("Pergunta 1", [])
    historico = [{"role": "user", "content": "Pergunta 1"}, {"role": "assistant", "content": r1.texto}]
    r2 = chat.responder("Pergunta 2", historico)
    assert r2.texto == MENSAGEM_DEMORA
    historico += [{"role": "user", "content": "Pergunta 2"}, {"role": "assistant", "content": r2.texto}]
    r3 = chat.responder("Pergunta 3", historico)

    assert r3.texto == "Resposta 3"
    # A pergunta que falhou e o aviso de demora não vão para a IA.
    assert ia.recebido[-1] == [
        {"role": "user", "content": "Pergunta 1"},
        {"role": "assistant", "content": "Resposta 1"},
        {"role": "user", "content": "Pergunta 3"},
    ]


# =============================================================
# 11. Pergunta duplicada da mesma sessão
# =============================================================

class AssistenteLento:
    def __init__(self):
        self.chamadas = 0
        self.liberar = threading.Event()

    def responder(self, pergunta, historico, cabecalhos):
        self.chamadas += 1
        self.liberar.wait(5)
        return SimpleNamespace(texto="ok")


def test_pergunta_duplicada_da_mesma_sessao_e_recusada_sem_chamar_a_ia():
    lento = AssistenteLento()
    responder = criar_funcao_de_resposta(lento)
    sessao = SimpleNamespace(headers={}, session_hash="sessao-a")
    primeira = {}
    linha = threading.Thread(target=lambda: primeira.setdefault("r", responder("1", [], sessao)))
    linha.start()
    time.sleep(0.2)

    assert responder("1 de novo", [], sessao) == MENSAGEM_AGUARDE  # mesma sessão: recusada
    outra = {}
    outra_linha = threading.Thread(
        target=lambda: outra.setdefault("r", responder("x", [], SimpleNamespace(headers={}, session_hash="sessao-b")))
    )
    outra_linha.start()  # outra pessoa continua sendo atendida
    time.sleep(0.2)
    lento.liberar.set()
    linha.join(5)
    outra_linha.join(5)

    assert primeira["r"] == "ok" and outra["r"] == "ok"
    assert lento.chamadas == 2  # a duplicada não chegou ao assistente
    assert responder("2", [], sessao) == "ok"  # terminada a primeira, a sessão volta a perguntar


# =============================================================
# Configuração e logs
# =============================================================

def test_tempo_total_menor_que_o_de_uma_tentativa_e_recusado():
    dados = CONFIG.model_dump()
    dados["geracao"] |= {"timeout_segundos": 50, "tempo_maximo_total_segundos": 30}
    with pytest.raises(ErroDeConfiguracao) as erro:
        validar_dados(dados)
    assert "tempo_maximo_total_segundos" in str(erro.value)


def test_config_atual_limita_a_espera_e_as_chamadas():
    assert GERACAO.tempo_maximo_total_segundos == 60
    assert GERACAO.timeout_segundos <= GERACAO.tempo_maximo_total_segundos
    assert GERACAO.tentativas_por_provedor == 2


def test_logs_tem_tempos_e_resultado_mas_nunca_conteudo_nem_chave(caplog):
    caplog.set_level(logging.INFO)
    provedor = openrouter(erro_http(503), resposta_openrouter("resposta-secreta-456"))
    chat = Assistente(CONFIG, provedores=[provedor], limitador=Limitador(CONFIG.limites))
    assert chat.responder(PERGUNTA_SECRETA, []).texto == "resposta-secreta-456"

    logs = caplog.text
    assert "pergunta_inicio id=" in logs
    assert "resultado=servidor" in logs and "resultado=sucesso" in logs
    assert "duracao_ms=" in logs and "total_ms=" in logs
    assert "modelo_servido=exemplo/modelo-gratis:free" in logs
    # O mesmo id liga todas as linhas desta pergunta.
    ids = {linha.split("id=")[1].split()[0] for linha in logs.splitlines() if " id=" in linha}
    assert len(ids) == 1
    for proibido in (PERGUNTA_SECRETA, "resposta-secreta-456", CHAVE_FALSA, INSTRUCOES):
        assert proibido not in logs
