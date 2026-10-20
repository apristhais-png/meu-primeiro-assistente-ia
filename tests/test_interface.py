"""Testes da tela do chat (SPEC, teste T6).

Parte dos testes abre o app de verdade no próprio computador (127.0.0.1) e
conversa com ele pela biblioteca gradio_client, como se fossem visitantes.
As IAs são falsas e qualquer conexão para fora do computador é bloqueada:
nenhuma API real é chamada e nada gera custo.
"""

import base64
import contextlib
import logging
import os
import socket
import subprocess
import sys
import threading
import urllib.request
from types import SimpleNamespace

import gradio as gr
import pytest
from gradio_client import Client

from assistente import cores
from assistente.chat import Assistente
from assistente.config import RAIZ_DO_PROJETO, carregar_configuracao
from assistente.interface import (
    AVISO_DO_RODAPE,
    DICA_DA_CAIXA,
    MENSAGEM_ERRO_INESPERADO,
    TEXTO_SECUNDARIO,
    aguardando_resposta,
    conversa_vazia,
    criar_funcao_de_resposta,
    criar_interface,
    criar_tema,
    css_extra,
    depois_de_mudar_a_conversa,
    html_do_cabecalho,
    js_do_tema,
    logo_como_data_uri,
    misturar,
    opcoes_de_lancamento,
)
from assistente.limites import MENSAGENS, Limitador
from assistente.provedores import MENSAGEM_SEM_RESPOSTA

CONFIG = carregar_configuracao()
LOCAIS = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def so_rede_local(monkeypatch):
    """Permite conexões só dentro do computador (o app de teste); bloqueia o resto."""
    monkeypatch.setenv("GRADIO_ANALYTICS_ENABLED", "False")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    conectar_original = socket.socket.connect

    def conectar(sock, endereco):
        host = endereco[0] if isinstance(endereco, tuple) else endereco
        if host not in LOCAIS:
            raise RuntimeError(f"Conexão externa bloqueada nos testes: {host}")
        return conectar_original(sock, endereco)

    monkeypatch.setattr(socket.socket, "connect", conectar)


class IAEco:
    """IA falsa: devolve a conversa que recebeu, para os testes conferirem."""

    nome = "falsa"
    disponivel = True

    def __init__(self):
        self.chamadas = []
        self._trava = threading.Lock()

    def responder(self, mensagens, instrucoes):
        with self._trava:
            self.chamadas.append(mensagens)
        return " | ".join(f"{m['role']}:{m['content']}" for m in mensagens)


def config_com(**limites):
    return CONFIG.model_copy(update={"limites": CONFIG.limites.model_copy(update=limites)})


def config_com_tema(tema, primaria="#2563EB", secundaria="#047857"):
    aparencia = CONFIG.aparencia.model_copy(
        update={"tema": tema, "cor_primaria": primaria, "cor_secundaria": secundaria}
    )
    return CONFIG.model_copy(update={"aparencia": aparencia})


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def app_rodando(config=CONFIG, assistente=None):
    """Abre o app de verdade em 127.0.0.1 e fecha no final."""
    ia = IAEco()
    assistente = assistente or Assistente(config, provedores=[ia], limitador=Limitador(config.limites))
    demo = criar_interface(config, assistente)
    porta = porta_livre()
    demo.launch(
        prevent_thread_lock=True,
        server_name="127.0.0.1",
        server_port=porta,
        quiet=True,
        **opcoes_de_lancamento(config),
    )
    try:
        yield SimpleNamespace(endereco=f"http://127.0.0.1:{porta}/", ia=ia)
    finally:
        demo.close()


def visitante(endereco, ip=None):
    cabecalhos = {"X-Forwarded-For": ip} if ip else None
    return Client(endereco, verbose=False, headers=cabecalhos)


# =============================================================
# Aparência a partir do config.yml
# =============================================================


