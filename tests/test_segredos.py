"""Testes do verificador de chaves vazadas (SPEC, teste T8).

As chaves usadas aqui são FALSAS e montadas durante o teste, para que o
próprio repositório nunca contenha algo parecido com uma chave.
"""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import verificar_segredos as vs

# ---------- Chaves falsas, montadas em tempo de execução ----------

def chave_falsa_openrouter() -> str:
    return "sk-or-v1-" + "a1" * 32


def chave_falsa_anthropic() -> str:
    return "sk-ant-" + "api03-" + "Ab1" * 30


def chave_falsa_openai() -> str:
    return "sk-" + "proj-" + "Zq9" * 16


def chave_falsa_hugging_face() -> str:
    return "hf_" + "Qw3" * 12


def chave_falsa_github() -> str:
    return "ghp_" + "Rt5" * 13


def criar_repositorio(pasta: Path, arquivos: dict[str, str]) -> None:
    """Cria um repositório Git temporário e adiciona os arquivos (sem commit)."""
    subprocess.run(["git", "init", "-q"], cwd=pasta, check=True)
    for nome, conteudo in arquivos.items():
        caminho = pasta / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(conteudo, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=pasta, check=True)


# ---------- Detecta chaves no formato completo ----------

def test_detecta_chave_de_cada_servico():
    casos = {
        "OpenRouter": chave_falsa_openrouter(),
        "Anthropic": chave_falsa_anthropic(),
        "OpenAI": chave_falsa_openai(),
        "Hugging Face": chave_falsa_hugging_face(),
        "GitHub": chave_falsa_github(),
    }
    for servico, chave in casos.items():
        achados = vs.procurar_no_texto(f'API_KEY = "{chave}"')
        assert [a.servico for a in achados] == [servico], servico


def test_cada_chave_e_contada_uma_vez_so():
    # Uma chave do OpenRouter também começa com "sk-", mas não pode
    # ser acusada de novo como se fosse da OpenAI.
    texto = chave_falsa_openrouter() + " " + chave_falsa_anthropic()
    servicos = sorted(a.servico for a in vs.procurar_no_texto(texto))
    assert servicos == ["Anthropic", "OpenRouter"]


def test_detecta_chave_em_arquivo_py_e_md(tmp_path):
    criar_repositorio(
        tmp_path,
        {
            "app.py": f'chave = "{chave_falsa_openrouter()}"\n',
            "docs/guia.md": f"# Guia\n\nMinha chave: {chave_falsa_hugging_face()}\n",
        },
    )
    achados, _ = vs.verificar(tmp_path)
    encontrados = sorted((a.arquivo, a.linha) for a in achados)
    assert encontrados == [("app.py", 1), ("docs/guia.md", 3)]


def test_main_falha_quando_ha_chave(tmp_path, capsys):
    criar_repositorio(tmp_path, {"config.yml": f"chave: {chave_falsa_openai()}\n"})
    assert vs.main(tmp_path) == 1
    saida = capsys.readouterr().out
    assert "config.yml, linha 1" in saida


# ---------- Não dá falso alarme ----------

def test_prefixos_sozinhos_nao_sao_acusados():
    texto = "Exemplos de prefixos: sk-, sk-ant-, hf_, ghp_ e sk-or-v1-..."
    assert vs.procurar_no_texto(texto) == []


def test_chaves_curtas_demais_nao_sao_acusadas():
    texto = "sk-abc123 hf_abc123 sk-or-v1-abc123"
    assert vs.procurar_no_texto(texto) == []


def test_valores_de_exemplo_nao_sao_acusados():
    textos = [
        "OPENROUTER_API_KEY=SUA_CHAVE_AQUI",
        "sk-proj-" + "x" * 48,
        "sk-" + "EXEMPLO" * 8,
        "hf_" + "EXAMPLE" * 5,
    ]
    for texto in textos:
        assert vs.procurar_no_texto(texto) == [], texto


def test_palavras_comuns_nao_sao_acusadas():
    # "task-" e "disk-" terminam em "sk-", mas não são chaves.
    texto = "task-" + "a" * 50 + " disk-" + "b" * 50
    assert vs.procurar_no_texto(texto) == []


def test_arquivo_binario_e_ignorado(tmp_path):
    criar_repositorio(tmp_path, {"leia.md": "nada aqui\n"})
    imagem = tmp_path / "logo.png"
    imagem.write_bytes(b"\x89PNG\0\0" + chave_falsa_openrouter().encode())
    subprocess.run(["git", "add", "logo.png"], cwd=tmp_path, check=True)
    achados, lidos = vs.verificar(tmp_path)
    assert achados == []
    assert lidos == 1


def test_arquivo_fora_do_git_e_ignorado(tmp_path):
    # Um .env local (ignorado pelo Git) não deve ser lido nem acusado.
    criar_repositorio(tmp_path, {".gitignore": ".env\n"})
    (tmp_path / ".env").write_text(f"OPENAI_API_KEY={chave_falsa_openai()}\n")
    achados, _ = vs.verificar(tmp_path)
    assert achados == []


# ---------- O alerta nunca mostra a chave inteira ----------

def test_alerta_esconde_a_chave(tmp_path, capsys):
    chave = chave_falsa_anthropic()
    criar_repositorio(tmp_path, {"notas.md": chave + "\n"})
    vs.main(tmp_path)
    saida = capsys.readouterr().out
    assert chave not in saida
    assert chave[: vs.CARACTERES_VISIVEIS] in saida
    assert chave[vs.CARACTERES_VISIVEIS : vs.CARACTERES_VISIVEIS + 10] not in saida


# ---------- O repositório real está limpo ----------

def test_repositorio_real_nao_tem_chaves(capsys):
    assert vs.main(RAIZ) == 0
    assert "[OK]" in capsys.readouterr().out
