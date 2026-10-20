"""Tela do chat no navegador, com Gradio (SPEC, seções 4.4 e 5).

Tudo que aparece na tela vem do config.yml: nome, descrição, logo, cores,
tema, mensagem de boas-vindas e perguntas de exemplo.

Sessões: cada visitante tem a própria conversa. O Gradio guarda o histórico
na sessão do navegador de cada pessoa e o envia junto com cada pergunta; o
Assistente (chat.py) não guarda conversa nenhuma.

Limites: continuam no servidor. A função de resposta passa os cabeçalhos do
pedido para o chat.py, que confere os limites antes de chamar qualquer IA.
Isso vale também para quem usar a API do Gradio sem a tela.
"""

import base64
import html
import logging
import mimetypes
import os
import threading
from pathlib import Path

import gradio as gr

from assistente import cores
from assistente.chat import MENSAGEM_AGUARDE, Assistente
from assistente.config import RAIZ_DO_PROJETO, Configuracao
from assistente.tutor import MODO_PADRAO, MODOS, NIVEIS, NIVEL_PADRAO, opcoes_para_tela

logger = logging.getLogger("assistente.interface")

MENSAGEM_ERRO_INESPERADO = "Desculpe, algo deu errado do nosso lado. Tente novamente em alguns minutos."

# Quantas perguntas são atendidas ao mesmo tempo, e quantas podem esperar na fila.
PERGUNTAS_AO_MESMO_TEMPO = 4
TAMANHO_DA_FILA = 30


# ---------- Aparência ----------


def misturar(cor: str, fundo: str, proporcao: float) -> str:
    """Mistura a cor com o fundo. proporcao=0.15 → 15% da cor e 85% do fundo."""
    cor, fundo = cores.validar_formato(cor), cores.validar_formato(fundo)
    canais = []
    for i in (1, 3, 5):
        a, b = int(cor[i : i + 2], 16), int(fundo[i : i + 2], 16)
        canais.append(round(a * proporcao + b * (1 - proporcao)))
    return "#{:02X}{:02X}{:02X}".format(*canais)


def criar_tema(config: Configuracao) -> gr.themes.Base:
    """Aplica as cores do config.yml por cima do tema padrão do Gradio."""
    aparencia = config.aparencia
    primaria = aparencia.cor_primaria
    secundaria = aparencia.cor_secundaria
    texto_do_botao = cores.cor_do_texto_do_botao(primaria)
    fundo = cores.FUNDOS[aparencia.tema]

    valores = {
        # Botões e destaques: cor primária, com texto branco ou preto (o mais legível).
        "button_primary_background_fill": primaria,
        "button_primary_background_fill_hover": primaria,
        "button_primary_border_color": primaria,
        "button_primary_text_color": texto_do_botao,
        "color_accent": primaria,
        "border_color_accent": primaria,
        # Balão das mensagens da pessoa: um tom clarinho da cor primária.
        "color_accent_soft": misturar(primaria, fundo, 0.12),
        "border_color_accent_subdued": misturar(primaria, fundo, 0.40),
        "input_border_color_focus": primaria,
        # Links e textos destacados: cor secundária.
        "link_text_color": secundaria,
        "link_text_color_hover": secundaria,
        "link_text_color_visited": secundaria,
        "link_text_color_active": secundaria,
        # Fundo da página do tema escolhido.
        "body_background_fill": fundo,
    }
    # As mesmas cores valem no modo escuro do Gradio, para a tela ser igual
    # em qualquer navegador (o contraste foi conferido contra o fundo escolhido).
    tema = gr.themes.Default()
    valores |= {f"{nome}_dark": valor for nome, valor in valores.items() if hasattr(tema, f"{nome}_dark")}
    return tema.set(**valores)


def js_do_tema(config: Configuracao) -> str:
    """Força o modo claro ou escuro escolhido no config.yml.

    Sem isso, o Gradio seguiria a preferência do navegador, e as cores
    poderiam aparecer sobre um fundo diferente do que foi validado.
    """
    escuro = "true" if config.aparencia.tema == "escuro" else "false"
    return f"() => {{ document.body.classList.toggle('dark', {escuro}); }}"


# Texto de apoio (descrição, aviso do rodapé): cinza com contraste de pelo
# menos 4,5 : 1 sobre o fundo de cada tema (conferido nos testes).
TEXTO_SECUNDARIO = {"claro": "#52525B", "escuro": "#A1A1AA"}
# Bordas discretas dos balões e da área do chat.
BORDA_NEUTRA = {"claro": "#E4E4E7", "escuro": "#27272A"}


