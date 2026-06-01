"""
Salesforce 360 MCP Server + Chat Web App

Port: 8107

Two interfaces:
  1. MCP protocol at /mcp — for Claude Code, Claude Desktop, Cursor
  2. Chat web app at / — browser-based chat UI for salespeople

The chat UI sends messages to Claude API, which calls the Salesforce
tools, and returns natural language responses. No MCP client needed.

Setup:
    export SF_USERNAME="you@company.com"
    export SF_PASSWORD="yourpassword"
    export SF_SECURITY_TOKEN="your_token"
    export ANTHROPIC_API_KEY="sk-ant-..."
    python -m salesforce-360.server
    # Open http://localhost:8107
"""

import json
import logging
import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse, FileResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles

from .tools import TOOLS

PORT = 8107
SERVER_NAME = "salesforce-360"
STATIC_DIR = Path(__file__).parent / "static"

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


async def chat_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    message = body.get("message", "").strip()
    history = body.get("history", [])

    if not message:
        return JSONResponse({"error": "No message provided"}, status_code=400)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return JSONResponse({
            "error": "ANTHROPIC_API_KEY not set. Add it to your environment variables and restart the server."
        }, status_code=500)

    try:
        from .chat import handle_chat
        result = await handle_chat(
            messages=[{"role": "user", "content": message}],
            conversation_history=history,
        )
        return JSONResponse(result)
    except Exception as e:
        logger.exception("Chat error")
        return JSONResponse({"error": str(e)}, status_code=500)


async def health(request: Request):
    sf_status = "not_configured"
    sf_instance = None
    try:
        from .sf_client import _get_sf
        sf = _get_sf()
        sf_status = "ok"
        sf_instance = sf.sf_instance
    except Exception as e:
        sf_status = str(e)

    anthropic_status = "ok" if os.environ.get("ANTHROPIC_API_KEY") else "not_configured"

    status = "ok" if sf_status == "ok" else "error"
    return JSONResponse({
        "status": status,
        "server": SERVER_NAME,
        "instance": sf_instance,
        "salesforce": sf_status,
        "anthropic_api": anthropic_status,
    })


async def index(request: Request):
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return JSONResponse({
        "server": SERVER_NAME,
        "description": "Headless Salesforce 360 — account intelligence for sales teams",
        "tools": list(TOOLS.keys()),
        "transport": "streamable-http",
        "endpoints": {"mcp": "/mcp", "chat": "/chat", "health": "/health"},
    })


@asynccontextmanager
async def lifespan(app):
    logger.info(f"Starting {SERVER_NAME} on port {PORT}")
    logger.info(f"Chat UI: http://localhost:{PORT}")
    logger.info(f"MCP endpoint: http://localhost:{PORT}/mcp")
    async with session_manager.run():
        yield
    logger.info(f"{SERVER_NAME} stopped")


starlette_app = Starlette(
    debug=False,
    lifespan=lifespan,
    routes=[
        Route("/", index),
        Route("/chat", chat_endpoint, methods=["POST"]),
        Route("/health", health),
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
