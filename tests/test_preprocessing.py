import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kg_extraction.features.preprocessing import (
    lemmatize_naive,
    remove_stopwords,
    split_sentences,
    tokenize,
)


def test_split_sentences_basic():
    text = "The patient had fever. She was treated with antibiotics."
    sentences = split_sentences(text)
    assert len(sentences) == 2
    assert sentences[0].startswith("The patient")
    assert sentences[1].startswith("She was treated")


def test_tokenize_keeps_numbers_and_words():
    tokens = tokenize("CRP was 96 mg/L today")
    assert "96" in tokens
    assert "CRP" in tokens
    assert "mg" in tokens  # unidades com barra são separadas pelo tokenizer léxico


def test_remove_stopwords():
    tokens = ["the", "patient", "was", "treated", "with", "antibiotics"]
    filtered = remove_stopwords(tokens)
    assert "the" not in filtered
    assert "patient" in filtered
    assert "antibiotics" in filtered


def test_lemmatize_naive_plurals_and_verbs():
    assert lemmatize_naive("symptoms") == "symptom"
    assert lemmatize_naive("biopsies") == "biopsy"
    assert lemmatize_naive("presented") == "present"
