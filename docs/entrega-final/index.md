# Relatório final do projeto

**Projeto:** Professor de Dados + Brasil em Dados (Censo 2022)  
**Repositório:** [apristhais-png/meu-primeiro-assistente-ia](https://github.com/apristhais-png/meu-primeiro-assistente-ia)  
**Versão validada:** `main` no commit `7c76658` (merge do PR #11)  
**Data da validação:** 21/10/2026

Este relatório reúne a **validação final feita na prática**: o projeto foi
clonado do zero, instalado de três formas diferentes e executado, e as
partes que dependem da internet foram conferidas no GitHub Actions com a API
real do IBGE. Cada resultado tem a sua evidência (log ou foto) nesta pasta.

| Página | Conteúdo |
|---|---|
| [Checklist dos requisitos](checklist.md) | Cada requisito da aula, o que foi feito e a evidência |
| [Testes e cobertura](testes-e-cobertura.md) | Números dos testes e da cobertura, arquivo por arquivo |
| [Auditoria de segurança](auditoria-seguranca.md) | Chaves, histórico do Git, workflows, código e vulnerabilidades |
| [Evidências](evidencias.md) | Comandos executados, saídas, fotos e links das execuções no GitHub |
| [Roteiro de apresentação](roteiro-apresentacao.md) | Roteiro de 5 a 10 minutos |

## 1. Resumo do que foi construído

| Produto | O que é | Tecnologias principais |
|---|---|---|
| **A — Professor de Dados** | Chat que ensina Engenharia de Dados e IA, com tutor por nível e modo de estudo, publicado no Render | Gradio, OpenRouter (modelos gratuitos), Pydantic, python-dotenv |
| **B — Brasil em Dados** | Pipeline do Censo 2022 do IBGE e dashboard interativo | Requests, Pydantic, Pandas, Streamlit, Plotly |
| **Qualidade e ambiente** | Testes, cobertura, padronização, CI, documentação | pytest, pytest-cov, Ruff, GitHub Actions, pyenv, pipx, Poetry, MkDocs Material |

O trabalho foi feito em entregas pequenas, cada uma num Pull Request revisado
e integrado com autorização:

| PR | Entrega |
|---|---|
| #1 | Especificação (SPEC) do assistente com CI/CD e publicação |
| #2, #4, #5, #6, #7 | Chatbot: modelo gratuito, tela acessível, confiabilidade, só modelos de conversa, tutor adaptativo |
| #8 | Entregas 1 e 2: auditoria do repositório e pipeline do IBGE |
| #9 | Entrega 3: dashboard Streamlit + Plotly |
| #10 | Entrega 4: ambiente Python (pipx, Poetry, pyenv) e qualidade (Ruff, cobertura) |
| #11 | Entrega 5: site de documentação MkDocs Material |
| este PR | Entrega 6: validação final e material de apresentação |

## 2. Como a validação foi feita

| Ambiente | Como | Para quê |
|---|---|---|
| Clone limpo + pip | `pip install -r requirements*.txt` num ambiente virtual novo | Igual à CI principal |
| Clone limpo + Poetry | `pipx install poetry==2.5.1` → `poetry install --with dados,dev,docs` | Instalação recomendada no computador |
| Clone limpo + só `requirements.txt` | Exatamente o `buildCommand` do `render.yaml` | Igual ao Render |
| pyenv 2.8.10 | Leitura do `.python-version` | Versão do Python |
| GitHub Actions (21/10/2026) | Workflows `api-ibge`, `ambiente` e `docs` disparados na `main` | O que precisa de internet: **API real do IBGE** |

O ambiente de desenvolvimento não acessa o site do IBGE nem o OpenRouter.
Por isso, nada que depende deles foi "simulado e chamado de real": a API real
foi conferida no GitHub Actions, e o chatbot foi conferido sem chave (ver
limitações).

## 3. Resultados principais

| Verificação | Resultado |
|---|---|
| Testes automáticos | **690 passaram**, 0 falharam, 0 pulados (pip e Poetry) |
| Cobertura do pipeline + dashboard (mínimo 80%) | **98,32%** |
| Cobertura do projeto inteiro (informativa) | 92% |
| Ruff (`check` e `format --check`) | Sem problemas (69 arquivos) |
| `pip check` (pip, Poetry e Render) | Sem conflitos |
| `poetry check --lock` | Sem problemas |
| `mkdocs build --strict` | Sem avisos (pip, Poetry e GitHub) |
| `validar_config.py` | `config.yml` correto |
| Chaves vazadas (arquivos atuais e os 52 commits do histórico) | Nenhuma |
| API real do IBGE (GitHub, 21/10/2026) | HTTP 200 em 3,1 s · **5.570 de 5.570** municípios válidos · 0 densidades inconsistentes |
| Dashboard com dados reais (GitHub) | 3 gráficos, CSV, filtro Sudeste + SP = 645 municípios; sem rolagem horizontal em 1280 px e 390 px |
| Chatbot instalado como no Render | Respondeu HTTP 200 em 9 s; Streamlit, Plotly, MkDocs e pytest **não** instalados |
| Chatbot no navegador | Tela, seletores de nível/modo, pergunta enviada, limite conferido e mensagem amigável sem chave |
| pyenv | `.python-version` = 3.11 → Python 3.11.17 escolhido sozinho |

### Números reais do Censo 2022 obtidos pelo pipeline

| Indicador | Valor |
|---|---|
| População total | 203.080.756 pessoas |
| Municípios | 5.570 |
| Mais populoso | São Paulo (SP), 11.451.999 pessoas |
| Média / mediana por município | 36.459,74 / 11.065 pessoas |
| Densidade demográfica do Brasil | 23,90 hab/km² |
| Sudeste · Nordeste · Sul · Norte · Centro-Oeste | 84.840.113 · 54.658.515 · 29.937.706 · 17.354.884 · 16.289.538 |

## 4. Achados da validação final

| Achado | O que foi feito |
|---|---|
| `GUIA-publicacao.md` ainda citava o roteador `openrouter/free`, trocado no PR #6 | **Corrigido** neste PR: o guia mostra a lista atual de modelos gratuitos |
| `pip-audit`: 8 vulnerabilidades conhecidas no **Pillow 12.3.0** (dependência indireta do Gradio e do Streamlit), corrigidas no Pillow 13 | **Sem correção compatível hoje**: as versões mais recentes do Gradio (6.30.0) e do Streamlit (1.66.0) exigem `pillow<13`. Todas tratam de abrir **arquivos de imagem** maliciosos; nenhum dos produtos aceita imagens das pessoas. Risco registrado, com ação de acompanhamento (ver [auditoria](auditoria-seguranca.md)) |
| PR #3 (diagnóstico antigo do "Port scan timeout", só documentação) continua aberto | Decisão da dona do projeto: integrar ou fechar |

## 5. Limitações (o que não foi validado)

- **Chatbot com IA de verdade**: não foi possível neste ambiente (o OpenRouter
  é bloqueado aqui e nenhuma chave foi usada, por regra do projeto). O fluxo
  completo com provedores é coberto por testes com IA simulada; a resposta
  real só pode ser conferida no serviço publicado no Render.
- **Serviço publicado no Render**: o endereço do serviço não está no
  repositório e o ambiente não acessa o Render. O que foi conferido: a `main`
  passou na CI (`CI e publicação`, execução após o merge do PR #11), que é a
  condição para o Render publicar, e a instalação idêntica à do Render funciona.
- **Windows**: os comandos documentados para Windows seguem a documentação
  oficial, mas a instalação foi executada em Linux (local e GitHub). O
  `poetry.lock` foi resolvido para todas as plataformas.
- **Fotos do dashboard com dados reais** ficam como artefato do GitHub
  (7 dias) e não foram copiadas para cá, porque o ambiente não consegue
  baixar artefatos.
- **Dados**: um único ano (Censo 2022), sem tendências.

## 6. Conclusão

Todos os requisitos da aula foram atendidos e **verificados na prática**
(ver [checklist](checklist.md)). O Professor de Dados continua com a mesma
configuração de produção (`render.yaml`, `requirements.txt` e o código do
chatbot não mudaram neste PR). As ações que ficam com a dona do projeto são:
conferir o chatbot publicado no Render, decidir sobre o PR #3 e, se quiser,
autorizar a publicação da documentação e do dashboard.
