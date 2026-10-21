# Professor de Dados

Projeto acadêmico de **Engenharia de Dados e Inteligência Artificial** com dois
produtos que vivem no mesmo repositório, mas funcionam de forma independente:

<div class="grid cards" markdown>

-   **Produto A — Professor de Dados**

    ---

    Um chat que ensina Engenharia de Dados, Python, SQL e IA com palavras
    simples. Feito com **Gradio**, usa modelos de IA **gratuitos** e está
    publicado no **Render**.

    [:octicons-arrow-right-24: Como o chatbot funciona](professor-de-dados.md)

-   **Produto B — Brasil em Dados (Censo 2022)**

    ---

    Um pipeline que busca dados oficiais do **IBGE** (requests → Pydantic →
    Pandas) e um dashboard interativo em **Streamlit + Plotly**.

    [:octicons-arrow-right-24: Como os dados são tratados](dados/api.md)

</div>

## Objetivos

1. **Ensinar** conceitos de dados e IA por meio de um chatbot que se adapta ao
   nível de quem pergunta (iniciante, intermediário ou avançado).
2. **Praticar um pipeline de dados completo** com uma API pública real:
   extrair, validar, transformar, calcular indicadores e visualizar.
3. **Trabalhar como em um projeto profissional**: ambiente reproduzível
   (pyenv, pipx, Poetry), testes automatizados com cobertura, padronização de
   código (Ruff), integração contínua (GitHub Actions) e publicação segura.
4. **Proteger custos e credenciais**: só modelos gratuitos, limites de uso no
   servidor e nenhuma chave guardada no código.

## Por onde começar

| Quero… | Página |
|---|---|
| Entender as peças e como se conectam | [Arquitetura e pastas](arquitetura.md) |
| Instalar tudo no Windows | [Windows 11 passo a passo](ambiente/windows.md) |
| Rodar o chatbot, o pipeline ou o dashboard | [Como executar localmente](executar.md) |
| Saber de onde vêm os dados do IBGE | [Funcionamento da API](dados/api.md) |
| Rodar os testes e ver a cobertura | [Testes](qualidade/testes.md) e [Cobertura](qualidade/cobertura.md) |
| Saber como as chaves e os custos são protegidos | [Segurança](seguranca.md) |
| Publicar ou atualizar o que está no ar | [Publicação](publicar.md) |
| Ver o relatório final, o checklist e o roteiro de apresentação | [Entrega final](entrega-final/index.md) |

!!! info "Sobre os dados"
    Os números do dashboard vêm da **tabela 4714 do Censo Demográfico 2022**
    (IBGE). É um único ano: o projeto **não** mostra tendências nem evolução no
    tempo.
