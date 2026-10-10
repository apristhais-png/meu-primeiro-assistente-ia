# SPEC — Parte 1: Assistente de IA com CI/CD e publicação

> **Status:** aguardando aprovação final. Nenhum código será escrito antes da sua autorização.
>
> **Baseado em:** `IDEIA-parte1.md`
>
> **Decisões já tomadas:**
> - Interface: **Python + Gradio**
> - Ordem dos provedores de IA: **OpenRouter → Anthropic → OpenAI**
> - Arquivo de configuração: **YAML**, com o nome **`config.yml`** (como na apostila)
> - Publicação: **automática a cada push na branch `main`**, só se os testes passarem
>
> **Histórico de revisões:**
> - **Revisão 2:** limites de uso, verificação de chaves mais precisa, versão do Gradio fixada, exclusão de arquivos antigos na publicação, cores personalizadas.
> - **Revisão 3 (esta):**
>   - limites aplicados **no servidor**;
>   - verificação de chaves passa a olhar **todos** os arquivos, inclusive a documentação, sem falso alarme;
>   - versão do Gradio conferida em **todos** os arquivos;
>   - publicação apaga só arquivos que **o projeto controla**;
>   - cores com **verificação de contraste**;
>   - arquivo renomeado para `config.yml`;
>   - códigos alinhados ao checklist: **RF** (requisitos), **T** (testes), **CA** (critérios de aceite) e **P** (passos de implementação).

---

## Glossário rápido (para iniciantes)

| Termo | O que significa |
|---|---|
| **Spec-Driven Development** | Primeiro escrevemos *o que* o sistema deve fazer (esta SPEC). Só depois programamos, sempre conferindo com a SPEC. |
| **Provedor de IA** | Empresa que oferece o modelo de IA pela internet (OpenRouter, Anthropic, OpenAI). |
| **Chave de API** | Uma "senha" que permite ao nosso programa usar a IA do provedor. É secreta e pode gerar cobranças. |
| **Fallback (alternativa)** | Se o primeiro provedor falhar, o sistema tenta o próximo automaticamente. |
| **CI/CD** | *Integração e Entrega Contínuas*: um robô testa o código e, se tudo der certo, publica sozinho. |
| **GitHub Actions** | O robô do GitHub que roda os testes e a publicação. |
| **Hugging Face Spaces** | Serviço gratuito que hospeda o nosso chat e gera um link público. |
| **Secret (segredo)** | Lugar seguro no GitHub ou no Hugging Face para guardar chaves sem que apareçam no código. |
| **Mock (simulação)** | Um "provedor de mentira" usado nos testes, para não gastar dinheiro nem depender da internet. |
| **Servidor** | O computador do Hugging Face onde o nosso código Python roda. O navegador da pessoa só mostra a tela; quem decide e chama a IA é o servidor. |
| **Contraste** | Diferença de claridade entre o texto e o fundo. Pouco contraste deixa o texto difícil de ler. É medido por um número: quanto maior, mais legível (21 é o máximo: preto no branco). |
| **Falso positivo (falso alarme)** | Quando a verificação acusa um problema que não existe, por exemplo, tratar um texto de exemplo como se fosse uma chave real. |

---

## 1. Objetivo do projeto

Criar um **chat de inteligência artificial que ensina Engenharia de Dados e IA de forma simples**, acessível por qualquer pessoa em um **link público no navegador**.

Nesta Parte 1 o foco é ter a **base funcionando de ponta a ponta**, mantendo o projeto **simples para iniciantes**:

1. Um chat simples que conversa usando IA.
2. Personalização (nome, cores, logo, instruções, modelos e limites de uso) **por um único arquivo**, o `config.yml`, sem mexer no código.
3. **Troca automática de provedor** se um deles falhar.
4. **Proteção dos créditos** com limites de uso aplicados no servidor.
5. **Testes automáticos** que impedem a publicação de código ou configuração com erro.
6. **Publicação automática** no Hugging Face Spaces pelo GitHub Actions.
7. **Nenhuma chave de API** dentro do código ou do repositório.

**Fora do escopo agora** (ficam para as próximas partes): base de documentos (RAG), interface profissional, login e histórico de conversas salvo.

---

## 2. Tecnologias utilizadas e o motivo de cada escolha

| Tecnologia | Para que serve | Por que escolhemos |
|---|---|---|
| **Python 3.11** | Linguagem principal | É a linguagem mais usada em Dados e IA, fácil de ler e com ótimas bibliotecas. A versão 3.11 é estável e aceita pelo Hugging Face. |
| **Gradio** | Cria a tela do chat no navegador | Já tem um componente de chat pronto (`ChatInterface`), aceita cores e logo, e o Hugging Face Spaces roda Gradio direto. A versão é **fixada** e precisa ser igual em todos os arquivos (veja a seção 3.2). |
| **PyYAML** | Lê o arquivo `config.yml` | YAML é fácil de ler e aceita comentários (`#`), então dá para explicar cada campo dentro do próprio arquivo. |
| **Pydantic** | Confere se a configuração está correta | Diz exatamente *qual* campo está errado e *por quê* (ex.: "cor inválida", "contraste baixo", "falta o nome"). É isso que impede publicar configuração errada. |
| **openai (biblioteca)** | Conversa com a OpenAI **e** com o OpenRouter | O OpenRouter usa o mesmo "idioma" da OpenAI, então uma biblioteca atende os dois, trocando só o endereço. Menos código. |
| **anthropic (biblioteca)** | Conversa com a Anthropic (Claude) | Biblioteca oficial, a forma mais segura e atualizada de usar o Claude. |
| **python-dotenv** | Lê as chaves de um arquivo `.env` no seu computador | Permite testar localmente sem escrever chaves no código. O `.env` nunca vai para o GitHub. |
| **pytest** | Roda os testes automáticos | Padrão do mercado em Python, simples de escrever e de ler. |
| **Ruff** | Verifica o estilo e erros comuns no código | Muito rápido, pega erros bobos (variável não usada, import faltando) antes dos testes. |
| **GitHub** | Guarda o código e o histórico | Pedido na IDEIA; também é onde o GitHub Actions roda. |
| **GitHub Actions** | Testa e publica automaticamente | Gratuito para repositórios públicos e integrado ao GitHub. |
| **Hugging Face Spaces** | Hospeda o chat com link público | Gratuito, feito para apps de IA, com área própria para segredos. |
| **huggingface_hub** | Envia os arquivos do GitHub para o Space | Mais simples e confiável do que `git push` direto para o Hugging Face (evita erros com imagens e histórico). Envia tudo em **uma única atualização**, então o Space nunca fica "pela metade". |

