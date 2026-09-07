"""Segmentação de sentenças (pré-processamento clássico, por regex).

Implementado sem depender de download de modelos/corpora externos (evita
falhas de rede em máquinas diferentes). Se a equipe preferir, é trivial
trocar por nltk.sent_tokenize.

Histórico: este módulo também teve tokenização de palavras, normalização
(lowercase) e um stemmer ingênuo (`tokenize`/`normalize`/`lemmatize_naive`),
removidos porque nunca chegaram a ser usados pelo pipeline de extração —
o matcher de gazetteer e o regex de valor/unidade operam direto sobre a
frase bruta, sem passar por eles. Investigamos plugá-los na frente do
matcher e não compensava (ver discussão no PR/histórico da equipe):
quebraria sinônimos multi-palavra com stopword interna (ex.: "acute on
chronic liver failure") e a adjacência número+unidade que o regex de
valor/unidade depende. `STOPWORDS` sobrevive porque scripts/build_units_
from_ncit.py a reaproveita pra filtrar abreviação-código coincidindo com
palavra comum do inglês.
"""

from __future__ import annotations

import re

# Lista curta de stop-words em inglês (o dataset MultiCaRe está em inglês).
# Mantida localmente por simplicidade; pode ser trocada por nltk.corpus.stopwords.
# Usada por scripts/build_units_from_ncit.py, não pelo pipeline de extração.
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on", "at",
    "for", "with", "without", "by", "from", "as", "is", "was", "were", "are",
    "be", "been", "being", "he", "she", "his", "her", "it", "its", "this",
    "that", "these", "those", "there", "which", "who", "whom", "into", "than",
    "then", "also", "not", "no", "did", "does", "do", "had", "has", "have",
    "her", "him", "they", "their", "we", "our", "you", "your", "us",
}

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def split_sentences(text: str) -> list[str]:
    """Segmentação de sentenças por regex (pontuação + letra maiúscula seguinte).

    Não é perfeita (ex.: abreviações como "Fig." podem quebrar a frase),
    mas é transparente, determinística e suficiente para casos clínicos
    curtos como os do MultiCaRe.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sentences = _SENTENCE_SPLIT_RE.split(text)
    return [s.strip() for s in sentences if s.strip()]
