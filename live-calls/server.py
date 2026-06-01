"""
Live Calls MCP Server — live earnings call intelligence, transcripts, and deception scoring.

Port: 8106
Tables: earnings_events, transcripts, earnings_insights, live_alerts, live_call_progress

Exposes tools for call insights, transcript retrieval, deception detection,
live monitoring alerts, upcoming call schedules, and full-text content search.
"""

import json
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server import Server
from mcp.types import Tool, TextContent

from shared.mcp_base import create_mcp_app, MCPJSONEncoder
from .tools import TOOLS

PORT = 8106
SERVER_NAME = "live-calls"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(SERVER_NAME)

mcp_server = Server(SERVER_NAME)


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name=name, description=meta["description"], inputSchema=meta["schema"])
        for name, meta in TOOLS.items()
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name not in TOOLS:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    try:
        result = await TOOLS[name]["fn"](**arguments)
        return [TextContent(type="text", text=json.dumps(result, cls=MCPJSONEncoder))]
    except Exception as e:
        logger.exception(f"Error in tool {name}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


app = create_mcp_app(SERVER_NAME, mcp_server, PORT)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
