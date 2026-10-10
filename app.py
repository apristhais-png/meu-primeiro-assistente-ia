"""Ponto de entrada do assistente. O Hugging Face roda este arquivo.

Para abrir no seu computador (na pasta do projeto, com o ambiente ativado):
    python app.py
Depois, abra no navegador o endereço mostrado (normalmente http://127.0.0.1:7860).

As chaves de API vêm do arquivo .env (no seu computador) ou dos Secrets do
Hugging Face. Sem nenhuma chave, o app abre, mas responde com a mensagem
amigável de erro.
"""

import logging
import os
import sys

# Não enviar estatísticas de uso do Gradio para fora.
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

from dotenv import load_dotenv

from assistente.chat import Assistente
from assistente.config import ErroDeConfiguracao, carregar_configuracao
from assistente.interface import criar_interface, opcoes_de_lancamento

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)

load_dotenv()  # lê o .env, se existir (no Hugging Face, as chaves vêm dos Secrets)

try:
    config = carregar_configuracao()
except ErroDeConfiguracao as erro:
    print(erro)
    sys.exit(1)

assistente = Assistente(config)
demo = criar_interface(config, assistente)

disponiveis = [p.nome for p in assistente.provedores if p.disponivel]
logging.getLogger("app").info(
    "Provedores com chave configurada: %s", ", ".join(disponiveis) or "nenhum (configure o .env ou os Secrets)"
)

if __name__ == "__main__":
    demo.launch(**opcoes_de_lancamento(config))