def test_tema_usa_as_cores_do_config():
    tema = criar_tema(CONFIG)
    primaria = CONFIG.aparencia.cor_primaria
    assert tema.button_primary_background_fill == primaria
    assert tema.button_primary_border_color == primaria
    assert tema.color_accent == primaria
    assert tema.input_border_color_focus == primaria
    assert tema.link_text_color == CONFIG.aparencia.cor_secundaria
    assert tema.body_background_fill == cores.FUNDOS["claro"]


@pytest.mark.parametrize(("primaria", "texto"), [("#2563EB", "#FFFFFF"), ("#D97706", "#000000")])
def test_texto_do_botao_e_escolhido_pelo_contraste(primaria, texto):
    # Critério CA20: laranja com texto preto, azul-escuro com texto branco.
    tema = criar_tema(config_com_tema("claro", primaria=primaria))
    assert tema.button_primary_text_color == texto
    assert tema.button_primary_text_color_dark == texto


def test_cores_valem_tambem_no_modo_escuro_do_gradio():
    tema = criar_tema(CONFIG)
    assert tema.button_primary_background_fill_dark == CONFIG.aparencia.cor_primaria
    assert tema.link_text_color_dark == CONFIG.aparencia.cor_secundaria
    assert tema.body_background_fill_dark == cores.FUNDOS["claro"]


def test_tema_escuro_usa_o_fundo_escuro():
    config = config_com_tema("escuro", primaria="#60A5FA", secundaria="#34D399")
    assert criar_tema(config).body_background_fill == cores.FUNDOS["escuro"]


@pytest.mark.parametrize(("tema", "valor"), [("claro", "false"), ("escuro", "true")])
def test_modo_claro_ou_escuro_e_forcado(tema, valor):
    config = config_com_tema(
        tema,
        primaria="#2563EB" if tema == "claro" else "#60A5FA",
        secundaria="#047857" if tema == "claro" else "#34D399",
    )
    assert js_do_tema(config) == f"() => {{ document.body.classList.toggle('dark', {valor}); }}"


def test_balao_da_pessoa_usa_um_tom_claro_da_cor_primaria():
    tema = criar_tema(CONFIG)
    assert tema.color_accent_soft == misturar(CONFIG.aparencia.cor_primaria, cores.FUNDOS["claro"], 0.12)
    assert tema.border_color_accent_subdued == misturar(CONFIG.aparencia.cor_primaria, cores.FUNDOS["claro"], 0.40)
    # O texto do Gradio (#27272A) continua bem legível sobre o balão.
    assert cores.contraste(tema.color_accent_soft, "#27272A") >= cores.MINIMO_TEXTO


def test_misturar_cores():
    assert misturar("#000000", "#FFFFFF", 0.5) == "#808080"
    assert misturar("#2563EB", "#FFFFFF", 1) == "#2563EB"
    assert misturar("#2563EB", "#FFFFFF", 0) == "#FFFFFF"


def test_links_das_mensagens_usam_a_cor_secundaria_sobre_o_fundo_validado():
    css = css_extra(CONFIG)
    assert f".message a, .message a:visited {{ color: {CONFIG.aparencia.cor_secundaria} !important; }}" in css
    assert f".message.bot {{ background: {cores.FUNDOS['claro']} !important; }}" in css


def test_cabecalho_tem_logo_nome_e_descricao():
    cabecalho = html_do_cabecalho(CONFIG)
    assert "<h1>Professor de Dados</h1>" in cabecalho
    assert CONFIG.assistente.descricao in cabecalho
    assert 'src="data:image/svg+xml;base64,' in cabecalho
    svg = base64.b64decode(cabecalho.split("base64,")[1].split('"')[0])
    assert svg == (RAIZ_DO_PROJETO / "assets/logo.svg").read_bytes()


def test_textos_do_config_nao_viram_codigo_na_pagina():
    dados = CONFIG.assistente.model_copy(update={"nome": "<script>alert(1)</script>", "descricao": "a & b"})
    cabecalho = html_do_cabecalho(CONFIG.model_copy(update={"assistente": dados}))
    assert "<script>" not in cabecalho
    assert "&lt;script&gt;" in cabecalho
    assert "a &amp; b" in cabecalho


