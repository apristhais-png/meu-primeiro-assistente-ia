# Roteiro de apresentação (5 a 10 minutos)

Sugestão de ordem, tempo e o que mostrar na tela. Os tempos somam cerca de
**8 minutos**; os itens marcados como *opcional* podem sair para ficar em 5.

## Antes de começar (preparação)

- [ ] Abrir o link do Professor de Dados no Render **uns 2 minutos antes**
      (no plano gratuito, a primeira visita depois de um tempo parado demora
      cerca de 1 minuto).
- [ ] Deixar abertos: o repositório no GitHub, a aba **Actions**, o dashboard
      (`poetry run streamlit run dashboard/app.py`) e o site da documentação
      (`poetry run mkdocs serve`).
- [ ] Se a internet do local for instável, ter à mão as fotos desta pasta
      (`docs/entrega-final/img/`) e as do artefato `fotos-dashboard`.

---

## 1. Abertura — o problema e a proposta (≈ 45 s)

> "Este projeto junta dois produtos de Engenharia de Dados e IA no mesmo
> repositório: um **chatbot que ensina** dados e IA e um **pipeline com
> dashboard** sobre o Censo 2022 do IBGE. Os dois foram construídos com
> práticas profissionais: ambiente reproduzível, testes, CI e documentação."

**Mostrar:** a página inicial da documentação (os dois cartões, Produto A e B).

## 2. Arquitetura (≈ 1 min)

> "Os dois produtos são independentes: um não importa o outro, e há testes que
> conferem isso. O chatbot vai para o Render; o pipeline e o dashboard rodam
> com bibliotecas separadas, que o Render não instala."

**Mostrar:** a página *Arquitetura e pastas* (diagrama e estrutura de pastas).

## 3. Produto A — Professor de Dados (≈ 1 min 30 s)

> "A pessoa escolhe o nível (iniciante, intermediário ou avançado) e o modo:
> explicação, exercício ou revisão. As respostas vêm de **modelos gratuitos**
> do OpenRouter, com troca automática de provedor em falhas temporárias."

**Mostrar:** o chatbot publicado. Escolher *Iniciante* + *Exercício prático* e
perguntar: *"Me passe um exercício sobre SELECT com WHERE."*

**Pontos para falar:**

- limites de uso conferidos no servidor (20 por minuto, 500 por dia);
- só modelos de preço zero, conferidos no catálogo antes de cada uso;
- nenhuma chave no código: elas ficam no `.env` ou na aba *Environment* do
  Render.

## 4. Produto B — pipeline do IBGE (≈ 1 min 30 s)

> "O pipeline segue quatro etapas: **Requests** busca os dados na API pública
> do IBGE, **Pydantic** confere o formato e cada município, **Pandas** organiza
> e calcula, e os **indicadores** têm definição, fórmula e unidade."

**Mostrar:** a página *Funcionamento da API* e o log da execução real
(`docs/entrega-final/logs/ci-api-ibge-pipeline.txt`):
"5.570 de 5.570 municípios válidos", "203.080.756 pessoas".

**Ponto para falar:** problemas recuperáveis são **contados** no relatório de
qualidade; nada é descartado em silêncio.

## 5. Dashboard — Streamlit e Plotly (≈ 1 min 30 s)

**Mostrar ao vivo:**

1. Os cartões de indicadores (passar o mouse no **?** para ver a fórmula).
2. Filtrar **Região = Sudeste** e depois **UF = SP**: tudo se atualiza.
3. Os três gráficos (ranking, população e densidade por região/UF).
4. A tabela com o código IBGE e o botão **Baixar CSV**.
5. A seção **Qualidade dos dados**.

> "Mexer nos filtros não baixa nada de novo: os dados ficam em cache. E como o
> Censo tem um único ano, o painel não inventa tendências."

## 6. Qualidade — testes, cobertura, Ruff e CI (≈ 1 min)

> "São **690 testes automáticos**, sem nenhuma IA ou internet de verdade: tudo é
> simulado. A cobertura do pipeline e do dashboard é de **98%** (o mínimo
> exigido é 80%). O Ruff padroniza o código, e o GitHub Actions roda tudo em
> cada Pull Request; o Render só publica depois que os testes passam."

**Mostrar:** a aba **Actions** com as execuções verdes e, *opcional*, o
relatório HTML da cobertura (`htmlcov/index.html`).

## 7. Ambiente e documentação (≈ 45 s) — *opcional*

> "Para instalar: **pyenv** escolhe o Python 3.11, **pipx** instala o **Poetry**
> isolado, e o Poetry instala as versões exatas do `poetry.lock`. A
> documentação é um site **MkDocs Material**, com passo a passo para Windows."

**Mostrar:** a página *Windows 11 passo a passo*.

## 8. Segurança e encerramento (≈ 45 s)

> "Nenhuma chave no repositório, nem no histórico; os workflows só têm
> permissão de leitura; o chat só troca texto. A auditoria final encontrou uma
> vulnerabilidade conhecida numa biblioteca de imagens usada indiretamente, sem
> correção compatível ainda e sem risco para estes produtos: ela está
> registrada com a ação de acompanhamento."

> "Próximos passos: publicar o dashboard e a documentação, e acrescentar uma
> série histórica do IBGE para comparar anos."

---

## Perguntas que podem aparecer

| Pergunta | Resposta curta |
|---|---|
| Por que dois arquivos de dependências (pip e Poetry)? | O Render usa o `requirements.txt`; o Poetry é para o computador. Um teste garante que as versões são iguais. |
| Como vocês sabem que a API real funciona, se os testes são simulados? | Um workflow separado roda o pipeline e o dashboard com a API **real** do IBGE em cada PR do pipeline. |
| E se o modelo gratuito sair do ar? | O app confere o catálogo antes de usar, pula modelos indisponíveis, usa as reservas e depois outros provedores. |
| O que acontece se alguém mandar muitas perguntas? | Os limites por minuto e por dia são conferidos no servidor, antes de chamar a IA. |
| Por que não há gráfico de evolução? | A tabela 4714 tem só o Censo 2022; mostrar tendência seria inventar dados. |
