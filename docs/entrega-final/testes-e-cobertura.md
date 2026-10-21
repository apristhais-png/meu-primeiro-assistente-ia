# Testes e cobertura

Executado em **21/10/2026**, num clone limpo da `main` (`7c76658`), com
Python 3.11.17, sem nenhuma chave de IA e sem acesso à internet para os
testes.

```bash
pytest -rs --cov=pipeline --cov=dashboard --cov-report=term-missing --cov-fail-under=80
```

```text
TOTAL                         595     10    98%
Required test coverage of 80% reached. Total coverage: 98.32%
690 passed, 72 warnings in 144.80s
```

O mesmo resultado (**690 passaram, 98,32%**) saiu da instalação com Poetry.
Log completo: [`logs/pytest.txt`](logs/pytest.txt) e
[`logs/poetry.txt`](logs/poetry.txt).

## Testes por arquivo

| Arquivo | Testes | Assunto |
|---|---:|---|
| `test_chat.py` | 29 | Uma pergunta do começo ao fim |
| `test_conferir_modelos.py` | 18 | Script que confere os modelos no catálogo |
| `test_confiabilidade.py` | 32 | Prazos, cancelamento, concorrência |
| `test_config.py` | 71 | `config.yml` |
| `test_cores.py` | 31 | Contraste das cores |
| `test_dashboard.py` | 36 | Dados, filtros, gráficos, CSV, erros, tela (`AppTest`) |
| `test_docs.py` | 30 | Site de documentação e os 21 temas |
| `test_interface.py` | 40 | Tela do Gradio |
| `test_limites.py` | 36 | Limites de uso |
| `test_modelos_gratuitos.py` | 54 | Catálogo, preço zero, quarentena |
| `test_pipeline.py` | 75 | Extração, validação, transformação, indicadores |
| `test_poetry.py` | 14 | Poetry × requirements |
| `test_provedores.py` | 68 | Provedores e fallback |
| `test_publicar.py` | 62 | Script legado do Hugging Face |
| `test_render.py` | 19 | `render.yaml` |
| `test_segredos.py` | 12 | Verificador de chaves |
| `test_tutor.py` | 33 | Níveis e modos do tutor |
| `test_versoes.py` | 10 | Versões fixas |
| `test_workflow.py` | 20 | GitHub Actions |
| **Total** | **690** | |

## Cobertura exigida: pipeline e dashboard (mínimo 80%)

| Módulo | Linhas | Não executadas | Cobertura |
|---|---:|---:|---:|
| `dashboard/app.py` | 93 | 4 | 96% |
| `dashboard/dados.py` | 124 | 0 | 100% |
| `dashboard/graficos.py` | 33 | 0 | 100% |
| `pipeline/__main__.py` | 3 | 3 | 0% |
| `pipeline/executar.py` | 47 | 1 | 98% |
| `pipeline/extracao.py` | 62 | 0 | 100% |
| `pipeline/fonte.py` | 22 | 0 | 100% |
| `pipeline/indicadores.py` | 35 | 0 | 100% |
| `pipeline/transformacao.py` | 34 | 0 | 100% |
| `pipeline/validacao.py` | 142 | 2 | 99% |
| **Total** | **595** | **10** | **98,32%** |

O `pipeline/__main__.py` tem só 3 linhas, que chamam `main()` (esta função
é testada, com 98% de cobertura). Ele não é chamado pelo pytest, mas foi
executado de verdade com `python -m pipeline`: no GitHub, com a API real
(`logs/ci-api-ibge-pipeline.txt`), e aqui, sem internet
(`logs/pipeline-sem-internet.txt`).

## Cobertura do projeto inteiro (informativa)

```bash
pytest --cov=assistente --cov=pipeline --cov=dashboard --cov=scripts
```

| Pasta | Cobertura |
|---|---|
| `assistente/` (chatbot) | 96% a 100% por arquivo |
| `pipeline/` e `dashboard/` | 98% |
| `scripts/` | varia: os scripts de conferência rodam na CI ou com chave real, fora do pytest |
| **Total** | **92%** (2.131 linhas) |

Log: [`logs/cobertura-projeto.txt`](logs/cobertura-projeto.txt).

## Regras que os testes seguem

- Nenhuma IA real é chamada e nenhuma chave é usada.
- A rede é bloqueada nos testes do pipeline e do dashboard; a API do IBGE é
  simulada com municípios **fictícios** identificados como tal.
- A conferência com a API **real** fica no workflow `api-ibge.yml` (ver
  [Evidências](evidencias.md)).
