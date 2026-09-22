"""Shared plumbing for every script in this repo.

Every Meko call goes through call(), so there is one place where the datapack,
the agent_id, and the conversation (trace) id get attached to a request.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv



def _env_file() -> str:
    """Settings come from .env, or from the file named after --env, e.g. --env .env.teammate."""
    if "--env" in sys.argv:
        i = sys.argv.index("--env")
        if i + 1 >= len(sys.argv):
            raise SystemExit("--env needs a file name, for example: --env .env.teammate")
        return sys.argv[i + 1]
    return ".env"


SETTINGS_FILE = Path(_env_file())
if not SETTINGS_FILE.is_file():
    raise SystemExit(f"{SETTINGS_FILE} not found. Copy .env.example to {SETTINGS_FILE} and fill it in.")
load_dotenv(SETTINGS_FILE, override=True)

from meko_client import make_meko_mcp_client

DATAPACK_ID = os.environ.get("MEKO_DATAPACK_ID", "").strip()
AGENT_ID = os.environ.get("MEKO_AGENT_ID", "").strip()  # the name this script saves under, e.g. chef:menu-demo

if not AGENT_ID:
    raise SystemExit(
        "MEKO_AGENT_ID is not set. Prefix the command with the name this script should save under, "
        "for example: MEKO_AGENT_ID=chef:menu-demo uv run chef.py"
    )

try:
    uuid.UUID(DATAPACK_ID)
except ValueError:
    raise SystemExit(
        f"MEKO_DATAPACK_ID is {DATAPACK_ID!r}, which is not a datapack id. It needs the UUID "
        "shown on the datapack's page at cloud.mekodata.ai, not the datapack's name."
    )


def call(client, tool: str, **arguments) -> dict:
    """Call one Meko MCP tool from plain Python and return its JSON payload."""
    res = client.call_tool_sync(
        tool_use_id=f"{tool}-{uuid.uuid4().hex[:8]}",
        name=tool,
        arguments={"agent_id": AGENT_ID, "datapack_id": DATAPACK_ID, **arguments},
    )
    text = "\n".join(c.get("text", "") for c in res.get("content", []) if "text" in c)
    if res.get("status") != "success":
        raise RuntimeError(f"Meko tool {tool} returned an error:\n{text or res}")
    # The tool's answer is JSON inside the text block.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(f"Meko tool {tool} returned something other than JSON:\n{text[:800] or res}")


def open_trace(client, title: str) -> str:
    """Create the conversation for this run. Its id is also the trace id."""
    convo_id = call(client, "conversation_create", title=title)["id"]
    print(f"trace: {convo_id}")
    return convo_id


def log_turn(client, convo_id: str, label: str, output: str, reasoning: str, plan: list[str]) -> None:
    """Put the agent's thinking in the trace: what it was asked, what came back, why, and the plan.

    `input` is a short label on purpose. Meko extracts memories from the input side
    of a posted turn, and a question there becomes a memory of its own that outranks
    the real decisions in search. A label extracts nothing; the question goes in `output`.
    """
    call(client, "conversation_add_message", conversation_id=convo_id,
         input=label, output=output, reasoning=reasoning, plan=plan)


__all__ = ["make_meko_mcp_client", "call", "open_trace", "log_turn", "AGENT_ID", "DATAPACK_ID"]
