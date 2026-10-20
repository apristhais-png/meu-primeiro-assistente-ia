"""De onde vêm os dados: a fonte oficial e a tabela fixa de UFs do IBGE.

Fonte escolhida: API de dados agregados do IBGE, versão 3
(https://servicodados.ibge.gov.br/api/docs/agregados?versao=3).

- Tabela (agregado) 4714 do SIDRA: "População Residente, Área territorial e
  Densidade demográfica", Censo Demográfico 2022
  (https://sidra.ibge.gov.br/tabela/4714).
- Nível territorial N6 = Município (todos os municípios do Brasil).
- Pública, gratuita e SEM autenticação: nenhuma chave é necessária.

Por que esta tabela: traz, numa única consulta, três medidas oficiais do
mesmo ano para cada município (população, área e densidade). Isso permite
comparar municípios, UFs e regiões sem inventar nada. Ela tem um único ano
(2022): por isso o projeto NÃO mostra tendências nem variações no tempo.
"""

from dataclasses import dataclass

URL_BASE = "https://servicodados.ibge.gov.br/api/v3/agregados"
AGREGADO = "4714"
PERIODO = "2022"
NIVEL_MUNICIPIO = "N6"


@dataclass(frozen=True)
class Variavel:
    id: str
    coluna: str  # nome da coluna no DataFrame
    unidade: str


# Variáveis da tabela 4714 usadas no projeto. A validação confere se a
# resposta da API traz exatamente estes ids.
POPULACAO = Variavel("93", "populacao", "pessoas")
AREA = Variavel("6318", "area_km2", "km²")
DENSIDADE = Variavel("614", "densidade_hab_km2", "hab/km²")
VARIAVEIS = (POPULACAO, AREA, DENSIDADE)

FONTE_CITACAO = "IBGE, Censo Demográfico 2022, tabela 4714 (SIDRA), API de dados agregados v3"
URL_TABELA = "https://sidra.ibge.gov.br/tabela/4714"
# Data de referência do Censo 2022: os números descrevem o Brasil neste dia.
DATA_REFERENCIA = "31/07/2022"


def url_da_consulta(localidades: str = f"{NIVEL_MUNICIPIO}[all]") -> str:
    """URL da consulta GET: as três variáveis, 2022, todos os municípios."""
    ids = "|".join(v.id for v in VARIAVEIS)
    return f"{URL_BASE}/{AGREGADO}/periodos/{PERIODO}/variaveis/{ids}?localidades={localidades}"


# Unidades da Federação pelo código oficial do IBGE (os 2 primeiros dígitos
# do código do município). O 1º dígito é a Grande Região.
# Fonte: códigos oficiais de UF do IBGE (tabela fixa, não muda com a API).
REGIOES = {"1": "Norte", "2": "Nordeste", "3": "Sudeste", "4": "Sul", "5": "Centro-Oeste"}

UFS = {
    "11": ("RO", "Rondônia"), "12": ("AC", "Acre"), "13": ("AM", "Amazonas"),
    "14": ("RR", "Roraima"), "15": ("PA", "Pará"), "16": ("AP", "Amapá"),
    "17": ("TO", "Tocantins"), "21": ("MA", "Maranhão"), "22": ("PI", "Piauí"),
    "23": ("CE", "Ceará"), "24": ("RN", "Rio Grande do Norte"), "25": ("PB", "Paraíba"),
    "26": ("PE", "Pernambuco"), "27": ("AL", "Alagoas"), "28": ("SE", "Sergipe"),
    "29": ("BA", "Bahia"), "31": ("MG", "Minas Gerais"), "32": ("ES", "Espírito Santo"),
    "33": ("RJ", "Rio de Janeiro"), "35": ("SP", "São Paulo"), "41": ("PR", "Paraná"),
    "42": ("SC", "Santa Catarina"), "43": ("RS", "Rio Grande do Sul"),
    "50": ("MS", "Mato Grosso do Sul"), "51": ("MT", "Mato Grosso"), "52": ("GO", "Goiás"),
    "53": ("DF", "Distrito Federal"),
}
