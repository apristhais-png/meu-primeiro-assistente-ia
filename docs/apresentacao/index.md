---
title: Apresentação
description: Apresentação de 7 slides do projeto Professor de Dados e Brasil em Dados (Censo 2022), com notas para quem apresenta.
hide:
  - navigation
  - toc
---

<link rel="stylesheet" href="apresentacao.css">

<div class="deck" id="deck" tabindex="-1" aria-roledescription="apresentação" aria-label="Apresentação do projeto, 7 slides">
<div class="deck-palco" id="palco">
<section class="slide slide-abertura" aria-roledescription="slide" aria-label="Slide 1 de 7: abertura" data-titulo="Dois produtos, um repositório">
<div class="slide-corpo">
<p class="abertura-projeto">Projeto acadêmico de Engenharia de Dados e IA</p>
<h2 class="abertura-titulo">Dois produtos,<br>um repositório</h2>
<div class="abertura-produtos">
<div class="produto">
<p class="produto-nome">Professor de Dados</p>
<p class="produto-texto">Um chat que ensina dados, Python, SQL e IA, adaptado ao nível de quem pergunta. Publicado no Render.</p>
</div>
<div class="produto">
<p class="produto-nome">Brasil em Dados</p>
<p class="produto-texto">Pipeline com os dados oficiais do Censo 2022 do IBGE e um dashboard interativo.</p>
</div>
</div>
</div>
<aside class="notas" hidden>
<p>Este projeto junta dois produtos de Engenharia de Dados e IA no mesmo repositório: um chatbot que ensina dados e IA e um pipeline com dashboard sobre o Censo 2022 do IBGE.</p>
<p>Os dois foram construídos com práticas profissionais: ambiente reproduzível, testes, integração contínua e documentação. Tempo sugerido: 45 segundos.</p>
</aside>
</section>
<section class="slide" aria-roledescription="slide" aria-label="Slide 2 de 7: arquitetura" data-titulo="Arquitetura">
<div class="slide-corpo">
<h2 class="slide-titulo">Dois caminhos que não se cruzam</h2>
<p class="slide-sub">Um produto não importa o outro, e há testes que conferem essa separação.</p>
<div class="trilhos">
<div class="trilho">
<p class="trilho-nome">Professor de Dados</p>
<ol class="trilho-etapas">
<li>Pergunta no navegador</li>
<li>Tela em Gradio</li>
<li>Limites de uso no servidor</li>
<li>Tutor: nível e modo de estudo</li>
<li>Modelos gratuitos do OpenRouter, com reservas</li>
</ol>
<p class="trilho-destino">Publicado no Render com o <code>requirements.txt</code></p>
</div>
<div class="trilho trilho-dados">
<p class="trilho-nome">Brasil em Dados</p>
<ol class="trilho-etapas">
<li>API do IBGE, tabela 4714</li>
<li>Requests: busca com tempo limite</li>
<li>Pydantic: confere o formato</li>
<li>Pandas: organiza e calcula</li>
<li>Streamlit e Plotly: o dashboard</li>
</ol>
<p class="trilho-destino">Bibliotecas próprias, que o Render não instala</p>
</div>
</div>
</div>
<aside class="notas" hidden>
<p>Os dois produtos são independentes: um não importa o outro, e há testes que conferem isso.</p>
<p>O chatbot vai para o Render; o pipeline e o dashboard rodam com bibliotecas separadas, que o Render não instala. Mostrar a página Arquitetura e pastas se houver tempo. Tempo sugerido: 1 minuto.</p>
</aside>
</section>
<section class="slide" aria-roledescription="slide" aria-label="Slide 3 de 7: Professor de Dados" data-titulo="Professor de Dados">
<div class="slide-corpo slide-duas-colunas">
<div>
<h2 class="slide-titulo">Professor de Dados</h2>
<p class="slide-sub">Ensina no ritmo de quem pergunta.</p>
<dl class="fatos">
<div><dt>Seu nível</dt><dd>Iniciante, intermediário ou avançado</dd></div>
<div><dt>Modo de estudo</dt><dd>Explicação, exercício prático ou revisão</dd></div>
<div><dt>Respostas</dt><dd>Só modelos gratuitos, conferidos no catálogo antes de cada uso</dd></div>
<div><dt>Proteção</dt><dd>20 perguntas por minuto e 500 por dia, conferidas no servidor</dd></div>
</dl>
</div>
<figure class="captura">
<img src="../entrega-final/img/chatbot-computador.png" alt="Tela do Professor de Dados com os seletores de nível e modo de estudo" loading="lazy">
<figcaption>A tela real, com os seletores de nível e modo.</figcaption>
</figure>
</div>
<aside class="notas" hidden>
<p>A pessoa escolhe o nível e o modo. As respostas vêm de modelos gratuitos do OpenRouter, com troca automática de provedor em falhas temporárias.</p>
<p>Demonstração: no chatbot publicado, escolher Iniciante e Exercício prático e perguntar "Me passe um exercício sobre SELECT com WHERE". Falar dos limites no servidor e de que nenhuma chave fica no código. Tempo sugerido: 1 minuto e 30 segundos.</p>
</aside>
</section>
<section class="slide slide-numeros" aria-roledescription="slide" aria-label="Slide 4 de 7: pipeline do IBGE" data-titulo="Pipeline do IBGE">
<div class="slide-corpo">
<h2 class="slide-titulo">O Censo 2022, conferido município por município</h2>
<p class="numero-gigante"><span class="numero-valor">5.570</span> <span class="numero-de">de 5.570</span></p>
<p class="numero-legenda">municípios válidos na API real do IBGE</p>
<div class="numeros-apoio">
<p><strong>203.080.756</strong> pessoas no Brasil</p>
<p><strong>0</strong> densidades fora do esperado</p>
<p><strong>3,1 s</strong> para a resposta da API</p>
</div>
<p class="fonte">Execução no GitHub Actions em 21/10/2026, registrada na entrega final.</p>
</div>
<aside class="notas" hidden>
<p>O pipeline segue quatro etapas: Requests busca os dados na API pública do IBGE, Pydantic confere o formato e cada município, Pandas organiza e calcula, e os indicadores têm definição, fórmula e unidade.</p>
<p>Problemas recuperáveis são contados no relatório de qualidade; nada é descartado em silêncio. Mostrar o log da execução real, se perguntarem. Tempo sugerido: 1 minuto e 30 segundos.</p>
</aside>
</section>
<section class="slide" aria-roledescription="slide" aria-label="Slide 5 de 7: dashboard" data-titulo="Dashboard">
<div class="slide-corpo slide-duas-colunas">
<div>
<h2 class="slide-titulo">Brasil em Dados</h2>
<p class="slide-sub">Filtros por região, UF e município atualizam tudo de uma vez.</p>
<ul class="lista">
<li>Seis indicadores, cada um com definição e fórmula</li>
<li>Três gráficos Plotly e a tabela com o código IBGE</li>
<li>Download do CSV dos dados filtrados</li>
<li>Cache: mexer nos filtros não baixa nada de novo</li>
</ul>
<p class="destaque-filtro">Sudeste + SP: <strong>645 municípios</strong>, 44.411.238 pessoas</p>
</div>
<figure class="grafico" aria-label="População por região no Censo 2022">
<figcaption>População por região, Censo 2022</figcaption>
<ul class="barras">
<li style="--valor: 84840113"><span class="barra-nome">Sudeste</span><span class="barra"></span><span class="barra-valor">84.840.113</span></li>
<li style="--valor: 54658515"><span class="barra-nome">Nordeste</span><span class="barra"></span><span class="barra-valor">54.658.515</span></li>
<li style="--valor: 29937706"><span class="barra-nome">Sul</span><span class="barra"></span><span class="barra-valor">29.937.706</span></li>
<li style="--valor: 17354884"><span class="barra-nome">Norte</span><span class="barra"></span><span class="barra-valor">17.354.884</span></li>
<li style="--valor: 16289538"><span class="barra-nome">Centro-Oeste</span><span class="barra"></span><span class="barra-valor">16.289.538</span></li>
</ul>
</figure>
</div>
<aside class="notas" hidden>
<p>Mostrar ao vivo: os cartões de indicadores (o "?" mostra a fórmula), filtrar Região Sudeste e depois UF SP, os três gráficos, a tabela, o botão Baixar CSV e a seção Qualidade dos dados.</p>
<p>Mexer nos filtros não baixa nada de novo: os dados ficam em cache. Como o Censo tem um único ano, o painel não inventa tendências. Tempo sugerido: 1 minuto e 30 segundos.</p>
</aside>
</section>
<section class="slide" aria-roledescription="slide" aria-label="Slide 6 de 7: qualidade e ambiente" data-titulo="Qualidade e ambiente">
<div class="slide-corpo">
<h2 class="slide-titulo">Tudo conferido antes de ir para o ar</h2>
<div class="qualidade">
<div class="qualidade-numero"><p class="qualidade-valor">690</p><p>testes automáticos, sem IA nem internet de verdade</p></div>
<div class="qualidade-numero"><p class="qualidade-valor">98,32%</p><p>de cobertura no pipeline e no dashboard (mínimo exigido: 80%)</p></div>
</div>
<div class="ferramentas">
<p><strong>Ambiente:</strong> pyenv escolhe o Python 3.11, pipx instala o Poetry e o Poetry instala as versões exatas do <code>poetry.lock</code>.</p>
<p><strong>Qualidade:</strong> Ruff padroniza o código; o GitHub Actions roda tudo em cada Pull Request, e o Render só publica depois que os testes passam.</p>
<p><strong>Documentação:</strong> este site MkDocs Material, publicado no GitHub Pages a partir da <code>main</code>.</p>
</div>
</div>
<aside class="notas" hidden>
<p>São 690 testes automáticos, sem nenhuma IA ou internet de verdade: tudo é simulado. A cobertura do pipeline e do dashboard é de 98%, e o mínimo exigido é 80%.</p>
<p>Opcional: mostrar a aba Actions com as execuções verdes e a página Windows 11 passo a passo. Tempo sugerido: 1 minuto e 45 segundos.</p>
</aside>
</section>
<section class="slide slide-fechamento" aria-roledescription="slide" aria-label="Slide 7 de 7: segurança e próximos passos" data-titulo="Segurança e próximos passos">
<div class="slide-corpo slide-duas-colunas">
<div>
<h2 class="slide-titulo">Seguro por padrão</h2>
<ul class="lista">
<li>Nenhuma chave nos arquivos nem nos 52 commits do histórico</li>
<li>O arquivo <code>.env</code> nunca foi enviado ao GitHub</li>
<li>Workflows sem segredos; o chat só troca texto</li>
<li>Um risco conhecido e registrado: o Pillow, sem correção compatível ainda, sem uso de imagens pelas pessoas</li>
</ul>
</div>
<div>
<h3 class="slide-titulo-menor">Próximos passos</h3>
<ul class="lista">
<li>Publicar o dashboard</li>
<li>Acrescentar uma série histórica do IBGE para comparar anos</li>
<li>Ligar os limites por pessoa no chatbot</li>
</ul>
<p class="enderecos">Documentação: apristhais-png.github.io/meu-primeiro-assistente-ia<br>Código: github.com/apristhais-png/meu-primeiro-assistente-ia</p>
</div>
</div>
<aside class="notas" hidden>
<p>Nenhuma chave no repositório, nem no histórico; os workflows não usam segredos; o chat só troca texto. A auditoria final encontrou uma vulnerabilidade conhecida numa biblioteca de imagens usada indiretamente, sem correção compatível ainda e sem risco para estes produtos: está registrada com a ação de acompanhamento.</p>
<p>Encerrar com os próximos passos e abrir para perguntas. Tempo sugerido: 45 segundos.</p>
</aside>
</section>
</div>
<div class="deck-controles">
<button type="button" class="botao" id="anterior" aria-label="Slide anterior">Anterior</button>
<p class="contador" id="contador" aria-live="polite">1 de 7</p>
<button type="button" class="botao" id="proximo" aria-label="Próximo slide">Próximo</button>
<span class="controles-espaco"></span>
<button type="button" class="botao botao-discreto" id="botao-notas" aria-pressed="false" aria-controls="painel-notas">Mostrar notas</button>
<button type="button" class="botao botao-discreto" id="janela-notas">Notas em outra janela</button>
<button type="button" class="botao botao-discreto" id="tela-cheia">Tela cheia</button>
</div>
<div class="deck-progresso" aria-hidden="true"><span id="progresso"></span></div>
</div>

<section class="painel-notas" id="painel-notas" hidden aria-label="Notas de apresentação">
<h2 id="notas-titulo">Notas</h2>
<div id="notas-texto"></div>
</section>

<p class="atalhos">Atalhos: setas ← e → (ou Espaço) trocam de slide, <kbd>N</kbd> mostra as notas, <kbd>F</kbd> liga a tela cheia. No celular, deslize para os lados. O roteiro completo está em <a href="../entrega-final/roteiro-apresentacao/">Roteiro de apresentação</a>.</p>

<script src="apresentacao.js" defer></script>