**Não usamos** banco de dados, Redis ou outros serviços extras. Os contadores dos limites ficam na memória do próprio app. Isso mantém o projeto simples (veja a seção 4.3).

---

## 3. Estrutura de arquivos

```
meu-primeiro-assistente-ia/
├── app.py                      # Ponto de entrada: o Hugging Face roda este arquivo
├── config.yml                  # ⭐ Personalização: nome, cores, logo, instruções, modelos, limites
├── assets/
│   └── logo.svg                # Logo do assistente (SVG, leve e sem problemas no upload)
├── assistente/                 # Código do assistente, separado por responsabilidade
│   ├── __init__.py
│   ├── config.py               # Lê e valida o config.yml
│   ├── cores.py                # Calcula contraste e escolhe a cor do texto dos botões
│   ├── provedores.py           # Fala com OpenRouter, Anthropic e OpenAI
│   ├── limites.py              # Limites de uso, aplicados no servidor
│   ├── chat.py                 # Junta tudo: limites → conversa → fallback entre provedores
│   └── interface.py            # Monta a tela do Gradio usando a configuração
├── scripts/
│   ├── validar_config.py       # Confere o config.yml antes de publicar
│   ├── verificar_segredos.py   # Procura chaves de API reais esquecidas nos arquivos
│   └── publicar.py             # Envia ao Space só o necessário e apaga o que saiu
├── tests/
│   ├── test_config.py          # Configuração
│   ├── test_cores.py           # Contraste e legibilidade
│   ├── test_provedores.py      # Provedores (com simulação)
│   ├── test_limites.py         # Limites de uso
│   ├── test_chat.py            # Conversa e fallback
│   ├── test_interface.py       # Tela
│   ├── test_versoes.py         # Versão do Gradio igual em todos os arquivos
│   ├── test_segredos.py        # Verificação de chaves
│   └── test_publicar.py        # Regras de publicação (o que envia, o que apaga, o que protege)
├── .github/
│   └── workflows/
│       └── ci-deploy.yml       # Robô: testa e depois publica no Hugging Face
├── requirements.txt            # Bibliotecas que o app precisa (única fonte da versão do Gradio)
├── requirements-dev.txt        # Bibliotecas extras só para testes (pytest, ruff), sem Gradio
├── .env.example                # Modelo de .env, SEM chaves reais
├── .gitignore                  # Garante que .env e lixo não subam para o GitHub
├── README.md                   # Explicação do projeto + cabeçalho exigido pelo Hugging Face
├── IDEIA-parte1.md             # Ideia original
└── SPEC-parte1-cicd-deploy.md  # Este documento
```

### 3.1 Por que separar em vários arquivos?
Cada arquivo tem uma única tarefa. Assim fica mais fácil achar um erro, testar cada parte sozinha e trocar uma peça (ex.: um provedor) sem quebrar o resto.

### 3.2 Versão do Gradio igual em todos os arquivos
O Hugging Face instala o Gradio pela versão escrita no **cabeçalho do `README.md`** (`sdk_version`), e não pela do `requirements.txt`. Se forem diferentes, o app pode funcionar no seu computador e quebrar no Space.

Regras:
1. **Uma única fonte da verdade:** a versão é escrita com `==` no `requirements.txt` (ex.: `gradio==X.Y.Z`).
2. O `sdk_version` do `README.md` usa **exatamente** o mesmo número.
3. **Nenhum outro arquivo** fixa uma versão diferente. O `requirements-dev.txt` não lista o Gradio, e o workflow instala tudo a partir do `requirements.txt`.
4. O teste `tests/test_versoes.py` confere tudo isso e **bloqueia a publicação** se algo estiver diferente.
5. **Para atualizar o Gradio:** trocar o número nos **dois** lugares (`requirements.txt` e `README.md`) no mesmo commit.

---

## 4. Configurações do assistente

Tudo que for personalizável fica no `config.yml`. **As chaves de API NÃO ficam aqui** (veja a seção 4.5).

### 4.1 Exemplo do `config.yml` (ilustrativo)

