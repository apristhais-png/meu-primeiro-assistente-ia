"""Tutor adaptativo: nível do aluno e modo de estudo (Módulo 2, Aula 2).

O nível e o modo escolhidos na tela viram parte das INSTRUÇÕES enviadas à IA,
junto com as instruções do config.yml. Não são só enfeite da tela.

Segurança: a tela (ou quem usa a API) só manda a CHAVE do nível e do modo
("iniciante", "exercicio"...). O texto das instruções vem daqui, nunca de
quem pergunta. Qualquer valor desconhecido vira o padrão, então ninguém
consegue colocar um texto próprio nas instruções da IA por esse caminho.

Continuidade: não há memória guardada. O exercício proposto e as tentativas
do aluno ficam no histórico da conversa (que a tela já envia a cada pergunta),
e as instruções pedem para a IA usá-lo.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Opcao:
    chave: str
    rotulo: str  # o que aparece na tela
    instrucoes: str  # o que vai para a IA


NIVEIS = {
    "iniciante": Opcao(
        "iniciante",
        "Iniciante",
        "NÍVEL DO ALUNO: iniciante.\n"
        "- Use frases curtas e palavras do dia a dia. Explique todo termo técnico na primeira vez.\n"
        "- Use analogias simples (cozinha, mercado, planilhas) e exemplos pequenos.\n"
        "- Mostre código curto, comentado linha a linha, e um passo de cada vez.\n"
        "- Não pressuponha conhecimento prévio de programação.",
    ),
    "intermediario": Opcao(
        "intermediario",
        "Intermediário",
        "NÍVEL DO ALUNO: intermediário.\n"
        "- O aluno já conhece o básico de Python e SQL: não explique o elementar.\n"
        "- Use exemplos realistas (tabelas com algumas colunas, funções com parâmetros).\n"
        "- Mostre boas práticas e erros comuns, com código de tamanho médio.",
    ),
    "avancado": Opcao(
        "avancado",
        "Avançado",
        "NÍVEL DO ALUNO: avançado.\n"
        "- Seja direto e técnico; use a terminologia correta sem simplificar demais.\n"
        "- Discuta desempenho, escalabilidade, trade-offs e casos de borda.\n"
        "- Use exemplos próximos de produção (pipelines, particionamento, otimização de consultas).",
    ),
}

MODOS = {
    "explicacao": Opcao(
        "explicacao",
        "Explicação",
        "MODO DE ESTUDO: explicação.\n"
        "- Explique o assunto perguntado de forma organizada: ideia principal, exemplo e um resumo final.\n"
        "- No fim, sugira um próximo passo de estudo ou uma pergunta para o aluno pensar.",
    ),
    "exercicio": Opcao(
        "exercicio",
        "Exercício prático",
        "MODO DE ESTUDO: exercício prático (Python, SQL ou Engenharia de Dados).\n"
        "- Se ainda não há um exercício em andamento na conversa, proponha UM exercício no assunto pedido "
        "(ou escolha entre Python, SQL e Engenharia de Dados), adequado ao nível do aluno, com:\n"
        "  1. Enunciado claro, com os dados de entrada (ex.: uma pequena tabela ou lista);\n"
        "  2. Uma dica curta;\n"
        "  3. Critérios de verificação: como o aluno pode saber se acertou (resultado esperado ou testes).\n"
        "- NÃO entregue a solução ao propor o exercício.\n"
        "- Se a última mensagem do aluno for uma tentativa de resolver o exercício que está na conversa, "
        "corrija: diga o que está certo, aponte cada erro e explique por quê, e oriente como melhorar "
        "com perguntas ou dicas. Só mostre a solução completa se o aluno pedir explicitamente ou depois "
        "de duas tentativas sem sucesso.\n"
        "- Use o histórico da conversa: não repita exercícios já propostos nem perguntas já respondidas.",
    ),
    "revisao": Opcao(
        "revisao",
        "Revisão",
        "MODO DE ESTUDO: revisão.\n"
        "- Faça um resumo curto dos pontos principais do assunto (ou do que já foi estudado nesta conversa).\n"
        "- Depois, faça de 3 a 5 perguntas rápidas para o aluno testar o que lembra, sem dar as respostas.\n"
        "- Quando o aluno responder, corrija cada item e reforce o que ficou fraco.\n"
        "- Use o histórico da conversa e não repita perguntas já feitas.",
    ),
}

NIVEL_PADRAO = "iniciante"
MODO_PADRAO = "explicacao"


def escolher_nivel(chave) -> Opcao:
    """Nível conhecido ou o padrão (nunca usa texto vindo de fora)."""
    return NIVEIS.get(chave if isinstance(chave, str) else "", NIVEIS[NIVEL_PADRAO])


def escolher_modo(chave) -> Opcao:
    """Modo conhecido ou o padrão (nunca usa texto vindo de fora)."""
    return MODOS.get(chave if isinstance(chave, str) else "", MODOS[MODO_PADRAO])


def montar_instrucoes(instrucoes_base: str, nivel=None, modo=None) -> str:
    """Instruções do config.yml + nível + modo, nessa ordem."""
    base = instrucoes_base.strip()
    return f"{base}\n\n{escolher_nivel(nivel).instrucoes}\n\n{escolher_modo(modo).instrucoes}"


def opcoes_para_tela(opcoes: dict[str, Opcao]) -> list[tuple[str, str]]:
    """Pares (rótulo, chave) para os seletores do Gradio."""
    return [(opcao.rotulo, opcao.chave) for opcao in opcoes.values()]
