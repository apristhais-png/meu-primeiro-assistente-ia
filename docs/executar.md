# Como executar localmente

Antes, prepare o ambiente ([Windows 11 passo a passo](ambiente/windows.md)).
Os comandos abaixo usam o Poetry; sem ele, tire o `poetry run` e ative o
ambiente virtual.

## Professor de Dados (chatbot)

```bash
cp .env.example .env            # Windows: Copy-Item .env.example .env
# edite o .env e coloque pelo menos uma chave (OPENROUTER_API_KEY, por exemplo)
poetry run python app.py
```

- Abra <http://127.0.0.1:7860>.
- Sem nenhuma chave, a tela abre, mas as perguntas recebem uma mensagem
  amigável de erro.
- No computador, o app escuta só em `127.0.0.1` (não aparece para outras
  máquinas da rede).
- Antes de mudar o `config.yml`, confira com `poetry run python scripts/validar_config.py`.

## Pipeline do IBGE

Precisa de internet; não precisa de chave.

```bash
poetry run python -m pipeline --cache dados/ibge_4714_2022.json --csv dados/municipios.csv
```

Mostra a qualidade dos dados, as unidades, os indicadores do Brasil e a
população por região, e salva o CSV. Com `--cache`, o download (~2 MB) é
reaproveitado nas próximas execuções.

## Dashboard Brasil em Dados

```bash
poetry run streamlit run dashboard/app.py
```

- Abre em <http://localhost:8501>. Para fechar: `Ctrl+C` no terminal.
- A primeira abertura baixa os dados do IBGE e guarda uma cópia em
  `dados/ibge_4714_2022.json`. Depois disso funciona até sem internet.
- Sem internet e sem a cópia, aparece uma mensagem amigável com o botão
  **Tentar de novo**.

## Testes, cobertura e Ruff

```bash
poetry run pytest                                  # todos os testes
poetry run pytest --cov=pipeline --cov=dashboard   # + cobertura (mínimo 80%)
poetry run ruff check .                            # erros comuns
poetry run ruff format --check .                   # formatação
poetry run python scripts/verificar_segredos.py    # chaves esquecidas nos arquivos
```

## Esta documentação

```bash
poetry install --with docs
poetry run mkdocs serve           # http://127.0.0.1:8000, atualiza sozinho ao salvar
poetry run mkdocs build --strict  # gera a pasta site/ e falha em links quebrados
```
