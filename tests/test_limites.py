"""Testes dos limites de uso e da identificação pelo IP (SPEC, teste T4).

Tudo é simulado: os pedidos são só cabeçalhos montados no teste, e um
relógio falso "adianta o tempo" sem esperar de verdade. Nenhuma IA é chamada.

Os IPs de exemplo (8.8.8.8, 1.1.1.1...) são públicos de verdade, porque a
regra só aceita IPs públicos. IPs como 203.0.113.7 são de uma faixa reservada
para documentação e servem aqui como valores "inventados".
"""

import logging
import threading
from datetime import datetime

import pytest

from assistente.config import Limites
from assistente.limites import FUSO_DE_BRASILIA, MENSAGENS, Limitador, ip_confiavel

PESSOA_A = "8.8.8.8"
PESSOA_B = "1.1.1.1"
IPV6_PUBLICO = "2001:4860:4860::8888"


class RelogioFalso:
    """Relógio que só anda quando o teste manda."""

    def __init__(self, inicio: datetime):
        self.agora = inicio.timestamp()

    def __call__(self) -> float:
        return self.agora

    def adiantar(self, segundos: float) -> None:
        self.agora += segundos


def limites(**mudancas) -> Limites:
    valores = {
        "perguntas_por_minuto_total": 20,
        "perguntas_por_dia_total": 500,
        "tamanho_maximo_pergunta": 2000,
        "identificar_por_ip": True,
        "perguntas_por_minuto_por_pessoa": 5,
        "perguntas_por_dia_por_pessoa": 50,
    }
    valores.update(mudancas)
    return Limites(**valores)


def criar(relogio=None, **mudancas) -> tuple[Limitador, RelogioFalso]:
    relogio = relogio or RelogioFalso(datetime(2026, 10, 10, 14, 0, tzinfo=FUSO_DE_BRASILIA))
    return Limitador(limites(**mudancas), relogio=relogio), relogio


def de(*ips: str) -> dict:
    """Cabeçalhos de um pedido com o X-Forwarded-For dado."""
    return {"X-Forwarded-For": ", ".join(ips)}


class CabecalhosRepetidos:
    """Imita os cabeçalhos do Gradio/Starlette, que podem ter linhas repetidas."""

    def __init__(self, *linhas: str):
        self.linhas = linhas

    def getlist(self, nome):
        return list(self.linhas) if nome == "x-forwarded-for" else []


def perguntar(limitador, vezes, cabecalhos=None, pergunta="O que é ETL?"):
    return [limitador.verificar(pergunta, cabecalhos) for _ in range(vezes)]


# =============================================================
# Limites globais (sempre ativos)
# =============================================================

def test_limite_global_por_minuto_bloqueia_todo_mundo():
    limitador, relogio = criar(perguntas_por_minuto_total=3, perguntas_por_minuto_por_pessoa=3)
    assert limitador.verificar("1", de(PESSOA_A)).permitido
    assert limitador.verificar("2", de(PESSOA_B)).permitido
    assert limitador.verificar("3", de(IPV6_PUBLICO)).permitido

    bloqueada = limitador.verificar("4", de("9.9.9.9"))  # uma quarta pessoa, nova
    assert not bloqueada.permitido
    assert bloqueada.motivo == "global_minuto"
    assert bloqueada.mensagem == MENSAGENS["global_minuto"]

    relogio.adiantar(61)
    assert limitador.verificar("5", de("9.9.9.9")).permitido


def test_limite_global_por_dia_bloqueia_ate_a_meia_noite_de_brasilia():
    inicio = datetime(2026, 10, 10, 23, 50, tzinfo=FUSO_DE_BRASILIA)
    limitador, relogio = criar(RelogioFalso(inicio), perguntas_por_dia_total=2, perguntas_por_dia_por_pessoa=2)
    assert all(d.permitido for d in perguntar(limitador, 2, de(PESSOA_A)))

    relogio.adiantar(120)  # 23:52, outra pessoa, mesmo dia
    bloqueada = limitador.verificar("?", de(PESSOA_B))
    assert (bloqueada.permitido, bloqueada.motivo) == (False, "global_dia")

    relogio.adiantar(9 * 60)  # 00:01 do dia seguinte em Brasília
    assert limitador.verificar("?", de(PESSOA_B)).permitido


def test_o_dia_segue_o_horario_de_brasilia_e_nao_o_utc():
    # 22:30 em Brasília já é o dia seguinte em UTC; o limite não pode zerar aí.
    inicio = datetime(2026, 10, 10, 20, 0, tzinfo=FUSO_DE_BRASILIA)
    limitador, relogio = criar(RelogioFalso(inicio), perguntas_por_dia_total=1, perguntas_por_dia_por_pessoa=1)
    assert limitador.verificar("?").permitido
    relogio.adiantar(2.5 * 3600)  # 22:30 em Brasília (01:30 UTC do dia 11)
    assert limitador.verificar("?").motivo == "global_dia"


