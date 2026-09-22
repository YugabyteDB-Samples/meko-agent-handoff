"""Connections. Two things live here so the agent scripts can stay about the agents.

  1. make_meko_mcp_client() connects to Meko. Meko's MCP server speaks Streamable
     HTTP at https://mcp.mekodata.ai/mcp, and the Meko API key goes in an
     `Authorization: Bearer <key>` header on every request.

  2. make_model() builds the model, if you use one. The scripts only call it when
     MODEL_PROVIDER is set. You bring your own key for Anthropic, Amazon Bedrock, or
     Google Vertex AI; Meko never sees it.

The two are separate on purpose. The Meko key unlocks memory, Shared Knowledge, and
the trace. A model key, if any, only powers the thinking.
"""

from __future__ import annotations

import os

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
    # Strands opens the connection the first time the client is used and sends these
    # headers with every request.
    return MCPClient(url=url, headers=headers)


# --------------------------------------------------------------------------- #
# Inference layer (bring your own model key - Meko never sees it)
# --------------------------------------------------------------------------- #
def make_model(provider: str | None = None):
    """Build a Strands model for the provider named by MODEL_PROVIDER (or the argument).

      - "anthropic": Anthropic API. Needs ANTHROPIC_API_KEY.
      - "bedrock"  : Amazon Bedrock, Strands' built-in default. Needs a Bedrock API key
                     in AWS_BEARER_TOKEN_BEDROCK (or an AWS profile or role) and
                     AWS_REGION. Returns None so Strands uses its default.
      - "vertex"   : Vertex AI through LiteLLM. No API key; it uses Application Default
                     Credentials from `gcloud auth application-default login`.
                     Reads VERTEX_PROJECT, VERTEX_LOCATION, and VERTEX_MODEL_ID.
    """
    provider = (provider or os.environ.get("MODEL_PROVIDER", "")).strip().lower()

    if provider == "vertex":
        from strands.models.litellm import LiteLLMModel

        # gemini-2.5-flash-lite in us-central1 unless VERTEX_MODEL_ID and
        # VERTEX_LOCATION say otherwise.
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
        # Check the key before importing, so a missing key gives a clear message even
        # if the anthropic package is not installed.
        if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
            raise RuntimeError("MODEL_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set.")
        from strands.models.anthropic import AnthropicModel

        model_id = os.environ.get("ANTHROPIC_MODEL_ID", "claude-sonnet-4-20250514").strip()
        return AnthropicModel(model_id=model_id)

    if provider == "bedrock":
        return None  # Strands default: Amazon Bedrock.

    raise RuntimeError(
        f"MODEL_PROVIDER is {provider!r}. Use 'anthropic', 'bedrock', or 'vertex', "
        "or leave it empty to run without a model."
    )
