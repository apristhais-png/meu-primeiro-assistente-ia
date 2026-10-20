# Testes com pytest

```bash
pytest                 # com Poetry: poetry run pytest
pytest -q tests/test_pipeline.py      # só um arquivo
pytest -k dashboard                   # só os testes com "dashboard" no nome
```

## Regras dos testes

- **Nenhuma IA de verdade** é chamada: os provedores são simulados e nenhuma
  chave é usada (a CI roda com as chaves vazias).
- **Nenhum acesso à internet**: nos testes do pipeline e do dashboard, a rede
  é bloqueada e a API do IBGE é simulada.
- **Dados fictícios identificados como tal**: municípios "Cidade Teste ..."
  com códigos no formato oficial.
- Nenhum token ou chave aparece nos testes.

## O que cada arquivo testa

| Arquivo | Assunto |
|---|---|
| `test_config.py`, `test_cores.py` | `config.yml` e contraste das cores |
| `test_chat.py`, `test_tutor.py` | Uma pergunta do começo ao fim; níveis e modos |
| `test_provedores.py`, `test_confiabilidade.py` | Fallback, tempos, cancelamento, concorrência |
| `test_modelos_gratuitos.py`, `test_conferir_modelos.py` | Catálogo, preço zero, classificadores, quarentena |
| `test_limites.py` | Limites por minuto, por dia e por IP |
| `test_interface.py` | Tela Gradio (seletores, botões, endereço do servidor) |
| `test_pipeline.py` | Extração, validação, transformação, indicadores e `python -m pipeline` |
| `test_dashboard.py` | Dados, filtros, gráficos, CSV, erros e a tela inteira com o `AppTest` do Streamlit |
| `test_segredos.py` | O verificador de chaves vazadas |
| `test_versoes.py`, `test_poetry.py` | Versões fixas e iguais entre `requirements*.txt`, `pyproject.toml` e `poetry.lock` |
| `test_render.py`, `test_workflow.py`, `test_publicar.py` | `render.yaml`, GitHub Actions e o script legado do Hugging Face |
| `test_docs.py` | Este site: menu, páginas e os 21 temas obrigatórios |

## Testando a tela sem navegador

O dashboard é testado com `streamlit.testing.v1.AppTest`: o teste abre o
`dashboard/app.py`, mexe nos filtros e confere os cartões, gráficos e
mensagens, com a API simulada.

```python
tela = AppTest.from_file("dashboard/app.py").run()
tela.multiselect(key="regioes").set_value(["Sudeste"]).run()
assert {m.label: m.value for m in tela.metric}["Municípios"] == "2"
```

Veja também: [Cobertura](cobertura.md) · [GitHub Actions](ci.md).
