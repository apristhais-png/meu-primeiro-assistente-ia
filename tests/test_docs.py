"""Testes do site de documentação (MkDocs Material).

Rodam sem o MkDocs instalado: leem o mkdocs.yml e as páginas em docs/. A
construção completa ("mkdocs build --strict", que também acha links
quebrados) roda no workflow docs.yml.
"""

from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
WORKFLOW = RAIZ / ".github" / "workflows" / "docs.yml"


class _CarregadorDoMkdocs(yaml.SafeLoader):
    """O mkdocs.yml usa tags !!python/name (extensões); aqui elas viram texto."""


_CarregadorDoMkdocs.add_multi_constructor("tag:yaml.org,2002:python/", lambda carregador, sufixo, no: sufixo)


@pytest.fixture(scope="module")
def mkdocs() -> dict:
    return yaml.load((RAIZ / "mkdocs.yml").read_text(encoding="utf-8"), Loader=_CarregadorDoMkdocs)


def paginas_do_menu(itens) -> list[str]:
    paginas = []
    for item in itens:
        if isinstance(item, str):
            paginas.append(item)
        elif isinstance(item, dict):
            for valor in item.values():
                paginas.extend(paginas_do_menu(valor) if isinstance(valor, list) else [valor])
    return paginas


# Os 21 temas obrigatórios (seção 14 do plano do projeto) → página e um trecho que precisa estar nela.
TEMAS = {
    "Apresentação do projeto": ("index.md", "Projeto acadêmico"),
    "Objetivos": ("index.md", "## Objetivos"),
    "Tecnologias utilizadas": ("tecnologias.md", "# Tecnologias utilizadas"),
    "Arquitetura": ("arquitetura.md", "## Visão geral"),
    "Estrutura de pastas": ("arquitetura.md", "## Estrutura de pastas"),
    "Configuração do ambiente": ("ambiente/index.md", "# Configuração do ambiente"),
    "Instalação com pipx, Poetry e pyenv": ("ambiente/instalacao.md", "pipx install poetry"),
    "Instruções para Windows": ("ambiente/windows.md", "pyenv-win"),
    "Funcionamento da API": ("dados/api.md", "localidades=N6[all]"),
    "Extração de dados": ("dados/extracao.md", "# Extração com Requests"),
    "Validação Pydantic": ("dados/validacao.md", "# Validação com Pydantic"),
    "Transformação Pandas": ("dados/transformacao.md", "# Transformação com Pandas"),
    "Dashboard Streamlit e Plotly": ("dashboard.md", "streamlit run dashboard/app.py"),
    "Professor de Dados": ("professor-de-dados.md", "# Professor de Dados"),
    "Testes com pytest": ("qualidade/testes.md", "# Testes com pytest"),
    "Cobertura com pytest-cov": ("qualidade/cobertura.md", "--cov=pipeline --cov=dashboard"),
    "Ruff": ("qualidade/ruff.md", "ruff format --check ."),
    "Segurança e variáveis de ambiente": ("seguranca.md", ".env.example"),
    "Como executar localmente": ("executar.md", "# Como executar localmente"),
    "Como publicar": ("publicar.md", "# Como publicar"),
    "Limitações e próximos passos": ("limitacoes.md", "## Próximos passos"),
}


def test_site_usa_o_tema_material_em_portugues(mkdocs):
    assert mkdocs["theme"]["name"] == "material"
    assert mkdocs["theme"]["language"] == "pt-BR"
    assert mkdocs["repo_url"] == "https://github.com/apristhais-png/meu-primeiro-assistente-ia"


def test_toda_pagina_do_menu_existe(mkdocs):
    faltando = [p for p in paginas_do_menu(mkdocs["nav"]) if not (DOCS / p).is_file()]
    assert faltando == []


def test_toda_pagina_esta_no_menu(mkdocs):
    no_menu = set(paginas_do_menu(mkdocs["nav"]))
    fora = sorted(str(p.relative_to(DOCS)) for p in DOCS.rglob("*.md") if str(p.relative_to(DOCS)) not in no_menu)
    assert fora == []


def test_links_quebrados_viram_erro_no_build(mkdocs):
    validacao = mkdocs["validation"]
    assert validacao["unrecognized_links"] == "warn"  # "mkdocs build --strict" transforma aviso em erro
    assert validacao["anchors"] == "warn"
    assert validacao["omitted_files"] == "warn"


@pytest.mark.parametrize(("tema", "pagina", "trecho"), [(t, *v) for t, v in TEMAS.items()])
def test_os_21_temas_obrigatorios_estao_documentados(tema, pagina, trecho):
    texto = (DOCS / pagina).read_text(encoding="utf-8")
    assert trecho in texto, f"{tema}: {trecho!r} não está em docs/{pagina}"


def test_sao_21_temas():
    assert len(TEMAS) == 21


def test_logo_do_site_e_a_mesma_do_chatbot(mkdocs):
    assert (DOCS / mkdocs["theme"]["logo"]).read_bytes() == (RAIZ / "assets" / "logo.svg").read_bytes()


# ---------- Workflow da documentação ----------


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_roda_so_em_pull_request_e_manual(workflow):
    # Chave "on" vira True no YAML 1.1.
    gatilhos = workflow[True]
    assert set(gatilhos) == {"pull_request", "workflow_dispatch"}  # nunca em push na main (não afeta o Render)


def test_workflow_so_le_e_nao_publica_no_github_pages(workflow):
    assert workflow["permissions"] == {"contents": "read"}
    texto = WORKFLOW.read_text(encoding="utf-8")
    for proibido in ("deploy-pages", "pages: write", "id-token", "gh-deploy", "secrets."):
        assert proibido not in texto


def test_workflow_constroi_em_modo_estrito(workflow):
    comandos = "\n".join(passo.get("run", "") for passo in workflow["jobs"]["docs"]["steps"])
    assert "pip install -r requirements-docs.txt" in comandos
    assert "mkdocs build --strict" in comandos


# ---------- Entrega final ----------

FERRAMENTAS_DA_AULA = [
    "Python 3.11",
    "pyenv",
    "pipx",
    "Poetry",
    "Requests",
    "Pydantic",
    "Pandas",
    "Streamlit",
    "Plotly",
    "python-dotenv",
    "pytest",
    "pytest-cov",
    "Ruff",
    "MkDocs Material",
    "GitHub Actions",
    "GitHub",
]


def test_checklist_final_cobre_todas_as_ferramentas_da_aula():
    texto = (DOCS / "entrega-final" / "checklist.md").read_text(encoding="utf-8")
    faltando = [f for f in FERRAMENTAS_DA_AULA if f"| **{f}** |" not in texto]
    assert faltando == []


def test_entrega_final_tem_relatorio_roteiro_e_evidencias():
    pasta = DOCS / "entrega-final"
    for pagina in (
        "index.md",
        "checklist.md",
        "testes-e-cobertura.md",
        "auditoria-seguranca.md",
        "evidencias.md",
        "roteiro-apresentacao.md",
    ):
        assert (pasta / pagina).is_file(), pagina
    assert list((pasta / "logs").glob("*.txt")), "faltam os logs de evidência"
    assert list((pasta / "img").glob("*.png")), "faltam as fotos de evidência"
