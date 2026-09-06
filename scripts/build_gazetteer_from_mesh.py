"""Gera um gazetteer (references/vocabularies/*.txt) a partir de uma
categoria REAL do MeSH, em vez de digitar os termos manualmente.

Usa o endpoint SPARQL público da NLM (id.nlm.nih.gov/mesh) — não precisa
baixar o arquivo inteiro do MeSH (que tem dezenas de MB) nem criar
cadastro/API key. Só funciona com acesso normal à internet (não roda
dentro de sandboxes com rede restrita).

Uso:
    pip install requests
    python scripts/build_gazetteer_from_mesh.py --category C23 --out references/vocabularies/symptoms.txt --canonical-type Symptom

    # Várias categorias de uma vez (resultados são unidos): útil quando um
    # tipo de entidade do projeto não cabe numa única árvore do MeSH.
    python scripts/build_gazetteer_from_mesh.py --category E02,E04 --out references/vocabularies/treatments.txt --canonical-type Treatment

    # --keep-manual: preserva termos que já existem no --out (ex.: entradas
    # digitadas à mão que não vêm da árvore do MeSH escolhida, como analitos
    # de laboratório em exams.txt) em vez de sobrescrever o arquivo do zero.
    # Sinônimos novos vindos do MeSH para um termo canônico já manual são
    # somados ao invés de duplicar a linha.
    python scripts/build_gazetteer_from_mesh.py --category E01 --out references/vocabularies/exams.txt --canonical-type Exam --keep-manual

Categorias MeSH úteis pro projeto (primeira letra/número do tree number):
    C23 -> Pathological Conditions, Signs and Symptoms
    E01 -> Diagnostic Techniques and Procedures (~equivalente a "Exam", mas
           não cobre analitos de laboratório como CRP/CEA — esses são
           substâncias, não procedimentos; ficam em outra árvore do MeSH)
    E02 -> Therapeutics (drogas/terapias gerais, ~equivalente a "Treatment")
    E04 -> Surgical Procedures, Operative (cirurgias nomeadas — some ao E02
           pra cobrir "Treatment" por completo, ex.: distal pancreatectomy)
    C   -> Diseases (C01-C26, ~equivalente a "Diagnosis" — MUITO grande,
           dezenas de milhares de descritores; considere um subramo)
    D   -> Chemicals and Drugs (MUITO grande — considere um subramo, ex. D27)
    A01-A10 -> Anatomy (regiões anatômicas)

Como funciona:
    1. Consulta via SPARQL todos os descritores cujo tree number começa
       com o prefixo pedido (ex.: "C23"), junto com seus "entry terms"
       (as variações textuais que a própria MeSH já resolve).
    2. Agrupa por descritor: label oficial = termo canônico; entry terms
       = sinônimos.
    3. Escreve no formato canonico | sinonimo1 | sinonimo2 | ...
       (mesmo formato que gazetteer_ner.py já sabe ler).
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict

import requests

SPARQL_ENDPOINT = "https://id.nlm.nih.gov/mesh/sparql"

SPARQL_PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
PREFIX mesh: <http://id.nlm.nih.gov/mesh/>
"""

# Fase 1: só os descritores (sem entry terms) de uma categoria. Uma
# categoria como C23 tem ~1000 descritores — poucas linhas por resposta.
DESCRIPTOR_QUERY_TEMPLATE = SPARQL_PREFIXES + """
SELECT DISTINCT ?descriptor ?label
FROM <http://id.nlm.nih.gov/mesh>
WHERE {{
  ?descriptor meshv:treeNumber ?treeNum .
  FILTER(STRSTARTS(STR(?treeNum), "http://id.nlm.nih.gov/mesh/{prefix}"))
  ?descriptor rdfs:label ?label .
}}
ORDER BY ?label
"""

# Fase 2: entry terms (sinônimos) só para um LOTE de descritores por vez
# (via VALUES), não para a categoria inteira de uma vez.
ENTRY_TERM_QUERY_TEMPLATE = SPARQL_PREFIXES + """
SELECT ?label ?entryTerm
FROM <http://id.nlm.nih.gov/mesh>
WHERE {{
  VALUES ?descriptor {{ {descriptor_iris} }}
  ?descriptor rdfs:label ?label .
  ?descriptor meshv:concept ?concept .
  ?concept meshv:term ?term .
  ?term rdfs:label ?entryTerm .
}}
"""

