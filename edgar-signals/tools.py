"""
EDGAR signal tools — SEC filing intelligence.

Source IDs: edgar-form4, edgar-8k, edgar-10q, edgar-10k, edgar-13f, edgar-13d,
edgar-ai-companies, edgar-bdc-ARCC, unusualwhales-insider, synthetic-insider_trade,
synthetic-sec_filing, sec-13f-holdings, sec-proxy-people.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, timezone
from typing import Optional

from shared.db import fetch, fetchval
from shared.mcp_base import serialize

EDGAR_SOURCES = [
    "edgar-form4", "edgar-8k", "edgar-10q", "edgar-10k",
    "edgar-13f", "edgar-13d", "edgar-ai-companies",
    "edgar-bdc-ARCC", "edgar-djt",
    "sec-13f-holdings", "sec-proxy-people",
    "synthetic-sec_filing",
]

INSIDER_SOURCES = [
    "edgar-form4", "unusualwhales-insider", "synthetic-insider_trade",
]


async def search_filings(
    query: str,
    form_type: Optional[str] = None,
    ticker: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """Search across SEC filing diffs by keyword, form type, ticker, and date range.

    Searches edgar-form4 (25K+), edgar-8k (4K+), edgar-10q, edgar-10k, edgar-13f,
    and other EDGAR sources. Returns matching filings with title, ticker, and URL.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=30)
    limit = min(limit, 100)

    conditions = ["d.recorded_at >= $1", "d.source_id = ANY($2)"]
    params: list = [since_dt, EDGAR_SOURCES]
    idx = 3

    conditions.append(f"(d.title ILIKE ${idx} OR d.summary ILIKE ${idx})")
    params.append(f"%{query}%")
    idx += 1

    if form_type:
        conditions.append(f"(d.source_id ILIKE ${idx} OR d.title ILIKE ${idx})")
        params.append(f"%{form_type}%")
        idx += 1

    if ticker:
        conditions.append(f"(d.ticker = ${idx} OR d.title ILIKE ${idx + 1})")
        params.append(ticker.upper())
        params.append(f"%({ticker.upper()})%")
        idx += 2

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.record_id, d.source_id, d.diff_type, d.ticker,
               d.category, d.title, d.magnitude, d.summary, d.url, d.recorded_at
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
        "query": {"query": query, "form_type": form_type, "ticker": ticker},
    })


async def get_insider_trades(
    ticker: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get insider trading activity from Form 4 filings and Unusual Whales data.

    Covers 25K+ Form 4 filings plus enriched insider trade data from
    Unusual Whales (price, amount, sector). Filter by ticker.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=30)
    limit = min(limit, 200)

    conditions = [
        "d.source_id = ANY($1)",
        "d.recorded_at >= $2",
    ]
    params: list = [INSIDER_SOURCES, since_dt]
    idx = 3

    if ticker:
        conditions.append(f"(d.ticker = ${idx} OR d.title ILIKE ${idx + 1})")
        params.append(ticker.upper())
        params.append(f"%{ticker.upper()}%")
        idx += 2

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.source_id, d.ticker, d.title, d.category,
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
        "query": {"ticker": ticker},
    })


