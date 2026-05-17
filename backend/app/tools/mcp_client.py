"""
MCP client — calls the local MCP server over HTTP (SSE transport).

The MCP server exposes medical reference tools:
  • get_medical_guidelines(symptom)
  • check_red_flags(symptoms_text)

Usage example inside a LangGraph node:
    from app.tools.mcp_client import MCPClient
    client = MCPClient()
    guidelines = client.get_medical_guidelines("fièvre")
"""
from __future__ import annotations
import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8001")


class MCPClient:
    """Lightweight HTTP client for the local MCP medical server."""

    def __init__(self, base_url: str = MCP_SERVER_URL, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _call_tool(self, tool_name: str, arguments: dict) -> str:
        """Generic tool call via the MCP /tools/call endpoint."""
        try:
            resp = requests.post(
                f"{self.base_url}/tools/call",
                json={"name": tool_name, "arguments": arguments},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            # MCP response: {"content": [{"type": "text", "text": "..."}]}
            content = data.get("content", [])
            return " ".join(
                block.get("text", "") for block in content if block.get("type") == "text"
            )
        except Exception as exc:
            logger.warning("MCP tool call failed (%s): %s", tool_name, exc)
            return f"[MCP indisponible: {exc}]"

    # ── Public helpers ────────────────────────────────────────────────────────

    def get_medical_guidelines(self, symptom: str) -> str:
        """Returns clinical guidelines for a given symptom keyword."""
        return self._call_tool("get_medical_guidelines", {"symptom": symptom})

    def check_red_flags(self, symptoms_text: str) -> str:
        """Checks whether the symptoms text contains known red flags."""
        return self._call_tool("check_red_flags", {"symptoms_text": symptoms_text})

    def list_tools(self) -> list[dict]:
        """Lists all tools exposed by the MCP server."""
        try:
            resp = requests.get(f"{self.base_url}/tools", timeout=self.timeout)
            resp.raise_for_status()
            return resp.json().get("tools", [])
        except Exception as exc:
            logger.warning("MCP list_tools failed: %s", exc)
            return []
