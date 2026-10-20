"""Executa o pipeline completo e mostra um resumo.

Uso (na pasta do projeto):
    python -m pipeline                 # baixa da API do IBGE (precisa de internet)
    python -m pipeline --cache dados/ibge_4714_2022.json   # reaproveita o download
    python -m pipeline --csv dados/municipios.csv          # salva o resultado

A pasta dados/ fica fora do Git (veja .gitignore).
"""

import argparse
import logging
import sys
from pathlib import Path

from pipeline.extracao import ErroDeExtracao, extrair
from pipeline.fonte import FONTE_CITACAO, url_da_consulta
from pipeline.indicadores import calcular, densidades_inconsistentes
from pipeline.transformacao import agregar, montar_dataframe, para_csv
from pipeline.validacao import ErroDeValidacao, validar


def formatar(valor) -> str:
    """Número no padrão brasileiro: 1.234.567 ou 1.234,56."""
    if valor is None:
        return "—"
    if isinstance(valor, int) or float(valor).is_integer():
        return f"{int(valor):,}".replace(",", ".")
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline IBGE: extração → validação → transformação → indicadores")
    parser.add_argument("--cache", type=Path, help="arquivo JSON para guardar/reaproveitar o download")
    parser.add_argument("--csv", type=Path, help="salvar o resultado em CSV")
    args = parser.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    print(f"Fonte: {FONTE_CITACAO}\nURL: {url_da_consulta()}\n")
    try:
        validados = validar(extrair(cache=args.cache))
    except (ErroDeExtracao, ErroDeValidacao) as erro:
        print(f"[ERRO] {erro}")
        return 1

    df = montar_dataframe(validados.registros)
    print(f"[OK] Qualidade: {validados.relatorio.resumo()}")
    print(f"[OK] Unidades informadas pela API: {validados.unidades}")
    inconsistentes = densidades_inconsistentes(df)
    print(f"[{'OK' if inconsistentes.empty else 'ATENÇÃO'}] Densidades que não batem com população ÷ área: {len(inconsistentes)}")

    print("\nIndicadores (Brasil):")
    for indicador in calcular(df, df).values():
        detalhe = f" — {indicador.detalhe}" if indicador.detalhe else ""
        print(f"  {indicador.definicao.nome}: {formatar(indicador.valor)} {indicador.definicao.unidade}{detalhe}")

    print("\nPopulação por região:")
    for linha in agregar(df, "regiao").itertuples():
        print(f"  {linha.regiao}: {formatar(int(linha.populacao))} pessoas em {linha.municipios} municípios")

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        args.csv.write_bytes(para_csv(df))
        print(f"\nCSV salvo em {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
