"""
MCP Gateway — single public entry point for all 6 MCP servers.

Provides:
  POST /mcp/request-key        — request an API key
  GET  /mcp/servers             — list available servers with connection info
  GET  /mcp/health              — aggregate health check
  GET  /                        — gateway info
  /s/{server}/mcp               — proxy to individual MCP server (POST/GET/DELETE)

One Cloudflare tunnel → one gateway → six MCP servers.
Clients connect via /s/{server-name}/mcp through the gateway URL.

Usage:
    python gateway.py
"""

import json
import logging
import os
import re
import secrets
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

import asyncpg
import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from shared.config import get_postgres_config

PORT = 8099
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-gateway")

_pool = None

SERVERS = {
    "edgar-signals": {
        "port": 8100,
        "description": "SEC filings, insider trades, Form D stealth fundraises, 8-K events, 13F holdings",
        "tools": ["search_filings", "get_insider_trades", "get_insider_clusters", "get_8k_events", "get_13f_holdings"],
        "example_query": "AI companies that filed Form D in the last 14 days with no press coverage",
        "data_points": "32K+",
    },
    "ai-labs": {
        "port": 8101,
        "description": "60+ AI orgs across HuggingFace, GitHub, arXiv, blogs — model releases, papers, research",
        "tools": ["get_lab_activity", "get_daily_papers", "search_research", "get_github_activity", "get_model_releases"],
        "example_query": "What did DeepSeek, Qwen, and Mistral ship this week?",
        "data_points": "6K+",
    },
    "earnings-intel": {
        "port": 8102,
        "description": "Earnings events, analyst revisions, earnings movers, NASDAQ calendar",
        "tools": ["get_earnings_events", "get_analyst_revisions", "search_earnings", "get_earnings_movers", "get_earnings_schedule"],
        "example_query": "Which stocks moved 10%+ on earnings this month?",
        "data_points": "13.7K+",
    },
    "govcon": {
        "port": 8103,
        "description": "Federal Register, congressional trades, lobbying disclosures, policy prediction markets",
        "tools": ["get_federal_register", "get_congressional_trades", "get_lobbying_activity", "get_policy_markets", "search_regulatory"],
        "example_query": "Congressional stock trades in AI companies this quarter",
        "data_points": "3.5K+",
    },
    "hiring-signals": {
        "port": 8104,
        "description": "Job postings across Greenhouse, Ashby, Lever — hiring velocity, first-hire detection",
        "tools": ["get_new_roles", "detect_first_hire", "get_hiring_velocity", "search_roles", "get_company_snapshot"],
        "example_query": "Companies that posted their first ML Engineer role this month",
        "data_points": "3.6K+",
    },
    "infra-signals": {
        "port": 8105,
        "description": "Cert transparency, GitHub releases, HuggingFace trending, MCP ecosystem tracking",
        "tools": ["get_github_releases", "get_trending_models", "get_cert_transparency", "get_mcp_ecosystem", "search_infra"],
        "example_query": "NVIDIA GitHub releases this month",
        "data_points": "1K+",
    },
}


