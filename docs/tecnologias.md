# Tecnologias utilizadas

Todas as versões são **fixas** (`==`) nos arquivos `requirements*.txt` e no
`poetry.lock`: o que é testado é exatamente o que é instalado. Um teste
(`tests/test_poetry.py`) confere que os dois formatos dizem a mesma coisa.

## Linguagem e ambiente

| Ferramenta | Para que serve aqui |
|---|---|
| **Python 3.11** | Versão única do projeto: no computador, na CI e no Render (arquivo `.python-version`). |
| **pyenv / pyenv-win** | Instalar e escolher a versão do Python sem mexer no Python do sistema. |
| **pipx** | Instalar programas de linha de comando (como o Poetry) isolados do projeto. |
| **Poetry** | Criar o ambiente virtual e instalar as versões exatas do `poetry.lock`. |
| **python-dotenv** | Ler as chaves de IA do arquivo `.env` no seu computador. |

## Produto A — chatbot

| Biblioteca | Papel |
|---|---|
| **Gradio** | A tela do chat (ChatInterface), com seletores de nível e de modo de estudo. |
| **openai** | Cliente usado para o OpenRouter e para a OpenAI (mesma API). |
| **anthropic** | Cliente da Anthropic (Claude), usado como reserva. |
| **Pydantic** | Confere se o `config.yml` está correto antes de o app abrir. |
| **PyYAML** | Lê o `config.yml`. |
| **tzdata** | Fuso horário de Brasília para zerar os limites diários à meia-noite. |

## Produto B — dados e dashboard

| Biblioteca | Papel |
|---|---|
| **Requests** | Busca os dados na API do IBGE (GET com tempo limite e novas tentativas). |
| **Pydantic** | Confere o formato da resposta da API e cada município. |
| **Pandas** | Organiza a tabela, filtra, ordena, soma e exporta CSV. |
| **Streamlit** | A tela interativa do dashboard (filtros, cartões, tabela, download, cache). |
| **Plotly** | Os gráficos interativos. |

## Qualidade e documentação

| Ferramenta | Papel |
|---|---|
| **pytest** | Testes automáticos (com IAs e API do IBGE simuladas). |
| **pytest-cov** | Mede quanto do código os testes exercitam (mínimo de 80% em dados e dashboard). |
| **Ruff** | Encontra erros comuns e padroniza a formatação. |
| **GitHub Actions** | Roda tudo isso a cada Pull Request. |
| **MkDocs + Material** | Este site de documentação. |

## Onde cada biblioteca é declarada

| Arquivo | Conteúdo | Quem instala |
|---|---|---|
| `requirements.txt` | Chatbot | **Render** e CI |
| `requirements-dados.txt` | Pipeline e dashboard | CI e computador |
| `requirements-dev.txt` | Testes e Ruff | CI e computador |
| `requirements-docs.txt` | MkDocs e tema Material | CI da documentação e computador |
| `pyproject.toml` + `poetry.lock` | Tudo acima (principais + grupos `dados`, `dev`, `docs`) | Poetry |
