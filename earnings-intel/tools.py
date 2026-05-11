"""
Earnings intel tools — earnings, analyst revisions, and market signal intelligence.

Source IDs: synthetic-earnings (3.8K), synthetic-analyst_revision (9.8K),
nasdaq-earnings (83), analyst-revisions (10), earnings-transcript (1).
All data is in the diffs table (records table is empty).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, timezone
from typing import Optional

from shared.db import fetch, fetchval
from shared.mcp_base import serialize

EARNINGS_SOURCES = [
    "synthetic-earnings", "nasdaq-earnings", "earnings-transcript",
    "hf-sp500-transcripts",
]

ANALYST_SOURCES = [
    "synthetic-analyst_revision", "analyst-revisions",
]


async def get_earnings_events(
    ticker: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get earnings events including beats, misses, and scheduled calls.

    Covers synthetic earnings signals (6K+), NASDAQ earnings calendar,
    and earnings transcripts. Returns ticker, direction, percentage change,
    and event details. Filter by ticker symbol.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=30)
    limit = min(limit, 200)

    conditions = [
        "d.source_id = ANY($1)",
        "d.recorded_at >= $2",
    ]
    params: list = [EARNINGS_SOURCES, since_dt]
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


async def get_analyst_revisions(
    ticker: Optional[str] = None,
    direction: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get analyst revision signals — upgrades, downgrades, and price target changes.

    Covers 9.8K+ synthetic analyst revision signals plus live analyst revision
    data. Each signal includes direction (long/short), percentage change,
    and archetype (upgrade, downgrade, etc.). Filter by ticker or direction.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=30)
    limit = min(limit, 200)

    conditions = [
        "d.source_id = ANY($1)",
        "d.recorded_at >= $2",
    ]
    params: list = [ANALYST_SOURCES, since_dt]
    idx = 3

    if ticker:
        conditions.append(f"(d.ticker = ${idx} OR d.title ILIKE ${idx + 1})")
        params.append(ticker.upper())
        params.append(f"%{ticker.upper()}%")
        idx += 2

    if direction:
        conditions.append(f"d.changed_fields->>'direction' = ${idx}")
        params.append(direction.lower())
        idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.source_id, d.ticker, d.title, d.category,
               d.magnitude, d.changed_fields, d.recorded_at
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
        "query": {"ticker": ticker, "direction": direction},
    })


async def search_earnings(
    query: str,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Full-text search across earnings events and analyst revisions.

    Search for specific companies, sectors, or signal types across all
    earnings and analyst data. Returns matching diffs with full context.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=90)
    limit = min(limit, 200)

    all_sources = EARNINGS_SOURCES + ANALYST_SOURCES

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
    total = await fetchval(
        "SELECT COUNT(*) FROM diffs d WHERE d.source_id = ANY($1) AND d.recorded_at >= $2 AND (d.title ILIKE $3 OR d.summary ILIKE $3 OR d.changed_fields::text ILIKE $3)",
        all_sources, since_dt, f"%{query}%",
    )

    return serialize({
        "results": [dict(r) for r in rows],
        "total": total,
        "since": since_dt.isoformat(),
        "query": {"query": query},
    })


async def get_earnings_movers(
    min_pct_change: float = 5.0,
    direction: Optional[str] = None,
    since: Optional[str] = None,
) -> dict:
    """Get stocks with significant earnings-driven moves.

    Filters synthetic earnings signals by minimum percentage change.
    Returns tickers that moved significantly on earnings, with direction
    (long/short) and magnitude. Great for finding earnings surprises.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=30)

    conditions = [
        "d.source_id = 'synthetic-earnings'",
        "d.recorded_at >= $1",
        f"(d.changed_fields->>'pct_change')::numeric >= $2 OR (d.changed_fields->>'pct_change')::numeric <= -$2",
    ]
    params: list = [since_dt, abs(min_pct_change)]
    idx = 3

    if direction:
        conditions.append(f"d.changed_fields->>'direction' = ${idx}")
        params.append(direction.lower())
        idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.ticker, d.title, d.changed_fields, d.recorded_at
        FROM diffs d
        WHERE {where}
        ORDER BY (d.changed_fields->>'pct_change')::numeric DESC
        LIMIT 100
    """

    rows = await fetch(sql, *params)
    return serialize({
        "results": [dict(r) for r in rows],
        "total": len(rows),
        "since": since_dt.isoformat(),
        "query": {"min_pct_change": min_pct_change, "direction": direction},
    })


async def get_earnings_schedule(
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get upcoming and recent earnings dates from NASDAQ calendar.

    Returns scheduled earnings calls with ticker, date, and timing
    (before-market, after-hours). Useful for planning around earnings events.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=7)
    limit = min(limit, 200)

    sql = f"""
        SELECT d.diff_id, d.ticker, d.title, d.category,
               d.url, d.recorded_at
        FROM diffs d
        WHERE d.source_id = 'nasdaq-earnings'
          AND d.recorded_at >= $1
        ORDER BY d.recorded_at DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, since_dt, limit=limit)
    return serialize({
        "results": [dict(r) for r in rows],
        "total": len(rows),
        "since": since_dt.isoformat(),
        "query": {},
    })


TOOLS = {
    "get_earnings_events": {
        "fn": get_earnings_events,
        "description": get_earnings_events.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol (e.g. 'AAPL', 'NVDA')"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 30 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "get_analyst_revisions": {
        "fn": get_analyst_revisions,
        "description": get_analyst_revisions.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol"},
                "direction": {"type": "string", "enum": ["long", "short"], "description": "Filter by signal direction"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 30 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "search_earnings": {
        "fn": search_earnings,
        "description": search_earnings.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords (company, sector, signal type)"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 90 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
            "required": ["query"],
        },
    },
    "get_earnings_movers": {
        "fn": get_earnings_movers,
        "description": get_earnings_movers.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "min_pct_change": {"type": "number", "default": 5.0, "description": "Minimum absolute % move"},
                "direction": {"type": "string", "enum": ["long", "short"], "description": "Filter by direction"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 30 days ago)"},
            },
        },
    },
    "get_earnings_schedule": {
        "fn": get_earnings_schedule,
        "description": get_earnings_schedule.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 7 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
}
