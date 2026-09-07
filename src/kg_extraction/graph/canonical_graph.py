"""Construção do grafo de conhecimento CANÔNICO de um caso clínico.

"Canônico" aqui significa: o grafo mais decomposto e rico que o pipeline
produz (no estilo do example2.md do enunciado — atributos como valor/unidade
viram nós próprios, e entidades são ligadas a vocabulários controlados).
As 3 visualizações de nível de abstração (básico/intermediário/detalhado)
são todas DERIVADAS deste grafo único por agregação/filtragem
(ver graph/views.py) — garantindo que os três níveis sejam sempre
consistentes entre si.

Todas as técnicas usadas aqui são clássicas (regras, regex, dicionários),
conforme exigido pelo enunciado para esta etapa do projeto.
"""

from __future__ import annotations

import pandas as pd

from kg_extraction.config import GAZETTEERS, ONTOLOGY_LINKS_CSV, UNITS_FILE
from kg_extraction.features.gazetteer_ner import (
    find_entities_in_sentence,
    build_matcher,
    load_all_gazetteers,
)
from kg_extraction.features.preprocessing import split_sentences
from kg_extraction.features.relation_rules import (
    classify_diagnosis_relation,
    classify_exam_finding_relation,
    classify_symptom_relation,
)
from kg_extraction.features.value_unit_extraction import (
    build_value_unit_pattern,
    find_reference_ranges,
    find_values,
    load_units,
)


class _IdCounter:
    """Gera ids sequenciais legíveis (S1, S2, E1, ...) por tipo de nó, por caso."""

    def __init__(self):
        self._counts: dict[str, int] = {}

    def next(self, prefix: str) -> str:
        self._counts[prefix] = self._counts.get(prefix, 0) + 1
        return f"{prefix}{self._counts[prefix]}"


_TYPE_PREFIX = {
    "Patient": "P",
    "History": "H",
    "Symptom": "S",
    "Exam": "E",
    "ExamResult": "R",
    "Value": "V",
    "Unit": "U",
    "ReferenceRange": "RR",
    "Diagnosis": "D",
    "Treatment": "T",
    "AnatomicalSite": "A",
    "OntologyConcept": "O",
}


def _load_ontology_links() -> pd.DataFrame:
    try:
        return pd.read_csv(ONTOLOGY_LINKS_CSV)
    except FileNotFoundError:
        return pd.DataFrame(columns=["entity_type", "canonical_label", "ontology", "code", "ontology_label"])


# Carregados uma única vez por processo (reaproveitados entre casos)
_GAZETTEER_MATCHER = build_matcher(load_all_gazetteers(GAZETTEERS))
_UNIT_PATTERN = build_value_unit_pattern(load_units(UNITS_FILE))
_ONTOLOGY_LINKS = _load_ontology_links()