```yaml
# Identidade do assistente
assistente:
  nome: "Professor de Dados"
  descricao: "Aprenda Engenharia de Dados e IA de forma simples."
  logo: "assets/logo.svg"
  mensagem_boas_vindas: "Olá! O que você quer aprender hoje?"
  exemplos_de_perguntas:
    - "O que é um pipeline de dados?"
    - "Qual a diferença entre ETL e ELT?"
    - "O que é um modelo de linguagem?"

# Aparência (cores no formato #RRGGBB)
aparencia:
  cor_primaria: "#2563EB"     # fundo dos botões, bordas e destaques
  cor_secundaria: "#047857"   # links e textos destacados
  tema: "claro"               # "claro" (fundo branco) ou "escuro" (fundo quase preto)

# Como a IA deve se comportar
instrucoes: |
  Você é um professor paciente de Engenharia de Dados e IA.
  Explique com palavras simples, exemplos do dia a dia e passo a passo.
  Responda sempre em português do Brasil.
  Se não souber algo, diga que não sabe.

# Ajustes das respostas
geracao:
  temperatura: 0.5            # 0 = mais previsível, 1 = mais criativo
  max_tokens: 1024            # tamanho máximo da resposta (também limita o custo)
  timeout_segundos: 30        # tempo máximo de espera por provedor
  max_mensagens_historico: 10 # quantas mensagens anteriores enviar para a IA

# Proteção dos créditos (aplicada no servidor; o link é público!)
limites:
  perguntas_por_minuto_por_pessoa: 5
  perguntas_por_dia_por_pessoa: 50
  perguntas_por_dia_total: 500       # soma de todas as pessoas
  tamanho_maximo_pergunta: 2000      # em caracteres

# Provedores, na ordem de preferência (o primeiro é o principal)
provedores:
  - nome: openrouter
    modelo: "meta-llama/llama-3.3-70b-instruct:free"
    ativo: true
  - nome: anthropic
    modelo: "claude-haiku-5-5"
    ativo: true
  - nome: openai
    modelo: "gpt-4o-mini"
    ativo: true
```

> Os nomes dos modelos são exemplos. Eles podem ser trocados no arquivo a qualquer momento, sem mexer no código. Antes de publicar, vamos confirmar no site de cada provedor se o modelo escolhido continua disponível.

### 4.2 Regras de validação (o que o sistema confere)

| Campo | Regra |
|---|---|
| `assistente.nome` | Obrigatório, entre 1 e 60 caracteres. |
| `assistente.logo` | Se informado, o arquivo precisa existir no repositório. |
| `aparencia.cor_*` | Formato `#RRGGBB` (ex.: `#2563EB`) **e** contraste suficiente (veja a seção 4.4). |
| `aparencia.tema` | Só aceita `claro` ou `escuro`. |
| `instrucoes` | Obrigatório e não pode ficar vazio. |
| `geracao.temperatura` | Número entre 0 e 1. |
| `geracao.max_tokens` | Número inteiro entre 1 e 4000. |
| `geracao.timeout_segundos` | Número entre 5 e 120. |
| `limites.perguntas_por_minuto_por_pessoa` | Inteiro entre 1 e 30. |
| `limites.perguntas_por_dia_por_pessoa` | Inteiro entre 1 e 500. |
| `limites.perguntas_por_dia_total` | Inteiro entre 1 e 5000. |
| `limites.tamanho_maximo_pergunta` | Inteiro entre 100 e 10000. |
| `limites` (seção inteira) | **Obrigatória.** Não existe "sem limite": um erro de digitação nunca desliga a proteção. |
| `provedores` | Pelo menos 1 provedor ativo; nomes só podem ser `openrouter`, `anthropic` ou `openai`; sem repetição. |
| Campos desconhecidos | São recusados (pega erros de digitação, como `nomee`). |

### 4.3 Limites de uso no servidor (proteção dos créditos)

**Por que no servidor?** Tudo que roda no navegador pode ser burlado por quem entende um pouco de programação. Por isso, a conferência dos limites acontece **no código Python do servidor**, **antes** de chamar qualquer IA. Se o limite foi atingido, a IA simplesmente não é chamada e nenhum crédito é gasto.

**Como funciona, passo a passo:**
1. Chega uma pergunta.
2. O servidor confere o **tamanho** da pergunta. Se for grande demais, recusa.
3. O servidor identifica a pessoa pelo **endereço de internet (IP)** da conexão. Recarregar a página não zera o contador.
4. O servidor confere o limite **por minuto** e **por dia** dessa pessoa, e o limite **total do dia** do app.
5. Se tudo estiver dentro do limite, conta +1 e só então chama a IA.

**Mensagens que a pessoa vê:**

| Situação | Mensagem |
|---|---|
| Pergunta longa demais | *"Sua pergunta ficou muito longa. Tente resumir em até 2000 caracteres."* |
| Muitas perguntas no minuto | *"Você fez muitas perguntas seguidas. Aguarde um minuto e tente de novo."* |
| Limite diário da pessoa | *"Você atingiu o limite de perguntas de hoje. Volte amanhã!"* |
| Limite total do app | *"O limite de uso de hoje foi atingido. Volte amanhã!"* |

**Escolhas para manter simples:**
- Os contadores ficam **na memória** do app, sem banco de dados. Se o Space reiniciar, os contadores voltam a zero. Isso é aceitável porque existe uma segunda proteção: o **limite de gastos no painel dos provedores** (seção 7.3).
- O "dia" vira à meia-noite no horário de Brasília.
- O IP é usado **só** para contar perguntas: **não** aparece nos logs e não é salvo em arquivo.

**Outras proteções de custo:**
- O provedor principal (OpenRouter) usa um **modelo gratuito** (terminado em `:free`).
- O `max_tokens` limita o tamanho, e portanto o custo, de cada resposta.
- O app atende **poucas perguntas ao mesmo tempo**, e as outras esperam na fila. Isso evita picos de gasto.
- **Limite de gastos em cada provedor** (OpenRouter, Anthropic e OpenAI permitem isso). É a proteção mais forte, porque funciona até se o código tiver algum erro.

### 4.4 Cores personalizadas com contraste e legibilidade

