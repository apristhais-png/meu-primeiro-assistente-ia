# Auditoria de segurança

Executada em 21/10/2026 sobre a `main` (`7c76658`). Logs:
[`logs/seguranca.txt`](logs/seguranca.txt),
[`logs/segredos.txt`](logs/segredos.txt) e
[`logs/pip-audit.txt`](logs/pip-audit.txt).

## 1. Chaves e credenciais

| Verificação | Resultado |
|---|---|
| `scripts/verificar_segredos.py` nos arquivos atuais | **0 chaves** em 92 arquivos |
| Mesmos padrões aplicados a **todo o histórico** (`git log --all -p`) | **0 chaves** em 52 commits |
| Algum commit já incluiu o `.env`? | **Não** (0 commits) |
| O `.gitignore` protege o `.env`? | Sim (`.gitignore:6`) |
| `.env.example` | Só `SUA_CHAVE_AQUI` |
| `render.yaml` | Chaves com `sync: false` (valor só no painel do Render) |

## 2. GitHub Actions

| Workflow | Permissão | Usa segredos? | Checkout sem credenciais |
|---|---|---|---|
| `ci-deploy.yml` | `contents: read` | Não | Sim |
| `api-ibge.yml` | `contents: read` | Não | Sim |
| `ambiente.yml` | `contents: read` | Não | Sim |
| `docs.yml` | `contents: read` | Não | Sim |

Nenhum workflow publica nada. Os que rodam testes ou ligam o chatbot deixam as
chaves de IA vazias.

## 3. Código do chatbot

| Verificação | Resultado |
|---|---|
| `eval`, `exec`, `subprocess`, `os.system` no chatbot | Nenhum |
| Envio de arquivos (upload, multimodal, `gr.File`) | Nenhum: o chat só troca texto |
| Detalhes técnicos de erro na tela | Desligados (`show_error=False`) |
| Instruções da IA vindas da tela | Só a **opção** de nível/modo; o texto vem do código |
| Conteúdo das perguntas nos logs | Não; só id, nível, modo, tempo e resultado |

Na execução real ([`logs/chatbot-execucao.txt`](logs/chatbot-execucao.txt)),
sem chave, a pergunta passou pelo limite de uso, nenhum provedor foi chamado e
a pessoa recebeu a mensagem amigável.

## 4. Custos

| Proteção | Situação |
|---|---|
| Só modelos `:free` de conversa, numa lista explícita | Mantido (`config.yml`) |
| Conferência no catálogo (preço zero) e `max_price = 0` | Mantido (testes) |
| Erro de cobrança/chave não aciona o próximo provedor | Mantido (testes) |
| Limites: 20/min, 500/dia, 2.000 caracteres | Mantido (`validar_config.py`) |
| Nenhum serviço pago contratado; GitHub Pages não ativado | Confirmado |

## 5. Testes sem acesso à internet

Durante a validação, um "espião" de conexões rodou junto com os 690 testes.

| Achado | O que foi feito |
|---|---|
| 1 tentativa de conexão ao `openrouter.ai` em `test_confiabilidade.py` (catálogo de modelos) | O teste já bloqueava conexões externas, mas um **proxy local** (`127.0.0.1`, como o deste ambiente) passava pelo bloqueio. **Corrigido**: o teste agora remove as variáveis de proxy. Depois da correção: 0 conexões. No GitHub (sem proxy) o bloqueio já funcionava. Nenhuma pergunta foi enviada a uma IA: era só a leitura do catálogo público, e ela foi recusada. |
| Tentativas de conexão ao `huggingface.co` nos testes da tela Gradio (`test_interface.py`, `test_tutor.py`) | Feitas pela própria biblioteca Gradio ao abrir o servidor de teste; não envolvem IA, chave nem custo. Os testes passam com a internet bloqueada (como neste ambiente), então **não dependem** dela. |

## 6. Vulnerabilidades conhecidas nas dependências (`pip-audit`)

```text
Found 8 known vulnerabilities in 1 package
Name   Version ID              Fix Versions
pillow 12.3.0  CVE-2026-112895 13.0.0
pillow 12.3.0  CVE-2026-112400 13.0.0
... (8 no total, todas corrigidas no Pillow 13.0.0)
```

**O que é:** o Pillow é uma biblioteca de imagens instalada **indiretamente**
pelo Gradio (chatbot) e pelo Streamlit (dashboard). As 8 falhas acontecem
quando um programa **abre um arquivo de imagem malicioso** (PDF, PPM, TIFF,
entre outros).

**Por que não foi atualizado:** as versões mais recentes do Gradio (6.30.0) e
do Streamlit (1.66.0) exigem `pillow<13`. Forçar o Pillow 13 quebraria a
instalação do chatbot no Render.

**Risco neste projeto: baixo.** O chatbot só recebe **texto** (não há envio de
arquivos) e o dashboard só lê o JSON do IBGE. O único arquivo de imagem aberto
é o logo do próprio projeto.

**Ação recomendada:** quando o Gradio e o Streamlit aceitarem o Pillow 13,
atualizar as três bibliotecas juntas, num PR próprio, e rodar de novo:

```bash
pip install pip-audit
pip-audit -r requirements.txt -r requirements-dados.txt -r requirements-dev.txt -r requirements-docs.txt
```

## Conclusão

Nenhuma chave exposta (nem no histórico), nenhum segredo nos workflows,
nenhuma entrada de código ou arquivo pela tela e proteções de custo mantidas.
Fica registrado um risco baixo e conhecido (Pillow), sem correção compatível
disponível hoje.
