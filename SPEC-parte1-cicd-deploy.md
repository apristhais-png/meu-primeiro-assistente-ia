# SPEC — Parte 1: Assistente de IA com CI/CD e publicação

> **Status:** aprovada como referência. Implementação em andamento, um passo por vez, com autorização a cada passo.
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
> - **Revisão 3:**
>   - limites aplicados **no servidor**;
>   - verificação de chaves passa a olhar **todos** os arquivos, inclusive a documentação, sem falso alarme;
>   - versão do Gradio conferida em **todos** os arquivos;
>   - publicação apaga só arquivos que **o projeto controla**;
>   - cores com **verificação de contraste**;
>   - arquivo renomeado para `config.yml`;
>   - códigos alinhados ao checklist: **RF** (requisitos), **T** (testes), **CA** (critérios de aceite) e **P** (passos de implementação).
> - **Revisão 4:**
>   - identificação da pessoa pelo IP feita de forma segura, com teste no Hugging Face e limites globais sempre ativos como proteção principal (RF11, RF17, T4, CA24, CA25, P15);
>   - CA13 feito só no computador local;
>   - CA20 com uma cor que passa na validação;
>   - logo criada no P4;
>   - CA16 com um arquivo de teste;
>   - novos critérios para memória, instruções e pergunta longa (CA21 a CA23) e teste de que as conversas não vão para os logs.
> - **Revisão 5 (durante o P6):**
>   - o fallback só acontece em falhas **temporárias**. Erros de chave, permissão ou cobrança **param** o fallback, para o problema não ficar escondido (RF6);
>   - o fallback passou do P8 para o P6, dentro do `provedores.py`; o P8 continua juntando limites, histórico e fallback no `chat.py`;
>   - a temperatura não é enviada à Anthropic, porque os modelos atuais do Claude recusam esse parâmetro.
> - **Revisão 6 (durante o P7):**
>   - exemplos de IP do T4 trocados por IPs públicos reais (os antigos eram de faixas de documentação);
>   - regra para linhas repetidas do `X-Forwarded-For`;
>   - `httpx2` (usado pelos testes) e `tzdata` (fuso de Brasília) declarados nas dependências.
> - **Revisão 7 (durante o P8):** regras de segurança para o histórico que vem do navegador (papel `system` descartado, tamanho máximo por mensagem, avisos do assistente removidos).
> - **Revisão 8 (durante o P9):** detalhes da tela: balão da pessoa e links nas cores do `config.yml`, balão da IA com o fundo validado, modo claro/escuro forçado, API `/chat` com os mesmos limites da tela.
> - **Revisão 9 (durante o P10):** o teste T7 também confere o cabeçalho do README (topo, `app_file`, Python 3.11 entre aspas, regras do Hugging Face) e que todas as bibliotecas têm versão fixada.
> - **Revisão 10 (durante o P11):** `scripts/publicar.py` só simula sem `--publicar`, envia só arquivos do Git na lista permitida, cancela tudo diante de arquivo perigoso, chave, config inválido, falta de essencial ou exclusão em massa, e publica numa única atualização presa à versão lida do Space. `huggingface_hub` declarado no `requirements-dev.txt`.
> - **Revisão 11 (durante o P12):** o workflow roda em todo Pull Request e em push na `main` (pushes num PR já disparam pelo próprio PR, sem rodar duas vezes). Novo `tests/test_workflow.py` confere gatilhos, Python 3.11, todas as verificações, nenhuma falha escondida e nenhum segredo ou publicação no job "testar".
> - **Revisão 12 (durante o P13):** `GUIA-publicacao.md` com o passo a passo para você e a situação dos modelos; `scripts/conferir_modelos.py` confere os modelos só consultando a lista de cada provedor (sem custo). Modelo da Anthropic confirmado na documentação oficial; OpenRouter e OpenAI ficaram pendentes (sites inacessíveis no ambiente de desenvolvimento).

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
| **IP** | O "endereço" de internet de quem está acessando. Pessoas na mesma rede (casa, escola) podem ter o mesmo IP. |
| **Proxy** | Um intermediário: no Hugging Face, toda conexão passa primeiro por um servidor do próprio Hugging Face e só depois chega ao nosso app. |
| **X-Forwarded-For** | Um campo extra da conexão em que os intermediários anotam o IP de quem fez o pedido. **Parte dele pode ser inventada** por quem acessa, por isso só confiamos no trecho escrito pelo Hugging Face. |
| **Identificador anônimo** | Um código embaralhado gerado a partir do IP (ex.: `a3f9c2e1`). Serve para contar perguntas e conferir os logs sem nunca mostrar o IP. |
| **Falso positivo (falso alarme)** | Quando a verificação acusa um problema que não existe, por exemplo, tratar um texto de exemplo como se fosse uma chave real. |

---

## 1. Objetivo do projeto

Criar um **chat de inteligência artificial que ensina Engenharia de Dados e IA de forma simples**, acessível por qualquer pessoa em um **link público no navegador**.

Nesta Parte 1 o foco é ter a **base funcionando de ponta a ponta**, mantendo o projeto **simples para iniciantes**:

