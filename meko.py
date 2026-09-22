"""Shared plumbing for the webinar demo. Prepared ahead of time, not typed live.

Every Meko call in the demo goes through call(), so there is a single place where
the datapack, the agent_id, and the conversation (trace) id get attached.
"""
from __future__ import annotations

import json
import os
import uuid

from dotenv import load_dotenv

load_dotenv(os.environ.get("ENV_FILE", ".env.me"), override=True)  # .env.teammate in terminal C

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
    return json.loads(res["content"][0]["text"])


def open_trace(client, title: str) -> str:
    """Create the conversation for this run. Its id is also the trace id."""
    convo_id = call(client, "conversation_create", title=title)["id"]
    print(f"trace: {convo_id}")
    return convo_id


__all__ = ["make_meko_mcp_client", "call", "open_trace", "AGENT_ID", "DATAPACK_ID"]
