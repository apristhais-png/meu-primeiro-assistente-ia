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
from pathlib import Path

import gradio as gr

from assistente import cores
from assistente.chat import Assistente
from assistente.config import RAIZ_DO_PROJETO, Configuracao

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
    valores |= {
        f"{nome}_dark": valor for nome, valor in valores.items() if hasattr(tema, f"{nome}_dark")
    }
    return tema.set(**valores)


def js_do_tema(config: Configuracao) -> str:
    """Força o modo claro ou escuro escolhido no config.yml.

    Sem isso, o Gradio seguiria a preferência do navegador, e as cores
    poderiam aparecer sobre um fundo diferente do que foi validado.
    """
    escuro = "true" if config.aparencia.tema == "escuro" else "false"
    return f"() => {{ document.body.classList.toggle('dark', {escuro}); }}"


def css_extra(config: Configuracao) -> str:
    fundo = cores.FUNDOS[config.aparencia.tema]
    secundaria = config.aparencia.cor_secundaria
    return f"""
    .cabecalho {{ display: flex; align-items: center; gap: 16px; padding: 8px 0; }}
    .cabecalho img {{ width: 64px; height: 64px; flex-shrink: 0; }}
    .cabecalho h1 {{ margin: 0; font-size: 1.6rem; }}
    .cabecalho p {{ margin: 4px 0 0; opacity: 0.85; }}
    /* Links nas mensagens usam a cor secundária. */
    .message a, .message a:visited {{ color: {secundaria} !important; }}
    /* Balão da IA com o mesmo fundo da página: o contraste dos links foi
       validado contra esse fundo (SPEC 4.4). */
    .message.bot {{ background: {fundo} !important; }}
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
    """Função chamada pelo Gradio a cada pergunta."""

    def responder(mensagem: str, historico: list, request: gr.Request = None) -> str:
        # Os cabeçalhos do pedido vão para os limites (identificação pelo IP).
        cabecalhos = request.headers if request is not None else None
        try:
            return assistente.responder(mensagem, historico, cabecalhos).texto
        except Exception as erro:  # noqa: BLE001 - a pessoa nunca deve ver um erro técnico
            # Só o tipo do erro vai para o log: nada de pergunta, resposta ou chave.
            logger.error("Erro inesperado ao responder (%s).", type(erro).__name__)
            return MENSAGEM_ERRO_INESPERADO

    return responder


# ---------- Tela ----------

def criar_interface(
    config: Configuracao, assistente: Assistente, raiz: Path = RAIZ_DO_PROJETO
) -> gr.Blocks:
    """Monta a tela do chat. Para abrir: demo.launch(**opcoes_de_lancamento(config))."""
    dados = config.assistente
    with gr.Blocks(title=dados.nome, analytics_enabled=False) as demo:
        gr.HTML(html_do_cabecalho(config, raiz))
        chat = gr.ChatInterface(
            fn=criar_funcao_de_resposta(assistente),
            chatbot=gr.Chatbot(
                placeholder=dados.mensagem_boas_vindas or None,
                show_label=False,
                height=520,
            ),
            textbox=gr.Textbox(
                placeholder="Digite sua pergunta...",
                show_label=False,
                # O limite real é conferido no servidor; isto só ajuda quem digita.
                max_length=config.limites.tamanho_maximo_pergunta,
            ),
            examples=dados.exemplos_de_perguntas or None,
            cache_examples=False,  # não chamar a IA ao abrir o app (sem custo)
            save_history=False,  # histórico salvo fica para outra etapa
            concurrency_limit=PERGUNTAS_AO_MESMO_TEMPO,
            api_name="chat",  # a API passa pelos mesmos limites da tela
            analytics_enabled=False,
        )
    demo.chat_interface = chat  # referência usada pelos testes
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
    }
    if config.assistente.logo:
        opcoes["favicon_path"] = str(raiz / config.assistente.logo)
    return opcoes
