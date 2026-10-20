# Professor de Dados (chatbot)

Um chat que ensina **Engenharia de Dados, Python, SQL e IA** com palavras
simples. Tela em **Gradio**, respostas de modelos de IA **gratuitos**,
publicado no **Render**.

```bash
python app.py        # com Poetry: poetry run python app.py
```

## Personalização sem código: `config.yml`

Nome, logo, mensagem de boas-vindas, sugestões de perguntas, cores, instruções
da IA, ajustes das respostas, limites de uso e provedores ficam no
`config.yml`. Antes de usar, ele é conferido com Pydantic:

```bash
python scripts/validar_config.py
```

A validação também confere o **contraste das cores** (regra de acessibilidade
WCAG) e sugere outra cor se o texto ficar difícil de ler.

## Tutor adaptativo

Acima da conversa há dois seletores:

| Seletor | Opções | O que muda |
|---|---|---|
| **Seu nível** | Iniciante · Intermediário · Avançado | Linguagem, tamanho dos exemplos e profundidade técnica. |
| **Modo de estudo** | Explicação · Exercício prático · Revisão | Explicação organizada; exercício com dica e critérios, **sem a solução**; ou resumo com perguntas rápidas. |

- No modo **Exercício prático**, a pessoa envia a tentativa e o tutor corrige.
  A solução completa só aparece se ela pedir ou depois de duas tentativas sem
  sucesso.
- O texto das instruções do tutor fica no código (`assistente/tutor.py`). A
  tela só manda a **opção** escolhida; qualquer valor desconhecido vira o
  padrão. Assim, ninguém consegue colocar instruções próprias por esse caminho.
- A continuidade vem do histórico da conversa (as últimas
  `max_mensagens_historico` mensagens). Nada fica guardado depois que a página
  é fechada.

## Provedores e troca automática (fallback)

Ordem definida no `config.yml`:

1. **OpenRouter**, só com modelos **gratuitos** de conversa, numa lista
   explícita (um principal e reservas);
2. **Anthropic** (reserva);
3. **OpenAI** (reserva).

Um provedor sem chave configurada é pulado.

| Falha | Tenta o próximo? |
|---|---|
| Tempo esgotado, conexão, 429, erro 5xx, resposta vazia | **Sim** |
| Chave inválida (401), sem permissão (403), sem créditos (402/cobrança) | **Não**: o problema aparece em vez de ficar escondido |
| Pedido inválido (ex.: modelo inexistente) | **Não** |

## Proteção do modelo gratuito

Antes de usar um modelo do OpenRouter, o app consulta o **catálogo oficial**
e só aceita modelos que existem, custam **zero** e respondem com texto. O
pedido ainda vai com **preço máximo zero**. Respostas que parecem de um
classificador de segurança (como "User Safety: safe") são recusadas, e o
modelo fica **15 minutos de quarentena**. Se todos estiverem em quarentena, a
pessoa recebe um aviso e nenhuma chamada é feita.

```bash
python scripts/conferir_modelos.py     # confere a lista do config.yml no catálogo
```

## Confiabilidade

| Regra | Valor |
|---|---|
| Tempo máximo por pergunta (todas as tentativas e o fallback) | 60 s |
| Tempo máximo de cada tentativa | 45 s |
| Nova tentativa no mesmo provedor | só no último provedor disponível, para falhas rápidas (conexão, 5xx, resposta vazia ou inadequada) |
| Chamadas à IA ao mesmo tempo (app inteiro) | no máximo 4, contando as canceladas |
| Perguntas ao mesmo tempo por conversa | 1 (uma segunda pergunta recebe "aguarde") |

Quando o prazo acaba, a conexão daquela tentativa é fechada, para que
chamadas abandonadas não se acumulem.

## Limites de uso (proteção dos créditos)

Conferidos **no servidor**, antes de chamar a IA:

| Limite | Valor padrão |
|---|---|
| Perguntas por minuto (todas as pessoas) | 20 |
| Perguntas por dia (todas as pessoas) | 500 (o dia vira à meia-noite de Brasília) |
| Tamanho máximo da pergunta | 2.000 caracteres |
| Limites por pessoa (por IP) | desligados por padrão (`identificar_por_ip: false`) |

## Privacidade e erros

- O conteúdo das perguntas e respostas **não** vai para os logs, só dados
  técnicos (tempo, provedor, tipo de falha).
- As chaves nunca aparecem em mensagens ou logs.
- A pessoa nunca vê detalhes técnicos de erros (`show_error=False`).
- O chat só troca **texto**: não há envio de arquivos e nenhum código enviado
  pela pessoa é executado.

## Interface

- Sugestões clicáveis na tela inicial, botão **Nova conversa** e aviso
  "Pensando…" enquanto a IA responde.
- Funciona no computador, no tablet e no celular, com navegação completa pelo
  teclado e foco visível.
- O rodapé mostra só o crédito do Gradio (sem "Use via API" e sem
  "Settings").
