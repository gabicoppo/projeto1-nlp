"""Expande references/vocabularies/ontology_links.csv com códigos MeSH reais
para os termos canônicos que já existem nos gazetteers (symptoms/exams/
diagnoses/treatments/anatomy.txt) — em vez de deixar a tabela só com as ~14
linhas digitadas à mão que serviam de exemplo (ver aviso em
docs/data_source.md: "os códigos nela foram digitados manualmente como
ilustração da técnica [...]. Antes da entrega final, a equipe deve expandir
a cobertura de termos").

Por que isso é "de graça": os scripts build_gazetteer_from_mesh.py e
build_units_from_ncit.py já RESOLVEM o código de cada termo durante o fetch
(o IRI do descritor MeSH termina exatamente no código, ex.:
http://id.nlm.nih.gov/mesh/D010195 -> código D010195) — só nunca gravamos
isso, jogamos fora depois de pegar só o rótulo e os sinônimos. Este script
reconsulta apenas a parte BARATA (lista de descritores da categoria, sem os
sinônimos/entry terms — a mesma fase 1 de build_gazetteer_from_mesh.py) para
recuperar esse código, sem precisar refazer o fetch caro de sinônimos.

Uso:
    python scripts/build_ontology_links_from_mesh.py

Não mexe nas linhas já existentes em ontology_links.csv (SNOMED_CT/LOINC/
ICD10 digitados à mão) — só ACRESCENTA uma linha nova (ontology=MeSH) para
todo (entity_type, canonical_label) que ainda não tem nenhum link e que
corresponde a um descritor de alguma das categorias MeSH já usadas pelos
gazetteers do projeto.
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_gazetteer_from_mesh import _fetch_descriptors  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parents[1]
ONTOLOGY_LINKS_CSV = ROOT_DIR / "references" / "vocabularies" / "ontology_links.csv"

# Mesmas categorias MeSH usadas pra gerar cada gazetteer (ver histórico dos
# comandos rodados) — reconsultamos só a lista de descritores (fase 1, barata).
ENTITY_CATEGORIES = {
    "Symptom": ["C23"],
    "Exam": ["E01"],
    "Diagnosis": ["C01", "C04", "C05", "C06", "C07", "C10", "C11", "C15", "C17", "C18", "C19", "C20"],
    "Treatment": ["E02", "E04"],
    "AnatomicalSite": ["A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10", "A12", "A14", "A15", "A17"],
}


def load_existing_links() -> tuple[list[dict], set[tuple[str, str]]]:
    rows = []
    keys = set()
    if ONTOLOGY_LINKS_CSV.exists():
        with open(ONTOLOGY_LINKS_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
                keys.add((row["entity_type"], row["canonical_label"].strip().lower()))
    return rows, keys


def fetch_mesh_codes(entity_type: str, categories: list[str]) -> dict[str, tuple[str, str]]:
    """Retorna {rótulo_canônico_lowercase: (código_mesh, rótulo_oficial)}."""
    codes: dict[str, tuple[str, str]] = {}
    for category in categories:
        print(f"  [{entity_type}] consultando descritores de '{category}'...")
        descriptors = _fetch_descriptors(category)
        for iri, label in descriptors:
            code = iri.rsplit("/", 1)[-1]
            codes[label.strip().lower()] = (code, label.strip())
        time.sleep(0.3)
    return codes


def main():
    existing_rows, existing_keys = load_existing_links()
    print(f"{len(existing_rows)} linhas já existentes em {ONTOLOGY_LINKS_CSV.name} (preservadas como estão)")

    new_rows = []
    for entity_type, categories in ENTITY_CATEGORIES.items():
        codes = fetch_mesh_codes(entity_type, categories)
        added = 0
        for label_lower, (code, official_label) in codes.items():
            key = (entity_type, label_lower)
            if key in existing_keys:
                continue  # já tem link (manual ou de uma rodada anterior) — não sobrescreve
            new_rows.append({
                "entity_type": entity_type,
                "canonical_label": label_lower,
                "ontology": "MeSH",
                "code": code,
                "ontology_label": official_label,
            })
            existing_keys.add(key)
            added += 1
        print(f"  [{entity_type}] {added} termo(s) novo(s) ligado(s) ao MeSH ({len(codes)} descritores na(s) categoria(s))")

    all_rows = existing_rows + new_rows
    with open(ONTOLOGY_LINKS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["entity_type", "canonical_label", "ontology", "code", "ontology_label"])
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n{len(new_rows)} linhas novas adicionadas -> {len(all_rows)} linhas no total -> {ONTOLOGY_LINKS_CSV}")


if __name__ == "__main__":
    main()
