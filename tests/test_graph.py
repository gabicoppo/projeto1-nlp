import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kg_extraction.graph.canonical_graph import extract_case_graph
from kg_extraction.graph.views import derive_view

SAMPLE_CASE = pd.Series(
    {
        "case_id": "TEST_01",
        "case_text": (
            "A 60-year-old man with a history of hypertension presented with "
            "abdominal pain and fever. Laboratory tests showed elevated "
            "serum lipase (850 U/L, reference range 10-140 U/L). Abdominal "
            "computed tomography confirmed acute pancreatitis. He was "
            "treated with intravenous fluids."
        ),
        "age": 60,
        "gender": "Male",
    }
)


def _graph():
    nodes, edges = extract_case_graph(SAMPLE_CASE)
    return pd.DataFrame(nodes), pd.DataFrame(edges)


def test_patient_node_created_with_demographics():
    nodes, _ = _graph()
    patient = nodes[nodes["type"] == "Patient"].iloc[0]
    assert "age=60" in patient["attributes"]
    assert "gender=Male" in patient["attributes"]


def test_history_vs_diagnosis_classification():
    nodes, edges = _graph()
    # hipertensão é histórico prévio -> nó History, não Diagnosis
    assert "hypertension" in nodes[nodes["type"] == "History"]["label"].tolist()
    assert "acute pancreatitis" in nodes[nodes["type"] == "Diagnosis"]["label"].tolist()
    assert "HAS_HISTORY" in edges["relation"].tolist()
    assert "DIAGNOSED_WITH" in edges["relation"].tolist()


def test_exam_result_value_unit_and_reference_range_extracted():
    nodes, edges = _graph()
    assert "ExamResult" in nodes["type"].tolist()
    assert "HAS_VALUE" in edges["relation"].tolist()
    assert "HAS_UNIT" in edges["relation"].tolist()
    assert "HAS_REFERENCE_RANGE" in edges["relation"].tolist()


def test_views_are_consistently_derived_from_canonical_graph():
    nodes, edges = _graph()
    basic_n, _ = derive_view("basic", nodes, edges, "TEST_01")
    detailed_n, _ = derive_view("detailed", nodes, edges, "TEST_01")

    # o nível básico não deve expor nós decompostos de Value/Unit/ReferenceRange
    assert not set(basic_n["type"]) & {"Value", "Unit", "ReferenceRange"}
    # o nível detalhado deve conter, sim, esses nós decompostos
    assert {"Value", "Unit"}.issubset(set(detailed_n["type"]))
    # o básico deve ter menos (ou igual) nós que o detalhado
    assert len(basic_n) <= len(detailed_n)
