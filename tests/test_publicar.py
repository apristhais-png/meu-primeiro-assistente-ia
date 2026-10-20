"""Testes das regras de publicação (SPEC, teste T9 e seção 7.2).

Tudo é simulado: cada teste monta um projeto de mentira numa pasta temporária
(com Git próprio) e usa um "Hugging Face de mentira" (ApiFalsa), que só anota
o que receberia. Nada é publicado, nenhum token real é usado e nada remoto é
apagado.
"""

import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import publicar as pub

TOKEN_FALSO = "token-de-teste-nao-real-777"
SPACE = "usuario-teste/professor-de-dados"
REVISAO = "abc123revisaofalsa"


@pytest.fixture(autouse=True)
def bloquear_rede(monkeypatch):
    def proibido(*args, **kwargs):
        raise RuntimeError("Acesso à rede bloqueado nos testes")

    monkeypatch.setattr(socket.socket, "connect", proibido)
    monkeypatch.setattr(socket, "create_connection", proibido)


class ApiFalsa:
    """Imita o Hugging Face: lista arquivos e anota as publicações, sem rede."""

    def __init__(self, arquivos=(), erro_ao_listar=None, erro_ao_publicar=None):
        self.arquivos = list(arquivos)
        self.erro_ao_listar = erro_ao_listar
        self.erro_ao_publicar = erro_ao_publicar
        self.publicacoes = []
        self.chamadas = []

    def repo_info(self, repo_id, repo_type):
        self.chamadas.append(("repo_info", repo_id, repo_type))
        if self.erro_ao_listar:
            raise self.erro_ao_listar
        return type("Info", (), {"sha": REVISAO})()

    def list_repo_files(self, repo_id, repo_type, revision):
        self.chamadas.append(("list_repo_files", repo_id, repo_type, revision))
        return list(self.arquivos)

    def create_commit(self, **argumentos):
        if self.erro_ao_publicar:
            raise self.erro_ao_publicar
        self.publicacoes.append(argumentos)


def git(pasta, *argumentos):
    subprocess.run(["git", *argumentos], cwd=pasta, check=True, capture_output=True)


