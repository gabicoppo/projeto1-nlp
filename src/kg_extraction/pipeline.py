"""Script de ponta a ponta: lê data/raw/cases.csv, extrai o grafo canônico
de cada caso (técnicas clássicas apenas) e grava data/processed/nodes.csv
e data/processed/edges.csv.

Uso:
    python -m kg_extraction.pipeline
    python -m kg_extraction.pipeline --limit 10   # só os 10 primeiros casos
"""

from __future__ import annotations

import argparse

import pandas as pd

from kg_extraction.config import EDGES_CSV, NODES_CSV, PROCESSED_DIR
from kg_extraction.data.make_dataset import load_cases
from kg_extraction.graph.canonical_graph import extract_case_graph


def run(limit: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    cases = load_cases()
    if limit:
        cases = cases.head(limit)

    all_nodes, all_edges = [], []
    for _, case_row in cases.iterrows():
        nodes, edges = extract_case_graph(case_row)
        all_nodes.extend(nodes)
        all_edges.extend(edges)

    nodes_df = pd.DataFrame(all_nodes)
    edges_df = pd.DataFrame(all_edges)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    nodes_df.to_csv(NODES_CSV, index=False)
    edges_df.to_csv(EDGES_CSV, index=False)

    print(f"{len(cases)} casos processados.")
    print(f"{len(nodes_df)} nós -> {NODES_CSV}")
    print(f"{len(edges_df)} arestas -> {EDGES_CSV}")
    return nodes_df, edges_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Processar só os N primeiros casos")
    args = parser.parse_args()
    run(limit=args.limit)
