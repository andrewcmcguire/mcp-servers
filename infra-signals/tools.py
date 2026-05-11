"""
Infrastructure & AI ecosystem tools — cert transparency, GitHub releases,
HuggingFace trending, ProductHunt, and MCP ecosystem tracking.

Source IDs: crtsh-ai-companies (482), huggingface-trending (109),
huggingface-trending-datasets (45), github-rel-* (15+ orgs, 350+ total),
github-* (bytedance, aider, cline, etc.), producthunt-ai (50),
mcp-spec/mcp-python-sdk/mcp-ts-sdk/mcp-servers-official (120+),
awesome-mcp-servers (30), various AI tool changelogs.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, timezone
from typing import Optional

from shared.db import fetch, fetchval
from shared.mcp_base import serialize


async def get_github_releases(
    org: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get GitHub release activity across tracked AI/ML organizations.

    Covers 15+ organizations including NVIDIA, Microsoft AI, Anthropic,
    Google DeepMind, Meta LLaMA, vLLM, LangChain, Mistral, Apple ML,
    LlamaIndex, and more. Each entry includes repo name, version, and URL.
    Filter by org name.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=30)
    limit = min(limit, 200)

    conditions = [
        "d.source_id LIKE 'github-rel-%'",
        "d.recorded_at >= $1",
    ]
    params: list = [since_dt]
    idx = 2

    if org:
        conditions.append(f"(d.source_id ILIKE ${idx} OR d.title ILIKE ${idx})")
        params.append(f"%{org}%")
        idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.source_id, d.title, d.magnitude,
               d.url, d.recorded_at
        FROM diffs d
        WHERE {where}
        ORDER BY d.recorded_at DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, *params, limit=limit)
    total = await fetchval(f"SELECT COUNT(*) FROM diffs d WHERE {where}", *params)

    return serialize({
        "results": [dict(r) for r in rows],
        "total": total,
        "since": since_dt.isoformat(),
        "query": {"org": org},
    })


async def get_trending_models(
    since: Optional[str] = None,
) -> dict:
    """Get trending models and datasets on HuggingFace.

    Tracks what's trending on HuggingFace including models (109 entries)
    and datasets (45 entries). Shows rank changes over time — useful for
    spotting breakout models and popular training datasets.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=30)

    sql = """
        SELECT d.diff_id, d.source_id, d.title, d.diff_type,
               d.changed_fields, d.recorded_at
        FROM diffs d
        WHERE d.source_id IN ('huggingface-trending', 'huggingface-trending-datasets')
          AND d.recorded_at >= $1
        ORDER BY d.recorded_at DESC
        LIMIT 100
    """

    rows = await fetch(sql, since_dt)
    return serialize({
        "results": [dict(r) for r in rows],
        "total": len(rows),
        "since": since_dt.isoformat(),
        "query": {},
    })


async def get_cert_transparency(
    domain: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Monitor certificate transparency events for AI companies.

    Tracks 482+ TLS certificate events across AI companies via crt.sh.
    New certificates can signal new subdomains, infrastructure changes,
    or upcoming product launches. Filter by domain name.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=30)
    limit = min(limit, 200)

    conditions = [
        "d.source_id = 'crtsh-ai-companies'",
        "d.recorded_at >= $1",
    ]
    params: list = [since_dt]
    idx = 2

    if domain:
        conditions.append(f"(d.title ILIKE ${idx} OR d.url ILIKE ${idx})")
        params.append(f"%{domain}%")
        idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.title, d.changed_fields, d.url, d.recorded_at
        FROM diffs d
        WHERE {where}
        ORDER BY d.recorded_at DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, *params, limit=limit)
    total = await fetchval(f"SELECT COUNT(*) FROM diffs d WHERE {where}", *params)

    return serialize({
        "results": [dict(r) for r in rows],
        "total": total,
        "since": since_dt.isoformat(),
        "query": {"domain": domain},
    })


async def get_mcp_ecosystem(
    since: Optional[str] = None,
) -> dict:
    """Track MCP (Model Context Protocol) ecosystem activity.

    Monitors the MCP spec, Python SDK, TypeScript SDK, official servers,
    and the awesome-mcp-servers list. Returns recent changes, releases,
    and community activity.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=30)

    mcp_sources = [
        "mcp-spec", "mcp-python-sdk", "mcp-ts-sdk", "mcp-servers-official",
        "awesome-mcp-servers",
    ]

    sql = """
        SELECT d.diff_id, d.source_id, d.title, d.diff_type,
               d.changed_fields, d.url, d.recorded_at
        FROM diffs d
        WHERE d.source_id = ANY($1)
          AND d.recorded_at >= $2
        ORDER BY d.recorded_at DESC
        LIMIT 100
    """

    rows = await fetch(sql, mcp_sources, since_dt)
    return serialize({
        "results": [dict(r) for r in rows],
        "total": len(rows),
        "since": since_dt.isoformat(),
        "query": {},
    })


async def search_infra(
    query: str,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Search across all infrastructure and AI ecosystem signals.

    Full-text search across GitHub releases, HuggingFace trending,
    certificate transparency, ProductHunt AI, MCP ecosystem, and
    AI tool changelogs. Returns matching entries from any infra source.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=90)
    limit = min(limit, 200)

    sql = f"""
        SELECT d.diff_id, d.source_id, d.title, d.diff_type,
               d.magnitude, d.changed_fields, d.url, d.recorded_at
        FROM diffs d
        WHERE (d.source_id LIKE 'github-%%' OR d.source_id LIKE 'huggingface-%%'
               OR d.source_id = 'crtsh-ai-companies' OR d.source_id LIKE 'mcp-%%'
               OR d.source_id = 'awesome-mcp-servers' OR d.source_id LIKE 'producthunt-%%'
               OR d.source_id LIKE 'ph-%%' OR d.source_id LIKE '%%changelog%%')
          AND d.recorded_at >= $1
          AND (d.title ILIKE $2 OR d.summary ILIKE $2)
        ORDER BY d.recorded_at DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, since_dt, f"%{query}%", limit=limit)

    return serialize({
        "results": [dict(r) for r in rows],
        "total": len(rows),
        "since": since_dt.isoformat(),
        "query": {"query": query},
    })


TOOLS = {
    "get_github_releases": {
        "fn": get_github_releases,
        "description": get_github_releases.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "org": {"type": "string", "description": "Organization filter (e.g. 'nvidia', 'anthropic', 'meta-llama')"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 30 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "get_trending_models": {
        "fn": get_trending_models,
        "description": get_trending_models.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 30 days ago)"},
            },
        },
    },
    "get_cert_transparency": {
        "fn": get_cert_transparency,
        "description": get_cert_transparency.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Domain filter (e.g. 'openai.com', 'anthropic.com')"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 30 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "get_mcp_ecosystem": {
        "fn": get_mcp_ecosystem,
        "description": get_mcp_ecosystem.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 30 days ago)"},
            },
        },
    },
    "search_infra": {
        "fn": search_infra,
        "description": search_infra.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords across all infra/ecosystem data"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 90 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
            "required": ["query"],
        },
    },
}
