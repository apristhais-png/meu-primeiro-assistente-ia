"""Leitura e validação do config.yml (SPEC, seção 4.2).

Uso:
    from assistente.config import carregar_configuracao
    config = carregar_configuracao()
    print(config.assistente.nome)

Se o arquivo tiver algum erro, é lançado um ErroDeConfiguracao com a lista
de problemas em português, dizendo qual campo está errado e como corrigir.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from assistente import cores
from assistente.modelos_gratuitos import motivo_para_recusar_id

RAIZ_DO_PROJETO = Path(__file__).resolve().parent.parent
CAMINHO_PADRAO = RAIZ_DO_PROJETO / "config.yml"

PROVEDORES_CONHECIDOS = ("openrouter", "anthropic", "openai")


class ErroDeConfiguracao(Exception):
    """O config.yml tem um ou mais problemas."""

    def __init__(self, problemas: list[str]):
        self.problemas = problemas
        linhas = "\n".join(f"  - {p}" for p in problemas)
        super().__init__(f"O config.yml tem {len(problemas)} problema(s):\n{linhas}")


class _Secao(BaseModel):
    # extra="forbid": campos desconhecidos são recusados (pega erros de digitação).
    model_config = ConfigDict(extra="forbid")


class Assistente(_Secao):
    nome: str = Field(min_length=1, max_length=60)
    descricao: str = ""
    logo: str | None = None
    mensagem_boas_vindas: str = ""
    exemplos_de_perguntas: list[str] = []

    @field_validator("nome")
    @classmethod
    def nome_nao_pode_ser_so_espacos(cls, nome: str) -> str:
        if not nome.strip():
            raise ValueError("o nome não pode ficar vazio")
        return nome.strip()

    @field_validator("logo")
    @classmethod
    def logo_precisa_existir(cls, logo: str | None, info: ValidationInfo) -> str | None:
        if logo is None:
            return None
        raiz = (info.context or {}).get("raiz", RAIZ_DO_PROJETO)
        if not (Path(raiz) / logo).is_file():
            raise ValueError(
                f"o arquivo da logo não foi encontrado: {logo!r}. "
                "Use um caminho a partir da raiz do projeto, por exemplo assets/logo.svg"
            )
        return logo


class Aparencia(_Secao):
    cor_primaria: str
    cor_secundaria: str
    tema: Literal["claro", "escuro"]

    @field_validator("cor_primaria", "cor_secundaria")
    @classmethod
    def formato_da_cor(cls, cor: str) -> str:
        return cores.validar_formato(cor)

    @model_validator(mode="after")
    def cores_legiveis(self) -> "Aparencia":
        problemas = cores.verificar_cores(self.cor_primaria, self.cor_secundaria, self.tema)
        if problemas:
            raise ValueError("\n".join(problemas))
        return self


class Geracao(_Secao):
    temperatura: float = Field(ge=0, le=1)
    max_tokens: int = Field(ge=1, le=4000)
    timeout_segundos: float = Field(ge=5, le=120)
    max_mensagens_historico: int = Field(ge=1, le=50)
    # Espera máxima de uma pergunta, somando tentativas, esperas e fallback.
    tempo_maximo_total_segundos: float = Field(default=60, ge=10, le=180)
    # Quantas vezes o último provedor disponível pode ser chamado por pergunta.
    tentativas_por_provedor: int = Field(default=2, ge=1, le=3)

    @model_validator(mode="after")
    def tempo_total_cobre_uma_tentativa(self) -> "Geracao":
        if self.tempo_maximo_total_segundos < self.timeout_segundos:
            raise ValueError(
                "tempo_maximo_total_segundos precisa ser maior ou igual a timeout_segundos"
            )
        return self


class Limites(_Secao):
    perguntas_por_minuto_total: int = Field(ge=1, le=120)
    perguntas_por_dia_total: int = Field(ge=1, le=5000)
    tamanho_maximo_pergunta: int = Field(ge=100, le=10000)
    identificar_por_ip: StrictBool
    perguntas_por_minuto_por_pessoa: int = Field(ge=1, le=30)
    perguntas_por_dia_por_pessoa: int = Field(ge=1, le=500)

    @model_validator(mode="after")
    def por_pessoa_nao_passa_do_total(self) -> "Limites":
        problemas = []
        if self.perguntas_por_minuto_por_pessoa > self.perguntas_por_minuto_total:
            problemas.append(
                "perguntas_por_minuto_por_pessoa não pode ser maior que perguntas_por_minuto_total"
            )
        if self.perguntas_por_dia_por_pessoa > self.perguntas_por_dia_total:
            problemas.append(
                "perguntas_por_dia_por_pessoa não pode ser maior que perguntas_por_dia_total"
            )
        if problemas:
            raise ValueError("\n".join(problemas))
        return self


class Provedor(_Secao):
    nome: Literal["openrouter", "anthropic", "openai"]
    modelo: str = Field(min_length=1)
    # Só no OpenRouter: outros modelos gratuitos, em ordem, se o principal
    # estiver indisponível ou responder mal.
    modelos_reserva: list[str] = []
    ativo: StrictBool = True

    @model_validator(mode="after")
    def modelos_do_openrouter_gratuitos_e_de_conversa(self) -> "Provedor":
        if self.nome != "openrouter":
            if self.modelos_reserva:
                raise ValueError("modelos_reserva só vale para o provedor openrouter")
            return self
        todos = [self.modelo, *self.modelos_reserva]
        repetidos = sorted({m for m in todos if todos.count(m) > 1})
        if repetidos:
            raise ValueError(f"modelo repetido no openrouter: {', '.join(repetidos)}")
        problemas = [
            f"{modelo!r}: {motivo}"
            for modelo in todos
            if (motivo := motivo_para_recusar_id(modelo))
        ]
        if problemas:
            raise ValueError("; ".join(problemas))
        return self


class Configuracao(_Secao):
    assistente: Assistente
    aparencia: Aparencia
    instrucoes: str
    geracao: Geracao
    limites: Limites
    provedores: list[Provedor] = Field(min_length=1)

    @field_validator("instrucoes")
    @classmethod
    def instrucoes_nao_podem_ficar_vazias(cls, instrucoes: str) -> str:
        if not instrucoes.strip():
            raise ValueError("as instruções não podem ficar vazias")
        return instrucoes.strip()

    @field_validator("provedores")
    @classmethod
    def provedores_validos(cls, provedores: list[Provedor]) -> list[Provedor]:
        nomes = [p.nome for p in provedores]
        repetidos = sorted({n for n in nomes if nomes.count(n) > 1})
        if repetidos:
            raise ValueError(f"provedor repetido: {', '.join(repetidos)}. Cada um só pode aparecer uma vez")
        if not any(p.ativo for p in provedores):
            raise ValueError("pelo menos um provedor precisa estar com ativo: true")
        return provedores

    @property
    def provedores_ativos(self) -> list[Provedor]:
        """Provedores ligados, na ordem de preferência."""
        return [p for p in self.provedores if p.ativo]


# ---------- Mensagens de erro em português ----------

def _traduzir(erro: dict) -> str:
    """Transforma um erro técnico do Pydantic em uma frase simples."""
    tipo = erro["type"]
    ctx = erro.get("ctx", {})

    if tipo == "missing":
        return "campo obrigatório que está faltando"
    if tipo == "extra_forbidden":
        return "campo desconhecido. Confira se o nome foi digitado certo"
    if tipo in ("greater_than_equal", "greater_than"):
        return f"valor {erro['input']!r} é pequeno demais. O mínimo é {ctx['ge' if 'ge' in ctx else 'gt']}"
    if tipo in ("less_than_equal", "less_than"):
        return f"valor {erro['input']!r} é grande demais. O máximo é {ctx['le' if 'le' in ctx else 'lt']}"
    if tipo == "string_too_short":
        return "não pode ficar vazio"
    if tipo == "string_too_long":
        return f"texto longo demais. O máximo é {ctx['max_length']} caracteres"
    if tipo == "too_short":
        return f"precisa ter pelo menos {ctx['min_length']} item(ns)"
    if tipo == "literal_error":
        opcoes = str(ctx["expected"]).replace(" or ", " ou ")
        return f"valor {erro['input']!r} não é aceito. Use um destes: {opcoes}"
    if tipo in ("int_parsing", "int_type", "int_from_float"):
        return f"valor {erro['input']!r} precisa ser um número inteiro (sem vírgula)"
    if tipo in ("float_parsing", "float_type"):
        return f"valor {erro['input']!r} precisa ser um número (use ponto: 0.5)"
    if tipo in ("bool_type", "bool_parsing"):
        return f"valor {erro['input']!r} precisa ser true ou false"
    if tipo in ("string_type",):
        return "precisa ser um texto (coloque entre aspas)"
    if tipo in ("model_type", "dict_type"):
        return "precisa ser uma seção com campos dentro (confira a indentação)"
    if tipo == "list_type":
        return "precisa ser uma lista (itens começando com '- ')"
    if tipo == "value_error":
        return str(ctx.get("error", erro["msg"]))
    return erro["msg"]


def _local(erro: dict) -> str:
    """Monta o nome do campo, por exemplo: provedores[2].nome"""
    texto = ""
    for parte in erro["loc"]:
        if isinstance(parte, int):
            texto += f"[{parte + 1}]"
        else:
            texto += f".{parte}" if texto else str(parte)
    return texto


def _problemas_do_pydantic(erro: ValidationError) -> list[str]:
    problemas = []
    for item in erro.errors():
        local = _local(item)
        for frase in _traduzir(item).split("\n"):
            # As mensagens de cores já dizem o campo (ex.: "aparencia.cor_primaria = ...").
            if frase.startswith(f"{local}."):
                problemas.append(frase)
            else:
                problemas.append(f"{local}: {frase}" if local else frase)
    return problemas


# ---------- Leitura do arquivo ----------

def validar_dados(dados: object, raiz: Path = RAIZ_DO_PROJETO) -> Configuracao:
    """Valida dados já lidos do YAML. Útil para testes."""
    if not isinstance(dados, dict):
        raise ErroDeConfiguracao(["o arquivo está vazio ou não tem o formato esperado (seções com campos)"])
    try:
        return Configuracao.model_validate(dados, context={"raiz": raiz})
    except ValidationError as erro:
        raise ErroDeConfiguracao(_problemas_do_pydantic(erro)) from None


def carregar_configuracao(caminho: Path = CAMINHO_PADRAO) -> Configuracao:
    """Lê e valida o config.yml. Lança ErroDeConfiguracao se houver problemas."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroDeConfiguracao([f"arquivo não encontrado: {caminho}"])

    try:
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except yaml.YAMLError as erro:
        marca = getattr(erro, "problem_mark", None)
        onde = f" (linha {marca.line + 1}, coluna {marca.column + 1})" if marca else ""
        raise ErroDeConfiguracao(
            [f"o arquivo não é um YAML válido{onde}. Confira a indentação (2 espaços, sem TAB) e as aspas"]
        ) from None

    return validar_dados(dados, raiz=caminho.parent)