def extract_case_graph(case_row) -> tuple[list[dict], list[dict]]:
    """Extrai o grafo canônico (nós, arestas) de UM caso clínico.

    Parameters
    ----------
    case_row : linha do DataFrame de cases.csv (precisa de case_id, case_text,
               age, gender).

    Returns
    -------
    (nodes, edges): listas de dicts prontas para virar as tabelas do
    enunciado (node_id/type/label/attributes e edge_id/source_id/target_id/
    relation/attributes), com uma coluna extra `case_id` para permitir
    filtrar por caso na aplicação web.
    """
    case_id = case_row["case_id"]
    ids = _IdCounter()
    nodes: list[dict] = []
    edges: list[dict] = []

    def add_node(node_type: str, label: str, attributes: dict | None = None) -> str:
        node_id = ids.next(_TYPE_PREFIX.get(node_type, "N"))
        nodes.append(
            {
                "node_id": node_id,
                "case_id": case_id,
                "type": node_type,
                "label": label,
                "attributes": _fmt_attrs(attributes or {}),
            }
        )
        return node_id

    _seen_simple_edges: set[tuple[str, str, str]] = set()

    def add_edge(source_id: str, target_id: str, relation: str, attributes: dict | None = None):
        # Para relações sem atributos próprios (ex.: PRESENTS_WITH, UNDERWENT_EXAM,
        # DIAGNOSED_WITH, SUPPORTS, TREATED_BY), evita duplicar a mesma aresta
        # quando a mesma entidade é mencionada de novo em outra frase do caso.
        if not attributes:
            key = (source_id, target_id, relation)
            if key in _seen_simple_edges:
                return
            _seen_simple_edges.add(key)
        edges.append(
            {
                "edge_id": f"e{len(edges) + 1}_{case_id}",
                "case_id": case_id,
                "source_id": source_id,
                "target_id": target_id,
                "relation": relation,
                "attributes": _fmt_attrs(attributes or {}),
            }
        )

    def link_ontology(node_id: str, entity_type: str, canonical_label: str):
        matches = _ONTOLOGY_LINKS[
            (_ONTOLOGY_LINKS["entity_type"] == entity_type)
            & (_ONTOLOGY_LINKS["canonical_label"] == canonical_label)
        ]
        for _, row in matches.iterrows():
            concept_id = add_node(
                "OntologyConcept",
                row["ontology_label"],
                {"ontology": row["ontology"], "code": row["code"]},
            )
            add_edge(node_id, concept_id, "LINKED_TO")

    # --- nó Patient -----------------------------------------------------
    patient_id = add_node(
        "Patient",
        f"case {case_id}",
        {"age": case_row.get("age"), "gender": case_row.get("gender")},
    )

    sentences = split_sentences(str(case_row["case_text"]))

    last_exam_id = None       # último Exam mencionado (para HAS_RESULT / achados)
    last_diagnosis_id = None  # último Diagnosis mencionado (para TREATED_BY / SUPPORTS)
    seen_labels: dict[tuple[str, str], str] = {}  # (type,label) -> node_id, evita duplicar nós

    def get_or_create_entity(entity_type: str, canonical_label: str) -> tuple[str, bool]:
        key = (entity_type, canonical_label)
        if key in seen_labels:
            return seen_labels[key], False
        node_id = add_node(entity_type, canonical_label)
        seen_labels[key] = node_id
        link_ontology(node_id, entity_type, canonical_label)
        return node_id, True

    for sent_idx, sentence in enumerate(sentences):
        entity_matches = find_entities_in_sentence(sentence, _GAZETTEER_MATCHER, sent_idx)
        diagnosis_ids_this_sentence = []
        supporting_ids_this_sentence = []
        anatomy_ids_this_sentence = []       # AnatomicalSite citados nesta frase
        clinical_entity_ids_this_sentence = []  # Symptom/Exam/Diagnosis/Treatment desta frase, p/ LOCATED_IN

        for em in entity_matches:
            if em.entity_type == "Symptom":
                relation = classify_symptom_relation(sentence, em.start)
                node_id, _ = get_or_create_entity("Symptom", em.canonical_label)
                add_edge(patient_id, node_id, relation)
                # um sintoma NEGADO ("denies fever") não deve apoiar um
                # diagnóstico nem herdar região anatômica da mesma frase —
                # isso implicaria que o achado é real, o oposto do texto.
                if relation == "PRESENTS_WITH":
                    supporting_ids_this_sentence.append(node_id)
                    clinical_entity_ids_this_sentence.append(node_id)

            elif em.entity_type == "Exam":
                node_id, _ = get_or_create_entity("Exam", em.canonical_label)
                add_edge(patient_id, node_id, "UNDERWENT_EXAM")
                last_exam_id = node_id
                supporting_ids_this_sentence.append(node_id)
                clinical_entity_ids_this_sentence.append(node_id)

            elif em.entity_type == "Diagnosis":
                relation = classify_diagnosis_relation(sentence, em.start)
                node_type = "History" if relation == "HAS_HISTORY" else "Diagnosis"
                node_id, _ = get_or_create_entity(node_type, em.canonical_label)
                add_edge(patient_id, node_id, relation)
                # um diagnóstico NEGADO ("ruled out acute pancreatitis") não
                # deve virar alvo de SUPPORTS nem de TREATED_BY — do
                # contrário o grafo diria que outros achados da mesma frase
                # sustentam um diagnóstico que o texto descarta, ou que um
                # tratamento citado depois trata algo que foi excluído.
                if relation == "DIAGNOSED_WITH":
                    diagnosis_ids_this_sentence.append(node_id)
                    last_diagnosis_id = node_id
                if relation != "DENIES":
                    clinical_entity_ids_this_sentence.append(node_id)

            elif em.entity_type == "Treatment":
                node_id, _ = get_or_create_entity("Treatment", em.canonical_label)
                target = last_diagnosis_id or patient_id
                relation = "TREATED_BY" if last_diagnosis_id else "UNDERWENT_TREATMENT"
                # a relação TREATED_BY parte do diagnóstico em direção ao tratamento
                if last_diagnosis_id:
                    add_edge(last_diagnosis_id, node_id, relation)
                else:
                    add_edge(patient_id, node_id, relation)
                clinical_entity_ids_this_sentence.append(node_id)

            elif em.entity_type == "AnatomicalSite":
                # Não liga direto ao Patient (achar que "paciente tem fígado" não é um
                # fato clínico) — é um modificador de outra entidade citada na mesma
                # frase (ver cross-join LOCATED_IN logo abaixo, mesmo padrão do SUPPORTS).
                node_id, _ = get_or_create_entity("AnatomicalSite", em.canonical_label)
                anatomy_ids_this_sentence.append(node_id)

        # valores numéricos + unidade (ex.: "850 U/L") -> associados ao último Exam da frase
        value_matches = find_values(sentence, _UNIT_PATTERN, sent_idx)
        range_matches = find_reference_ranges(sentence, sent_idx)
        if value_matches and last_exam_id is not None:
            for vm in value_matches:
                result_id = add_node("ExamResult", f"{vm.value} {vm.unit}")
                add_edge(last_exam_id, result_id, "HAS_RESULT")

                value_id = add_node("Value", vm.value)
                add_edge(result_id, value_id, "HAS_VALUE")

                unit_id = add_node("Unit", vm.unit)
                add_edge(result_id, unit_id, "HAS_UNIT")

                for rm in range_matches:
                    range_id = add_node(
                        "ReferenceRange",
                        f"{rm.low}-{rm.high} {rm.unit or vm.unit}",
                        {"low": rm.low, "high": rm.high, "unit": rm.unit or vm.unit},
                    )
                    add_edge(result_id, range_id, "HAS_REFERENCE_RANGE")

        # relação SUPPORTS: sintomas/exames/achados citados na MESMA frase que um
        # diagnóstico são heuristicamente considerados evidências de apoio a ele.
        if diagnosis_ids_this_sentence:
            for diag_id in diagnosis_ids_this_sentence:
                for support_id in supporting_ids_this_sentence:
                    add_edge(support_id, diag_id, "SUPPORTS")

        # relação LOCATED_IN: mesma heurística de co-ocorrência do SUPPORTS, mas
        # para região anatômica — "abdominal ultrasound" na mesma frase que
        # "pancreatic pseudocyst" liga pseudocyst -> pancreas (a entidade clínica
        # aponta para o local, não o contrário).
        if anatomy_ids_this_sentence:
            for anatomy_id in anatomy_ids_this_sentence:
                for entity_id in clinical_entity_ids_this_sentence:
                    add_edge(entity_id, anatomy_id, "LOCATED_IN")

        # achados de exame de imagem (CONFIRMS/EXCLUDES/REVEALS) — heurística leve:
        # se a frase tem um verbo-gatilho e um Exam, e menciona um Diagnosis já
        # visto anteriormente, registra o tipo de achado como atributo da aresta.
        if last_exam_id is not None and any(
            em.entity_type == "Diagnosis" for em in entity_matches
        ):
            finding_relation = classify_exam_finding_relation(sentence)
            if finding_relation != "REVEALS":  # só registra quando há sinal explícito
                for diag_id in diagnosis_ids_this_sentence:
                    add_edge(last_exam_id, diag_id, finding_relation)

    return nodes, edges


def _fmt_attrs(attributes: dict) -> str:
    """Formata atributos como 'chave=valor; chave=valor', igual ao example1.md,
    para a coluna `attributes` da tabela de nós/arestas. Usado apenas para os
    poucos atributos que NÃO foram decompostos em nós próprios (ex.: idade e
    gênero do paciente).
    """
    parts = [f"{k}={v}" for k, v in attributes.items() if v not in (None, "", float("nan"))]
    return "; ".join(parts)
