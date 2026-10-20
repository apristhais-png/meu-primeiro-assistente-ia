"""Envia o app para o Hugging Face Spaces, com regras de segurança.

LEGADO: desde a Revisão 13 da SPEC, o app é publicado no Render, que busca o
código direto do GitHub. Este script foi mantido (e continua testado), mas NÃO
faz parte da publicação pelo Render.

Como usar (na pasta do projeto):
    python scripts/publicar.py              # SIMULAÇÃO: só mostra o plano, não muda nada
    python scripts/publicar.py --publicar   # publica de verdade

Variáveis de ambiente:
    HF_SPACE_ID  nome do Space, no formato usuario/nome-do-space
    HF_TOKEN     token do Hugging Face com permissão de escrita (só para --publicar)

Regras:
    - ENVIA só os arquivos do app (LISTA PERMITIDA), e só se estiverem guardados no Git.
    - NUNCA envia .env, chaves, testes, workflows, documentos internos etc.
    - APAGA no Space só arquivos do app que saíram do projeto.
    - NUNCA mexe em .gitattributes nem em arquivos fora das pastas do app
      (por exemplo, algo criado à mão direto no Space).
    - Tudo vai em UMA atualização. Se o Space mudar enquanto o script roda,
      a atualização é recusada e nada é alterado.
    - Qualquer dúvida ou erro: para sem publicar (falha segura).
"""

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

RAIZ_DO_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_DO_PROJETO))
sys.path.insert(0, str(RAIZ_DO_PROJETO / "scripts"))

from verificar_segredos import procurar_no_texto

from assistente.config import ErroDeConfiguracao, carregar_configuracao

# ---------- As regras (conferidas pelos testes T9) ----------

# LISTA PERMITIDA: só isto pode ser enviado e, portanto, só isto é "do app".
ARQUIVOS_DO_APP = ("app.py", "config.yml", "requirements.txt", "README.md")
PASTAS_DO_APP = ("assistente/", "assets/")

# Sem estes, o app não funciona: se faltar algum, o script para.
ESSENCIAIS = ("app.py", "config.yml", "requirements.txt", "README.md", "assistente/__init__.py")

# Nunca são apagados, mesmo que alguém mude as listas acima por engano.
PROTEGIDOS = (".gitattributes",)

# Nunca são enviados, mesmo que estejam dentro de uma pasta do app.
PROIBIDOS = (
    ".env",
    ".env.*",
    "*.env",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "*secret*",
    "__pycache__/*",
    "*.pyc",
    ".git/*",
    ".github/*",
    "tests/*",
    "scripts/*",
    ".venv/*",
    "venv/*",
)

# Trava contra exclusões em massa (ex.: rodar o script na pasta errada).
MAXIMO_DE_EXCLUSOES = 20

_ID_DO_SPACE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")


class PublicacaoRecusada(Exception):
    """Uma regra de segurança impediu a publicação. Nada foi alterado."""


@dataclass
class Plano:
    enviar: list[str] = field(default_factory=list)
    apagar: list[str] = field(default_factory=list)
    intocados: list[str] = field(default_factory=list)  # arquivos do Space que não são do app


# ---------- Regras sobre caminhos ----------


def caminho_seguro(caminho: str) -> bool:
    """Recusa caminhos estranhos: absolutos, com "..", com barra invertida etc."""
    if not caminho or caminho.startswith("/") or "\\" in caminho or "\0" in caminho:
        return False
    # Confere o texto original, pedaço por pedaço. (Não usamos PurePosixPath
    # aqui porque ele "arruma" caminhos como "a//b" e "./a" e esconderia o problema.)
    return all(parte not in ("", ".", "..") for parte in caminho.split("/"))


def e_do_app(caminho: str) -> bool:
    """O caminho pertence ao app (está na lista permitida)?"""
    return caminho in ARQUIVOS_DO_APP or caminho.startswith(PASTAS_DO_APP)


def e_proibido(caminho: str) -> bool:
    nome = PurePosixPath(caminho).name
    for padrao in PROIBIDOS:
        if fnmatch.fnmatch(caminho, padrao) or fnmatch.fnmatch(nome, padrao):
            return True
        # "__pycache__/*" também vale para assistente/__pycache__/...
        if padrao.endswith("/*") and f"/{padrao[:-2]}/" in f"/{caminho}":
            return True
    return False


