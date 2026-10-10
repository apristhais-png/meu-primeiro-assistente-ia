# SPEC — Parte 1: Assistente de IA com CI/CD e publicação

> **Status:** aguardando aprovação. Nenhum código será escrito antes da sua autorização.
>
> **Baseado em:** `IDEIA-parte1.md`
>
> **Decisões já tomadas:**
> - Interface: **Python + Gradio**
> - Ordem dos provedores de IA: **OpenRouter → Anthropic → OpenAI**
> - Arquivo de configuração: **YAML** (`config.yaml`)
> - Publicação: **automática a cada push na branch `main`**, só se os testes passarem

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

---

## 1. Objetivo do projeto

Criar um **chat de inteligência artificial que ensina Engenharia de Dados e IA de forma simples**, acessível por qualquer pessoa em um **link público no navegador**.

Nesta Parte 1 o foco é ter a **base funcionando de ponta a ponta**:

1. Um chat simples que conversa usando IA.
2. Personalização (nome, cores, logo, instruções e modelos) **por um único arquivo**, o `config.yaml`, sem mexer no código.
3. **Troca automática de provedor** se um deles falhar.
4. **Testes automáticos** que impedem a publicação de código ou configuração com erro.
5. **Publicação automática** no Hugging Face Spaces pelo GitHub Actions.
6. **Nenhuma chave de API** dentro do código ou do repositório.

**Fora do escopo agora** (ficam para as próximas partes): base de documentos (RAG), interface profissional, login e histórico de conversas salvo.

---

## 2. Tecnologias utilizadas e o motivo de cada escolha

| Tecnologia | Para que serve | Por que escolhemos |
|---|---|---|
| **Python 3.11** | Linguagem principal | É a linguagem mais usada em Dados e IA, fácil de ler e com ótimas bibliotecas. A versão 3.11 é estável e aceita pelo Hugging Face. |
| **Gradio** | Cria a tela do chat no navegador | Já tem um componente de chat pronto (`ChatInterface`), aceita cores e logo, e o Hugging Face Spaces roda Gradio direto, sem configuração extra. |
| **PyYAML** | Lê o arquivo `config.yaml` | YAML é fácil de ler e aceita comentários (`#`), então dá para explicar cada campo dentro do próprio arquivo. |
| **Pydantic** | Confere se a configuração está correta | Diz exatamente *qual* campo está errado e *por quê* (ex.: "cor inválida", "falta o nome"). É isso que impede publicar configuração errada. |
| **openai (biblioteca)** | Conversa com a OpenAI **e** com o OpenRouter | O OpenRouter usa o mesmo "idioma" da OpenAI, então uma biblioteca atende os dois, trocando só o endereço. Menos código. |
| **anthropic (biblioteca)** | Conversa com a Anthropic (Claude) | Biblioteca oficial, a forma mais segura e atualizada de usar o Claude. |
| **python-dotenv** | Lê as chaves de um arquivo `.env` no seu computador | Permite testar localmente sem escrever chaves no código. O `.env` nunca vai para o GitHub. |
| **pytest** | Roda os testes automáticos | Padrão do mercado em Python, simples de escrever e de ler. |
| **Ruff** | Verifica o estilo e erros comuns no código | Muito rápido, pega erros bobos (variável não usada, import faltando) antes dos testes. |
| **GitHub** | Guarda o código e o histórico | Pedido na IDEIA; também é onde o GitHub Actions roda. |
| **GitHub Actions** | Testa e publica automaticamente | Gratuito para repositórios públicos e integrado ao GitHub. |
| **Hugging Face Spaces** | Hospeda o chat com link público | Gratuito, feito para apps de IA, com área própria para segredos. |
| **huggingface_hub (CLI `hf`)** | Envia os arquivos do GitHub para o Space | Mais simples e confiável do que `git push` direto para o Hugging Face (evita erros com imagens e histórico). |

---

## 3. Estrutura de arquivos

