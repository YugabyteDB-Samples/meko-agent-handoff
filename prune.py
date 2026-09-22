"""Cleanup for a shared datapack. Code finds the candidates, a person decides.

Runs the questions this project actually asks against memory_search. A memory
that never clears the score floor for any of them is a candidate. Nothing is
deleted without a y, and a superseded decision can be corrected instead.
"""
from meko import call, make_meko_mcp_client, open_trace

QUESTIONS = [
    "http_client.py retry behavior: backoff, which status codes to retry, and Retry-After handling",
    "which HTTP status codes should be retried",
    "how long to wait between retries",
]
FLOOR = 0.6  # raw cosine similarity; tune it against your own datapack

client = make_meko_mcp_client()
with client:
    convo_id = open_trace(client, "prune: retry policy")

    seen: dict[str, dict] = {}
    best: dict[str, float] = {}
    for q in QUESTIONS:
        for m in call(client, "memory_search", conversation_id=convo_id, query=q, limit=20)["results"]:
            seen[m["id"]] = m
            best[m["id"]] = max(best.get(m["id"], 0.0), m["raw_similarity_score"])

    for mid, m in seen.items():
        flag = "KEEP" if best[mid] >= FLOOR else "LOW "
        print(f"\n{flag} best={best[mid]:.2f} by {m['agent_id']}\n  {m['memory'][:120]}")
        if flag == "KEEP":
            continue
        choice = input("  [d]elete, [c]orrect, or keep? ").strip().lower()
        if choice == "d":
            print(call(client, "memory_delete_by_id", conversation_id=convo_id, memory_id=mid))
        elif choice == "c":
            text = input("  replacement text: ").strip()
            print(call(client, "memory_update", conversation_id=convo_id, memory_id=mid, text=text))
