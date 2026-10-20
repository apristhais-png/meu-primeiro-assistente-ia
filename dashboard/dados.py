"""PREPARAÇÃO DOS DADOS do dashboard (sem Streamlit e sem gráficos).

Tudo aqui só CHAMA o pipeline: busca (extracao), conferência (validacao),
filtros, rankings e totais (transformacao) e indicadores (indicadores).
Nenhuma regra de cálculo é repetida neste arquivo; ele apenas junta as peças
na forma que a tela precisa e traduz erros técnicos em mensagens amigáveis.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
from pandas.io.formats.style import Styler

from pipeline.extracao import ErroDeExtracao, extrair
from pipeline.fonte import REGIOES, UFS
from pipeline.indicadores import Indicador, calcular, densidades_inconsistentes
from pipeline.transformacao import agregar, filtrar, maiores, montar_dataframe
from pipeline.validacao import ErroDeValidacao, RelatorioDeQualidade, validar

logger = logging.getLogger(__name__)

# Cópia local do download (a pasta dados/ fica fora do Git). Os números do
# Censo 2022 não mudam, então a cópia evita baixar ~2 MB a cada vez que o
# dashboard é aberto. Apague o arquivo para forçar um download novo.
CAMINHO_CACHE = Path(__file__).resolve().parents[1] / "dados" / "ibge_4714_2022.json"

NOMES_VARIAVEIS = {"populacao": "população", "area_km2": "área", "densidade_hab_km2": "densidade"}
AGRUPAMENTOS = {"regiao": "Região", "uf_sigla": "UF"}
RANKING_MINIMO, RANKING_MAXIMO, RANKING_PADRAO = 5, 50, 10

MENSAGEM_SEM_CONEXAO = (
    "Não foi possível buscar os dados no IBGE agora. Confira sua conexão com a "
    "internet e tente de novo em alguns minutos."
)
MENSAGEM_RECUSADA = (
    "O serviço do IBGE não aceitou a consulta. Tente de novo mais tarde; se o "
    "problema continuar, a API pode ter mudado."
)
MENSAGEM_FALHA = (
    "Não foi possível obter os dados do IBGE agora. Tente de novo mais tarde."
)
MENSAGEM_FORMATO = (
    "Os dados do IBGE chegaram num formato diferente do esperado, por isso o "
    "dashboard não mostra números que poderiam estar errados."
)


class ErroAoCarregar(Exception):
    """Falha ao obter os dados, com uma mensagem própria para mostrar na tela."""


@dataclass(frozen=True)
class Base:
    """Todos os municípios do Brasil, já conferidos, e o relatório de qualidade."""

    municipios: pd.DataFrame
    relatorio: RelatorioDeQualidade
    unidades: dict[str, str]
    densidades_inconsistentes: int
    origem: str  # "API do IBGE" ou "cópia local"
    carregado_em: datetime = field(default_factory=datetime.now)


def carregar_base(cache: Path | None = None) -> Base:
    """Busca e confere os dados. Lança ErroAoCarregar com mensagem amigável.

    Se a cópia local estiver corrompida ou fora do formato, ela é ignorada e
    os dados são baixados de novo (uma vez).
    """
    cache = CAMINHO_CACHE if cache is None else cache
    usou_copia = cache.is_file()
    try:
        try:
            validados = validar(extrair(cache=cache))
        except (json.JSONDecodeError, UnicodeDecodeError, ErroDeValidacao):
            if not usou_copia:
                raise
            logger.warning("dashboard copia_local_invalida=%s baixando_de_novo", cache)
            cache.unlink(missing_ok=True)
            usou_copia = False
            validados = validar(extrair(cache=cache))
    except ErroDeExtracao as erro:
        logger.error("dashboard falha_extracao status=%s erro=%s", erro.status, erro)
        if erro.temporario:
            mensagem = MENSAGEM_SEM_CONEXAO
        elif erro.status is not None:
            mensagem = MENSAGEM_RECUSADA
        else:
            mensagem = MENSAGEM_FALHA
        raise ErroAoCarregar(mensagem) from None
    except (ErroDeValidacao, json.JSONDecodeError, UnicodeDecodeError) as erro:
        logger.error("dashboard falha_validacao erro=%s", erro)
        raise ErroAoCarregar(MENSAGEM_FORMATO) from None

    df = montar_dataframe(validados.registros)
    return Base(
        municipios=df,
        relatorio=validados.relatorio,
        unidades=validados.unidades,
        densidades_inconsistentes=len(densidades_inconsistentes(df)),
        origem="cópia local" if usou_copia else "API do IBGE",
    )


# ---------- Filtros ----------

@dataclass(frozen=True)
class Filtros:
    regioes: tuple[str, ...] = ()
    ufs: tuple[str, ...] = ()
    municipios: tuple[str, ...] = ()  # códigos IBGE
    quantidade_ranking: int = RANKING_PADRAO
    agrupar_por: str = "regiao"

    def __post_init__(self):
        if self.agrupar_por not in AGRUPAMENTOS:
            raise ValueError(f"agrupamento inválido: {self.agrupar_por!r}")
        if not RANKING_MINIMO <= self.quantidade_ranking <= RANKING_MAXIMO:
            raise ValueError("quantidade do ranking fora do intervalo")

    @property
    def ativos(self) -> bool:
        return bool(self.regioes or self.ufs or self.municipios)


def opcoes_de_regioes(df: pd.DataFrame) -> list[str]:
    """Regiões presentes nos dados, na ordem oficial do IBGE (Norte → Centro-Oeste)."""
    presentes = set(df["regiao"])
    return [r for r in REGIOES.values() if r in presentes]


def opcoes_de_ufs(df: pd.DataFrame, regioes: tuple[str, ...] = ()) -> dict[str, str]:
    """UFs (sigla → "SP — São Paulo") das regiões escolhidas, em ordem alfabética."""
    nomes = dict(UFS.values())
    siglas = filtrar(df, regioes=regioes)["uf_sigla"].unique()
    return {s: f"{s} — {nomes[s]}" for s in sorted(siglas)}


def opcoes_de_municipios(
    df: pd.DataFrame, regioes: tuple[str, ...] = (), ufs: tuple[str, ...] = ()
) -> dict[str, str]:
    """Municípios (código IBGE → "Nome (UF)") das regiões/UFs escolhidas, por nome."""
    dados = filtrar(df, regioes=regioes, ufs=ufs).sort_values(["municipio", "uf_sigla"])
    return dict(zip(dados["codigo_ibge"], dados["municipio"] + " (" + dados["uf_sigla"] + ")", strict=True))


def manter_validos(escolhidos, opcoes) -> list:
    """Remove escolhas que deixaram de existir (ex.: UF de uma região desmarcada)."""
    return [e for e in (escolhidos or []) if e in opcoes]


# ---------- Seleção ----------

@dataclass(frozen=True)
class Selecao:
    municipios: pd.DataFrame  # municípios filtrados (todas as colunas do pipeline)
    indicadores: dict[str, Indicador]
    ranking: pd.DataFrame  # os N mais populosos da seleção
    grupos: pd.DataFrame  # totais por região ou UF
    agrupar_por: str
    densidade_brasil: float | None

    @property
    def vazia(self) -> bool:
        return self.municipios.empty


def montar_selecao(todos: pd.DataFrame, filtros: Filtros) -> Selecao:
    """Aplica os filtros juntos e calcula tudo o que a tela mostra."""
    selecao = filtrar(todos, filtros.regioes, filtros.ufs, filtros.municipios)
    vazia = selecao.empty
    return Selecao(
        municipios=selecao,
        indicadores=calcular(selecao, todos),
        ranking=selecao if vazia else maiores(selecao, filtros.quantidade_ranking),
        grupos=selecao if vazia else agregar(selecao, filtros.agrupar_por),
        agrupar_por=filtros.agrupar_por,
        densidade_brasil=calcular(todos, todos)["densidade_selecao"].valor,
    )


def descrever_filtros(filtros: Filtros, todos: pd.DataFrame) -> str:
    """Frase curta com o que está sendo mostrado."""
    if not filtros.ativos:
        return "Mostrando todo o Brasil."
    partes = []
    if filtros.regioes:
        partes.append(f"regiões: {', '.join(filtros.regioes)}")
    if filtros.ufs:
        partes.append(f"UFs: {', '.join(filtros.ufs)}")
    if filtros.municipios:
        nomes = opcoes_de_municipios(todos)
        escolhidos = [nomes.get(c, c) for c in filtros.municipios]
        resumo = ", ".join(escolhidos[:3]) + (f" e mais {len(escolhidos) - 3}" if len(escolhidos) > 3 else "")
        partes.append(f"municípios: {resumo}")
    return "Filtros: " + "; ".join(partes) + "."


# ---------- Tabelas para a tela ----------

COLUNAS_TABELA = {
    "codigo_ibge": "Código IBGE",
    "municipio": "Município",
    "uf_sigla": "UF",
    "regiao": "Região",
    "populacao": "População (pessoas)",
    "area_km2": "Área (km²)",
    "densidade_hab_km2": "Densidade (hab/km²)",
}

COLUNAS_GRUPOS = {
    "municipios": "Municípios",
    "populacao": "População (pessoas)",
    "area_km2": "Área (km²)",
    "densidade_hab_km2": "Densidade (hab/km²)",
}


def _formato_brasileiro(estilo: Styler, inteiras: list[str], decimais: list[str]) -> Styler:
    """Números com ponto no milhar e vírgula decimal; ausente aparece como "—"."""
    estilo = estilo.format(thousands=".", decimal=",", precision=0, subset=inteiras, na_rep="—")
    return estilo.format(thousands=".", decimal=",", precision=2, subset=decimais, na_rep="—")


def tabela_de_municipios(selecao: pd.DataFrame) -> Styler:
    """Municípios filtrados com nomes de coluna em português e números no padrão brasileiro.

    Só a aparência muda: a ordenação na tela continua usando os números.
    """
    tabela = selecao[list(COLUNAS_TABELA)].rename(columns=COLUNAS_TABELA)
    return _formato_brasileiro(
        tabela.style,
        inteiras=["População (pessoas)"],
        decimais=["Área (km²)", "Densidade (hab/km²)"],
    )


def tabela_de_grupos(grupos: pd.DataFrame, agrupar_por: str) -> Styler:
    """Totais por região ou UF (a "versão em tabela" dos gráficos)."""
    colunas = {agrupar_por: AGRUPAMENTOS[agrupar_por], **COLUNAS_GRUPOS}
    tabela = grupos[list(colunas)].rename(columns=colunas)
    return _formato_brasileiro(
        tabela.style,
        inteiras=["Municípios", "População (pessoas)"],
        decimais=["Área (km²)", "Densidade (hab/km²)"],
    )
