import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kg_extraction.features.preprocessing import split_sentences


def test_split_sentences_basic():
    text = "The patient had fever. She was treated with antibiotics."
    sentences = split_sentences(text)
    assert len(sentences) == 2
    assert sentences[0].startswith("The patient")
    assert sentences[1].startswith("She was treated")