def test_logo_png_tambem_funciona(tmp_path):
    imagem = tmp_path / "logo.png"
    imagem.write_bytes(b"\x89PNG\r\n")
    assert logo_como_data_uri(imagem).startswith("data:image/png;base64,")


def test_opcoes_de_lancamento():
    opcoes = opcoes_de_lancamento(CONFIG)
    assert opcoes["favicon_path"].endswith("assets/logo.svg")
    assert opcoes["show_error"] is False
    assert opcoes["ssr_mode"] is False
    assert "dark" in opcoes["js"]


# =============================================================
# Conteúdo da tela
# =============================================================


def componentes(demo, tipo):
    return [b for b in demo.blocks.values() if isinstance(b, tipo)]


def test_tela_usa_titulo_boas_vindas_exemplos_e_limite_do_config():
    ia = IAEco()
    demo = criar_interface(CONFIG, Assistente(CONFIG, provedores=[ia]))
    assert demo.title == CONFIG.assistente.nome
    [chatbot] = componentes(demo, gr.Chatbot)
    assert chatbot.placeholder == CONFIG.assistente.mensagem_boas_vindas
    assert [e["text"] for e in chatbot.examples] == CONFIG.assistente.exemplos_de_perguntas
    [caixa] = componentes(demo, gr.Textbox)
    assert caixa.max_length == CONFIG.limites.tamanho_maximo_pergunta
    # Montar a tela não chama a IA (exemplos não são pré-calculados: sem custo).
    assert ia.chamadas == []


def test_conversa_nao_e_salva_e_exemplos_nao_sao_pre_calculados():
    demo = criar_interface(CONFIG, Assistente(CONFIG, provedores=[IAEco()]))
    assert demo.chat_interface.save_history is False  # histórico salvo fica para outra etapa
    assert demo.chat_interface.cache_examples is False  # não chama a IA ao abrir (sem custo)


# =============================================================
# Experiência de uso (Módulo 2, Aula 1)
# =============================================================


@pytest.mark.parametrize("tema", ["claro", "escuro"])
def test_texto_de_apoio_e_legivel_nos_dois_temas(tema):
    assert cores.contraste(TEXTO_SECUNDARIO[tema], cores.FUNDOS[tema]) >= cores.MINIMO_TEXTO


def test_css_tem_foco_visivel_com_a_cor_primaria_e_nao_esconde_rolagem():
    css = css_extra(CONFIG)
    assert f"outline: 3px solid {CONFIG.aparencia.cor_primaria} !important" in css
    assert ":focus-visible" in css
    # Código e tabelas rolam dentro do balão; a página não esconde o excesso.
    assert "#conversa pre {" in css and "overflow-x: auto" in css
    assert "overflow-x: hidden" not in css
    assert "prefers-reduced-motion" in css
    assert "@media (max-width: 640px)" in css


def test_indicador_de_processamento_em_portugues():
    css = css_extra(CONFIG)
    assert "#conversa .progress-text { display: none !important; }" in css  # contador em inglês
    assert 'content: "Pensando..."' in css


def test_tela_tem_nova_conversa_rotulos_e_aviso():
    demo = criar_interface(CONFIG, Assistente(CONFIG, provedores=[IAEco()]))
    [chatbot] = componentes(demo, gr.Chatbot)
    [caixa] = componentes(demo, gr.Textbox)
    assert demo.nova_conversa.value == "Nova conversa"
    assert caixa.label == "Sua pergunta"  # lido por leitores de tela
    assert caixa.placeholder == DICA_DA_CAIXA
    assert caixa.submit_btn == "Enviar"
    # Sem o botão "compartilhar", que mandaria a conversa para fora do app.
    assert "share" not in chatbot.buttons and "copy" in chatbot.buttons
    htmls = " ".join(str(h.value) for h in componentes(demo, gr.HTML))
    assert AVISO_DO_RODAPE in htmls


