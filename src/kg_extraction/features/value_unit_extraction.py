"""Extração de valores numéricos, unidades e faixas de referência via regex.

Técnica clássica: expressões regulares construídas a partir de uma lista
controlada de unidades (references/vocabularies/units.txt). Isto resolve o
segundo ponto pedido no enunciado: "valores associados a resultados de
exames e dosagem de medicamentos, bem como suas unidades de medida".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ValueMatch:
    value: str
    unit: str
    start: int
    end: int
    sentence_index: int


@dataclass
class ReferenceRangeMatch:
    low: str
    high: str
    unit: str | None
    start: int
    end: int
    sentence_index: int


def load_units(path: Path) -> list[str]:
    with open(path, encoding="utf-8") as f:
        units = [line.strip().lower() for line in f if line.strip() and not line.startswith("#")]
    # unidades mais longas primeiro, para o regex não casar "l" dentro de "mg/l"
    return sorted(units, key=len, reverse=True)


def build_value_unit_pattern(units: list[str]) -> re.Pattern:
    unit_alt = "|".join(re.escape(u) for u in units)
    # número (com milhar/decimal opcional) seguido, com espaço opcional, da unidade
    # Fronteira final: (?!\w), não \b. \b exige uma transição \w<->não-\w, então
    # nunca fecha depois de uma unidade que termina em caractere não-alfanumérico
    # (ex.: "%") quando o próximo caractere também é não-alfanumérico (espaço,
    # vírgula, fim de string) — que é o caso comum ("45%", "45% "). Isso fazia
    # "%" nunca casar de verdade apesar de estar na lista de unidades.
    # (?!\w) só exige que o próximo caractere não seja alfanumérico, o que
    # continua impedindo "mg" de casar dentro de "mgxyz" e também deixa "%"
    # funcionar.
    return re.compile(
        rf"(?P<value>\d[\d,\.]*)\s*(?P<unit>{unit_alt})(?!\w)",
        re.IGNORECASE,
    )


REFERENCE_RANGE_PATTERN = re.compile(
    r"reference\s+range[,:]?\s*(?P<low>\d[\d,\.]*)\s*[-–to]+\s*(?P<high>\d[\d,\.]*)\s*(?P<unit>[a-zA-Z/%]+)?",
    re.IGNORECASE,
)


def find_values(sentence: str, unit_pattern: re.Pattern, sentence_index: int) -> list[ValueMatch]:
    matches = []
    for m in unit_pattern.finditer(sentence):
        matches.append(
            ValueMatch(
                value=m.group("value").replace(",", ""),
                unit=m.group("unit").lower(),
                start=m.start(),
                end=m.end(),
                sentence_index=sentence_index,
            )
        )
    return matches


def find_reference_ranges(sentence: str, sentence_index: int) -> list[ReferenceRangeMatch]:
    matches = []
    for m in REFERENCE_RANGE_PATTERN.finditer(sentence):
        matches.append(
            ReferenceRangeMatch(
                low=m.group("low").replace(",", ""),
                high=m.group("high").replace(",", ""),
                unit=(m.group("unit") or "").strip() or None,
                start=m.start(),
                end=m.end(),
                sentence_index=sentence_index,
            )
        )
    return matches
