"""Agent 1, the chef. Decides the dishes, records them, and later shares the decided ones.

    MEKO_AGENT_ID=chef:menu-demo uv run chef.py             # decide the dishes and record them
    MEKO_AGENT_ID=chef:menu-demo uv run chef.py --promote   # share the decided dishes with the team
"""
import json
import os
import sys
from pathlib import Path

from meko import call, log_turn, make_meko_mcp_client, open_trace

SYSTEM = (
    "You are the head chef of a small neighborhood bistro planning next season's menu. "
    "Answer the question with exactly four findings: the three dishes you decided to add, "
    "then one question you could not settle. Return ONLY a JSON list of four items. Each "
    "item has: kind ('decision' or 'open_question'), text (the dish and its place on the "
    "menu, or the question), reason, and rejected (an alternative you ruled out, or null)."
)
QUESTION = "What should we add to the autumn menu?"
QUERY = "autumn menu: the dishes decided for the starter, main, and dessert, the ingredients to buy for each, and what is still undecided"
SHOPPING_QUERY = "what does the kitchen need to buy"  # so the kitchen's notes clear the search floor on the promote run
MAX_FINDINGS = 4  # three dishes and one open question; the code holds the line even if the model does not

# An example answer to QUESTION. With no MODEL_PROVIDER set, the chef uses it instead
# of calling a model, so all you need is a Meko key.
EXAMPLE_FILE = Path(__file__).with_name("chef_example.json")


def ask_model(question: str) -> str:
    """Return the model's answer as text, or the example answer when no model is configured."""
    if not os.environ.get("MODEL_PROVIDER", "").strip():
        return EXAMPLE_FILE.read_text()
    from strands import Agent
    from meko_client import make_model

    # The model gets no Meko tools, so it cannot save anything. The code below does that.
    agent = Agent(model=make_model(), system_prompt=SYSTEM, callback_handler=None)  # no streaming to the terminal
    return str(agent(question))


def parse_findings(raw: str) -> list[dict]:
    """Pull the JSON list out of the model's answer, ignoring any prose or code fences around it."""
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        raise SystemExit("The model's answer had no JSON list in it. Run again.")
    return json.loads(raw[start:end + 1])


def record_decision(client, convo_id: str, d: dict) -> None:
    """Turn one finding into a single line of text and store it as written."""
    text = f"{d['kind'].upper()}: {d['text']} REASON: {d['reason']}"
    if d.get("rejected"):
        text += f" REJECTED: {d['rejected']}"
    call(client, "memory_add", conversation_id=convo_id, text=text)
    print(f"recorded: {text[:80]}")


def allowed_by_policy(text: str) -> tuple[bool, str]:
    """What the chef is willing to share. Open questions and the kitchen's notes stay private."""
    if text.startswith("OPEN_QUESTION"):
        return False, "open questions stay private until settled"
    if not text.startswith("DECISION"):
        return False, "only decided dishes go on the menu"
    if "REASON:" not in text:
        return False, "a decision without a reason is not ready to share"
    return True, "decided, with a reason"


def decide(client, raw: str, source: str) -> None:
    """Record every finding from the answer, up to MAX_FINDINGS."""
    findings = parse_findings(raw)[:MAX_FINDINGS]
    convo_id = open_trace(client, "chef: autumn menu")
    log_turn(client, convo_id, "chef run",
             output=f"Question: {QUESTION}\n\nModel answer ({source}):\n{raw}",
             reasoning=f"The model answered; the code below writes the first {MAX_FINDINGS} "
                       "findings so the record does not depend on the model choosing to save it.",
             plan=["Ask the model for dishes, reasons, and rejected alternatives as JSON.",
                   "Write each one to memory with memory_add so the wording is kept.",
                   "Leave open questions private until someone settles them."])
    for d in findings:
        record_decision(client, convo_id, d)  # the code writes the findings, every run


def promote(client) -> None:
    """Move the decided dishes into Shared Knowledge. A rule in code decides which."""
    convo_id = open_trace(client, "chef: share the decided dishes")
    candidates: dict[str, dict] = {}
    for query in (QUERY, SHOPPING_QUERY):  # two searches, joined by id, so every private record gets a verdict
        for m in call(client, "memory_search", conversation_id=convo_id, query=query)["results"]:
            candidates.setdefault(m["id"], m)

    approved, verdicts = [], []
    for m in candidates.values():
        ok, why = allowed_by_policy(m["memory"])
        verdicts.append(f"{'PROMOTE' if ok else 'KEEP'}: {m['memory'][:70]} ({why})")
        print(f"{'PROMOTE' if ok else 'KEEP   '} {m['memory'][:70]}\n         {why}")
        if ok:
            approved.append(m["id"])

    log_turn(client, convo_id, "chef promotion", output="\n".join(verdicts) or "no candidates",
             reasoning="A rule in code picked the records to share; nothing else was consulted.",
             plan=["Search private memories.", "Apply the policy.",
                   "Promote the approved ones with memory_promote."])
    if approved:
        print(call(client, "memory_promote", conversation_id=convo_id, memory_ids=approved))
    else:
        print("nothing promoted")


def main() -> None:
    if "--promote" not in sys.argv:
        raw = ask_model(QUESTION)
        source = "example answer from chef_example.json" if not os.environ.get("MODEL_PROVIDER", "").strip() \
            else os.environ["MODEL_PROVIDER"]

    client = make_meko_mcp_client()
    with client:
        if "--promote" in sys.argv:
            promote(client)
        else:
            decide(client, raw, source)


if __name__ == "__main__":
    main()
