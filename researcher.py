"""Agent 1. Researches a question, then plain Python records what it decided."""
import json

from strands import Agent

from meko import call, log_turn, make_meko_mcp_client, open_trace
from meko_client import make_model

SYSTEM = (
    "You are a research agent for a Python HTTP client library. Answer the question, "
    "then return ONLY a JSON list. Each item has: kind ('decision' or 'open_question'), "
    "text, reason, and rejected (an alternative you ruled out, or null)."
)
QUESTION = "How should http_client.py retry failed requests?"


def record_decision(client, convo_id: str, d: dict) -> None:
    # --- typed live ---
    text = f"{d['kind'].upper()}: {d['text']} REASON: {d['reason']}"
    if d.get("rejected"):
        text += f" REJECTED: {d['rejected']}"
    call(client, "memory_add", conversation_id=convo_id, text=text)
    print(f"recorded: {text[:80]}")


def main() -> None:
    agent = Agent(model=make_model(), system_prompt=SYSTEM)  # no Meko tools attached
    raw = str(agent(QUESTION)).strip().removeprefix("```json").removesuffix("```")
    findings = json.loads(raw)

    client = make_meko_mcp_client()
    with client:
        convo_id = open_trace(client, "researcher: retry policy")
        log_turn(client, convo_id, "researcher run",
                 output=f"Question: {QUESTION}\n\nModel answer:\n{raw}",
                 reasoning="The model answered; the code below writes every decision so the "
                           "record does not depend on the model choosing to save it.",
                 plan=["Ask the model for decisions, reasons, and rejected alternatives as JSON.",
                       "Write each one to memory with memory_add so the wording is kept.",
                       "Leave open questions private until someone settles them."])
        for d in findings:
            record_decision(client, convo_id, d)  # the code decides, every time


if __name__ == "__main__":
    main()
