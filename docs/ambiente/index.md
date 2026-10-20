# Configuração do ambiente

O projeto usa **Python 3.11** em todos os lugares. Para que o resultado seja o
mesmo no seu computador, na CI e no Render, as versões das bibliotecas são
fixas e há duas formas de instalar: **Poetry** (recomendada no computador) ou
**pip** com os arquivos `requirements*.txt` (usada pelo Render e pela CI).

## Para que serve cada ferramenta

| Ferramenta | Para que serve | Onde é usada |
|---|---|---|
| **Python 3.11** | Versão do projeto (`.python-version`). | Computador, CI e Render |
| **pyenv / pyenv-win** | Instala e troca versões do Python sem mexer no Python do sistema. Opcional. | Computador |
| **pipx** | Instala o Poetry numa "caixinha" própria, fora do projeto. | Computador e CI |
| **Poetry** | Cria o ambiente virtual do projeto e instala as versões do `poetry.lock`. **Não** é dependência do app. | Computador e CI |

## Como as dependências estão organizadas

| Arquivo pip | Grupo no Poetry | O que tem |
|---|---|---|
| `requirements.txt` | dependências principais | Chatbot (Gradio, openai, anthropic, Pydantic…) |
| `requirements-dados.txt` | grupo opcional `dados` | Requests, Pandas, Streamlit, Plotly |
| `requirements-dev.txt` | grupo opcional `dev` | pytest, pytest-cov, Ruff… |
| `requirements-docs.txt` | grupo opcional `docs` | MkDocs e tema Material |

```bash
poetry install                          # só o chatbot (o mesmo conjunto do Render)
poetry install --with dados,dev         # chatbot + pipeline + dashboard + testes
poetry install --with dados,dev,docs    # tudo, inclusive esta documentação
```

## Instalação local × publicação no Render

| | No seu computador | No Render |
|---|---|---|
| Como instala | Poetry (`poetry install --with ...`) ou pip | `pip install -r requirements.txt` (veja `render.yaml`) |
| O que instala | O que você escolher: chatbot, dados, testes, docs | **Só o chatbot** |
| Chaves de IA | Arquivo `.env` (nunca vai para o GitHub) | Aba *Environment* do serviço |
| Endereço | `127.0.0.1` (só o seu computador) | `0.0.0.0` na porta `PORT` |

O Poetry, o Streamlit, o Plotly e o MkDocs **nunca** são instalados no Render.

## Mudando uma versão

1. Altere a linha no `requirements*.txt` **e** no `pyproject.toml`.
2. Rode `poetry lock`.
3. Rode `pytest tests/test_poetry.py tests/test_versoes.py`: eles falham se
   os dois lados ficarem diferentes.

Próximas páginas: [pipx, Poetry e pyenv](instalacao.md) ·
[Windows 11 passo a passo](windows.md).
