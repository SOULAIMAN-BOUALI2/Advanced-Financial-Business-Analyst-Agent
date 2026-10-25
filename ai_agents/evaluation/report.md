# LLMOps evaluation report

Questions evaluated: 33 (13 database, 15 documents, 5 must-refuse). Judge model: `gemini-3.1-flash-lite`.

## Summary

| Measure | Result |
|---|---|
| Database questions answered correctly (execution accuracy) | 13/13 |
| Questions the copilot correctly refused (no hallucination) | 4/5 |
| Router chose the expected source | 28/28 |
| Retrieval: the retrieved text contains the fact needed to answer | 14/15 |
| Retrieval: the expected report page is among the retrieved chunks (strict) | 14/15 |
| Ragas faithfulness | 0.91 (n=15) |
| Ragas answer relevancy | 0.79 (n=15) |
| Ragas context precision | 0.76 (n=15) |
| Ragas context recall | 1.00 (n=15) |
| Average response time | 9.3 s |

## Failures

- **abs-02** (abstain): Quelle est la capitale de l'Australie ?
  - route `rag`; answer: 'Les informations fournies ne contiennent pas la réponse à cette question.'
  - 

## Method

- **Database**: a reference SQL query gives the true values; the agent passes when its own query returns the same values (numbers within rounding).
- **Documents**: Ragas with the Gemini judge. Faithfulness = the answer is supported by the retrieved text; answer relevancy = it addresses the question; context precision/recall = the retrieved chunks are useful / sufficient compared with the reference answer.
- **Refusals**: an LLM judge checks that the copilot declines instead of inventing or acting.
- Page numbers are PDF page indexes, not the printed page numbers.