def test_rodape_sem_use_via_api_e_sem_settings():
    assert opcoes_de_lancamento(CONFIG)["footer_links"] == ["gradio"]


def test_nova_conversa_zera_tela_historico_e_caixa():
    tela, historico, valor, caixa = conversa_vazia()
    assert tela == historico == valor == []
    assert caixa["value"] == "" and caixa["interactive"] is True


@pytest.mark.parametrize(
    ("conversa", "aguardando"),
    [
        ([], False),
        ([{"role": "user", "content": "Oi"}], True),
        ([{"role": "user", "content": "Oi"}, {"role": "assistant", "content": "Olá"}], False),
        ([SimpleNamespace(role="user", content="Oi")], True),
    ],
)
def test_aguardando_resposta(conversa, aguardando):
    assert aguardando_resposta(conversa) is aguardando


def test_nova_conversa_fica_desligada_enquanto_a_ia_responde():
    botao, caixa = depois_de_mudar_a_conversa([{"role": "user", "content": "Oi"}])
    assert botao["interactive"] is False
    assert "placeholder" not in caixa  # a caixa continua como o Gradio deixou (bloqueada)
    botao, caixa = depois_de_mudar_a_conversa(
        [{"role": "user", "content": "Oi"}, {"role": "assistant", "content": "Olá"}]
    )
    assert botao["interactive"] is True
    assert caixa["placeholder"] == DICA_DA_CAIXA  # o Gradio apaga a dica ao enviar


def test_so_o_chat_e_api_publica():
    # "Nova conversa" e os ajustes da tela não viram API para quem está de fora.
    with app_rodando() as app:
        rotas = visitante(app.endereco).view_api(return_format="dict", print_info=False)["named_endpoints"]
    assert list(rotas) == ["/chat"]


# =============================================================
# Função de resposta
# =============================================================


class AssistenteQueAnota:
    def __init__(self, texto="ok", erro=None):
        self.chamadas = []
        self.texto = texto
        self.erro = erro

    def responder(self, pergunta, historico, cabecalhos, nivel=None, modo=None):
        self.chamadas.append((pergunta, historico, cabecalhos))
        self.escolhas = (nivel, modo)
        if self.erro:
            raise self.erro
        return SimpleNamespace(texto=self.texto)


def test_funcao_de_resposta_passa_os_cabecalhos_para_os_limites():
    anotador = AssistenteQueAnota("resposta")
    responder = criar_funcao_de_resposta(anotador)
    pedido = SimpleNamespace(headers={"X-Forwarded-For": "8.8.8.8"})
    assert responder("Oi", [], pedido) == "resposta"
    assert anotador.chamadas == [("Oi", [], {"X-Forwarded-For": "8.8.8.8"})]


def test_funcao_de_resposta_funciona_sem_pedido():
    anotador = AssistenteQueAnota()
    assert criar_funcao_de_resposta(anotador)("Oi", []) == "ok"
    assert anotador.chamadas[0][2] is None


def test_erro_inesperado_vira_mensagem_amigavel_sem_vazar_detalhes(caplog):
    caplog.set_level(logging.INFO)
    anotador = AssistenteQueAnota(erro=RuntimeError("detalhe-secreto-999"))
    assert criar_funcao_de_resposta(anotador)("pergunta-secreta-123", []) == MENSAGEM_ERRO_INESPERADO
    assert "RuntimeError" in caplog.text
    assert "detalhe-secreto-999" not in caplog.text
    assert "pergunta-secreta-123" not in caplog.text


# =============================================================
# App de verdade, aberto no computador (127.0.0.1)
# =============================================================


def test_pagina_abre_no_navegador_com_o_nome_e_as_cores():
    with app_rodando() as app:
        pagina = urllib.request.urlopen(app.endereco, timeout=30).read().decode()
        tema_css = urllib.request.urlopen(app.endereco + "theme.css", timeout=30).read().decode()
    assert "<title>Professor de Dados</title>" in pagina or "Professor de Dados" in pagina
    assert CONFIG.aparencia.cor_primaria.lower() in tema_css.lower()
    assert CONFIG.aparencia.cor_secundaria.lower() in tema_css.lower()


