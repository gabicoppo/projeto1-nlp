"""Aplicação web (Flask) para visualizar o grafo de conhecimento extraído,
em 3 níveis de abstração escolhidos pelo usuário.

Rodar (a partir da raiz do repositório, com PYTHONPATH=src):
    export PYTHONPATH=src
    export FLASK_APP=kg_extraction.app.app
    flask run --debug

ou simplesmente:
    python -m kg_extraction.app.app

Pré-requisito: rodar antes `python -m kg_extraction.pipeline` para gerar
data/processed/nodes.csv e edges.csv.
"""

import pandas as pd
from flask import Flask, jsonify, render_template

from kg_extraction.config import EDGES_CSV, NODES_CSV
from kg_extraction.data.make_dataset import load_cases
from kg_extraction.graph.views import derive_view

app = Flask(__name__)

# Cores por tipo de nó (mesma paleta usada nos exemplos do enunciado, em mermaid)
NODE_COLORS = {
    "Patient": "#fef3c7",
    "History": "#e0e7ff",
    "Symptom": "#fee2e2",
    "Exam": "#dbeafe",
    "ExamResult": "#cffafe",
    "Value": "#a5f3fc",
    "Unit": "#67e8f9",
    "ReferenceRange": "#bae6fd",
    "Diagnosis": "#dcfce7",
    "Treatment": "#fef9c3",
    "OntologyConcept": "#f3e8ff",
}


def _load_graph_tables():
    nodes_df = pd.read_csv(NODES_CSV)
    edges_df = pd.read_csv(EDGES_CSV)
    return nodes_df, edges_df


@app.route("/")
def index():
    cases = load_cases()
    case_options = [
        {"case_id": row["case_id"], "age": row["age"], "gender": row["gender"]}
        for _, row in cases.iterrows()
    ]
    return render_template("index.html", cases=case_options)


@app.route("/api/case_text/<case_id>")
def api_case_text(case_id):
    cases = load_cases()
    row = cases.loc[cases["case_id"] == case_id]
    if row.empty:
        return jsonify({"error": "case not found"}), 404
    return jsonify({"case_id": case_id, "case_text": row.iloc[0]["case_text"]})


@app.route("/api/graph/<case_id>/<level>")
def api_graph(case_id, level):
    nodes_df, edges_df = _load_graph_tables()
    try:
        n, e = derive_view(level, nodes_df, edges_df, case_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if n.empty:
        return jsonify({"error": "case not found or graph not generated yet"}), 404

    cy_nodes = [
        {
            "data": {
                "id": row["node_id"],
                "label": row["label"],
                "type": row["type"],
                "attributes": "" if pd.isna(row["attributes"]) else row["attributes"],
                "color": NODE_COLORS.get(row["type"], "#e5e7eb"),
            }
        }
        for _, row in n.iterrows()
    ]
    cy_edges = [
        {
            "data": {
                "id": row["edge_id"],
                "source": row["source_id"],
                "target": row["target_id"],
                "relation": row["relation"],
            }
        }
        for _, row in e.iterrows()
    ]
    return jsonify({"nodes": cy_nodes, "edges": cy_edges})


if __name__ == "__main__":
    app.run(debug=True)
