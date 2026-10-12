# Auditoria pré-publicação (passo P15) — 11/10/2026

Nada foi publicado, nenhuma chave real foi usada e o PR #1 não foi incorporado.

## Como o app foi testado "como no Render"
- Clone limpo da branch, Python **3.11** novo e **só** o `requirements.txt`
  (como o Render instala): 32 s de instalação, sem conflitos, sem bibliotecas de teste.
- `python app.py` com `PORT=10000`: o app abriu em **6,5 s**, escutando em
  `0.0.0.0:10000`, usando cerca de **190–196 MB** de memória.
- Chat de verdade pela API do app, com um **provedor de IA falso** rodando no
  próprio computador (formato da OpenAI, chave falsa, custo zero).

## Critérios de aceite (CA)

Legenda: ✅ comprovado · 🧪 comprovado em simulação local · ⏳ só dá para conferir com o app no ar (P16) · ➖ não se aplica enquanto a identificação por IP estiver desligada

| CA | Critério | Situação | Como foi conferido |
|---|---|---|---|
| CA1 | Chat responde pelo link público | 🧪 / ⏳ | Página abre na `PORT` em 0.0.0.0; o link público só existe depois de publicar. |
| CA2 | Personalização funciona | ✅ / ⏳ | Testes de tela (T6) e fotos do P9; no link, conferir no P16. |
| CA3 | Fallback funciona | ✅ 🧪 | Testes T3/T5; na simulação, provedores sem chave foram pulados e o seguinte respondeu. |
| CA4 | Falha total é amigável | 🧪 | Provedor falso com erro 503 e 401: o visitante viu a mensagem amigável. |
| CA5 | Configuração errada é bloqueada | ✅ | O GitHub Actions roda `validar_config.py` e os testes; o comando termina com erro em configuração inválida. |
| CA6 | Código com erro é bloqueado | ✅ / ⏳ | O job "testar" falha em qualquer erro; o Render só respeita isso com *After CI Checks Pass* ligado. |
| CA7 | Pull Request não publica | ✅ | O workflow não publica nada; o Render só publica a `main`. |
| CA8 | Testes passam localmente | ✅ | 395 testes no Python 3.11. |
| CA9 | Limite por minuto **por pessoa** | ➖ | Identificação por IP desligada; o limite global (CA25) cobre. |
| CA10 | Limite não burlado recarregando | ➖ | Mesmo motivo do CA9. |
| CA11 | Bloqueio não gasta crédito | 🧪 | Logs: "Limite atingido … nenhuma IA chamada". |
| CA12 | Limite de gastos definido | ⏳ | Depende de você (painel de cada provedor). |
| CA13 | Chave real é detectada | ✅ | Teste T8 e simulação do P2. |
| CA14 | Sem falso alarme na documentação | ✅ | Verificador de segredos limpo em todos os arquivos **e em todo o histórico do Git**. |
| CA15 | Versões alinhadas | ✅ | Teste T7. |
| CA16 | Render publica só depois dos testes | ⏳ | Depende de ligar *After CI Checks Pass* no painel do Render. |
| CA17 | Chaves fora do repositório | ✅ / ⏳ | Repositório e histórico sem chaves; `render.yaml` sem valores. No Render, conferir no P16. |
| CA18 | Cores aparecem | ✅ / ⏳ | Fotos do P9; no link, conferir no P16. |
| CA19 | Cor ilegível bloqueada | ✅ | Testes T1/T2. |
| CA20 | Texto dos botões legível | ✅ | Testes T2/T6. |
| CA21 | IA lembra da conversa | 🧪 / ⏳ | A 2ª pergunta foi enviada com o histórico; a qualidade da resposta só com IA de verdade. |
| CA22 | Instruções seguidas | 🧪 / ⏳ | As instruções foram enviadas no pedido; responder em português depende da IA de verdade. |
| CA23 | Pergunta longa recusada | 🧪 | Mensagem amigável, nenhuma IA chamada. |
| CA24 | Identificação por IP no Render | ⏳ | Continua **desligada** (`identificar_por_ip: false`). Testar no P16 ou manter desligada. |
| CA25 | Proteção global sem identificação | 🧪 | 20 perguntas liberadas no minuto, a 21ª bloqueada com aviso. |

## Segurança das chaves e variáveis
- Nenhuma chave nos arquivos nem nos **21 commits** do histórico.
- `.env` ignorado pelo Git; o único arquivo de ambiente guardado é o `.env.example`.
- `render.yaml`: chaves com `sync: false`, sem valor.
- GitHub Actions: sem segredos, chaves de IA vazias, só leitura.
- O app em execução **recusou** baixar `.env`, `config.yml`, `app.py` e `/etc/passwd` (HTTP 403/404).
- Logs: mostram quais provedores têm chave, mas nunca a chave, a pergunta ou a resposta.
- O app não fez nenhuma conexão externa além do provedor de IA. (As conexões
  ao huggingface.co vistas na auditoria vieram do **cliente de teste**, não do app.)

## Limites globais e reinicializações
- Valem sempre: **20 perguntas por minuto** e **500 por dia**, somando todo mundo.
- **Os contadores ficam na memória e zeram** quando o serviço reinicia, é
  republicado ou **dorme** (Render grátis: após 15 minutos sem acesso). Comprovado
  na simulação: logo depois de reiniciar, a pergunta foi aceita de novo.
- **Pior caso teórico:** alguém faz 500 perguntas em 25 minutos, espera o
  serviço dormir (15 min) e repete. Isso permitiria bem mais de 500 perguntas por
  dia (na conta mais pessimista, perto de 17 mil).
- **Por isso:** o limite de gastos em cada provedor é obrigatório, e a forma mais
  segura de começar é publicar **só com a chave do OpenRouter usando o modelo
  gratuito** (custo zero mesmo no pior caso).
