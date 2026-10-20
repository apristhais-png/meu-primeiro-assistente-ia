"""Poetry e requirements*.txt precisam dizer a MESMA coisa.

O Render instala o requirements.txt (pip); no computador dá para usar o
Poetry (pyproject.toml + poetry.lock). Se um lado mudar e o outro não, o
que é testado deixa de ser o que é publicado. Estes testes impedem isso:

    requirements.txt        <->  [project] dependencies
    requirements-dados.txt  <->  [tool.poetry.group.dados.dependencies]
    requirements-dev.txt    <->  [tool.poetry.group.dev.dependencies]

E conferem que o poetry.lock trava exatamente essas versões. (O workflow
poetry.yml roda também "poetry check --lock" e uma instalação completa.)
"""

import re
import tomllib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


def normalizar(nome: str) -> str:
    """Nomes de pacote como o pip/PyPI comparam (PEP 503): PyYAML == pyyaml, a_b == a-b."""
    return re.sub(r"[-_.]+", "-", nome).lower()


def requisitos(arquivo: str) -> dict[str, str]:
    pinos = {}
    for linha in (RAIZ / arquivo).read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if linha:
            pacote, versao = linha.split("==")
            pinos[normalizar(pacote)] = versao
    return pinos


@pytest.fixture(scope="module")
def pyproject() -> dict:
    return tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lock() -> dict[str, str]:
    dados = tomllib.loads((RAIZ / "poetry.lock").read_text(encoding="utf-8"))
    return {normalizar(p["name"]): p["version"] for p in dados["package"]}


def dependencias_principais(pyproject) -> dict[str, str]:
    pinos = {}
    for item in pyproject["project"]["dependencies"]:
        pacote, versao = item.split("==")
        pinos[normalizar(pacote)] = versao
    return pinos


def grupo(pyproject, nome: str) -> dict[str, str]:
    dependencias = pyproject["tool"]["poetry"]["group"][nome]["dependencies"]
    return {normalizar(p): v for p, v in dependencias.items()}


def test_dependencias_do_chatbot_sao_as_do_requirements_txt(pyproject):
    assert dependencias_principais(pyproject) == requisitos("requirements.txt")


def test_grupo_dados_e_o_requirements_dados_txt(pyproject):
    esperado = requisitos("requirements-dados.txt")
    # O pydantic é do chatbot também: no Poetry ele fica só nas principais (mesma versão).
    assert esperado.pop("pydantic") == dependencias_principais(pyproject)["pydantic"]
    assert grupo(pyproject, "dados") == esperado


def test_grupo_dev_e_o_requirements_dev_txt(pyproject):
    assert grupo(pyproject, "dev") == requisitos("requirements-dev.txt")


def test_versoes_exatas_no_pyproject(pyproject):
    # Igual aos requirements: nada de faixas (^, ~, >=), o instalado é o testado.
    for versao in [
        *dependencias_principais(pyproject).values(),
        *grupo(pyproject, "dados").values(),
        *grupo(pyproject, "dev").values(),
    ]:
        assert re.fullmatch(r"\d+(\.\d+)*", versao), versao


@pytest.mark.parametrize("arquivo", ["requirements.txt", "requirements-dados.txt", "requirements-dev.txt"])
def test_poetry_lock_trava_as_mesmas_versoes(lock, arquivo):
    for pacote, versao in requisitos(arquivo).items():
        assert lock.get(pacote) == versao, f"{pacote}: requirements={versao}, poetry.lock={lock.get(pacote)}"


def test_streamlit_e_plotly_ficam_fora_das_dependencias_do_chatbot(pyproject):
    principais = dependencias_principais(pyproject)
    assert "streamlit" not in principais and "plotly" not in principais
    assert {"streamlit", "plotly"} <= set(grupo(pyproject, "dados"))


def test_grupos_opcionais_poetry_install_instala_so_o_chatbot(pyproject):
    for nome in ("dados", "dev"):
        assert pyproject["tool"]["poetry"]["group"][nome]["optional"] is True


def test_poetry_nao_empacota_e_nao_entra_nas_dependencias(pyproject):
    assert pyproject["tool"]["poetry"]["package-mode"] is False
    todas = {*dependencias_principais(pyproject), *grupo(pyproject, "dados"), *grupo(pyproject, "dev")}
    assert "poetry" not in todas  # o Poetry é instalado à parte, com o pipx


def test_python_311_em_todos_os_lugares(pyproject):
    assert (RAIZ / ".python-version").read_text(encoding="utf-8").strip() == "3.11"
    assert pyproject["project"]["requires-python"] == ">=3.11,<3.12"
    assert pyproject["tool"]["ruff"]["target-version"] == "py311"
    lock = tomllib.loads((RAIZ / "poetry.lock").read_text(encoding="utf-8"))
    assert lock["metadata"]["python-versions"] == ">=3.11,<3.12"


def test_render_continua_com_pip_e_requirements_txt():
    render = (RAIZ / "render.yaml").read_text(encoding="utf-8")
    assert "buildCommand: pip install -r requirements.txt\n" in render
    assert "poetry" not in render.lower()
