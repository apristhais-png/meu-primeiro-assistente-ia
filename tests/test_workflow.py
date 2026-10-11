"""Testes do workflow do GitHub Actions (SPEC, seção 7.1, passo P12).

Conferem o arquivo .github/workflows/ci-deploy.yml: quando ele roda, quais
verificações faz, e que o job "testar" não usa segredos nem publica nada.
"""

from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOW = RAIZ / ".github" / "workflows" / "ci-deploy.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def testar(workflow) -> dict:
    return workflow["jobs"]["testar"]


def comandos(job: dict) -> str:
    return "\n".join(passo.get("run", "") for passo in job["steps"])


def gatilhos(workflow: dict) -> dict:
    # Atenção: no YAML, a palavra "on" sozinha vira o valor True.
    return workflow.get("on", workflow.get(True))


# ---------- Quando roda ----------

def test_roda_em_todo_pull_request_e_em_push_na_main(workflow):
    quando = gatilhos(workflow)
    assert "pull_request" in quando
    assert quando["push"]["branches"] == ["main"]


def test_robo_so_tem_permissao_de_leitura(workflow):
    assert workflow["permissions"] == {"contents": "read"}


# ---------- O que o job "testar" faz ----------

def test_usa_python_311(testar):
    [passo] = [p for p in testar["steps"] if str(p.get("uses", "")).startswith("actions/setup-python")]
    assert passo["with"]["python-version"] == "3.11"


@pytest.mark.parametrize(
    "comando",
    [
        "pip install -r requirements.txt -r requirements-dev.txt",
        "pip check",
        "python scripts/verificar_segredos.py",
        "ruff check .",
        "python scripts/validar_config.py",
        "pytest",
    ],
)
def test_faz_todas_as_verificacoes(testar, comando):
    assert comando in comandos(testar)


def test_nenhuma_falha_e_escondida(testar):
    # Qualquer passo que falhar precisa deixar o job vermelho.
    assert "continue-on-error" not in testar
    for passo in testar["steps"]:
        assert not passo.get("continue-on-error"), passo.get("name")
    texto = comandos(testar)
    assert "|| true" not in texto and "|| exit 0" not in texto and "set +e" not in texto


# ---------- O job "testar" não publica nem usa segredos ----------

def test_testar_nao_usa_segredos_nem_token(testar):
    texto = yaml.safe_dump(testar)
    assert "secrets." not in texto
    assert "HF_TOKEN" not in texto
    assert "HF_SPACE_ID" not in texto


def test_testar_nao_publica(testar):
    assert "publicar.py" not in comandos(testar)


def test_testar_roda_sem_nenhuma_chave_de_ia(testar):
    for chave in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        assert testar["env"][chave] == ""


def test_checkout_nao_guarda_credenciais(testar):
    [passo] = [p for p in testar["steps"] if str(p.get("uses", "")).startswith("actions/checkout")]
    assert passo["with"]["persist-credentials"] is False


def test_por_enquanto_nenhum_job_publica(workflow):
    # Só o job "testar": quem publica é o Render, depois que este job passa
    # (Revisão 13). O GitHub Actions nunca publica nada.
    assert list(workflow["jobs"]) == ["testar"]
    assert "publicar.py" not in WORKFLOW.read_text(encoding="utf-8").split("jobs:", 1)[1]
