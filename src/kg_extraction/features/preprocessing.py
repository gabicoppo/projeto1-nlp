"""Pré-processamento clássico de texto.

Implementado sem depender de download de modelos/corpora externos
(evita falhas de rede em máquinas diferentes): tokenização de frases e
palavras por regex, normalização (lowercase) e uma lista de stop-words
mantida localmente. Se a equipe preferir, é trivial trocar por
nltk.sent_tokenize / nltk.word_tokenize ou spaCy (apenas o tokenizer,
sem nenhum modelo estatístico/neural de NER).
"""

from __future__ import annotations

import re

# Lista curta de stop-words em inglês (o dataset MultiCaRe está em inglês).
# Mantida localmente por simplicidade; pode ser trocada por nltk.corpus.stopwords.
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on", "at",
    "for", "with", "without", "by", "from", "as", "is", "was", "were", "are",
    "be", "been", "being", "he", "she", "his", "her", "it", "its", "this",
    "that", "these", "those", "there", "which", "who", "whom", "into", "than",
    "then", "also", "not", "no", "did", "does", "do", "had", "has", "have",
    "her", "him", "they", "their", "we", "our", "you", "your", "us",
}

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-]*|\d[\d,\.]*")


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


def tokenize(text: str) -> list[str]:
    """Tokenização de palavras/números por regex."""
    return _WORD_RE.findall(text)


def normalize(text: str) -> str:
    """Normalização simples: lowercase + espaços colapsados."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def remove_stopwords(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t.lower() not in STOPWORDS]


def lemmatize_naive(token: str) -> str:
    """Lematização por regras de sufixo (bem simples, mas 100% clássica/determinística).

    Não usa nenhum modelo estatístico. Cobre os casos mais comuns do domínio
    clínico (plurais regulares, -ing, -ed). Para um projeto mais robusto,
    a equipe pode trocar por nltk.stem.WordNetLemmatizer.
    """
    t = token.lower()
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("es") and not t.endswith("ses"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    if len(t) > 5 and t.endswith("ing"):
        return t[:-3]
    if len(t) > 4 and t.endswith("ed"):
        return t[:-2]
    return t
