"""Regras de extração de relações entre entidades.

Técnica clássica de "modelos de regras" citada no enunciado: em vez de um
parser de dependências ou um modelo treinado, usamos:
  1. Co-ocorrência na mesma sentença (ex.: Sintoma na mesma frase do paciente
     -> PRESENTS_WITH);
  2. Expressões-gatilho por regex (ex.: "history of" antes de um diagnóstico
     -> HAS_HISTORY em vez de DIAGNOSED_WITH);
  3. Proximidade sequencial entre sentenças (ex.: o Exam mais próximo antes
     de um valor numérico recebe o HAS_RESULT; o Diagnosis mencionado mais
     recentemente antes de um Treatment recebe o TREATED_BY).

As regras são propositalmente simples e comentadas para que a equipe
entenda o impacto de cada uma no grafo final e possa ajustá-las.
"""

import re

HISTORY_TRIGGER = re.compile(r"\bhistory of\b", re.IGNORECASE)
EXCLUDE_TRIGGER = re.compile(r"\bexclud(ed|ing|es)?\b", re.IGNORECASE)
CONFIRM_TRIGGER = re.compile(r"\bconfirm(ed|ing|s)?\b", re.IGNORECASE)


def classify_diagnosis_relation(sentence: str, entity_start: int) -> str:
    """Decide se um Diagnosis mencionado é histórico prévio (HAS_HISTORY) ou
    o diagnóstico do caso atual (DIAGNOSED_WITH), olhando o texto que
    precede a entidade na mesma sentença.
    """
    preceding_text = sentence[:entity_start]
    if HISTORY_TRIGGER.search(preceding_text):
        return "HAS_HISTORY"
    return "DIAGNOSED_WITH"


def classify_exam_finding_relation(sentence: str) -> str:
    """Para achados de exame (ex.: EUS confirmou / excluiu algo), decide a
    relação a partir de verbos-gatilho na sentença.
    """
    if EXCLUDE_TRIGGER.search(sentence):
        return "EXCLUDES"
    if CONFIRM_TRIGGER.search(sentence):
        return "CONFIRMS"
    return "REVEALS"
