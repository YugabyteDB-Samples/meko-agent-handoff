"""Agent 2, the kitchen manager. New process, no local state. Reads the chef's dishes,
works out what each one needs, and records that as memories of its own."""
import json
import os
from pathlib import Path

from meko import call, log_turn, make_meko_mcp_client, open_trace

QUERY = "autumn menu: the dishes decided for the starter, main, and dessert, the ingredients to buy for each, and what is still undecided"
SYSTEM = (
    "You run the kitchen at a small bistro. Given one dish, list the ingredients to buy for "
    "it, at most five. Return ONLY a JSON list of strings."
)
# Ingredients for each dish in chef_example.json, keyed by the dish text. With no
# MODEL_PROVIDER set, the kitchen manager looks dishes up here instead of asking a model.
INGREDIENTS_FILE = Path(__file__).with_name("kitchen_manager_example.json")


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
    """Split a record the chef wrote: KIND: text REASON: reason REJECTED: alternative."""
    kind, _, rest = text.partition(": ")
    body, _, rejected = rest.partition(" REJECTED: ")
    dish, _, reason = body.partition(" REASON: ")
    return {"kind": kind, "text": dish, "reason": reason, "rejected": rejected}


def ingredients_for(dish: str) -> list[str] | None:
    """What to buy for one dish: from the model if there is one, otherwise from the recorded list."""
    if not os.environ.get("MODEL_PROVIDER", "").strip():
        return json.loads(INGREDIENTS_FILE.read_text()).get(dish)
    from strands import Agent
    from meko_client import make_model

    raw = str(Agent(model=make_model(), system_prompt=SYSTEM, callback_handler=None)(dish))
    start, end = raw.find("["), raw.rfind("]")  # the JSON list, whatever surrounds it
    return json.loads(raw[start:end + 1])[:5]


def record_ingredients(client, convo_id: str, dish: str, ingredients: list[str]) -> str:
    """Store the shopping note for one dish as a memory of the kitchen manager's own."""
    text = f"INGREDIENTS: {dish} NEEDS: {', '.join(ingredients)}"
    call(client, "memory_add", conversation_id=convo_id, text=text)
    print(f"recorded: {text[:80]}")
    return text


def main() -> None:
    client = make_meko_mcp_client()
    with client:
        convo_id = open_trace(client, "kitchen-manager: what each dish needs")
        records = recall(client, convo_id)
        dishes = [parse_record(r["text"]) for r in records]
        dishes = [d for d in dishes if d["kind"] == "DECISION"]

        if not dishes:
            log_turn(client, convo_id, "kitchen-manager run", output="Stopped: no decided dishes found.",
                     reasoning="Nothing in memory or Shared Knowledge is a decided dish, so there is "
                               "nothing to shop for.",
                     plan=["Search memory and Shared Knowledge.", "Stop if no dish is decided."])
            print("\nNo decided dishes found. The kitchen manager would be guessing, so it stops.")
            return

        notes, to_buy = [], {}
        for d in dishes:
            ingredients = ingredients_for(d["text"])
            if not ingredients:
                print(f"skipped: no recorded ingredients for {d['text']!r}; set MODEL_PROVIDER to work them out")
                continue
            notes.append(record_ingredients(client, convo_id, d["text"], ingredients))
            for i in ingredients:
                to_buy.setdefault(i, []).append(d["text"].rstrip("."))

        print("\n# To buy for the autumn menu\n")
        for i, for_dishes in sorted(to_buy.items()):
            print(f"- {i} (for: {'; '.join(for_dishes)})")

        log_turn(client, convo_id, "kitchen-manager run",
                 output=f"Dishes found:\n" + "\n".join(d["text"] for d in dishes) + "\n\nRecorded:\n" + "\n".join(notes),
                 reasoning=f"{len(dishes)} decided dishes were found; one INGREDIENTS memory was written per dish. "
                           "Open questions were left alone.",
                 plan=["Search memory and Shared Knowledge.", "Keep only the decided dishes.",
                       "Work out what each needs and record it with memory_add."])


if __name__ == "__main__":
    main()
