# Funcionamento da API do IBGE

## A fonte

| Item | Valor |
|---|---|
| Serviço | [API de dados agregados do IBGE, versão 3](https://servicodados.ibge.gov.br/api/docs/agregados?versao=3) |
| Tabela | [4714 do SIDRA](https://sidra.ibge.gov.br/tabela/4714): população residente, área territorial e densidade demográfica |
| Pesquisa | Censo Demográfico 2022 (data de referência: 31/07/2022) |
| Nível territorial | `N6` = município (todos os 5.570) |
| Autenticação | **Nenhuma**: a API é pública e gratuita, não há chave |

Tudo isso fica num só lugar: `pipeline/fonte.py`.

## A consulta

Uma única requisição **HTTP GET** traz as três variáveis para todos os
municípios:

```text
https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/variaveis/93|6318|614?localidades=N6[all]
```

| Parte da URL | Significado |
|---|---|
| `agregados/4714` | tabela 4714 |
| `periodos/2022` | ano do Censo |
| `variaveis/93\|6318\|614` | população (93), área em km² (6318), densidade em hab/km² (614) |
| `localidades=N6[all]` | todos os municípios |

## O formato da resposta

A API devolve uma **lista com uma entrada por variável**. Dentro de cada
variável, há uma série por município:

```json
[
  {
    "id": "93",
    "variavel": "População residente",
    "unidade": "Pessoas",
    "resultados": [{
      "classificacoes": [],
      "series": [{
        "localidade": {"id": "3304557", "nivel": {"id": "N6", "nome": "Município"},
                       "nome": "Rio de Janeiro - RJ"},
        "serie": {"2022": "6211223"}
      }]
    }]
  }
]
```

- O **código IBGE** do município tem 7 dígitos. Os 2 primeiros são a UF e o
  primeiro é a região (1 = Norte, 2 = Nordeste, 3 = Sudeste, 4 = Sul,
  5 = Centro-Oeste).
- Os valores chegam como **texto**. Há valores especiais: `-` significa zero;
  `...`, `..` e `X` significam "não disponível" ou "sigilo".
- A resposta completa tem cerca de 2 MB.

## Validação com a API real

O ambiente de desenvolvimento não acessa o site do IBGE, então os testes
normais usam uma API **simulada**. A conferência com a API **real** roda no
GitHub Actions (workflow `api-ibge.yml`) nos Pull Requests que mexem no
pipeline ou no dashboard. Na execução registrada no PR #8:

| Conferência | Resultado |
|---|---|
| Resposta | HTTP 200, cerca de 2 MB |
| Municípios válidos | 5.570 de 5.570 |
| Unidades | Pessoas · Quilômetros quadrados · Habitante por quilômetro quadrado |
| Densidade do IBGE × população ÷ área | 0 municípios com diferença acima de 1% |
| População total | 203.080.756 (maior município: São Paulo, 11.451.999) |

Próximas etapas: [Extração](extracao.md) → [Validação](validacao.md) →
[Transformação e indicadores](transformacao.md).
