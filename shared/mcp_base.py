"""
Base factory for creating MCP servers with Starlette + Streamable HTTP transport.

Each domain server calls `create_mcp_app()` to get a Starlette app wired up
with the MCP Streamable HTTP transport, auth, and health check.
"""

import json
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .auth import validate_bearer_token
from .db import close_pool, get_pool

logger = logging.getLogger(__name__)


class MCPJSONEncoder(json.JSONEncoder):
    """Handle Postgres types that aren't natively JSON serializable."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, memoryview):
            return bytes(obj).hex()
        return super().default(obj)


def serialize(obj: Any) -> Any:
    """Recursively serialize an object to JSON-safe types."""
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize(i) for i in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, memoryview):
        return bytes(obj).hex()
    return obj


def create_mcp_app(
    server_name: str,
    mcp_server: Server,
    port: int,
):
    """
    Create an ASGI application with MCP Streamable HTTP transport, auth, and lifecycle.
    Uses Streamable HTTP instead of SSE to work through Cloudflare tunnels.
    """

    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        json_response=False,
        stateless=False,
    )

    async def _send_json_error(send, status: int, error: str):
        body = json.dumps({"error": error}).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode()],
            ],
        })
        await send({"type": "http.response.body", "body": body})

    async def _check_auth_asgi(scope, send) -> bool:
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        if not auth_header.startswith("Bearer "):
            await _send_json_error(send, 401, "Missing or invalid Authorization header. Use: Bearer mcp_<your_key>")
            return False
        api_key = auth_header[7:].strip()
        error = await validate_bearer_token(api_key)
        if error:
            status = 429 if "Rate limit" in error else 401
            await _send_json_error(send, status, error)
            return False
        return True

    async def handle_mcp(scope, receive, send):
        if not await _check_auth_asgi(scope, send):
            return
        await session_manager.handle_request(scope, receive, send)

    async def health(request: Request):
        return JSONResponse({"status": "ok", "server": server_name, "port": port})

    async def root(request: Request):
        return JSONResponse({
            "server": server_name,
            "transport": "streamable-http",
            "endpoints": {
                "mcp": "/mcp",
                "health": "/health",
            },
        })

    @asynccontextmanager
    async def lifespan(app):
        logger.info(f"Starting {server_name} MCP server on port {port}")
        try:
            await get_pool()
            logger.info(f"{server_name}: database pool ready")
        except Exception as e:
            logger.warning(f"{server_name}: database not available at startup: {e}")
        async with session_manager.run():
            yield
        await close_pool()
        logger.info(f"{server_name} MCP server stopped")

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

    return app
