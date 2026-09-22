"""Agent 2, the kitchen manager. New process, no local state. Recalls the menu, then writes the shopping list."""
import os

from meko import DATAPACK_ID, call, log_turn, make_meko_mcp_client, open_trace

TASK = "Write the shopping list for the dishes already decided for the autumn menu."
QUERY = "autumn menu: the dishes decided for the starter, main, and dessert, the ingredients to buy for each, and what is still undecided"
# With no MODEL_PROVIDER set, the kitchen manager builds the shopping list from the
# recalled records instead of asking a model, so the demo runs on a Meko key alone.
# Every line in that list comes from a record in Meko, labeled with the agent that wrote it.


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
    """Split a record the chef wrote: KIND: text INGREDIENTS: a, b REASON: reason REJECTED: alternative."""
    kind, _, rest = text.partition(": ")
    body, _, rejected = rest.partition(" REJECTED: ")
    body, _, reason = body.partition(" REASON: ")
    dish, _, ingredients = body.partition(" INGREDIENTS: ")
    return {"kind": kind, "text": dish, "reason": reason, "rejected": rejected,
            "ingredients": [i.strip() for i in ingredients.split(",") if i.strip()]}


def plural(n: int, word: str, plural_word: str | None = None) -> str:
    return f"{n} {word if n == 1 else (plural_word or word + 's')}"


def format_shopping_list(records: list[dict]) -> str:
    """Build the shopping list from the records, with no model. Nothing here is invented."""
    dishes, open_questions, to_buy = [], [], {}
    for r in records:
        p = parse_record(r["text"])
        origin = f"{r['agent']} ({r['scope']})"
        if p["kind"] == "OPEN_QUESTION":
            open_questions.append(f"- {p['text']}\n  Why it is open: {p['reason']}\n  Recorded by: {origin}")
        elif p["kind"] == "DECISION":
            item = f"- {p['text']}\n  Why: {p['reason']}"
            if p["rejected"]:
                item += f"\n  Rejected: {p['rejected']}"
            dishes.append(item + f"\n  Decided by: {origin}")
            for ingredient in p["ingredients"]:
                to_buy.setdefault(ingredient, []).append(p["text"].rstrip("."))
        else:
            dishes.append(f"- {r['text']}\n  Recorded by: {origin}")

    parts = ["# Shopping list for the autumn menu", "",
             f"{plural(len(dishes), 'dish', 'dishes')} decided and "
             f"{plural(len(open_questions), 'question')} still open were recalled from Meko.", ""]
    if dishes:
        parts += ["## Dishes", ""] + dishes + [""]
    if to_buy:
        parts += ["## To buy", ""] + [f"- {i} (for: {'; '.join(d)})" for i, d in sorted(to_buy.items())] + [""]
    if open_questions:
        parts += ["## Still open, nothing to buy yet", ""] + open_questions + [""]
    return "\n".join(parts).rstrip()


def write(records: list[dict]) -> tuple[str, str]:
    """Return the shopping list and a note on who wrote it."""
    if not os.environ.get("MODEL_PROVIDER", "").strip():
        return format_shopping_list(records), "formatted from the records, no model"
    from strands import Agent
    from meko_client import make_model

    context = "\n".join(r["text"] for r in records)
    agent = Agent(model=make_model(), callback_handler=None)  # no streaming to the terminal
    return str(agent(f"{TASK}\n\nDecisions already made about this menu:\n{context}")), \
        f"written by the model ({os.environ['MODEL_PROVIDER']})"


def main() -> None:
    client = make_meko_mcp_client()
    with client:
        convo_id = open_trace(client, f"kitchen-manager: shopping list ({DATAPACK_ID[:8]})")
        records = recall(client, convo_id)

        if not records:
            log_turn(client, convo_id, "kitchen-manager run", output="Stopped: no recorded decisions found.",
                     reasoning="Nothing in memory or Shared Knowledge matched, so writing the "
                               "shopping list would mean inventing a menu.",
                     plan=["Search memory and Shared Knowledge.", "Stop if both are empty."])
            print("\nNo recorded decisions found. The kitchen manager would be guessing, so it stops.")
            return

        shopping_list, how = write(records)
        context = "\n".join(r["text"] for r in records)
        log_turn(client, convo_id, "kitchen-manager run",
                 output=f"Task: {TASK}\n\nContext used:\n{context}\n\nShopping list ({how}):\n{shopping_list}",
                 reasoning=f"{len(records)} recorded decisions were found; the shopping list was {how}.",
                 plan=["Search memory and Shared Knowledge.",
                       "Build the shopping list from what was found.",
                       "Post the list and its sources to the trace."])
        print(f"\n{shopping_list}")


if __name__ == "__main__":
    main()