Qualquer cor `#RRGGBB` é aceita, **desde que dê para ler**. Usamos a regra internacional de acessibilidade **WCAG 2.1, nível AA**:
- textos precisam de contraste de pelo menos **4.5 : 1**;
- bordas e contornos precisam de pelo menos **3 : 1**.

**Onde cada cor é usada e o que é conferido:**

| Cor | Onde aparece | O que o sistema confere |
|---|---|---|
| `cor_primaria` | **Fundo dos botões** | O sistema escolhe **sozinho** a cor do texto do botão, **branco ou preto**, o que ficar mais legível. O contraste precisa ser ≥ 4.5 : 1. |
| `cor_primaria` | Bordas e contorno do campo selecionado | Contraste ≥ 3 : 1 contra o fundo da página. |
| `cor_secundaria` | Links e textos destacados | Contraste ≥ 4.5 : 1 contra o fundo da página. |

**Fundo da página:** branco `#FFFFFF` no tema `claro`, e quase preto `#0B0F19` no tema `escuro`.

**Se a cor não passar**, a validação explica em português o que fazer. Exemplo:
> ❌ `aparencia.cor_secundaria = #10B981`: contraste 2.5 : 1 com o fundo claro (mínimo 4.5 : 1). Use uma cor **mais escura**, por exemplo `#047857`.

**Atenção ao trocar o tema:** uma cor escura que funciona no tema `claro` pode ficar ilegível no tema `escuro`. A validação avisa nesse caso também.

**Como as cores entram na tela:** o Gradio trabalha com paletas prontas. O arquivo `assistente/interface.py` aplica as cores do `config.yml` por cima do tema padrão. Para você, nada muda: basta escrever o código da cor.

### 4.5 Segurança: onde ficam as chaves de API

As chaves são lidas de **variáveis de ambiente**, nunca do código:

| Variável | Onde configurar |
|---|---|
| `OPENROUTER_API_KEY` | **Hugging Face → Space → Settings → Secrets** (e no `.env` local, se quiser testar no seu computador) |
| `ANTHROPIC_API_KEY` | Mesmo lugar |
| `OPENAI_API_KEY` | Mesmo lugar |
| `HF_TOKEN` | **GitHub → Settings → Secrets and variables → Actions → Secrets** (usado só para publicar) |
| `HF_SPACE_ID` | **GitHub → Settings → Secrets and variables → Actions → Variables** (ex.: `seu-usuario/professor-de-dados`) |

Regras:
- O arquivo `.env` está no `.gitignore` e **nunca** é enviado ao GitHub.
- O `.env.example` mostra apenas os **nomes** das variáveis, com valores claramente falsos (ex.: `SUA_CHAVE_AQUI`).
- Um provedor sem chave é **pulado automaticamente** (com aviso no log), sem derrubar o app.
- Mensagens de erro e logs **nunca** mostram a chave.

---

## 5. Requisitos funcionais (RF)

*O que o assistente precisa fazer. É a lista de capacidades que a pessoa usuária ou você vão perceber.*

| # | Requisito | Descrição simples |
|---|---|---|
| RF1 | **Chat no navegador** | A pessoa digita uma pergunta e recebe a resposta da IA na mesma tela. |
| RF2 | **Memória da conversa atual** | A IA lembra das últimas mensagens *da conversa aberta* (limitado por `max_mensagens_historico`). Ao recarregar a página, a conversa recomeça (histórico salvo fica para depois). |
| RF3 | **Instruções do assistente** | O texto de `instrucoes` é enviado em toda conversa para definir o jeito de responder. |
| RF4 | **Personalização visual** | Nome, descrição, logo, cores, tema, mensagem de boas-vindas e perguntas de exemplo vêm do `config.yml`. |
| RF5 | **Escolha de provedor por ordem** | Usa o primeiro provedor ativo e com chave configurada. |
| RF6 | **Fallback automático** | Se o provedor falhar (fora do ar, sem crédito, tempo esgotado, chave inválida), tenta o próximo da lista. |
| RF7 | **Mensagem amigável quando tudo falha** | Se nenhum provedor responder, mostra: *"Desculpe, não consegui responder agora. Tente novamente em alguns minutos."* Sem erros técnicos. |
| RF8 | **Validação da configuração** | Ao iniciar, o app confere o `config.yml`. Se houver erro, mostra claramente qual campo está errado e como corrigir. |
| RF9 | **Script de validação** | `python scripts/validar_config.py` confere o arquivo antes de publicar (usado também pelo GitHub Actions). |
| RF10 | **Logs simples e sem dados sensíveis** | Registra qual provedor respondeu e quais falharam, e quando um limite foi atingido. **Nunca** registra chaves, IPs ou o conteúdo das conversas. |
| RF11 | **Limites de uso no servidor** | Limites por minuto e por dia de cada pessoa (identificada pelo IP) e limite total diário do app, conferidos no servidor **antes** de chamar a IA (seção 4.3). |
| RF12 | **Pergunta muito longa é recusada** | Perguntas maiores que `tamanho_maximo_pergunta` são recusadas com uma mensagem amigável, sem chamar a IA. |
| RF13 | **Cores personalizadas legíveis** | Qualquer `#RRGGBB` é aceito se passar no teste de contraste. A cor do texto dos botões é escolhida automaticamente (seção 4.4). |
| RF14 | **Verificação de chaves vazadas** | `python scripts/verificar_segredos.py` procura chaves **reais** em todos os arquivos do repositório, inclusive a documentação, sem falso alarme com textos de exemplo (seção 6, T8). |
| RF15 | **Versão do Gradio consistente** | A mesma versão do Gradio em todos os arquivos; se houver diferença, a publicação é bloqueada (seção 3.2). |
| RF16 | **Publicação que espelha o projeto com segurança** | O Space recebe só os arquivos do app, apaga do Space os arquivos do app que saíram do projeto e **nunca** toca no que precisa permanecer (seção 7.2). |