@pytest.fixture
def projeto(tmp_path):
    """Um projeto de mentira, parecido com o real, com Git próprio."""
    arquivos = {
        "app.py": "print('app')\n",
        "README.md": "---\nsdk: gradio\n---\n# Teste\n",
        "assistente/__init__.py": "",
        "assistente/chat.py": "# chat\n",
        "tests/test_algo.py": "# teste\n",
        "scripts/publicar.py": "# script\n",
        "SPEC-parte1-cicd-deploy.md": "# spec\n",
        "IDEIA-parte1.md": "# ideia\n",
        ".github/workflows/ci-deploy.yml": "name: ci\n",
        ".env.example": "OPENAI_API_KEY=SUA_CHAVE_AQUI\n",
        ".gitignore": ".env\n__pycache__/\n",
        "pyproject.toml": "[tool.pytest.ini_options]\n",
    }
    for nome, conteudo in arquivos.items():
        caminho = tmp_path / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(conteudo, encoding="utf-8")
    shutil.copy(RAIZ / "config.yml", tmp_path / "config.yml")
    shutil.copy(RAIZ / "requirements.txt", tmp_path / "requirements.txt")
    (tmp_path / "assets").mkdir()
    shutil.copy(RAIZ / "assets" / "logo.svg", tmp_path / "assets" / "logo.svg")
    # Um .env de verdade (ignorado pelo Git), que NUNCA pode ser enviado.
    (tmp_path / ".env").write_text(f"HF_TOKEN={TOKEN_FALSO}\n", encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    return tmp_path


ESPERADOS = [
    "README.md",
    "app.py",
    "assets/logo.svg",
    "assistente/__init__.py",
    "assistente/chat.py",
    "config.yml",
    "requirements.txt",
]


def rodar(projeto, *argumentos, api=None, ambiente=None):
    ambiente = {"HF_SPACE_ID": SPACE, "HF_TOKEN": TOKEN_FALSO} if ambiente is None else ambiente
    return pub.main(list(argumentos), ambiente=ambiente, api=api, raiz=projeto)


# =============================================================
# Lista permitida: o que é enviado
# =============================================================


def test_envia_so_os_arquivos_do_app(projeto):
    enviar = pub.escolher_arquivos_para_enviar(pub.listar_arquivos_do_git(projeto), projeto)
    assert enviar == ESPERADOS


@pytest.mark.parametrize(
    "nunca",
    [
        "tests/test_algo.py",
        "scripts/publicar.py",
        "SPEC-parte1-cicd-deploy.md",
        "IDEIA-parte1.md",
        ".github/workflows/ci-deploy.yml",
        ".env",
        ".env.example",
        ".gitignore",
        "pyproject.toml",
    ],
)
def test_nunca_envia_testes_scripts_documentos_e_segredos(projeto, nunca):
    assert nunca not in pub.escolher_arquivos_para_enviar(pub.listar_arquivos_do_git(projeto), projeto)


def test_arquivo_fora_do_git_nao_e_enviado(projeto):
    (projeto / "assistente" / "rascunho.py").write_text("# não adicionado ao Git\n")
    assert "assistente/rascunho.py" not in pub.escolher_arquivos_para_enviar(
        pub.listar_arquivos_do_git(projeto), projeto
    )


@pytest.mark.parametrize(
    "perigoso",
    [
        "assistente/.env",
        "assets/.env.local",
        "assets/chave.pem",
        "assets/servidor.key",
        "assistente/client_secret.json",
        "assistente/__pycache__/chat.cpython-311.pyc",
        "assets/id_rsa",
    ],
)
def test_arquivo_perigoso_numa_pasta_do_app_cancela_tudo(projeto, perigoso, capsys):
    caminho = projeto / perigoso
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("conteúdo sensível\n")
    git(projeto, "add", "-f", perigoso)
    api = ApiFalsa()
    assert rodar(projeto, "--publicar", api=api) == 1
    assert "NUNCA pode ser enviado" in capsys.readouterr().out
    assert api.publicacoes == [] and api.chamadas == []


def test_chave_dentro_de_um_arquivo_do_app_cancela_tudo(projeto, capsys):
    chave_falsa = "sk-or-v1-" + "a1" * 32  # montada aqui, nunca guardada no repositório
    (projeto / "assistente" / "chat.py").write_text(f'CHAVE = "{chave_falsa}"\n')
    api = ApiFalsa()
    assert rodar(projeto, "--publicar", api=api) == 1
    saida = capsys.readouterr().out
    assert "possível chave OpenRouter em assistente/chat.py" in saida
    assert chave_falsa not in saida
    assert api.publicacoes == []


@pytest.mark.parametrize(
    "essencial", ["app.py", "config.yml", "requirements.txt", "README.md", "assistente/__init__.py"]
)
def test_falta_de_arquivo_essencial_cancela_tudo(projeto, essencial, capsys):
    git(projeto, "rm", "-q", "--cached", essencial)
    api = ApiFalsa()
    assert rodar(projeto, "--publicar", api=api) == 1
    assert "faltam arquivos essenciais" in capsys.readouterr().out
    assert api.publicacoes == []


def test_config_invalido_cancela_tudo(projeto, capsys):
    (projeto / "config.yml").write_text("assistente:\n  nome: ''\n", encoding="utf-8")
    api = ApiFalsa()
    assert rodar(projeto, "--publicar", api=api) == 1
    assert "config.yml tem problemas" in capsys.readouterr().out
    assert api.publicacoes == []


# =============================================================
# O que é apagado e o que é protegido no Space
# =============================================================


def test_apaga_so_arquivos_do_app_que_sairam_do_projeto():
    no_space = [
        "app.py",
        "README.md",
        ".gitattributes",
        "assets/logo.svg",
        "assets/logo-antiga.svg",
        "assistente/modulo_removido.py",
        "dados/arquivo.csv",
        "notas.txt",
        "outra-pasta/x.py",
        "tests/test_velho.py",
    ]
    plano = pub.planejar(ESPERADOS, no_space)
    assert plano.apagar == ["assets/logo-antiga.svg", "assistente/modulo_removido.py"]
    assert plano.intocados == [
        ".gitattributes",
        "dados/arquivo.csv",
        "notas.txt",
        "outra-pasta/x.py",
        "tests/test_velho.py",
    ]
    assert plano.enviar == ESPERADOS


def test_ca16_arquivo_de_teste_sai_do_space_e_a_logo_fica():
    plano = pub.planejar(ESPERADOS, ["assets/logo.svg", "assets/teste.txt", ".gitattributes"])
    assert plano.apagar == ["assets/teste.txt"]
    assert "assets/logo.svg" not in plano.apagar


def test_caminhos_estranhos_no_space_nunca_sao_apagados():
    estranhos = ["assets/../app.py", "assets//x", "assets/./x", "/assets/x", "assets\\x"]
    plano = pub.planejar(ESPERADOS, estranhos)
    assert plano.apagar == []
    assert sorted(plano.intocados) == sorted(estranhos)


@pytest.mark.parametrize("caminho", [".gitattributes", "app.py", "config.yml", "dados/arquivo.csv"])
def test_trava_final_impede_apagar_protegidos(caminho):
    with pytest.raises(pub.PublicacaoRecusada, match="protegido"):
        pub.conferir_plano(pub.Plano(enviar=ESPERADOS, apagar=[caminho]))


def test_exclusao_em_massa_e_bloqueada(projeto, capsys):
    antigos = [f"assets/antigo-{n}.png" for n in range(pub.MAXIMO_DE_EXCLUSOES + 1)]
    api = ApiFalsa(arquivos=antigos)
    assert rodar(projeto, "--publicar", api=api) == 1
    assert "parece um engano" in capsys.readouterr().out
    assert api.publicacoes == []


def test_ate_o_limite_de_exclusoes_e_permitido():
    antigos = [f"assets/antigo-{n}.png" for n in range(pub.MAXIMO_DE_EXCLUSOES)]
    assert len(pub.planejar(ESPERADOS, antigos).apagar) == pub.MAXIMO_DE_EXCLUSOES


# =============================================================
# Simulação x publicação
# =============================================================


def test_sem_publicar_e_so_simulacao(projeto, capsys):
    api = ApiFalsa(arquivos=["assets/velho.svg", "notas.txt"])
    assert rodar(projeto, api=api) == 0
    saida = capsys.readouterr().out
    assert "SIMULAÇÃO" in saida and "- assets/velho.svg" in saida and "= notas.txt" in saida
    assert api.publicacoes == []


def test_simulacao_funciona_sem_token(projeto):
    api = ApiFalsa()
    assert rodar(projeto, api=api, ambiente={"HF_SPACE_ID": SPACE}) == 0


def test_publicacao_e_uma_unica_atualizacao_presa_a_versao_lida(projeto):
    api = ApiFalsa(arquivos=["app.py", "assets/velho.svg", ".gitattributes", "dados/arquivo.csv"])
    assert rodar(projeto, "--publicar", api=api) == 0
    [publicacao] = api.publicacoes
    assert publicacao["repo_id"] == SPACE
    assert publicacao["repo_type"] == "space"
    assert publicacao["parent_commit"] == REVISAO
    assert ("list_repo_files", SPACE, "space", REVISAO) in api.chamadas

    operacoes = publicacao["operations"]
    enviados = sorted(op.path_in_repo for op in operacoes if type(op).__name__ == "CommitOperationAdd")
    apagados = [op.path_in_repo for op in operacoes if type(op).__name__ == "CommitOperationDelete"]
    assert enviados == ESPERADOS
    assert apagados == ["assets/velho.svg"]
    for op in operacoes:
        if type(op).__name__ == "CommitOperationAdd":
            assert Path(op.path_or_fileobj) == projeto / op.path_in_repo


# =============================================================
# Falha segura: configuração incompleta e erros
# =============================================================


@pytest.mark.parametrize(
    ("ambiente", "mensagem"),
    [
        ({"HF_TOKEN": TOKEN_FALSO}, "falta a variável HF_SPACE_ID"),
        ({"HF_SPACE_ID": "  ", "HF_TOKEN": TOKEN_FALSO}, "falta a variável HF_SPACE_ID"),
        ({"HF_SPACE_ID": "sem-barra", "HF_TOKEN": TOKEN_FALSO}, "HF_SPACE_ID inválido"),
        ({"HF_SPACE_ID": "a/b/c", "HF_TOKEN": TOKEN_FALSO}, "HF_SPACE_ID inválido"),
        ({"HF_SPACE_ID": "../x", "HF_TOKEN": TOKEN_FALSO}, "HF_SPACE_ID inválido"),
        ({"HF_SPACE_ID": SPACE}, "falta a variável HF_TOKEN"),
        ({"HF_SPACE_ID": SPACE, "HF_TOKEN": "   "}, "falta a variável HF_TOKEN"),
    ],
)
def test_configuracao_incompleta_cancela_antes_de_qualquer_acesso(projeto, capsys, ambiente, mensagem):
    api = ApiFalsa()
    assert rodar(projeto, "--publicar", api=api, ambiente=ambiente) == 1
    saida = capsys.readouterr().out
    assert mensagem in saida and "Nada foi alterado" in saida
    assert api.chamadas == [] and api.publicacoes == []


def test_erro_ao_ler_o_space_cancela_sem_mostrar_o_token(projeto, capsys):
    api = ApiFalsa(erro_ao_listar=RuntimeError(f"401 Unauthorized para o token {TOKEN_FALSO}"))
    assert rodar(projeto, "--publicar", api=api) == 1
    saida = capsys.readouterr()
    assert "RuntimeError" in saida.out and "Nada foi alterado" in saida.out
    assert TOKEN_FALSO not in saida.out + saida.err
    assert api.publicacoes == []


def test_erro_ao_publicar_avisa_que_nada_mudou_sem_mostrar_o_token(projeto, capsys):
    api = ApiFalsa(erro_ao_publicar=RuntimeError(f"412 o Space mudou; token {TOKEN_FALSO}"))
    assert rodar(projeto, "--publicar", api=api) == 1
    saida = capsys.readouterr()
    assert "recusou a publicação" in saida.out and "Nada foi alterado" in saida.out
    assert TOKEN_FALSO not in saida.out + saida.err


def test_token_nunca_aparece_na_saida(projeto, capsys):
    rodar(projeto, "--publicar", api=ApiFalsa(arquivos=["assets/velho.svg"]))
    saida = capsys.readouterr()
    assert TOKEN_FALSO not in saida.out + saida.err


# =============================================================
# Regras sobre caminhos
# =============================================================


@pytest.mark.parametrize("caminho", ["app.py", "assets/logo.svg", "assistente/sub/x.py"])
def test_caminhos_normais_sao_seguros(caminho):
    assert pub.caminho_seguro(caminho)


@pytest.mark.parametrize("caminho", ["", "/etc/passwd", "../x", "a/../b", "a//b", "./a", "a\\b", "a\0b"])
def test_caminhos_estranhos_sao_recusados(caminho):
    assert not pub.caminho_seguro(caminho)


@pytest.mark.parametrize("caminho", ["assistente/tokens.py", "assets/logo.png", "assistente/chat.py"])
def test_arquivos_comuns_nao_sao_proibidos(caminho):
    assert not pub.e_proibido(caminho)


# =============================================================
# O projeto real
# =============================================================


def test_projeto_real_envia_a_lista_esperada_sem_chaves():
    enviar = pub.escolher_arquivos_para_enviar(pub.listar_arquivos_do_git(RAIZ), RAIZ)
    for caminho in enviar:
        assert pub.e_do_app(caminho), caminho
    for essencial in pub.ESSENCIAIS:
        assert essencial in enviar
    assert "assets/logo.svg" in enviar and "assistente/interface.py" in enviar
    assert not any(
        c.startswith(("tests/", "scripts/", ".github/")) or c.endswith(".md") and c != "README.md" for c in enviar
    )
    pub.conferir_chaves(enviar, RAIZ)
    pub.conferir_config(RAIZ)
