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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
    MENSAGEM_OCUPADO,
    MENSAGEM_SEM_RESPOSTA,
    NOTA_RESPOSTA_INCOMPLETA,
    FalhaDoProvedor,
    ProvedorCompativelComOpenAI,
    SemResposta,
    chamadas_em_andamento,
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


LOCAIS = {"127.0.0.1", "localhost"}


@pytest.fixture(autouse=True)
def rapido_e_sem_rede(monkeypatch):
    """Sem internet (só o próprio computador); esperas encurtadas para os testes rodarem em segundos."""
    conectar_original = socket.socket.connect

    def so_local(sock, endereco):
        host = endereco[0] if isinstance(endereco, tuple) else endereco
        if host not in LOCAIS:
            raise RuntimeError("Acesso à rede bloqueado nos testes")
        return conectar_original(sock, endereco)

    monkeypatch.setattr(socket.socket, "connect", so_local)
    # Um proxy local (127.0.0.1) passaria pelo bloqueio acima e levaria o
    # pedido para a internet: sem as variáveis de proxy, isso não acontece.
    for variavel in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(variavel, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
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
        provedores,
        MENSAGENS,
        INSTRUCOES,
        tempo_maximo_total=total,
        timeout_por_tentativa=por_tentativa,
        tentativas_por_provedor=vezes,
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
            [provedor],
            MENSAGENS,
            INSTRUCOES,
            tempo_maximo_total=60,
            tentativas_por_provedor=2,
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


@pytest.mark.parametrize("falha", [erro_http(503), erro_http(500), openai.APIConnectionError(request=REQUISICAO)])
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
        # Caminho real: um cliente novo por tentativa (aqui, um simulado).
        clientes[provedor.nome] = MagicMock()
        provedor._criar_cliente = lambda c=clientes[provedor.nome]: c
    clientes["openrouter"].chat.completions.create.side_effect = [erro_http(503), erro_http(503)]

    with pytest.raises(SemResposta) as erro:
        com_prazo(lista)

    assert clientes["openrouter"].chat.completions.create.call_count == 2
    assert clientes["openrouter"].close.call_count == 2  # cada tentativa fecha o próprio cliente
    clientes["anthropic"].messages.create.assert_not_called()
    clientes["openai"].chat.completions.create.assert_not_called()
    assert [t.resultado for t in erro.value.tentativas] == ["servidor", "servidor", "sem_chave", "sem_chave"]


def test_modelos_do_openrouter_no_config_sao_gratuitos_e_explicitos():
    [item] = [p for p in CONFIG.provedores_ativos if p.nome == "openrouter"]
    for modelo in (item.modelo, *item.modelos_reserva):
        assert modelo.endswith(":free")
        assert not modelo.startswith("openrouter/")  # nada de roteador que sorteia classificadores


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

    def responder(self, pergunta, historico, cabecalhos, nivel=None, modo=None):
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


# =============================================================
# Cancelamento e teto de chamadas simultâneas (revisão do PR #5)
# =============================================================


def esperar_ate(condicao, segundos=5.0):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicao():
            return True
        time.sleep(0.02)
    return condicao()


def linhas_de_chamada():
    return sum(1 for linha in threading.enumerate() if linha.name == "chamada-ia")


@pytest.fixture
def teto(monkeypatch):
    """Troca o teto de chamadas simultâneas por um valor pequeno."""

    def aplicar(maximo):
        # Chamadas de testes anteriores que ignoram o cancelamento (IALenta)
        # ainda ocupam vagas por alguns segundos: é o teto funcionando.
        assert esperar_ate(lambda: chamadas_em_andamento() == 0, 5.0)
        monkeypatch.setattr(modulo, "MAX_CHAMADAS_SIMULTANEAS", maximo)
        monkeypatch.setattr(modulo, "_vagas", threading.BoundedSemaphore(maximo))

    yield aplicar
    assert esperar_ate(lambda: chamadas_em_andamento() == 0), "chamadas ficaram presas"


class IACancelavel:
    """IA simulada lenta que obedece ao cancelamento (como o cliente HTTP fechado)."""

    nome = "openrouter"
    disponivel = True
    aceita_cancelamento = True

    def __init__(self, segundos=5.0, obedece=True):
        self.segundos = segundos
        self.obedece = obedece
        self.chamadas = 0
        self.canceladas = 0
        self.ativas = 0
        self.maximo_de_ativas = 0
        self.trava = threading.Lock()

    def responder(self, mensagens, instrucoes, prazo=None, ao_iniciar=None):
        sinal = threading.Event()
        if ao_iniciar is not None and self.obedece:
            ao_iniciar(sinal.set)
        with self.trava:
            self.chamadas += 1
            self.ativas += 1
            self.maximo_de_ativas = max(self.maximo_de_ativas, self.ativas)
        try:
            if sinal.wait(self.segundos):
                with self.trava:
                    self.canceladas += 1
                raise FalhaDoProvedor(self.nome, "conexao")
            return "resposta tardia"
        finally:
            with self.trava:
                self.ativas -= 1


def test_varias_perguntas_lentas_ao_mesmo_tempo_respeitam_o_teto(teto):
    teto(3)
    ia = IACancelavel(segundos=10)
    resultados = []
    trava = threading.Lock()

    def perguntar():
        try:
            com_prazo([ia], total=0.8)
        except SemResposta as erro:
            with trava:
                resultados.append(erro.mensagem_para_pessoa)

    inicio = time.monotonic()
    pessoas = [threading.Thread(target=perguntar) for _ in range(10)]
    for pessoa in pessoas:
        pessoa.start()
    for pessoa in pessoas:
        pessoa.join(5)

    assert time.monotonic() - inicio < 2.0  # ninguém esperou os 10 s da IA
    assert len(resultados) == 10
    assert ia.maximo_de_ativas <= 3  # nunca mais que o teto ao mesmo tempo
    assert ia.chamadas <= 3  # sem vaga, nenhuma chamada nova foi criada
    assert set(resultados) <= {MENSAGEM_DEMORA, MENSAGEM_OCUPADO}
    assert MENSAGEM_OCUPADO in resultados
    # As chamadas canceladas terminam logo, e as vagas voltam.
    assert esperar_ate(lambda: chamadas_em_andamento() == 0, 2.0)
    assert ia.canceladas == ia.chamadas


def test_timeouts_seguidos_nao_acumulam_linhas_de_execucao(teto):
    teto(2)
    ia = IACancelavel(segundos=10)
    antes = linhas_de_chamada()
    for _ in range(15):
        with pytest.raises(SemResposta) as erro:
            com_prazo([ia], total=0.4)
        assert erro.value.mensagem_para_pessoa == MENSAGEM_DEMORA
        assert linhas_de_chamada() - antes <= 2  # nunca passa do teto
    assert esperar_ate(lambda: linhas_de_chamada() == antes, 2.0)
    assert ia.chamadas == 15 and ia.canceladas == 15  # todas canceladas de verdade


def test_ia_que_ignora_o_cancelamento_ocupa_a_vaga_ate_terminar_e_nada_novo_e_criado(teto):
    teto(2)
    ia = IACancelavel(segundos=3.0, obedece=False)
    respostas = []
    for _ in range(5):
        with pytest.raises(SemResposta) as erro:
            com_prazo([ia], total=0.5)
        respostas.append(erro.value.mensagem_para_pessoa)
        assert chamadas_em_andamento() <= 2
    # As duas primeiras ficaram presas (até 3 s); as outras nem começaram.
    assert ia.chamadas == 2
    assert respostas[:2] == [MENSAGEM_DEMORA, MENSAGEM_DEMORA]
    assert set(respostas[2:]) == {MENSAGEM_OCUPADO}
    # Quando terminam sozinhas, as vagas voltam e novas perguntas são atendidas.
    assert esperar_ate(lambda: chamadas_em_andamento() == 0, 4.0)


def test_aviso_de_ocupado_nao_vai_para_a_ia_no_historico():
    ia = IAFalsa("ok")
    chat = Assistente(CONFIG, provedores=[ia], limitador=Limitador(CONFIG.limites))
    historico = [{"role": "user", "content": "Pergunta 1"}, {"role": "assistant", "content": MENSAGEM_OCUPADO}]
    chat.responder("Pergunta 2", historico)
    assert ia.recebido[-1] == [{"role": "user", "content": "Pergunta 2"}]


def test_sem_vaga_nao_tenta_outro_provedor(teto):
    teto(1)
    presa = IACancelavel(segundos=1.0, obedece=False)
    with pytest.raises(SemResposta):
        com_prazo([presa], total=0.3)
    segundo = openrouter(resposta_openrouter("não deveria ser chamado"), nome="openai")
    with pytest.raises(SemResposta) as erro:
        com_prazo([IACancelavel(), segundo], total=0.4)
    assert [t.resultado for t in erro.value.tentativas] == ["sem_vaga"]
    segundo.criar.assert_not_called()


# ---------- Cliente real da biblioteca openai, com um servidor no próprio computador ----------


class _ServidorLento(BaseHTTPRequestHandler):
    """Responde 200 e fica 3 s sem terminar: mandando espaços ('ainda processando') ou em silêncio."""

    protocol_version = "HTTP/1.1"
    manda_sinais = True

    def log_message(self, *args):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        try:
            for _ in range(15):
                if self.manda_sinais:
                    self.wfile.write(b"1\r\n \r\n")
                    self.wfile.flush()
                time.sleep(0.2)
        except OSError:
            pass  # o app fechou a conexão (cancelou)


@pytest.fixture
def servidor_lento():
    servidores = []

    def abrir(manda_sinais):
        tratador = type("Tratador", (_ServidorLento,), {"manda_sinais": manda_sinais})
        servidor = ThreadingHTTPServer(("127.0.0.1", 0), tratador)
        servidor.daemon_threads = True
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        servidores.append(servidor)
        return f"http://127.0.0.1:{servidor.server_port}/v1"

    yield abrir
    for servidor in servidores:
        servidor.shutdown()
        servidor.server_close()


def provedor_real(endereco):
    return ProvedorCompativelComOpenAI("openrouter", "openrouter/free", CHAVE_FALSA, GERACAO, endereco=endereco)


def test_cancelamento_efetivo_quando_o_provedor_manda_sinais_de_processando(servidor_lento):
    # O caso dos 48 s: o provedor mantém a conexão viva. Fechar o cliente da
    # tentativa derruba a conexão e a chamada termina logo depois do prazo.
    provedor = provedor_real(servidor_lento(manda_sinais=True))
    inicio = time.monotonic()
    with pytest.raises(SemResposta) as erro:
        com_prazo([provedor], total=1.0, por_tentativa=1.0)
    assert time.monotonic() - inicio < 1.6
    assert erro.value.mensagem_para_pessoa == MENSAGEM_DEMORA
    assert esperar_ate(lambda: chamadas_em_andamento() == 0, 1.0)  # a chamada morreu de verdade


def test_provedor_em_silencio_termina_no_limite_de_leitura_da_tentativa(servidor_lento):
    # Em silêncio total, fechar não acorda a leitura bloqueada: ela acaba no
    # limite de leitura da tentativa (aqui 1 s), nunca depois disso.
    provedor = provedor_real(servidor_lento(manda_sinais=False))
    inicio = time.monotonic()
    with pytest.raises(SemResposta):
        com_prazo([provedor], total=1.0, por_tentativa=1.0)
    assert time.monotonic() - inicio < 1.6
    assert esperar_ate(lambda: chamadas_em_andamento() == 0, 2.0)
