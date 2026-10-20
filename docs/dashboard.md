# Dashboard Brasil em Dados — Censo 2022

```bash
streamlit run dashboard/app.py      # com Poetry: poetry run streamlit run dashboard/app.py
```

## Organização do código

| Arquivo | Papel |
|---|---|
| `dashboard/dados.py` | Carrega a base pelo pipeline, aplica os filtros e prepara as tabelas. Traduz erros técnicos em mensagens simples. |
| `dashboard/graficos.py` | Só monta os gráficos Plotly. |
| `dashboard/app.py` | Só a interface Streamlit. |

Nenhuma regra de cálculo é repetida no dashboard: filtros, ranking, totais,
indicadores e CSV vêm do `pipeline/`.

## O que a tela mostra

1. **Cabeçalho**: nome, propósito, fonte (link para o SIDRA) e aviso de que os
   dados são de 2022.
2. **Indicadores**: população total, municípios, município mais populoso,
   população média (e mediana), densidade e participação no Brasil.
3. **Filtros** (barra lateral, funcionam juntos):
    - região → UF → município (as listas se ajustam: ao escolher uma região,
      só aparecem as UFs e os municípios dela);
    - quantidade de municípios no ranking (5 a 50);
    - comparação por região ou por UF;
    - botão **Limpar filtros**.
4. **Gráficos Plotly**:
    - os municípios mais populosos;
    - população por região/UF;
    - densidade por região/UF, com a do Brasil como linha de referência.
5. **Tabela** com o código IBGE de cada município e números no padrão
   brasileiro (1.234.567 e 12,34).
6. **Download CSV** dos dados filtrados.
7. **Qualidade dos dados**: recebidos, válidos, descartados, ausentes,
   unidades, conferência da densidade, data de referência e fonte.

## Escolhas de visualização

- **Barras horizontais**: os nomes ficam legíveis, inclusive no celular.
- **Uma cor só**: cada gráfico tem uma única série, então a cor não precisa
  de legenda. O título diz o que é medido.
- Cada gráfico tem **texto alternativo** e os números também aparecem em
  tabela.
- **Nenhuma linha no tempo**: a fonte tem um único ano.

## Cache: por que é rápido

| Camada | Duração | Efeito |
|---|---|---|
| `st.cache_data` (memória) | 24 horas | Mexer nos filtros não baixa nada; só refaz contas. |
| Cópia em disco `dados/ibge_4714_2022.json` | até ser apagada | Reabrir o dashboard não baixa de novo, mesmo sem internet. |

- Erros **não** ficam no cache: **Tentar de novo** consulta o IBGE outra vez.
- Uma cópia corrompida é descartada e baixada de novo sozinha.

## Erros e estados vazios

| Situação | O que aparece |
|---|---|
| IBGE fora do ar ou sem internet | "Não foi possível buscar os dados no IBGE agora…" + **Tentar de novo** |
| IBGE recusou a consulta | Mensagem dizendo que a API pode ter mudado |
| Formato inesperado | Aviso de que os números não são mostrados para não estarem errados |
| Nenhum município nos filtros | Aviso para remover filtros, sem números |

## Validação com dados reais

O workflow `api-ibge.yml` abre o dashboard com os dados reais, confere os
indicadores, aplica um filtro e tira fotos da tela (computador e celular),
guardadas como artefato da execução por 7 dias.
