# Ruff

O Ruff faz duas coisas:

1. **Lint** (`ruff check`): procura erros comuns, imports sem uso, código que
   pode ser simplificado e alguns problemas de segurança.
2. **Formatação** (`ruff format`): deixa o código com o mesmo estilo em todos
   os arquivos (espaços, aspas, quebras de linha).

## Comandos

```bash
ruff check .            # mostra os problemas
ruff check --fix .      # corrige os que são seguros de corrigir sozinho
ruff format .           # formata todos os arquivos
ruff format --check .   # só confere, sem mudar nada (é o que a CI faz)
```

Com Poetry: `poetry run ruff check .`.

## Configuração (`pyproject.toml`)

```toml
[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
extend-select = ["E501"]   # linhas com mais de 120 caracteres

[tool.ruff.format]
quote-style = "double"
line-ending = "lf"
```

- As regras são o **conjunto padrão do Ruff 0.17**, que já é amplo (erros,
  bugs comuns, imports, modernização, simplificações e parte das regras de
  segurança). Nenhuma foi desligada; só foi acrescentado o limite de tamanho
  de linha.
- A versão do Ruff é fixa (`ruff==0.17.0`), então o resultado é o mesmo no seu
  computador e na CI.

## Na CI

O job `testar` roda `ruff check .` e `ruff format --check .` em todo Pull
Request. Se algo estiver fora do padrão, o job fica vermelho e o Render não
publica.
