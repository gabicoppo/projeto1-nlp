.PHONY: install pipeline app test clean

## Instala o pacote em modo editável + dependências
install:
	pip install -e ".[dev]"

## Roda o pipeline de extração completo (data/raw -> data/processed)
pipeline:
	PYTHONPATH=src python -m kg_extraction.pipeline

## Sobe a aplicação web de visualização (requer `make pipeline` antes)
app:
	PYTHONPATH=src FLASK_APP=kg_extraction.app.app flask run --debug

## Roda a suíte de testes
test:
	PYTHONPATH=src pytest tests/ -v

## Remove artefatos gerados
clean:
	rm -f data/processed/*.csv
	find . -type d -name "__pycache__" -exec rm -rf {} +
