"""Validação REAL com o OpenRouter: uma pergunta curta, pelo mesmo caminho do app.

Como usar (na pasta do projeto, com OPENROUTER_API_KEY no .env):
    python scripts/conferir_modelos.py      # 1º: confere a lista no catálogo (sem custo)
    python scripts/testar_openrouter.py     # 2º: faz UMA pergunta de verdade

Custo: zero. Só modelos ":free" são usados e o pedido vai com preço máximo
zero (provider.max_price). Gasta 1 ou 2 dos pedidos gratuitos do dia
(o OpenRouter permite 50 por dia em contas sem créditos comprados).

Só o OpenRouter é usado, mesmo que existam outras chaves no .env.
Mostra o modelo que respondeu e o começo da resposta; nunca mostra a chave.

Resultado:
    - Código 0: um modelo de conversa respondeu com uma explicação.
    - Código 1: sem chave, sem resposta ou resposta inadequada.
"""

import logging
import os
import sys
from pathlib import Path

RAIZ_DO_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_DO_PROJETO))

from assistente.chat import Assistente
from assistente.config import ErroDeConfiguracao, carregar_configuracao
from assistente.modelos_gratuitos import parece_classificacao
from assistente.provedores import criar_provedores

PERGUNTA = "Em duas frases: o que é um pipeline de dados?"


def main(ambiente=None, raiz: Path = RAIZ_DO_PROJETO) -> int:
    if ambiente is None:
        from dotenv import load_dotenv

        load_dotenv(raiz / ".env")
        ambiente = os.environ
    chave = (ambiente.get("OPENROUTER_API_KEY") or "").strip()
    if not chave:
        print("[ERRO] Coloque a OPENROUTER_API_KEY no arquivo .env (nunca no chat nem no GitHub).")
        return 1
    try:
        config = carregar_configuracao(raiz / "config.yml")
    except ErroDeConfiguracao as erro:
        print(f"[ERRO] {erro}")
        return 1

    # Só o OpenRouter: as outras chaves (se existirem) são ignoradas aqui.
    provedores = [p for p in criar_provedores(config, {"OPENROUTER_API_KEY": chave}) if p.nome == "openrouter"]
    logging.basicConfig(level=logging.INFO, format="  log: %(message)s")
    resultado = Assistente(config, provedores=provedores).responder(PERGUNTA, [])

    print(f"\nPergunta: {PERGUNTA}")
    print(f"Resultado: {resultado.situacao}")
    print(f"Resposta (início): {resultado.texto[:300]!r}")
    if resultado.situacao != "sucesso":
        print("\n[ERRO] Nenhum modelo respondeu. Veja as linhas 'log:' acima (ia_modelos, ia_chamada).")
        return 1
    if parece_classificacao(resultado.texto):
        print("\n[ERRO] A resposta parece uma classificação, não uma explicação.")
        return 1
    print("\n[OK] Um modelo gratuito de conversa respondeu. O modelo usado aparece em 'modelo_servido'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
