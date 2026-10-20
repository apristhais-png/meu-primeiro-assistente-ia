# Windows 11 passo a passo

Todos os comandos são para o **PowerShell** (não precisa ser como
administrador). Faça os passos 1 e 2 uma vez por computador.

!!! tip "Se o PowerShell bloquear scripts"
    Rode uma vez: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 1. Python 3.11

Escolha **uma** opção.

=== "Com pyenv-win (recomendado)"

    ```powershell
    Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"; &"./install-pyenv-win.ps1"
    ```

    Feche e abra o PowerShell. Depois:

    ```powershell
    pyenv install 3.11.9
    pyenv global 3.11.9
    python --version          # Python 3.11.9
    ```

    A 3.11.9 é a última versão 3.11 com instalador oficial para Windows.

=== "Sem pyenv (winget)"

    ```powershell
    winget install -e --id Python.Python.3.11
    py -3.11 --version
    ```

    Ou baixe o instalador no [python.org](https://www.python.org/downloads/windows/)
    e marque **"Add python.exe to PATH"**.

## 2. pipx e Poetry

```powershell
py -3.11 -m pip install --user pipx
py -3.11 -m pipx ensurepath
```

Feche e abra o PowerShell. Depois:

```powershell
pipx install poetry==2.5.1
poetry --version          # Poetry (version 2.5.1)
```

## 3. Baixar o projeto e instalar as dependências

```powershell
git clone https://github.com/apristhais-png/meu-primeiro-assistente-ia.git
cd meu-primeiro-assistente-ia
poetry env use 3.11
poetry install --with dados,dev
```

## 4. Usar

| O que | Comando |
|---|---|
| Chatbot | `Copy-Item .env.example .env` (coloque uma chave) e `poetry run python app.py` |
| Pipeline | `poetry run python -m pipeline --cache dados\ibge_4714_2022.json --csv dados\municipios.csv` |
| Dashboard | `poetry run streamlit run dashboard/app.py` |
| Testes | `poetry run pytest` |
| Cobertura em HTML | `poetry run pytest --cov=pipeline --cov=dashboard --cov-report=html` e `start htmlcov\index.html` |
| Ruff | `poetry run ruff check .` e `poetry run ruff format .` |
| Esta documentação | `poetry install --with docs` e `poetry run mkdocs serve` |

Detalhes de cada um em [Como executar localmente](../executar.md).

## Sem Poetry

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dados.txt -r requirements-dev.txt
python app.py
```

!!! note "O que foi validado"
    Estes comandos seguem a documentação oficial do pyenv-win, do pipx e do
    Poetry. A instalação completa foi conferida em Linux (no computador de
    desenvolvimento e no GitHub Actions); o `poetry.lock` foi resolvido para
    todas as plataformas, inclusive Windows.
