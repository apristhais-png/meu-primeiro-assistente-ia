// Navegação da apresentação (docs/apresentacao/index.md).
// Teclado: ← → PageUp PageDown Espaço Home End, N (notas), F (tela cheia).
// Toque: deslizar para os lados. O endereço guarda o slide atual (#slide-3).
(function () {
  "use strict";

  const deck = document.getElementById("deck");
  if (!deck) return;

  const slides = Array.from(deck.querySelectorAll(".slide"));
  const anterior = document.getElementById("anterior");
  const proximo = document.getElementById("proximo");
  const contador = document.getElementById("contador");
  const progresso = document.getElementById("progresso");
  const botaoNotas = document.getElementById("botao-notas");
  const painelNotas = document.getElementById("painel-notas");
  const notasTitulo = document.getElementById("notas-titulo");
  const notasTexto = document.getElementById("notas-texto");
  const botaoJanela = document.getElementById("janela-notas");
  const botaoTelaCheia = document.getElementById("tela-cheia");

  let atual = 0;
  let janelaNotas = null;

  function lerSlideDoEndereco() {
    const achado = /^#slide-(\d+)$/.exec(window.location.hash);
    const numero = achado ? Number(achado[1]) - 1 : 0;
    return Math.min(Math.max(numero, 0), slides.length - 1);
  }

  function notasDe(indice) {
    const aside = slides[indice].querySelector(".notas");
    return aside ? aside.innerHTML : "";
  }

  function tituloDe(indice) {
    return slides[indice].dataset.titulo || `Slide ${indice + 1}`;
  }

  function atualizarJanelaNotas() {
    if (!janelaNotas || janelaNotas.closed) return;
    const doc = janelaNotas.document;
    doc.getElementById("titulo").textContent = `${atual + 1} de ${slides.length}: ${tituloDe(atual)}`;
    doc.getElementById("texto").innerHTML = notasDe(atual);
    doc.getElementById("seguinte").textContent =
      atual + 1 < slides.length ? `Próximo: ${tituloDe(atual + 1)}` : "Este é o último slide.";
  }

  function mostrar(indice, { atualizarEndereco = true } = {}) {
    atual = Math.min(Math.max(indice, 0), slides.length - 1);
    slides.forEach((slide, i) => {
      const ativo = i === atual;
      slide.classList.toggle("ativo", ativo);
      slide.setAttribute("aria-hidden", ativo ? "false" : "true");
      slide.inert = !ativo;
    });
    contador.textContent = `${atual + 1} de ${slides.length}`;
    progresso.style.width = `${((atual + 1) / slides.length) * 100}%`;
    anterior.disabled = atual === 0;
    proximo.disabled = atual === slides.length - 1;
    notasTitulo.textContent = `Notas: ${tituloDe(atual)}`;
    notasTexto.innerHTML = notasDe(atual);
    atualizarJanelaNotas();
    if (atualizarEndereco) {
      history.replaceState(null, "", `#slide-${atual + 1}`);
    }
  }

  function alternarNotas() {
    const abrir = painelNotas.hidden;
    painelNotas.hidden = !abrir;
    botaoNotas.setAttribute("aria-pressed", String(abrir));
    botaoNotas.textContent = abrir ? "Esconder notas" : "Mostrar notas";
  }

  function abrirJanelaNotas() {
    if (janelaNotas && !janelaNotas.closed) {
      janelaNotas.focus();
      return;
    }
    janelaNotas = window.open("", "notas-apresentacao", "width=560,height=620");
    if (!janelaNotas) return; // bloqueado pelo navegador: o painel de notas continua disponível
    const doc = janelaNotas.document;
    doc.open();
    doc.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Notas da apresentação</title>
<style>
  body { margin: 0; padding: 1.5rem; background: #0f2236; color: #f5f8fb;
         font: 1.15rem/1.6 "IBM Plex Sans", system-ui, sans-serif; }
  h1 { font-size: 1.1rem; color: #2bb3a3; margin: 0 0 1rem; }
  #seguinte { color: #a9bcd0; border-top: 1px solid #2a4a6b; padding-top: .75rem; margin-top: 1.25rem; }
  p { margin: 0 0 .9rem; }
</style></head><body>
<h1 id="titulo"></h1><div id="texto"></div><p id="seguinte"></p>
</body></html>`);
    doc.close();
    // As setas também funcionam na janela de notas.
    janelaNotas.addEventListener("keydown", teclas);
    atualizarJanelaNotas();
  }

  function alternarTelaCheia() {
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else if (deck.requestFullscreen) {
      deck.requestFullscreen();
      deck.focus();
    }
  }

  // Teclas da apresentação. O tema Material também usa N (próxima página) e
  // F (busca): por isso a apresentação ouve antes (fase de captura) e para a
  // tecla aqui. Fora disso (por exemplo, digitando na busca), nada muda.
  const ACOES = {
    ArrowRight: () => mostrar(atual + 1),
    PageDown: () => mostrar(atual + 1),
    ArrowLeft: () => mostrar(atual - 1),
    PageUp: () => mostrar(atual - 1),
    Home: () => mostrar(0),
    End: () => mostrar(slides.length - 1),
    n: alternarNotas,
    N: alternarNotas,
    f: alternarTelaCheia,
    F: alternarTelaCheia,
  };

  function teclas(evento) {
    const alvo = evento.target;
    if (alvo && (/^(INPUT|TEXTAREA|SELECT)$/.test(alvo.tagName) || alvo.isContentEditable)) return;
    if (evento.altKey || evento.ctrlKey || evento.metaKey) return;
    let acao = ACOES[evento.key];
    if (evento.key === " " && deck.contains(document.activeElement) && !(alvo && alvo.tagName === "BUTTON")) {
      acao = ACOES.ArrowRight;
    }
    if (!acao) return;
    evento.preventDefault();
    evento.stopPropagation();
    acao();
  }

  // Deslizar no celular.
  let inicioX = null;
  deck.addEventListener("touchstart", (e) => { inicioX = e.touches[0].clientX; }, { passive: true });
  deck.addEventListener("touchend", (e) => {
    if (inicioX === null) return;
    const diferenca = e.changedTouches[0].clientX - inicioX;
    if (Math.abs(diferenca) > 50) mostrar(atual + (diferenca < 0 ? 1 : -1));
    inicioX = null;
  });

  anterior.addEventListener("click", () => mostrar(atual - 1));
  proximo.addEventListener("click", () => mostrar(atual + 1));
  botaoNotas.addEventListener("click", alternarNotas);
  botaoJanela.addEventListener("click", abrirJanelaNotas);
  botaoTelaCheia.addEventListener("click", alternarTelaCheia);
  window.addEventListener("keydown", teclas, true);
  document.addEventListener("fullscreenchange", () => {
    botaoTelaCheia.textContent = document.fullscreenElement ? "Sair da tela cheia" : "Tela cheia";
  });
  window.addEventListener("hashchange", () => mostrar(lerSlideDoEndereco(), { atualizarEndereco: false }));
  window.addEventListener("beforeunload", () => {
    if (janelaNotas && !janelaNotas.closed) janelaNotas.close();
  });

  mostrar(lerSlideDoEndereco(), { atualizarEndereco: false });
})();
