"""Valida a qualidade da extração de Diagnosis cruzando com mesh_terms/
major_mesh_terms de metadata.csv — a análise que o próprio README.md já
sugere em "Análises que podem ser realizadas" ("Cruzar major_mesh_terms de
metadata.csv com os Diagnosis extraídos para validar a qualidade da
extração contra uma anotação externa") e que nunca tinha sido implementada.

100% offline: não reconsulta o MeSH pela rede a cada execução. Em vez
disso, usa o próprio references/vocabularies/diagnoses.txt (já construído
a partir do MeSH — ver scripts/build_gazetteer_from_mesh.py) como critério
pra saber se um termo do metadata é uma "doença" (árvore C): se o termo
aparece lá como rótulo canônico ou sinônimo, tratamos como doença; senão
(ex.: "Humans", "Case Reports", "Gastroscopy", "Methylprednisolone" — check
tags, tipo de publicação, procedimento, substância) é ignorado. Essa
filtragem é a mesma ideia mecânica usada pra decidir o escopo de
diagnoses.txt: perguntar ao MeSH, não adivinhar lendo o texto.

Prioriza `major_mesh_terms` (termos centrais do artigo, é o que o README
sugere) e cai pra `mesh_terms` (mais denso, mas menos "central") quando o
artigo não tem major_mesh_terms.

Roda sobre TODOS os casos de cases.csv, não só os que têm anotação externa
disponível — os que não têm ficam registrados com status "sem_gold"/
"sem_metadata" em vez de somem silenciosamente, pra deixar claro qual
fração do dataset é de fato validável dessa forma.

Uso:
    PYTHONPATH=src python scripts/validate_against_metadata.py

Pré-requisito: rodar `make pipeline` antes (lê data/processed/nodes.csv).
Saída: imprime o resumo no terminal e grava o detalhe por caso em
data/processed/validation_against_metadata.csv (reaproveitável em slides/
relatório, sem precisar rodar de novo).
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kg_extraction.config import NODES_CSV, PROCESSED_DIR, VOCAB_DIR  # noqa: E402
from kg_extraction.data.make_dataset import load_cases, load_metadata  # noqa: E402

REPORT_CSV = PROCESSED_DIR / "validation_against_metadata.csv"


def load_diagnosis_vocabulary() -> set[str]:
    """Todos os rótulos canônicos + sinônimos de diagnoses.txt, num set só,
    pra checagem rápida de "isso é um termo de doença conhecido?"."""
    vocab = set()
    with open(VOCAB_DIR / "diagnoses.txt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for part in line.split("|"):
                vocab.add(part.strip().lower())
    return vocab


def gold_diagnoses_for_article(mesh_terms: list, vocab: set[str]) -> set[str]:
    """De uma lista de mesh_terms (às vezes com qualificador tipo
    'X / diagnosis'), retorna só os que são termos de doença conhecidos
    (aparecem em diagnoses.txt), com o qualificador removido."""
    gold = set()
    for term in mesh_terms or []:
        base = str(term).split(" / ")[0].strip().lower()
        if base in vocab:
            gold.add(base)
    return gold


def main():
    vocab = load_diagnosis_vocabulary()
    print(f"{len(vocab)} rótulos/sinônimos conhecidos em diagnoses.txt\n")

    cases = load_cases()
    metadata = load_metadata()
    nodes = pd.read_csv(NODES_CSV)

    cases["article_id"] = cases["article_id"].astype(str)
    metadata["article_id"] = metadata["article_id"].astype(str)
    metadata_by_article = metadata.set_index("article_id")

    extracted_by_case = defaultdict(set)
    for _, row in nodes[nodes["type"] == "Diagnosis"].iterrows():
        extracted_by_case[row["case_id"]].add(str(row["label"]).strip().lower())

    report_rows = []
    for _, case_row in cases.iterrows():
        case_id = case_row["case_id"]
        article_id = case_row["article_id"]
        base_row = {"case_id": case_id, "article_id": article_id}

        if article_id not in metadata_by_article.index:
            report_rows.append({**base_row, "status": "sem_metadata", "source": "",
                                 "n_gold": 0, "n_found": 0, "gold": "", "encontrados": "", "perdidos": ""})
            continue

        article = metadata_by_article.loc[article_id]
        major = article.get("major_mesh_terms")
        source_terms, source_name = (major, "major_mesh_terms") if major else (article.get("mesh_terms"), "mesh_terms")
        gold = gold_diagnoses_for_article(source_terms, vocab)

        if not gold:
            report_rows.append({**base_row, "status": "sem_gold", "source": source_name,
                                 "n_gold": 0, "n_found": 0, "gold": "", "encontrados": "", "perdidos": ""})
            continue

        extracted = extracted_by_case.get(case_id, set())
        found = gold & extracted
        missed = gold - extracted
        report_rows.append({
            **base_row,
            "status": "validado",
            "source": source_name,
            "n_gold": len(gold),
            "n_found": len(found),
            "gold": "|".join(sorted(gold)),
            "encontrados": "|".join(sorted(found)),
            "perdidos": "|".join(sorted(missed)),
        })

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "article_id", "status", "source",
                                                "n_gold", "n_found", "gold", "encontrados", "perdidos"])
        writer.writeheader()
        writer.writerows(report_rows)

    # --- resumo ---
    n_total = len(report_rows)
    n_sem_metadata = sum(1 for r in report_rows if r["status"] == "sem_metadata")
    n_sem_gold = sum(1 for r in report_rows if r["status"] == "sem_gold")
    validated = [r for r in report_rows if r["status"] == "validado"]
    n_validado = len(validated)
    total_gold = sum(r["n_gold"] for r in validated)
    total_found = sum(r["n_found"] for r in validated)

    print(f"{n_total} casos no total")
    print(f"  {n_sem_metadata} sem artigo correspondente em metadata.csv")
    print(f"  {n_sem_gold} com metadata mas sem nenhum termo de doença nos mesh_terms")
    print(f"  {n_validado} validáveis (têm termo de doença pra comparar)\n")

    for r in validated:
        status = "OK    " if not r["perdidos"] else ("parcial" if r["encontrados"] else "FALHOU")
        print(f"[{status}] {r['case_id']} ({r['source']}): gold=[{r['gold']}] | achados=[{r['encontrados']}] | perdidos=[{r['perdidos']}]")

    if total_gold:
        pct = 100 * total_found / total_gold
        print(f"\nRECALL AGREGADO (só nos {n_validado} casos validáveis de {n_total} no total): "
              f"{total_found}/{total_gold} termos de doença indexados pela PubMed "
              f"também extraídos pelo pipeline ({pct:.1f}%)")
    else:
        print("\nNenhum artigo com termo de doença nos mesh_terms — nada pra comparar.")

    print(f"\nDetalhe por caso salvo em {REPORT_CSV}")


if __name__ == "__main__":
    main()
