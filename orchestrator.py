"""Agent-decided promotion. An orchestrator reviews private memories and promotes
the ones the team should build on. Code sets the guardrail; a model may judge inside it.

Runs as its own agent_id so the trace shows who made the promotion call.

    MEKO_AGENT_ID=orchestrator:retry-demo uv run orchestrator.py            # model judges
    MEKO_AGENT_ID=orchestrator:retry-demo uv run orchestrator.py --rules   # code only
"""
import json
import sys

from meko import call, log_turn, make_meko_mcp_client, open_trace

QUERY = "http_client.py retry behavior: backoff, which status codes to retry, and Retry-After handling"
JUDGE = (
    "You review engineering decision records. Given one record, answer ONLY with JSON: "
    '{"promote": true|false, "why": "<one sentence>"}. Promote only a settled decision '
    "that states its reason. Never promote an open question or a record without a reason."
)


def allowed_by_policy(text: str) -> tuple[bool, str]:
    """The guardrail. The model never gets to override this."""
    if text.startswith("OPEN_QUESTION"):
        return False, "open questions stay private until settled"
    if not text.startswith("DECISION"):
        return False, "only DECISION records are eligible"
    if "REASON:" not in text:
        return False, "a decision without a reason is not ready to share"
    return True, "eligible"


def judged_by_model(text: str) -> tuple[bool, str]:
    from strands import Agent
    from meko_client import make_model

    raw = str(Agent(model=make_model(), system_prompt=JUDGE)(text)).strip()
    verdict = json.loads(raw.removeprefix("```json").removesuffix("```"))
    return bool(verdict["promote"]), verdict["why"]


def main() -> None:
    rules_only = "--rules" in sys.argv
    client = make_meko_mcp_client()
    with client:
        convo_id = open_trace(client, "orchestrator: promotion review")
        candidates = call(client, "memory_search", conversation_id=convo_id, query=QUERY)["results"]

        approved, verdicts = [], []
        for m in candidates:
            ok, why = allowed_by_policy(m["memory"])
            if ok and not rules_only:
                ok, why = judged_by_model(m["memory"])
            verdicts.append(f"{'PROMOTE' if ok else 'KEEP'}: {m['memory'][:70]} ({why})")
            print(f"{'PROMOTE' if ok else 'KEEP   '} {m['memory'][:70]}\n         {why}")
            if ok:
                approved.append(m["id"])

        log_turn(client, convo_id, "orchestrator run", output="\n".join(verdicts) or "no candidates",
                 reasoning="The policy in code ran first; the model only judged records the policy allowed."
                           if not rules_only else "Rules only: no model call.",
                 plan=["Search private memories.", "Apply the policy.",
                       "Promote the approved ones with memory_promote."])
        if approved:
            print(call(client, "memory_promote", conversation_id=convo_id, memory_ids=approved))
        else:
            print("nothing promoted")


if __name__ == "__main__":
    main()
