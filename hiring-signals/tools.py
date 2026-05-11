"""
Hiring signal tools — job posting and labor market intelligence.

Queries diffs from ATS parsers (Greenhouse, Ashby, Lever) where source_ids
follow the pattern: gh-{board}, ashby-{board}, lever-{company}.
Diff types: new_record, field_change, deletion.
Title format: "{company}: {job_title}".
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, timezone
from typing import Optional

from shared.db import fetch, fetchval
from shared.mcp_base import serialize

ATS_SOURCE_PATTERN = "(d.source_id LIKE 'gh-%' OR d.source_id LIKE 'ashby-%' OR d.source_id LIKE 'lever-%')"


async def get_new_roles(
    company: Optional[str] = None,
    title_contains: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get new job postings across Greenhouse, Ashby, and Lever ATS platforms.

    Tracks job postings from AI labs and tech companies including Anthropic,
    OpenAI, SpaceX, Databricks, xAI, and more. Filter by company name or
    job title keywords. New roles signal team expansion or strategic pivots.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=7)
    limit = min(limit, 200)

    conditions = [
        ATS_SOURCE_PATTERN,
        "d.recorded_at >= $1",
        "d.diff_type = 'new_record'",
    ]
    params: list = [since_dt]
    idx = 2

    if company:
        conditions.append(f"(d.source_id ILIKE ${idx} OR d.title ILIKE ${idx})")
        params.append(f"%{company}%")
        idx += 1

    if title_contains:
        conditions.append(f"d.title ILIKE ${idx}")
        params.append(f"%{title_contains}%")
        idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.source_id, d.record_id, d.title,
               d.magnitude, d.recorded_at, d.url
        FROM diffs d
        WHERE {where}
        ORDER BY d.recorded_at DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, *params, limit=limit)
    total = await fetchval(f"SELECT COUNT(*) FROM diffs d WHERE {where}", *params)

    results = []
    for r in rows:
        row = dict(r)
        title = row.get("title", "") or ""
        if ": " in title:
            row["company"] = title.split(": ", 1)[0]
            row["job_title"] = title.split(": ", 1)[1]
        else:
            row["company"] = row.get("source_id", "").split("-", 1)[-1] if row.get("source_id") else ""
            row["job_title"] = title
        results.append(row)

    return serialize({
        "results": results,
        "total": total,
        "since": since_dt.isoformat(),
        "query": {"company": company, "title_contains": title_contains},
    })


async def detect_first_hire(
    role_type: str,
    since: Optional[str] = None,
) -> dict:
    """Detect companies posting their first role in a specific function.

    Finds companies that have never previously posted a role matching the given
    type (e.g. 'ML Engineer', 'AI', 'Security', 'Data Science'). A first hire
    in a new function signals strategic investment in that capability.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=30)

    sql = f"""
        WITH recent_posts AS (
            SELECT d.source_id,
                   d.title,
                   d.recorded_at,
                   d.url,
                   d.diff_id
            FROM diffs d
            WHERE {ATS_SOURCE_PATTERN}
              AND d.diff_type = 'new_record'
              AND d.recorded_at >= $1
              AND d.title ILIKE $2
        ),
        prior_sources AS (
            SELECT DISTINCT d.source_id
            FROM diffs d
            WHERE {ATS_SOURCE_PATTERN}
              AND d.recorded_at < $1
              AND d.title ILIKE $2
        )
        SELECT rp.source_id, rp.title, rp.recorded_at, rp.url, rp.diff_id
        FROM recent_posts rp
        LEFT JOIN prior_sources ps ON rp.source_id = ps.source_id
        WHERE ps.source_id IS NULL
        ORDER BY rp.recorded_at DESC
        LIMIT 50
    """

    rows = await fetch(sql, since_dt, f"%{role_type}%")

    results = []
    for r in rows:
        row = dict(r)
        sid = row.get("source_id", "")
        row["company"] = sid.split("-", 1)[-1] if "-" in sid else sid
        row["ats"] = sid.split("-", 1)[0] if "-" in sid else "unknown"
        results.append(row)

    return serialize({
        "results": results,
        "total": len(results),
        "since": since_dt.isoformat(),
        "query": {"role_type": role_type},
    })