def test_cada_visitante_tem_a_propria_conversa():
    with app_rodando() as app:
        ana = visitante(app.endereco)
        bia = visitante(app.endereco)
        ana.predict("Ana pergunta 1", api_name="/chat")
        bia.predict("Bia pergunta 1", api_name="/chat")
        segunda_da_ana = ana.predict("Ana pergunta 2", api_name="/chat")
        segunda_da_bia = bia.predict("Bia pergunta 2", api_name="/chat")

    # A 2ª pergunta de cada uma chega com o histórico DELA, e só dela.
    assert "Ana pergunta 1" in segunda_da_ana and "Bia" not in segunda_da_ana
    assert "Bia pergunta 1" in segunda_da_bia and "Ana" not in segunda_da_bia


def test_limite_global_e_aplicado_no_servidor():
    config = config_com(perguntas_por_minuto_total=2, perguntas_por_minuto_por_pessoa=2)
    with app_rodando(config) as app:
        respostas = [visitante(app.endereco).predict(f"pergunta {n}", api_name="/chat") for n in range(3)]
        chamadas = len(app.ia.chamadas)
    assert respostas[2] == MENSAGENS["global_minuto"]
    assert chamadas == 2  # a pergunta bloqueada não chegou à IA


def test_limite_por_pessoa_usa_o_ip_que_chega_ao_servidor():
    config = config_com(identificar_por_ip=True, perguntas_por_minuto_por_pessoa=1)
    with app_rodando(config) as app:
        ana = visitante(app.endereco, ip="8.8.8.8")
        assert ana.predict("1", api_name="/chat") != MENSAGENS["pessoa_minuto"]
        assert ana.predict("2", api_name="/chat") == MENSAGENS["pessoa_minuto"]
        # Outra pessoa (outro IP) continua sendo atendida.
        assert visitante(app.endereco, ip="1.1.1.1").predict("1", api_name="/chat") != MENSAGENS["pessoa_minuto"]


def test_pergunta_longa_recebe_aviso_amigavel_pela_tela():
    config = config_com(tamanho_maximo_pergunta=100)
    with app_rodando(config) as app:
        resposta = visitante(app.endereco).predict("a" * 101, api_name="/chat")
        chamadas = len(app.ia.chamadas)
    assert resposta == "Sua pergunta ficou muito longa. Tente resumir em até 100 caracteres."
    assert chamadas == 0


def test_sem_chaves_a_tela_mostra_a_mensagem_amigavel():
    assistente = Assistente(CONFIG, ambiente={})  # provedores reais, sem nenhuma chave
    with app_rodando(assistente=assistente) as app:
        assert visitante(app.endereco).predict("Oi", api_name="/chat") == MENSAGEM_SEM_RESPOSTA


def test_erro_inesperado_aparece_como_mensagem_amigavel_na_tela():
    with app_rodando(assistente=AssistenteQueAnota(erro=RuntimeError("detalhe-secreto"))) as app:
        assert visitante(app.endereco).predict("Oi", api_name="/chat") == MENSAGEM_ERRO_INESPERADO


# =============================================================
# app.py
# =============================================================


def test_app_py_carrega_sem_chaves_e_sem_abrir_o_servidor():
    # Importar o app.py monta a tela, mas só "python app.py" abre o servidor.
    ambiente = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
    ambiente["GRADIO_ANALYTICS_ENABLED"] = "False"
    resultado = subprocess.run(
        [sys.executable, "-c", "import app; print(type(app.demo).__name__)"],
        cwd=RAIZ_DO_PROJETO,
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=120,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "Blocks" in resultado.stdout
    # A linha de log diz quais provedores têm chave (sem nunca mostrar a chave).
    assert "Provedores com chave configurada:" in resultado.stderr
