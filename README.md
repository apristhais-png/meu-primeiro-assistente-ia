---
title: Professor de Dados
emoji: 📊
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 6.30.0
python_version: "3.11"
app_file: app.py
pinned: false
short_description: Aprenda Engenharia de Dados e IA de forma simples
---

# Meu primeiro assistente de IA

Um chat que ensina **Engenharia de Dados e IA** de forma simples, aberto para
qualquer pessoa pelo navegador.

> **Sobre o bloco no topo deste arquivo (entre as linhas `---`):** é o cabeçalho
> que o Hugging Face Spaces lê para saber como rodar o app: usa **Gradio**
> (`sdk`), na versão `sdk_version`, com **Python 3.11**, abrindo o arquivo
> **`app.py`**. Não apague esse bloco.
>
> ⚠️ O `sdk_version` precisa ser **igual** à versão do Gradio no
> `requirements.txt`. Para atualizar o Gradio, mude os dois juntos, no mesmo
> commit. Um teste automático (`tests/test_versoes.py`) bloqueia a publicação se
> eles forem diferentes.

## O que ele faz

- Conversa usando IA, com **troca automática de provedor** (OpenRouter →
  Anthropic → OpenAI) quando um deles tem uma falha temporária.
- É personalizado **só pelo arquivo `config.yml`**: nome, logo, cores,
  instruções, modelos e limites de uso.
- Protege seus créditos com **limites de uso conferidos no servidor**.
- Não guarda nenhuma chave de API no código.

## Como rodar no seu computador

Na pasta do projeto:

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # no Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
```

Para conversar com uma IA de verdade, copie o `.env.example` para `.env` e
coloque pelo menos uma chave (o `.env` nunca vai para o GitHub). Depois:

```bash
python app.py
```

Abra no navegador o endereço mostrado (normalmente http://127.0.0.1:7860).
Sem nenhuma chave, a tela abre, mas as perguntas recebem uma mensagem amigável
de erro.

## Como personalizar

Edite o `config.yml` (cada campo tem um comentário explicando) e confira se
está tudo certo com:

```bash
python scripts/validar_config.py
```

## Como conferir se está tudo certo

```bash
pytest                               # testes automáticos (sem chamar IAs reais)
ruff check .                         # estilo e erros comuns
python scripts/validar_config.py     # configuração
python scripts/verificar_segredos.py # chaves de API esquecidas nos arquivos
```

## Onde ficam as chaves de API

| Chave | Onde configurar |
|---|---|
| `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | No seu computador: arquivo `.env`. No Hugging Face: *Settings → Variables and secrets*. |

**Nunca** coloque chaves no `config.yml`, no código ou em qualquer arquivo
enviado ao GitHub.

## Documentação do projeto

- `IDEIA-parte1.md`: a ideia original.
- `SPEC-parte1-cicd-deploy.md`: a especificação completa (o que o sistema deve
  fazer, testes, critérios de aceite e ordem de implementação).