@pytest.mark.parametrize("identificar", [True, False])
def test_pergunta_longa_e_recusada(identificar):
    limitador, _ = criar(tamanho_maximo_pergunta=100, identificar_por_ip=identificar)
    assert limitador.verificar("a" * 100, de(PESSOA_A)).permitido
    recusada = limitador.verificar("a" * 101, de(PESSOA_A))
    assert (recusada.permitido, recusada.motivo) == (False, "pergunta_longa")
    assert recusada.mensagem == "Sua pergunta ficou muito longa. Tente resumir em até 100 caracteres."


def test_pergunta_longa_nao_gasta_a_cota():
    limitador, _ = criar(tamanho_maximo_pergunta=100, perguntas_por_minuto_total=1, perguntas_por_minuto_por_pessoa=1)
    for _ in range(5):
        assert limitador.verificar("a" * 500).motivo == "pergunta_longa"
    assert limitador.verificar("curta").permitido


def test_sem_identificacao_vale_so_o_limite_global():
    limitador, _ = criar(
        identificar_por_ip=False, perguntas_por_minuto_total=10, perguntas_por_minuto_por_pessoa=2
    )
    # A mesma pessoa passa do limite "por pessoa" (2), porque ele está desligado...
    decisoes = perguntar(limitador, 10, de(PESSOA_A))
    assert all(d.permitido for d in decisoes)
    assert all(d.pessoa is None for d in decisoes)
    # ...mas o limite global continua bloqueando.
    assert limitador.verificar("?", de(PESSOA_A)).motivo == "global_minuto"


# =============================================================
# Identificação segura (identificar_por_ip: true)
# =============================================================

def test_um_ip_no_x_forwarded_for_identifica_a_pessoa():
    assert ip_confiavel(de(PESSOA_A)) == (PESSOA_A, 1)


def test_usa_o_ultimo_item_e_nunca_o_primeiro():
    assert ip_confiavel(de("203.0.113.7", PESSOA_A)) == (PESSOA_A, 2)
    assert ip_confiavel(de(PESSOA_B, PESSOA_A)) == (PESSOA_A, 2)


def test_ip_inventado_nao_engana():
    limitador, _ = criar()
    falsos = ["203.0.113.7", PESSOA_B, "9.9.9.9", "4.4.4.4", "abc", "1.0.0.1"]
    decisoes = [limitador.verificar("?", de(falso, PESSOA_A)) for falso in falsos]
    # Sempre o mesmo identificador, e a pessoa é bloqueada ao passar de 5 perguntas.
    assert len({d.pessoa for d in decisoes}) == 1
    assert [d.permitido for d in decisoes] == [True] * 5 + [False]
    assert decisoes[-1].motivo == "pessoa_minuto"


def test_linha_inventada_antes_da_linha_do_proxy_nao_engana():
    # A pessoa manda o próprio X-Forwarded-For, e o proxy acrescenta outra linha.
    cabecalhos = CabecalhosRepetidos("1.1.1.1", PESSOA_A)
    assert ip_confiavel(cabecalhos) == (PESSOA_A, 2)


@pytest.mark.parametrize(
    "cabecalhos",
    [
        None,
        {},
        {"X-Forwarded-For": ""},
        {"X-Forwarded-For": "   "},
        de("abc"),
        de(PESSOA_A, "abc"),
        de("10.0.0.1"),
        de("192.168.0.5"),
        de("127.0.0.1"),
        de("::1"),
        de("100.64.0.1"),
        de("203.0.113.7"),  # faixa de documentação: não existe na internet real
        de(PESSOA_A, "10.0.0.1"),
    ],
    ids=lambda c: repr(c),
)
def test_sem_ip_confiavel_a_pessoa_fica_nao_identificada(cabecalhos):
    limitador, _ = criar()
    decisao = limitador.verificar("?", cabecalhos)
    assert decisao.permitido
    assert decisao.pessoa is None


def test_nao_identificada_fica_so_com_o_limite_global():
    limitador, _ = criar(perguntas_por_minuto_total=8, perguntas_por_minuto_por_pessoa=2)
    assert all(d.permitido for d in perguntar(limitador, 8, de("10.0.0.1")))
    assert limitador.verificar("?", de("10.0.0.1")).motivo == "global_minuto"


def test_ipv6_publico_e_aceito():
    assert ip_confiavel(de(IPV6_PUBLICO)) == (IPV6_PUBLICO, 1)


def test_nome_do_cabecalho_nao_depende_de_maiusculas():
    assert ip_confiavel({"x-forwarded-for": PESSOA_A}) == (PESSOA_A, 1)


