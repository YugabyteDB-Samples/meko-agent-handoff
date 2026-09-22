"""Agent 3, the restaurant manager. Runs on a teammate's account. Publishes the menu from
what the kitchen has shared, and says so plainly when nothing has been shared yet."""
import os

from meko import DATAPACK_ID, call, log_turn, make_meko_mcp_client, open_trace

TASK = "Write the autumn menu card from the dishes the kitchen has decided."
QUERY = "autumn menu: the dishes decided for the starter, main, and dessert, the ingredients to buy for each, and what is still undecided"


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


def dish_of(text: str) -> str | None:
    """The dish named in a DECISION record, or None for anything else."""
    if not text.startswith("DECISION: "):
        return None
    return text.removeprefix("DECISION: ").partition(" REASON: ")[0]


def format_menu(dishes: list[dict]) -> str:
    """Build the menu card from the shared records, with no model. Nothing here is invented."""
    lines = ["# Autumn menu", "", f"{len(dishes)} dish{'es' if len(dishes) != 1 else ''} decided by the kitchen.", ""]
    for d in dishes:
        lines.append(f"- {d['dish']}\n  Decided by: {d['agent']} ({d['scope']})")
    return "\n".join(lines)


def write(dishes: list[dict]) -> tuple[str, str]:
    """Return the menu and a note on who wrote it."""
    if not os.environ.get("MODEL_PROVIDER", "").strip():
        return format_menu(dishes), "formatted from the records, no model"
    from strands import Agent
    from meko_client import make_model

    context = "\n".join(d["dish"] for d in dishes)
    agent = Agent(model=make_model(), callback_handler=None)  # no streaming to the terminal
    return str(agent(f"{TASK}\n\nDishes the kitchen has decided:\n{context}")), \
        f"written by the model ({os.environ['MODEL_PROVIDER']})"


def main() -> None:
    client = make_meko_mcp_client()
    with client:
        convo_id = open_trace(client, f"restaurant-manager: menu ({DATAPACK_ID[:8]})")
        records = recall(client, convo_id)
        dishes = [{**r, "dish": dish_of(r["text"])} for r in records if dish_of(r["text"])]

        if not dishes:
            log_turn(client, convo_id, "restaurant-manager run", output="Stopped: the menu is not ready.",
                     reasoning="No decided dish is visible to this account, so there is nothing to publish.",
                     plan=["Search memory and Shared Knowledge.", "Stop if no decided dish is visible."])
            print("\nThe menu is not ready yet. Nothing has been shared with the team.")
            return

        menu, how = write(dishes)
        log_turn(client, convo_id, "restaurant-manager run",
                 output=f"Task: {TASK}\n\nDishes used:\n" + "\n".join(d["dish"] for d in dishes) + f"\n\nMenu ({how}):\n{menu}",
                 reasoning=f"{len(dishes)} decided dishes were visible to this account; the menu was {how}.",
                 plan=["Search memory and Shared Knowledge.", "Keep only the decided dishes.",
                       "Publish the menu from what was shared."])
        print(f"\n{menu}")


if __name__ == "__main__":
    main()