async def _get_pool():
    global _pool
    if _pool is None:
        pg = get_postgres_config()
        _pool = await asyncpg.create_pool(
            host=pg["host"],
            port=pg["port"],
            database=pg["database"],
            user=pg.get("user", "postgres"),
            password=pg.get("password", ""),
            min_size=1,
            max_size=5,
        )
        async with _pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS public.mcp_api_keys (
                    api_key TEXT PRIMARY KEY,
                    owner TEXT,
                    email TEXT,
                    use_case TEXT,
                    referral TEXT,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    daily_count INT DEFAULT 0,
                    last_used DATE DEFAULT CURRENT_DATE,
                    approved BOOLEAN DEFAULT TRUE
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS public.mcp_key_requests (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    use_case TEXT,
                    referral TEXT,
                    api_key TEXT,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    status TEXT DEFAULT 'approved'
                )
            """)
    return _pool


def _generate_key():
    return f"mcp_{secrets.token_urlsafe(24)}"


async def request_key(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip()
    use_case = (body.get("use_case") or body.get("what_are_you_building") or "").strip()
    referral = (body.get("referral") or body.get("how_did_you_find_this") or "").strip()

    if not name or not email:
        return JSONResponse({"error": "name and email are required"}, status_code=400)

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return JSONResponse({"error": "Invalid email format"}, status_code=400)

    pool = await _get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT api_key FROM public.mcp_key_requests WHERE email = $1 AND status = 'approved'",
            email,
        )
        if existing:
            return JSONResponse({
                "api_key": existing["api_key"],
                "message": "You already have a key. Here it is again.",
                "rate_limit": "100 requests/day",
                "servers": {k: f"http://mcp.andrewcmcguire.com:{v['port']}/mcp" for k, v in SERVERS.items()},
            })

        key_count = await conn.fetchval("SELECT COUNT(*) FROM public.mcp_api_keys")
        if key_count >= 50:
            return JSONResponse({
                "error": "All 50 free API keys have been claimed. Email andrew@andrewcmcguire.com for access.",
            }, status_code=503)

        api_key = _generate_key()

        await conn.execute(
            """INSERT INTO public.mcp_api_keys (api_key, owner, email, use_case, referral)
               VALUES ($1, $2, $3, $4, $5)""",
            api_key, name, email, use_case, referral,
        )
        await conn.execute(
            """INSERT INTO public.mcp_key_requests (name, email, use_case, referral, api_key, status)
               VALUES ($1, $2, $3, $4, $5, 'approved')""",
            name, email, use_case, referral, api_key,
        )

    logger.info(f"New API key issued to {name} <{email}>")

    return JSONResponse({
        "api_key": api_key,
        "message": f"Welcome, {name}. Your key is ready.",
        "rate_limit": "100 requests/day",
        "connect": {
            "transport": "Streamable HTTP",
            "auth": f"Bearer {api_key}",
            "servers": {k: {"url": f"/mcp", "port": v["port"]} for k, v in SERVERS.items()},
        },
        "quick_start": {
            "claude_desktop": "Add to claude_desktop_config.json under mcpServers",
            "cursor": "Add to .cursor/mcp.json",
            "python": "from mcp.client.streamable_http import streamablehttp_client",
        },
    })


async def list_servers(request: Request):
    host = request.headers.get("host", "localhost")
    result = {}
    for name, info in SERVERS.items():
        result[name] = {
            "description": info["description"],
            "tools": info["tools"],
            "data_points": info["data_points"],
            "example_query": info["example_query"],
            "endpoint": f"http://{host.split(':')[0]}:{info['port']}/mcp",
            "transport": "streamable-http",
            "health": f"http://{host.split(':')[0]}:{info['port']}/health",
        }
    return JSONResponse({
        "servers": result,
        "total_servers": len(result),
        "total_tools": sum(len(s["tools"]) for s in SERVERS.values()),
        "auth": "Bearer <your_api_key>",
        "request_key": f"POST http://{host}/mcp/request-key",
        "rate_limit": "100 requests/day per key",
    })


async def health(request: Request):
    import httpx
    results = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, info in SERVERS.items():
            try:
                r = await client.get(f"http://localhost:{info['port']}/health")
                results[name] = {"status": "ok", "port": info["port"]}
            except Exception:
                results[name] = {"status": "down", "port": info["port"]}

    up_count = sum(1 for v in results.values() if v["status"] == "ok")
    return JSONResponse({
        "status": "ok" if up_count > 0 else "degraded",
        "servers_up": up_count,
        "servers_total": len(SERVERS),
        "servers": results,
    })


async def root(request: Request):
    host = request.headers.get("host", "localhost")
    return JSONResponse({
        "service": "MCP Intelligence Gateway",
        "operator": "Andrew McGuire",
        "description": "Six MCP servers querying a 1,470-source intelligence pipeline. SEC filings. AI lab releases. Earnings calls. Hiring signals. Government contracts. Infrastructure changes.",
        "endpoints": {
            "servers": f"http://{host}/mcp/servers",
            "request_key": f"POST http://{host}/mcp/request-key",
            "health": f"http://{host}/mcp/health",
        },
        "website": "https://andrewcmcguire.com/mcp",
        "transport": "streamable-http",
        "rate_limit": "100 requests/day. First 50 keys free.",
    })


async def _proxy_to_server(scope, receive, send):
    """Proxy /s/{server-name}/mcp to the appropriate backend MCP server."""
    import httpx

    path = scope.get("path", "")
    parts = path.split("/")
    if len(parts) < 4 or parts[1] != "s" or parts[3] != "mcp":
        body = json.dumps({"error": f"Invalid proxy path: {path}. Use /s/{{server-name}}/mcp"}).encode()
        await send({"type": "http.response.start", "status": 404,
                     "headers": [[b"content-type", b"application/json"]]})
        await send({"type": "http.response.body", "body": body})
        return

    server_name = parts[2]
    if server_name not in SERVERS:
        body = json.dumps({"error": f"Unknown server: {server_name}", "available": list(SERVERS.keys())}).encode()
        await send({"type": "http.response.start", "status": 404,
                     "headers": [[b"content-type", b"application/json"]]})
        await send({"type": "http.response.body", "body": body})
        return

    backend_port = SERVERS[server_name]["port"]
    backend_url = f"http://localhost:{backend_port}/mcp"
    method = scope.get("method", "GET")

    request_headers = {}
    for key, value in scope.get("headers", []):
        header_name = key.decode().lower()
        if header_name in ("authorization", "content-type", "accept", "mcp-session-id"):
            request_headers[header_name] = value.decode()

    request_body = b""
    if method in ("POST", "PUT", "PATCH"):
        while True:
            message = await receive()
            request_body += message.get("body", b"")
            if not message.get("more_body", False):
                break

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                resp = await client.get(backend_url, headers=request_headers)
            elif method == "POST":
                resp = await client.post(backend_url, headers=request_headers, content=request_body)
            elif method == "DELETE":
                resp = await client.delete(backend_url, headers=request_headers)
            else:
                resp = await client.request(method, backend_url, headers=request_headers, content=request_body)

        response_headers = []
        for k, v in resp.headers.items():
            if k.lower() not in ("transfer-encoding", "content-encoding"):
                response_headers.append([k.encode(), v.encode()])

        await send({"type": "http.response.start", "status": resp.status_code,
                     "headers": response_headers})
        await send({"type": "http.response.body", "body": resp.content})

    except Exception as e:
        logger.exception(f"Proxy error for {server_name}")
        body = json.dumps({"error": f"Backend {server_name} unavailable: {str(e)}"}).encode()
        await send({"type": "http.response.start", "status": 502,
                     "headers": [[b"content-type", b"application/json"]]})
        await send({"type": "http.response.body", "body": body})


starlette_app = Starlette(
    debug=False,
    routes=[
        Route("/", root),
        Route("/mcp/request-key", request_key, methods=["POST"]),
        Route("/mcp/servers", list_servers),
        Route("/mcp/health", health),
    ],
)

starlette_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


async def app(scope, receive, send):
    path = scope.get("path", "")
    if scope["type"] == "http" and path.startswith("/s/"):
        await _proxy_to_server(scope, receive, send)
    else:
        await starlette_app(scope, receive, send)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
