"""Deriva os 3 níveis de abstração pedidos no projeto a partir do grafo
CANÔNICO único (graph/canonical_graph.py), por agregação/filtragem — não
são três extrações independentes. Isso garante que os três níveis sejam
sempre consistentes entre si e reduz o retrabalho de manutenção.

- basic        -> estilo example1.md: bom para leitura rápida de um caso
                  simples (ex.: médico assistente olhando o caso do seu
                  paciente). Resultados de exame viram um único nó
                  "ExamResult" com os atributos (valor/unidade/faixa de
                  referência) agregados em texto, e não há nós de
                  vocabulário controlado.
- intermediate -> para um caso complexo em que o médico precisa de mais
                  segurança no diagnóstico: mantém a estrutura do "basic"
                  mas preserva a ligação dos DIAGNÓSTICOS aos códigos de
                  vocabulário controlado (ICD-10/SNOMED/MeSH), sem
                  decompor exames/valores.
- detailed     -> estilo example2.md: o grafo canônico completo, com
                  Value/Unit/ReferenceRange como nós próprios e todas as
                  entidades ligadas a vocabulários controlados. Útil para
                  quem estuda o caso em profundidade (ex.: prova de
                  residência).
"""

from __future__ import annotations

import pandas as pd

_DECOMPOSED_ATTR_TYPES = {"Value", "Unit", "ReferenceRange"}
_ATTR_EDGE_RELATIONS = {"HAS_VALUE", "HAS_UNIT", "HAS_REFERENCE_RANGE"}


def _filter_case(nodes_df: pd.DataFrame, edges_df: pd.DataFrame, case_id: str):
    n = nodes_df[nodes_df["case_id"] == case_id].copy()
    e = edges_df[edges_df["case_id"] == case_id].copy()
    return n, e


def _collapse_decomposed_attributes(nodes_df: pd.DataFrame, edges_df: pd.DataFrame):
    """Junta Value/Unit/ReferenceRange de volta como texto no `attributes`
    do ExamResult pai, e remove esses nós/arestas 'satélite' do grafo.
    """
    nodes_by_id = nodes_df.set_index("node_id").to_dict("index")
    extra_attrs: dict[str, list[str]] = {}

    attr_edges = edges_df[edges_df["relation"].isin(_ATTR_EDGE_RELATIONS)]
    for _, edge in attr_edges.iterrows():
        child = nodes_by_id.get(edge["target_id"])
        if child is None:
            continue
        key = "value" if child["type"] == "Value" else (
            "unit" if child["type"] == "Unit" else "reference_range"
        )
        extra_attrs.setdefault(edge["source_id"], []).append(f"{key}={child['label']}")

    def merge_attrs(row):
        existing = row["attributes"]
        existing = "" if pd.isna(existing) else str(existing)
        if row["node_id"] in extra_attrs:
            pieces = [existing] if existing else []
            pieces.extend(extra_attrs[row["node_id"]])
            return "; ".join(p for p in pieces if p)
        return existing

    nodes_df = nodes_df.copy()
    nodes_df["attributes"] = nodes_df.apply(merge_attrs, axis=1)

    keep_nodes = nodes_df[~nodes_df["type"].isin(_DECOMPOSED_ATTR_TYPES)]
    keep_edges = edges_df[~edges_df["relation"].isin(_ATTR_EDGE_RELATIONS)]
    keep_edges = keep_edges[keep_edges["target_id"].isin(keep_nodes["node_id"]) | keep_edges["relation"].eq("LINKED_TO")]
    return keep_nodes, keep_edges


def _drop_ontology(nodes_df: pd.DataFrame, edges_df: pd.DataFrame, keep_for_types: set[str] | None = None):
    """Remove nós OntologyConcept e arestas LINKED_TO. Se `keep_for_types`
    for informado, preserva apenas as ligações cujo nó de origem seja de um
    dos tipos indicados (ex.: {"Diagnosis"} no nível intermediário).
    """
    nodes_by_id = nodes_df.set_index("node_id").to_dict("index")
    linked_edges = edges_df[edges_df["relation"] == "LINKED_TO"]

    if keep_for_types:
        edges_to_keep_ids = {
            edge["target_id"]
            for _, edge in linked_edges.iterrows()
            if nodes_by_id.get(edge["source_id"], {}).get("type") in keep_for_types
        }
    else:
        edges_to_keep_ids = set()

    nodes_out = nodes_df[
        (nodes_df["type"] != "OntologyConcept") | (nodes_df["node_id"].isin(edges_to_keep_ids))
    ]
    edges_out = edges_df[
        (edges_df["relation"] != "LINKED_TO") | (edges_df["target_id"].isin(edges_to_keep_ids))
    ]
    return nodes_out, edges_out


def derive_basic(nodes_df: pd.DataFrame, edges_df: pd.DataFrame, case_id: str):
    n, e = _filter_case(nodes_df, edges_df, case_id)
    n, e = _collapse_decomposed_attributes(n, e)
    n, e = _drop_ontology(n, e, keep_for_types=None)
    return n.reset_index(drop=True), e.reset_index(drop=True)


def derive_intermediate(nodes_df: pd.DataFrame, edges_df: pd.DataFrame, case_id: str):
    n, e = _filter_case(nodes_df, edges_df, case_id)
    n, e = _collapse_decomposed_attributes(n, e)
    n, e = _drop_ontology(n, e, keep_for_types={"Diagnosis"})
    return n.reset_index(drop=True), e.reset_index(drop=True)


def derive_detailed(nodes_df: pd.DataFrame, edges_df: pd.DataFrame, case_id: str):
    n, e = _filter_case(nodes_df, edges_df, case_id)
    return n.reset_index(drop=True), e.reset_index(drop=True)


VIEW_BUILDERS = {
    "basic": derive_basic,
    "intermediate": derive_intermediate,
    "detailed": derive_detailed,
}


def derive_view(level: str, nodes_df: pd.DataFrame, edges_df: pd.DataFrame, case_id: str):
    if level not in VIEW_BUILDERS:
        raise ValueError(f"Nível de abstração desconhecido: {level!r}. Use um de {list(VIEW_BUILDERS)}.")
    return VIEW_BUILDERS[level](nodes_df, edges_df, case_id)
