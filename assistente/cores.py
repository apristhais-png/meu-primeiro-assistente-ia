"""Cálculo de contraste e legibilidade das cores (SPEC, seção 4.4).

Usamos a regra internacional de acessibilidade WCAG 2.1, nível AA:
    - textos precisam de contraste de pelo menos 4.5 : 1;
    - bordas e contornos precisam de pelo menos 3 : 1.

O contraste vai de 1 : 1 (cores iguais, impossível ler) até
21 : 1 (preto no branco, o máximo).
"""

import math
import re

# Contraste mínimo exigido (WCAG 2.1, nível AA).
MINIMO_TEXTO = 4.5
MINIMO_BORDA = 3.0

# Cor do fundo da página em cada tema.
FUNDOS = {
    "claro": "#FFFFFF",
    "escuro": "#0B0F19",
}

BRANCO = "#FFFFFF"
PRETO = "#000000"

_FORMATO_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def validar_formato(cor: str) -> str:
    """Confere se a cor está no formato #RRGGBB e devolve em maiúsculas."""
    if not isinstance(cor, str) or not _FORMATO_HEX.match(cor):
        raise ValueError(f"cor inválida: {cor!r}. Use o formato #RRGGBB, por exemplo #2563EB.")
    return cor.upper()


def _para_rgb(cor: str) -> tuple[int, int, int]:
    cor = validar_formato(cor)
    return int(cor[1:3], 16), int(cor[3:5], 16), int(cor[5:7], 16)


def _para_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def luminancia(cor: str) -> float:
    """Quanto a cor é "clara" para o olho humano: 0 (preto) até 1 (branco)."""

    def canal(valor: int) -> float:
        c = valor / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _para_rgb(cor)
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def contraste(cor_a: str, cor_b: str) -> float:
    """Razão de contraste entre duas cores, de 1 até 21."""
    clara, escura = sorted((luminancia(cor_a), luminancia(cor_b)), reverse=True)
    return (clara + 0.05) / (escura + 0.05)


def cor_do_texto_do_botao(cor_fundo: str) -> str:
    """Escolhe branco ou preto para o texto do botão: o que ficar mais legível."""
    if contraste(cor_fundo, BRANCO) >= contraste(cor_fundo, PRETO):
        return BRANCO
    return PRETO


def _formatar(razao: float) -> str:
    # Arredonda para baixo, para nunca mostrar "4.50" quando o valor é 4.497.
    return f"{math.floor(razao * 100) / 100:.2f}".replace(".", ",")


def sugerir_cor(cor: str, fundo: str, minimo: float) -> str:
    """Escurece ou clareia a cor aos poucos até atingir o contraste mínimo."""
    alvo = (0, 0, 0) if luminancia(fundo) > 0.5 else (255, 255, 255)
    r, g, b = _para_rgb(cor)
    for passo in range(1, 101):
        t = passo / 100
        candidata = _para_hex(*(round(c + (a - c) * t) for c, a in zip((r, g, b), alvo, strict=True)))
        if contraste(candidata, fundo) >= minimo:
            return candidata
    return _para_hex(*alvo)


def verificar_cores(cor_primaria: str, cor_secundaria: str, tema: str) -> list[str]:
    """Confere a legibilidade das cores no tema escolhido.

    Devolve uma lista de problemas em português. Lista vazia = tudo certo.
    """
    if tema not in FUNDOS:
        raise ValueError(f"tema inválido: {tema!r}. Use 'claro' ou 'escuro'.")

    fundo = FUNDOS[tema]
    direcao = "mais escura" if tema == "claro" else "mais clara"
    nome_fundo = f"o fundo {tema}"
    problemas = []

    # Contraste mínimo de cada uso das cores (SPEC, seção 4.4).
    regras = [
        ("cor_primaria", cor_primaria, "nas bordas e contornos", MINIMO_BORDA),
        ("cor_secundaria", cor_secundaria, "nos links e textos destacados", MINIMO_TEXTO),
    ]
    for campo, cor, uso, minimo in regras:
        cor = validar_formato(cor)
        razao = contraste(cor, fundo)
        if razao < minimo:
            sugestao = sugerir_cor(cor, fundo, minimo)
            problemas.append(
                f"aparencia.{campo} = {cor}: contraste {_formatar(razao)} : 1 "
                f"com {nome_fundo}, {uso} (mínimo {_formatar(minimo)} : 1). "
                f"Use uma cor {direcao}, por exemplo {sugestao}."
            )

    # Texto do botão: branco ou preto, escolhido automaticamente.
    cor_primaria = validar_formato(cor_primaria)
    texto = cor_do_texto_do_botao(cor_primaria)
    razao = contraste(cor_primaria, texto)
    if razao < MINIMO_TEXTO:
        problemas.append(
            f"aparencia.cor_primaria = {cor_primaria}: o texto do botão fica "
            f"com contraste {_formatar(razao)} : 1 (mínimo {_formatar(MINIMO_TEXTO)} : 1). "
            "Escolha uma cor bem mais clara ou bem mais escura."
        )

    return problemas
