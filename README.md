# Projeto `Projeto 1 - Grafos de Conhecimento Multinível para Casos Clínicos`
# Project `Project 1 - Multilevel Knowledge Graphs for Clinical Cases`

> Equipe: `Gabriela Coppo`, `João Rafael`

## Slides

> Coloque aqui o link para o PDF da apresentação (pasta `assets/slides/`).

## Metodologia

O grafo de conhecimento é extraído em um pipeline de 6 estágios, todos
baseados em técnicas clássicas de NLP (nenhum modelo de linguagem é usado
nesta etapa):

```
cases.csv ──▶ segmentação de ──▶ NER por gazetteer ──▶ extração de   ──▶ regras de   ──▶ grafo canônico ──▶ 2 views por
              frases (regex)     (dicionários de       valores/unidades   relação        (nós + arestas)    abstração
                                  sintomas, exames,     (regex + lista     (histórico vs.                    (básico/
                                  diagnósticos,         de unidades)       diagnóstico,                       detalhado)
                                  tratamentos,                             DENIES, SUPPORTS,
                                  regiões anatômicas)                      TREATED_BY, ...)
```

Nota sobre técnicas clássicas exploradas e descartadas: chegamos a implementar
tokenização de palavras, normalização e um stemmer ingênuo (histórico em
`src/kg_extraction/features/preprocessing.py`), mas eles nunca entraram no
caminho de extração — testamos plugá-los na frente do NER por gazetteer e do
regex de valor/unidade, e ambos quebrariam: sinônimos multi-palavra com
stopword interna (ex.: `"acute on chronic liver failure"`) e a adjacência
número+unidade (`"96mg/dl"`) que o regex depende. Removemos o código morto em
vez de deixá-lo desconectado do pipeline.

Pontos-chave da abordagem:

- **NER baseada em dicionários (gazetteers)**: `references/vocabularies/*.txt` — cada
  termo canônico lista seus sinônimos textuais, resolvendo a unificação de
  diferentes formas de escrever o mesmo conceito.
- **Extração de valores/unidades por regex**: construída dinamicamente a
  partir de uma lista controlada de unidades (`units.txt`), reconhecendo
  também faixas de referência (`reference range X-Y`).
- **Relações por regras**: co-ocorrência na mesma sentença + expressões-gatilho
  (ex.: `"history of"` classifica um diagnóstico como histórico prévio em vez
  de diagnóstico do caso atual) + proximidade sequencial (o tratamento mais
  próximo de um diagnóstico recebe a aresta `TREATED_BY`).
- **Um único grafo canônico por caso**, decomposto no estilo do `example2.md`
  do enunciado (valor, unidade e faixa de referência viram nós próprios,
  entidades ligadas a vocabulários controlados). As 3 visualizações de nível
  de abstração são **derivadas** deste grafo único por agregação/filtragem —
  não são três extrações independentes — o que garante consistência entre
  elas.

Trecho de código ilustrando a extração de valor+unidade por regex:

~~~python
def build_value_unit_pattern(units: list[str]) -> re.Pattern:
    unit_alt = "|".join(re.escape(u) for u in units)
    return re.compile(rf"(?P<value>\d[\d,\.]*)\s*(?P<unit>{unit_alt})\b", re.IGNORECASE)
~~~

Código completo em [`src/kg_extraction/`](src/kg_extraction/) ([instruções de instalação/execução](src/README.md)).

## Trabalhos Estudados

> Debater brevemente outros trabalhos/abordagens pesquisados pela equipe
> (ex.: outras extrações de KG a partir de casos clínicos, uso de UMLS/cTAKES/
> MetaMap para linking terminológico, etc.).

## Modelo Lógico

O grafo é representado em duas tabelas (esquema livre, mantendo a ideia de
nós + arestas do enunciado):