1. Um chat simples que conversa usando IA.
2. Personalização (nome, cores, logo, instruções, modelos e limites de uso) **por um único arquivo**, o `config.yml`, sem mexer no código.
3. **Troca automática de provedor** se um deles falhar.
4. **Proteção dos créditos** com limites de uso aplicados no servidor: limites **globais** sempre ativos e limites **por pessoa** só quando a identificação for comprovada.
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
│   ├── provedores.py           # Fala com OpenRouter, Anthropic e OpenAI + fallback entre eles
│   ├── limites.py              # Limites de uso no servidor + identificação segura pelo IP
│   ├── chat.py                 # Junta tudo: limites → histórico → fallback (de provedores.py)
│   └── interface.py            # Monta a tela do Gradio usando a configuração
├── scripts/
│   ├── validar_config.py       # Confere o config.yml antes de publicar
│   ├── conferir_modelos.py     # Confere se os modelos existem nos provedores (só consulta, sem custo)
│   ├── verificar_segredos.py   # Procura chaves de API reais esquecidas nos arquivos
│   └── publicar.py             # Envia ao Space só o necessário e apaga o que saiu
├── tests/
│   ├── test_config.py          # Configuração
│   ├── test_cores.py           # Contraste e legibilidade
│   ├── test_provedores.py      # Provedores e fallback (com simulação)
│   ├── test_limites.py         # Limites de uso
│   ├── test_chat.py            # Conversa: limites, histórico e logs
│   ├── test_interface.py       # Tela
│   ├── test_versoes.py         # Versão do Gradio igual em todos os arquivos
│   ├── test_segredos.py        # Verificação de chaves
│   ├── test_publicar.py        # Regras de publicação (o que envia, o que apaga, o que protege)
│   ├── test_workflow.py        # O workflow: gatilhos, verificações, sem segredos no job testar
│   └── test_conferir_modelos.py # Conferência de modelos (simulada, sem custo)
├── .github/
│   └── workflows/
│       └── ci-deploy.yml       # Robô: testa e depois publica no Hugging Face
├── requirements.txt            # Bibliotecas que o app precisa (única fonte da versão do Gradio)
├── requirements-dev.txt        # Bibliotecas extras só para testes (pytest, ruff), sem Gradio
├── .env.example                # Modelo de .env, SEM chaves reais
├── .gitignore                  # Garante que .env e lixo não subam para o GitHub
├── README.md                   # Explicação do projeto + cabeçalho exigido pelo Hugging Face
├── IDEIA-parte1.md             # Ideia original
├── GUIA-publicacao.md          # Passo a passo do Hugging Face, do GitHub e dos provedores (P13)
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
  # Limites GLOBAIS: valem sempre, para a soma de todas as pessoas
  perguntas_por_minuto_total: 20
  perguntas_por_dia_total: 500
  tamanho_maximo_pergunta: 2000      # em caracteres
  # Limites POR PESSOA: só valem se identificar_por_ip for true
  identificar_por_ip: false          # só mude para true depois do passo P15 (critério CA24)
  perguntas_por_minuto_por_pessoa: 5
  perguntas_por_dia_por_pessoa: 50

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
| `limites.perguntas_por_minuto_total` | Inteiro entre 1 e 120. |
| `limites.perguntas_por_dia_total` | Inteiro entre 1 e 5000. |
| `limites.tamanho_maximo_pergunta` | Inteiro entre 100 e 10000. |
| `limites.identificar_por_ip` | `true` ou `false`. **Obrigatório**, para que a escolha seja sempre consciente. |
| `limites.perguntas_por_minuto_por_pessoa` | Inteiro entre 1 e 30, e **não maior** que `perguntas_por_minuto_total`. |
| `limites.perguntas_por_dia_por_pessoa` | Inteiro entre 1 e 500, e **não maior** que `perguntas_por_dia_total`. |
| `limites` (seção inteira) | **Obrigatória.** Não existe "sem limite": um erro de digitação nunca desliga a proteção global. |
| `provedores` | Pelo menos 1 provedor ativo; nomes só podem ser `openrouter`, `anthropic` ou `openai`; sem repetição. |
| Campos desconhecidos | São recusados (pega erros de digitação, como `nomee`). |

### 4.3 Limites de uso no servidor (proteção dos créditos)

**Por que no servidor?** Tudo que roda no navegador pode ser burlado por quem entende um pouco de programação. Por isso, a conferência dos limites acontece **no código Python do servidor**, **antes** de chamar qualquer IA. Se o limite foi atingido, a IA simplesmente não é chamada e nenhum crédito é gasto. Isso vale também para quem tenta usar o app por programas, sem a tela: todo pedido passa pela mesma conferência.

**Duas camadas de limite:**

