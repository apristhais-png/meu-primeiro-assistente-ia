---
title: Professor de Dados
emoji: 📊
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 6.30.0
python_version: "3.11"
app_file: app.py
pinned: false
short_description: Aprenda Engenharia de Dados e IA de forma simples
---

# Meu primeiro assistente de IA

Um chat que ensina **Engenharia de Dados e IA** de forma simples, aberto para
qualquer pessoa pelo navegador.

> **Onde o app fica no ar:** no **Render** (plano gratuito). O Render usa o
> `render.yaml`, o `.python-version` (Python 3.11) e roda `python app.py`. Veja o
> `GUIA-publicacao.md`.
>
> **Sobre o bloco no topo deste arquivo (entre as linhas `---`):** é o cabeçalho
> do Hugging Face Spaces, onde o projeto seria publicado antes. O Render o
> ignora, mas ele foi mantido: o `sdk_version` precisa continuar **igual** à
> versão do Gradio no `requirements.txt`, e um teste automático
> (`tests/test_versoes.py`) confere isso. Para atualizar o Gradio, mude os dois
> juntos, no mesmo commit.

## O que ele faz

- Conversa usando IA, com **troca automática de provedor** (OpenRouter →
  Anthropic → OpenAI) quando um deles tem uma falha temporária.
- É personalizado **só pelo arquivo `config.yml`**: nome, logo, cores,
  instruções, modelos e limites de uso.
- Protege seus créditos com **limites de uso conferidos no servidor**.
- Tela pensada para qualquer aparelho (computador, tablet e celular): sugestões
  clicáveis na tela inicial, botão **Nova conversa**, aviso "Pensando..."
  enquanto a IA responde, código e tabelas legíveis e navegação completa pelo
  teclado, com foco bem visível.
- Não guarda nenhuma chave de API no código.

## Tutor adaptativo (nível e modo de estudo)

Acima da conversa há dois seletores:

| Seletor | Opções | O que muda na resposta |
|---|---|---|
| **Seu nível** | Iniciante · Intermediário · Avançado | Linguagem, tamanho dos exemplos e profundidade técnica. |
| **Modo de estudo** | Explicação · Exercício prático · Revisão | Explicação organizada; um exercício (Python, SQL ou Engenharia de Dados) com dica e critérios de verificação, **sem a solução**; ou um resumo com perguntas rápidas. |

- No modo **Exercício prático**, envie sua tentativa na conversa: o tutor diz o
  que está certo, explica os erros e orienta como melhorar. A solução completa
  só aparece se você pedir ou depois de duas tentativas sem sucesso.
- O nível e o modo entram nas **instruções enviadas à IA** a cada pergunta
  (arquivo `assistente/tutor.py`), junto com as `instrucoes` do `config.yml`.
  A tela e a API só mandam a opção escolhida; o texto das instruções vem do
  app, então ninguém consegue colocar instruções próprias por esse caminho.
- **Continuidade:** o exercício e as tentativas ficam no histórico desta
  conversa (as últimas `max_mensagens_historico` mensagens). Nada é guardado
  depois que a página é fechada ou a conversa é reiniciada; não há cadastro
  nem banco de dados.

## Brasil em Dados — Censo 2022 (Produto B: dashboard)

Um painel interativo para explorar a **população**, a **área** e a **densidade
demográfica** de todos os municípios do Brasil, com dados oficiais do IBGE.
Ele é **independente do chatbot**: roda separado, com outro comando, e o
Render continua publicando só o Professor de Dados.

```bash
streamlit run dashboard/app.py
```

### O que a tela mostra

- **Indicadores** da seleção: população total, quantidade de municípios,
  município mais populoso, população média (e mediana), densidade demográfica
  agregada (Σ população ÷ Σ área) e participação na população do Brasil.
  O **?** de cada cartão mostra a definição e a fórmula.
- **Filtros** (barra lateral, funcionam juntos): região, UF, município,
  quantidade de municípios no ranking e comparação por região ou por UF.
  Ao escolher uma região, a lista de UFs e de municípios passa a mostrar só
  os dela (escolhas que deixam de valer são retiradas sozinhas).
- **Gráficos Plotly**: ranking dos municípios mais populosos, população por
  região/UF e densidade por região/UF (com a densidade do Brasil como linha
  de referência). Todos têm os números também em tabela.
- **Tabela** com o código IBGE (identificador oficial) de cada município,
  números no padrão brasileiro e ordenação por coluna.
- **Download CSV** dos dados filtrados (separador `;` e vírgula decimal, abre
  direto no Excel em português).
