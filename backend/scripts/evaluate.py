"""Run the evaluation questions through the real agent (local LLM + pgvector) and write a report.

Usage (inside the backend container, after seeding the knowledge base):
    docker compose exec backend python -m scripts.evaluate
    docker compose exec backend python -m scripts.evaluate --threshold 0.82

Outputs eval/results.md (table for the technical report) and eval/results.json.
"""

import argparse
import json
import os
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, help="Override SIMILARITY_THRESHOLD for this run")
    parser.add_argument("--questions", default=str(EVAL_DIR / "questions.json"))
    args = parser.parse_args()
    if args.threshold is not None:
        os.environ["SIMILARITY_THRESHOLD"] = str(args.threshold)

    # Imported after the env override so the settings pick it up.
    from app.agent.graph import build_graph
    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.repositories import DocumentRepository
    from app.services.embeddings import get_embeddings

    settings = get_settings()
    db = SessionLocal()
    repo = DocumentRepository(db)
    embeddings = get_embeddings()
    graph = build_graph()

    def search(query: str, top_k: int):
        return repo.search(embeddings.embed_query(query), top_k)

    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    by_id: dict[int, dict] = {}
    results = []
    for q in questions:
        history = []
        if q.get("follow_up_of") in by_id:
            prev = by_id[q["follow_up_of"]]
            history = [{"role": "user", "content": prev["question"]}, {"role": "assistant", "content": prev["answer"]}]

        start = time.perf_counter()
        state = graph.invoke(
            {"question": q["question"], "user_id": "eval", "conversation_id": "eval", "history": history},
            config={"configurable": {"retriever": search, "history_store": None}},
        )
        seconds = time.perf_counter() - start

        answered = state["status"] == "answered"
        if q["expected"] == "answer":
            text = state["answer"].lower()
            correct = answered and any(k.lower() in text for k in q.get("keywords", []))
            outcome = "correct" if correct else ("wrong answer" if answered else "false rejection")
        else:
            outcome = "correct rejection" if not answered else "HALLUCINATION RISK"

        best = state.get("retrieved", [{}])[0].get("similarity", 0.0) if state.get("retrieved") else 0.0
        row = {
            **q,
            "status": state["status"],
            "reject_reason": state.get("reject_reason"),
            "answer": state["answer"],
            "best_similarity": best,
            "sources": [s["title"] for s in state.get("sources", [])],
            "seconds": round(seconds, 1),
            "outcome": outcome,
        }
        by_id[q["id"]] = row
        results.append(row)
        print(f"[{q['id']:>2}] {outcome:<20} sim={best:.3f} {seconds:5.1f}s  {q['question']}")

    db.close()

    ok = sum(r["outcome"].startswith("correct") for r in results)
    lines = [
        f"# Evaluation results\n",
        f"- Model: `{settings.llm_model}` | Embeddings: `{settings.embedding_model}`",
        f"- Similarity threshold: `{settings.similarity_threshold}` | top-k: `{settings.retrieval_top_k}`",
        f"- Score: **{ok}/{len(results)}** correct | "
        f"avg latency {sum(r['seconds'] for r in results) / len(results):.1f}s\n",
        "| # | Question | Expected | Status | Best sim. | Outcome | Time (s) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['id']} | {r['question']} | {r['expected']} | {r['status']} | "
            f"{r['best_similarity']:.3f} | {r['outcome']} | {r['seconds']} |"
        )
    (EVAL_DIR / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (EVAL_DIR / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nScore {ok}/{len(results)}. Report written to {EVAL_DIR / 'results.md'}")


if __name__ == "__main__":
    main()
