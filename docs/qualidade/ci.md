# GitHub Actions

Todos os workflows têm **só permissão de leitura**, não usam segredos nem
chaves de IA e não publicam nada.

| Workflow | Job | Quando roda | O que faz |
|---|---|---|---|
| `ci-deploy.yml` | `testar` | Todo PR e todo push na `main` | Instala com pip, `pip check`, procura chaves vazadas, Ruff (lint e formatação), valida o `config.yml` e roda **todos os testes** com cobertura mínima de 80%. |
| `api-ibge.yml` | `api-ibge` | PRs que mexem no pipeline ou no dashboard | Roda o pipeline com a **API real** do IBGE, abre o dashboard com os dados reais e guarda fotos da tela. |
| `ambiente.yml` | `poetry` | PRs que mexem em dependências | Instala o Poetry com o pipx, confere o `poetry.lock`, instala tudo do zero, Ruff e todos os testes. |
| `ambiente.yml` | `render` | PRs que mexem em dependências | Instala **como o Render** (só `requirements.txt`) e liga o chatbot até ele responder. |
| `docs.yml` | `docs` | PRs que mexem na documentação | Instala o MkDocs e roda `mkdocs build --strict`; guarda o site gerado como artefato. |

## Relação com o Render

O Render publica a `main` **só depois** que as verificações passam (opção
*After CI Checks Pass*). Por isso:

- o job `testar` roda em todo push na `main`;
- os outros workflows rodam **só em Pull Requests** (e quando alguém pede, em
  *Run workflow*). Eles nunca atrasam nem bloqueiam a publicação do chatbot e
  não publicam nada sozinhos.

## Onde ver os resultados

No GitHub: aba **Actions**, ou a lista de verificações no fim de cada Pull
Request. Artefatos (fotos do dashboard, site da documentação) ficam em
*Actions → execução → Summary → Artifacts* por 7 dias.
