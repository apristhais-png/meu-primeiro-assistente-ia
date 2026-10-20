"""Confere o dashboard com os dados REAIS do IBGE (usado no workflow api-ibge.yml).

Uso (na pasta do projeto, com internet):
    python -m pipeline --cache dados/ibge_4714_2022.json   # baixa uma vez
    python scripts/conferir_dashboard.py                   # abre a tela e confere
    python scripts/conferir_dashboard.py --fotos fotos/    # também tira fotos (precisa do Playwright)

1. Executa a tela com o AppTest do Streamlit (sem navegador), sem simulação:
   os dados vêm da cópia local do download real. Mostra os indicadores e
   falha se a tela tiver qualquer erro.
2. Com --fotos, sobe o Streamlit de verdade e fotografa a página no tamanho
   de computador e de celular.
"""

import argparse
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

APP = RAIZ / "dashboard" / "app.py"


def conferir_tela() -> int:
    from streamlit.testing.v1 import AppTest

    tela = AppTest.from_file(str(APP), default_timeout=300).run()
    if tela.exception:
        print(f"[ERRO] a tela quebrou: {tela.exception[0].value}")
        return 1
    if tela.error:
        print(f"[ERRO] a tela mostrou um erro: {tela.error[0].value}")
        return 1
    print(f"[OK] {tela.title[0].value}")
    for metrica in tela.metric:
        complemento = f" ({metrica.delta})" if metrica.delta else ""
        print(f"  {metrica.label}: {metrica.value}{complemento}")
    print(f"[OK] gráficos: {len(tela.get('plotly_chart'))}; botões de download: {len(tela.get('download_button'))}")

    tela.multiselect(key="regioes").set_value(["Sudeste"]).run()
    tela.multiselect(key="ufs").set_value(["SP"]).run()
    metricas = {m.label: m.value for m in tela.metric}
    print(f"[OK] filtro Sudeste + SP: {metricas['Municípios']} municípios, {metricas['População total']}")
    return 1 if tela.exception else 0


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fotografar(pasta: Path) -> int:
    from playwright.sync_api import sync_playwright

    pasta.mkdir(parents=True, exist_ok=True)
    porta = _porta_livre()
    servidor = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(APP),
            "--server.headless",
            "true",
            "--server.port",
            str(porta),
            "--server.address",
            "127.0.0.1",
        ],
        cwd=RAIZ,
    )
    try:
        endereco = f"http://127.0.0.1:{porta}"
        for _ in range(60):
            try:
                urllib.request.urlopen(f"{endereco}/_stcore/health", timeout=2)
                break
            except OSError:
                time.sleep(1)
        with sync_playwright() as p:
            navegador = p.chromium.launch()
            for nome, largura, altura in [("computador", 1280, 3200), ("celular", 390, 5600)]:
                pagina = navegador.new_page(viewport={"width": largura, "height": altura})
                pagina.goto(endereco, wait_until="networkidle")
                pagina.wait_for_selector("text=Qualidade dos dados", timeout=120_000)
                pagina.wait_for_timeout(3000)
                largura_real = pagina.evaluate("document.documentElement.scrollWidth")
                pagina.screenshot(path=pasta / f"dashboard-{nome}.png")
                print(f"[OK] foto {nome}: largura da página {largura_real}px (tela de {largura}px)")
                if largura_real > largura:
                    print("[ERRO] a página passa da largura da tela (rolagem horizontal)")
                    return 1
            navegador.close()
    finally:
        servidor.terminate()
        servidor.wait(timeout=30)
    return 0


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fotos", type=Path, help="pasta para salvar as fotos da tela")
    args = parser.parse_args(argumentos)
    resultado = conferir_tela()
    if resultado == 0 and args.fotos:
        resultado = fotografar(args.fotos)
    return resultado


if __name__ == "__main__":
    sys.exit(main())