| Camada | Quando vale | Para que serve |
|---|---|---|
| **Global** (`perguntas_por_minuto_total`, `perguntas_por_dia_total`, `tamanho_maximo_pergunta`) | **Sempre.** Não depende de saber quem é quem. | É a **proteção principal dos créditos**. Mesmo que alguém consiga se passar por várias pessoas, o total nunca passa desses números. |
| **Por pessoa** (`perguntas_por_minuto_por_pessoa`, `perguntas_por_dia_por_pessoa`) | Só se `identificar_por_ip: true` **e** a pessoa for identificada com segurança. | Evita que **uma** pessoa gaste sozinha todo o limite global. É uma camada **extra**, de "melhor esforço". |

**Como funciona, passo a passo:**
1. Chega uma pergunta.
2. O servidor confere o **tamanho** da pergunta. Se for grande demais, recusa.
3. O servidor confere os **limites globais** (minuto e dia). Se algum foi atingido, recusa.
4. Se `identificar_por_ip` for `true`, o servidor tenta identificar a pessoa (veja abaixo). Se conseguir, confere os **limites por pessoa**. Se não conseguir, a pergunta segue só com os limites globais, que já foram conferidos.
5. Se tudo estiver dentro do limite, conta +1 e só então chama a IA.

#### Como o IP é obtido com segurança no Hugging Face

**O problema:** no Hugging Face, o app não recebe a conexão direto da pessoa. Ela passa antes pelo **proxy** do Hugging Face. Por isso:
- o "IP da conexão" que o app enxerga é o do **proxy**, e é igual para todo mundo. Esse valor **nunca** é usado;
- o IP real chega no campo **`X-Forwarded-For`**, que é uma lista de IPs separados por vírgula. Cada intermediário **acrescenta um IP no fim** da lista;
- **o começo da lista pode ser inventado** por quem acessa, que pode enviar um `X-Forwarded-For` falso junto com o pedido. O proxy do Hugging Face só acrescenta o IP verdadeiro **depois** do valor falso.

**A regra que vamos seguir (nunca confiar no começo da lista):**
1. Ler o `X-Forwarded-For`.
2. Usar **somente o último item da lista**, que é o escrito pelo proxy do Hugging Face. **Nunca** usar o primeiro item nem qualquer outro.
3. Conferir se esse item é um IP válido e **público**. Valores como `abc`, vazio, `10.0.0.1`, `192.168.x.x` ou `127.0.0.1` são recusados.
4. Se o campo não existir, estiver vazio ou o último item for inválido, a pessoa fica como **"não identificada"**. Ela continua sujeita aos limites globais. O app não trava e não mostra erro.
5. O IP vira um **identificador anônimo**: um código embaralhado com um "tempero" aleatório criado a cada vez que o app inicia, e que fica só na memória. Os contadores e os logs usam apenas esse código, **nunca** o IP.

**Por que começamos com `identificar_por_ip: false`:** a regra acima é uma **hipótese**. Ela depende de o Hugging Face acrescentar exatamente um item no fim da lista, e isso não é garantido pela documentação dele. Por segurança, o app é publicado primeiro **só com os limites globais**. A camada por pessoa só é ligada depois de comprovar a hipótese no próprio Space.

#### Como testar a identificação no Hugging Face (passo P15, critério CA24)
Com o app publicado e `identificar_por_ip: true` **temporariamente**:
1. **Mesma pessoa, mesmo código:** fazer duas perguntas pelo navegador do seu computador. Nos logs do Space, as duas linhas mostram o **mesmo** identificador anônimo.
2. **Redes diferentes, códigos diferentes:** fazer uma pergunta pelo celular **com o Wi-Fi desligado** (usando os dados móveis). O identificador nos logs deve ser **diferente** do anterior.
3. **IP inventado não engana:** do seu computador, enviar uma pergunta pelo programa de teste do Gradio (`gradio_client`) com um `X-Forwarded-For` falso (ex.: `203.0.113.7`). O identificador nos logs deve ser **o mesmo** do item 1. Eu preparo o comando pronto nesse passo.
4. **Formato da lista:** cada linha de log também mostra **quantos itens** o `X-Forwarded-For` tinha. Isso confirma se o Hugging Face acrescenta exatamente um item.

**Decisão depois do teste:**
- **Se os 4 itens passarem:** manter `identificar_por_ip: true`. Os limites por pessoa passam a valer.
- **Se algum item falhar:** voltar para `identificar_por_ip: false` e registrar a limitação no `README.md`: *"Nesta versão, os limites valem para o total de pessoas; não há limite individual."* Os créditos continuam protegidos pelos limites globais e pelo limite de gastos dos provedores. Ajustar a regra de leitura fica para uma parte futura.

**Limitações conhecidas (mesmo com a identificação ligada):**
- Pessoas na **mesma rede** (casa, escola, empresa) têm o mesmo IP e dividem o mesmo limite por pessoa.
- Quem trocar de rede (ex.: Wi-Fi → dados móveis) ganha um novo limite por pessoa. O **limite global continua valendo**.

**Mensagens que a pessoa vê:**

| Situação | Mensagem |
|---|---|
| Pergunta longa demais | *"Sua pergunta ficou muito longa. Tente resumir em até 2000 caracteres."* |
| Limite global por minuto | *"O assistente está muito movimentado agora. Aguarde um minuto e tente de novo."* |
| Limite global do dia | *"O limite de uso de hoje foi atingido. Volte amanhã!"* |
| Limite da pessoa por minuto | *"Você fez muitas perguntas seguidas. Aguarde um minuto e tente de novo."* |
| Limite da pessoa por dia | *"Você atingiu o limite de perguntas de hoje. Volte amanhã!"* |