---

## 6. Testes automáticos (T)

*Pequenos programas que conferem sozinhos se cada parte funciona.*

**Princípio:** os testes **nunca** chamam as IAs de verdade. Usamos **simulações (mocks)**. Assim os testes são gratuitos, rápidos, não precisam de chaves e não falham por causa da internet. Os testes de publicação também **não** enviam nada ao Hugging Face: só conferem as regras.

### T1 — `tests/test_config.py` — configuração
- O `config.yml` real do repositório é válido. *(Este é o teste que impede publicar configuração errada.)*
- Recusa configuração sem `nome`.
- Recusa cor em formato errado (ex.: `azul` ou `#12`).
- Recusa `temperatura` fora de 0 a 1.
- Recusa provedor desconhecido (ex.: `gemini`).
- Recusa lista de provedores vazia ou sem nenhum ativo.
- Recusa provedor repetido.
- Recusa logo que não existe.
- Recusa campo desconhecido (erro de digitação).
- Recusa configuração **sem** a seção `limites`.
- Recusa limites fora das faixas (ex.: `perguntas_por_minuto_por_pessoa: 0` ou `perguntas_por_dia_total: 1000000`).

### T2 — `tests/test_cores.py` — contraste e legibilidade
- O cálculo de contraste está correto em casos conhecidos: preto × branco = 21 : 1; branco × branco = 1 : 1.
- Em botão azul-escuro, o texto escolhido é **branco**; em botão amarelo-claro, o texto escolhido é **preto**.
- `cor_secundaria` clara demais no tema `claro` (ex.: `#FFFF66`) é **recusada**, com sugestão de cor mais escura.
- `cor_secundaria` escura demais no tema `escuro` (ex.: `#1E1E1E`) é **recusada**, com sugestão de cor mais clara.
- `cor_primaria` quase igual ao fundo (contraste < 3 : 1) é **recusada**.
- As cores do `config.yml` real passam em todas as regras.

### T3 — `tests/test_provedores.py` — provedores
- Cada provedor monta a requisição com o modelo, a temperatura, o `max_tokens` e as instruções certas.
- O OpenRouter usa o endereço correto (`https://openrouter.ai/api/v1`).
- Um provedor sem chave é marcado como "indisponível".
- A chave nunca aparece em mensagens de erro.

### T4 — `tests/test_limites.py` — limites no servidor
- Até o limite por minuto, tudo funciona; a pergunta seguinte é bloqueada com a mensagem certa.
- Depois de 1 minuto, a pessoa pode perguntar de novo. *(O teste "adianta o relógio", sem esperar de verdade.)*
- O limite diário da pessoa bloqueia só aquela pessoa; o limite total bloqueia todo mundo.
- Os contadores zeram à meia-noite (horário de Brasília).
- O limite de uma pessoa (um IP) não afeta outra pessoa (outro IP).
- Pergunta maior que `tamanho_maximo_pergunta` é recusada.
- Quando há bloqueio, **nenhum** provedor é chamado. *(O teste confirma que a simulação da IA recebeu zero chamadas.)*
- O IP não aparece nos logs.

### T5 — `tests/test_chat.py` — conversa e fallback
- Se o 1º provedor responde, o 2º não é chamado.
- Se o 1º falha, o 2º é chamado e sua resposta é usada.
- Se o 1º e o 2º falham, o 3º é usado.
- Se todos falham, aparece a mensagem amigável (RF7).
- Provedores com `ativo: false` são ignorados.
- O histórico enviado respeita o limite `max_mensagens_historico`.
- Os limites são conferidos **antes** do fallback começar.

### T6 — `tests/test_interface.py` — tela
- A interface do Gradio é criada sem erro usando o `config.yml` real.
- O título da tela é o `nome` da configuração.
- As cores do `config.yml` e a cor de texto escolhida para os botões aparecem no estilo aplicado.

### T7 — `tests/test_versoes.py` — versão do Gradio
- O `requirements.txt` fixa o Gradio com `==`, **uma única vez**.
- O `sdk_version` do cabeçalho do `README.md` é **igual** a essa versão.
- Nenhum outro arquivo do projeto fixa uma versão diferente do Gradio, e o `requirements-dev.txt` não lista o Gradio.
- No GitHub Actions, a versão **instalada** do Gradio também é igual. Isso confirma que o que foi testado é o que será publicado.

### T8 — `tests/test_segredos.py` + `scripts/verificar_segredos.py` — chaves vazadas
Como a verificação funciona:
- Olha **todos** os arquivos de texto guardados no Git, **inclusive** `.md`, `.yml` e o workflow. Uma chave real colada na documentação também é um vazamento.
- Procura o **formato completo** de chaves reais, e não só o começo:
  - OpenRouter: `sk-or-v1-` seguido de 64 letras e números;
  - Anthropic: `sk-ant-` seguido de dezenas de caracteres;
  - OpenAI: `sk-` (ou `sk-proj-`) seguido de dezenas de caracteres;
  - Hugging Face: `hf_` seguido de cerca de 34 letras e números;
  - GitHub: `ghp_` e semelhantes.
- **Evita falsos positivos:**
  - textos curtos como `sk-` ou `hf_` sozinhos não são acusados;
  - valores claramente falsos também não, como os que contêm `SUA_CHAVE`, `EXEMPLO`, `xxxx` ou `...`;
  - por isso, esta SPEC, o README e o `.env.example` passam sem alarme.
