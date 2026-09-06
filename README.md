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
cases.csv ──▶ pré-processamento ──▶ NER por gazetteer ──▶ extração de   ──▶ regras de   ──▶ grafo canônico ──▶ 3 views por
              (tokenização,          (dicionários de       valores/unidades   relação        (nós + arestas)    abstração
              normalização,          sintomas, exames,     (regex + lista     (histórico vs.                    (básico/
              stop-words)            diagnósticos,         de unidades)       diagnóstico,                       intermediário/
                                     tratamentos)                             SUPPORTS,                          detalhado)
                                                                              TREATED_BY, ...)
```

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
`ReferenceRange`, `Diagnosis`, `Treatment`, `OntologyConcept`.

**Arestas** (`edge_id`, `case_id`, `source_id`, `target_id`, `relation`,
`attributes`) — relações usadas: `HAS_HISTORY`, `PRESENTS_WITH`,
`UNDERWENT_EXAM`, `HAS_RESULT`, `HAS_VALUE`, `HAS_UNIT`,
`HAS_REFERENCE_RANGE`, `DIAGNOSED_WITH`, `SUPPORTS`, `TREATED_BY`,
`UNDERWENT_TREATMENT`, `CONFIRMS`/`EXCLUDES`, `LINKED_TO` (para vocabulários
controlados).

> Coloque aqui a imagem do modelo lógico de propriedades da equipe (ver
> [modelo de base](https://docs.google.com/presentation/d/10RN7bDKUka_Ro2_41WyEE76Wxm4AioiJOrsh6BRY3Kk/edit?usp=sharing)),
> em `assets/images/modelo-logico-grafos.png`.

## Análises que podem ser realizadas

- Comparar, por caso, a "densidade" do grafo detalhado vs. básico como proxy
  de complexidade clínica.
- Cruzar `major_mesh_terms` de `metadata.csv` com os `Diagnosis` extraídos
  para validar a qualidade da extração contra uma anotação externa.
- Identificar quais `Exam` mais frequentemente co-ocorrem (via `SUPPORTS`)
  com cada `Diagnosis`, sugerindo protocolos diagnósticos recorrentes.
- Medir cobertura do gazetteer (quantas sentenças não geraram nenhuma
  entidade) para orientar onde expandir os dicionários.

> Complementar com as análises efetivamente realizadas pela equipe.

## Ferramentas

- **Python** (pandas) para o pipeline de extração.
- Técnicas clássicas de NLP implementadas from-scratch (tokenização/normalização
  por regex, gazetteers, regex de valores/unidades, regras de relação) —
  sem bibliotecas de NER estatístico/neural, conforme exigido nesta etapa.
- **Flask** + **Cytoscape.js** para a visualização web interativa multinível.
- Estrutura de projeto: [Cookiecutter Data Science](https://drivendata.github.io/cookiecutter-data-science/).

## Resultados

> Descrever e discutir os resultados após rodar o pipeline completo
> (`make pipeline`) sobre os 56 casos da amostra: nº de nós/arestas por
> tipo, exemplos de grafos considerados bem-sucedidos e mal-sucedidos,
> limitações observadas do gazetteer/regex.
>
> Incluir capturas de tela da aplicação web nos 3 níveis de abstração
> (colocar as imagens em `assets/images/`).

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