async def get_insider_clusters(
    ticker: Optional[str] = None,
    days: int = 30,
    min_trades: int = 3,
) -> dict:
    """Detect clusters of insider activity by ticker using Form 4 and Unusual Whales data.

    Groups insider transactions by ticker, returning clusters where trade count
    meets the threshold. Clustered insider buying/selling often precedes price moves.
    """
    since_dt = datetime.now(timezone.utc) - timedelta(days=days)

    conditions = [
        "d.source_id = ANY($1)",
        "d.recorded_at >= $2",
        "d.ticker IS NOT NULL",
    ]
    params: list = [INSIDER_SOURCES, since_dt]
    idx = 3

    if ticker:
        conditions.append(f"d.ticker = ${idx}")
        params.append(ticker.upper())
        idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.ticker,
               COUNT(*) AS trade_count,
               MIN(d.recorded_at) AS first_trade,
               MAX(d.recorded_at) AS last_trade,
               array_agg(DISTINCT d.source_id) AS sources
        FROM diffs d
        WHERE {where}
        GROUP BY d.ticker
        HAVING COUNT(*) >= ${idx}
        ORDER BY trade_count DESC
        LIMIT 50
    """
    params.append(min_trades)

    rows = await fetch(sql, *params)
    return serialize({
        "results": [dict(r) for r in rows],
        "total": len(rows),
        "since": since_dt.isoformat(),
        "query": {"ticker": ticker, "days": days, "min_trades": min_trades},
    })


async def get_8k_events(
    since: Optional[str] = None,
    item_type: Optional[str] = None,
    ticker: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get 8-K material event filings.

    Common item types (parsed from title):
    - 1.01: Material definitive agreement
    - 2.01: Acquisition or disposition
    - 5.02: Departure/election of directors/officers
    - 7.01: Regulation FD disclosure
    - 8.01: Other events

    Filter by item type substring or ticker.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=7)
    limit = min(limit, 200)

    conditions = [
        "d.source_id = 'edgar-8k'",
        "d.recorded_at >= $1",
    ]
    params: list = [since_dt]
    idx = 2

    if item_type:
        conditions.append(f"d.title ILIKE ${idx}")
        params.append(f"% {item_type}%")
        idx += 1

    if ticker:
        conditions.append(f"(d.ticker = ${idx} OR d.title ILIKE ${idx + 1})")
        params.append(ticker.upper())
        params.append(f"%({ticker.upper()})%")
        idx += 2

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.ticker, d.title, d.category,
               d.magnitude, d.url, d.recorded_at
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
        "query": {"item_type": item_type, "ticker": ticker},
    })


async def get_13f_holdings(
    since: Optional[str] = None,
    ticker: Optional[str] = None,
) -> dict:
    """Get 13F institutional holdings filings.

    Tracks institutional investor portfolio disclosures required for managers
    with $100M+ AUM. Useful for tracking hedge fund positions and big money flows.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=90)

    conditions = [
        "d.source_id IN ('edgar-13f', 'sec-13f-holdings')",
        "d.recorded_at >= $1",
    ]
    params: list = [since_dt]
    idx = 2

    if ticker:
        conditions.append(f"(d.ticker = ${idx} OR d.title ILIKE ${idx + 1})")
        params.append(ticker.upper())
        params.append(f"%{ticker.upper()}%")
        idx += 2

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.ticker, d.title, d.category,
               d.magnitude, d.url, d.recorded_at
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
        "query": {"ticker": ticker},
    })


TOOLS = {
    "search_filings": {
        "fn": search_filings,
        "description": search_filings.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords for filing titles and summaries"},
                "form_type": {"type": "string", "description": "Form type filter (e.g. 'form4', '8k', '10-K', '10-Q', '13f')"},
                "ticker": {"type": "string", "description": "Company ticker symbol"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 30 days ago)"},
                "limit": {"type": "integer", "default": 20, "description": "Max results (up to 100)"},
            },
            "required": ["query"],
        },
    },
    "get_insider_trades": {
        "fn": get_insider_trades,
        "description": get_insider_trades.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Filter by ticker symbol"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 30 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "get_insider_clusters": {
        "fn": get_insider_clusters,
        "description": get_insider_clusters.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Filter to a specific ticker"},
                "days": {"type": "integer", "default": 30, "description": "Lookback period in days"},
                "min_trades": {"type": "integer", "default": 3, "description": "Minimum trades to form a cluster"},
            },
        },
    },
    "get_8k_events": {
        "fn": get_8k_events,
        "description": get_8k_events.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 7 days ago)"},
                "item_type": {"type": "string", "description": "8-K item type filter (e.g. '5.02', '1.01', '2.01')"},
                "ticker": {"type": "string", "description": "Company ticker symbol"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "get_13f_holdings": {
        "fn": get_13f_holdings,
        "description": get_13f_holdings.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 90 days ago)"},
                "ticker": {"type": "string", "description": "Filter by ticker symbol"},
            },
        },
    },
}