```
meu-primeiro-assistente-ia/
├── app.py                      # Ponto de entrada: o Hugging Face roda este arquivo
├── config.yaml                 # ⭐ Personalização: nome, cores, logo, instruções, modelos
├── assets/
│   └── logo.svg                # Logo do assistente (SVG, leve e sem problemas no upload)
├── assistente/                 # Código do assistente, separado por responsabilidade
│   ├── __init__.py
│   ├── config.py               # Lê e valida o config.yaml
│   ├── provedores.py           # Fala com OpenRouter, Anthropic e OpenAI
│   ├── chat.py                 # Monta a conversa e aplica o fallback entre provedores
│   └── interface.py            # Monta a tela do Gradio usando a configuração
├── scripts/
│   └── validar_config.py       # Comando para conferir o config.yaml antes de publicar
├── tests/
│   ├── test_config.py          # Testes da configuração
│   ├── test_provedores.py      # Testes dos provedores (com simulação)
│   ├── test_chat.py            # Testes do fallback e da conversa
│   └── test_interface.py       # Testa se a tela é criada sem erro
├── .github/
│   └── workflows/
│       └── ci-deploy.yml       # Robô: testa e depois publica no Hugging Face
├── requirements.txt            # Bibliotecas que o app precisa (usado pelo Hugging Face)
├── requirements-dev.txt        # Bibliotecas extras só para testes (pytest, ruff)
├── .env.example                # Modelo de .env, SEM chaves reais
├── .gitignore                  # Garante que .env e lixo não subam para o GitHub
├── README.md                   # Explicação do projeto + cabeçalho exigido pelo Hugging Face
├── IDEIA-parte1.md             # Ideia original
└── SPEC-parte1-cicd-deploy.md  # Este documento
```

**Por que separar em vários arquivos?** Cada arquivo tem uma única tarefa. Assim fica mais fácil achar um erro, testar cada parte sozinha e trocar uma peça (ex.: um provedor) sem quebrar o resto.

**Sobre o `README.md`:** o Hugging Face exige um pequeno cabeçalho no topo do README (entre linhas `---`) dizendo que o app usa Gradio, qual arquivo rodar e qual versão do Python. Abaixo do cabeçalho fica a explicação normal do projeto.

---

## 4. Configurações do assistente

Tudo que for personalizável fica no `config.yaml`. **As chaves de API NÃO ficam aqui** (veja a seção de segurança abaixo).

### 4.1 Exemplo do `config.yaml` (ilustrativo)

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

# Aparência
aparencia:
  cor_primaria: "#2563EB"     # cor dos botões e destaques (formato #RRGGBB)
  cor_secundaria: "#10B981"
  tema: "claro"               # "claro" ou "escuro"

# Como a IA deve se comportar
instrucoes: |
  Você é um professor paciente de Engenharia de Dados e IA.
  Explique com palavras simples, exemplos do dia a dia e passo a passo.
  Responda sempre em português do Brasil.
  Se não souber algo, diga que não sabe.

# Ajustes das respostas
geracao:
  temperatura: 0.5            # 0 = mais previsível, 1 = mais criativo
  max_tokens: 1024            # tamanho máximo da resposta
  timeout_segundos: 30        # tempo máximo de espera por provedor
  max_mensagens_historico: 10 # quantas mensagens anteriores enviar para a IA

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
| `aparencia.cor_*` | Precisa estar no formato `#RRGGBB` (ex.: `#2563EB`). |
| `aparencia.tema` | Só aceita `claro` ou `escuro`. |
| `instrucoes` | Obrigatório e não pode ficar vazio. |
| `geracao.temperatura` | Número entre 0 e 1. |
| `geracao.max_tokens` | Número inteiro entre 1 e 8000. |
| `geracao.timeout_segundos` | Número entre 5 e 120. |
| `provedores` | Pelo menos 1 provedor ativo; nomes só podem ser `openrouter`, `anthropic` ou `openai`; sem repetição. |
| Campos desconhecidos | São recusados (pega erros de digitação, como `nomee`). |

### 4.3 Segurança: onde ficam as chaves de API

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
- O `.env.example` mostra apenas os **nomes** das variáveis, sem valores.
- Um provedor sem chave é **pulado automaticamente** (com aviso no log), sem derrubar o app.
- Mensagens de erro e logs **nunca** mostram a chave.

---

## 5. Funcionalidades necessárias

