"""VALIDAÇÃO: confere e normaliza o JSON do IBGE com Pydantic.

Formato da resposta da API de agregados v3 (uma lista, uma entrada por variável):

    [{"id": "93", "variavel": "População residente", "unidade": "Pessoas",
      "resultados": [{"classificacoes": [],
                      "series": [{"localidade": {"id": "3304557",
                                                 "nivel": {"id": "N6", "nome": "Município"},
                                                 "nome": "Rio de Janeiro - RJ"},
                                  "serie": {"2022": "6211223"}}]}]},
     ...]

Dois tipos de problema:
- ERRO que impede a análise (ErroDeValidacao): estrutura inesperada, variável
  faltando, nenhum município válido. Nada é mostrado com dados pela metade.
- Problema RECUPERÁVEL (vai para o RelatorioDeQualidade): um município com
  valor ausente ou inválido é deixado de fora, e o relatório diz quantos e
  por quê. Nada é descartado em silêncio.

Valores especiais do IBGE: "-" (zero absoluto), "..." / ".." (não disponível
ou não se aplica), "X" (sigilo). Só "-" vira número (0); os outros viram
ausentes.
"""

from collections import Counter
from dataclasses import dataclass, field

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
)

from pipeline.fonte import NIVEL_MUNICIPIO, PERIODO, REGIOES, UFS, VARIAVEIS, Variavel


class ErroDeValidacao(Exception):
    """Os dados não têm a estrutura esperada: a análise não pode continuar."""


# ---------- Modelos do JSON bruto (o que a API devolve) ----------


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="ignore")  # campos novos da API não quebram o pipeline


class NivelIBGE(_Modelo):
    id: str
    nome: str


class LocalidadeIBGE(_Modelo):
    id: str = Field(pattern=r"^\d{7}$")  # código IBGE do município: 7 dígitos
    nivel: NivelIBGE
    nome: str = Field(min_length=1)


class SerieIBGE(_Modelo):
    localidade: LocalidadeIBGE
    serie: dict[str, str | None]


class ResultadoIBGE(_Modelo):
    classificacoes: list = []
    series: list[SerieIBGE]


class VariavelIBGE(_Modelo):
    id: str
    variavel: str
    unidade: str
    resultados: list[ResultadoIBGE] = Field(min_length=1)


RespostaIBGE = TypeAdapter(list[VariavelIBGE])


# ---------- Registro normalizado (uma linha por município) ----------


class RegistroMunicipio(_Modelo):
    codigo_ibge: str = Field(pattern=r"^\d{7}$")
    municipio: str = Field(min_length=1)
    uf_sigla: str = Field(pattern=r"^[A-Z]{2}$")
    uf_nome: str
    regiao: str
    ano: int = Field(ge=1872, le=2100)
    populacao: int = Field(ge=0)
    area_km2: float | None = Field(default=None, gt=0)
    densidade_hab_km2: float | None = Field(default=None, ge=0)

    @field_validator("regiao")
    @classmethod
    def regiao_oficial(cls, regiao: str) -> str:
        if regiao not in REGIOES.values():
            raise ValueError(f"região desconhecida: {regiao!r}")
        return regiao


@dataclass
class RelatorioDeQualidade:
    """O que foi recebido, aceito e descartado (e por quê)."""

    municipios_recebidos: int = 0
    municipios_validos: int = 0
    descartados: Counter = field(default_factory=Counter)  # motivo -> quantidade
    valores_ausentes: Counter = field(default_factory=Counter)  # coluna -> quantidade
    duplicados_removidos: int = 0

    @property
    def municipios_descartados(self) -> int:
        return sum(self.descartados.values())

    def resumo(self) -> str:
        partes = [f"{self.municipios_validos} de {self.municipios_recebidos} municípios válidos"]
        if self.descartados:
            partes.append("descartados: " + ", ".join(f"{m} ({n})" for m, n in sorted(self.descartados.items())))
        if self.valores_ausentes:
            partes.append(
                "valores ausentes: " + ", ".join(f"{c} ({n})" for c, n in sorted(self.valores_ausentes.items()))
            )
        if self.duplicados_removidos:
            partes.append(f"duplicados removidos: {self.duplicados_removidos}")
        return "; ".join(partes)


@dataclass
class DadosValidados:
    registros: list[RegistroMunicipio]
    relatorio: RelatorioDeQualidade
    unidades: dict[str, str]  # coluna -> unidade informada pela API