def css_extra(config: Configuracao) -> str:
    """Estilo da tela. Só CSS: nada de bibliotecas extras (leve no Render grátis)."""
    tema = config.aparencia.tema
    fundo = cores.FUNDOS[tema]
    primaria = config.aparencia.cor_primaria
    secundaria = config.aparencia.cor_secundaria
    apoio = TEXTO_SECUNDARIO[tema]
    borda = BORDA_NEUTRA[tema]
    return f"""
    /* ---------- Página: coluna central, sem rolagem para os lados ---------- */
    .gradio-container {{ width: 100% !important; max-width: 920px !important; margin: 0 auto !important; }}
    .gradio-container, .gradio-container * {{ min-width: 0; }}

    /* ---------- Topo: logo, nome, descrição e "Nova conversa" ---------- */
    .topo {{ align-items: center !important; gap: 12px !important; flex-wrap: nowrap !important;
             padding: 4px 0 12px; border-bottom: 1px solid {borda}; }}
    .cabecalho {{ display: flex; align-items: center; gap: 14px; }}
    .cabecalho img {{ width: 48px; height: 48px; flex-shrink: 0; }}
    .cabecalho h1 {{ margin: 0; font-size: 1.375rem; line-height: 1.25; }}
    .cabecalho p {{ margin: 2px 0 0; color: {apoio}; font-size: 0.95rem; }}
    #nova-conversa {{ min-height: 44px; white-space: nowrap; }}

    /* ---------- Mensagens ---------- */
    #conversa .message {{ font-size: 1rem; line-height: 1.65; overflow-wrap: anywhere; }}
    #conversa .message.user {{ border: 1px solid {misturar(primaria, fundo, 0.40)} !important; }}
    #conversa .message.bot {{ border: 1px solid {borda} !important; }}
    /* Links nas mensagens usam a cor secundária. */
    .message a, .message a:visited {{ color: {secundaria} !important; }}
    /* Balão da IA com o mesmo fundo da página: o contraste dos links foi
       validado contra esse fundo (SPEC 4.4). */
    .message.bot {{ background: {fundo} !important; }}
    /* Código e tabelas largas rolam dentro do balão, nunca a página inteira. */
    #conversa pre {{ max-width: 100%; overflow-x: auto; border-radius: 8px; }}
    #conversa table {{ display: block; max-width: 100%; overflow-x: auto; }}
    #conversa :is(th, td) {{ overflow-wrap: normal; word-break: normal; }}
    #conversa .placeholder-content h3 {{ margin-bottom: 8px; }}
    /* Enquanto a IA responde: três pontinhos + "Pensando...", sem o contador
       técnico em inglês ("processing | 1.0s"). */
    #conversa .progress-text {{ display: none !important; }}
    #conversa .message.pending .message-content::after {{ content: "Pensando..."; margin-left: 10px; color: {apoio}; }}

    /* ---------- Acessibilidade ---------- */
    /* Foco bem visível para quem navega pelo teclado (cor primária: contraste
       de pelo menos 3 : 1 com o fundo, conferido na validação das cores). */
    .gradio-container :is(button, a, textarea, input, [tabindex]):focus-visible {{
        outline: 3px solid {primaria} !important; outline-offset: 2px !important; }}
    /* Botões de ícone (copiar, limpar...) com área de toque confortável. */
    #conversa button.icon-button {{ min-width: 32px; min-height: 32px; }}
    #conversa .example {{ min-height: 44px; }}
    @media (prefers-reduced-motion: reduce) {{
        .gradio-container * {{ animation: none !important; transition: none !important; }} }}

    /* ---------- Nível e modo (discretos, quebram linha no celular) ---------- */
    .controles-tutor {{ gap: 8px !important; flex-wrap: wrap !important; }}
    .controles-tutor > * {{ flex: 1 1 260px !important; }}
    .controles-tutor .wrap {{ gap: 6px !important; }}
    .controles-tutor label {{ min-height: 36px; }}

    /* ---------- Rodapé ---------- */
    .aviso {{ text-align: center; color: {apoio}; font-size: 0.85rem; margin: 0; }}

    /* ---------- Celular ---------- */
    @media (max-width: 640px) {{
        .gradio-container {{ padding: 0 8px !important; }}
        .cabecalho img {{ width: 40px; height: 40px; }}
        .cabecalho h1 {{ font-size: 1.15rem; }}
        .cabecalho p {{ display: none; }}
        #nova-conversa {{ padding: 0 12px; }}
    }}
    """


def logo_como_data_uri(caminho: Path) -> str:
    """Embute a logo na página, sem precisar liberar acesso a arquivos."""
    tipo = mimetypes.guess_type(caminho.name)[0] or "image/png"
    if caminho.suffix.lower() == ".svg":
        tipo = "image/svg+xml"
    conteudo = base64.b64encode(caminho.read_bytes()).decode("ascii")
    return f"data:{tipo};base64,{conteudo}"


