# Instalação com pipx, Poetry e pyenv

Esta página explica **o que** cada ferramenta faz. Os comandos exatos para o
Windows estão em [Windows 11 passo a passo](windows.md).

## 1. pyenv — a versão certa do Python

O pyenv instala várias versões do Python lado a lado e escolhe qual usar em
cada pasta. O projeto tem um arquivo `.python-version` com `3.11`.

=== "Linux e macOS (pyenv)"

    ```bash
    pyenv install 3.11      # instala a versão 3.11 mais recente
    cd meu-primeiro-assistente-ia
    python --version        # Python 3.11.x (o .python-version escolhe sozinho)
    ```

=== "Windows (pyenv-win)"

    ```powershell
    pyenv install 3.11.9    # última 3.11 com instalador oficial para Windows
    pyenv global 3.11.9
    python --version        # Python 3.11.9
    ```

O pyenv é **opcional**: se o Python 3.11 já estiver instalado (por exemplo,
pelo `winget` ou pelo site python.org), pode pular este passo.

## 2. pipx — programas isolados

O pipx instala programas de linha de comando, cada um no seu próprio ambiente.
Assim, o Poetry não se mistura com as bibliotecas do projeto.

```bash
python -m pip install --user pipx
python -m pipx ensurepath     # depois, feche e abra o terminal
```

## 3. Poetry — o ambiente do projeto

```bash
pipx install poetry==2.5.1
poetry --version
```

Na pasta do projeto:

```bash
poetry env use 3.11
poetry install --with dados,dev
poetry run pytest
```

- `poetry install` lê o `pyproject.toml` e instala as versões **exatas** do
  `poetry.lock`.
- `poetry run <comando>` executa o comando dentro do ambiente do projeto.
- `package-mode = false`: o Poetry só cuida das dependências; o projeto não é
  empacotado como biblioteca.

## Alternativa sem Poetry (pip)

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dados.txt -r requirements-dev.txt
```

É assim que a CI instala. O resultado é o mesmo, porque as versões são iguais
nos dois formatos.
