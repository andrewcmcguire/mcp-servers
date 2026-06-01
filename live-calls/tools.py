"""
Live earnings call tools — transcripts, NLP insights, deception scoring,
live monitoring alerts, and call scheduling intelligence.

Tables: fin45.earnings_events (26K), fin45.transcripts (349),
fin45.earnings_insights (585), fin45.live_alerts, fin45.live_call_progress
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, timezone
from typing import Optional

from shared.db import fetch, fetchval
from shared.mcp_base import serialize


async def get_call_insights(
    ticker: Optional[str] = None,
    direction: Optional[str] = None,
    min_signal_score: float = 0.0,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get NLP-extracted insights from earnings calls — sentiment, deception scores,
    guidance direction, signal scores, surprises, and key quotes.

    Each insight is scored 0.0–1.0 for signal strength and deception probability.
    Signal direction is bullish/bearish/neutral. Guidance direction is raised/lowered/maintained.
    Covers 585+ analyzed calls with full NLP extraction including Q&A highlights.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=90)
    limit = min(limit, 200)

    conditions = ["i.created_at >= $1"]
    params: list = [since_dt]
    idx = 2

    if ticker:
        conditions.append(f"i.ticker = ${idx}")
        params.append(ticker.upper())
        idx += 1

    if direction:
        conditions.append(f"i.signal_direction = ${idx}")
        params.append(direction.lower())
        idx += 1

    if min_signal_score > 0:
        conditions.append(f"i.signal_score >= ${idx}")
        params.append(min_signal_score)
        idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT i.insight_id, i.ticker, i.call_date, i.signal_score,
               i.signal_direction, i.sentiment_score, i.deception_score,
               i.guidance_direction, i.summary, i.surprises, i.tone_analysis,
               i.key_metrics, i.qa_highlights, i.key_quotes,
               i.model_used, i.created_at
        FROM fin45.earnings_insights i
        WHERE {where}
        ORDER BY i.created_at DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, *params, limit=limit)
    total = await fetchval(f"SELECT COUNT(*) FROM fin45.earnings_insights i WHERE {where}", *params)

    return serialize({
        "results": [dict(r) for r in rows],
        "total": total,
        "since": since_dt.isoformat(),
        "query": {"ticker": ticker, "direction": direction, "min_signal_score": min_signal_score},
    })


async def get_transcripts(
    ticker: Optional[str] = None,
    since: Optional[str] = None,
    include_text: bool = False,
    limit: int = 20,
) -> dict:
    """Get earnings call transcripts with metadata. Returns company, date,
    word count, and model used. Set include_text=true to get the full transcript text.

    Covers 349+ transcripts from 8-K press releases and Motley Fool sourced calls.
    Full text can be large — use include_text only when you need the actual words.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=90)
    limit = min(limit, 50)

    conditions = ["t.created_at >= $1"]
    params: list = [since_dt]
    idx = 2

    if ticker:
        conditions.append(f"t.ticker = ${idx}")
        params.append(ticker.upper())
        idx += 1

    where = " AND ".join(conditions)

    text_col = ", t.raw_text" if include_text else ""
    sql = f"""
        SELECT t.transcript_id, t.ticker, t.company, t.report_date,
               t.word_count, t.duration_seconds, t.model_used, t.created_at
               {text_col}
        FROM fin45.transcripts t
        WHERE {where}
        ORDER BY t.created_at DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, *params, limit=limit)
    total = await fetchval(f"SELECT COUNT(*) FROM fin45.transcripts t WHERE {where}", *params)

    return serialize({
        "results": [dict(r) for r in rows],
        "total": total,
        "since": since_dt.isoformat(),
        "query": {"ticker": ticker, "include_text": include_text},
    })


async def get_deception_signals(
    min_deception_score: float = 0.4,
    ticker: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Detect potential deception in earnings calls using NLP scoring.

    Returns calls where the deception probability exceeds the threshold (default 0.4).
    Based on Larcker-Zakolyukina linguistic deception markers — hedging language,
    lack of specificity, distancing pronouns, and unusual verbal patterns.
    Higher scores indicate more linguistic markers associated with deception.
    Cross-reference with guidance_direction and signal_score for actionable signals.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=180)
    limit = min(limit, 200)

    conditions = [
        "i.created_at >= $1",
        "i.deception_score >= $2",
    ]
    params: list = [since_dt, min_deception_score]
    idx = 3

    if ticker:
        conditions.append(f"i.ticker = ${idx}")
        params.append(ticker.upper())
        idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT i.insight_id, i.ticker, i.call_date, i.deception_score,
               i.deception_analysis, i.signal_score, i.signal_direction,
               i.sentiment_score, i.guidance_direction, i.summary,
               i.key_quotes, i.model_used, i.created_at
        FROM fin45.earnings_insights i
        WHERE {where}
        ORDER BY i.deception_score DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, *params, limit=limit)
    total = await fetchval(f"SELECT COUNT(*) FROM fin45.earnings_insights i WHERE {where}", *params)

    return serialize({
        "results": [dict(r) for r in rows],
        "total": total,
        "since": since_dt.isoformat(),
        "query": {"min_deception_score": min_deception_score, "ticker": ticker},
    })


async def get_live_alerts(
    ticker: Optional[str] = None,
    unconsumed_only: bool = False,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get real-time alerts generated during live earnings call monitoring.

    Alerts fire when the NLP pipeline detects signal_score >= 0.70 during an
    active call. Each alert contains the ticker, alert type, and a JSONB payload
    with signal_score, signal_direction, guidance changes, and key quotes.
    Use unconsumed_only=true to see alerts not yet acted on by the trading agent.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=7)
    limit = min(limit, 200)

    conditions = ["a.created_at >= $1"]
    params: list = [since_dt]
    idx = 2

    if ticker:
        conditions.append(f"a.ticker = ${idx}")
        params.append(ticker.upper())
        idx += 1

    if unconsumed_only:
        conditions.append("a.consumed = FALSE")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT a.alert_id, a.ticker, a.alert_type, a.payload,
               a.consumed, a.consumed_at, a.created_at
        FROM fin45.live_alerts a
        WHERE {where}
        ORDER BY a.created_at DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, *params, limit=limit)
    total = await fetchval(f"SELECT COUNT(*) FROM fin45.live_alerts a WHERE {where}", *params)

    return serialize({
        "results": [dict(r) for r in rows],
        "total": total,
        "since": since_dt.isoformat(),
        "query": {"ticker": ticker, "unconsumed_only": unconsumed_only},
    })


async def get_upcoming_calls(
    days_ahead: int = 7,
    ticker: Optional[str] = None,
    has_webcast: Optional[bool] = None,
    limit: int = 100,
) -> dict:
    """Get upcoming earnings calls with scheduling details.

    Returns calls scheduled in the next N days, with company, ticker, report time
    (before-market/after-hours), EPS/revenue estimates, expected move, and whether
    a webcast URL is available for live monitoring. 26K+ events in the calendar.
    Use has_webcast=true to filter to calls that can be live-monitored.
    """
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days_ahead)
    limit = min(limit, 500)

    conditions = [
        "e.report_date >= $1",
        "e.report_date <= $2",
        "e.status = 'scheduled'",
    ]
    params: list = [now.date(), cutoff.date()]
    idx = 3

    if ticker:
        conditions.append(f"e.ticker = ${idx}")
        params.append(ticker.upper())
        idx += 1

    if has_webcast is True:
        conditions.append("e.webcast_url IS NOT NULL")
    elif has_webcast is False:
        conditions.append("e.webcast_url IS NULL")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT e.event_id, e.ticker, e.company, e.report_date, e.report_time,
               e.eps_estimate, e.rev_estimate, e.expected_move_pct,
               e.options_iv, e.webcast_url IS NOT NULL AS has_webcast,
               e.source, e.fiscal_quarter
        FROM fin45.earnings_events e
        WHERE {where}
        ORDER BY e.report_date ASC, e.ticker ASC
        LIMIT {limit}
    """

    rows = await fetch(sql, *params, limit=limit)
    total = await fetchval(f"SELECT COUNT(*) FROM fin45.earnings_events e WHERE {where}", *params)

    return serialize({
        "results": [dict(r) for r in rows],
        "total": total,
        "window": {"from": now.date().isoformat(), "to": cutoff.date().isoformat()},
        "query": {"days_ahead": days_ahead, "ticker": ticker, "has_webcast": has_webcast},
    })


