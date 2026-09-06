"""Gera references/vocabularies/units.txt a partir do NCI Thesaurus (NCIt),
em vez de digitar/curar as unidades manualmente lendo os casos.

Por que NCIt e não MeSH: o MeSH (usado em build_gazetteer_from_mesh.py) não
modela unidades de medida como conceitos — é um vocabulário de assunto
biomédico, não uma ontologia de grandezas/unidades. O NCIt tem um ramo
dedicado, "Unit of Measure" (C25709), com sub-branches por categoria física
(Concentration, Mass, Volume, Pressure, Time, ...) e cada conceito já vem
com sinônimos reais classificados por tipo (`termType`), incluindo `AB`
(abreviação oficial) — ex.: o conceito "Milligram per Deciliter" tem "mg/dL"
como sinônimo AB, vindo das fontes HL7/UCUM/CDISC/NCI. Isso deixa a extração
tão "clássica" (dicionário controlado + regra determinística) quanto a do
MeSH: nenhuma unidade entra no arquivo por eu ter lido os casos e achado que
"parecia" uma unidade — só entra o que o NCIt já classifica formalmente
como abreviação de uma unidade.

Uso:
    pip install requests
    python scripts/build_units_from_ncit.py --out references/vocabularies/units.txt

    # escolher outras sub-branches (default: conjunto clínico abaixo)
    python scripts/build_units_from_ncit.py --branch C48207 --branch C44279 --out references/vocabularies/units.txt

Sub-branches de "Unit by Category" (C42568) usadas por default — escolhidas
pelo nome oficial da categoria no NCIt (mesmo critério taxonômico usado
pra escolher C23/E01/E02/E04 no MeSH, não por leitura dos casos):
    C48207 Unit of Concentration
    C48463 Unit of Biological and Biochemical Measurement
    C42579 Unit of Mass
    C48208 Unit of Weight
    C44279 Unit of Volume
    C42578 Unit of Length
    C49669 Unit of Pressure
    C42574 Unit of Time
    C67313 Unit of Frequency
    C44276 Unit of Temperature
    C48574 Unit of Fraction
    C48567 Unit of Flow Rate
    C66973 Unit of Dose Calculation
    C48470 Potency Unit

Como funciona:
    1. Busca todos os descendentes (subárvore inteira) de cada branch via
       GET /concept/ncit/{code}/descendants — endpoint da NCI EVS REST API,
       pública, sem cadastro/API key (mesmo espírito do SPARQL do MeSH).
    2. Busca os sinônimos de cada conceito em lotes (endpoint
       /concept/ncit?list=cod1,cod2,...&include=synonyms — equivalente ao
       VALUES do SPARQL usado no script do MeSH).
    3. De cada conceito, mantém só os sinônimos com termType == "AB"
       (abreviação oficial) — critério formal do próprio NCIt, não uma
       escolha nossa. Isso sozinho não basta: a mesma tag também marca
       códigos UCUM em sintaxe de máquina ("a_g", "dr_ap") e letras soltas
       de unidades físicas formais ("a" = are, "c" = coulomb); um filtro
       sintático adicional (comprimento >= 2, só caracteres alfanuméricos/
       %/°/-/. /) descarta esses casos sem depender de leitura caso a caso.
    4. Escreve uma unidade por linha (mesmo formato "flat" que
       value_unit_extraction.load_units já lê hoje — o arquivo não tem
       distinção canônico/sinônimo porque o código também não usa isso
       pra unidades: o texto casado vira o rótulo do nó Unit direto).
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import requests

# Reaproveita a lista de stop-words que o projeto já usa em
# preprocessing.py (mesma técnica clássica, mesmo recurso — não uma lista
# nova inventada só pra unidades). Import por caminho de arquivo pra manter
# este script standalone (sem exigir `pip install -e .`/PYTHONPATH=src).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from kg_extraction.features.preprocessing import STOPWORDS  # noqa: E402

NCIT_API_BASE = "https://api-evsrest.nci.nih.gov/api/v1"

# "am"/"pm" aparecem como abreviação (AB) de conceitos do NCIt, mas
# denotam notação de hora do dia (antes/depois do meio-dia), não uma
# unidade de grandeza — categoria diferente do que este arquivo modela,
# então a exclusão é por definição do conceito, não por leitura dos casos.
_NOT_A_MEASUREMENT_UNIT = {"am", "pm"}

# Sinônimos com termType == "AB" no NCIt não são só abreviações clínicas
# (ex.: "mg/dL"): a mesma tag também marca códigos internos UCUM em sintaxe
# de máquina (ex.: "a_g", "dr_ap", "bbl_us") e letras soltas de unidades
# físicas formais (ex.: "a" = are, "c" = coulomb, "d" = day, "f" = farad).
# Como token de regex sobre texto corrido, uma letra alfanumérica sozinha
# ou um código com "_"/"'"/"^"/"*"/chaves nunca é uma unidade segura de se
# casar — combina com estadiamento ("grade 2c"), rótulo de figura ("3D")
# etc. Já um símbolo sozinho que não é letra/dígito (ex.: "%") não tem essa
# ambiguidade. Este filtro é sintático (conjunto de caracteres e se o token
# de 1 caractere é alfanumérico), não uma escolha nossa sobre qual unidade
# "parece" relevante pro corpus.
_VALID_ABBREV = re.compile(r"^[a-z0-9%/.\-°]+$")


def _is_safe_abbreviation(name: str) -> bool:
    if not _VALID_ABBREV.match(name):
        return False
    if len(name) == 1 and name.isalnum():
        return False
    if name in STOPWORDS or name in _NOT_A_MEASUREMENT_UNIT:
        return False
    return True

DEFAULT_BRANCHES = {
    "C48207": "Unit of Concentration",
    "C48463": "Unit of Biological and Biochemical Measurement",
    "C42579": "Unit of Mass",
    "C48208": "Unit of Weight",
    "C44279": "Unit of Volume",
    "C42578": "Unit of Length",
    "C49669": "Unit of Pressure",
    "C42574": "Unit of Time",
    "C67313": "Unit of Frequency",
    "C44276": "Unit of Temperature",
    "C48574": "Unit of Fraction",
    "C48567": "Unit of Flow Rate",
    "C66973": "Unit of Dose Calculation",
    "C48470": "Potency Unit",
}


def _get_json(url: str, params: dict | None = None, max_retries: int = 3):
    last_error: Exception | None = None
    for attempt in range(max_retries):
        resp = requests.get(url, params=params, timeout=120)
        if resp.ok:
            try:
                return resp.json()
            except requests.exceptions.JSONDecodeError as exc:
                last_error = exc
        else:
            print(f"--- erro HTTP {resp.status_code} em {resp.url} ---", file=sys.stderr)
            print(resp.text[:2000], file=sys.stderr)
            last_error = requests.exceptions.HTTPError(f"HTTP {resp.status_code}")
        time.sleep(2 * (attempt + 1))
    assert last_error is not None
    raise last_error


def fetch_branch_descendants(branch_code: str) -> list[str]:
    """Retorna os codes de todos os conceitos da subárvore (o próprio branch
    não vem incluído, só os descendentes — igual /descendants da EVS API)."""
    data = _get_json(f"{NCIT_API_BASE}/concept/ncit/{branch_code}/descendants")
    return [row["code"] for row in data]


def fetch_synonym_abbreviations(codes: list[str], batch_size: int = 300) -> dict[str, set[str]]:
    """Retorna {code: {abreviacao1, abreviacao2, ...}} usando só sinônimos
    com termType == 'AB' (abreviação oficial, campo do próprio NCIt)."""
    result: dict[str, set[str]] = {}
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        concepts = _get_json(
            f"{NCIT_API_BASE}/concept/ncit",
            params={"list": ",".join(batch), "include": "synonyms"},
        )
        for concept in concepts:
            abbrevs = set()
            for syn in concept.get("synonyms", []):
                if syn.get("termType") != "AB":
                    continue
                name = syn["name"].strip().lower()
                if not _is_safe_abbreviation(name):
                    continue  # ver comentário de _VALID_ABBREV: letra solta ou código UCUM em sintaxe de máquina
                abbrevs.add(name)
            if abbrevs:
                result[concept["code"]] = abbrevs
        done = min(i + batch_size, len(codes))
        print(f"  sinônimos: {done}/{len(codes)} conceitos processados")
        time.sleep(0.3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, help="Caminho do .txt de saída")
    parser.add_argument(
        "--branch",
        action="append",
        dest="branches",
        help="Code de sub-branch do NCIt sob 'Unit by Category' (C42568). Pode repetir. Default: conjunto clínico documentado no topo do arquivo.",
    )
    args = parser.parse_args()

    branches = args.branches or list(DEFAULT_BRANCHES.keys())

    all_codes: set[str] = set()
    for branch in branches:
        label = DEFAULT_BRANCHES.get(branch, branch)
        print(f"Buscando descendentes de '{label}' ({branch})...")
        codes = fetch_branch_descendants(branch)
        print(f"  {len(codes)} conceitos")
        all_codes.update(codes)

    all_codes_list = sorted(all_codes)
    print(f"\n{len(all_codes_list)} conceitos únicos no total (após deduplicar entre branches).")
    print("Buscando sinônimos (abreviações) de cada conceito...")
    abbrevs_by_code = fetch_synonym_abbreviations(all_codes_list)

    units: set[str] = set()
    for abbrevs in abbrevs_by_code.values():
        units.update(abbrevs)

    if not units:
        print("Nenhuma unidade encontrada. Verifique os codes de branch.", file=sys.stderr)
        sys.exit(1)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("# Unidades de medida reconhecidas na extração de valores numéricos (value_unit_extraction.py).\n")
        f.write("# Gerado automaticamente por scripts/build_units_from_ncit.py — NÃO editar à mão.\n")
        f.write("# Fonte: NCI Thesaurus (NCIt), ramo 'Unit of Measure' (C25709), sinônimos com termType=AB.\n")
        f.write(f"# Branches usadas: {', '.join(sorted(branches))}\n")
        f.write("# Uma unidade por linha. Ordem não importa (o regex ordena por tamanho para casar o mais específico primeiro).\n")
        for unit in sorted(units):
            f.write(f"{unit}\n")

    concepts_with_abbrev = len(abbrevs_by_code)
    print(f"\n{concepts_with_abbrev}/{len(all_codes_list)} conceitos tinham ao menos uma abreviação.")
    print(f"{len(units)} unidades únicas -> {args.out}")


if __name__ == "__main__":
    main()
