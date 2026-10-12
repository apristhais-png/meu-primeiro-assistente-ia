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

> **Onde o app fica no ar:** no **Render** (plano gratuito). O Render usa o
> `render.yaml`, o `.python-version` (Python 3.11) e roda `python app.py`. Veja o
> `GUIA-publicacao.md`.
>
> **Sobre o bloco no topo deste arquivo (entre as linhas `---`):** é o cabeçalho
> do Hugging Face Spaces, onde o projeto seria publicado antes. O Render o
> ignora, mas ele foi mantido: o `sdk_version` precisa continuar **igual** à
> versão do Gradio no `requirements.txt`, e um teste automático
> (`tests/test_versoes.py`) confere isso. Para atualizar o Gradio, mude os dois
> juntos, no mesmo commit.

## O que ele faz

- Conversa usando IA, com **troca automática de provedor** (OpenRouter →
  Anthropic → OpenAI) quando um deles tem uma falha temporária.
- É personalizado **só pelo arquivo `config.yml`**: nome, logo, cores,
  instruções, modelos e limites de uso.
- Protege seus créditos com **limites de uso conferidos no servidor**.
- Tela pensada para qualquer aparelho (computador, tablet e celular): sugestões
  clicáveis na tela inicial, botão **Nova conversa**, aviso "Pensando..."
  enquanto a IA responde, código e tabelas legíveis e navegação completa pelo
  teclado, com foco bem visível.
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

> No seu computador, o app escuta só em `127.0.0.1` (não fica visível para
> outras máquinas da rede). No Render, ele escuta em `0.0.0.0`, na porta da
> variável `PORT`, como o Render exige.

## Como publicar (Render)

1. O GitHub Actions testa cada Pull Request e cada push na `main`.
2. O Render publica a `main` sozinho, **só depois** que os testes passam
   (opção *After CI Checks Pass*).
3. As chaves de IA ficam na aba *Environment* do Render, nunca no repositório.

O passo a passo completo, incluindo os limites do plano gratuito (o serviço
dorme após 15 minutos sem acesso), está no `GUIA-publicacao.md`.

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
| `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | No seu computador: arquivo `.env`. No Render: aba *Environment* do serviço. |

**Nunca** coloque chaves no `config.yml`, no código ou em qualquer arquivo
enviado ao GitHub.

## Documentação do projeto

- `IDEIA-parte1.md`: a ideia original.
- `SPEC-parte1-cicd-deploy.md`: a especificação completa (o que o sistema deve
  fazer, testes, critérios de aceite e ordem de implementação).
- `GUIA-publicacao.md`: passo a passo para colocar o assistente no ar no
  Render (serviço, chaves, publicação só depois dos testes).
- `AUDITORIA-pre-publicacao.md`: resultado da auditoria antes da primeira
  publicação (critérios de aceite, segurança e limites).
- `scripts/publicar.py`: legado da época do Hugging Face. Foi mantido (e
  continua testado), mas **não** é usado na publicação pelo Render.
