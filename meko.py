"""Shared plumbing for the webinar demo. Prepared ahead of time, not typed live.

Every Meko call in the demo goes through call(), so there is a single place where
the datapack, the agent_id, and the conversation (trace) id get attached.
"""
from __future__ import annotations

import json
import os
import uuid

from dotenv import load_dotenv

load_dotenv(os.environ.get("ENV_FILE", ".env"), override=True)  # ENV_FILE=.env.teammate for terminal C

from meko_client import make_meko_mcp_client  # unchanged from the sample repo

DATAPACK_ID = os.environ["MEKO_DATAPACK_ID"]
AGENT_ID = os.environ["MEKO_AGENT_ID"]  # e.g. researcher:retry-demo


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
    if "structuredContent" in res:  # mcp 2.x servers may return the payload here
        return res["structuredContent"]
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