# ---------- Conversão de valores ----------

_AUSENTES = {"...", "..", "X", "", None}


def converter_numero(texto: str | None) -> float | None:
    """Valor da série do IBGE → número (ou None se ausente)."""
    if texto in _AUSENTES:
        return None
    if texto == "-":
        return 0.0  # "-" significa zero absoluto no IBGE
    try:
        return float(str(texto).replace(",", "."))
    except ValueError:
        return None


def separar_nome_e_uf(nome: str) -> tuple[str, str | None]:
    """'Rio de Janeiro - RJ' → ('Rio de Janeiro', 'RJ')."""
    if " - " in nome:
        municipio, uf = nome.rsplit(" - ", 1)
        return municipio.strip(), uf.strip()
    return nome.strip(), None


# ---------- Validação principal ----------


def validar(bruto: object, ano: str = PERIODO, variaveis: tuple[Variavel, ...] = VARIAVEIS) -> DadosValidados:
    """JSON bruto da API → registros validados + relatório de qualidade."""
    try:
        respostas = RespostaIBGE.validate_python(bruto)
    except ValidationError as erro:
        raise ErroDeValidacao(
            f"a resposta do IBGE não tem o formato esperado ({erro.error_count()} problema(s))"
        ) from None

    por_id = {r.id: r for r in respostas}
    faltando = [v.id for v in variaveis if v.id not in por_id]
    if faltando:
        raise ErroDeValidacao(f"a resposta do IBGE não trouxe as variáveis {faltando}")

    # Junta as variáveis por município: {codigo: {"nome": ..., coluna: valor}}
    linhas: dict[str, dict] = {}
    relatorio = RelatorioDeQualidade()
    duplicados = 0
    for variavel in variaveis:
        vistos: set[str] = set()
        for resultado in por_id[variavel.id].resultados:
            for serie in resultado.series:
                local = serie.localidade
                if local.nivel.id != NIVEL_MUNICIPIO:
                    raise ErroDeValidacao(f"esperava municípios ({NIVEL_MUNICIPIO}), veio {local.nivel.id}")
                if local.id in vistos:
                    duplicados += 1
                    continue
                vistos.add(local.id)
                linha = linhas.setdefault(local.id, {"nome": local.nome})
                linha[variavel.coluna] = serie.serie.get(ano)

    relatorio.municipios_recebidos = len(linhas)
    relatorio.duplicados_removidos = duplicados
    registros = []
    for codigo, linha in linhas.items():
        registro, motivo = _normalizar(codigo, linha, ano, variaveis, relatorio)
        if registro is None:
            relatorio.descartados[motivo] += 1
        else:
            registros.append(registro)
    relatorio.municipios_validos = len(registros)

    if not registros:
        raise ErroDeValidacao("nenhum município válido na resposta do IBGE")
    unidades = {v.coluna: por_id[v.id].unidade for v in variaveis}
    return DadosValidados(registros, relatorio, unidades)


def _normalizar(codigo, linha, ano, variaveis, relatorio):
    municipio, uf_no_nome = separar_nome_e_uf(linha["nome"])
    uf = UFS.get(codigo[:2])
    if uf is None:
        return None, "código de UF desconhecido"
    uf_sigla, uf_nome = uf
    if uf_no_nome is not None and uf_no_nome != uf_sigla:
        return None, "UF do nome diferente da UF do código"

    valores = {}
    for variavel in variaveis:
        valor = converter_numero(linha.get(variavel.coluna))
        if valor is None:
            relatorio.valores_ausentes[variavel.coluna] += 1
        valores[variavel.coluna] = valor
    if valores.get("populacao") is None:
        return None, "população ausente"
    if valores["populacao"] != int(valores["populacao"]):
        return None, "população não é um número inteiro"

    try:
        registro = RegistroMunicipio(
            codigo_ibge=codigo,
            municipio=municipio,
            uf_sigla=uf_sigla,
            uf_nome=uf_nome,
            regiao=REGIOES[codigo[0]],
            ano=int(ano),
            populacao=int(valores["populacao"]),
            area_km2=valores.get("area_km2"),
            densidade_hab_km2=valores.get("densidade_hab_km2"),
        )
    except ValidationError:
        return None, "valores fora do intervalo válido"
    return registro, None
