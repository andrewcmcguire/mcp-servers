"""
Government & regulatory tools — federal register, Congress, lobbying, and policy intelligence.

Source IDs: federal-register (97), federal-register-eo (94), regulations-gov (25),
congress-members-119 (250), stock-act-house (50), capitol-trades (11),
lda-filings (25), lda-contributions (25), openfec (20),
synthetic-congressional_trade (2.1K), kalshi-regulation (600),
polymarket-regulation (140), bis-entity-list (50), white-house-fact-sheets (50).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, timezone
from typing import Optional

from shared.db import fetch, fetchval
from shared.mcp_base import serialize

REGULATORY_SOURCES = [
    "federal-register", "federal-register-eo", "regulations-gov",
    "white-house-fact-sheets", "bis-entity-list",
]

CONGRESS_SOURCES = [
    "congress-members-119", "stock-act-house", "capitol-trades",
    "synthetic-congressional_trade",
]

LOBBYING_SOURCES = [
    "lda-filings", "lda-contributions", "openfec",
]

POLICY_MARKET_SOURCES = [
    "kalshi-regulation", "polymarket-regulation",
]


async def get_federal_register(
    query: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get Federal Register notices, rules, proposed rules, and executive orders.

    Covers 190+ federal register entries including executive orders (94) and
    standard filings (97). Search by keyword or browse recent entries.
    Returns title, category, URL, and any detected field changes.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=30)
    limit = min(limit, 200)

    conditions = [
        "d.source_id IN ('federal-register', 'federal-register-eo', 'white-house-fact-sheets')",
        "d.recorded_at >= $1",
    ]
    params: list = [since_dt]
    idx = 2

    if query:
        conditions.append(f"(d.title ILIKE ${idx} OR d.summary ILIKE ${idx})")
        params.append(f"%{query}%")
        idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.source_id, d.title, d.category, d.magnitude,
               d.changed_fields, d.url, d.recorded_at
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
        "query": {"query": query},
    })


async def get_congressional_trades(
    ticker: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get congressional stock trading activity (STOCK Act disclosures).

    Covers House STOCK Act filings (50), Capitol Trades data (11), and
    2.1K+ synthetic congressional trade signals. Each signal includes
    ticker, direction, and percentage impact. Filter by ticker.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=90)
    limit = min(limit, 200)

    conditions = [
        "d.source_id = ANY($1)",
        "d.recorded_at >= $2",
    ]
    params: list = [CONGRESS_SOURCES, since_dt]
    idx = 3

    if ticker:
        conditions.append(f"(d.ticker = ${idx} OR d.title ILIKE ${idx + 1})")
        params.append(ticker.upper())
        params.append(f"%{ticker.upper()}%")
        idx += 2

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.source_id, d.ticker, d.title, d.category,
               d.magnitude, d.changed_fields, d.url, d.recorded_at
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
        "query": {"ticker": ticker},
    })


async def get_lobbying_activity(
    query: Optional[str] = None,
    since: Optional[str] = None,
) -> dict:
    """Get lobbying disclosure filings and political contributions.

    Covers LDA lobbying filings (25), LDA contributions (25), and
    OpenFEC data (20). Search by company, lobbyist, or issue keyword.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=90)

    conditions = [
        "d.source_id = ANY($1)",
        "d.recorded_at >= $2",
    ]
    params: list = [LOBBYING_SOURCES, since_dt]
    idx = 3

    if query:
        conditions.append(f"(d.title ILIKE ${idx} OR d.summary ILIKE ${idx} OR d.changed_fields::text ILIKE ${idx})")
        params.append(f"%{query}%")
        idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.source_id, d.title, d.category,
               d.changed_fields, d.url, d.recorded_at
        FROM diffs d
        WHERE {where}
        ORDER BY d.recorded_at DESC
        LIMIT 100
    """

    rows = await fetch(sql, *params)
    return serialize({
        "results": [dict(r) for r in rows],
        "total": len(rows),
        "since": since_dt.isoformat(),
        "query": {"query": query},
    })


async def get_policy_markets(
    query: Optional[str] = None,
    since: Optional[str] = None,
) -> dict:
    """Get prediction market data for regulatory and policy outcomes.

    Covers Kalshi regulation markets (600) and Polymarket regulation
    markets (140). These markets price the probability of regulatory
    actions, policy changes, and government decisions.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=30)

    conditions = [
        "d.source_id = ANY($1)",
        "d.recorded_at >= $2",
    ]
    params: list = [POLICY_MARKET_SOURCES, since_dt]
    idx = 3

    if query:
        conditions.append(f"(d.title ILIKE ${idx} OR d.summary ILIKE ${idx})")
        params.append(f"%{query}%")
        idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.source_id, d.title, d.category,
               d.magnitude, d.changed_fields, d.url, d.recorded_at
        FROM diffs d
        WHERE {where}
        ORDER BY d.recorded_at DESC
        LIMIT 100
    """

    rows = await fetch(sql, *params)
    return serialize({
        "results": [dict(r) for r in rows],
        "total": len(rows),
        "since": since_dt.isoformat(),
        "query": {"query": query},
    })


async def search_regulatory(
    query: str,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Search across all government and regulatory data sources.

    Full-text search across Federal Register, Congress, lobbying,
    regulations.gov, entity lists, and policy markets. Returns
    matching entries from any government-related source.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=90)
    limit = min(limit, 200)

    all_sources = REGULATORY_SOURCES + CONGRESS_SOURCES + LOBBYING_SOURCES + POLICY_MARKET_SOURCES

    sql = f"""
        SELECT d.diff_id, d.source_id, d.ticker, d.title, d.category,
               d.magnitude, d.changed_fields, d.url, d.recorded_at
        FROM diffs d
        WHERE d.source_id = ANY($1)
          AND d.recorded_at >= $2
          AND (d.title ILIKE $3 OR d.summary ILIKE $3 OR d.changed_fields::text ILIKE $3)
        ORDER BY d.recorded_at DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, all_sources, since_dt, f"%{query}%", limit=limit)

    return serialize({
        "results": [dict(r) for r in rows],
        "total": len(rows),
        "since": since_dt.isoformat(),
        "query": {"query": query},
    })


TOOLS = {
    "get_federal_register": {
        "fn": get_federal_register,
        "description": get_federal_register.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords for titles/summaries"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 30 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "get_congressional_trades": {
        "fn": get_congressional_trades,
        "description": get_congressional_trades.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Filter by ticker symbol"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 90 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "get_lobbying_activity": {
        "fn": get_lobbying_activity,
        "description": get_lobbying_activity.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search by company, lobbyist, or issue"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 90 days ago)"},
            },
        },
    },
    "get_policy_markets": {
        "fn": get_policy_markets,
        "description": get_policy_markets.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords for market titles"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 30 days ago)"},
            },
        },
    },
    "search_regulatory": {
        "fn": search_regulatory,
        "description": search_regulatory.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords across all gov/regulatory data"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 90 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
            "required": ["query"],
        },
    },
}
