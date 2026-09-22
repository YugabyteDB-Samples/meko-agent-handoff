"""Agent 2. New process, no local state. Recalls context, then writes."""
from strands import Agent

from meko import DATAPACK_ID, call, log_turn, make_meko_mcp_client, open_trace
from meko_client import make_model

TASK = "Write the pull request description for the retry logic in http_client.py."
QUERY = "http_client.py retry behavior: backoff, which status codes to retry, and Retry-After handling"


def recall(client, convo_id: str) -> list[str]:
    # --- typed live ---
    mine = call(client, "memory_search", conversation_id=convo_id, query=QUERY)["results"]
    team = call(client, "knowledgebase_search", conversation_id=convo_id, query=QUERY)["results"]

    print(f"memory: {len(mine)} results")
    for m in mine:
        print(f"  [{m['agent_id']}] {m['memory'][:90]}")

    print(f"shared knowledge: {len(team)} results")
    for k in team:
        print(f"  [{k['metadata_filters'].get('agent_id')}] {k['chunk_text'][:90]}")

    return [m["memory"] for m in mine] + [k["chunk_text"] for k in team]


def main() -> None:
    client = make_meko_mcp_client()
    with client:
        convo_id = open_trace(client, f"writer: PR description ({DATAPACK_ID[:8]})")
        context = recall(client, convo_id)

        if not context:
            log_turn(client, convo_id, "writer run", output="Stopped: no recorded decisions found.",
                     reasoning="Nothing in memory or Shared Knowledge matched, so writing the "
                               "description would mean inventing a retry policy.",
                     plan=["Search memory and Shared Knowledge.", "Stop if both are empty."])
            print("\nNo recorded decisions found. The writer would be guessing, so it stops.")
            return

        agent = Agent(model=make_model())
        description = str(agent(f"{TASK}\n\nDecisions already made on this project:\n" + "\n".join(context)))
        log_turn(client, convo_id, "writer run",
                 output=f"Task: {TASK}\n\nContext used:\n" + "\n".join(context) + f"\n\nDescription:\n{description}",
                 reasoning=f"{len(context)} recorded decisions were found and given to the model as context.",
                 plan=["Search memory and Shared Knowledge.", "Give what was found to the model.",
                       "Write the pull request description from it."])
        print(description)


if __name__ == "__main__":
    main()
