# Cobertura com pytest-cov

A cobertura mostra **quais linhas do código os testes executaram**. O projeto
exige **pelo menos 80%** nos módulos de dados (`pipeline/`) e do dashboard
(`dashboard/`); a CI falha abaixo disso.

## Comandos

```bash
pytest --cov=pipeline --cov=dashboard                        # resumo no terminal
pytest --cov=pipeline --cov=dashboard --cov-report=term-missing   # + linhas não testadas
pytest --cov=pipeline --cov=dashboard --cov-report=html      # relatório em htmlcov/
```

Depois do relatório HTML, abra `htmlcov/index.html` no navegador (no Windows:
`start htmlcov\index.html`). As linhas em vermelho não foram executadas por
nenhum teste.

## Configuração (`pyproject.toml`)

```toml
[tool.coverage.run]
source = ["pipeline", "dashboard"]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

## Como ler o resultado

```text
Name                        Stmts   Miss  Cover   Missing
---------------------------------------------------------
dashboard/dados.py            124      0   100%
pipeline/validacao.py         142      2    99%   100, 127
...
TOTAL                         595     10    98%
Required test coverage of 80% reached.
```

- **Stmts**: linhas de código executáveis.
- **Miss**: linhas que nenhum teste executou.
- **Missing**: os números dessas linhas.

!!! note "Cobertura não é qualidade"
    Uma linha executada não é necessariamente uma linha bem testada. Por isso
    os testes conferem **valores e comportamentos**, não só que o código roda.

Os arquivos de cobertura (`.coverage`, `htmlcov/`) ficam fora do Git.