def html_do_cabecalho(config: Configuracao, raiz: Path = RAIZ_DO_PROJETO) -> str:
    """Logo, nome e descrição. Os textos são "escapados" para não virarem código."""
    dados = config.assistente
    logo = ""
    if dados.logo:
        logo = f'<img src="{logo_como_data_uri(raiz / dados.logo)}" alt="Logo de {html.escape(dados.nome)}">'
    descricao = f"<p>{html.escape(dados.descricao)}</p>" if dados.descricao else ""
    return f'<div class="cabecalho">{logo}<div><h1>{html.escape(dados.nome)}</h1>{descricao}</div></div>'


# ---------- Resposta ----------


def criar_funcao_de_resposta(assistente: Assistente):
    """Função chamada pelo Gradio a cada pergunta.

    Uma sessão (aba do navegador ou cliente da API) só tem uma pergunta em
    andamento por vez. A tela já bloqueia a caixa de texto enquanto a IA
    responde; esta trava vale também para quem usa a API diretamente, e
    evita chamadas duplicadas à IA.
    """
    em_andamento: set[str] = set()
    trava = threading.Lock()

    # O Gradio coloca o "request" na posição dele e manda nível e modo depois.
    def responder(mensagem: str, historico: list, request: gr.Request = None, nivel=None, modo=None) -> str:
        # Os cabeçalhos do pedido vão para os limites (identificação pelo IP).
        cabecalhos = request.headers if request is not None else None
        sessao = getattr(request, "session_hash", None) if request is not None else None
        if sessao:
            with trava:
                if sessao in em_andamento:
                    logger.info("Pergunta repetida recusada: a anterior desta sessão ainda está em andamento.")
                    return MENSAGEM_AGUARDE
                em_andamento.add(sessao)
        try:
            return assistente.responder(mensagem, historico, cabecalhos, nivel=nivel, modo=modo).texto
        except Exception as erro:  # noqa: BLE001 - a pessoa nunca deve ver um erro técnico
            # Só o tipo do erro vai para o log: nada de pergunta, resposta ou chave.
            logger.error("Erro inesperado ao responder (%s).", type(erro).__name__)
            return MENSAGEM_ERRO_INESPERADO
        finally:
            if sessao:
                with trava:
                    em_andamento.discard(sessao)

    return responder


# ---------- Tela ----------

DICA_DA_CAIXA = "Escreva sua pergunta..."
AVISO_DO_RODAPE = "As respostas são geradas por IA e podem conter erros. Não compartilhe senhas nem dados pessoais."


def conversa_vazia():
    """'Nova conversa': limpa a tela e o histórico guardado na sessão."""
    return [], [], [], gr.update(value="", interactive=True)


def aguardando_resposta(conversa: list) -> bool:
    """True se a última mensagem é da pessoa, ou seja, a IA ainda está respondendo."""
    if not conversa:
        return False
    ultima = conversa[-1]
    papel = ultima.get("role") if isinstance(ultima, dict) else getattr(ultima, "role", None)
    return papel == "user"


def depois_de_mudar_a_conversa(conversa: list):
    """Liga/desliga o 'Nova conversa' e devolve a dica da caixa de texto.

    O Gradio apaga a dica (placeholder) da caixa ao enviar e não a devolve.
    """
    if aguardando_resposta(conversa):
        return gr.update(interactive=False), gr.update()
    return gr.update(interactive=True), gr.update(placeholder=DICA_DA_CAIXA)