| # | Funcionalidade | Descrição simples |
|---|---|---|
| F1 | **Chat no navegador** | A pessoa digita uma pergunta e recebe a resposta da IA na mesma tela. |
| F2 | **Memória da conversa atual** | A IA lembra das últimas mensagens *da conversa aberta* (limitado por `max_mensagens_historico`). Ao recarregar a página, a conversa recomeça (histórico salvo fica para depois). |
| F3 | **Instruções do assistente** | O texto de `instrucoes` é enviado em toda conversa para definir o jeito de responder. |
| F4 | **Personalização visual** | Nome, descrição, logo, cores, tema, mensagem de boas-vindas e perguntas de exemplo vêm do `config.yaml`. |
| F5 | **Escolha de provedor por ordem** | Usa o primeiro provedor ativo e com chave configurada. |
| F6 | **Fallback automático** | Se o provedor falhar (fora do ar, sem crédito, tempo esgotado, chave inválida), tenta o próximo da lista. |
| F7 | **Mensagem amigável quando tudo falha** | Se nenhum provedor responder, mostra: *"Desculpe, não consegui responder agora. Tente novamente em alguns minutos."* Sem mostrar erros técnicos à pessoa. |
| F8 | **Validação da configuração** | Ao iniciar, o app confere o `config.yaml`. Se houver erro, mostra claramente qual campo está errado. |
| F9 | **Script de validação** | `python scripts/validar_config.py` confere o arquivo antes de publicar (usado também pelo GitHub Actions). |
| F10 | **Logs simples** | Registra qual provedor respondeu e quais falharam, sem registrar chaves nem o conteúdo das conversas. |

---

## 6. Testes automáticos

**Princípio:** os testes **nunca** chamam as IAs de verdade. Usamos **simulações (mocks)**. Assim os testes são gratuitos, rápidos, não precisam de chaves e não falham por causa da internet.

### 6.1 `tests/test_config.py` — configuração
- O `config.yaml` real do repositório é válido. *(Este é o teste que impede publicar configuração errada.)*
- Recusa configuração sem `nome`.
- Recusa cor em formato errado (ex.: `azul` ou `#12`).
- Recusa `temperatura` fora de 0 a 1.
- Recusa provedor desconhecido (ex.: `gemini`).
- Recusa lista de provedores vazia ou sem nenhum ativo.
- Recusa provedor repetido.
- Recusa logo que não existe.
- Recusa campo desconhecido (erro de digitação).

### 6.2 `tests/test_provedores.py` — provedores
- Cada provedor monta a requisição com o modelo, a temperatura e as instruções certas.
- O OpenRouter usa o endereço correto (`https://openrouter.ai/api/v1`).
- Um provedor sem chave é marcado como "indisponível".
- A chave nunca aparece em mensagens de erro.

### 6.3 `tests/test_chat.py` — conversa e fallback
- Se o 1º provedor responde, o 2º não é chamado.
- Se o 1º falha, o 2º é chamado e sua resposta é usada.
- Se o 1º e o 2º falham, o 3º é usado.
- Se todos falham, aparece a mensagem amigável (F7).
- Provedores com `ativo: false` são ignorados.
- O histórico enviado respeita o limite `max_mensagens_historico`.

### 6.4 `tests/test_interface.py` — tela
- A interface do Gradio é criada sem erro usando o `config.yaml` real.
- O título da tela é o `nome` da configuração.

### 6.5 Verificação de segurança
- Uma etapa no GitHub Actions procura padrões de chaves (ex.: `sk-`, `sk-ant-`, `sk-or-`, `hf_`) nos arquivos do repositório e **falha** se encontrar algum.

### 6.6 Como rodar no seu computador
```
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
pytest
python scripts/validar_config.py
```

---

## 7. Publicação pelo GitHub Actions e Hugging Face

### 7.1 Visão geral do fluxo

```
Você faz push no GitHub
        │
        ▼
┌──────────────────────────────┐
│ Job 1: "testar"              │  roda em TODO push e Pull Request
│  1. Baixa o código           │
│  2. Instala Python 3.11      │
│  3. Instala as bibliotecas   │
│  4. Procura chaves vazadas   │
│  5. Ruff (estilo)            │
│  6. Valida o config.yaml     │
│  7. pytest (todos os testes) │
└──────────────┬───────────────┘
               │ passou? E é a branch main?
               ▼
┌──────────────────────────────┐
│ Job 2: "publicar"            │  só roda se o Job 1 passar E for push na main
│  1. Baixa o código           │
│  2. Instala o huggingface_hub│
│  3. Envia os arquivos para   │
│     o Space (usando HF_TOKEN)│
└──────────────┬───────────────┘
               ▼
Hugging Face reconstrói o Space e o link público é atualizado
```

