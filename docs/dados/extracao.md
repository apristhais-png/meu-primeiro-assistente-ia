# Extração com Requests

Arquivo: `pipeline/extracao.py`. Função principal: `extrair()`.

## O que ela faz

1. Se existir uma **cópia local** (parâmetro `cache`), lê o arquivo e não
   acessa a internet.
2. Senão, faz o **GET** na URL da tabela 4714 com tempo limite.
3. Confere o **status HTTP**, se a resposta é um **JSON válido** e se não
   está **vazia**.
4. Em falha **temporária**, espera 2 segundos e tenta **mais uma vez**.
5. Se pediu cópia local, salva o JSON para a próxima vez.

## Regras

| Regra | Valor |
|---|---|
| Tempo limite | 10 s para conectar, 60 s para receber a resposta |
| Tentativas | 2 (1 + 1 repetição, só em falha temporária) |
| Espera entre tentativas | 2 segundos |

| Situação | Temporária? | O que acontece |
|---|---|---|
| Demorou demais (timeout) | sim | tenta de novo |
| Sem conexão | sim | tenta de novo |
| HTTP 429 (pedidos demais) | sim | tenta de novo |
| HTTP 5xx (problema no IBGE) | sim | tenta de novo |
| HTTP 400 ou 404 | não | para com uma mensagem clara |
| Outro status diferente de 200 | não | para com uma mensagem clara |
| JSON inválido ou resposta vazia | não | para com uma mensagem clara |

Todas as falhas viram um `ErroDeExtracao` com a mensagem, o status (quando
houver) e a indicação de "temporária". No dashboard, essas mensagens técnicas
viram textos simples para a pessoa ("Não foi possível buscar os dados no IBGE
agora…") e o detalhe fica só no log.

## Log

Cada requisição registra só dados públicos:

```text
ibge_get status=200 duracao_ms=21034 tamanho=2084216
```

A API não usa chave, então não há segredo que possa vazar no log.

## Exemplo

```python
from pathlib import Path
from pipeline.extracao import extrair

bruto = extrair(cache=Path("dados/ibge_4714_2022.json"))
```

## Testes

`tests/test_pipeline.py` simula cada caso da tabela acima (400, 404, 429, 5xx,
timeout, sem conexão, JSON inválido, resposta vazia, cópia local) sem acessar
a internet: a rede é bloqueada durante os testes.