**Escolhas para manter simples:**
- Os contadores ficam **na memória** do app, sem banco de dados. Se o Space reiniciar, os contadores voltam a zero. Isso é aceitável porque existe uma segunda proteção: o **limite de gastos no painel dos provedores** (seção 7.3).
- O "dia" vira à meia-noite no horário de Brasília.
- O IP é usado **só** para gerar o identificador anônimo: **não** aparece nos logs e não é salvo em arquivo.

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
| RF6 | **Fallback automático só em falhas temporárias** | Se o provedor tiver uma falha **temporária** (tempo esgotado, falha de conexão, excesso de pedidos 429, erro no servidor 5xx ou resposta vazia), tenta o próximo da lista. Se o erro for de **chave** (401), **permissão** (403), **cobrança/sem créditos** (402, ou 429/400 que indiquem falta de créditos) ou **pedido inválido** (ex.: modelo inexistente), o fallback **para**: os outros provedores não são tentados, a pessoa vê a mensagem amigável (RF7) e o log explica o que corrigir. Provedor **sem chave configurada** é pulado sem ser chamado. |
| RF7 | **Mensagem amigável quando tudo falha** | Se nenhum provedor responder, mostra: *"Desculpe, não consegui responder agora. Tente novamente em alguns minutos."* Sem erros técnicos. |
| RF8 | **Validação da configuração** | Ao iniciar, o app confere o `config.yml`. Se houver erro, mostra claramente qual campo está errado e como corrigir. |
| RF9 | **Script de validação** | `python scripts/validar_config.py` confere o arquivo antes de publicar (usado também pelo GitHub Actions). |
| RF10 | **Logs simples e sem dados sensíveis** | Registra qual provedor respondeu e quais falharam, quando um limite foi atingido, o identificador anônimo e quantos itens tinha o `X-Forwarded-For`. **Nunca** registra chaves, IPs ou o conteúdo das perguntas e respostas. |
| RF11 | **Limites globais no servidor (sempre ativos)** | Limites totais por minuto e por dia, somando todas as pessoas, conferidos no servidor **antes** de chamar a IA. Valem mesmo sem identificar ninguém e são a proteção principal dos créditos (seção 4.3). |
| RF12 | **Pergunta muito longa é recusada** | Perguntas maiores que `tamanho_maximo_pergunta` são recusadas com uma mensagem amigável, sem chamar a IA. |
| RF13 | **Cores personalizadas legíveis** | Qualquer `#RRGGBB` é aceito se passar no teste de contraste. A cor do texto dos botões é escolhida automaticamente (seção 4.4). |
| RF14 | **Verificação de chaves vazadas** | `python scripts/verificar_segredos.py` procura chaves **reais** em todos os arquivos do repositório, inclusive a documentação, sem falso alarme com textos de exemplo (seção 6, T8). |
| RF15 | **Versão do Gradio consistente** | A mesma versão do Gradio em todos os arquivos; se houver diferença, a publicação é bloqueada (seção 3.2). |
| RF16 | **Publicação que espelha o projeto com segurança** | O Space recebe só os arquivos do app, apaga do Space os arquivos do app que saíram do projeto e **nunca** toca no que precisa permanecer (seção 7.2). |
| RF17 | **Limites por pessoa com identificação segura** | Quando `identificar_por_ip: true`, usa **somente o último item** do `X-Forwarded-For` (o escrito pelo proxy do Hugging Face) e só se for um IP público válido. Caso contrário, a pessoa fica "não identificada" e vale só o limite global. Começa **desligado** e só é ligado depois de comprovado no Space (seção 4.3, CA24). |

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
- Recusa configuração sem `identificar_por_ip`.
- Recusa limite por pessoa maior que o limite global correspondente.

### T2 — `tests/test_cores.py` — contraste e legibilidade
- O cálculo de contraste está correto em casos conhecidos: preto × branco = 21 : 1; branco × branco = 1 : 1.
- Em botão azul-escuro, o texto escolhido é **branco**; em botão amarelo-claro, o texto escolhido é **preto**.
- `cor_secundaria` clara demais no tema `claro` (ex.: `#FFFF66`) é **recusada**, com sugestão de cor mais escura.
- `cor_secundaria` escura demais no tema `escuro` (ex.: `#1E1E1E`) é **recusada**, com sugestão de cor mais clara.
- `cor_primaria` quase igual ao fundo (contraste < 3 : 1) é **recusada**.
- As cores do `config.yml` real passam em todas as regras.

### T3 — `tests/test_provedores.py` — provedores e fallback
*A rede fica bloqueada durante esses testes: nenhuma IA de verdade é chamada.*

