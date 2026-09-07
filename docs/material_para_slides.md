# Material de apoio para os slides de apresentação

> Rascunho de conteúdo organizado em blocos pensados como slides — tópicos
> curtos, não parágrafo, conforme o enunciado pede ("não coloque muito
> texto, utilize apenas tópicos indicativos"; "se vai mostrar código, não
> mostre inteiro, só a parte que se destaca"). Inclui o endereço do
> repositório GitHub em algum slide, como o enunciado também pede.

---

## Bloco 1 — Visão geral (1 slide)

- Extração de **grafo de conhecimento multinível** a partir de casos
  clínicos do **MultiCaRe** (56 casos, 50 artigos PubMed)
- 100% técnicas clássicas de NLP (regex, dicionários, regras) — **zero
  LLM na etapa de extração**, conforme exigido
- Saída: 2 tabelas (nós/arestas), 2 níveis de abstração
  (básico/detalhado), visualização web interativa
- Estrutura de projeto segue o padrão [Cookiecutter Data
  Science](https://drivendata.github.io/cookiecutter-data-science/) —
  organização convencional, não inventada pelo time

---

## Bloco 2 — Pipeline e modelo de relações (1-2 slides)

```
cases.csv → segmentação de frases → NER por gazetteer → valor/unidade → regras de relação → grafo canônico → 2 views
```

O enunciado pede duas coisas que, no nosso grafo, viram **a mesma
resposta**: entidade nomeada (sintoma, doença, exame, tratamento, região
anatômica) e valor/unidade associado a exame ou dosagem. As duas são nó,
estruturalmente iguais — só representam tipo de conteúdo diferente
(rótulo textual vs. número+unidade):

| categoria do enunciado | tipos de nó no grafo |
|---|---|
| Entidades nomeadas | `Symptom`, `Exam`, `Diagnosis`, `Treatment`, `AnatomicalSite`, `History` |
| Valores/unidades associados | `ExamResult`, `Value`, `Unit`, `ReferenceRange` |
| Paciente + vocabulário externo | `Patient`, `OntologyConcept` |

**12 tipos de nó no total, 14 tipos de relação.** Falta 1 das 6 categorias
de entidade que o enunciado sugere — **medicamento** (nome de droga
específico) ainda não tem nó próprio, fica misturado dentro de `Treatment`
genérico. Decisão em aberto, não escondida (ver Bloco 7).

**As 14 relações, agrupadas por função:**

| grupo | relações | o que significam |
|---|---|---|
| Paciente ↔ achado | `PRESENTS_WITH`, `DENIES`, `HAS_HISTORY`, `DIAGNOSED_WITH` | sintoma/diagnóstico presente, negado, ou histórico prévio |
| Investigação | `UNDERWENT_EXAM`, `HAS_RESULT`, `HAS_VALUE`, `HAS_UNIT`, `HAS_REFERENCE_RANGE` | exame → resultado → valor/unidade/faixa decompostos |
| Evidência diagnóstica | `SUPPORTS`, `CONFIRMS`, `EXCLUDES` | achado apoia diagnóstico; exame confirma/exclui |
| Tratamento | `TREATED_BY`, `UNDERWENT_TREATMENT` | tratamento ligado ao diagnóstico (se houver) ou direto ao paciente |
| Modificador | `LOCATED_IN` | região anatômica de qualquer entidade citada na mesma frase |
| Vocabulário externo | `LINKED_TO` | entidade → código SNOMED/LOINC/ICD10/MeSH |

---

## Bloco 3 — Técnicas clássicas, com trecho de código (não o arquivo inteiro)

**Gazetteer — matching por span mais longo, sem sobreposição:**
```python
for pattern, entry in matcher:            # ordenado por nº de palavras, decrescente
    for m in pattern.finditer(sentence):
        if any(occupied[start:end]): continue   # span já reservado, pula
        occupied[start:end] = True              # reserva pro sinônimo mais longo
```

**Regex de valor/unidade:**
```python
rf"(?P<value>\d[\d,\.]*)\s*(?P<unit>{unit_alt})(?!\w)"
```
*(o `(?!\w)` no lugar de `\b` corrigiu um bug real: `%` estava na lista de
unidades desde sempre e nunca funcionava — vale mostrar o antes/depois)*

**Regras de relação — gatilho textual de negação:**
```python
NEGATION_TRIGGER = re.compile(
    r"\b(?:den(?:y|ies|ied|ying)|no evidence of|negative for|...)\b"
    r"|\bno\b(?!\s+(?:longer|one|further))"
)

def classify_symptom_relation(sentence, entity_start):
    if NEGATION_TRIGGER.search(sentence[:entity_start]):
        return "DENIES"
    return "PRESENTS_WITH"
```

**Tokenização/normalização/stopwords/lematização**: testadas, e
**descartadas com justificativa documentada** — não plugamos na frente do
gazetteer/regex porque quebrariam sinônimo multi-palavra com stopword
interna (`"acute on chronic liver failure"`) e a adjacência número+unidade
(`"96mg/dl"`). Bom ponto pra mostrar rigor: entender o impacto de uma
técnica inclui saber por que ela não deveria ser usada aqui.

---

## Bloco 4 — De onde vêm os dicionários, e por quê (1-2 slides)

| gazetteer | fonte | termos |
|---|---|---|
| symptoms.txt | MeSH C23 | 966 |
| exams.txt | MeSH E01 + 8 manuais | 792 |
| diagnoses.txt | MeSH, 12 categorias derivadas de `metadata.csv` | 3844 |
| treatments.txt | MeSH E02+E04 + 9 manuais | 1207 |
| anatomy.txt | MeSH, 14 categorias A | 1399 |
| units.txt | NCI Thesaurus, "Unit of Measure" | 1268 |
| ontology_links.csv | MeSH + SNOMED/LOINC/ICD10 manuais | 8192 |

**Justificativa por entidade** (a lógica de escolha muda por tipo — prova
que não foi arbitrário):

| entidade | por que essa categoria, e não outra |
|---|---|
| **Symptom → C23** | categoria MeSH literalmente "Pathological Conditions, Signs and Symptoms" — correspondência direta |
| **Exam → E01** | "Diagnostic Techniques and Procedures" — mas não cobre analito de lab (CRP, CEA); por isso 8 termos manuais preservados |
| **Treatment → E02+E04** | E02 = terapêutica geral, não cobre cirurgia nomeada ("distal pancreatectomy"); essa vive em E04 |
| **AnatomicalSite → 14 categorias A** | MeSH divide anatomia em ~48 sub-branches por sistema; escolhemos as relevantes pra paciente humano, excluindo Cells/Animal/Plant/Fungal/Bacterial Structures |
| **Diagnosis → 12 categorias C, não a árvore inteira** | **a justificativa mais forte pra slide**: em vez de escolher categorias "que parecem relevantes", extraímos os `mesh_terms` reais que a PubMed atribuiu aos 56 casos, consultamos o tree number de cada um, e usamos só as categorias que de fato apareceram — decisão orientada a dado, não a achismo |
| **units.txt → NCIt, não MeSH** | MeSH é vocabulário de assunto biomédico, não modela unidade de medida; NCIt tem ramo dedicado "Unit of Measure" |

Argumento pro professor: cada fonte foi escolhida com critério mecânico e
verificável — reproduzível por qualquer pessoa que rodar os mesmos
scripts, não uma escolha de "achismo".

---

## Bloco 5 — Descobertas técnicas (auditácia / criatividade)

1. **Bug de paginação real no endpoint SPARQL do MeSH**: limite de 1000
   linhas/resposta + teto de ~10 mil linhas em query com JOIN — corrigido
   paginando em 2 fases (descritores primeiro, entry terms em lotes
   depois)
2. **Filtro "objetivo" que não bastou**: NCIt marca abreviação clínica de
   verdade (`mg/dL`) com a mesma tag de código UCUM interno (`bbl_us`) e
   letra solta de unidade física (`a` = are) — precisou de filtro
   sintático adicional (comprimento, conjunto de caracteres, stopwords)
3. **Bug de 1 caractere invisível por sessões**: `%` estava na lista de
   unidades desde sempre e nunca funcionava — `\b` não fecha depois de
   símbolo não-alfanumérico
4. **Achado quantificado, não teórico**: 132 frases no corpus usam forma
   adjetiva (`abdominal`, `pancreatic`) sem o órgão correspondente ser
   extraído — MeSH não lista adjetivo como sinônimo do substantivo
5. **Negação tratada errado até corrigirmos**: `"denies fever"` virava
   `PRESENTS_WITH` — corrigido com `DENIES`, calibrado contra o corpus
   real (não uma lista genérica de livro-texto)

---

## Bloco 6 — Resultados

**Números do grafo detalhado**, 56 casos:
- 3934 nós / 4214 arestas
- Validação contra indexação da PubMed (`metadata.csv`): 14,3% bruto —
  **investigado e explicado**: parte da "falha" é o pipeline sendo mais
  específico que o padrão-ouro (ex.: extraiu `"gastric duplication cyst"`
  onde o metadata só indexa a categoria geral `"Stomach Diseases"`)
- Pipeline: <1s → ~2min25s conforme os dicionários cresceram (trade-off
  documentado, não descoberto tarde demais)

### Por que 2 níveis (básico/detalhado), pensando no usuário

| nível | usuário-alvo | por que a decomposição certa importa |
|---|---|---|
| **Básico** | médico assistente vendo o caso do *seu* paciente, rápido | não quer navegar `Value`→`Unit` separado pra saber que "lipase = 850 U/L" — quer ler isso num atributo só |
| **Detalhado** | quem estuda o caso a fundo (residente estudando, pesquisador) | precisa que `850` e `U/L` sejam nós navegáveis/consultáveis, e que cada entidade aponte pro código oficial (MeSH/SNOMED) — é trabalho de referência, não leitura corrida |

Ponto forte pro slide: **os dois níveis vêm do mesmo grafo canônico
único**, por agregação/filtragem — não são duas extrações independentes.
Garante consistência entre os níveis, e é o espírito dos dois exemplos
(`example1.md`/`example2.md`) que o próprio enunciado forneceu como
referência de granularidade.

---

## Bloco 7 — Limitações conhecidas (honestidade > perfeição)

- Medicamento como entidade própria: decisão em aberto, não implementada
- Performance do matcher: Aho-Corasick discutido a fundo, não implementado
  ainda — pipeline em ~2min25s
- Forma verbal flexionada (`"biopsied"`, `"resected"`) não capturada —
  precisaria de stemming real, não do stemmer ingênuo que já foi removido
- Desempate de sinônimo por ordem de carregamento no matcher — corrigimos
  1 colisão pontual, mecanismo de fundo continua assim

---

## Lembrete de formatação (do próprio enunciado)

- Explorar diagramas e ilustrações
- Não colocar muito texto — só tópicos indicativos
- Código: nunca mostrar o arquivo inteiro, só o trecho que se destaca
- Incluir o endereço do repositório GitHub da equipe em algum slide