# Diagnóstico (rodando contra o endpoint real, ver histórico no PR/commit):
# o /mesh/sparql responde certinho em JSON (o parsing abaixo já esperava
# results.bindings[].{label,entryTerm}.value, e isso está correto) — o
# JSONDecodeError não era de formato, e sim de PAGINAÇÃO:
#   1. Cada resposta é limitada a no máximo 1000 linhas, mesmo pedindo mais.
#   2. Uma query que já faz o JOIN descriptor->concept->term e pagina com
#      offset/limit "achatado" para de retornar dados depois de ~10000
#      linhas no total (o offset seguinte volta corpo VAZIO — nem JSON
#      vazio válido, corpo mesmo vazio, daí o "Expecting value: char 0").
#      Numa categoria grande (C23 tem 966 descritores, bem mais de 10000
#      pares descriptor/entryTerm no total) isso trunca dados de verdade:
#      faltavam todos os descritores a partir de "Sweating Sickness" em
#      diante (confirmado comparando com a lista completa de descritores).
# A correção é paginar em duas fases: (1) buscar só os descritores da
# categoria — poucas centenas/milhares de linhas, cabe numa resposta ou
# poucas páginas; (2) buscar entry terms em LOTES pequenos de descritores
# (via VALUES), o que mantém cada resposta bem abaixo do limite de 1000
# linhas e nunca esbarra no teto de ~10000 linhas totais.


def _get_json(params: dict, max_retries: int = 3) -> dict:
    """GET no endpoint SPARQL com retry: o endpoint às vezes responde
    HTTP 200 com corpo vazio (não é JSON vazio válido, é vazio mesmo) sob
    carga, em vez de um erro — tratamos isso como falha transitória.
    """
    last_error: Exception | None = None
    for attempt in range(max_retries):
        resp = requests.get(SPARQL_ENDPOINT, params=params, timeout=120)
        if not resp.ok:
            print("--- Resposta de erro da NLM (corpo completo) ---", file=sys.stderr)
            print(resp.text[:3000], file=sys.stderr)
            print("--- Content-Type ---", file=sys.stderr)
            print(resp.headers.get("content-type"), file=sys.stderr)
            print("--- URL efetivamente chamada ---", file=sys.stderr)
            print(resp.url, file=sys.stderr)
            resp.raise_for_status()
        if not resp.text.strip():
            last_error = RuntimeError("corpo de resposta vazio (provável throttling do endpoint)")
            time.sleep(2 * (attempt + 1))
            continue
        try:
            return resp.json()
        except requests.exceptions.JSONDecodeError as exc:
            last_error = exc
            print("--- Corpo de resposta que falhou ao parsear como JSON ---", file=sys.stderr)
            print(f"Content-Type: {resp.headers.get('content-type')}", file=sys.stderr)
            print(resp.text[:3000], file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    assert last_error is not None
    raise last_error


def _fetch_descriptors(tree_prefix: str, page_size: int = 1000) -> list[tuple[str, str]]:
    """Retorna [(descriptor_iri, label), ...] para a categoria (fase 1)."""
    query = DESCRIPTOR_QUERY_TEMPLATE.format(prefix=tree_prefix)
    descriptors: list[tuple[str, str]] = []
    offset = 0
    while True:
        params = {
            "query": query,
            "format": "JSON",
            "inference": "true",
            "year": "current",
            "limit": str(page_size),
            "offset": str(offset),
        }
        data = _get_json(params)
        rows = data["results"]["bindings"]
        print(f"  descritores: {len(rows)} linhas (offset={offset})")
        for row in rows:
            label = row["label"]["value"]
            if label.strip().lower().startswith("[obsolete]"):
                # Descritor depreciado que a NLM mantém por compatibilidade:
                # seus entry terms já pertencem ao descritor ativo que o
                # substituiu (ex.: "[Obsolete] Intensive Care" tem "intensive
                # care" como sinônimo, e "Critical Care" — o descritor atual
                # — já tem esse mesmo sinônimo). Incluir os dois criaria dois
                # termos canônicos concorrendo pelo mesmo texto de entrada.
                continue
            descriptors.append((row["descriptor"]["value"], label))
        if len(rows) < page_size:
            break
        offset += page_size
        time.sleep(0.5)
    return descriptors


def fetch_mesh_terms(tree_prefix: str, batch_size: int = 50, page_size: int = 1000) -> dict[str, set[str]]:
    """Retorna {termo_canonico: {sinonimo1, sinonimo2, ...}} para uma
    categoria MeSH (prefixo de tree number, ex.: 'C23').

    Duas fases (ver comentário acima do motivo): busca a lista de
    descritores da categoria e depois busca entry terms em pequenos
    lotes de descritores por vez, paginando dentro de cada lote se
    necessário.
    """
    terms: dict[str, set[str]] = defaultdict(set)

    descriptors = _fetch_descriptors(tree_prefix, page_size=page_size)
    print(f"  {len(descriptors)} descritores encontrados na categoria '{tree_prefix}'")

    for batch_start in range(0, len(descriptors), batch_size):
        batch = descriptors[batch_start:batch_start + batch_size]
        descriptor_iris = " ".join(f"<{iri}>" for iri, _label in batch)
        query = ENTRY_TERM_QUERY_TEMPLATE.format(descriptor_iris=descriptor_iris)

        offset = 0
        while True:
            params = {
                "query": query,
                "format": "JSON",
                "inference": "true",
                "year": "current",
                "limit": str(page_size),
                "offset": str(offset),
            }
            data = _get_json(params)
            rows = data["results"]["bindings"]
            for row in rows:
                label = row["label"]["value"].strip().lower()
                entry_term = row["entryTerm"]["value"].strip().lower()
                terms[label].add(entry_term)
                terms[label].add(label)
            if len(rows) < page_size:
                break  # lote inteiro veio numa página só (o caso comum)
            offset += page_size  # lote raro grande demais: pagina dentro dele
            time.sleep(0.5)

        done = min(batch_start + batch_size, len(descriptors))
        print(f"  entry terms: {done}/{len(descriptors)} descritores processados")
        time.sleep(0.5)

    return terms


def load_existing_gazetteer(path: str) -> dict[str, set[str]]:
    """Lê um gazetteer já existente no formato canonico | syn1 | syn2 | ...
    (mesmo parser de gazetteer_ner.load_gazetteer_file, sem depender do
    pacote kg_extraction pra manter este script standalone). Usado só com
    --keep-manual, pra não perder termos digitados à mão ao regerar."""
    terms: dict[str, set[str]] = defaultdict(set)
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip().lower() for p in line.split("|")]
                canonical, synonyms = parts[0], parts[1:] or [parts[0]]
                terms[canonical].update(synonyms)
                terms[canonical].add(canonical)
    except FileNotFoundError:
        pass
    return terms


