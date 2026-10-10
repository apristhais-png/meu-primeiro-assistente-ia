"""Procura chaves de API reais esquecidas nos arquivos do repositório.

Como usar (na pasta do projeto):
    python scripts/verificar_segredos.py

Resultado:
    - Nenhuma chave encontrada: mostra [OK] e termina com código 0.
    - Alguma chave encontrada: mostra o arquivo e a linha (com a chave
      escondida) e termina com código 1, o que deixa o GitHub Actions vermelho.

Regras (SPEC, teste T8):
    - Olha TODOS os arquivos de texto guardados no Git, inclusive .md e .yml.
    - Procura o formato COMPLETO de chaves reais, não só o começo (ex.: "sk-").
    - Ignora valores claramente falsos, como SUA_CHAVE_AQUI ou xxxx.
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ_DO_PROJETO = Path(__file__).resolve().parent.parent

# Impede que a chave seja só um pedaço de uma palavra maior.
_INICIO = r"(?<![A-Za-z0-9_-])"

# Formato completo das chaves de cada serviço.
PADROES = {
    "OpenRouter": re.compile(_INICIO + r"sk-or-v1-[0-9a-f]{64}"),
    "Anthropic": re.compile(_INICIO + r"sk-ant-[A-Za-z0-9_-]{80,}"),
    # "sk-" seguido de muitos caracteres, desde que não seja OpenRouter
    # nem Anthropic (essas já têm padrão próprio acima).
    "OpenAI": re.compile(_INICIO + r"sk-(?!or-|ant-)(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{40,}"),
    "Hugging Face": re.compile(_INICIO + r"hf_[A-Za-z0-9]{30,}"),
    "GitHub": re.compile(_INICIO + r"(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})"),
}

# Trechos que mostram que o valor é só um exemplo, e não uma chave real.
MARCAS_DE_EXEMPLO = ("SUA_CHAVE", "EXEMPLO", "EXAMPLE", "XXXX")

# Quantos caracteres da chave podem aparecer no alerta.
CARACTERES_VISIVEIS = 6


@dataclass
class Achado:
    """Uma possível chave encontrada em um arquivo."""

    arquivo: str
    linha: int
    servico: str
    chave_escondida: str


def esconder(chave: str) -> str:
    """Mostra só o começo da chave, para o alerta nunca expô-la inteira."""
    return f"{chave[:CARACTERES_VISIVEIS]}... ({len(chave)} caracteres)"


def parece_exemplo(valor: str) -> bool:
    """Diz se o valor é claramente falso, como SUA_CHAVE_AQUI ou xxxx."""
    valor_maiusculo = valor.upper()
    return any(marca in valor_maiusculo for marca in MARCAS_DE_EXEMPLO)


def procurar_no_texto(texto: str, arquivo: str = "") -> list[Achado]:
    """Procura chaves reais em um texto e devolve o que encontrou."""
    achados = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        for servico, padrao in PADROES.items():
            for encontrado in padrao.finditer(linha):
                chave = encontrado.group(0)
                if parece_exemplo(chave):
                    continue
                achados.append(Achado(arquivo, numero, servico, esconder(chave)))
    return achados


def ler_texto(caminho: Path) -> str | None:
    """Lê um arquivo de texto. Devolve None se for binário (ex.: imagem)."""
    conteudo = caminho.read_bytes()
    if b"\0" in conteudo:
        return None
    return conteudo.decode("utf-8", errors="ignore")


def listar_arquivos_do_git(raiz: Path) -> list[str]:
    """Lista os arquivos guardados no Git (inclui os adicionados com git add)."""
    resultado = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=raiz,
        capture_output=True,
        check=True,
    )
    nomes = resultado.stdout.decode("utf-8").split("\0")
    return [nome for nome in nomes if nome]


def verificar(raiz: Path) -> tuple[list[Achado], int]:
    """Verifica todos os arquivos do Git. Devolve (achados, arquivos lidos)."""
    achados = []
    lidos = 0
    for nome in listar_arquivos_do_git(raiz):
        caminho = raiz / nome
        if not caminho.is_file():
            continue
        texto = ler_texto(caminho)
        if texto is None:
            continue
        lidos += 1
        achados.extend(procurar_no_texto(texto, nome))
    return achados, lidos


def main(raiz: Path = RAIZ_DO_PROJETO) -> int:
    achados, lidos = verificar(raiz)

    if not achados:
        print(f"[OK] Nenhuma chave encontrada em {lidos} arquivos.")
        return 0

    print(f"[ERRO] {len(achados)} possível(is) chave(s) encontrada(s):")
    for achado in achados:
        print(
            f"  - {achado.arquivo}, linha {achado.linha}: "
            f"chave {achado.servico} {achado.chave_escondida}"
        )
    print()
    print("O que fazer:")
    print("  1. Se for uma chave REAL: revogue-a agora no site do serviço e crie outra.")
    print("  2. Tire a chave do arquivo (chaves ficam só no .env e nos Secrets).")
    print("  3. Se for só um exemplo: troque por um texto como SUA_CHAVE_AQUI.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
