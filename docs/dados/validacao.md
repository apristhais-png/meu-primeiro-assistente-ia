# Validação com Pydantic

Arquivo: `pipeline/validacao.py`. Função principal: `validar()`.

A validação acontece em **duas camadas**.

## 1. O formato da resposta (modelos da API)

Os modelos Pydantic descrevem o JSON que a API devolve:

| Modelo | Confere |
|---|---|
| `VariavelIBGE` | `id`, nome, unidade e pelo menos um resultado |
| `ResultadoIBGE` | lista de séries |
| `SerieIBGE` | a localidade e os valores por ano |
| `LocalidadeIBGE` | código com **7 dígitos**, nível e nome |

Campos novos que a API venha a criar são ignorados (`extra="ignore"`), para
não quebrar o pipeline à toa.

## 2. Cada município (registro normalizado)

`RegistroMunicipio` é uma linha limpa da tabela final:

| Campo | Regra |
|---|---|
| `codigo_ibge` | 7 dígitos |
| `municipio` | não vazio (o " - UF" do nome é separado) |
| `uf_sigla`, `uf_nome` | vêm do código (2 primeiros dígitos), numa tabela fixa de UFs |
| `regiao` | uma das 5 regiões oficiais |
| `ano` | entre 1872 e 2100 |
| `populacao` | número inteiro, maior ou igual a 0 |
| `area_km2` | maior que 0 (ou ausente) |
| `densidade_hab_km2` | maior ou igual a 0 (ou ausente) |

## Dois tipos de problema

=== "Erro que para tudo"

    `ErroDeValidacao` — a análise não pode continuar:

    - a estrutura do JSON é diferente da esperada;
    - falta uma das três variáveis;
    - veio um nível diferente de município;
    - nenhum município ficou válido.

    Nada é mostrado com dados pela metade.

=== "Problema recuperável"

    O município é deixado de fora e **contado** no relatório de qualidade:

    - código de UF desconhecido;
    - UF do nome diferente da UF do código;
    - população ausente ou não inteira;
    - valores fora do intervalo válido.

    Nada é descartado em silêncio.

## Relatório de qualidade

`RelatorioDeQualidade` guarda quantos municípios foram recebidos, quantos são
válidos, os descartados (por motivo), os valores ausentes (por coluna) e os
duplicados removidos. O dashboard mostra esse relatório na seção
**Qualidade dos dados**.

```text
5570 de 5570 municípios válidos
```

## Valores especiais do IBGE

| Texto | Vira |
|---|---|
| `-` | 0 (zero absoluto) |
| `...`, `..`, `X`, vazio | ausente (`None`) |
| `"6211223"`, `"5,5"` | número |