**Regra mais importante:** se **qualquer** passo do Job 1 falhar, o Job 2 **não roda**. Configuração errada nunca chega ao link público.

### 7.2 O que é enviado ao Space
Somente o necessário para o app rodar: `app.py`, `config.yaml`, `assistente/`, `assets/`, `requirements.txt` e `README.md`. Testes, workflows e documentos de SPEC **não** são enviados.

### 7.3 Configuração inicial (feita uma única vez, por você, com meu passo a passo)
1. **Criar o Space** no Hugging Face: *New Space* → SDK **Gradio** → visibilidade **Public**.
2. **Adicionar as chaves de IA** no Space: *Settings → Variables and secrets → New secret* (`OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`). Não é preciso ter as três; o fallback só usa as que existirem.
3. **Criar um token** no Hugging Face: *Settings → Access Tokens* → tipo **Write** (ou *fine-grained* com permissão de escrita só nesse Space).
4. **No GitHub**, em *Settings → Secrets and variables → Actions*:
   - Secret `HF_TOKEN` = o token do passo 3.
   - Variable `HF_SPACE_ID` = `seu-usuario/nome-do-space`.
5. Fazer um push na `main` e acompanhar na aba **Actions** do GitHub.

### 7.4 Como mudar uma configuração e ver a atualização
1. Editar o `config.yaml` (ex.: trocar `cor_primaria`).
2. Fazer commit e push para a `main` (ou abrir um Pull Request e fazer o merge).
3. O GitHub Actions testa e publica (normalmente em poucos minutos).
4. O Space reconstrói; ao recarregar o link, a mudança aparece.

---

## 8. Critérios para verificar se tudo funciona

A Parte 1 só será considerada **pronta** quando **todos** os itens abaixo forem verdadeiros:

| # | Critério | Como verificar |
|---|---|---|
| C1 | O chat responde pelo link público | Abrir `https://huggingface.co/spaces/<usuario>/<space>` e fazer uma pergunta. |
| C2 | A personalização funciona | Mudar o `nome` e a `cor_primaria` no `config.yaml`, fazer push e ver a mudança no link. |
| C3 | O fallback funciona | Remover temporariamente a chave do OpenRouter no Space: o chat continua respondendo pelo próximo provedor. |
| C4 | Falha total é amigável | Sem nenhuma chave, o chat mostra a mensagem amigável, sem erro técnico. |
| C5 | Configuração errada é bloqueada | Em um Pull Request, colocar `cor_primaria: "azul"`: o GitHub Actions fica **vermelho** e nada é publicado. |
| C6 | Código com erro é bloqueado | Um teste falhando impede o Job "publicar". |
| C7 | Nenhuma chave no repositório | A verificação de segurança passa e uma busca por `sk-` e `hf_` no GitHub não encontra nada. |
| C8 | Testes passam localmente | `pytest` mostra todos os testes passando. |
| C9 | Pull Request não publica | Abrir um PR roda os testes, mas **não** publica. |

---

## 9. Ordem das tarefas de implementação

Cada tarefa é pequena e termina com algo que dá para testar. Só passo para a próxima quando a anterior estiver funcionando.

| # | Tarefa | Resultado esperado |
|---|---|---|
| T1 | Criar a estrutura básica: `.gitignore`, `.env.example`, `requirements*.txt`, pastas | Projeto organizado, sem nenhuma chave. |
| T2 | Criar o `config.yaml` e o `assistente/config.py` (leitura + validação) | Configuração validada com mensagens de erro claras. |
| T3 | Escrever `tests/test_config.py` e o `scripts/validar_config.py` | Testes de configuração passando. |
| T4 | Criar o `assistente/provedores.py` (OpenRouter, Anthropic, OpenAI) | Cada provedor sabe enviar uma pergunta. |
| T5 | Escrever `tests/test_provedores.py` (com simulações) | Testes dos provedores passando. |
| T6 | Criar o `assistente/chat.py` com o fallback | Conversa usando a ordem e trocando de provedor quando falha. |
| T7 | Escrever `tests/test_chat.py` | Testes de fallback passando. |
| T8 | Criar o `assistente/interface.py`, o `app.py` e a logo | Chat abrindo no navegador do seu computador. |
| T9 | Escrever `tests/test_interface.py` | Teste da tela passando. |
| T10 | Atualizar o `README.md` (cabeçalho do Hugging Face + instruções) | Repositório pronto para o Space. |
| T11 | Criar o `.github/workflows/ci-deploy.yml` (só o Job "testar") | Testes rodando automaticamente no GitHub. |
| T12 | Configuração inicial no Hugging Face e no GitHub (seção 7.3) | Segredos criados (feito por você, com meu guia). |
| T13 | Adicionar o Job "publicar" ao workflow | Publicação automática funcionando. |
| T14 | Conferir todos os critérios da seção 8 | Parte 1 concluída. ✅ |

