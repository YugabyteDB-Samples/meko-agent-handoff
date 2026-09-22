"""Agent 2. New process, no local state. Recalls context, then writes."""
import os

from meko import DATAPACK_ID, call, log_turn, make_meko_mcp_client, open_trace

TASK = "Write the pull request description for the retry logic in http_client.py."
QUERY = "http_client.py retry behavior: backoff, which status codes to retry, and Retry-After handling"
# With no MODEL_PROVIDER set, the writer formats the description from the recalled
# records instead of asking a model, so the demo runs on a Meko key alone. Every line
# in that description is a record from Meko, labeled with the agent that wrote it.


def recall(client, convo_id: str) -> list[dict]:
    """Ask both scopes: memory_search for your memories, knowledgebase_search for the team's."""
    mine = call(client, "memory_search", conversation_id=convo_id, query=QUERY)["results"]
    team = call(client, "knowledgebase_search", conversation_id=convo_id, query=QUERY)["results"]

    print(f"memory: {len(mine)} results")
    for m in mine:
        print(f"  [{m['agent_id']}] {m['memory'][:90]}")

    print(f"shared knowledge: {len(team)} results")
    for k in team:
        print(f"  [{k['metadata_filters'].get('agent_id')}] {k['chunk_text'][:90]}")

    return ([{"scope": "memory", "agent": m["agent_id"], "text": m["memory"]} for m in mine]
            + [{"scope": "Shared Knowledge", "agent": k["metadata_filters"].get("agent_id"),
                "text": k["chunk_text"]} for k in team])


def parse_record(text: str) -> dict:
    """Split a record the researcher wrote (KIND: text REASON: reason REJECTED: alt)."""
    kind, _, rest = text.partition(": ")
    body, _, rejected = rest.partition(" REJECTED: ")
    text, _, reason = body.partition(" REASON: ")
    return {"kind": kind, "text": text, "reason": reason, "rejected": rejected}


def format_description(records: list[dict]) -> str:
    """Build the description from the records, with no model. Nothing here is invented."""
    decisions, open_questions = [], []
    for r in records:
        p = parse_record(r["text"])
        origin = f"{r['agent']} ({r['scope']})"
        if p["kind"] == "OPEN_QUESTION":
            open_questions.append(f"- {p['text']}\n  Why it is open: {p['reason']}\n  Recorded by: {origin}")
        elif p["kind"] == "DECISION":
            item = f"- {p['text']}\n  Why: {p['reason']}"
            if p["rejected"]:
                item += f"\n  Rejected: {p['rejected']}"
            decisions.append(item + f"\n  Recorded by: {origin}")
        else:
            decisions.append(f"- {r['text']}\n  Recorded by: {origin}")

    parts = ["# Retry logic for http_client.py", "",
             f"This change implements the retry policy already decided on this project. "
             f"{len(decisions)} decision(s) and {len(open_questions)} open question(s) were recalled from Meko.", ""]
    if decisions:
        parts += ["## Decisions", ""] + decisions + [""]
    if open_questions:
        parts += ["## Open questions, not part of this change", ""] + open_questions + [""]
    return "\n".join(parts).rstrip()


def write(records: list[dict]) -> tuple[str, str]:
    """Return the description and a note on who wrote it."""
    if not os.environ.get("MODEL_PROVIDER", "").strip():
        return format_description(records), "formatted from the records, no model"
    from strands import Agent
    from meko_client import make_model

    context = "\n".join(r["text"] for r in records)
    agent = Agent(model=make_model(), callback_handler=None)  # no streaming to the terminal
    return str(agent(f"{TASK}\n\nDecisions already made on this project:\n{context}")), \
        f"written by the model ({os.environ['MODEL_PROVIDER']})"


def main() -> None:
    client = make_meko_mcp_client()
    with client:
        convo_id = open_trace(client, f"writer: PR description ({DATAPACK_ID[:8]})")
        records = recall(client, convo_id)

        if not records:
            log_turn(client, convo_id, "writer run", output="Stopped: no recorded decisions found.",
                     reasoning="Nothing in memory or Shared Knowledge matched, so writing the "
                               "description would mean inventing a retry policy.",
                     plan=["Search memory and Shared Knowledge.", "Stop if both are empty."])
            print("\nNo recorded decisions found. The writer would be guessing, so it stops.")
            return

        description, how = write(records)
        context = "\n".join(r["text"] for r in records)
        log_turn(client, convo_id, "writer run",
                 output=f"Task: {TASK}\n\nContext used:\n{context}\n\nDescription ({how}):\n{description}",
                 reasoning=f"{len(records)} recorded decisions were found; the description was {how}.",
                 plan=["Search memory and Shared Knowledge.",
                       "Build the pull request description from what was found.",
                       "Post the description and its sources to the trace."])
        print(f"\n{description}")


if __name__ == "__main__":
    main()
