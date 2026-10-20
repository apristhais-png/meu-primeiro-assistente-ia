# Transformação com Pandas e indicadores

## Transformação (`pipeline/transformacao.py`)

| Função | O que faz |
|---|---|
| `montar_dataframe(registros)` | Cria o DataFrame com colunas e tipos padronizados, remove códigos repetidos e ordena por população (maior primeiro). |
| `filtrar(df, regioes, ufs, municipios)` | Aplica os filtros **juntos**. Filtro vazio = sem filtro. |
| `maiores(df, quantidade, coluna)` | Os N maiores (ranking). |
| `agregar(df, por)` | Totais por `"regiao"` ou `"uf_sigla"`: municípios, população, área e densidade. |
| `para_csv(df)` | CSV para o Excel em português: separador `;`, vírgula decimal e UTF-8 com BOM. |

Colunas finais:

```text
codigo_ibge · municipio · uf_sigla · uf_nome · regiao · ano · populacao · area_km2 · densidade_hab_km2
```

!!! note "Densidade de um grupo"
    A densidade de uma região é **população total ÷ área total**, e não a
    média das densidades dos municípios. A média daria o mesmo peso a uma
    cidade pequena e a uma capital.

## Indicadores (`pipeline/indicadores.py`)

Cada indicador tem nome, definição, fórmula, unidade, fonte e período. O
dashboard mostra essa definição no **?** de cada cartão.

| Indicador | Fórmula | Unidade |
|---|---|---|
| População total da seleção | Σ população | pessoas |
| Municípios analisados | contagem | municípios |
| Maior população | máx(população) | pessoas |
| População média | Σ população ÷ nº de municípios | pessoas |
| População mediana | mediana(população) | pessoas |
| Densidade da seleção | Σ população ÷ Σ área | hab/km² |
| Participação no Brasil | Σ população da seleção ÷ Σ população do Brasil × 100 | % |

- Se a seleção estiver vazia, todos os indicadores ficam **sem valor** (nada
  é inventado).
- `densidades_inconsistentes()` confere se a densidade publicada pelo IBGE bate
  com população ÷ área (tolerância de 1%).
- Não há indicadores de tendência: a fonte tem um único ano.

## Rodando o pipeline inteiro

```bash
python -m pipeline --cache dados/ibge_4714_2022.json --csv dados/municipios.csv
```

```text
[OK] Qualidade: 5570 de 5570 municípios válidos
[OK] Densidades que não batem com população ÷ área: 0
Indicadores (Brasil):
  População total da seleção: 203.080.756 pessoas
  ...
```