def criar_interface(config: Configuracao, assistente: Assistente, raiz: Path = RAIZ_DO_PROJETO) -> gr.Blocks:
    """Monta a tela do chat. Para abrir: demo.launch(**opcoes_de_lancamento(config))."""
    dados = config.assistente
    with gr.Blocks(title=dados.nome, analytics_enabled=False) as demo:
        with gr.Row(elem_classes="topo"):
            gr.HTML(html_do_cabecalho(config, raiz))
            nova_conversa = gr.Button(
                "Nova conversa",
                variant="secondary",
                size="md",
                scale=0,
                min_width=140,
                elem_id="nova-conversa",
            )
        # Tutor adaptativo: nível e modo vão para as instruções da IA (tutor.py).
        with gr.Row(elem_classes="controles-tutor"):
            nivel = gr.Radio(
                opcoes_para_tela(NIVEIS),
                value=NIVEL_PADRAO,
                label="Seu nível",
                elem_id="nivel",
                min_width=0,
            )
            modo = gr.Radio(
                opcoes_para_tela(MODOS),
                value=MODO_PADRAO,
                label="Modo de estudo",
                elem_id="modo",
                min_width=0,
            )
        chat = gr.ChatInterface(
            fn=criar_funcao_de_resposta(assistente),
            chatbot=gr.Chatbot(
                label="Conversa com o " + dados.nome,
                placeholder=dados.mensagem_boas_vindas or None,
                show_label=False,
                # A conversa ocupa a altura da tela, em qualquer aparelho.
                height="calc(100dvh - 300px)",
                min_height=360,
                # Copiar cada mensagem ou a conversa toda. Sem "compartilhar",
                # que enviaria a conversa para fora do app.
                buttons=["copy", "copy_all"],
                avatar_images=(None, str(raiz / dados.logo)) if dados.logo else None,
                elem_id="conversa",
            ),
            textbox=gr.Textbox(
                label="Sua pergunta",  # lido por leitores de tela
                placeholder=DICA_DA_CAIXA,
                show_label=False,
                lines=1,
                max_lines=6,
                submit_btn="Enviar",
                # O limite real é conferido no servidor; isto só ajuda quem digita.
                max_length=config.limites.tamanho_maximo_pergunta,
                html_attributes=gr.InputHTMLAttributes(lang="pt-BR", enterkeyhint="send", autocomplete="off"),
            ),
            additional_inputs=[nivel, modo],
            # Com nível e modo, o Gradio pede cada exemplo como lista; só a
            # pergunta vai nela, e o nível e o modo continuam os da tela.
            examples=[[exemplo] for exemplo in dados.exemplos_de_perguntas] or None,
            cache_examples=False,  # não chamar a IA ao abrir o app (sem custo)
            save_history=False,  # histórico salvo fica para outra etapa
            concurrency_limit=PERGUNTAS_AO_MESMO_TEMPO,
            api_name="chat",  # a API passa pelos mesmos limites da tela
            analytics_enabled=False,
            show_progress="minimal",  # três pontinhos na conversa enquanto a IA responde
        )
        gr.HTML(f'<p class="aviso">{html.escape(AVISO_DO_RODAPE)}</p>')

        # "Nova conversa" zera a tela e o histórico da sessão (o histórico
        # que vai para a IA fica em chatbot_state). Não é uma API pública.
        nova_conversa.click(
            conversa_vazia,
            None,
            [chat.chatbot, chat.chatbot_state, chat.chatbot_value, chat.textbox],
            queue=False,
            api_visibility="private",
        )
        # Enquanto a IA responde, o botão fica desligado: uma resposta atrasada
        # não pode trazer de volta a conversa que acabou de ser apagada.
        # (A caixa de texto já fica bloqueada nesse tempo, o que impede
        # perguntas duplicadas.)
        chat.chatbot.change(
            depois_de_mudar_a_conversa,
            chat.chatbot,
            [nova_conversa, chat.textbox],
            queue=False,
            api_visibility="private",
        )
    demo.chat_interface = chat  # referência usada pelos testes
    demo.nova_conversa = nova_conversa
    demo.nivel, demo.modo = nivel, modo
    demo.queue(max_size=TAMANHO_DA_FILA)
    return demo


def opcoes_de_lancamento(config: Configuracao, raiz: Path = RAIZ_DO_PROJETO) -> dict:
    """Opções do demo.launch(): tema, cores e ícone da aba do navegador."""
    opcoes = {
        "theme": criar_tema(config),
        "css": css_extra(config),
        "js": js_do_tema(config),
        "ssr_mode": False,
        "show_error": False,  # a pessoa nunca vê detalhes técnicos de erros
        # Rodapé só com o crédito do Gradio: sem "Use via API" e sem
        # "Settings" (que permitiria trocar o tema e fugir das cores validadas).
        "footer_links": ["gradio"],
    }
    if config.assistente.logo:
        opcoes["favicon_path"] = str(raiz / config.assistente.logo)
    return opcoes


# ---------- Endereço do servidor (Render ou computador local) ----------

ENDERECO_LOCAL = ("127.0.0.1", 7860)


def endereco_do_servidor(ambiente=None) -> tuple[str, int]:
    """Onde o app escuta.

    - No Render: a variável PORT existe. O app escuta em 0.0.0.0 (todas as
      interfaces), na porta PORT, como o Render exige.
    - No seu computador (sem PORT): só em 127.0.0.1:7860, para o app não
      ficar visível para outras máquinas da sua rede.
    """
    ambiente = os.environ if ambiente is None else ambiente
    valor = (ambiente.get("PORT") or "").strip()
    if not valor:
        return ENDERECO_LOCAL
    if not valor.isdigit() or not 1 <= int(valor) <= 65535:
        raise ValueError(f"PORT inválida: {valor!r}. Use um número entre 1 e 65535.")
    # O Render exige escutar em todas as interfaces (0.0.0.0).
    return "0.0.0.0", int(valor)