**Provedores:**
- Cada provedor monta a requisição com o modelo, o `max_tokens` e as instruções certas. OpenRouter e OpenAI também recebem a temperatura; a Anthropic **não** (os modelos atuais do Claude recusam esse parâmetro). A OpenAI usa `max_completion_tokens`.
- O OpenRouter usa o endereço correto (`https://openrouter.ai/api/v1`).
- Os clientes não repetem pedidos sozinhos (`max_retries=0`): quem decide é o fallback.
- Um provedor sem chave (ou com só espaços) é marcado como "indisponível"; espaços em volta da chave são removidos.
- A chave nunca aparece em mensagens de erro, nem no `repr` do provedor, nem anexada ao erro original.

**Classificação dos erros:**
- **Temporários (permitem fallback):** tempo esgotado, conexão, 408, 429 de excesso de pedidos, 500, 502, 503, 529, resposta vazia.
- **Não temporários (param o fallback):** 401, 403, 402, 429 com `insufficient_quota`, 400 com "credit balance is too low" ou `billing_error`, 404, 400 e 422 comuns, e erros inesperados.

**Fallback:**
- Se o 1º provedor responde, o 2º não é chamado.
- Se o 1º tem falha temporária, o 2º é chamado; se o 1º e o 2º falham temporariamente, o 3º é usado.
- Se todos falham temporariamente, aparece a mensagem amigável (RF7).
- Erro de chave, permissão, cobrança ou pedido inválido **para** o fallback: os provedores seguintes **não** são chamados.
- Falha temporária no 1º e cobrança no 2º: para no 2º, e o 3º não é chamado.
- Provedor sem chave é pulado sem ser chamado (CA3); sem nenhuma chave, aparece a mensagem amigável (CA4).
- Os logs mostram quais provedores responderam ou falharam, mas **nunca** a chave, a pergunta, a resposta ou as instruções.

### T4 — `tests/test_limites.py` — limites e identificação no servidor
*Os testes simulam pedidos com diferentes `X-Forwarded-For`, sem internet.*

**Limites globais (sempre ativos):**
- Ao atingir `perguntas_por_minuto_total`, **todos** são bloqueados até o minuto seguinte. *(O teste "adianta o relógio", sem esperar de verdade.)*
- Ao atingir `perguntas_por_dia_total`, **todos** são bloqueados até a meia-noite (horário de Brasília).
- Pergunta maior que `tamanho_maximo_pergunta` é recusada.
- Com `identificar_por_ip: false`, os limites por pessoa são ignorados, mas os globais **continuam bloqueando**.

**Identificação segura (com `identificar_por_ip: true`):**
*Os testes usam IPs públicos de verdade (ex.: `8.8.8.8`, `1.1.1.1`). IPs como `203.0.113.7` e `198.51.100.10` são de faixas reservadas para documentação: não existem na internet real e por isso são tratados como não confiáveis.*
- `X-Forwarded-For: 8.8.8.8` → a pessoa é identificada por esse IP.
- `X-Forwarded-For: 203.0.113.7, 8.8.8.8` → usa **8.8.8.8** (o último), **nunca** o primeiro.
- **IP inventado não engana:** a mesma pessoa (último item `8.8.8.8`) enviando vários valores falsos diferentes no começo da lista recebe **sempre o mesmo** identificador e continua bloqueada ao passar do limite.
- **Linhas repetidas:** se o pedido tiver duas linhas `X-Forwarded-For` (uma inventada e outra do proxy), as duas são juntadas na ordem de chegada, e vale o último item.
- Sem `X-Forwarded-For`, com valor vazio, com `abc` no último item, ou com IP privado/local (`10.0.0.1`, `192.168.0.5`, `127.0.0.1`) → "não identificada". Só os limites globais valem, e o app não dá erro.
- O IP da conexão do proxy **nunca** é usado como identificação.
- IPv6 válido e público também é aceito.

**Limites por pessoa:**
- Até o limite por minuto, tudo funciona; a pergunta seguinte é bloqueada com a mensagem certa; depois de 1 minuto, libera.
- O limite diário da pessoa bloqueia só aquela pessoa.
- O limite de uma pessoa (um IP) não afeta outra pessoa (outro IP).

**Custo e privacidade:**
- Quando há bloqueio, **nenhum** provedor é chamado. *(O teste confirma que a simulação da IA recebeu zero chamadas.)*
- Os logs mostram o identificador anônimo e a quantidade de itens do `X-Forwarded-For`, mas **nunca** o IP.
- O mesmo IP gera identificadores diferentes depois que o app reinicia (o "tempero" muda).

