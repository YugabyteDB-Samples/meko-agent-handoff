"""Agent 1. Researches a question, then plain Python records what it decided."""
import json
import os
from pathlib import Path

from meko import call, log_turn, make_meko_mcp_client, open_trace

SYSTEM = (
    "You are a research agent for a Python HTTP client library. Answer the question, "
    "then return ONLY a JSON list. Each item has: kind ('decision' or 'open_question'), "
    "text, reason, and rejected (an alternative you ruled out, or null)."
)
QUESTION = "How should http_client.py retry failed requests?"
# A recorded model answer to QUESTION. With no MODEL_PROVIDER set, the researcher
# replays it instead of calling a model, so all you need is a Meko key.
REPLAY_FILE = Path(__file__).with_name("researcher_example.json")


def ask_model(question: str) -> str:
    """Return the model's answer as text, or the recorded answer when no model is configured."""
    if not os.environ.get("MODEL_PROVIDER", "").strip():
        return REPLAY_FILE.read_text()
    from strands import Agent
    from meko_client import make_model

    # The model gets no Meko tools, so it cannot save anything. The code below does that.
    agent = Agent(model=make_model(), system_prompt=SYSTEM)
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


def main() -> None:
    raw = ask_model(QUESTION)
    findings = parse_findings(raw)
    source = "replayed from researcher_example.json" if not os.environ.get("MODEL_PROVIDER", "").strip() \
        else os.environ["MODEL_PROVIDER"]

    client = make_meko_mcp_client()
    with client:
        convo_id = open_trace(client, "researcher: retry policy")
        log_turn(client, convo_id, "researcher run",
                 output=f"Question: {QUESTION}\n\nModel answer ({source}):\n{raw}",
                 reasoning="The model answered; the code below writes every decision so the "
                           "record does not depend on the model choosing to save it.",
                 plan=["Ask the model for decisions, reasons, and rejected alternatives as JSON.",
                       "Write each one to memory with memory_add so the wording is kept.",
                       "Leave open questions private until someone settles them."])
        for d in findings:
            record_decision(client, convo_id, d)  # the code writes every finding, every run


if __name__ == "__main__":
    main()
