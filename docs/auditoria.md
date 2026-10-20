# Auditoria do repositório e plano (Entrega 1)

Data: 20/10/2026 · Base: `main` em `3571166` (merge do PR #7).

## Estado verificado da `main`

| Verificação | Resultado |
|---|---|
| Chatbot preservado | Sim: `app.py` + `assistente/` (chat, interface, tutor, limites, provedores, modelos gratuitos). |
| Testes existentes | **529 passaram** (Python 3.11, sem rede, IAs simuladas). |
| Ruff / `validar_config.py` / `verificar_segredos.py` | Sem problemas. |
| CI (`.github/workflows/ci-deploy.yml`) | Um job `testar`, só leitura, sem segredos; verde no último PR (#7). |
| Render (`render.yaml`) | Instala só o `requirements.txt` e roda `python app.py`. Publica a `main` depois que a CI passa. |
| Dependências | Todas fixadas com `==` em `requirements*.txt`. `pip check` sem conflitos. `pyproject.toml` só configura o pytest. |
| Pronto para o dashboard | Sim, se as bibliotecas novas **não** entrarem no `requirements.txt` (que é do Render e do chatbot). |

## Requisitos da aula

Legenda: ✅ atendido · 🟡 parcialmente atendido · ❌ não atendido (situação **antes** desta entrega).

| Requisito | Situação atual | Evidência no repositório | O que será implementado |
|---|---|---|---|
| Python 3.11 | ✅ | `.python-version`, CI e Render em 3.11 | Manter. |
| pyenv | 🟡 | `.python-version` já existe; nada documentado | Documentar `pyenv` / `pyenv-win` (Entrega 4). |
| pipx | ❌ | — | Documentar a instalação do Poetry via pipx (Entrega 4). |
| Poetry | ❌ | `pyproject.toml` só tem configuração do pytest | Grupos de dependências + `poetry.lock`, sem mudar o Render (Entrega 4). |
| Requests | ❌ | — | `pipeline/extracao.py` (**esta entrega**). |
| Pydantic | 🟡 | Usado na configuração do chatbot | Modelos da API do IBGE em `pipeline/validacao.py` (**esta entrega**). |
| Pandas | ❌ (instalado só como dependência do Gradio) | — | `pipeline/transformacao.py` e `pipeline/indicadores.py` (**esta entrega**). |
| Streamlit | ❌ | — | `dashboard/` (Entrega 3). |
| Plotly | ❌ | — | Gráficos do dashboard (Entrega 3). |
| python-dotenv | ✅ | `app.py` lê o `.env` | Manter (o pipeline não precisa de chave). |
| pytest | ✅ | 15 arquivos de teste | Testes do pipeline (**esta entrega**). |
| pytest-cov | ❌ | — | Cobertura do pipeline na CI, mínimo 80% (**esta entrega**). |
| Ruff | 🟡 | `ruff check .` na CI; sem configuração nem formatação | `[tool.ruff]` e `ruff format` (Entrega 4). |
| MkDocs Material | ❌ | Documentação em `.md` soltos na raiz | Site em `docs/` + `mkdocs.yml` (Entrega 5). |
| GitHub Actions | ✅ | `ci-deploy.yml` | Ampliado com pipeline e cobertura (**esta entrega**); docs (Entrega 5). |

## Riscos e como foram evitados

| Risco | Cuidado |
|---|---|
| Quebrar o deploy do chatbot no Render | As bibliotecas do pipeline/dashboard ficam em `requirements-dados.txt`, que o Render **não** instala. |
| Um produto derrubar o outro | `pipeline/` não importa `assistente/` (há um teste que confere) e o `app.py` não importa `pipeline/`. |
| CI depender da internet | Os testes usam uma API simulada. A chamada real ao IBGE roda num workflow separado, só em PRs do pipeline, fora do "After CI Checks Pass". |
| Versões divergentes entre arquivos | Teste novo: a mesma biblioteca precisa ter a mesma versão em todos os `requirements*.txt`. |
| Dados inventados | Fonte oficial única (IBGE, Censo 2022), sem séries temporais. Os testes usam municípios **fictícios** e identificados como tal. |

## Plano de entregas

1. **Auditoria e arquitetura**: este documento.
2. **Pipeline de dados**: `pipeline/` (requests → Pydantic → Pandas → indicadores), testes e cobertura. *(Este PR.)*
3. **Dashboard**: `dashboard/` com Streamlit + Plotly, usando o `pipeline/`.
4. **Ambiente e qualidade**: Poetry (via pipx), pyenv, configuração do Ruff.
5. **Documentação**: MkDocs Material (+ GitHub Pages, se autorizado).
6. **Validação final**: checklist completo.

## Arquitetura

```text
app.py, assistente/     → Produto A: Professor de Dados (Gradio, Render)
pipeline/               → Produto B: dados do IBGE
  fonte.py              → onde estão os dados (URL, tabela, variáveis, UFs)
  extracao.py           → requests: GET com timeout, status, JSON, cache
  validacao.py          → Pydantic: formato da API → registros normalizados
  transformacao.py      → Pandas: DataFrame, filtros, agregações, CSV
  indicadores.py        → indicadores com definição, fórmula, unidade e fonte
  executar.py           → python -m pipeline (roda tudo e mostra o resumo)
dashboard/              → (Entrega 3) só tela: chama o pipeline, desenha gráficos
```

## Fonte de dados escolhida

API de dados agregados do IBGE (v3): **tabela 4714 do Censo 2022** (população residente, área territorial e densidade demográfica), todos os municípios (nível N6).

| Critério | Situação |
|---|---|
| Fonte oficial e sem chave | Sim. |
| Ano de referência | 2022 (um único ano: por isso o projeto não mostra tendências). |
| Identificador dos municípios | Código IBGE de 7 dígitos. |
| Comparações úteis | Municípios, UFs e regiões, por população, área e densidade. |

**Validação real ainda pendente:** este ambiente de desenvolvimento não alcança o site do IBGE, por isso o formato da resposta foi implementado a partir da documentação. O workflow `api-ibge.yml` roda o pipeline contra a API real no PR. É ele que confirma (ou não) o formato e os números.

Fontes: [tabela 4714 no SIDRA](https://sidra.ibge.gov.br/tabela/4714) · [documentação da API de agregados](https://servicodados.ibge.gov.br/api/docs/agregados?versao=3).
