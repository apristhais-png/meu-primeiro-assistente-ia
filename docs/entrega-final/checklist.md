# Checklist dos requisitos

Legenda: ✅ atendido e verificado na prática · ⚠️ atendido com ressalva
(explicada na linha). Os logs citados estão em
[`docs/entrega-final/logs/`](https://github.com/apristhais-png/meu-primeiro-assistente-ia/tree/main/docs/entrega-final/logs).

## Ferramentas obrigatórias

| Requisito | Situação | Onde está | Evidência |
|---|---|---|---|
| **Python 3.11** | ✅ | `.python-version`, `pyproject.toml` (`>=3.11,<3.12`), CI e Render | `pyenv.txt`, `poetry.txt` (Python 3.11.17) |
| **pyenv** | ✅ | README e [Windows 11](../ambiente/windows.md) (pyenv-win) | `pyenv.txt`: pyenv 2.8.10 leu o `.python-version` e escolheu 3.11.17 |
| **pipx** | ✅ | README, [instalação](../ambiente/instalacao.md), workflow `ambiente.yml` | `poetry.txt`: pipx 1.18.4 instalou o Poetry isolado |
| **Poetry** | ✅ | `pyproject.toml` (grupos `dados`, `dev`, `docs`) + `poetry.lock` | `poetry.txt`: `check --lock` ok, 98 pacotes do zero, 690 testes |
| **Requests** | ✅ | `pipeline/extracao.py` | `ci-api-ibge-pipeline.txt`: `ibge_get status=200` |
| **Pydantic** | ✅ | `pipeline/validacao.py`, `assistente/config.py` | 5.570 de 5.570 válidos; `config.txt` |
| **Pandas** | ✅ | `pipeline/transformacao.py`, `indicadores.py` | indicadores e totais por região em `ci-api-ibge-pipeline.txt` |
| **Streamlit** | ✅ | `dashboard/app.py` | `dashboard-saude.txt` (ok) e dashboard com dados reais no GitHub |
| **Plotly** | ✅ | `dashboard/graficos.py` | "gráficos: 3" com dados reais |
| **python-dotenv** | ✅ | `app.py` lê o `.env`; `.env.example` sem valores reais | `seguranca.txt` |
| **pytest** | ✅ | `tests/` (19 arquivos) | `pytest.txt`: 690 passaram |
| **pytest-cov** | ✅ | `[tool.coverage]` no `pyproject.toml`; mínimo 80% na CI | 98,32% (pipeline + dashboard) |
| **Ruff** | ✅ | `[tool.ruff]` no `pyproject.toml`; `check` e `format --check` na CI | `ruff.txt` |
| **MkDocs Material** | ✅ | `mkdocs.yml` + `docs/` | `mkdocs.txt`: build estrito sem avisos |
| **GitHub Actions** | ✅ | `ci-deploy.yml`, `api-ibge.yml`, `ambiente.yml`, `docs.yml` | execuções verdes listadas em [Evidências](evidencias.md) |
| **GitHub** | ✅ | todo o código, a documentação e esta entrega no mesmo repositório; uma branch e um PR por entrega | PRs #1 a #11 |

## Critérios de aceitação do projeto

| Critério | Situação | Como foi verificado |
|---|---|---|
| Clonar o repositório | ✅ | Clone limpo da `main` (`7c76658`) |
| Configurar o Python | ✅ | pyenv + `.python-version`; Python 3.11.17 |
| Instalar as dependências | ✅ | pip, Poetry e Render: `pip check` sem conflitos nos três |
| Executar o chatbot | ✅ | `python app.py` respondeu HTTP 200; pergunta enviada pelo navegador |
| Executar o pipeline de dados | ✅ | `python -m pipeline` com a API real no GitHub; sem internet, mensagem de erro clara e código 1 |
| Executar o dashboard | ✅ | `streamlit run dashboard/app.py`: saúde ok; dados reais no GitHub |
| Consultar uma API real | ✅ | IBGE, HTTP 200, 2.084.216 bytes (GitHub, 21/10/2026) |
| Validar dados com Pydantic | ✅ | 5.570 de 5.570 válidos, relatório de qualidade |
| Transformar dados com Pandas | ✅ | DataFrame, filtros, ranking, totais, CSV |
| Visualizar gráficos com Plotly | ✅ | 3 gráficos com dados reais |
| Filtrar dados pelo Streamlit | ✅ | Filtro Sudeste + SP = 645 municípios (dados reais) e testes `AppTest` |
| Exportar CSV | ✅ | `dados/municipios.csv` gerado no GitHub; botão de download na tela |
| Executar os testes pytest | ✅ | 690 passaram |
| Gerar relatório pytest-cov | ✅ | terminal e HTML (`--cov-report=html`) |
| Executar Ruff | ✅ | sem problemas |
| Construir a documentação MkDocs | ✅ | `mkdocs build --strict` sem avisos |
| Consultar o código e a documentação no GitHub | ✅ | repositório e `docs/` |
| Manter o Professor de Dados publicado no Render | ⚠️ | Configuração intacta e CI da `main` verde (condição para publicar). O serviço em si não pôde ser aberto deste ambiente: **conferir no link do Render** |
| Execução reproduzível no Windows | ⚠️ | Passo a passo documentado e `poetry.lock` para todas as plataformas; não executado num Windows |

## Segurança

| Requisito | Situação | Evidência |
|---|---|---|
| Nunca versionar o `.env` real | ✅ | 0 commits tocaram `.env` no histórico; `.gitignore` o ignora |
| Nunca inserir chaves no código, testes ou docs | ✅ | 0 chaves nos arquivos atuais (92) e nos 52 commits |
| Não exibir segredos nos logs | ✅ | Logs só com dados técnicos; erros dos provedores não são repassados |
| `.env.example` sem valores confidenciais | ✅ | só `SUA_CHAVE_AQUI` |
| Usar variáveis de ambiente | ✅ | `.env` local; aba *Environment* no Render (`sync: false`) |
| Não usar serviços pagos / não trocar para modelo pago | ✅ | só modelos `:free`, catálogo com preço zero, `max_price = 0` |
| Não desativar proteções existentes | ✅ | limites, prazos e quarentena mantidos (testes) |
| Não executar código do usuário no chatbot | ✅ | sem `eval`/`exec`/`subprocess`/upload no chatbot |
| Não expor arquivos do servidor | ✅ | o chat só troca texto; `show_error=False` |
| Dependências sem vulnerabilidades conhecidas | ⚠️ | Pillow 12.3.0 (indireta): sem correção compatível; não explorável pelos produtos — ver [auditoria](auditoria-seguranca.md) |

## Organização do trabalho

| Requisito | Situação |
|---|---|
| Não criar outros repositórios | ✅ |
| Não substituir o projeto nem apagar código funcional | ✅ (o chatbot foi preservado e evoluiu) |
| Não perder o histórico de commits | ✅ (52 commits, nenhum reescrito na `main`) |
| Não modificar a `main` diretamente; uma branch e um PR por entrega | ✅ |
| Merge só com autorização | ✅ (todos os merges feitos pela dona do projeto) |
| Workflows de docs e dashboard não disparam deploy do chatbot | ✅ (rodam só em PR ou manualmente) |
| CI sem depender de serviços externos | ✅ (`testar` usa simulações; a API real fica no `api-ibge.yml`) |
