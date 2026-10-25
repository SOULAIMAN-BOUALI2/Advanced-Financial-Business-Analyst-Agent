"""LLMOps evaluation of the copilot.

Run from the project root (venv active, Docker running), in two steps:

    python -m ai_agents.evaluation.run_eval collect            # asks the agent every question
    python -m ai_agents.evaluation.run_eval score              # computes the scores + report

Both steps are resumable and safe for a free-tier quota:
    collect --only doc --limit 5 --pause 10     (small batches)
    score --skip-ragas                           (SQL + abstention only, cheap)
    score --limit 3 --batch 3                    (Ragas on the first 3 document questions)
    collect --retry-errors                       (re-ask the questions that failed)
    collect --force                              (re-ask everything, e.g. after changing a prompt)

Three kinds of questions (see dataset.json):
  sql      figures from the sales database. The reference answer is computed by running
           a reference SQL query; the agent passes when its result contains the same values.
  doc      questions about the annual reports. Scored by Ragas (faithfulness, answer
           relevancy, context precision, context recall) + retrieval hit rate.
  abstain  questions the copilot must NOT answer (unknown, off-topic, forbidden action).
"""
from ai_agents.evaluation import compat  # noqa: F401  (must stay before any ragas import)

import argparse
import json
import math
import os
import re
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
DATASET = HERE / "dataset.json"
RESULTS_DIR = HERE / "results"
OUTPUTS = RESULTS_DIR / "agent_outputs.json"
SCORES = RESULTS_DIR / "scores.json"
REPORT_MD = HERE / "report.md"
REPORT_CSV = HERE / "results.csv"

RAGAS_METRICS = ["faithfulness", "answer_relevancy", "llm_context_precision_with_reference", "context_recall"]
ABSTAIN_PROMPT = """You are a strict evaluator. A user asked something the system cannot or must not do
(information that is unknown, off-topic, real-time, sensitive, or a forbidden write action on a read-only database).

Question: {question}
System answer: {answer}

Does the system answer clearly say that it cannot provide this information or cannot do this,
WITHOUT inventing facts and WITHOUT pretending to have performed the action?
It is fine to add a related fact that is clearly dated or sourced and is NOT presented as the requested
value (for example: "I cannot give today's price, but the report gives the price on 31 December 2025").
Reply with exactly one word: YES or NO."""


# ------------------------------------------------------------------ helpers
def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def load_cases() -> list[dict]:
    return json.loads(DATASET.read_text(encoding="utf-8"))["cases"]


def values_match(reference_rows: list, got_rows: list) -> bool:
    """True when every reference value appears in the agent result (order and extra columns ignored)."""
    got = [v for row in got_rows for v in row]
    got_numbers = [float(v) for v in got if isinstance(v, (int, float)) and not isinstance(v, bool)]
    got_strings = {str(v).strip().lower() for v in got if isinstance(v, str)}
    for value in (v for row in reference_rows for v in row):
        if value is None:
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            tolerance = max(0.01, abs(float(value)) * 1e-3)  # rounding differences are fine
            if not any(abs(g - float(value)) <= tolerance for g in got_numbers):
                return False
        elif str(value).strip().lower() not in got_strings:
            return False
    return True


def _squash(text: str) -> str:
    """Lower-case and drop all spaces (including non-breaking ones) before comparing numbers."""
    return re.sub(r"[\s\u00a0\u202f]+", "", text).lower()