**Nós** (`node_id`, `case_id`, `type`, `label`, `attributes`) — tipos usados:
`Patient`, `History`, `Symptom`, `Exam`, `ExamResult`, `Value`, `Unit`,
`ReferenceRange`, `Diagnosis`, `Treatment`, `AnatomicalSite`, `OntologyConcept`.

**Arestas** (`edge_id`, `case_id`, `source_id`, `target_id`, `relation`,
`attributes`) — relações usadas: `HAS_HISTORY`, `PRESENTS_WITH`, `DENIES`
(sintoma/diagnóstico negado — "denies fever", "no evidence of jaundice",
"ruled out X" — em vez de tratar a negação como se o achado fosse real),
`UNDERWENT_EXAM`, `HAS_RESULT`, `HAS_VALUE`, `HAS_UNIT`,
`HAS_REFERENCE_RANGE`, `DIAGNOSED_WITH`, `SUPPORTS`, `LOCATED_IN` (região
anatômica de um Symptom/Exam/Diagnosis/Treatment citado na mesma frase),
`TREATED_BY`, `UNDERWENT_TREATMENT`, `CONFIRMS`/`EXCLUDES`, `LINKED_TO`
(para vocabulários controlados).

> Coloque aqui a imagem do modelo lógico de propriedades da equipe (ver
> [modelo de base](https://docs.google.com/presentation/d/10RN7bDKUka_Ro2_41WyEE76Wxm4AioiJOrsh6BRY3Kk/edit?usp=sharing)),
> em `assets/images/modelo-logico-grafos.png`.

## Análises que podem ser realizadas

- Comparar, por caso, a "densidade" do grafo detalhado vs. básico como proxy
  de complexidade clínica.
- ~~Cruzar `major_mesh_terms` de `metadata.csv` com os `Diagnosis`
  extraídos para validar a qualidade da extração contra uma anotação
  externa.~~ **Feito** — ver `scripts/validate_against_metadata.py` e a
  seção Resultados acima.
- Identificar quais `Exam` mais frequentemente co-ocorrem (via `SUPPORTS`)
  com cada `Diagnosis`, sugerindo protocolos diagnósticos recorrentes.
- Medir cobertura do gazetteer (quantas sentenças não geraram nenhuma
  entidade) para orientar onde expandir os dicionários.

> Complementar com as demais análises efetivamente realizadas pela equipe.

## Ferramentas

- **Python** (pandas) para o pipeline de extração.
- Técnicas clássicas de NLP implementadas from-scratch (segmentação de frases
  por regex, gazetteers, regex de valores/unidades, regras de relação) —
  sem bibliotecas de NER estatístico/neural, conforme exigido nesta etapa.
- **Flask** + **Cytoscape.js** para a visualização web interativa multinível.
- Estrutura de projeto: [Cookiecutter Data Science](https://drivendata.github.io/cookiecutter-data-science/).

## Resultados

Números do grafo canônico (nível detalhado) rodando `make pipeline` sobre
os 56 casos da amostra:

**Nós — 3934 no total**

| tipo | nº | | tipo | nº |
|---|---|---|---|---|
| OntologyConcept | 1281 | | Treatment | 180 |
| AnatomicalSite | 429 | | Diagnosis | 157 |
| ExamResult | 415 | | Patient | 56 |
| Value | 415 | | History | 19 |
| Unit | 415 | | | |
| Exam | 285 | | | |
| Symptom | 282 | | | |

**Arestas — 4214 no total**

| relação | nº | | relação | nº |
|---|---|---|---|---|
| LINKED_TO | 1281 | | DENIES | 118 |
| LOCATED_IN | 627 | | DIAGNOSED_WITH | 118 |
| HAS_RESULT/HAS_VALUE/HAS_UNIT | 415 cada | | SUPPORTS | 93 |
| UNDERWENT_EXAM | 285 | | UNDERWENT_TREATMENT | 62 |
| PRESENTS_WITH | 221 | | HAS_HISTORY | 19 |
| TREATED_BY | 139 | | CONFIRMS | 6 |

### Validação contra anotação externa (`scripts/validate_against_metadata.py`)

Cruzamos os `Diagnosis` extraídos com os `mesh_terms`/`major_mesh_terms`
que a própria PubMed atribuiu a cada artigo (metadata.csv) — a análise que
esta seção já pedia. Resultado salvo em
`data/processed/validation_against_metadata.csv` (todos os 56 casos, não
só os validáveis, para ficar transparente qual fração do dataset dá pra
comparar dessa forma):

- **56 casos no total**: 0 sem artigo correspondente em `metadata.csv`,
  **50 com metadata mas sem nenhum termo de doença listado no
  `mesh_terms`** (a indexação da PubMed é rala — a maioria dos artigos só
  tem check-tags como "Case Reports"/"Humans", sem termo de doença
  específico), **6 validáveis**.
- Nesses 6 casos: **2 de 14** termos de doença indexados pela PubMed
  também foram extraídos pelo pipeline (14,3%). Investigamos os dois
  motivos principais desse número baixo (não é simplesmente "o gazetteer
  falhou"):
  1. **A indexação reflete o artigo inteiro, não só o `case_text`.** Ex.:
     `PMC9387390_01` é indexado com "Gastric Outlet Obstruction", mas essa
     frase não aparece em lugar nenhum do trecho de caso que temos — o
     texto só descreve o achado clínico (*"causing extrinsic narrowing of
     the second portion of the duodenum"*) que levaria a esse diagnóstico,
     provavelmente concluído no abstract/discussão do artigo completo.
  2. **A PubMed indexa pela categoria geral da árvore MeSH; nosso pipeline
     acerta o diagnóstico específico.** Ex.: `PMC5137649_01` é indexado com
     "Stomach Diseases" (categoria pai), mas o pipeline extraiu
     corretamente `"gastric duplication cyst"` — o diagnóstico específico
     do caso, que é filho de "Stomach Diseases" na árvore do MeSH. Uma
     comparação por string exata conta isso como falha, quando na
     realidade a extração foi mais precisa que o rótulo de indexação.

Conclusão: o número bruto (14,3%) **subestima** a qualidade real da
extração — parte das "falhas" é o pipeline sendo mais específico que o
padrão-ouro, não menos capaz. Ainda assim, o primeiro motivo (indexação
baseada no artigo completo) é uma limitação real e esperada: nossa
extração só vê o trecho de `case_text`, não o artigo completo.

> Falta: exemplos visuais de grafos bem-sucedidos/mal-sucedidos e capturas
> de tela da aplicação web nos 2 níveis de abstração (colocar em
> `assets/images/`).

## Como Modelos de Linguagem foram Usados

Conforme o enunciado, **nenhum LLM foi usado na etapa de extração do grafo**
(NER, extração de valores e extração de relações são 100% baseadas em regras,
dicionários e regex — ver `src/kg_extraction/features/`).

Modelos de linguagem foram usados apenas para:
- Apoiar o design e a implementação da **aplicação web de visualização**
  (Flask + Cytoscape.js), que o enunciado explicitamente libera para uso
  de IA;
- `<a equipe deve completar aqui outros usos, ex.: revisão de texto, geração
  de rascunho dos slides, etc.>`

## Referências Bibliográficas

- Nievas Offidani, M., Roffet, F., González Galtier, M. C., Massiris, M., &
  Delrieux, C. (2025). An Open-Source Clinical Case Dataset for Medical Image
  Classification and Multimodal AI Applications. *Data*, 10(8), 123.
  https://doi.org/10.3390/DATA10080123
- Ji, S., Pan, S., Cambria, E., Marttinen, P., & Yu, P. S. (2022). A Survey on
  Knowledge Graphs: Representation, Acquisition, and Applications. *IEEE
  Transactions on Neural Networks and Learning Systems*, 33(2), 494–514.
  https://doi.org/10.1109/TNNLS.2021.3070843
- `<demais referências da equipe>`
