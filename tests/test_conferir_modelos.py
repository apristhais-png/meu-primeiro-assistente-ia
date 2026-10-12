"""Testes do scripts/conferir_modelos.py (passo P13).

Tudo simulado: nenhuma consulta real, nenhuma chave real, nenhum custo.
"""

import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx2
import openai
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import conferir_modelos as cm

from assistente.config import carregar_configuracao

CONFIG = carregar_configuracao()
CHAVE_FALSA = "chave-de-teste-nao-real-555"
REQUISICAO = httpx2.Request("GET", "https://exemplo.invalid")


@pytest.fixture(autouse=True)
def bloquear_rede(monkeypatch):
    def proibido(*args, **kwargs):
        raise RuntimeError("Acesso à rede bloqueado nos testes")

    monkeypatch.setattr(socket.socket, "connect", proibido)
    monkeypatch.setattr(socket, "create_connection", proibido)


def lista_openrouter(*modelos):
    return lambda: list(modelos)


def modelo_or(id_, prompt="0", completion="0"):
    return {"id": id_, "pricing": {"prompt": prompt, "completion": completion}}


def nao_encontrado(sdk):
    return sdk.NotFoundError("não existe", response=httpx2.Response(404, request=REQUISICAO), body={})


# ---------- OpenRouter (lista pública) ----------

def test_openrouter_modelo_gratuito_confirmado():
    r = cm.conferir_openrouter("m:free", lista_openrouter(modelo_or("m:free")))
    assert (r.situacao, r.detalhe) == ("confirmado", "gratuito, conversa em texto")


def test_openrouter_avisa_quando_o_modelo_e_pago():
    r = cm.conferir_openrouter("m", lista_openrouter(modelo_or("m", "0.000001", "0.000002")))
    assert (r.situacao, r.detalhe) == ("inadequado", "ATENÇÃO: é pago")  # pago agora é erro


def test_openrouter_modelo_inexistente():
    assert cm.conferir_openrouter("sumiu", lista_openrouter(modelo_or("outro"))).situacao == "nao_encontrado"


def test_openrouter_sem_acesso_fica_pendente():
    def sem_rede():
        raise OSError("sem rede")

    r = cm.conferir_openrouter("m", sem_rede)
    assert r.situacao == "pendente" and "OSError" in r.detalhe


# ---------- Anthropic e OpenAI (precisam de chave) ----------

@pytest.mark.parametrize("provedor", ["anthropic", "openai"])
def test_sem_chave_fica_pendente_e_nao_consulta(provedor):
    chamadas = []
    r = cm.conferir_com_chave(provedor, "m", None, lambda *a: chamadas.append(a))
    assert r.situacao == "pendente" and "sem" in r.detalhe
    assert chamadas == []


@pytest.mark.parametrize(("existe", "situacao"), [(True, "confirmado"), (False, "nao_encontrado")])
def test_com_chave_confirma_ou_recusa(existe, situacao):
    assert cm.conferir_com_chave("anthropic", "m", CHAVE_FALSA, lambda m, c: existe).situacao == situacao


def test_erro_na_consulta_fica_pendente_sem_mostrar_a_chave():
    def falha(modelo, chave):
        raise RuntimeError(f"401 chave inválida {chave}")

    r = cm.conferir_com_chave("openai", "m", CHAVE_FALSA, falha)
    assert r.situacao == "pendente"
    assert CHAVE_FALSA not in r.detalhe


# ---------- As consultas reais só LEEM (custo zero) ----------

class ClienteFalso:
    def __init__(self, erro=None):
        self.erro = erro
        self.consultados = []
        self.models = SimpleNamespace(retrieve=self._retrieve)
        # Se o script tentasse gerar texto, estes atributos acusariam o erro.
        self.messages = SimpleNamespace(create=self._proibido)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._proibido))

    def _retrieve(self, modelo):
        self.consultados.append(modelo)
        if self.erro:
            raise self.erro

    def _proibido(self, **_):
        raise AssertionError("o script não pode gerar texto (teria custo)")


