# Fonte dos dados

Os arquivos em `data/raw/` (`cases.csv`, `metadata.csv`, `data_dictionary.csv`)
são a amostra fixa de 50 artigos do dataset **MultiCaRe** fornecida pela
disciplina, descrita em:

> Nievas Offidani, M., Roffet, F., González Galtier, M. C., Massiris, M., &
> Delrieux, C. (2025). An Open-Source Clinical Case Dataset for Medical Image
> Classification and Multimodal AI Applications. *Data*, 10(8), 123.
> https://doi.org/10.3390/DATA10080123

Ver o enunciado completo do projeto para mais contexto sobre os campos de
cada arquivo.

## ⚠️ Sobre `references/vocabularies/ontology_links.csv`

Essa tabela liga alguns termos canônicos (sintomas, exames, diagnósticos) a
códigos de SNOMED CT, LOINC, ICD-10 e MeSH, para servir de **exemplo de como
plugar vocabulários controlados** no grafo (nível "detalhado").

**Os códigos nela foram digitados manualmente como ilustração da técnica e
cobrem só ~12 termos** — eles não foram verificados contra uma base
terminológica oficial e não devem ser citados como corretos no relatório
sem validação. Antes da entrega final, a equipe deve:

1. Expandir a cobertura de termos (idealmente cruzando os `mesh_terms` que já
   vêm em `metadata.csv` por artigo);
2. Verificar os códigos usados contra uma fonte oficial (ex.: [SNOMED CT
   Browser](https://browser.ihtsdotools.org/), [LOINC](https://loinc.org/),
   tabelas oficiais de ICD-10, ou o [UMLS Metathesaurus](https://www.nlm.nih.gov/research/umls/)).

Isso é exatamente o tipo de "unificação de formas diferentes de escrever um
mesmo conceito" que o enunciado pede — só precisa ser feito com uma fonte
terminológica validada em vez do arquivo-exemplo.