- **Qualidade dos dados**: municípios recebidos, válidos e descartados,
  valores ausentes, unidades informadas pela API, conferência da densidade,
  data de referência e fonte.
- **Erros e estados vazios**: se o IBGE não responder, aparece uma mensagem
  simples com o botão **Tentar de novo** (sem detalhes técnicos na tela). Se
  nenhum município atender aos filtros, a tela avisa em vez de mostrar números.

### Como funciona o cache (por que é rápido)

1. **Na memória** (`st.cache_data`, 24 horas): mexer nos filtros não baixa
   nada de novo; só refaz contas sobre a tabela já carregada.
2. **Em disco** (`dados/ibge_4714_2022.json`, fora do Git): o primeiro download
   (~2 MB) é guardado. Reabrir o dashboard depois usa essa cópia, inclusive
   sem internet. Se ela estiver corrompida, é baixada de novo sozinha.
   Para forçar dados novos, apague o arquivo.

Erros **não** ficam no cache: depois de uma falha, a próxima tentativa
consulta o IBGE de novo.

### Estrutura

```text
pipeline/          → dados: requests → Pydantic → Pandas → indicadores
  fonte.py         → URL, tabela 4714, variáveis, UFs e regiões
  extracao.py      → GET com timeout, tentativas, cópia local
  validacao.py     → formato da API + relatório de qualidade
  transformacao.py → DataFrame, filtros, ranking, totais, CSV
  indicadores.py   → indicadores com definição, fórmula e unidade
dashboard/         → tela (não repete regras do pipeline)
  dados.py         → carrega a base, aplica os filtros, prepara as tabelas
  graficos.py      → gráficos Plotly
  app.py           → interface Streamlit
.streamlit/config.toml → cor e opções do Streamlit
scripts/conferir_dashboard.py → confere a tela com os dados reais (usado na CI)
```

### Tecnologias

| Biblioteca | Papel |
|---|---|
| Requests | Busca os dados na API do IBGE (GET, timeout, novas tentativas). |
| Pydantic | Confere se a resposta tem o formato esperado. |
| Pandas | Organiza a tabela, filtra, ordena e soma. |
| Streamlit | A tela interativa (filtros, cartões, tabela, download, cache). |
| Plotly | Os gráficos interativos. |
| pytest + pytest-cov | Testes com API simulada e cobertura mínima de 80%. |

### Como abrir

Depois de preparar o ambiente (veja **Ambiente de desenvolvimento no Windows 11**
mais abaixo):

```powershell
poetry run streamlit run dashboard/app.py
```

O navegador abre em http://localhost:8501 (para fechar: `Ctrl+C` no terminal).
O dashboard **não precisa de nenhuma chave**: a API do IBGE é pública.

### Origem dos dados e limitações

