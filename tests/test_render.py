"""Testes da preparação para o Render (passo P14).

Conferem o render.yaml, a versão do Python e o endereço em que o app escuta.
Um teste sobe o app.py de verdade com a variável PORT, como o Render faz,
SEM chaves de IA (nenhuma IA é chamada, nada gera custo).
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
import yaml

from assistente.interface import ENDERECO_LOCAL, endereco_do_servidor

RAIZ = Path(__file__).resolve().parent.parent
CHAVES_DE_IA = ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")


@pytest.fixture(scope="module")
def servico() -> dict:
    blueprint = yaml.safe_load((RAIZ / "render.yaml").read_text(encoding="utf-8"))
    [servico] = blueprint["services"]
    return servico


def variaveis(servico) -> dict:
    return {item["key"]: item for item in servico["envVars"]}


# ---------- render.yaml ----------


def test_servico_web_python_gratuito_na_main(servico):
    assert servico["type"] == "web"
    assert servico["runtime"] == "python"
    assert servico["plan"] == "free"
    assert servico["branch"] == "main"


def test_instala_so_as_bibliotecas_do_app_e_abre_o_app_py(servico):
    assert servico["buildCommand"] == "pip install -r requirements.txt"  # sem as de teste
    assert servico["startCommand"] == "python app.py"
    assert (RAIZ / "app.py").is_file()


def test_chaves_de_ia_nao_tem_valor_no_repositorio(servico):
    todas = variaveis(servico)
    for chave in CHAVES_DE_IA:
        assert todas[chave]["sync"] is False
        assert "value" not in todas[chave], f"{chave} não pode ter valor no render.yaml"


def test_nenhuma_variavel_secreta_tem_valor(servico):
    for nome, item in variaveis(servico).items():
        if any(palavra in nome.upper() for palavra in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            assert "value" not in item, nome


def test_estatisticas_do_gradio_desligadas(servico):
    assert variaveis(servico)["GRADIO_ANALYTICS_ENABLED"]["value"] == "False"


# ---------- Versão do Python ----------


def test_python_version_e_311_e_igual_ao_readme_e_ao_workflow():
    versao = (RAIZ / ".python-version").read_text(encoding="utf-8").strip()
    assert versao == "3.11"
    readme = (RAIZ / "README.md").read_text(encoding="utf-8").split("---\n", 2)[1]
    assert yaml.safe_load(readme)["python_version"] == versao
    workflow = yaml.safe_load((RAIZ / ".github/workflows/ci-deploy.yml").read_text(encoding="utf-8"))
    passos = workflow["jobs"]["testar"]["steps"]
    [python] = [p for p in passos if str(p.get("uses", "")).startswith("actions/setup-python")]
    assert python["with"]["python-version"] == versao


# ---------- Endereço do servidor ----------


def test_sem_port_escuta_so_no_proprio_computador():
    assert endereco_do_servidor({}) == ENDERECO_LOCAL == ("127.0.0.1", 7860)
    assert endereco_do_servidor({"PORT": "  "}) == ENDERECO_LOCAL


@pytest.mark.parametrize(("valor", "porta"), [("10000", 10000), (" 8080 ", 8080), ("1", 1), ("65535", 65535)])
def test_com_port_escuta_em_todas_as_interfaces(valor, porta):
    assert endereco_do_servidor({"PORT": valor}) == ("0.0.0.0", porta)


@pytest.mark.parametrize("valor", ["abc", "0", "65536", "-1", "10.5", "1e4"])
def test_port_invalida_e_recusada(valor):
    with pytest.raises(ValueError, match="PORT inválida"):
        endereco_do_servidor({"PORT": valor})


# ---------- O app.py de verdade ----------


def ambiente_sem_chaves(**extras) -> dict:
    ambiente = {k: v for k, v in os.environ.items() if k not in CHAVES_DE_IA}
    ambiente.update(
        {"GRADIO_ANALYTICS_ENABLED": "False", "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}
    )
    ambiente.update(extras)
    return ambiente


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_app_py_recusa_port_invalida():
    resultado = subprocess.run(
        [sys.executable, "app.py"],
        cwd=RAIZ,
        env=ambiente_sem_chaves(PORT="abc"),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert resultado.returncode == 1
    assert "PORT inválida" in resultado.stdout


def test_app_py_abre_na_porta_do_render():
    porta = porta_livre()
    processo = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=RAIZ,
        env=ambiente_sem_chaves(PORT=str(porta)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        pagina = None
        limite = time.monotonic() + 90
        while time.monotonic() < limite and processo.poll() is None:
            try:
                pagina = urllib.request.urlopen(f"http://127.0.0.1:{porta}/", timeout=5).read().decode()
                break
            except OSError:
                time.sleep(0.5)
        assert pagina is not None, "o app não respondeu na porta PORT"
        assert "Professor de Dados" in pagina
    finally:
        processo.terminate()
        try:
            saida, _ = processo.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            processo.kill()
            saida, _ = processo.communicate()
    assert f"Abrindo o app em 0.0.0.0:{porta}" in saida
