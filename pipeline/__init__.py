"""Pipeline de Engenharia de Dados do projeto (Produto B).

EXTRAÇÃO (requests) → VALIDAÇÃO (Pydantic) → TRANSFORMAÇÃO (Pandas) → INDICADORES

Fonte: API de dados agregados do IBGE (v3), tabela 4714 do Censo Demográfico
2022 (população residente, área territorial e densidade demográfica por
município). Veja docs em fonte.py.

Este pacote não depende do chatbot (pasta assistente/) e o chatbot não
depende dele: se um falhar, o outro continua funcionando.
"""
