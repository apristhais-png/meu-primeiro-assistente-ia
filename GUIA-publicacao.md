# Guia de publicação no Render (passos P13 e P14)

Este guia prepara tudo para o assistente ir ao ar no **Render** (plano gratuito,
*Free Web Service*). Nada aqui publica o app sozinho: quem cria o serviço no
Render é você, seguindo os passos abaixo.

> **Por que Render?** O Hugging Face Spaces passou a exigir plano pago para
> rodar apps Gradio. O app, os testes e o GitHub Actions continuam os mesmos;
> só mudou o lugar onde o app fica no ar.

> 🔒 **Regra de ouro:** chaves **nunca** vão para o chat, para o código, para
> issues/PRs ou para qualquer arquivo do repositório. Elas só são coladas na aba
> *Environment* do Render (e no seu `.env` local). Se uma chave vazar,
> **revogue-a na hora** no site do provedor e crie outra.

---

## 1. Situação dos modelos do `config.yml` (conferido em 11/10/2026)

| Provedor | Modelo no `config.yml` | Situação | Fonte |
|---|---|---|---|
| Anthropic | `claude-haiku-5-5` | ✅ **Confirmado** na documentação oficial. Aposentadoria prevista para não antes de 07/10/2027. | [platform.claude.com — Models overview](https://platform.claude.com/docs/en/about-claude/models/overview) |
| OpenRouter | `meta-llama/llama-3.3-70b-instruct:free` | ⏳ **Pendente.** A página oficial do modelo existe nos resultados de busca, mas o site do OpenRouter não abre no ambiente de desenvolvimento, então não foi possível confirmar se ele **continua disponível e gratuito hoje**. Modelos `:free` mudam com frequência. | [openrouter.ai — Llama 3.3 70B Instruct (free)](https://openrouter.ai/meta-llama/llama-3.3-70b-instruct:free) |
| OpenAI | `gpt-4o-mini` | ⏳ **Pendente.** O site da OpenAI não abre no ambiente de desenvolvimento. Resultados de busca indicam que variantes do `gpt-4o-mini` (áudio, realtime, busca) têm datas de desligamento, mas **não** confirmam a situação do modelo base. | [OpenAI — Deprecations](https://developers.openai.com/api/docs/deprecations) |

### Como confirmar os pendentes, sem custo
No seu computador (com o ambiente ativado e o `.env` com as chaves que você tiver):

```bash
python scripts/conferir_modelos.py
```

Ele só **consulta a lista de modelos** de cada provedor; nenhuma pergunta é
enviada à IA, então **nada é cobrado**. Exemplo de saída:

```
[OK]       openrouter: meta-llama/llama-3.3-70b-instruct:free (gratuito)
[OK]       anthropic: claude-haiku-5-5
[PENDENTE] openai: gpt-4o-mini (sem OPENAI_API_KEY configurada)
```

- `[OK]`: o modelo existe. No OpenRouter, ele também avisa se é **gratuito** ou **pago**.
- `[ERRO]`: o modelo **não existe**. Troque o nome no `config.yml` por um que
  apareça no site do provedor e rode de novo.
- `[PENDENTE]`: faltou a chave ou a internet; dá para conferir pelo site.

Você não precisa ter as três chaves: o assistente usa as que existirem.

---

## 2. O que você vai precisar

- Conta no **Render** (gratuita): https://render.com. Entre com a sua conta
  do **GitHub**, assim o Render consegue ler o repositório.
- Pelo menos **uma** chave de IA. A mais barata para começar é a do
  **OpenRouter** com modelo gratuito.

O que **já está pronto** no repositório:

| Arquivo | Para que serve |
|---|---|
| `render.yaml` | Configuração do serviço: web, Python, plano **free**, branch `main`, `pip install -r requirements.txt` e `python app.py`. As chaves aparecem **sem valor**. |
| `.python-version` | Faz o Render usar **Python 3.11** (o padrão dele é mais novo). |
| `app.py` | Escuta em `0.0.0.0` na porta `PORT` que o Render informa. |

---

## 3. Passo a passo (feito por você)

### Passo A: limite de gastos em cada provedor (critério CA12)
No painel de cada provedor que você usar, defina um **limite de gastos**
mensal (por exemplo, alguns dólares). É a proteção mais forte dos seus créditos.
No Render gratuito, os contadores de limite do app **zeram** sempre que o
serviço dorme, então o limite do provedor é o que garante o teto de gastos.

| Provedor | Onde procurar |
|---|---|
| OpenRouter | Painel da conta → *Credits* / *Keys* (limite por chave) |
| Anthropic | Console → *Settings* → *Limits* / *Billing* |
| OpenAI | Plataforma → *Settings* → *Limits* / *Billing* |

> Os nomes dos menus mudam de vez em quando; se não encontrar, procure por
> "limit" ou "budget" na página de cobrança.

### Passo B: decidir quando o código vai para a `main`
O Render publica a branch **`main`**. Hoje, o `render.yaml`, o `.python-version`
e o `app.py` novo estão **só no PR #1**. Eles chegam à `main` quando você fizer
o merge do PR #1 (isso fica para o P15, com a sua decisão).

### Passo C: criar o serviço no Render
**Opção 1 — pelo `render.yaml` (recomendada):**
1. No painel do Render: **New** → **Blueprint**.
2. Escolha o repositório `meu-primeiro-assistente-ia` e a branch **`main`**.
3. O Render lê o `render.yaml` e mostra o serviço `professor-de-dados`.
4. Ele vai **pedir os valores** de `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY` e
   `OPENAI_API_KEY`. Preencha as chaves que você tiver e deixe as outras vazias.

**Opção 2 — manual (se o Blueprint der algum erro):**
1. **New** → **Web Service** → escolha o repositório.
2. **Branch:** `main` · **Runtime/Language:** Python 3 · **Instance Type:** **Free**
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `python app.py`
5. Em **Environment**, adicione `GRADIO_ANALYTICS_ENABLED` = `False` e as chaves de IA.

> O valor `plan: free` do `render.yaml` foi confirmado só por fontes de
> terceiros. Se o Render reclamar dele, use a Opção 2.

### Passo D: cadastrar ou trocar as chaves depois
No serviço: **Environment** → **Add Environment Variable**.

| Nome (exatamente assim) | Valor |
|---|---|
| `OPENROUTER_API_KEY` | sua chave do OpenRouter |
| `ANTHROPIC_API_KEY` | sua chave da Anthropic (se tiver) |
| `OPENAI_API_KEY` | sua chave da OpenAI (se tiver) |

Salvar reinicia o serviço. As variáveis do Render **não** ficam no repositório
nem aparecem para quem visita o app.

### Passo E: publicar só depois dos testes
No serviço: **Settings** → **Build & Deploy** → **Auto-Deploy** →
**After CI Checks Pass**.

Assim, o Render só publica um commit da `main` quando **todas** as verificações
do GitHub Actions passarem. Se algum teste falhar, nada é publicado.

### Passo F: acompanhar o primeiro deploy
Na aba **Logs** do serviço, procure:
- a versão do Python, que deve ser **3.11**;
- `Provedores com chave configurada: ...`, mostrando **quais** provedores têm
  chave (nunca a chave em si);
- `Abrindo o app em 0.0.0.0:10000` (ou outra porta informada pelo Render).

Depois, abra o link `https://<nome-do-servico>.onrender.com`.

### Passo G (opcional): se você já configurou o Hugging Face no P13
- O `HF_TOKEN` e o `HF_SPACE_ID` **não são mais usados**. Se você os cadastrou
  no GitHub, pode apagá-los e **revogar o token** no Hugging Face.
- O Space criado no Hugging Face não é alterado por nada deste projeto. Você
  pode mantê-lo ou apagá-lo quando quiser.

---

## 4. Como o plano gratuito do Render se comporta

| O que acontece | O que significa |
|---|---|
| **Dorme após 15 minutos sem acesso** | O primeiro acesso depois disso demora **cerca de 1 minuto**. |
| **Contadores de limite zeram** quando dorme ou reinicia | O limite de gastos nos provedores (Passo A) é a proteção que não zera. |
| **750 horas grátis por mês** por conta | Serviço dormindo não gasta horas. Se acabarem, os serviços grátis param até o mês seguinte. |
| **Memória** (512 MB, segundo fontes de terceiros) | Em teste local, o app usou cerca de **190 MB** parado. |

---

## 5. Checklist antes do P15

- [ ] Modelos conferidos com `python scripts/conferir_modelos.py` (ou no site de cada provedor)
- [ ] Limite de gastos definido em cada provedor usado
- [ ] Conta no Render criada com o GitHub
- [ ] Decisão sobre o merge do PR #1 na `main` (o Render publica a `main`)

No P15, com a sua autorização: criar o serviço (Passo C), cadastrar as chaves
(Passo D), ligar o *After CI Checks Pass* (Passo E), acompanhar o primeiro
deploy (Passo F) e fazer o teste da identificação pelo IP (critério CA24).

Quando terminar cada etapa, me conte **só** o que foi feito (por exemplo:
"serviço criado: `professor-de-dados`; chave do OpenRouter cadastrada;
Auto-Deploy em After CI Checks Pass"). **Nunca** envie as chaves no chat.