### T5 — `tests/test_chat.py` — conversa
*Os casos de fallback ficam no T3 (P6). Aqui se testa a conversa completa usando o fallback.*
- Se o fallback não consegue resposta, a pessoa vê a mensagem amigável (RF7).
- Provedores com `ativo: false` são ignorados.
- O histórico enviado respeita o limite `max_mensagens_historico`.
- Os limites são conferidos **antes** do fallback começar.
- O texto da pergunta e o da resposta **não** aparecem nos logs (RF10). *(O teste usa uma frase única, como `pergunta-secreta-123`, e confere que ela não está em nenhuma linha de log.)*
- Pergunta bloqueada (longa, limite global ou por pessoa) e pergunta vazia **não chamam nenhuma IA** (as IAs simuladas contam zero chamadas).
- **Conversas não se misturam:** o `Assistente` não guarda conversa nenhuma; o histórico chega com cada pergunta e é copiado. Testado com conversas intercaladas e com 15 conversas ao mesmo tempo.
- **Histórico vindo do navegador é tratado como não confiável:** papel `system` (ou qualquer papel diferente de `user`/`assistant`) é descartado; cada mensagem é cortada num tamanho máximo; avisos do próprio assistente (limite atingido, falha) saem do histórico junto com a pergunta que os gerou; o histórico original não é alterado.

### T6 — `tests/test_interface.py` — tela
- A interface do Gradio é criada sem erro usando o `config.yml` real.
- O título da tela é o `nome` da configuração.
- As cores do `config.yml` e a cor de texto escolhida para os botões aparecem no estilo aplicado.
- O balão das mensagens da pessoa usa um tom claro da `cor_primaria`; os links nas mensagens usam a `cor_secundaria`, sobre o mesmo fundo em que o contraste foi validado.
- O modo claro ou escuro do `config.yml` é forçado, mesmo que o navegador prefira o outro.
- Logo, descrição, boas-vindas e exemplos vêm do `config.yml`; textos do config não viram código na página.
- Os exemplos não são pré-calculados (abrir o app não chama a IA) e a conversa não é salva no navegador.
- Erro inesperado vira mensagem amigável, sem detalhes técnicos na tela nem nos logs.
- **App de verdade, aberto em 127.0.0.1 com IA falsa e rede externa bloqueada:** a página abre com o nome e as cores; cada visitante tem a própria conversa; os limites global e por pessoa são aplicados no servidor (inclusive pela API `/chat`); pergunta longa e falta de chaves mostram as mensagens amigáveis.

### T7 — `tests/test_versoes.py` — versão do Gradio
- O `requirements.txt` fixa o Gradio com `==`, **uma única vez**.
- O `sdk_version` do cabeçalho do `README.md` é **igual** a essa versão.
- Nenhum outro arquivo do projeto fixa uma versão diferente do Gradio, e o `requirements-dev.txt` não lista o Gradio.
- No GitHub Actions, a versão **instalada** do Gradio também é igual. Isso confirma que o que foi testado é o que será publicado.
- O cabeçalho do `README.md` está no **topo** do arquivo, é um YAML válido e tem `sdk: gradio`, `app_file: app.py` (que existe) e `python_version: "3.11"` (entre aspas). `colorFrom`/`colorTo` usam cores aceitas pelo Hugging Face e `short_description` tem até 60 caracteres.
- Todas as bibliotecas dos `requirements*.txt` têm versão fixada com `==`.
- Quando o workflow do GitHub Actions existir (P12), a `python-version` dele é a mesma do README.

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
- Só arquivos **guardados no Git** são enviados (um `.env` ou rascunho fora do Git nunca vai).
- Arquivo perigoso dentro de uma pasta do app (`.env`, `*.pem`, `*.key`, `*secret*`, `__pycache__`…), chave dentro de um arquivo enviado, `config.yml` inválido ou falta de arquivo essencial **cancelam** a publicação inteira.
- Caminhos estranhos no Space (`..`, `//`, `./`, absolutos, barra invertida) nunca são apagados.
- Trava contra exclusão em massa: mais de 20 exclusões cancelam a publicação.
- Sem `--publicar`, o script só **simula** (mostra o plano). A publicação é **uma única atualização**, presa à versão do Space que foi lida (`parent_commit`): se o Space mudou no meio, nada é alterado.
- `HF_SPACE_ID` ausente ou inválido, ou `HF_TOKEN` ausente, cancelam **antes** de qualquer acesso ao Hugging Face. Erros nunca mostram o token.

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
│ Job 1: "testar"                  │  roda em todo Pull Request (e cada push nele) e em todo push na main
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
| CA9 | Limite por minuto funciona no link público | Com `identificar_por_ip: true`: fazer mais perguntas seguidas do que `perguntas_por_minuto_por_pessoa` permite, e aparece o aviso para aguardar. Se a identificação tiver sido desligada no P15, este critério é verificado pelo CA25. |
| CA10 | O limite não é burlado recarregando a página | Com `identificar_por_ip: true`: atingir o limite, recarregar a página e perguntar de novo, e o aviso **continua** aparecendo. Se a identificação tiver sido desligada no P15, a recarga não importa, porque vale só o limite global (CA25). |
| CA11 | Bloqueio não gasta crédito | Nos logs do Space, as perguntas bloqueadas aparecem como "limite atingido", sem nenhuma chamada a provedor. |
| CA12 | Limite de gastos definido | O painel de cada provedor usado mostra um limite de gastos configurado. |
| CA13 | Chave real é detectada | **Só no seu computador**, sem commit: criar um arquivo `.md` temporário com uma chave **falsa no formato completo** (eu forneço o comando que a gera), rodar `git add` nele (sem commit), rodar `python scripts/verificar_segredos.py` e ver o alerta com o arquivo e a linha, sem a chave inteira. Depois, rodar `git rm --cached` e apagar o arquivo. **Nunca** fazer commit ou push dele. No GitHub, a detecção já é comprovada pelo T8. |
| CA14 | Sem falso alarme na documentação | Com a SPEC, o README e o `.env.example` como estão, a verificação de segurança passa. |
| CA15 | Versões alinhadas | Em um PR, mudar a versão do Gradio só no `requirements.txt`: o Actions fica **vermelho**. |
| CA16 | Arquivo antigo some do Space | Adicionar `assets/teste.txt`, publicar e conferir que ele aparece na aba *Files* do Space. Depois, remover o arquivo do projeto, publicar de novo e conferir que ele **sumiu** do Space. A logo continua lá. |
| CA17 | O que precisa permanecer, permanece | Depois de uma publicação, conferir que o `.gitattributes` continua no Space e que os Secrets (chaves de IA) continuam configurados. |
| CA18 | Cores personalizadas aparecem | Trocar a `cor_primaria` para uma cor bem diferente (ex.: `#E11D48`) e ver os botões mudarem no link. |
| CA19 | Cor ilegível é bloqueada | Em um PR, colocar `cor_secundaria: "#FFFF66"` com tema `claro`: o Actions fica **vermelho**, com mensagem sugerindo uma cor mais escura. |
| CA20 | Texto dos botões legível | No tema `claro`, com `cor_primaria: "#D97706"` (laranja: contraste 3,19 com o fundo, passa na regra de bordas), o texto dos botões fica **preto** (contraste 6,59). Com `#2563EB` (azul-escuro), fica **branco** (contraste 5,17). |
| CA21 | A IA lembra da conversa (RF2) | Perguntar "O que é ETL?" e, em seguida, "Me dê um exemplo disso". A segunda resposta fala de ETL sem precisar repetir o assunto. |
| CA22 | As instruções são seguidas (RF3) | Perguntar algo em inglês (ex.: "What is a data lake?"). A resposta vem em **português do Brasil**, simples e com exemplo, como manda o `config.yml`. |
| CA23 | Pergunta longa é recusada (RF12) | Colar um texto com mais de 2000 caracteres: aparece a mensagem pedindo para resumir, e os logs mostram que nenhum provedor foi chamado. |
| CA24 | Identificação pelo IP comprovada no Hugging Face (RF17) | Seguir os 4 itens de "Como testar a identificação no Hugging Face" (seção 4.3): mesma pessoa = mesmo identificador; rede diferente = identificador diferente; `X-Forwarded-For` falso **não** muda o identificador; os logs mostram a quantidade de itens esperada. **Resultado:** se tudo passar, `identificar_por_ip: true`; se algo falhar, `identificar_por_ip: false` e a limitação registrada no `README.md`. Os dois resultados são aceitos, desde que a decisão esteja registrada. |
| CA25 | Proteção global funciona sem identificação (RF11) | Com `perguntas_por_minuto_total` baixo **temporariamente** (ex.: 3), fazer perguntas pelo computador e pelo celular (redes diferentes): ao passar de 3 no mesmo minuto, **ambos** veem o aviso de "muito movimentado". Depois, voltar o valor original. |