# =============================================================
# Limites por pessoa
# =============================================================

def test_limite_por_minuto_da_pessoa_e_liberado_depois_de_um_minuto():
    limitador, relogio = criar()
    decisoes = perguntar(limitador, 6, de(PESSOA_A))
    assert [d.permitido for d in decisoes] == [True] * 5 + [False]
    assert decisoes[-1].mensagem == MENSAGENS["pessoa_minuto"]

    relogio.adiantar(30)
    assert not limitador.verificar("?", de(PESSOA_A)).permitido
    relogio.adiantar(31)
    assert limitador.verificar("?", de(PESSOA_A)).permitido


def test_limite_diario_bloqueia_so_aquela_pessoa():
    limitador, relogio = criar(perguntas_por_dia_por_pessoa=3)
    for _ in range(3):
        assert limitador.verificar("?", de(PESSOA_A)).permitido
        relogio.adiantar(61)
    bloqueada = limitador.verificar("?", de(PESSOA_A))
    assert (bloqueada.motivo, bloqueada.mensagem) == ("pessoa_dia", MENSAGENS["pessoa_dia"])
    assert limitador.verificar("?", de(PESSOA_B)).permitido


def test_uma_pessoa_nao_afeta_outra():
    limitador, _ = criar()
    perguntar(limitador, 5, de(PESSOA_A))
    assert not limitador.verificar("?", de(PESSOA_A)).permitido
    assert all(d.permitido for d in perguntar(limitador, 5, de(PESSOA_B)))


def test_pergunta_bloqueada_nao_gasta_a_cota_global():
    limitador, _ = criar(perguntas_por_minuto_total=6, perguntas_por_minuto_por_pessoa=5)
    perguntar(limitador, 5, de(PESSOA_A))
    bloqueadas = perguntar(limitador, 10, de(PESSOA_A))
    assert all(d.motivo == "pessoa_minuto" for d in bloqueadas)
    assert limitador.verificar("?", de(PESSOA_B)).permitido  # a 6ª vaga global continua livre


# =============================================================
# Privacidade e segurança
# =============================================================

def test_logs_mostram_o_identificador_e_os_itens_mas_nunca_o_ip_nem_a_pergunta(caplog):
    caplog.set_level(logging.INFO, logger="assistente.limites")
    limitador, _ = criar(perguntas_por_minuto_por_pessoa=1)
    liberada = limitador.verificar("pergunta-secreta-123", de("203.0.113.7", PESSOA_A))
    limitador.verificar("pergunta-secreta-123", de(PESSOA_A))
    texto = caplog.text
    assert f"pessoa={liberada.pessoa}" in texto
    assert "itens_x_forwarded_for=2" in texto
    assert "Limite atingido (pessoa_minuto)" in texto
    assert "nenhuma IA chamada" in texto
    assert PESSOA_A not in texto
    assert "203.0.113.7" not in texto
    assert "pergunta-secreta-123" not in texto


def test_identificador_e_anonimo_e_muda_quando_o_app_reinicia():
    primeiro, _ = criar()
    segundo, _ = criar()  # simula o app reiniciando: novo "tempero"
    id_1 = primeiro.verificar("?", de(PESSOA_A)).pessoa
    assert id_1 == primeiro.verificar("?", de(PESSOA_A)).pessoa
    assert id_1 != segundo.verificar("?", de(PESSOA_A)).pessoa
    assert PESSOA_A not in id_1 and len(id_1) == 12


def test_identificacao_desligada_nao_gera_identificador():
    limitador, _ = criar(identificar_por_ip=False)
    decisao = limitador.verificar("?", de(PESSOA_A))
    assert decisao.pessoa is None
    assert decisao.itens_x_forwarded_for == 1


def test_config_real_comeca_com_a_identificacao_desligada():
    from assistente.config import carregar_configuracao

    limitador = Limitador(carregar_configuracao().limites)
    assert limitador.verificar("?", de(PESSOA_A)).pessoa is None


def test_pedidos_ao_mesmo_tempo_nao_passam_do_limite():
    # Muitas pessoas perguntando juntas: o limite global precisa ser exato.
    limitador, _ = criar(perguntas_por_minuto_total=20, perguntas_por_minuto_por_pessoa=20)
    resultados = []
    trava = threading.Lock()

    def perguntar_em_paralelo(numero):
        decisao = limitador.verificar("?", de(f"8.8.{numero // 250}.{numero % 250 + 1}"))
        with trava:
            resultados.append(decisao.permitido)

    linhas = [threading.Thread(target=perguntar_em_paralelo, args=(n,)) for n in range(200)]
    for linha in linhas:
        linha.start()
    for linha in linhas:
        linha.join()
    assert resultados.count(True) == 20
