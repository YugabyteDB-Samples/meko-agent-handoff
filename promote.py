"""A person decides what becomes Shared Knowledge. Promotion is one-way."""
from meko import call, make_meko_mcp_client, open_trace

client = make_meko_mcp_client()
with client:
    convo_id = open_trace(client, "promote: autumn menu")
    found = call(client, "memory_search", conversation_id=convo_id,
                 query="autumn menu: the dishes decided for the starter, main, and dessert, the ingredients to buy for each, and what is still undecided",
                 limit=20)["results"]

    chosen = []
    for m in found:
        print(f"\n{m['memory']}\n  id={m['id']}  written by {m['agent_id']}")
        if input("  promote to Shared Knowledge? [y/N] ").strip().lower() == "y":
            chosen.append(m["id"])

    if chosen:
        print(call(client, "memory_promote", conversation_id=convo_id, memory_ids=chosen))
