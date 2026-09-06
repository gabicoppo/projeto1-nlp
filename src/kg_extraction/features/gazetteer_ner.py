"""Reconhecimento de entidades baseado em dicionários (gazetteers).

Esta é a técnica clássica exigida pelo enunciado: em vez de um modelo
estatístico/neural de NER, usamos listas controladas de termos (que podem
vir de tesauros/ontologias como SNOMED CT, LOINC, MeSH) e casamos essas
listas contra o texto normalizado usando regex de fronteira de palavra.

Cada entrada do gazetteer tem um "termo canônico" (o rótulo normalizado
que vai para o grafo) e uma lista de sinônimos/variações textuais que
apontam para ele — essa é a "unificação de formas diferentes de escrever
um mesmo conceito" sugerida no enunciado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GazetteerEntry:
    entity_type: str
    canonical_label: str
    synonym: str  # forma de superfície já normalizada (lowercase)


@dataclass
class EntityMatch:
    entity_type: str
    canonical_label: str
    matched_text: str
    start: int
    end: int
    sentence_index: int


def load_gazetteer_file(path: Path, entity_type: str) -> list[GazetteerEntry]:
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip().lower() for p in line.split("|")]
            canonical = parts[0]
            synonyms = parts[1:] if len(parts) > 1 else [canonical]
            for syn in synonyms:
                entries.append(GazetteerEntry(entity_type, canonical, syn))
    return entries


def load_all_gazetteers(gazetteer_paths: dict) -> list[GazetteerEntry]:
    """gazetteer_paths: dict {entity_type: path}. Ver config.GAZETTEERS."""
    all_entries: list[GazetteerEntry] = []
    for entity_type, path in gazetteer_paths.items():
        all_entries.extend(load_gazetteer_file(path, entity_type))
    return all_entries


def build_matcher(entries: list[GazetteerEntry]):
    """Compila os sinônimos em padrões regex, ordenados do mais longo para o
    mais curto (em nº de palavras), para que "abdominal pain" seja casado
    antes de um sinônimo mais genérico que por acaso seja substring, evitando
    matches parciais indesejados.
    """
    compiled = []
    for entry in sorted(entries, key=lambda e: -len(e.synonym.split())):
        pattern = re.compile(r"\b" + re.escape(entry.synonym) + r"\b", re.IGNORECASE)
        compiled.append((pattern, entry))
    return compiled


def find_entities_in_sentence(sentence: str, matcher, sentence_index: int) -> list[EntityMatch]:
    """Aplica o matcher a uma sentença, evitando sobreposição de spans
    (o primeiro match — que, por causa do build_matcher, é o mais longo —
    "reserva" aquele trecho do texto).
    """
    occupied = [False] * len(sentence)
    matches: list[EntityMatch] = []
    for pattern, entry in matcher:
        for m in pattern.finditer(sentence):
            start, end = m.start(), m.end()
            if any(occupied[start:end]):
                continue
            for i in range(start, end):
                occupied[i] = True
            matches.append(
                EntityMatch(
                    entity_type=entry.entity_type,
                    canonical_label=entry.canonical_label,
                    matched_text=sentence[start:end],
                    start=start,
                    end=end,
                    sentence_index=sentence_index,
                )
            )
    matches.sort(key=lambda x: x.start)
    return matches
