"""Carrega os dados brutos da amostra do MultiCaRe.

cases.csv    -> um caso clínico por linha (article_id, case_id, case_text, age, gender)
metadata.csv -> um artigo por linha (article_id, title, mesh_terms, ...)
"""

import ast

import pandas as pd

from kg_extraction.config import CASES_CSV, METADATA_CSV


def _parse_listlike(value: str):
    """metadata.csv guarda listas como texto entre colchetes, ex: "[Female]".
    Convertemos para uma lista Python real quando possível.
    """
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        # fallback simples: remove colchetes e separa por vírgula
        return [v.strip().strip("'\"") for v in value.strip("[]").split(",") if v.strip()]


def load_cases(path=CASES_CSV) -> pd.DataFrame:
    """Retorna o DataFrame de casos clínicos (1 linha = 1 paciente/caso)."""
    df = pd.read_csv(path)
    df["case_text"] = df["case_text"].fillna("")
    return df


def load_metadata(path=METADATA_CSV) -> pd.DataFrame:
    """Retorna o DataFrame de metadados dos artigos, com colunas de lista já parseadas."""
    df = pd.read_csv(path)
    for col in ("authors", "mesh_terms", "major_mesh_terms", "keywords"):
        if col in df.columns:
            df[col] = df[col].apply(_parse_listlike)
    return df


def load_case_with_metadata(case_id: str):
    """Conveniência: retorna (linha_do_caso, linha_do_artigo) para um case_id específico."""
    cases = load_cases()
    metadata = load_metadata()
    case_row = cases.loc[cases["case_id"] == case_id].iloc[0]
    article_row = metadata.loc[metadata["article_id"] == case_row["article_id"]].iloc[0]
    return case_row, article_row


if __name__ == "__main__":
    cases = load_cases()
    metadata = load_metadata()
    print(f"{len(cases)} casos carregados de {len(metadata)} artigos.")
    print(cases.head(3)[["case_id", "age", "gender"]])
