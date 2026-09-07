# Instalação e execução

## Requisitos
- Python 3.10+

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Rodar o pipeline de extração (gera `data/processed/nodes.csv` e `edges.csv`)

```bash
make pipeline
# equivalente a: PYTHONPATH=src python -m kg_extraction.pipeline
```

Use `--limit N` para rodar só os N primeiros casos durante o desenvolvimento:

```bash
PYTHONPATH=src python -m kg_extraction.pipeline --limit 5
```

## Rodar a aplicação web de visualização

```bash
make app
# equivalente a: PYTHONPATH=src FLASK_APP=kg_extraction.app.app flask run --debug
```

Acesse http://127.0.0.1:5000. Selecione um caso no menu e alterne entre os
níveis **Básico / Detalhado**.

## Rodar os testes

```bash
make test
```

## Estrutura do código (`src/kg_extraction/`)

| Módulo | Responsabilidade |
|---|---|
| `data/make_dataset.py` | Carrega `cases.csv` / `metadata.csv` |
| `features/preprocessing.py` | Segmentação de frases (regras); mantém `STOPWORDS` reaproveitado por `scripts/build_units_from_ncit.py` |
| `features/gazetteer_ner.py` | Reconhecimento de entidades por dicionários controlados |
| `features/value_unit_extraction.py` | Regex para valores numéricos, unidades e faixas de referência |
| `features/relation_rules.py` | Regras de classificação de relações (histórico vs. diagnóstico, achados) |
| `graph/canonical_graph.py` | Orquestra tudo acima em um grafo canônico por caso (nós/arestas) |
| `graph/views.py` | Deriva os 2 níveis de abstração a partir do grafo canônico |
| `pipeline.py` | Script de ponta a ponta (todos os casos → CSVs em `data/processed/`) |
| `app/` | Aplicação Flask + Cytoscape.js para visualização interativa |