---

## 9. Ordem dos passos de implementação (P)

Cada passo é pequeno e termina com algo que dá para testar. Só passo para o próximo quando o anterior estiver funcionando.

| # | Passo | Resultado esperado |
|---|---|---|
| P1 | Criar a estrutura básica: `.gitignore`, `.env.example`, `requirements*.txt` (Gradio fixado), pastas | Projeto organizado, sem nenhuma chave. |
| P2 | Criar o `scripts/verificar_segredos.py` e o teste T8 | Proteção contra vazamento ativa desde o começo. |
| P3 | Criar o `assistente/cores.py` e o teste T2 | Cálculo de contraste funcionando. |
| P4 | Criar o `config.yml` (com `identificar_por_ip: false`), a logo `assets/logo.svg` e o `assistente/config.py` (leitura + validação, usando `cores.py`) | Configuração validada com mensagens claras; a logo já existe, então o teste T1 passa desde o início. |
| P5 | Escrever o teste T1 e o `scripts/validar_config.py` | Testes de configuração passando. |
| P6 | Criar o `assistente/provedores.py` (provedores + fallback só em falhas temporárias) e o teste T3 | Cada provedor sabe enviar uma pergunta, e o fallback funciona (testado com simulação, sem rede). |
| P7 | Criar o `assistente/limites.py` (limites globais, identificação segura pelo último item do `X-Forwarded-For`, identificador anônimo) e o teste T4 | Limites funcionando no servidor; IP inventado não engana. |
| P8 | Criar o `assistente/chat.py` (limites → histórico → fallback do P6, logs sem conversas) e o teste T5 | Conversa completa, protegida e com troca de provedor. |
| P9 | Criar o `assistente/interface.py`, o `app.py` e o teste T6 | Chat abrindo no navegador do seu computador, com as cores do `config.yml`. |
| P10 | Atualizar o `README.md` (cabeçalho do Hugging Face com `sdk_version`) e criar o teste T7 | Versões alinhadas e conferidas. |
| P11 | Criar o `scripts/publicar.py` e o teste T9 | Regras de envio, exclusão e proteção conferidas. |
| P12 | Criar o `.github/workflows/ci-deploy.yml` (só o Job "testar") | Testes rodando automaticamente no GitHub. |
| P13 | Conferir os modelos (`scripts/conferir_modelos.py`, sem custo) e fazer a configuração inicial no Hugging Face, no GitHub e nos provedores seguindo o `GUIA-publicacao.md` (seção 7.3) | Modelos confirmados, segredos criados e limites de gastos definidos (feito por você, com o guia). |
| P14 | Adicionar o Job "publicar" ao workflow | Publicação automática funcionando, só com os limites globais (`identificar_por_ip: false`). |
| P15 | Testar a identificação pelo IP no Space (seção 4.3, CA24): ligar `identificar_por_ip` temporariamente, fazer os 4 testes e decidir | Decisão registrada: identificação ligada (comprovada) **ou** desligada, com a limitação anotada no `README.md`. |
| P16 | Conferir todos os critérios de aceite (CA1 a CA25) | Parte 1 concluída. ✅ |