def write_gazetteer(terms: dict[str, set[str]], out_path: str, header_comment: str):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# {header_comment}\n")
        f.write("# Gerado automaticamente por scripts/build_gazetteer_from_mesh.py — NÃO editar à mão.\n")
        f.write("# Para adicionar termos manuais, rode de novo com --keep-manual.\n")
        for canonical in sorted(terms):
            synonyms = sorted(terms[canonical])
            f.write(f"{canonical} | " + " | ".join(synonyms) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--category", required=True, help="Prefixo(s) do tree number MeSH, separados por vírgula, ex.: C23 ou E02,E04")
    parser.add_argument("--out", required=True, help="Caminho do .txt de saída")
    parser.add_argument("--canonical-type", default="Entity", help="Só usado no comentário de cabeçalho do arquivo")
    parser.add_argument(
        "--keep-manual",
        action="store_true",
        help="Preserva termos já existentes em --out que não vieram do MeSH (soma sinônimos em vez de sobrescrever).",
    )
    args = parser.parse_args()

    categories = [c.strip() for c in args.category.split(",") if c.strip()]
    terms: dict[str, set[str]] = defaultdict(set)
    for category in categories:
        print(f"Consultando MeSH SPARQL para a categoria '{category}'...")
        category_terms = fetch_mesh_terms(category)
        for canonical, synonyms in category_terms.items():
            terms[canonical].update(synonyms)

    if not terms:
        print(f"Nenhum termo encontrado para o(s) prefixo(s) '{args.category}'. Verifique o(s) código(s) da categoria.", file=sys.stderr)
        sys.exit(1)

    mesh_canonical_count = len(terms)
    if args.keep_manual:
        existing = load_existing_gazetteer(args.out)
        added_manual = 0
        for canonical, synonyms in existing.items():
            if canonical not in terms:
                added_manual += 1
            terms[canonical].update(synonyms)
        print(f"  --keep-manual: {added_manual} termo(s) manual(is) preservado(s) de {args.out}")

    write_gazetteer(
        terms,
        args.out,
        header_comment=f"Gazetteer de {args.canonical_type} — extraído do MeSH, categoria(s) {args.category}"
        + (" + termos manuais preservados" if args.keep_manual else ""),
    )
    total_synonyms = sum(len(v) for v in terms.values())
    print(f"{mesh_canonical_count} termos canônicos do MeSH, {len(terms)} termos canônicos no total, {total_synonyms} sinônimos no total -> {args.out}")


if __name__ == "__main__":
    main()