async def search_call_content(
    query: str,
    since: Optional[str] = None,
    limit: int = 30,
) -> dict:
    """Full-text search across earnings call transcripts and NLP insights.

    Searches transcript text, insight summaries, key quotes, and surprise details
    for keywords. Use this to find specific mentions — vendor names, product lines,
    guidance language, risk factors, or competitive references across all analyzed calls.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=180)
    limit = min(limit, 100)
    pattern = f"%{query}%"

    transcript_sql = """
        SELECT t.transcript_id AS id, 'transcript' AS result_type,
               t.ticker, t.company, t.report_date, t.word_count,
               t.created_at, NULL::jsonb AS extras
        FROM fin45.transcripts t
        WHERE t.created_at >= $1
          AND (t.raw_text ILIKE $2 OR t.company ILIKE $2)
        ORDER BY t.created_at DESC
        LIMIT $3
    """

    insight_sql = """
        SELECT i.insight_id AS id, 'insight' AS result_type,
               i.ticker, NULL AS company, i.call_date AS report_date,
               NULL::int AS word_count, i.created_at,
               jsonb_build_object(
                   'signal_score', i.signal_score,
                   'signal_direction', i.signal_direction,
                   'deception_score', i.deception_score,
                   'guidance_direction', i.guidance_direction
               ) AS extras
        FROM fin45.earnings_insights i
        WHERE i.created_at >= $1
          AND (i.summary ILIKE $2 OR i.key_quotes::text ILIKE $2
               OR i.surprises::text ILIKE $2 OR i.qa_highlights::text ILIKE $2)
        ORDER BY i.created_at DESC
        LIMIT $3
    """

    t_rows = await fetch(transcript_sql, since_dt, pattern, limit, limit=limit)
    i_rows = await fetch(insight_sql, since_dt, pattern, limit, limit=limit)

    combined = sorted(
        [dict(r) for r in t_rows] + [dict(r) for r in i_rows],
        key=lambda x: x.get("created_at") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[:limit]

    return serialize({
        "results": combined,
        "total": len(combined),
        "since": since_dt.isoformat(),
        "query": {"query": query},
    })


async def get_call_monitor_status(
    ticker: Optional[str] = None,
) -> dict:
    """Get the status of live call monitoring — which calls are being actively
    transcribed, chunk progress, and word counts.

    Shows real-time progress for calls currently being captured and transcribed
    by the live monitoring pipeline. Each entry shows the latest chunk index,
    cumulative words, and seconds of audio processed.
    """
    conditions = []
    params: list = []
    idx = 1

    if ticker:
        conditions.append(f"p.ticker = ${idx}")
        params.append(ticker.upper())
        idx += 1

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"""
        SELECT p.event_id, p.ticker, MAX(p.chunk_index) AS chunks_processed,
               MAX(p.cumulative_words) AS total_words,
               MAX(p.cumulative_seconds) AS total_seconds,
               MAX(p.updated_at) AS last_update
        FROM fin45.live_call_progress p
        {where}
        GROUP BY p.event_id, p.ticker
        ORDER BY MAX(p.updated_at) DESC
        LIMIT 50
    """

    rows = await fetch(sql, *params)

    active_sql = """
        SELECT COUNT(DISTINCT ticker)
        FROM fin45.earnings_events
        WHERE status = 'capturing' OR status = 'live_monitoring'
    """
    active = await fetchval(active_sql)

    return serialize({
        "results": [dict(r) for r in rows],
        "active_monitors": active,
        "query": {"ticker": ticker},
    })


async def get_call_directory(
    ticker: Optional[str] = None,
    status: Optional[str] = None,
    has_transcript: Optional[bool] = None,
    has_insights: Optional[bool] = None,
    since: Optional[str] = None,
    limit: int = 100,
) -> dict:
    """Master earnings call directory — 26K+ calls across 5,192 tickers with
    linked transcripts, NLP insights, and IR contact info.

    Each row joins the earnings event with its transcript (if captured) and
    NLP insight (signal score, deception, guidance). Use this to build call
    lists, find companies to contact, or export to a CRM/dialer system.
    Filter by status (scheduled/complete/needs_transcript), or narrow to calls
    that have transcripts or NLP insights already processed.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=365)
    limit = min(limit, 500)

    conditions = ["e.report_date >= $1"]
    params: list = [since_dt.date()]
    idx = 2

    if ticker:
        conditions.append(f"e.ticker = ${idx}")
        params.append(ticker.upper())
        idx += 1

    if status:
        conditions.append(f"e.status = ${idx}")
        params.append(status.lower())
        idx += 1

    if has_transcript is True:
        conditions.append("t.transcript_id IS NOT NULL")
    elif has_transcript is False:
        conditions.append("t.transcript_id IS NULL")

    if has_insights is True:
        conditions.append("i.insight_id IS NOT NULL")
    elif has_insights is False:
        conditions.append("i.insight_id IS NULL")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT e.event_id, e.ticker, e.company, e.report_date, e.report_time,
               e.fiscal_quarter, e.status,
               e.eps_estimate, e.rev_estimate, e.eps_actual, e.rev_actual,
               e.surprise_pct, e.expected_move_pct, e.options_iv,
               e.webcast_url, e.ir_page_url, e.replay_url, e.source,
               t.transcript_id IS NOT NULL AS has_transcript,
               t.word_count AS transcript_words,
               i.signal_score, i.signal_direction, i.sentiment_score,
               i.deception_score, i.guidance_direction, i.summary AS nlp_summary
        FROM fin45.earnings_events e
        LEFT JOIN fin45.transcripts t
            ON t.ticker = e.ticker AND t.report_date = e.report_date
        LEFT JOIN LATERAL (
            SELECT * FROM fin45.earnings_insights ei
            WHERE ei.ticker = e.ticker AND ei.report_date = e.report_date
            ORDER BY ei.created_at DESC LIMIT 1
        ) i ON TRUE
        WHERE {where}
        ORDER BY e.report_date DESC, e.ticker ASC
        LIMIT {limit}
    """

    rows = await fetch(sql, *params, limit=limit)

    count_where = " AND ".join(conditions).replace("t.transcript_id", "(SELECT 1 FROM fin45.transcripts t2 WHERE t2.ticker = e.ticker AND t2.report_date = e.report_date)")
    count_where = count_where.replace("i.insight_id", "(SELECT 1 FROM fin45.earnings_insights i2 WHERE i2.ticker = e.ticker AND i2.report_date = e.report_date)")
    count_sql = f"SELECT COUNT(*) FROM fin45.earnings_events e WHERE {conditions[0]}"
    if ticker:
        count_sql += f" AND e.ticker = ${idx - (1 if status else 0) - (1 if has_transcript is not None else 0) - (1 if has_insights is not None else 0)}"

    return serialize({
        "results": [dict(r) for r in rows],
        "total": len(rows),
        "since": since_dt.date().isoformat(),
        "query": {"ticker": ticker, "status": status, "has_transcript": has_transcript, "has_insights": has_insights},
    })


TOOLS = {
    "get_call_insights": {
        "fn": get_call_insights,
        "description": get_call_insights.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol (e.g. 'NVDA', 'CRM')"},
                "direction": {"type": "string", "enum": ["bullish", "bearish", "neutral"], "description": "Filter by signal direction"},
                "min_signal_score": {"type": "number", "default": 0.0, "description": "Minimum signal score (0.0–1.0)"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 90 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "get_transcripts": {
        "fn": get_transcripts,
        "description": get_transcripts.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 90 days ago)"},
                "include_text": {"type": "boolean", "default": False, "description": "Include full transcript text (can be large)"},
                "limit": {"type": "integer", "default": 20, "description": "Max results (up to 50)"},
            },
        },
    },
    "get_deception_signals": {
        "fn": get_deception_signals,
        "description": get_deception_signals.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "min_deception_score": {"type": "number", "default": 0.4, "description": "Minimum deception probability (0.0–1.0)"},
                "ticker": {"type": "string", "description": "Company ticker symbol"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 180 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "get_live_alerts": {
        "fn": get_live_alerts,
        "description": get_live_alerts.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol"},
                "unconsumed_only": {"type": "boolean", "default": False, "description": "Only show alerts not yet acted on"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 7 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "get_upcoming_calls": {
        "fn": get_upcoming_calls,
        "description": get_upcoming_calls.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "default": 7, "description": "How many days ahead to look"},
                "ticker": {"type": "string", "description": "Company ticker symbol"},
                "has_webcast": {"type": "boolean", "description": "Filter to calls with webcast URLs (live-monitorable)"},
                "limit": {"type": "integer", "default": 100, "description": "Max results (up to 500)"},
            },
        },
    },
    "search_call_content": {
        "fn": search_call_content,
        "description": search_call_content.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords (vendor name, product, risk factor, etc.)"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 180 days ago)"},
                "limit": {"type": "integer", "default": 30, "description": "Max results (up to 100)"},
            },
            "required": ["query"],
        },
    },
    "get_call_monitor_status": {
        "fn": get_call_monitor_status,
        "description": get_call_monitor_status.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol"},
            },
        },
    },
    "get_call_directory": {
        "fn": get_call_directory,
        "description": get_call_directory.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol"},
                "status": {"type": "string", "enum": ["scheduled", "complete", "needs_transcript", "capturing", "failed"], "description": "Filter by call status"},
                "has_transcript": {"type": "boolean", "description": "Filter to calls with/without transcripts"},
                "has_insights": {"type": "boolean", "description": "Filter to calls with/without NLP insights"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 1 year ago)"},
                "limit": {"type": "integer", "default": 100, "description": "Max results (up to 500)"},
            },
        },
    },
}