def e_protegido(caminho: str) -> bool:
    return caminho in PROTEGIDOS


# ---------- Arquivos locais ----------


def listar_arquivos_do_git(raiz: Path) -> list[str]:
    resultado = subprocess.run(["git", "ls-files", "-z"], cwd=raiz, capture_output=True, check=True)
    return [nome for nome in resultado.stdout.decode("utf-8").split("\0") if nome]


def escolher_arquivos_para_enviar(arquivos_do_git: list[str], raiz: Path) -> list[str]:
    """Aplica a lista permitida e todas as proteções. Para se algo estiver estranho."""
    enviar = []
    for caminho in arquivos_do_git:
        if not e_do_app(caminho):
            continue  # testes, scripts, SPEC, .github etc.: nunca vão para o Space
        if not caminho_seguro(caminho):
            raise PublicacaoRecusada(f"caminho estranho no projeto: {caminho!r}")
        if e_proibido(caminho):
            raise PublicacaoRecusada(
                f"o arquivo {caminho!r} está numa pasta do app, mas é do tipo que NUNCA "
                "pode ser enviado (chaves, .env, temporários). Tire-o do Git."
            )
        if not (raiz / caminho).is_file():
            raise PublicacaoRecusada(f"o arquivo {caminho!r} está no Git, mas não existe na pasta")
        enviar.append(caminho)

    faltando = [nome for nome in ESSENCIAIS if nome not in enviar]
    if faltando:
        raise PublicacaoRecusada(
            f"faltam arquivos essenciais do app: {', '.join(faltando)}. "
            "Confira se o script está rodando na pasta certa."
        )
    return sorted(enviar)


def conferir_chaves(enviar: list[str], raiz: Path) -> None:
    """Última barreira: nenhum arquivo enviado pode conter uma chave."""
    for caminho in enviar:
        conteudo = (raiz / caminho).read_bytes()
        if b"\0" in conteudo:
            continue  # binário (imagem)
        achados = procurar_no_texto(conteudo.decode("utf-8", errors="ignore"), caminho)
        if achados:
            a = achados[0]
            raise PublicacaoRecusada(f"possível chave {a.servico} em {a.arquivo}, linha {a.linha}")


def conferir_config(raiz: Path) -> None:
    try:
        carregar_configuracao(raiz / "config.yml")
    except ErroDeConfiguracao as erro:
        raise PublicacaoRecusada(f"o config.yml tem problemas:\n{erro}") from None


# ---------- Plano ----------


def planejar(enviar: list[str], arquivos_do_space: list[str]) -> Plano:
    """Decide o que enviar, o que apagar e o que deixar como está no Space."""
    locais = set(enviar)
    apagar, intocados = [], []
    for caminho in sorted(arquivos_do_space):
        if e_protegido(caminho) or not e_do_app(caminho) or not caminho_seguro(caminho):
            intocados.append(caminho)  # não é do app: não mexemos
        elif caminho not in locais:
            apagar.append(caminho)  # é do app e saiu do projeto
    plano = Plano(enviar=sorted(enviar), apagar=apagar, intocados=intocados)
    conferir_plano(plano)
    return plano


def conferir_plano(plano: Plano) -> None:
    """Travas finais antes de qualquer alteração."""
    for caminho in plano.apagar:
        if e_protegido(caminho) or not e_do_app(caminho) or caminho in ESSENCIAIS:
            raise PublicacaoRecusada(f"o plano tentaria apagar {caminho!r}, que é protegido")
    if len(plano.apagar) > MAXIMO_DE_EXCLUSOES:
        raise PublicacaoRecusada(
            f"o plano apagaria {len(plano.apagar)} arquivos (máximo: {MAXIMO_DE_EXCLUSOES}). "
            "Isso parece um engano; confira o projeto antes de publicar."
        )


# ---------- Hugging Face ----------


def criar_api(token: str | None):
    from huggingface_hub import HfApi

    return HfApi(token=token)


