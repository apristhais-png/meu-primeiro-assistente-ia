# Segurança e variáveis de ambiente

## Onde ficam as chaves

| Chave | No seu computador | No Render |
|---|---|---|
| `OPENROUTER_API_KEY` | arquivo `.env` | aba *Environment* do serviço |
| `ANTHROPIC_API_KEY` | arquivo `.env` | aba *Environment* do serviço |
| `OPENAI_API_KEY` | arquivo `.env` | aba *Environment* do serviço |

- Não é preciso ter as três: o app usa as que existirem, na ordem do
  `config.yml`.
- O pipeline e o dashboard **não usam chave nenhuma** (a API do IBGE é
  pública).

```bash
cp .env.example .env      # Windows: Copy-Item .env.example .env
```

O `.env.example` só tem valores falsos (`SUA_CHAVE_AQUI`). O `.env` real está
no `.gitignore` e **nunca** vai para o GitHub. No Render, o `render.yaml`
lista as chaves com `sync: false`: o valor é digitado no painel e não fica no
repositório.

## Regras do projeto

- Nunca versionar o `.env` real.
- Nunca colocar chaves no código, no `config.yml`, nos testes ou na
  documentação.
- Nunca mostrar segredos nos logs: as mensagens de erro dos provedores não são
  repassadas, porque algumas trazem parte da chave.
- Não usar serviços pagos sem autorização e não trocar o modelo gratuito por
  um pago.
- Não desativar as proteções existentes.
- Não executar código enviado pela pessoa no chatbot e não expor arquivos do
  servidor pela tela.

## Verificador de chaves vazadas

```bash
python scripts/verificar_segredos.py
```

Procura, em **todos os arquivos guardados no Git** (inclusive `.md` e `.yml`),
o formato completo de chaves reais da OpenRouter, Anthropic, OpenAI, Hugging
Face e GitHub. Valores de exemplo (`SUA_CHAVE`, `EXEMPLO`, `XXXX`) são
ignorados. Se encontrar algo, mostra o arquivo e a linha **com a chave
escondida** e termina com erro, o que deixa a CI vermelha.

## Proteção de custos

| Proteção | Onde |
|---|---|
| Só modelos `:free` de conversa, numa lista explícita | `config.yml` |
| Conferência no catálogo do OpenRouter (preço zero) e `max_price = 0` | `assistente/modelos_gratuitos.py` |
| Erro de cobrança ou de chave **não** dispara o próximo provedor | `assistente/provedores.py` |
| Limites por minuto, por dia e tamanho da pergunta, no servidor | `assistente/limites.py` |
| Tamanho máximo da resposta (`max_tokens`) | `config.yml` |
| Teto de chamadas simultâneas à IA | `assistente/provedores.py` |
| Testes sem nenhuma chamada real | `tests/` |

Também é recomendado definir um **limite de gastos** no painel de cada
provedor (veja o
[guia de publicação](https://github.com/apristhais-png/meu-primeiro-assistente-ia/blob/main/GUIA-publicacao.md)).

## Privacidade

- O conteúdo das perguntas e respostas não vai para os logs.
- Não há banco de dados nem cadastro; a conversa some quando a página fecha.
- A identificação por IP (para limites por pessoa) vem desligada e, quando
  ligada, usa só o último item do `X-Forwarded-For`, que é o escrito pelo
  Render.

## GitHub Actions

Todos os workflows têm permissão **só de leitura**, não recebem nenhum
segredo e fazem o checkout sem guardar credenciais. Os jobs que rodam os
testes ou ligam o chatbot ainda deixam as chaves de IA explicitamente
**vazias**.