- Ao encontrar algo, mostra **o arquivo e a linha**, mas **esconde** a chave (só os 6 primeiros caracteres).

Testes:
- Uma chave falsa no formato completo é detectada em um arquivo `.py` **e** em um arquivo `.md`. *(A chave falsa é montada durante o teste, em uma pasta temporária, para que o próprio repositório nunca contenha algo parecido com uma chave.)*
- Os textos `sk-`, `hf_` e `sk-or-v1-...` sozinhos **não** são detectados.
- Placeholders como `SUA_CHAVE_AQUI` **não** são detectados.
- A mensagem de alerta não mostra a chave inteira.
- O repositório real passa sem nenhum alerta.

### T9 — `tests/test_publicar.py` — regras de publicação
- A lista do que é **enviado** contém tudo que o app precisa: `app.py`, `config.yml`, `requirements.txt`, `README.md`, `assistente/` e `assets/`.
- A lista do que é enviado **não** contém testes, workflows, SPEC, IDEIA ou `.env`.
- A lista do que pode ser **apagado** no Space contém **apenas** caminhos do app.
- Arquivos protegidos **nunca** podem ser apagados: `.gitattributes` e qualquer arquivo fora das pastas do app.
- Simulação: se o Space tem `assets/logo-antiga.svg` e o projeto não tem mais, ele entra na lista para apagar. Se o Space tem `.gitattributes` ou `dados/arquivo.csv`, eles **não** entram.

### Como rodar no seu computador
```
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
pytest
python scripts/validar_config.py
python scripts/verificar_segredos.py
```

---

## 7. Publicação pelo GitHub Actions e Hugging Face

### 7.1 Visão geral do fluxo

```
Você faz push no GitHub
        │
        ▼
┌──────────────────────────────────┐
│ Job 1: "testar"                  │  roda em TODO push e Pull Request
│  1. Baixa o código               │
│  2. Instala Python 3.11          │
│  3. Instala as bibliotecas       │
│  4. Procura chaves reais vazadas │
│  5. Ruff (estilo)                │
│  6. Valida o config.yml          │
│     (inclui contraste e limites) │
│  7. pytest (todos os testes,     │
│     inclusive versões e regras   │
│     de publicação)               │
└──────────────┬───────────────────┘
               │ passou? E é push na main?
               ▼
┌──────────────────────────────────┐
│ Job 2: "publicar"                │  só roda se o Job 1 passar E for push na main
│  1. Baixa o código               │
│  2. Instala o huggingface_hub    │
│  3. Roda scripts/publicar.py:    │
│     envia os arquivos do app e   │
│     apaga do Space só os arquivos│
│     do app que saíram do projeto │
│     (tudo em uma única           │
│     atualização)                 │
└──────────────┬───────────────────┘
               ▼
Hugging Face reconstrói o Space e o link público é atualizado
```

**Regra mais importante:** se **qualquer** passo do Job 1 falhar, o Job 2 **não roda**. Configuração errada nunca chega ao link público.

**Uma publicação por vez:** se você fizer dois pushes seguidos, o segundo espera o primeiro terminar, para não misturar versões.

### 7.2 O que é enviado, o que é apagado e o que é protegido

**Enviado ao Space (arquivos do app):**
- `app.py`, `config.yml`, `requirements.txt`, `README.md`
- tudo dentro de `assistente/` e de `assets/`

**Apagado do Space:** **apenas** arquivos que estão nos caminhos acima e que **não existem mais** no projeto. Exemplos: uma logo trocada ou um arquivo de código removido. Assim o Space fica igual ao GitHub, sem "lixo" antigo.

**Nunca tocado (protegido):**

| O que | Por que precisa permanecer |
|---|---|
| `.gitattributes` | Arquivo de controle que o próprio Hugging Face cria em todo Space. |
| Qualquer arquivo **fora** das pastas do app | Ex.: um arquivo que você colocou à mão no Space. A publicação só mexe no que ela mesma controla. |
| **Secrets e variáveis** do Space (chaves de API) | Ficam nas configurações do Space, e não nos arquivos, por isso a publicação não consegue apagá-los. |
| **Configurações** do Space (hardware, visibilidade, etc.) | Também não são arquivos; não são alteradas. |
| **Armazenamento persistente** (`/data`), se um dia for ativado | É separado dos arquivos do código; não é afetado. |

Essas listas ficam em um único lugar (`scripts/publicar.py`) e são conferidas pelo teste T9. Assim, ninguém altera sem querer o que pode ser apagado.

### 7.3 Configuração inicial (feita uma única vez, por você, com meu passo a passo)
1. **Criar o Space** no Hugging Face: *New Space* → SDK **Gradio** → visibilidade **Public**.
2. **Adicionar as chaves de IA** no Space: *Settings → Variables and secrets → New secret* (`OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`). Não é preciso ter as três; o fallback só usa as que existirem.
3. **Definir um limite de gastos** no painel de cada provedor que você usar (ex.: alguns dólares por mês). Assim, mesmo com muito uso, a conta nunca passa do valor que você escolheu.
4. **Criar um token** no Hugging Face: *Settings → Access Tokens* → tipo **Write** (ou *fine-grained* com permissão de escrita só nesse Space).
5. **No GitHub**, em *Settings → Secrets and variables → Actions*:
   - Secret `HF_TOKEN` = o token do passo 4.
   - Variable `HF_SPACE_ID` = `seu-usuario/nome-do-space`.
6. Fazer um push na `main` e acompanhar na aba **Actions** do GitHub.

