# LLMOps evaluation report

Questions evaluated: 33 (13 database, 15 documents, 5 must-refuse). Judge model: `gemini-3.1-flash-lite`.

## Summary

| Measure | Result |
|---|---|
| Database questions answered correctly (execution accuracy) | 13/13 |
| Questions the copilot correctly refused (no hallucination) | 5/5 |
| Router chose the expected source | 19/28 |
| Retrieval hit rate (expected report page in the top 4 chunks) | 9/15 |
| Ragas faithfulness | n/a |
| Ragas answer relevancy | n/a |
| Ragas context precision | n/a |
| Ragas context recall | n/a |
| Average response time | 11.9 s |

## Failures

None.

## Method

- **Database**: a reference SQL query gives the true values; the agent passes when its own query returns the same values (numbers within rounding).
- **Documents**: Ragas with the Gemini judge. Faithfulness = the answer is supported by the retrieved text; answer relevancy = it addresses the question; context precision/recall = the retrieved chunks are useful / sufficient compared with the reference answer.
- **Refusals**: an LLM judge checks that the copilot declines instead of inventing or acting.
- Page numbers are PDF page indexes, not the printed page numbers.