- **Fonte:** IBGE, Censo Demográfico 2022, [tabela 4714 do SIDRA](https://sidra.ibge.gov.br/tabela/4714),
  pela API de dados agregados v3. Data de referência: 31/07/2022.
- **Um único ano:** o Censo 2022 é uma fotografia. O painel **não** mostra
  tendências nem evolução no tempo, porque essa fonte não tem série histórica.
- Só três medidas por município (população, área e densidade). Não há renda,
  idade, sexo ou outros recortes nesta tabela.
- A densidade do IBGE vem arredondada; o painel confere se ela bate com
  população ÷ área (diferença de até 1%).
- A conferência com a API real roda no GitHub (workflow `api-ibge.yml`), que
  também guarda fotos da tela como artefato.

O pipeline também roda sozinho, sem tela: `python -m pipeline --csv dados/municipios.csv`.
Plano e auditoria: `docs/auditoria.md`.

## Ambiente de desenvolvimento no Windows 11

### Para que serve cada ferramenta

| Ferramenta | Para que serve neste projeto | Onde fica |
|---|---|---|
| **Python 3.11** | Versão usada em tudo: no seu computador, na CI e no Render (arquivo `.python-version`). | Seu computador |
| **pyenv / pyenv-win** | Instala e troca versões do Python sem mexer no Python do sistema. Opcional, mas evita "funciona aqui e não lá". | Seu computador |
| **pipx** | Instala programas de linha de comando (como o Poetry) cada um na sua caixinha isolada, fora do projeto. | Seu computador |
| **Poetry** | Cria o ambiente virtual do projeto e instala as versões exatas do `poetry.lock`. **Não** é dependência do app. | Seu computador e CI |
| **pytest + pytest-cov** | Testes automáticos (com IAs e API do IBGE simuladas) e a medida de cobertura. | Seu computador e CI |
| **Ruff** | Procura erros comuns e padroniza a formatação do código. Regras no `pyproject.toml`. | Seu computador e CI |

As versões das bibliotecas estão em dois formatos, sempre iguais (um teste confere):

| Arquivo | O que tem | Quem usa |
|---|---|---|
| `requirements.txt` | Chatbot (Gradio, OpenAI, Anthropic…) | **Render** (`pip install -r requirements.txt`) e CI |
| `requirements-dados.txt` | Pipeline e dashboard (Requests, Pandas, Streamlit, Plotly) | CI e quem não usa o Poetry |
| `requirements-dev.txt` | Testes e qualidade (pytest, pytest-cov, Ruff…) | CI e quem não usa o Poetry |
| `requirements-docs.txt` | Documentação (MkDocs e tema Material) | CI da documentação e quem não usa o Poetry |
| `pyproject.toml` + `poetry.lock` | Os quatro acima: principais = chatbot, grupos `dados`, `dev` e `docs` | Poetry (seu computador) |

### Instalação local × publicação no Render

- **No seu computador** você instala tudo (chatbot + dados + testes) com o
  Poetry, para desenvolver e testar.
- **No Render** nada disso muda: ele continua rodando
  `pip install -r requirements.txt` e `python app.py` (veja `render.yaml`).
  O Poetry, o Streamlit e o Plotly **não** são instalados lá.
- Para trocar a versão de uma biblioteca, mude o `requirements*.txt` **e** o
  `pyproject.toml`, rode `poetry lock` e depois `pytest tests/test_poetry.py`.

### Passo a passo (PowerShell)

Abra o **PowerShell** (não precisa ser como administrador).

**1. Python 3.11** — escolha **uma** opção:

- *Com pyenv-win* (recomendado se você usa outras versões do Python):

  ```powershell
  Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"; &"./install-pyenv-win.ps1"
  ```

  Feche e abra o PowerShell de novo. Depois:

  ```powershell
  pyenv install 3.11.9
  pyenv global 3.11.9
  python --version          # deve mostrar Python 3.11.9
  ```

  (3.11.9 é a última versão 3.11 com instalador oficial para Windows.)
- *Sem pyenv*: `winget install -e --id Python.Python.3.11` (ou o instalador
  do [python.org](https://www.python.org/downloads/windows/), marcando
  "Add python.exe to PATH"). Confira com `py -3.11 --version`.

Se o PowerShell bloquear scripts, rode uma vez:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

**2. pipx e Poetry** (uma vez por computador):

```powershell
py -3.11 -m pip install --user pipx
py -3.11 -m pipx ensurepath
```

Feche e abra o PowerShell de novo. Depois:

```powershell
pipx install poetry==2.5.1
poetry --version          # Poetry (version 2.5.1)
```

**3. Dependências do projeto** (na pasta do projeto):

```powershell
cd caminho\para\meu-primeiro-assistente-ia
poetry env use 3.11
poetry install --with dados,dev
```

Isso cria um ambiente virtual só deste projeto, com as versões exatas do
`poetry.lock`. Para instalar só o chatbot: `poetry install` (sem `--with`).

**4. Rodar o chatbot (Professor de Dados)**

```powershell
Copy-Item .env.example .env     # depois coloque pelo menos uma chave no .env
poetry run python app.py
```

Abra http://127.0.0.1:7860. Sem nenhuma chave, a tela abre, mas as perguntas
recebem uma mensagem amigável de erro. O `.env` nunca vai para o GitHub.

> No seu computador, o app escuta só em `127.0.0.1` (não fica visível para
> outras máquinas da rede). No Render, ele escuta em `0.0.0.0`, na porta da
> variável `PORT`, como o Render exige.

**5. Rodar o pipeline do IBGE** (precisa de internet; não precisa de chave):

```powershell
poetry run python -m pipeline --cache dados\ibge_4714_2022.json --csv dados\municipios.csv
```

**6. Rodar o dashboard**

```powershell
poetry run streamlit run dashboard/app.py
```

**7. Testes e cobertura**

```powershell
poetry run pytest                                            # todos os testes
poetry run pytest --cov=pipeline --cov=dashboard             # + cobertura (mínimo 80%)
poetry run pytest --cov=pipeline --cov=dashboard --cov-report=html
start htmlcov\index.html                                     # relatório no navegador
```

Os testes não usam internet nem chaves: as IAs e a API do IBGE são simuladas.

**8. Ruff (erros comuns e formatação)**

```powershell
poetry run ruff check .          # procura problemas
poetry run ruff format .         # formata o código
poetry run ruff format --check . # só confere (é o que a CI faz)
```

### Sem Poetry (alternativa com pip)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dados.txt -r requirements-dev.txt
python app.py                         # ou: streamlit run dashboard/app.py
```

### Linux e macOS

Os mesmos passos, com o [pyenv](https://github.com/pyenv/pyenv)
(`pyenv install 3.11`: o `.python-version` do projeto já escolhe o 3.11) e
o pipx do sistema (`python3 -m pip install --user pipx && python3 -m pipx ensurepath`).
Caminhos usam `/` em vez de `\`.

## Como publicar (Render)

1. O GitHub Actions testa cada Pull Request e cada push na `main`.
2. O Render publica a `main` sozinho, **só depois** que os testes passam
   (opção *After CI Checks Pass*).
3. As chaves de IA ficam na aba *Environment* do Render, nunca no repositório.

O passo a passo completo, incluindo os limites do plano gratuito (o serviço
dorme após 15 minutos sem acesso), está no `GUIA-publicacao.md`.

## Como personalizar

Edite o `config.yml` (cada campo tem um comentário explicando) e confira se
está tudo certo com:

```bash
python scripts/validar_config.py
```

## Como conferir se está tudo certo

```bash
pytest --cov=pipeline --cov=dashboard # testes automáticos + cobertura (sem IAs reais nem internet)
ruff check .                          # estilo e erros comuns
ruff format --check .                 # formatação
python scripts/validar_config.py      # configuração
python scripts/verificar_segredos.py  # chaves de API esquecidas nos arquivos
```

Com o Poetry, coloque `poetry run` antes de cada comando. A CI faz tudo isso
em cada Pull Request (`ci-deploy.yml`); o workflow `ambiente.yml` também
instala o projeto do zero com o Poetry e simula a instalação do Render.

## Onde ficam as chaves de API

| Chave | Onde configurar |
|---|---|
| `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | No seu computador: arquivo `.env`. No Render: aba *Environment* do serviço. |

**Nunca** coloque chaves no `config.yml`, no código ou em qualquer arquivo
enviado ao GitHub.

## Entrega final (validação, checklist e apresentação)

O relatório da validação final, com evidências, resultados dos testes,
cobertura, checklist dos requisitos, auditoria de segurança e roteiro de
apresentação, fica em [`docs/entrega-final/`](docs/entrega-final/index.md)
(também aparece no site da documentação, na aba **Entrega final**).

## Site de documentação (MkDocs Material)

A documentação completa, em português, fica na pasta `docs/` e vira um site
com o **MkDocs** e o tema **Material**: apresentação, arquitetura, ambiente
(pipx, Poetry, pyenv, Windows 11), API do IBGE, extração, validação,
transformação, dashboard, Professor de Dados, testes, cobertura, Ruff,
segurança, execução local, publicação e limitações.

```powershell
poetry install --with docs        # ou: pip install -r requirements-docs.txt
poetry run mkdocs serve           # abre em http://127.0.0.1:8000 e atualiza ao salvar
poetry run mkdocs build --strict  # gera a pasta site/ e falha se houver link quebrado
```

- Configuração: `mkdocs.yml`. As páginas são arquivos Markdown em `docs/`.
- **Site publicado (GitHub Pages):**
  <https://apristhais-png.github.io/meu-primeiro-assistente-ia/>
- Em todo Pull Request que mexe na documentação, o workflow `docs.yml` roda
  `mkdocs build --strict` (só confere, não publica).
- Depois do merge na `main`, o mesmo workflow constrói o site em modo estrito,
  publica no GitHub Pages e confere se o endereço público abre. Só a `main`
  publica; não há chaves nem tokens manuais. Detalhes em `docs/publicar.md`.
- Configuração única (dona do repositório): **Settings → Pages → Source:
  GitHub Actions**.
- O MkDocs não é instalado no Render e não muda nada no chatbot.

## Documentação do projeto

- `IDEIA-parte1.md`: a ideia original.
- `SPEC-parte1-cicd-deploy.md`: a especificação completa (o que o sistema deve
  fazer, testes, critérios de aceite e ordem de implementação).
- `GUIA-publicacao.md`: passo a passo para colocar o assistente no ar no
  Render (serviço, chaves, publicação só depois dos testes).
- `AUDITORIA-pre-publicacao.md`: resultado da auditoria antes da primeira
  publicação (critérios de aceite, segurança e limites).
- `scripts/publicar.py`: legado da época do Hugging Face. Foi mantido (e
  continua testado), mas **não** é usado na publicação pelo Render.