### 7.4 Como mudar uma configuração e ver a atualização
1. Editar o `config.yml` (ex.: trocar `cor_primaria`).
2. (Opcional) Rodar `python scripts/validar_config.py` no seu computador para conferir antes.
3. Fazer commit e push para a `main` (ou abrir um Pull Request e fazer o merge).
4. O GitHub Actions testa e publica (normalmente em poucos minutos).
5. O Space reconstrói; ao recarregar o link, a mudança aparece.

---

## 8. Critérios de aceite (CA)

*As provas finais. São verificações reais, feitas no link público e no GitHub. A Parte 1 só está **pronta** quando **todas** passarem.*

| # | Critério | Como verificar |
|---|---|---|
| CA1 | O chat responde pelo link público | Abrir `https://huggingface.co/spaces/<usuario>/<space>` e fazer uma pergunta. |
| CA2 | A personalização funciona | Mudar o `nome` e a `cor_primaria` no `config.yml`, fazer push e ver a mudança no link. |
| CA3 | O fallback funciona | Remover temporariamente a chave do OpenRouter no Space: o chat continua respondendo pelo próximo provedor. |
| CA4 | Falha total é amigável | Sem nenhuma chave, o chat mostra a mensagem amigável, sem erro técnico. |
| CA5 | Configuração errada é bloqueada | Em um Pull Request, colocar `cor_primaria: "azul"`: o GitHub Actions fica **vermelho** e nada é publicado. |
| CA6 | Código com erro é bloqueado | Um teste falhando impede o Job "publicar". |
| CA7 | Pull Request não publica | Abrir um PR roda os testes, mas **não** publica. |
| CA8 | Testes passam localmente | `pytest` mostra todos os testes passando. |
| CA9 | Limite por minuto funciona no link público | Fazer mais perguntas seguidas do que o limite permite: aparece o aviso para aguardar. |
| CA10 | O limite não é burlado recarregando a página | Atingir o limite, recarregar a página e perguntar de novo: o aviso **continua** aparecendo. |
| CA11 | Bloqueio não gasta crédito | Nos logs do Space, as perguntas bloqueadas aparecem como "limite atingido", sem nenhuma chamada a provedor. |
| CA12 | Limite de gastos definido | O painel de cada provedor usado mostra um limite de gastos configurado. |
| CA13 | Chave real é detectada | Em um PR de teste, colar uma chave **falsa no formato completo** em um arquivo `.md`: o Actions fica **vermelho** e mostra o arquivo e a linha, sem mostrar a chave inteira. Depois, fechar o PR sem fazer merge. |
| CA14 | Sem falso alarme na documentação | Com a SPEC, o README e o `.env.example` como estão, a verificação de segurança passa. |
| CA15 | Versões alinhadas | Em um PR, mudar a versão do Gradio só no `requirements.txt`: o Actions fica **vermelho**. |
| CA16 | Arquivo antigo some do Space | Remover um arquivo de `assets/`, fazer push e conferir na aba *Files* do Space que ele sumiu. |
| CA17 | O que precisa permanecer, permanece | Depois de uma publicação, conferir que o `.gitattributes` continua no Space e que os Secrets (chaves de IA) continuam configurados. |
| CA18 | Cores personalizadas aparecem | Trocar a `cor_primaria` para uma cor bem diferente (ex.: `#E11D48`) e ver os botões mudarem no link. |
| CA19 | Cor ilegível é bloqueada | Em um PR, colocar `cor_secundaria: "#FFFF66"` com tema `claro`: o Actions fica **vermelho**, com mensagem sugerindo uma cor mais escura. |
| CA20 | Texto dos botões legível | Com uma `cor_primaria` clara (ex.: `#FDE68A`), o texto dos botões fica **preto**; com uma escura, fica **branco**. |

---

## 9. Ordem dos passos de implementação (P)

Cada passo é pequeno e termina com algo que dá para testar. Só passo para o próximo quando o anterior estiver funcionando.

| # | Passo | Resultado esperado |
|---|---|---|
| P1 | Criar a estrutura básica: `.gitignore`, `.env.example`, `requirements*.txt` (Gradio fixado), pastas | Projeto organizado, sem nenhuma chave. |
| P2 | Criar o `scripts/verificar_segredos.py` e o teste T8 | Proteção contra vazamento ativa desde o começo. |
| P3 | Criar o `assistente/cores.py` e o teste T2 | Cálculo de contraste funcionando. |
| P4 | Criar o `config.yml` e o `assistente/config.py` (leitura + validação, usando `cores.py`) | Configuração validada com mensagens claras. |
| P5 | Escrever o teste T1 e o `scripts/validar_config.py` | Testes de configuração passando. |
| P6 | Criar o `assistente/provedores.py` e o teste T3 | Cada provedor sabe enviar uma pergunta (testado com simulação). |
| P7 | Criar o `assistente/limites.py` e o teste T4 | Limites funcionando no servidor. |
| P8 | Criar o `assistente/chat.py` (limites → fallback) e o teste T5 | Conversa completa, protegida e com troca de provedor. |
| P9 | Criar o `assistente/interface.py`, o `app.py`, a logo e o teste T6 | Chat abrindo no navegador do seu computador, com as cores do `config.yml`. |
| P10 | Atualizar o `README.md` (cabeçalho do Hugging Face com `sdk_version`) e criar o teste T7 | Versões alinhadas e conferidas. |
| P11 | Criar o `scripts/publicar.py` e o teste T9 | Regras de envio, exclusão e proteção conferidas. |
| P12 | Criar o `.github/workflows/ci-deploy.yml` (só o Job "testar") | Testes rodando automaticamente no GitHub. |
| P13 | Configuração inicial no Hugging Face, no GitHub e nos provedores (seção 7.3) | Segredos criados e limites de gastos definidos (feito por você, com meu guia). |
| P14 | Adicionar o Job "publicar" ao workflow | Publicação automática funcionando. |
| P15 | Conferir todos os critérios de aceite (CA1 a CA20) | Parte 1 concluída. ✅ |