async def get_hiring_velocity(
    company: str,
    since: Optional[str] = None,
) -> dict:
    """Get the rate of new job postings over time for a specific company.

    Returns weekly posting counts broken down by new roles vs deleted roles.
    Accelerating hiring velocity often precedes product launches or
    funding announcements. Decelerating velocity may signal headwinds.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=90)

    sql = f"""
        SELECT
            date_trunc('week', d.recorded_at) AS week,
            COUNT(*) AS total_changes,
            COUNT(*) FILTER (WHERE d.diff_type = 'new_record') AS new_roles,
            COUNT(*) FILTER (WHERE d.diff_type = 'deletion') AS removed_roles
        FROM diffs d
        WHERE {ATS_SOURCE_PATTERN}
          AND d.recorded_at >= $1
          AND (d.source_id ILIKE $2 OR d.title ILIKE $2)
        GROUP BY date_trunc('week', d.recorded_at)
        ORDER BY week DESC
    """

    rows = await fetch(sql, since_dt, f"%{company}%")

    total_open = await fetchval(
        f"""SELECT COUNT(*) FROM diffs d
           WHERE {ATS_SOURCE_PATTERN}
             AND d.diff_type = 'new_record'
             AND d.recorded_at >= $1
             AND (d.source_id ILIKE $2 OR d.title ILIKE $2)""",
        since_dt, f"%{company}%",
    )

    return serialize({
        "results": [dict(r) for r in rows],
        "total_new_roles": total_open,
        "since": since_dt.isoformat(),
        "query": {"company": company},
    })


async def search_roles(
    query: str,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Full-text search across all job postings by title or keyword.

    Search for technology keywords, role types, or company names across all
    ATS job postings. Examples: 'Kubernetes', 'Rust', 'ML Engineer',
    'product manager'. Returns matching roles with company and URL.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=30)
    limit = min(limit, 200)

    sql = f"""
        SELECT d.diff_id, d.source_id, d.record_id, d.title,
               d.diff_type, d.magnitude, d.recorded_at, d.url
        FROM diffs d
        WHERE {ATS_SOURCE_PATTERN}
          AND d.recorded_at >= $1
          AND d.title ILIKE $2
        ORDER BY d.recorded_at DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, since_dt, f"%{query}%")
    total = await fetchval(
        f"SELECT COUNT(*) FROM diffs d WHERE {ATS_SOURCE_PATTERN} AND d.recorded_at >= $1 AND d.title ILIKE $2",
        since_dt, f"%{query}%",
    )

    results = []
    for r in rows:
        row = dict(r)
        title = row.get("title", "") or ""
        if ": " in title:
            row["company"] = title.split(": ", 1)[0]
            row["job_title"] = title.split(": ", 1)[1]
        else:
            row["company"] = row.get("source_id", "").split("-", 1)[-1] if row.get("source_id") else ""
            row["job_title"] = title
        results.append(row)

    return serialize({
        "results": results,
        "total": total,
        "since": since_dt.isoformat(),
        "query": {"query": query},
    })


async def get_company_snapshot(
    company: str,
) -> dict:
    """Get a complete hiring snapshot for a specific company.

    Returns total open roles, most recent postings, and role categories.
    Uses the latest data available regardless of time window. Company
    matches against source_id (e.g. 'anthropic' matches 'gh-anthropic').
    """
    sql = f"""
        SELECT d.source_id, d.title, d.url, d.recorded_at, d.diff_type
        FROM diffs d
        WHERE {ATS_SOURCE_PATTERN}
          AND (d.source_id ILIKE $1 OR d.title ILIKE $1)
        ORDER BY d.recorded_at DESC
        LIMIT 200
    """

    rows = await fetch(sql, f"%{company}%")

    total = await fetchval(
        f"SELECT COUNT(*) FROM diffs d WHERE {ATS_SOURCE_PATTERN} AND (d.source_id ILIKE $1 OR d.title ILIKE $1)",
        f"%{company}%",
    )

    new_count = sum(1 for r in rows if r["diff_type"] == "new_record")
    deleted_count = sum(1 for r in rows if r["diff_type"] == "deletion")

    sources = list(set(r["source_id"] for r in rows))

    results = []
    for r in rows[:50]:
        row = dict(r)
        title = row.get("title", "") or ""
        if ": " in title:
            row["job_title"] = title.split(": ", 1)[1]
        else:
            row["job_title"] = title
        results.append(row)

    return serialize({
        "results": results,
        "total_diffs": total,
        "new_roles": new_count,
        "deleted_roles": deleted_count,
        "ats_sources": sources,
        "query": {"company": company},
    })


TOOLS = {
    "get_new_roles": {
        "fn": get_new_roles,
        "description": get_new_roles.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name filter (e.g. 'anthropic', 'spacex', 'openai')"},
                "title_contains": {"type": "string", "description": "Job title keyword filter (e.g. 'engineer', 'manager')"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 7 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "detect_first_hire": {
        "fn": detect_first_hire,
        "description": detect_first_hire.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "role_type": {"type": "string", "description": "Role function to detect (e.g. 'ML Engineer', 'AI', 'Security')"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 30 days ago)"},
            },
            "required": ["role_type"],
        },
    },
    "get_hiring_velocity": {
        "fn": get_hiring_velocity,
        "description": get_hiring_velocity.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name (e.g. 'anthropic', 'spacex')"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 90 days ago)"},
            },
            "required": ["company"],
        },
    },
    "search_roles": {
        "fn": search_roles,
        "description": search_roles.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term for job titles (e.g. 'Rust', 'ML', 'product manager')"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 30 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
            "required": ["query"],
        },
    },
    "get_company_snapshot": {
        "fn": get_company_snapshot,
        "description": get_company_snapshot.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name (e.g. 'anthropic', 'databricks', 'openai')"},
            },
            "required": ["company"],
        },
    },
}