@pytest.mark.parametrize(("sdk", "funcao"), [(anthropic, cm.existe_na_anthropic), (openai, cm.existe_na_openai)])
def test_consulta_real_so_usa_models_retrieve(monkeypatch, sdk, funcao):
    cliente = ClienteFalso()
    classe = "Anthropic" if sdk is anthropic else "OpenAI"
    monkeypatch.setattr(sdk, classe, lambda **kwargs: cliente)
    assert funcao("modelo-x", CHAVE_FALSA) is True
    assert cliente.consultados == ["modelo-x"]


@pytest.mark.parametrize(("sdk", "funcao"), [(anthropic, cm.existe_na_anthropic), (openai, cm.existe_na_openai)])
def test_modelo_inexistente_vira_false(monkeypatch, sdk, funcao):
    cliente = ClienteFalso(erro=nao_encontrado(sdk))
    classe = "Anthropic" if sdk is anthropic else "OpenAI"
    monkeypatch.setattr(sdk, classe, lambda **kwargs: cliente)
    assert funcao("sumiu", CHAVE_FALSA) is False


# ---------- Programa completo ----------

MODELOS_DO_OPENROUTER = [CONFIG.provedores[0].modelo, *CONFIG.provedores[0].modelos_reserva]


def consultas(openrouter=None, anthropic_existe=True, openai_existe=True):
    return {
        "openrouter": openrouter or lista_openrouter(*(modelo_or(m) for m in MODELOS_DO_OPENROUTER)),
        "anthropic": lambda m, c: anthropic_existe,
        "openai": lambda m, c: openai_existe,
    }


def test_tudo_confirmado(capsys):
    ambiente = {"ANTHROPIC_API_KEY": CHAVE_FALSA, "OPENAI_API_KEY": CHAVE_FALSA}
    assert cm.main(ambiente=ambiente, consultas=consultas()) == 0
    saida = capsys.readouterr().out
    assert saida.count("[OK]") == len(MODELOS_DO_OPENROUTER) + 2  # principal e reservas do OpenRouter
    assert CHAVE_FALSA not in saida


def test_modelo_inexistente_termina_com_erro(capsys):
    ambiente = {"ANTHROPIC_API_KEY": CHAVE_FALSA, "OPENAI_API_KEY": CHAVE_FALSA}
    assert cm.main(ambiente=ambiente, consultas=consultas(openai_existe=False)) == 1
    assert "Corrija o config.yml" in capsys.readouterr().out


def test_sem_chaves_fica_pendente_mas_nao_falha(capsys):
    assert cm.main(ambiente={}, consultas=consultas()) == 0
    saida = capsys.readouterr().out
    assert saida.count("[PENDENTE]") == 2
    assert "ficaram pendentes" in saida


def test_reserva_do_openrouter_que_virou_paga_ou_classificador_e_erro(capsys):
    itens = [modelo_or(m) for m in MODELOS_DO_OPENROUTER]
    itens[1] = modelo_or(MODELOS_DO_OPENROUTER[1], completion="0.000001")
    itens[2] = {**modelo_or(MODELOS_DO_OPENROUTER[2]), "name": "Exemplo Content Safety (free)"}
    assert cm.main(ambiente={}, consultas=consultas(openrouter=lista_openrouter(*itens))) == 1
    saida = capsys.readouterr().out
    assert "ATENÇÃO: é pago" in saida and "não conversa" in saida


def test_lista_do_openrouter_e_baixada_uma_vez_so():
    chamadas = []

    def baixar():
        chamadas.append(1)
        return [modelo_or(m) for m in MODELOS_DO_OPENROUTER]

    cm.conferir(CONFIG, {}, consultas(openrouter=baixar))
    assert len(chamadas) == 1