---

## 10. Erros comuns e soluções

| Erro / sintoma | Causa provável | Solução |
|---|---|---|
| Space mostra **"Configuration error"** | Falta o cabeçalho YAML no topo do `README.md` ou ele está mal formatado | Conferir se o README começa com `---`, contém `sdk: gradio`, `sdk_version` e `app_file: app.py`, e fecha com `---`. |
| Space mostra **"Runtime error"** / `ModuleNotFoundError` | Biblioteca faltando no `requirements.txt` | Adicionar a biblioteca ao `requirements.txt` e publicar de novo. |
| App funciona no computador mas quebra no Space | Versão do Gradio diferente entre o README e o `requirements.txt` | Usar o mesmo número nos dois lugares; o teste T7 avisa antes de publicar. |
| Chat responde sempre a mensagem amigável de erro | Nenhuma chave configurada no Space ou todas inválidas | Conferir *Settings → Secrets* do Space; os nomes devem ser exatamente `OPENROUTER_API_KEY` etc. Depois, reiniciar o Space. |
| Erro **401 / Unauthorized** nos logs | Chave errada, expirada ou copiada com espaço sobrando | Gerar uma nova chave no site do provedor e colar de novo, sem espaços. |
| Erro **402 / sem crédito** | Conta do provedor sem saldo ou limite de gastos atingido | Adicionar créditos, aumentar o limite de gastos ou usar um modelo `:free` do OpenRouter; o fallback cobre enquanto isso. |
| Erro **404 / model not found** | Nome do modelo errado ou modelo descontinuado | Conferir o nome exato no site do provedor e corrigir no `config.yml`. |
| Erro **429 / rate limit** do provedor | Muitas perguntas em pouco tempo (comum em modelos gratuitos) | Esperar um pouco; o fallback passa para o próximo provedor. Se for frequente, reduzir os `limites`. |
| Muita gente vê "limite de uso de hoje atingido" | `perguntas_por_dia_total` baixo demais para o movimento | Aumentar o valor no `config.yml`, se o orçamento permitir. |
| Várias pessoas da mesma escola ou empresa são bloqueadas juntas | Elas saem para a internet pelo **mesmo IP**, então contam como uma pessoa só | Aumentar `perguntas_por_minuto_por_pessoa` e `perguntas_por_dia_por_pessoa`. Limite conhecido desta versão simples. |
| Contadores de limite "zeraram" do nada | O Space reiniciou (os contadores ficam na memória) | Comportamento esperado. O limite de gastos no provedor continua protegendo. |
| Conta do provedor gastou mais do que o esperado | Link muito usado, ou limites altos demais | Baixar os valores em `limites` e conferir o limite de gastos no painel do provedor. |
| Validação reclama de **cor inválida** | Cor escrita como nome (`azul`) ou faltando dígitos | Usar o formato `#RRGGBB`, ex.: `#2563EB`. |
| Validação reclama de **contraste baixo** | Cor clara demais no tema claro, ou escura demais no tema escuro | Seguir a sugestão da mensagem (cor mais escura ou mais clara). Sites de "contrast checker" ajudam a escolher. |
| Cor que funcionava passou a ser recusada | O `tema` foi trocado (claro ↔ escuro) | Ajustar as cores para o novo fundo. |
| Erro ao ler o YAML (`mapping values are not allowed`) | Indentação errada ou falta de aspas | Usar **2 espaços** (nunca TAB) e colocar textos com `:` ou `#` entre aspas. |
| A logo não aparece | Caminho errado em `assistente.logo` | O caminho é relativo à raiz do projeto, ex.: `assets/logo.svg`. A validação já avisa se o arquivo não existir. |
| Mudei o `config.yml` e nada mudou no link | Publicação ainda em andamento ou o navegador guardou a versão antiga | Esperar o Actions ficar verde e o Space terminar o *build*; recarregar com Ctrl+Shift+R. |
| Verificação de segurança acusa algo que não é uma chave real | Texto de exemplo no formato completo de uma chave | Trocar o exemplo por um texto claramente falso (ex.: `SUA_CHAVE_AQUI`). |
| Chave apareceu no GitHub por engano | `.env` enviado ou chave colada em algum arquivo | **Revogar a chave imediatamente** no site do provedor e criar outra. Apagar o arquivo não basta, pois ela continua no histórico. |
| GitHub Actions falha em **"publicar"** com 401/403 | `HF_TOKEN` ausente, errado ou só com permissão de leitura | Criar um token com permissão **Write** e atualizar o secret no GitHub. |
| GitHub Actions falha com **"Space not found"** | `HF_SPACE_ID` digitado errado | Usar o formato `usuario/nome-do-space`, igual à URL do Space. |
| Job "publicar" nunca roda | O push não foi na `main`, ou algum teste falhou | Ver a aba **Actions**; corrigir o teste que falhou ou fazer o merge na `main`. |
| Arquivo antigo continua no Space | Está fora das pastas do app (a publicação não mexe nele, por segurança) | Se não for mais necessário, apagá-lo à mão na aba *Files* do Space. |
| Testes passam no seu computador mas falham no Actions | Versão de biblioteca ou de Python diferente | Instalar pelo `requirements.txt` e usar Python 3.11 nos dois lugares. |

---

## Próximo passo

Revise esta SPEC. Você pode:
- **Aprovar como está**, e eu começo pelo passo P1; ou
- **Pedir ajustes**.

Nenhum código será escrito até a sua autorização final.
