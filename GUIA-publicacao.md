# Guia de publicação (passo P13)

Este guia prepara tudo para o assistente ir ao ar no **Hugging Face Spaces**.
Nada aqui publica o app: a publicação automática só entra no passo P14.

> 🔒 **Regra de ouro:** chaves e tokens **nunca** vão para o chat, para o código,
> para issues/PRs ou para qualquer arquivo do repositório. Eles só são colados
> nas telas de *Secrets* do Hugging Face e do GitHub (e no seu `.env` local).
> Se uma chave vazar, **revogue-a na hora** no site do provedor e crie outra.

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

- Conta no **Hugging Face** (gratuita): https://huggingface.co/join
- Pelo menos **uma** chave de IA. A mais barata para começar é a do
  **OpenRouter** com modelo gratuito.
- Acesso de administrador ao repositório no **GitHub** (você já tem).

---

## 3. Passo a passo (feito por você)

### Passo A: limite de gastos em cada provedor (critério CA12)
No painel de cada provedor que você usar, defina um **limite de gastos**
mensal (por exemplo, alguns dólares). É a proteção mais forte dos seus créditos:
vale mesmo se algo der errado no código.

| Provedor | Onde procurar |
|---|---|
| OpenRouter | Painel da conta → *Credits* / *Keys* (limite por chave) |
| Anthropic | Console → *Settings* → *Limits* / *Billing* |
| OpenAI | Plataforma → *Settings* → *Limits* / *Billing* |

> Os nomes dos menus mudam de vez em quando; se não encontrar, procure por
> "limit" ou "budget" na página de cobrança.

### Passo B: criar o Space
1. Acesse https://huggingface.co/new-space
2. **Space name:** por exemplo `professor-de-dados`.
3. **SDK:** escolha **Gradio**.
4. **Hardware:** **CPU basic** (gratuito). Ele "dorme" depois de um tempo sem
   uso; o primeiro acesso depois disso demora um pouco.
5. **Visibilidade:** **Public**.
6. Crie o Space. Anote o nome completo, no formato `seu-usuario/professor-de-dados`.
   Esse é o seu **HF_SPACE_ID**.

> O Hugging Face cria sozinho um `README.md` e um `.gitattributes`. Pode
> deixar como está: a publicação do P14 substitui o `README.md` pelo nosso e
> **nunca** mexe no `.gitattributes`.

### Passo C: cadastrar as chaves de IA no Space
1. No Space: **Settings** → **Variables and secrets** → **New secret**.
2. Cadastre **como Secret** (nunca como *Variable*, que é **pública**):

| Nome (exatamente assim) | Valor |
|---|---|
| `OPENROUTER_API_KEY` | sua chave do OpenRouter |
| `ANTHROPIC_API_KEY` | sua chave da Anthropic (se tiver) |
| `OPENAI_API_KEY` | sua chave da OpenAI (se tiver) |

Depois de salvo, o valor de um *Secret* não aparece mais na tela, nem para
você. O Space reinicia sozinho quando os secrets mudam.

### Passo D: criar o token de publicação do Hugging Face
1. https://huggingface.co/settings/tokens → **Create new token**.
2. Prefira o tipo **Fine-grained** e dê permissão de **escrita** (*write*)
   **somente** ao repositório do seu Space. Se essa opção não aparecer de forma
   clara, um token do tipo **Write** também funciona, mas dá acesso a todos os
   seus repositórios (mais arriscado).
3. Copie o token **uma vez** e cole direto no GitHub (passo E). Não guarde em
   arquivos.

### Passo E: cadastrar no GitHub
No repositório: **Settings** → **Secrets and variables** → **Actions**.

| Aba | Botão | Nome | Valor |
|---|---|---|---|
| **Secrets** | *New repository secret* | `HF_TOKEN` | o token do passo D |
| **Variables** | *New repository variable* | `HF_SPACE_ID` | `seu-usuario/professor-de-dados` |

O `HF_SPACE_ID` é uma *Variable* (não é segredo: é o mesmo nome que aparece no
link público do Space). O `HF_TOKEN` é *Secret*.

> Até o P14, nenhum workflow usa esses valores: o job "testar" foi feito para
> **não** ter acesso a segredos.

### Passo F (opcional): simular a publicação no seu computador
Sem token e sem mudar nada no Space, você pode ver o que seria enviado:

```bash
# Linux/macOS
HF_SPACE_ID=seu-usuario/professor-de-dados python scripts/publicar.py

# Windows (PowerShell)
$env:HF_SPACE_ID="seu-usuario/professor-de-dados"; python scripts/publicar.py
```

A saída mostra `=== SIMULAÇÃO (nada será alterado) ===` e as listas do que
seria **enviado**, **apagado** e **mantido**.

---

## 4. Checklist antes do P14

- [ ] Modelos conferidos com `python scripts/conferir_modelos.py` (ou no site de cada provedor)
- [ ] Limite de gastos definido em cada provedor usado
- [ ] Space criado com SDK **Gradio**, hardware gratuito e visibilidade pública
- [ ] Chaves de IA cadastradas como **Secrets** no Space
- [ ] `HF_TOKEN` cadastrado como **Secret** no GitHub
- [ ] `HF_SPACE_ID` cadastrado como **Variable** no GitHub

Quando terminar, me conte **só** o que foi feito (por exemplo: "Space criado:
`usuario/professor-de-dados`; secrets do OpenRouter e da Anthropic cadastrados;
limite de gastos definido; HF_TOKEN e HF_SPACE_ID no GitHub").
**Nunca** envie as chaves ou o token no chat.
