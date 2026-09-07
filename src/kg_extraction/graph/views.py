"""Deriva os 2 níveis de abstração pedidos no projeto a partir do grafo
CANÔNICO único (graph/canonical_graph.py), por agregação/filtragem — não
são duas extrações independentes. Isso garante que os dois níveis sejam
sempre consistentes entre si e reduz o retrabalho de manutenção.

- basic    -> estilo example1.md: bom para leitura rápida de um caso
              simples (ex.: médico assistente olhando o caso do seu
              paciente). Resultados de exame viram um único nó
              "ExamResult" com os atributos (valor/unidade/faixa de
              referência) agregados em texto, e não há nós de vocabulário
              controlado.
- detailed -> estilo example2.md: o grafo canônico completo, com
              Value/Unit/ReferenceRange como nós próprios e todas as
              entidades ligadas a vocabulários controlados. Útil para
              quem estuda o caso em profundidade (ex.: prova de
              residência).

(Havia um terceiro nível, "intermediate", que ficava entre os dois —
removido a pedido da equipe para simplificar para 2 níveis; não
correspondia a nenhum dos exemplos do enunciado, era uma invenção do time.)
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


def _drop_ontology(nodes_df: pd.DataFrame, edges_df: pd.DataFrame):
    """Remove nós OntologyConcept e arestas LINKED_TO (usado só pelo nível
    básico — o detalhado mantém vocabulário controlado pra toda entidade)."""
    nodes_out = nodes_df[nodes_df["type"] != "OntologyConcept"]
    edges_out = edges_df[edges_df["relation"] != "LINKED_TO"]
    return nodes_out, edges_out


def derive_basic(nodes_df: pd.DataFrame, edges_df: pd.DataFrame, case_id: str):
    n, e = _filter_case(nodes_df, edges_df, case_id)
    n, e = _collapse_decomposed_attributes(n, e)
    n, e = _drop_ontology(n, e)
    return n.reset_index(drop=True), e.reset_index(drop=True)


def derive_detailed(nodes_df: pd.DataFrame, edges_df: pd.DataFrame, case_id: str):
    n, e = _filter_case(nodes_df, edges_df, case_id)
    return n.reset_index(drop=True), e.reset_index(drop=True)


VIEW_BUILDERS = {
    "basic": derive_basic,
    "detailed": derive_detailed,
}


def derive_view(level: str, nodes_df: pd.DataFrame, edges_df: pd.DataFrame, case_id: str):
    if level not in VIEW_BUILDERS:
        raise ValueError(f"Nível de abstração desconhecido: {level!r}. Use um de {list(VIEW_BUILDERS)}.")
    return VIEW_BUILDERS[level](nodes_df, edges_df, case_id)
