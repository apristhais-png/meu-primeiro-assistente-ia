"""Testes de consistência das versões (SPEC, teste T7 e seção 3.2).

O Hugging Face instala o Gradio pela versão do cabeçalho do README.md
(sdk_version), e não pela do requirements.txt. Se as duas forem diferentes,
o app pode funcionar no computador e quebrar no Space. Estes testes bloqueiam
a publicação nesse caso.
"""

import re
import subprocess
from importlib.metadata import version
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent

# Uma linha que fixa o Gradio, como "gradio==X.Y.Z" (com números no lugar de X, Y e Z).
# O (?![-_\w]) evita confundir com pacotes como "gradio-client".
_VERSAO_DO_GRADIO = re.compile(r"\bgradio(?![-_\w])\s*(==|>=|<=|~=|!=|>|<)\s*([0-9][0-9.]*)", re.IGNORECASE)


def linhas_de_requisitos(nome: str) -> list[str]:
    """Linhas de um requirements*.txt, sem comentários e linhas vazias."""
    linhas = []
    for linha in (RAIZ / nome).read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if linha:
            linhas.append(linha)
    return linhas


def versao_fixada_do_gradio() -> str:
    pinos = [linha for linha in linhas_de_requisitos("requirements.txt") if _VERSAO_DO_GRADIO.search(linha)]
    assert len(pinos) == 1, f"O Gradio deve aparecer UMA vez no requirements.txt, apareceu: {pinos}"
    operador, numero = _VERSAO_DO_GRADIO.search(pinos[0]).groups()
    assert operador == "==", f"Fixe a versão com '==' (encontrado: {pinos[0]!r})"
    return numero


def cabecalho_do_readme() -> dict:
    texto = (RAIZ / "README.md").read_text(encoding="utf-8")
    assert texto.startswith("---\n"), "O README.md precisa COMEÇAR com o cabeçalho do Hugging Face (linha '---')"
    bloco = texto.split("---\n", 2)[1]
    dados = yaml.safe_load(bloco)
    assert isinstance(dados, dict), "O cabeçalho do README.md não é um YAML válido"
    return dados


def arquivos_do_git() -> list[Path]:
    resultado = subprocess.run(["git", "ls-files", "-z"], cwd=RAIZ, capture_output=True, check=True)
    return [RAIZ / nome for nome in resultado.stdout.decode().split("\0") if nome]


# ---------- requirements.txt ----------

def test_gradio_fixado_com_igual_igual_uma_unica_vez():
    assert re.fullmatch(r"\d+\.\d+\.\d+", versao_fixada_do_gradio())


def test_todas_as_bibliotecas_tem_versao_fixada():
    # Versões fixas: o que é testado é exatamente o que será publicado.
    for nome in ("requirements.txt", "requirements-dev.txt", "requirements-dados.txt"):
        for linha in linhas_de_requisitos(nome):
            assert re.fullmatch(r"[A-Za-z0-9_.\-\[\]]+==[0-9][0-9A-Za-z.]*", linha), f"{nome}: fixe com '==' → {linha!r}"


def test_bibliotecas_repetidas_tem_a_mesma_versao_em_todos_os_arquivos():
    # Ex.: o pydantic aparece no requirements.txt (chatbot) e no requirements-dados.txt (pipeline).
    versoes: dict[str, set[str]] = {}
    for nome in ("requirements.txt", "requirements-dev.txt", "requirements-dados.txt"):
        for linha in linhas_de_requisitos(nome):
            pacote, versao = linha.split("==")
            versoes.setdefault(pacote.lower(), set()).add(versao)
    diferentes = {pacote: v for pacote, v in versoes.items() if len(v) > 1}
    assert diferentes == {}, f"Versões diferentes entre os arquivos: {diferentes}"


def test_requirements_dev_nao_lista_o_gradio():
    for linha in linhas_de_requisitos("requirements-dev.txt"):
        assert not re.match(r"gradio(?![-_\w])", linha, re.IGNORECASE), "O Gradio só pode estar no requirements.txt"


# ---------- Cabeçalho do README.md (Hugging Face) ----------

def test_cabecalho_usa_gradio_app_py_e_python_311():
    dados = cabecalho_do_readme()
    assert dados["sdk"] == "gradio"
    assert dados["app_file"] == "app.py"
    assert (RAIZ / dados["app_file"]).is_file()
    # Entre aspas no YAML: sem aspas, 3.10 viraria o número 3.1.
    assert dados["python_version"] == "3.11"


def test_sdk_version_do_readme_e_igual_ao_requirements():
    assert str(cabecalho_do_readme()["sdk_version"]) == versao_fixada_do_gradio()


def test_campos_do_cabecalho_seguem_as_regras_do_hugging_face():
    dados = cabecalho_do_readme()
    cores_aceitas = {"red", "yellow", "green", "blue", "indigo", "purple", "pink", "gray"}
    assert dados["colorFrom"] in cores_aceitas
    assert dados["colorTo"] in cores_aceitas
    assert dados["title"]
    assert len(dados.get("short_description", "")) <= 60


# ---------- Nenhum outro arquivo com versão diferente ----------

def test_nenhum_arquivo_fixa_outra_versao_do_gradio():
    esperada = versao_fixada_do_gradio()
    diferentes = []
    for caminho in arquivos_do_git():
        if caminho.suffix in {".png", ".svg"} or not caminho.is_file():
            continue
        texto = caminho.read_text(encoding="utf-8", errors="ignore")
        for numero_da_linha, linha in enumerate(texto.splitlines(), start=1):
            for _, numero in _VERSAO_DO_GRADIO.findall(linha):
                if numero != esperada:
                    diferentes.append(f"{caminho.relative_to(RAIZ)}:{numero_da_linha} → {numero}")
            achado = re.search(r"^\s*sdk_version:\s*['\"]?([0-9][0-9.]*)", linha)
            if achado and achado.group(1) != esperada:
                diferentes.append(f"{caminho.relative_to(RAIZ)}:{numero_da_linha} → sdk_version {achado.group(1)}")
    assert diferentes == [], f"Versões do Gradio diferentes de {esperada}: {diferentes}"


# ---------- O que está instalado é o que será publicado ----------

def test_gradio_instalado_e_o_mesmo_do_requirements():
    instalada = version("gradio")
    assert instalada == versao_fixada_do_gradio(), (
        f"Gradio instalado ({instalada}) é diferente do requirements.txt. "
        "Rode: pip install -r requirements.txt"
    )


def test_python_do_workflow_e_o_mesmo_do_readme():
    # O workflow do GitHub Actions é criado no passo P12; até lá, o teste é pulado.
    workflows = sorted((RAIZ / ".github" / "workflows").glob("*.yml"))
    if not workflows:
        pytest.skip("Ainda não há workflow do GitHub Actions (passo P12).")
    esperado = cabecalho_do_readme()["python_version"]
    for workflow in workflows:
        versoes = re.findall(r"python-version:\s*['\"]?([0-9.]+)", workflow.read_text(encoding="utf-8"))
        assert versoes, f"{workflow.name}: defina python-version"
        assert set(versoes) == {esperado}, f"{workflow.name}: use Python {esperado}"
