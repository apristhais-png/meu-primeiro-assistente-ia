"""Confere se os modelos do config.yml existem nos provedores, SEM CUSTO.

Como usar (na pasta do projeto):
    python scripts/conferir_modelos.py

O que ele faz:
    - Só CONSULTA a lista de modelos de cada provedor. Nenhuma pergunta é
      enviada à IA, então nada é cobrado.
    - OpenRouter: a lista é pública, não precisa de chave.
    - Anthropic e OpenAI: precisam da chave no .env (ou no ambiente). Sem a
      chave, o modelo fica como "pendente".
    - Nunca mostra as chaves; em caso de erro, mostra só o tipo do erro.

OpenRouter: confere o modelo principal E os modelos_reserva. Cada um precisa
existir no catálogo oficial, ter TODOS os preços iguais a zero e gerar só texto
(não pode ser classificador, moderação, embeddings...).

Resultado:
    - Código 0: tudo certo (ou pendente por falta de chave/internet).
    - Código 1: algum modelo não existe ou não serve (pago ou não conversa).
"""

import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

RAIZ_DO_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_DO_PROJETO))

from assistente.config import ErroDeConfiguracao, carregar_configuracao
from assistente.modelos_gratuitos import motivo_para_recusar_no_catalogo
from assistente.provedores import VARIAVEIS_DE_CHAVE

LISTA_PUBLICA_DO_OPENROUTER = "https://openrouter.ai/api/v1/models"


@dataclass
class Resultado:
    provedor: str
    modelo: str
    situacao: str  # "confirmado", "nao_encontrado", "inadequado", "pendente"
    detalhe: str = ""


# ---------- Consultas (substituídas por simulações nos testes) ----------

def baixar_lista_do_openrouter() -> list[dict]:
    with urllib.request.urlopen(LISTA_PUBLICA_DO_OPENROUTER, timeout=30) as resposta:
        return json.load(resposta).get("data", [])


def existe_na_anthropic(modelo: str, chave: str) -> bool:
    import anthropic

    cliente = anthropic.Anthropic(api_key=chave, max_retries=0, timeout=30)
    try:
        cliente.models.retrieve(modelo)  # só consulta; não gera texto
    except anthropic.NotFoundError:
        return False
    return True


def existe_na_openai(modelo: str, chave: str) -> bool:
    import openai

    cliente = openai.OpenAI(api_key=chave, max_retries=0, timeout=30)
    try:
        cliente.models.retrieve(modelo)  # só consulta; não gera texto
    except openai.NotFoundError:
        return False
    return True


# ---------- Conferência ----------

def conferir_openrouter(modelo: str, baixar=baixar_lista_do_openrouter) -> Resultado:
    try:
        modelos = {m.get("id"): m for m in baixar()}
    except Exception as erro:  # noqa: BLE001 - sem rede: fica pendente, não quebra
        return Resultado("openrouter", modelo, "pendente", f"sem acesso à lista ({type(erro).__name__})")
    if modelo not in modelos:
        return Resultado("openrouter", modelo, "nao_encontrado", "não está na lista oficial")
    motivo = motivo_para_recusar_no_catalogo(modelos[modelo])
    if motivo is None:
        return Resultado("openrouter", modelo, "confirmado", "gratuito, conversa em texto")
    if motivo.startswith("não é gratuito"):
        return Resultado("openrouter", modelo, "inadequado", "ATENÇÃO: é pago")
    return Resultado("openrouter", modelo, "inadequado", f"ATENÇÃO: {motivo}")


def conferir_com_chave(provedor: str, modelo: str, chave: str | None, consultar) -> Resultado:
    if not chave:
        return Resultado(provedor, modelo, "pendente", f"sem {VARIAVEIS_DE_CHAVE[provedor]} configurada")
    try:
        existe = consultar(modelo, chave)
    except Exception as erro:  # noqa: BLE001 - chave errada, rede etc.: fica pendente
        return Resultado(provedor, modelo, "pendente", f"não foi possível consultar ({type(erro).__name__})")
    if not existe:
        return Resultado(provedor, modelo, "nao_encontrado", "o provedor diz que este modelo não existe")
    return Resultado(provedor, modelo, "confirmado")


def conferir(config, ambiente, consultas=None) -> list[Resultado]:
    consultas = consultas or {
        "openrouter": baixar_lista_do_openrouter,
        "anthropic": existe_na_anthropic,
        "openai": existe_na_openai,
    }
    resultados = []
    lista_do_openrouter = None

    def baixar_uma_vez():
        nonlocal lista_do_openrouter
        if lista_do_openrouter is None:
            lista_do_openrouter = consultas["openrouter"]()
        return lista_do_openrouter

    for item in config.provedores_ativos:
        if item.nome == "openrouter":
            for modelo in (item.modelo, *item.modelos_reserva):
                resultados.append(conferir_openrouter(modelo, baixar_uma_vez))
        else:
            chave = (ambiente.get(VARIAVEIS_DE_CHAVE[item.nome]) or "").strip() or None
            resultados.append(conferir_com_chave(item.nome, item.modelo, chave, consultas[item.nome]))
    return resultados


SIMBOLOS = {
    "confirmado": "[OK]      ", "nao_encontrado": "[ERRO]    ", "inadequado": "[ERRO]    ", "pendente": "[PENDENTE]",
}


def main(ambiente=None, consultas=None, raiz: Path = RAIZ_DO_PROJETO) -> int:
    if ambiente is None:
        from dotenv import load_dotenv

        load_dotenv(raiz / ".env")
        ambiente = os.environ
    try:
        config = carregar_configuracao(raiz / "config.yml")
    except ErroDeConfiguracao as erro:
        print(f"[ERRO] {erro}")
        return 1

    resultados = conferir(config, ambiente, consultas)
    for r in resultados:
        detalhe = f" ({r.detalhe})" if r.detalhe else ""
        print(f"{SIMBOLOS[r.situacao]} {r.provedor}: {r.modelo}{detalhe}")

    if any(r.situacao in ("nao_encontrado", "inadequado") for r in resultados):
        print("\nCorrija o config.yml: troque os modelos marcados com [ERRO] (confira no site do provedor).")
        return 1
    if any(r.situacao == "pendente" for r in resultados):
        print("\nAlguns modelos ficaram pendentes: configure a chave no .env ou confira no site do provedor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