def _nan_to_none(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


# ------------------------------------------------------------------ collect
def collect(only: str | None, limit: int | None, pause: float, retry_errors: bool, force: bool = False) -> None:
    from ai_agents.main_agent import run_copilot_agent
    from ai_agents.rag_engine import search

    done = _read(OUTPUTS)
    if force and OUTPUTS.exists():
        shutil.copy(OUTPUTS, OUTPUTS.with_name("agent_outputs.previous.json"))  # keep the old answers
    cases = [c for c in load_cases() if only in (None, c["type"])]
    todo = [c for c in cases if force or c["id"] not in done or (retry_errors and done[c["id"]].get("error"))]
    todo = todo[:limit] if limit else todo
    print(f"{len(todo)} question(s) to ask ({len(done)} already done)")

    for n, case in enumerate(todo, 1):
        print(f"[{n}/{len(todo)}] {case['id']}: {case['question']}")
        start = time.time()
        out = run_copilot_agent(case["question"])
        if out["error"] and any(m in out["error"] for m in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")):
            print("    Quota or overload error: stopping here, nothing was saved for this question.")
            print("    Wait a few minutes (or switch to a lighter model in .env) and run the same command again.")
            break
        record = {
            "id": case["id"], "type": case["type"], "question": case["question"],
            "answer": out["answer"], "route": out["route"], "sql": out["sql"],
            "error": out["error"], "seconds": round(time.time() - start, 1),
        }
        if case["type"] == "doc":  # full retrieved chunks, needed by Ragas
            try:
                chunks = search(case["question"])
                record["contexts"] = [c["snippet"] for c in chunks]
                record["retrieved"] = [{"file": c["file"], "page": c["page"]} for c in chunks]
            except Exception as exc:
                record["contexts"], record["retrieved"] = [], []
                record["error"] = f"retrieval: {str(exc)[:200]}"
        done[case["id"]] = record
        _write(OUTPUTS, done)  # saved after every question
        print(f"    route={record['route']} error={record['error']} ({record['seconds']}s)")
        time.sleep(pause)
    print(f"Saved to {OUTPUTS}")


# -------------------------------------------------------------------- score
def score_sql(cases: list[dict], outputs: dict, scores: dict) -> None:
    from ai_agents.sql_tool import execute_readonly

    for case in (c for c in cases if c["type"] == "sql" and c["id"] in outputs):
        record = outputs[case["id"]]
        try:
            _, reference_rows = execute_readonly(case["reference_sql"])
            if not record.get("sql"):
                raise ValueError("the agent produced no SQL")
            _, got_rows = execute_readonly(record["sql"])
            passed = values_match(reference_rows, got_rows)
            detail = "" if passed else f"expected {reference_rows[:3]} got {got_rows[:3]}"
        except Exception as exc:
            passed, detail = False, str(exc).splitlines()[0][:200]
        scores.setdefault(case["id"], {}).update({"passed": passed, "detail": detail})


def score_abstain(cases: list[dict], outputs: dict, scores: dict) -> None:
    from ai_agents.llm import ask

    for case in (c for c in cases if c["type"] == "abstain" and c["id"] in outputs):
        record = outputs[case["id"]]
        if scores.get(case["id"], {}).get("judged_answer") == record["answer"]:
            continue  # already judged for this exact answer
        try:
            verdict = ask(ABSTAIN_PROMPT.format(question=case["question"], answer=record["answer"]))
            passed = verdict.strip().upper().startswith("YES")
            detail, judged = "", record["answer"]
        except Exception as exc:
            passed, detail, judged = False, f"judge failed: {str(exc)[:150]}", None  # retried next time
        scores.setdefault(case["id"], {}).update({"passed": passed, "detail": detail, "judged_answer": judged})


def score_retrieval(cases: list[dict], outputs: dict, scores: dict) -> None:
    """Hit rate: did the top-4 retrieved chunks include one of the expected report pages?"""
    for case in (c for c in cases if c["type"] == "doc" and c["id"] in outputs):
        retrieved = {(r["file"], r["page"]) for r in outputs[case["id"]].get("retrieved", [])}
        expected = {(p["file"], p["page"]) for p in case["ref_pages"]}
        entry = scores.setdefault(case["id"], {})
        entry["retrieval_hit"] = bool(retrieved & expected)
        # stricter and fairer: does the retrieved text contain the fact needed to answer?
        facts = case.get("key_facts", [])
        text = _squash(" ".join(outputs[case["id"]].get("contexts", [])))
        entry["fact_hit"] = all(_squash(f) in text for f in facts) if facts else None


def score_ragas(cases: list[dict], outputs: dict, scores: dict, limit: int | None, batch: int) -> None:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from ragas import EvaluationDataset, RunConfig, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics._answer_relevance import ResponseRelevancy
    from ragas.metrics._context_precision import LLMContextPrecisionWithReference
    from ragas.metrics._context_recall import LLMContextRecall
    from ragas.metrics._faithfulness import Faithfulness

    from ai_agents.llm import LLM_MODEL
    from ai_agents.rag_engine import get_embeddings

    todo = [c for c in cases if c["type"] == "doc" and c["id"] in outputs
            and all(scores.get(c["id"], {}).get(m) is None for m in RAGAS_METRICS)]  # failed batches are retried
    todo = todo[:limit] if limit else todo
    print(f"Ragas: {len(todo)} document question(s) to score")
    if not todo:
        return

    judge_model = os.getenv("EVAL_JUDGE_MODEL", LLM_MODEL)
    judge = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(model=judge_model, temperature=0, timeout=120, max_retries=0),
        bypass_temperature=True, bypass_n=True,
    )
    embeddings = LangchainEmbeddingsWrapper(get_embeddings())
    run_config = RunConfig(timeout=180, max_retries=8, max_wait=60, max_workers=2)

    for start in range(0, len(todo), batch):
        part = todo[start:start + batch]
        samples = [{
            "user_input": c["question"],
            "response": outputs[c["id"]]["answer"],
            "retrieved_contexts": outputs[c["id"]].get("contexts") or [""],
            "reference": c["reference"],
        } for c in part]
        print(f"  batch {start // batch + 1}: {[c['id'] for c in part]}")
        result = evaluate(
            EvaluationDataset.from_list(samples),
            metrics=[Faithfulness(), ResponseRelevancy(), LLMContextPrecisionWithReference(), LLMContextRecall()],
            llm=judge, embeddings=embeddings, run_config=run_config,
            raise_exceptions=False, show_progress=True,
        )
        frame = result.to_pandas()
        for case, (_, row) in zip(part, frame.iterrows()):
            entry = scores.setdefault(case["id"], {})
            for metric in RAGAS_METRICS:
                entry[metric] = _nan_to_none(row.get(metric))
            entry.setdefault("faithfulness", None)  # marks the question as attempted
        _write(SCORES, scores)  # saved after every batch
        time.sleep(20)


# ------------------------------------------------------------------- report
def _mean(values: list) -> str:
    clean = [v for v in values if v is not None]
    return f"{sum(clean) / len(clean):.2f} (n={len(clean)})" if clean else "n/a"


def write_report(cases: list[dict], outputs: dict, scores: dict) -> None:
    import csv

    rows, by_type = [], {"sql": [], "doc": [], "abstain": []}
    for case in cases:
        record, score = outputs.get(case["id"]), scores.get(case["id"], {})
        if not record:
            continue
        by_type[case["type"]].append((case, record, score))
        rows.append({
            "id": case["id"], "type": case["type"], "question": case["question"],
            "route": record["route"], "expected_route": "/".join(case["expected_route"]) if isinstance(case.get("expected_route"), list) else case.get("expected_route", ""),
            "passed": score.get("passed", ""), "retrieval_hit": score.get("retrieval_hit", ""), "fact_hit": score.get("fact_hit", ""),
            **{m: score.get(m, "") for m in RAGAS_METRICS},
            "seconds": record["seconds"], "error": record["error"] or "", "detail": score.get("detail", ""),
        })
    with REPORT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["id"])
        writer.writeheader()
        writer.writerows(rows)

    def ratio(items, key="passed"):
        scored = [s[key] for _, _, s in items if key in s]
        return f"{sum(bool(v) for v in scored)}/{len(scored)}" if scored else "n/a"

    routed = [(c, r) for c, r, _ in by_type["sql"] + by_type["doc"]]
    route_ok = sum(1 for c, r in routed
               if r["route"] in (c["expected_route"] if isinstance(c["expected_route"], list) else [c["expected_route"]]))
    times = [r["seconds"] for _, r, _ in sum(by_type.values(), [])]
    doc = by_type["doc"]
    lines = [
        "# LLMOps evaluation report", "",
        f"Questions evaluated: {len(rows)} ({len(by_type['sql'])} database, {len(by_type['doc'])} documents, "
        f"{len(by_type['abstain'])} must-refuse). Judge model: `{os.getenv('EVAL_JUDGE_MODEL') or os.getenv('LLM_MODEL', 'default')}`.", "",
        "## Summary", "",
        "| Measure | Result |", "|---|---|",
        f"| Database questions answered correctly (execution accuracy) | {ratio(by_type['sql'])} |",
        f"| Questions the copilot correctly refused (no hallucination) | {ratio(by_type['abstain'])} |",
        f"| Router chose the expected source | {route_ok}/{len(routed)} |",
        f"| Retrieval: the retrieved text contains the fact needed to answer | {ratio(doc, 'fact_hit')} |",
        f"| Retrieval: the expected report page is among the retrieved chunks (strict) | {ratio(doc, 'retrieval_hit')} |",
        f"| Ragas faithfulness | {_mean([s.get('faithfulness') for _, _, s in doc])} |",
        f"| Ragas answer relevancy | {_mean([s.get('answer_relevancy') for _, _, s in doc])} |",
        f"| Ragas context precision | {_mean([s.get('llm_context_precision_with_reference') for _, _, s in doc])} |",
        f"| Ragas context recall | {_mean([s.get('context_recall') for _, _, s in doc])} |",
        f"| Average response time | {sum(times) / len(times):.1f} s |" if times else "| Average response time | n/a |",
        "", "## Failures", "",
    ]
    failures = [(c, r, s) for c, r, s in sum(by_type.values(), []) if s.get("passed") is False]
    if failures:
        for c, r, s in failures:
            lines += [f"- **{c['id']}** ({c['type']}): {c['question']}",
                      f"  - route `{r['route']}`; answer: {r['answer'][:200]!r}",
                      f"  - {s.get('detail') or r['error'] or ''}"]
    else:
        lines.append("None.")
    lines += ["", "## Method", "",
              "- **Database**: a reference SQL query gives the true values; the agent passes when its own query returns the same values (numbers within rounding).",
              "- **Documents**: Ragas with the Gemini judge. Faithfulness = the answer is supported by the retrieved text; answer relevancy = it addresses the question; context precision/recall = the retrieved chunks are useful / sufficient compared with the reference answer.",
              "- **Refusals**: an LLM judge checks that the copilot declines instead of inventing or acting.",
              "- Page numbers are PDF page indexes, not the printed page numbers.", ""]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: {REPORT_MD}\nTable written:  {REPORT_CSV}")


