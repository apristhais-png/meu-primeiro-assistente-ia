"""TRANSFORMAÇÃO: monta e prepara os dados com Pandas.

Recebe os registros já validados (validacao.py) e entrega DataFrames prontos
para os indicadores e para o dashboard. Nenhuma função aqui busca dados na
internet nem desenha gráficos.
"""

from collections.abc import Iterable

import pandas as pd

from pipeline.validacao import RegistroMunicipio

COLUNAS = [
    "codigo_ibge",
    "municipio",
    "uf_sigla",
    "uf_nome",
    "regiao",
    "ano",
    "populacao",
    "area_km2",
    "densidade_hab_km2",
]
TIPOS = {
    "codigo_ibge": "string",
    "municipio": "string",
    "uf_sigla": "string",
    "uf_nome": "string",
    "regiao": "string",
    "ano": "int64",
    "populacao": "int64",
    "area_km2": "float64",
    "densidade_hab_km2": "float64",
}


def montar_dataframe(registros: Iterable[RegistroMunicipio]) -> pd.DataFrame:
    """Registros validados → DataFrame com nomes, tipos e ordem padronizados.

    - Remove municípios repetidos (mesmo código IBGE), mantendo o primeiro.
    - Ordena por população, do maior para o menor.
    """
    df = pd.DataFrame([r.model_dump() for r in registros], columns=COLUNAS)
    df = df.drop_duplicates(subset="codigo_ibge", keep="first")
    df = df.astype(TIPOS)
    return df.sort_values(["populacao", "municipio"], ascending=[False, True], ignore_index=True)


def filtrar(
    df: pd.DataFrame,
    regioes: Iterable[str] | None = None,
    ufs: Iterable[str] | None = None,
    municipios: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Filtra por região, UF (sigla) e/ou código IBGE. Filtro vazio = sem filtro."""
    mascara = pd.Series(True, index=df.index)
    if regioes:
        mascara &= df["regiao"].isin(list(regioes))
    if ufs:
        mascara &= df["uf_sigla"].isin(list(ufs))
    if municipios:
        mascara &= df["codigo_ibge"].isin(list(municipios))
    return df[mascara].reset_index(drop=True)


def maiores(df: pd.DataFrame, quantidade: int, coluna: str = "populacao") -> pd.DataFrame:
    """Os "quantidade" municípios com maior valor na coluna (sem valores ausentes)."""
    if quantidade < 1:
        raise ValueError("a quantidade precisa ser pelo menos 1")
    return df.dropna(subset=[coluna]).nlargest(quantidade, coluna).reset_index(drop=True)


def agregar(df: pd.DataFrame, por: str) -> pd.DataFrame:
    """Totais por "regiao" ou "uf_sigla": municípios, população, área e densidade.

    A densidade do grupo é população total / área total (não a média das
    densidades, que daria o mesmo peso a municípios pequenos e grandes).
    Municípios sem área ficam fora da soma de área e da população usada na densidade.
    """
    if por not in ("regiao", "uf_sigla"):
        raise ValueError("agregue por 'regiao' ou 'uf_sigla'")
    com_area = df.dropna(subset=["area_km2"])
    grupos = df.groupby(por, observed=True)
    resultado = pd.DataFrame(
        {
            "municipios": grupos.size(),
            "populacao": grupos["populacao"].sum(),
            "area_km2": com_area.groupby(por, observed=True)["area_km2"].sum(),
            "_pop_com_area": com_area.groupby(por, observed=True)["populacao"].sum(),
        }
    )
    resultado["densidade_hab_km2"] = resultado["_pop_com_area"] / resultado["area_km2"]
    resultado = resultado.drop(columns="_pop_com_area").reset_index()
    return resultado.sort_values("populacao", ascending=False, ignore_index=True)


def para_csv(df: pd.DataFrame) -> bytes:
    """CSV para planilhas (Excel em português): separador ';', vírgula decimal e UTF-8 com BOM."""
    return df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
