"""Ponto de entrada do assistente.

O Render roda este arquivo com "python app.py" (veja o render.yaml).

Para abrir no seu computador (na pasta do projeto, com o ambiente ativado):
    python app.py
Depois, abra no navegador o endereço mostrado (normalmente http://127.0.0.1:7860).

Endereço:
    - No Render, a variável PORT existe: o app escuta em 0.0.0.0:PORT.
    - No seu computador, sem PORT: só em 127.0.0.1:7860.

As chaves de API vêm do arquivo .env (no seu computador) ou das variáveis de
ambiente do Render (aba Environment). Sem nenhuma chave, o app abre, mas
responde com a mensagem amigável de erro.
"""

import logging
import os
import sys

# Não enviar estatísticas de uso do Gradio para fora.
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

from dotenv import load_dotenv

from assistente.chat import Assistente
from assistente.config import ErroDeConfiguracao, carregar_configuracao
from assistente.interface import (
    criar_interface,
    endereco_do_servidor,
    opcoes_de_lancamento,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)

load_dotenv()  # lê o .env, se existir (no Render, as chaves vêm da aba Environment)

try:
    config = carregar_configuracao()
except ErroDeConfiguracao as erro:
    print(erro)
    sys.exit(1)

assistente = Assistente(config)
demo = criar_interface(config, assistente)

disponiveis = [p.nome for p in assistente.provedores if p.disponivel]
logging.getLogger("app").info(
    "Provedores com chave configurada: %s",
    ", ".join(disponiveis) or "nenhum (configure o .env ou a aba Environment do Render)",
)

if __name__ == "__main__":
    try:
        host, porta = endereco_do_servidor()
    except ValueError as erro:
        print(erro)
        sys.exit(1)
    logging.getLogger("app").info("Abrindo o app em %s:%d", host, porta)
    demo.launch(server_name=host, server_port=porta, **opcoes_de_lancamento(config))