---

## 10. Erros comuns e soluções

| Erro / sintoma | Causa provável | Solução |
|---|---|---|
| Space mostra **"Configuration error"** | Falta o cabeçalho YAML no topo do `README.md` ou ele está mal formatado | Conferir se o README começa com `---`, contém `sdk: gradio`, `sdk_version` e `app_file: app.py`, e fecha com `---`. |
| Space mostra **"Runtime error"** / `ModuleNotFoundError` | Biblioteca faltando no `requirements.txt` | Adicionar a biblioteca ao `requirements.txt` e publicar de novo. |
| App funciona no computador mas quebra no Space | Versão do Gradio diferente entre o README e o `requirements.txt` | Usar o mesmo número nos dois lugares; o teste T7 avisa antes de publicar. |
| Chat responde sempre a mensagem amigável de erro | Nenhuma chave configurada no Space, ou o **primeiro** provedor com chave tem erro de chave, permissão ou cobrança (o fallback para nesses casos) | Ler os logs do Space: a linha "Erro de configuração" diz qual provedor e o que corrigir. Conferir *Settings → Secrets*; os nomes devem ser exatamente `OPENROUTER_API_KEY` etc. Depois, reiniciar o Space. |
| Erro **401 / Unauthorized** nos logs | Chave errada, expirada ou revogada | Gerar uma nova chave no site do provedor e colar de novo. **O fallback não cobre esse erro**: enquanto não for corrigido, o chat não responde. Para usar outro provedor enquanto isso, apague a chave errada do Space (provedor sem chave é pulado) ou coloque `ativo: false` nele. |
| Erro de **cobrança** nos logs (402, ou 429 `insufficient_quota`, ou "credit balance is too low") | Conta do provedor sem saldo ou limite de gastos atingido | Adicionar créditos, aumentar o limite de gastos ou usar um modelo `:free` do OpenRouter. **O fallback não cobre esse erro**, de propósito, para você perceber o problema. Enquanto isso, dá para desligar o provedor com `ativo: false`. |
| Erro **404 / model not found** | Nome do modelo errado ou modelo descontinuado | Conferir o nome exato no site do provedor e corrigir no `config.yml`. |
| Erro **429 / rate limit** do provedor | Muitas perguntas em pouco tempo (comum em modelos gratuitos) | Esperar um pouco; o fallback passa para o próximo provedor (é uma falha temporária). Se for frequente, reduzir os `limites`. |
| Muita gente vê "limite de uso de hoje atingido" | `perguntas_por_dia_total` baixo demais para o movimento | Aumentar o valor no `config.yml`, se o orçamento permitir. |
| Várias pessoas da mesma escola ou empresa são bloqueadas juntas | Elas saem para a internet pelo **mesmo IP**, então contam como uma pessoa só | Aumentar `perguntas_por_minuto_por_pessoa` e `perguntas_por_dia_por_pessoa`. Limite conhecido desta versão simples. |
| Todo mundo recebe o **mesmo** identificador nos logs | A identificação não está funcionando no Space (ex.: o Hugging Face mudou o jeito de preencher o `X-Forwarded-For`) | Colocar `identificar_por_ip: false` e registrar a limitação no `README.md`. Os limites globais continuam protegendo. |
| Logs mostram muitas pessoas "não identificadas" | O `X-Forwarded-For` não chegou ou chegou num formato inesperado | Conferir nos logs quantos itens a lista tinha. Se o problema for constante, desligar `identificar_por_ip`. |
| Aviso "assistente muito movimentado" aparece com frequência | `perguntas_por_minuto_total` baixo demais para o movimento | Aumentar o valor no `config.yml`, se o orçamento permitir. |
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
- **Aprovar como está**, e eu começo pelo passo P1 (de P1 a P16); ou
- **Pedir ajustes**.

Nenhum código será escrito até a sua autorização final.
