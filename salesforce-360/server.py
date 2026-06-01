"""
Salesforce 360 MCP Server — headless account intelligence for sales teams.

Port: 8107
Auth: Salesforce credentials via environment variables (not the gateway API key)

This server connects to YOUR Salesforce org and gives you a full 360 view
of your accounts, pipeline, and day — without opening the Salesforce UI.

Designed to run locally or on your own infrastructure with your SF credentials.
"""

import json
import logging
import sys
import os
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .tools import TOOLS

PORT = 8107
SERVER_NAME = "salesforce-360"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(SERVER_NAME)

mcp_server = Server(SERVER_NAME)


class SFJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        from datetime import date, datetime
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


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
        return [TextContent(type="text", text=json.dumps(result, cls=SFJSONEncoder))]
    except Exception as e:
        logger.exception(f"Error in tool {name}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


session_manager = StreamableHTTPSessionManager(
    app=mcp_server,
    json_response=False,
    stateless=False,
)


async def handle_mcp(scope, receive, send):
    await session_manager.handle_request(scope, receive, send)


async def health(request: Request):
    try:
        from .sf_client import _get_sf
        sf = _get_sf()
        return JSONResponse({"status": "ok", "server": SERVER_NAME, "instance": sf.sf_instance})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=503)


async def root(request: Request):
    return JSONResponse({
        "server": SERVER_NAME,
        "description": "Headless Salesforce 360 — account intelligence for sales teams via MCP",
        "tools": list(TOOLS.keys()),
        "transport": "streamable-http",
        "endpoints": {"mcp": "/mcp", "health": "/health"},
        "setup": "Set SF_USERNAME, SF_PASSWORD, SF_SECURITY_TOKEN as environment variables",
    })


@asynccontextmanager
async def lifespan(app):
    logger.info(f"Starting {SERVER_NAME} on port {PORT}")
    async with session_manager.run():
        yield
    logger.info(f"{SERVER_NAME} stopped")


starlette_app = Starlette(
    debug=False,
    lifespan=lifespan,
    routes=[
        Route("/health", health),
        Route("/", root),
    ],
)


async def app(scope, receive, send):
    path = scope.get("path", "")
    if scope["type"] == "http" and path == "/mcp":
        await handle_mcp(scope, receive, send)
    else:
        await starlette_app(scope, receive, send)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
