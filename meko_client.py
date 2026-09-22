"""Wiring for the Meko x Strands sample.

Two things live here so `agent.py` can stay about the *agent*:

  1. `make_meko_mcp_client()` - a Strands MCPClient pointed at a Meko datapack.
     Meko's Cloud MCP server speaks Streamable HTTP at https://mcp.mekodata.ai/mcp.
     Auth is a Meko API key sent as an `Authorization: Bearer <key>` header.

  2. `make_model()` - the inference layer. You bring your own model key here; Meko
     never sees it. The default path is Vertex AI via LiteLLM using Application
     Default Credentials (no API key to manage), which is the path most Yugabyte
     folks already have through gcloud. Anthropic and Bedrock are one env var away.

The split is the point of the sample: the *Meko key* unlocks the data plane
(memory + knowledge + audit), and a *separate model key you already own* powers the
inference. Swap the model provider without touching any Meko code.
"""

from __future__ import annotations

import os

from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient


DEFAULT_MEKO_MCP_URL = "https://mcp.mekodata.ai/mcp"


# --------------------------------------------------------------------------- #
# Meko data plane (MCP)
# --------------------------------------------------------------------------- #
def _auth_headers() -> dict[str, str]:
    """Auth header for the Meko MCP endpoint: `Authorization: Bearer <MEKO_API_KEY>`.

    That's the header the Cloud endpoint expects. `MEKO_API_KEY_HEADER` exists only
    for non-standard self-hosted deployments; leave it unset for Cloud Meko.
    """
    api_key = os.environ.get("MEKO_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "MEKO_API_KEY is not set. Copy .env.example to .env and fill it in. "
            "This is the key that unlocks your datapack's memory + knowledge + audit "
            "trail. If your datapack only supports interactive OAuth, run from a client "
            "that brokers OAuth (e.g. Claude Desktop) or request a programmatic key."
        )
    header_name = os.environ.get("MEKO_API_KEY_HEADER", "Authorization").strip()
    if header_name.lower() == "authorization":
        return {"Authorization": f"Bearer {api_key}"}
    return {header_name: api_key}


def make_meko_mcp_client() -> MCPClient:
    """Return a Strands MCPClient for the configured Meko datapack.

    Strands requires MCP tools be used inside the client's context manager:

        client = make_meko_mcp_client()
        with client:
            tools = client.list_tools_sync()
            agent = Agent(model=make_model(), tools=tools)
            agent("...")
    """
    url = os.environ.get("MEKO_MCP_URL", DEFAULT_MEKO_MCP_URL).strip() or DEFAULT_MEKO_MCP_URL
    headers = _auth_headers()
    # streamablehttp_client is invoked lazily by MCPClient on first use.
    return MCPClient(lambda: streamablehttp_client(url=url, headers=headers))


def meko_env() -> dict[str, str]:
    """Read the datapack identifiers the agent needs, with a clear error if missing."""
    datapack_id = os.environ.get("MEKO_DATAPACK_ID", "").strip()
    name = os.environ.get("MEKO_DATAPACK_NAME", "").strip()
    agent_id = os.environ.get("MEKO_AGENT_ID", "discord-digest-agent").strip() \
        or "discord-digest-agent"
    if not datapack_id:
        raise RuntimeError(
            "MEKO_DATAPACK_ID is not set. Memory + knowledge tools scope to the datapack "
            "UUID and knowledgebase_search requires it. Set it in .env."
        )
    return {"name": name, "datapack_id": datapack_id, "agent_id": agent_id}


# --------------------------------------------------------------------------- #
# Inference layer (bring your own model key - Meko never sees it)
# --------------------------------------------------------------------------- #
def make_model(provider: str | None = None):
    """Build a Strands model for the chosen provider.

    provider precedence: explicit arg > MODEL_PROVIDER env > "vertex".

      - "vertex"   : Vertex AI via LiteLLM. No API key. Uses Application Default
                     Credentials (run `gcloud auth application-default login` once).
                     Reads VERTEX_MODEL_ID / VERTEX_PROJECT / VERTEX_LOCATION.
      - "anthropic": Anthropic API. Needs ANTHROPIC_API_KEY.
      - "bedrock"  : Strands' built-in default (Amazon Bedrock). Needs AWS creds +
                     Bedrock model access. Returns None so Strands uses its default.
    """
    provider = (provider or os.environ.get("MODEL_PROVIDER", "vertex")).strip().lower()

    if provider == "vertex":
        # Vertex through LiteLLM. Auth is ADC, not a key: `gcloud auth
        # application-default login` writes ~/.config/gcloud/application_default_credentials.json
        # and LiteLLM exchanges it for a short-lived token automatically.
        from strands.models.litellm import LiteLLMModel

        # Vertex config: us-central1, temperature 0.7, max_tokens 1024. Default
        # model is gemini-2.5-flash-lite, verified available in us-central1. The
        # newer gemini-3.1-flash-lite 404s ("Publisher model ... not found") in
        # some projects/regions as of 2026-07; override with VERTEX_MODEL_ID once
        # it's enabled for your project/region.
        model_id = os.environ.get("VERTEX_MODEL_ID", "vertex_ai/gemini-2.5-flash-lite").strip()
        project = os.environ.get(
            "VERTEX_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        ).strip()
        location = os.environ.get("VERTEX_LOCATION", "us-central1").strip()
        if not project:
            raise RuntimeError(
                "VERTEX_PROJECT (or GOOGLE_CLOUD_PROJECT) is not set. Point it at a GCP "
                "project you can use Vertex AI in (with roles/aiplatform.user), and run "
                "`gcloud auth application-default login` first."
            )
        return LiteLLMModel(
            model_id=model_id,
            params={
                "vertex_project": project,
                "vertex_location": location,
                "temperature": 0.7,
                "max_tokens": 1024,
            },
        )

    if provider == "anthropic":
        # Check the key before importing so a missing key gives a clear message
        # even if the optional `anthropic` extra isn't installed.
        if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
            raise RuntimeError("MODEL_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set.")
        from strands.models.anthropic import AnthropicModel

        model_id = os.environ.get("ANTHROPIC_MODEL_ID", "claude-sonnet-4-20250514").strip()
        return AnthropicModel(model_id=model_id)

    if provider == "bedrock":
        return None  # Strands default: Amazon Bedrock.

    raise RuntimeError(
        f"Unknown MODEL_PROVIDER {provider!r}. Use 'vertex', 'anthropic', or 'bedrock'."
    )