def publicar_no_space(api, space_id: str, plano: Plano, raiz: Path, revisao: str) -> None:
    """Envia tudo em UMA atualização, presa à versão do Space que foi lida."""
    from huggingface_hub import CommitOperationAdd, CommitOperationDelete

    operacoes = [CommitOperationAdd(path_in_repo=c, path_or_fileobj=str(raiz / c)) for c in plano.enviar]
    operacoes += [CommitOperationDelete(path_in_repo=c) for c in plano.apagar]
    api.create_commit(
        repo_id=space_id,
        repo_type="space",
        operations=operacoes,
        commit_message="Publicação automática pelo GitHub Actions",
        # Se o Space mudou depois da leitura, o Hugging Face recusa a atualização.
        parent_commit=revisao,
    )


def mostrar_plano(plano: Plano) -> None:
    print(f"Enviar ({len(plano.enviar)}):")
    for caminho in plano.enviar:
        print(f"  + {caminho}")
    print(f"Apagar do Space ({len(plano.apagar)}):")
    for caminho in plano.apagar:
        print(f"  - {caminho}")
    print(f"Deixar como está no Space ({len(plano.intocados)}):")
    for caminho in plano.intocados:
        print(f"  = {caminho}")


# ---------- Programa ----------


def main(argumentos=None, ambiente=None, api=None, raiz: Path = RAIZ_DO_PROJETO) -> int:
    leitor = argparse.ArgumentParser(description="Publica o app no Hugging Face Spaces.")
    leitor.add_argument("--publicar", action="store_true", help="publica de verdade (sem isto, só simula)")
    opcoes = leitor.parse_args(argumentos)
    ambiente = os.environ if ambiente is None else ambiente

    space_id = (ambiente.get("HF_SPACE_ID") or "").strip()
    token = (ambiente.get("HF_TOKEN") or "").strip() or None
    modo = "PUBLICAÇÃO" if opcoes.publicar else "SIMULAÇÃO (nada será alterado)"
    print(f"=== {modo} ===")

    try:
        # 1. Configuração mínima.
        if not space_id:
            raise PublicacaoRecusada("falta a variável HF_SPACE_ID (ex.: usuario/nome-do-space)")
        if not _ID_DO_SPACE.match(space_id):
            raise PublicacaoRecusada(f"HF_SPACE_ID inválido: {space_id!r}. Use o formato usuario/nome-do-space")
        if opcoes.publicar and not token:
            raise PublicacaoRecusada("falta a variável HF_TOKEN (token com permissão de escrita)")

        # 2. O que vai ser enviado, com todas as proteções.
        enviar = escolher_arquivos_para_enviar(listar_arquivos_do_git(raiz), raiz)
        conferir_config(raiz)
        conferir_chaves(enviar, raiz)

        # 3. O que já está no Space, numa versão fixa.
        api = api or criar_api(token)
        revisao = api.repo_info(repo_id=space_id, repo_type="space").sha
        arquivos_do_space = api.list_repo_files(repo_id=space_id, repo_type="space", revision=revisao)

        # 4. O plano, com as travas finais.
        plano = planejar(enviar, arquivos_do_space)
    except PublicacaoRecusada as motivo:
        print(f"[ERRO] Publicação cancelada: {motivo}")
        print("Nada foi alterado no Space.")
        return 1
    except Exception as erro:  # noqa: BLE001 - falha segura: qualquer erro cancela
        # Só o tipo do erro: a mensagem poderia conter dados sensíveis.
        print(f"[ERRO] Falha ao preparar a publicação ({type(erro).__name__}). Nada foi alterado no Space.")
        return 1

    mostrar_plano(plano)
    if not opcoes.publicar:
        print("[OK] Simulação concluída. Para publicar de verdade, use --publicar.")
        return 0

    try:
        publicar_no_space(api, space_id, plano, raiz, revisao)
    except Exception as erro:  # noqa: BLE001 - falha segura: a atualização é única, nada pela metade
        print(f"[ERRO] O Hugging Face recusou a publicação ({type(erro).__name__}). Nada foi alterado no Space.")
        print("Se o Space mudou enquanto o script rodava, rode a publicação de novo.")
        return 1

    print(f"[OK] Publicado em https://huggingface.co/spaces/{space_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
