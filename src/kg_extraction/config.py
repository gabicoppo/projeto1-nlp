"""Caminhos e constantes centrais do projeto.

Mantemos tudo em um único lugar para que notebooks, scripts e o app Flask
apontem sempre para os mesmos arquivos.
"""

from pathlib import Path

# Raiz do repositório (dois níveis acima deste arquivo: src/kg_extraction/config.py -> raiz)
ROOT_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

REFERENCES_DIR = ROOT_DIR / "references"
VOCAB_DIR = REFERENCES_DIR / "vocabularies"

# Arquivos de entrada (amostra do MultiCaRe fornecida pela disciplina)
CASES_CSV = RAW_DIR / "cases.csv"
METADATA_CSV = RAW_DIR / "metadata.csv"

# Gazetteers (dicionários controlados usados na extração baseada em regras)
GAZETTEERS = {
    "Symptom": VOCAB_DIR / "symptoms.txt",
    "Exam": VOCAB_DIR / "exams.txt",
    "Diagnosis": VOCAB_DIR / "diagnoses.txt",
    "Treatment": VOCAB_DIR / "treatments.txt",
}
UNITS_FILE = VOCAB_DIR / "units.txt"
ONTOLOGY_LINKS_CSV = VOCAB_DIR / "ontology_links.csv"

# Saídas do pipeline: o grafo CANÔNICO (mais detalhado, estilo example2)
NODES_CSV = PROCESSED_DIR / "nodes.csv"
EDGES_CSV = PROCESSED_DIR / "edges.csv"

# Três níveis de abstração derivados do grafo canônico (usados pela visualização)
ABSTRACTION_LEVELS = ("basic", "intermediate", "detailed")
