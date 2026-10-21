# GitHub Actions

Todos os workflows **leem** o repositório sem segredos nem chaves de IA. A
única exceção de escrita é o job `publicar` do `docs.yml`, que publica este
site no GitHub Pages (permissões `pages: write` e `id-token: write`, só nele).

| Workflow | Job | Quando roda | O que faz |
|---|---|---|---|
| `ci-deploy.yml` | `testar` | Todo PR e todo push na `main` | Instala com pip, `pip check`, procura chaves vazadas, Ruff (lint e formatação), valida o `config.yml` e roda **todos os testes** com cobertura mínima de 80%. |
| `api-ibge.yml` | `api-ibge` | PRs que mexem no pipeline ou no dashboard | Roda o pipeline com a **API real** do IBGE, abre o dashboard com os dados reais e guarda fotos da tela. |
| `ambiente.yml` | `poetry` | PRs que mexem em dependências | Instala o Poetry com o pipx, confere o `poetry.lock`, instala tudo do zero, Ruff e todos os testes. |
| `ambiente.yml` | `render` | PRs que mexem em dependências | Instala **como o Render** (só `requirements.txt`) e liga o chatbot até ele responder. |
| `docs.yml` | `docs` | PRs e pushes na `main` que mexem na documentação | Instala o MkDocs e roda `mkdocs build --strict`; guarda o site gerado como artefato. |
| `docs.yml` | `publicar` | Só na `main`, depois do `docs` | Publica no **GitHub Pages** e confere se o endereço público abre. |

## Relação com o Render

O Render publica a `main` **só depois** que as verificações passam (opção
*After CI Checks Pass*). Por isso:

- o job `testar` roda em todo push na `main`;
- `api-ibge.yml` e `ambiente.yml` rodam **só em Pull Requests** (e quando
  alguém pede, em *Run workflow*);
- o `docs.yml` também roda na `main`, mas **só quando a documentação muda**.
  Nesses merges, o Render espera ele terminar; se falhar, o chatbot segue no
  ar com a versão anterior (o mesmo código). Veja [Publicação](../publicar.md).

## Onde ver os resultados

No GitHub: aba **Actions**, ou a lista de verificações no fim de cada Pull
Request. Artefatos (fotos do dashboard, site da documentação) ficam em
*Actions → execução → Summary → Artifacts* por 7 dias.