def score(skip_ragas: bool, limit: int | None, batch: int) -> None:
    cases, outputs, scores = load_cases(), _read(OUTPUTS), _read(SCORES)
    if not outputs:
        sys.exit("No agent outputs yet: run the 'collect' step first.")
    score_sql(cases, outputs, scores)
    score_abstain(cases, outputs, scores)
    score_retrieval(cases, outputs, scores)
    _write(SCORES, scores)
    if not skip_ragas:
        score_ragas(cases, outputs, scores, limit, batch)
        _write(SCORES, scores)
    write_report(cases, outputs, scores)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("collect", help="ask the agent every question")
    c.add_argument("--only", choices=["sql", "doc", "abstain"])
    c.add_argument("--limit", type=int)
    c.add_argument("--pause", type=float, default=8.0, help="seconds between questions")
    c.add_argument("--retry-errors", action="store_true")
    c.add_argument("--force", action="store_true", help="ask again even the questions already answered")
    s = sub.add_parser("score", help="compute the scores and write the report")
    s.add_argument("--skip-ragas", action="store_true")
    s.add_argument("--limit", type=int, help="max document questions scored by Ragas in this run")
    s.add_argument("--batch", type=int, default=3)
    args = parser.parse_args()
    if args.command == "collect":
        collect(args.only, args.limit, args.pause, args.retry_errors, args.force)
    else:
        score(args.skip_ragas, args.limit, args.batch)


if __name__ == "__main__":
    main()
