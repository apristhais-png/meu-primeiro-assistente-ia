"""Confere se o config.yml está correto antes de publicar.

Como usar (na pasta do projeto):
    python scripts/validar_config.py                  # confere o config.yml
    python scripts/validar_config.py outro-arquivo.yml

Resultado:
    - Tudo certo: mostra [OK] com um resumo e termina com código 0.
    - Algum erro: mostra cada problema e como corrigir, e termina com
      código 1, o que deixa o GitHub Actions vermelho e bloqueia a publicação.
"""

import sys
from pathlib import Path

# Permite rodar o script direto, encontrando a pasta "assistente/".
RAIZ_DO_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_DO_PROJETO))

from assistente.config import (
    CAMINHO_PADRAO,
    ErroDeConfiguracao,
    carregar_configuracao,
)


def main(argumentos: list[str] | None = None) -> int:
    argumentos = sys.argv[1:] if argumentos is None else argumentos
    caminho = Path(argumentos[0]) if argumentos else CAMINHO_PADRAO

    try:
        config = carregar_configuracao(caminho)
    except ErroDeConfiguracao as erro:
        print(f"[ERRO] {erro}")
        print()
        print("Corrija os itens acima no config.yml e rode este comando de novo.")
        return 1

    ativos = ", ".join(f"{p.nome} ({p.modelo})" for p in config.provedores_ativos)
    identificacao = "ligada" if config.limites.identificar_por_ip else "desligada"
    print(f"[OK] {caminho.name} está correto.")
    print(f"  Assistente: {config.assistente.nome}")
    print(
        f"  Tema: {config.aparencia.tema} | cores {config.aparencia.cor_primaria} e {config.aparencia.cor_secundaria}"
    )
    print(f"  Provedores ativos, em ordem: {ativos}")
    print(
        f"  Limites globais: {config.limites.perguntas_por_minuto_total}/minuto e "
        f"{config.limites.perguntas_por_dia_total}/dia | identificação por IP {identificacao}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