---

## 10. Erros comuns e soluções

| Erro / sintoma | Causa provável | Solução |
|---|---|---|
| Space mostra **"Configuration error"** | Falta o cabeçalho YAML no topo do `README.md` ou ele está mal formatado | Conferir se o README começa com `---`, contém `sdk: gradio` e `app_file: app.py`, e fecha com `---`. |
| Space mostra **"Runtime error"** / `ModuleNotFoundError` | Biblioteca faltando no `requirements.txt` | Adicionar a biblioteca ao `requirements.txt` e publicar de novo. |
| Chat responde sempre a mensagem amigável de erro | Nenhuma chave configurada no Space ou todas inválidas | Conferir *Settings → Secrets* do Space; os nomes devem ser exatamente `OPENROUTER_API_KEY` etc. Depois, reiniciar o Space. |
| Erro **401 / Unauthorized** nos logs | Chave errada, expirada ou copiada com espaço sobrando | Gerar uma nova chave no site do provedor e colar de novo, sem espaços. |
| Erro **402 / sem crédito** | Conta do provedor sem saldo | Adicionar créditos ou usar um modelo `:free` do OpenRouter; o fallback cobre enquanto isso. |
| Erro **404 / model not found** | Nome do modelo errado ou modelo descontinuado | Conferir o nome exato no site do provedor e corrigir no `config.yaml`. |
| Erro **429 / rate limit** | Muitas perguntas em pouco tempo (comum em modelos gratuitos) | Esperar um pouco; o fallback passa para o próximo provedor. |
| GitHub Actions falha em **"publicar"** com 401/403 | `HF_TOKEN` ausente, errado ou só com permissão de leitura | Criar um token com permissão **Write** e atualizar o secret no GitHub. |
| GitHub Actions falha com **"Space not found"** | `HF_SPACE_ID` digitado errado | Usar o formato `usuario/nome-do-space`, igual à URL do Space. |
| Job "publicar" nunca roda | O push não foi na `main`, ou algum teste falhou | Ver a aba **Actions**; corrigir o teste que falhou ou fazer o merge na `main`. |
| Validação reclama de **cor inválida** | Cor escrita como nome (`azul`) ou faltando dígitos | Usar o formato `#RRGGBB`, ex.: `#2563EB`. |
| Erro ao ler o YAML (`mapping values are not allowed`) | Indentação errada ou falta de aspas | Usar **2 espaços** (nunca TAB) e colocar textos com `:` entre aspas. |
| A logo não aparece | Caminho errado em `assistente.logo` | O caminho é relativo à raiz do projeto, ex.: `assets/logo.svg`. A validação já avisa se o arquivo não existir. |
| Mudei o `config.yaml` e nada mudou no link | Publicação ainda em andamento ou o navegador guardou a versão antiga | Esperar o Actions ficar verde e o Space terminar o *build*; recarregar com Ctrl+Shift+R. |
| Chave apareceu no GitHub por engano | `.env` enviado ou chave colada no código | **Revogar a chave imediatamente** no site do provedor e criar outra. Apagar o arquivo não basta, pois ela continua no histórico. |
| Testes passam no seu computador mas falham no Actions | Versão de biblioteca ou de Python diferente | Fixar as versões no `requirements.txt` e usar Python 3.11 nos dois lugares. |

---

## Próximo passo

Revise esta SPEC. Você pode:
- **Aprovar como está**, e eu começo pela tarefa T1; ou
- **Pedir ajustes** (por exemplo: outros modelos, outras cores, mais ou menos testes).

Nenhum código será escrito até a sua autorização.
