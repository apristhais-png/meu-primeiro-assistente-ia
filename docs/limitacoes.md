# Limitações conhecidas e próximos passos

## Limitações

### Dados

- **Um único ano**: a tabela 4714 traz o Censo 2022. Não há série histórica,
  então o projeto **não** mostra tendências nem evolução no tempo.
- **Três medidas por município** (população, área e densidade). Renda, idade,
  sexo e outros recortes estão em outras tabelas do IBGE.
- A densidade publicada pelo IBGE é arredondada; o pipeline confere se ela
  bate com população ÷ área (diferença de até 1%).
- O ambiente de desenvolvimento não acessa o site do IBGE: a validação com a
  **API real** acontece no GitHub Actions (`api-ibge.yml`), só em Pull
  Requests do pipeline ou do dashboard.

### Chatbot

- Depende de **modelos gratuitos** do OpenRouter, que podem ficar lentos,
  sair do ar ou mudar de nome. A lista é conferida no catálogo antes de cada
  uso, mas pode precisar de atualização (`python scripts/conferir_modelos.py`).
- No plano gratuito do Render, o serviço **dorme** após 15 minutos sem acesso.
- Não há memória entre conversas: fechar a página apaga o histórico.
- Os limites por pessoa (por IP) estão desligados por padrão; valem os limites
  globais.

### Ambiente e publicação

- Os comandos de **Windows** seguem a documentação oficial das ferramentas,
  mas a instalação completa foi conferida em Linux (computador de
  desenvolvimento e GitHub Actions).
- As versões ficam em dois formatos (`requirements*.txt` e Poetry). Mudar uma
  versão exige alterar os dois e rodar `poetry lock`; um teste avisa se
  alguém esquecer.
- A documentação usa o **MkDocs 1.6** com o tema Material, fixados nessa
  versão. O MkDocs 2.0 anunciou mudanças incompatíveis (plugins e temas), então
  uma atualização futura precisará ser avaliada antes.
- O **dashboard** e esta **documentação** ainda não estão publicados na
  internet (dependem de autorização).
- Qualquer merge na `main` faz o Render republicar o chatbot, mesmo quando só
  a documentação mudou.

## Próximos passos possíveis

1. Decidir se e onde publicar o **dashboard** (veja [Publicação](publicar.md)).
2. Autorizar a publicação desta documentação no **GitHub Pages**.
3. Acrescentar outra tabela do IBGE (por exemplo, uma série histórica de
   estimativas de população) para permitir comparações no tempo.
4. Ligar os limites por pessoa no chatbot depois do teste com o Render
   (critério CA24 do guia).
5. Fazer a **validação final** do projeto (Entrega 6): testes completos,
   cobertura, dependências, segurança, compatibilidade com o Render e o
   checklist acadêmico.
