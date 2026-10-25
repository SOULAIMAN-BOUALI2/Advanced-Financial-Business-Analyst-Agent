# LLMOps evaluation report

Questions evaluated: 33 (13 database, 15 documents, 5 must-refuse). Judge model: `gemini-3.1-flash-lite`.

## Summary

| Measure | Result |
|---|---|
| Database questions answered correctly (execution accuracy) | 11/13 |
| Questions the copilot correctly refused (no hallucination) | 4/5 |
| Router chose the expected source | 26/28 |
| Retrieval: the retrieved text contains the fact needed to answer | 14/15 |
| Retrieval: the expected report page is among the retrieved chunks (strict) | 14/15 |
| Ragas faithfulness | n/a |
| Ragas answer relevancy | n/a |
| Ragas context precision | n/a |
| Ragas context recall | n/a |
| Average response time | 11.8 s |

## Failures

- **sql-01** (sql): Quel est le chiffre d'affaires total ?
  - route `rag`; answer: "D'après les documents fournis, le chiffre d'affaires total varie selon les périodes et les rapports :\n\n* **Au 31 décembre 2023** : Le chiffre d'affaires total est de **8 212 021 milliers de Dirhams** "
  - the agent produced no SQL
- **sql-11** (sql): Quel est le chiffre d'affaires par année ?
  - route `rag`; answer: "Sur la base des documents fournis, le chiffre d'affaires par année (en milliers de dirhams) est le suivant :\n\n* **Exercice clos au 31 décembre 2025 :** 8 936 255 milliers de dirhams [annual_report_202"
  - the agent produced no SQL
- **abs-03** (abstain): Quel est le cours de l'action Holcim aujourd'hui ?
  - route `rag`; answer: "Les informations fournies ne permettent pas de connaître le cours de l'action aujourd'hui. Cependant, le document indique que le cours boursier au 31 décembre 2025 s'élève à 1 840 MAD/action [annual_r"
  - 

## Method

- **Database**: a reference SQL query gives the true values; the agent passes when its own query returns the same values (numbers within rounding).
- **Documents**: Ragas with the Gemini judge. Faithfulness = the answer is supported by the retrieved text; answer relevancy = it addresses the question; context precision/recall = the retrieved chunks are useful / sufficient compared with the reference answer.
- **Refusals**: an LLM judge checks that the copilot declines instead of inventing or acting.
- Page numbers are PDF page indexes, not the printed page numbers.
