"""
AI Labs signal tools — AI research and model intelligence.

Covers: HuggingFace model releases (52 intl orgs), arxiv papers,
AI lab blogs, GitHub org activity, and framework/package trends.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, timezone
from typing import Optional

from shared.db import fetch, fetchval
from shared.mcp_base import serialize

# Actual source_id patterns in the diffs table
HF_MODEL_SOURCES = (
    "hf-qwen", "hf-deepseek", "hf-internlm", "hf-baai", "hf-stepfun",
    "hf-tencent", "hf-01ai", "hf-baichuan", "hf-minimax", "hf-moonshot",
    "hf-sp500-transcripts", "huggingface-trending", "huggingface-trending-datasets",
)

ARXIV_SOURCES = (
    "arxiv-cs-lg", "arxiv-cs-ai", "arxiv-cs-cl", "arxiv-cs-cv",
    "arxiv-stat-ml", "arxiv-search-llm", "arxiv-q-fin", "arxiv-econ-gn",
)

BLOG_SOURCES = (
    "blog-openai", "blog-huggingface", "blog-elevenlabs", "blog-mistral",
    "blog-google-deepmind", "blog-google-research", "blog-anthropic",
    "blog-aws-ml", "blog-nvidia", "blog-databricks", "blog-character",
    "blog-runway", "blog-meta-ai", "blog-pika",
)

GITHUB_SOURCES = (
    "gh-spacex", "gh-databricks", "gh-anthropic", "gh-coreweave",
    "gh-xai", "gh-scaleai", "github-rel-anthropics", "github-rel-google-deepmind",
    "github-rel-mistralai",
)

RESEARCH_SOURCES = ("anthropic-research",)

ALL_AI_SOURCES = HF_MODEL_SOURCES + ARXIV_SOURCES + BLOG_SOURCES + GITHUB_SOURCES + RESEARCH_SOURCES


async def get_lab_activity(
    org: Optional[str] = None,
    source_type: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get recent AI lab activity across HuggingFace model releases, GitHub commits, blog posts, and research papers.

    Tracks 60+ international AI orgs including OpenAI, Google DeepMind, Meta,
    Anthropic, Mistral, DeepSeek, Qwen, xAI, and others. Filter by org name
    or source type to monitor specific labs' output.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=7)
    limit = min(limit, 200)

    conditions = ["d.source_id = ANY($1::text[])", "d.recorded_at >= $2"]
    params: list = [list(ALL_AI_SOURCES), since_dt]
    idx = 3

    if org:
        conditions.append(f"(d.source_id ILIKE ${idx} OR d.title ILIKE ${idx})")
        params.append(f"%{org}%")
        idx += 1

    if source_type:
        source_map = {
            "models": list(HF_MODEL_SOURCES),
            "papers": list(ARXIV_SOURCES),
            "blogs": list(BLOG_SOURCES),
            "github": list(GITHUB_SOURCES),
            "research": list(RESEARCH_SOURCES),
        }
        if source_type in source_map:
            conditions[0] = f"d.source_id = ANY(${idx}::text[])"
            params.append(source_map[source_type])
            idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.source_id, d.ticker, d.title, d.summary,
               d.magnitude, d.category, d.changed_fields, d.recorded_at, d.url
        FROM diffs d
        WHERE {where}
        ORDER BY d.recorded_at DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, *params, limit=limit)
    total = await fetchval(f"SELECT COUNT(*) FROM diffs d WHERE {where}", *params)
    return serialize({
        "results": rows,
        "total": total,
        "since": since_dt.isoformat(),
        "query": {"org": org, "source_type": source_type},
    })


async def get_daily_papers(
    since: Optional[str] = None,
    topic: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get recent AI/ML research papers from arxiv.

    Covers cs.LG (machine learning), cs.AI (artificial intelligence),
    cs.CL (computation & language / NLP), cs.CV (computer vision),
    stat.ML (statistics/ML), and quantitative finance. Filter by topic
    keywords or arxiv category.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=7)
    limit = min(limit, 200)

    conditions = ["d.source_id = ANY($1::text[])", "d.recorded_at >= $2"]
    params: list = [list(ARXIV_SOURCES), since_dt]
    idx = 3

    if topic:
        conditions.append(f"(d.title ILIKE ${idx} OR d.summary ILIKE ${idx})")
        params.append(f"%{topic}%")
        idx += 1

    if category:
        cat_map = {
            "ml": "arxiv-cs-lg",
            "ai": "arxiv-cs-ai",
            "nlp": "arxiv-cs-cl",
            "cv": "arxiv-cs-cv",
            "stats": "arxiv-stat-ml",
            "llm": "arxiv-search-llm",
            "finance": "arxiv-q-fin",
        }
        if category in cat_map:
            conditions[0] = f"d.source_id = ${idx}"
            params.append(cat_map[category])
            idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.source_id, d.title, d.summary, d.magnitude,
               d.changed_fields, d.recorded_at, d.url
        FROM diffs d
        WHERE {where}
        ORDER BY d.recorded_at DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, *params, limit=limit)
    total = await fetchval(f"SELECT COUNT(*) FROM diffs d WHERE {where}", *params)
    return serialize({
        "results": rows,
        "total": total,
        "since": since_dt.isoformat(),
        "query": {"topic": topic, "category": category},
    })


async def search_research(
    query: str,
    since: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """Full-text search across all AI research papers, blog posts, and announcements.

    Searches titles and summaries across arxiv papers, AI lab blogs,
    and research publications. Useful for finding work on specific topics,
    tracking research from specific labs, or monitoring emerging areas.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=90)
    limit = min(limit, 100)

    search_sources = list(ARXIV_SOURCES + BLOG_SOURCES + RESEARCH_SOURCES)

    sql = """
        SELECT d.diff_id, d.source_id, d.title, d.summary, d.magnitude,
               d.category, d.changed_fields, d.recorded_at, d.url
        FROM diffs d
        WHERE d.source_id = ANY($1::text[])
          AND d.recorded_at >= $2
          AND (d.title ILIKE $3 OR d.summary ILIKE $3)
        ORDER BY d.recorded_at DESC
        LIMIT $4
    """

    rows = await fetch(sql, search_sources, since_dt, f"%{query}%", limit)
    total = await fetchval(
        """SELECT COUNT(*) FROM diffs d
           WHERE d.source_id = ANY($1::text[])
             AND d.recorded_at >= $2
             AND (d.title ILIKE $3 OR d.summary ILIKE $3)""",
        search_sources, since_dt, f"%{query}%",
    )
    return serialize({
        "results": rows,
        "total": total,
        "since": since_dt.isoformat(),
        "query": {"query": query},
    })


async def get_github_activity(
    org: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get GitHub repository activity from major AI labs and companies.

    Tracks repos from xAI, Anthropic, SpaceX, Databricks, CoreWeave,
    Scale AI, Google DeepMind, and Mistral. Includes new repos, commits,
    releases, and stars. Filter by org name.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=7)
    limit = min(limit, 200)

    conditions = ["d.source_id = ANY($1::text[])", "d.recorded_at >= $2"]
    params: list = [list(GITHUB_SOURCES), since_dt]
    idx = 3

    if org:
        conditions.append(f"(d.source_id ILIKE ${idx} OR d.title ILIKE ${idx})")
        params.append(f"%{org}%")
        idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.source_id, d.title, d.summary, d.magnitude,
               d.changed_fields, d.recorded_at, d.url
        FROM diffs d
        WHERE {where}
        ORDER BY d.recorded_at DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, *params, limit=limit)
    total = await fetchval(f"SELECT COUNT(*) FROM diffs d WHERE {where}", *params)
    return serialize({
        "results": rows,
        "total": total,
        "since": since_dt.isoformat(),
        "query": {"org": org},
    })


async def get_model_releases(
    org: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Get HuggingFace model releases from tracked AI labs.

    Monitors model uploads and updates from 52 international AI orgs including
    Qwen, DeepSeek, InternLM, BAAI, StepFun, Tencent, 01.AI, Baichuan,
    MiniMax, and others. Includes trending models and datasets.
    """
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(days=30)
    limit = min(limit, 200)

    conditions = ["d.source_id = ANY($1::text[])", "d.recorded_at >= $2"]
    params: list = [list(HF_MODEL_SOURCES), since_dt]
    idx = 3

    if org:
        conditions.append(f"(d.source_id ILIKE ${idx} OR d.title ILIKE ${idx})")
        params.append(f"%{org}%")
        idx += 1

    where = " AND ".join(conditions)
    sql = f"""
        SELECT d.diff_id, d.source_id, d.title, d.summary, d.magnitude,
               d.changed_fields, d.recorded_at, d.url
        FROM diffs d
        WHERE {where}
        ORDER BY d.recorded_at DESC
        LIMIT {limit}
    """

    rows = await fetch(sql, *params, limit=limit)
    total = await fetchval(f"SELECT COUNT(*) FROM diffs d WHERE {where}", *params)
    return serialize({
        "results": rows,
        "total": total,
        "since": since_dt.isoformat(),
        "query": {"org": org},
    })


TOOLS = {
    "get_lab_activity": {
        "fn": get_lab_activity,
        "description": get_lab_activity.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "org": {"type": "string", "description": "AI lab or org name (e.g. 'anthropic', 'openai', 'deepseek', 'xai')"},
                "source_type": {
                    "type": "string",
                    "enum": ["models", "papers", "blogs", "github", "research"],
                    "description": "Filter by source type",
                },
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 7 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "get_daily_papers": {
        "fn": get_daily_papers,
        "description": get_daily_papers.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 7 days ago)"},
                "topic": {"type": "string", "description": "Topic keyword filter (e.g. 'reasoning', 'vision', 'agents', 'alignment')"},
                "category": {
                    "type": "string",
                    "enum": ["ml", "ai", "nlp", "cv", "stats", "llm", "finance"],
                    "description": "Arxiv category shorthand",
                },
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "search_research": {
        "fn": search_research,
        "description": search_research.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords for titles and summaries"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 90 days ago)"},
                "limit": {"type": "integer", "default": 20, "description": "Max results (up to 100)"},
            },
            "required": ["query"],
        },
    },
    "get_github_activity": {
        "fn": get_github_activity,
        "description": get_github_activity.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "org": {"type": "string", "description": "GitHub org name (e.g. 'anthropic', 'xai', 'databricks', 'coreweave')"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 7 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
    "get_model_releases": {
        "fn": get_model_releases,
        "description": get_model_releases.__doc__,
        "schema": {
            "type": "object",
            "properties": {
                "org": {"type": "string", "description": "HuggingFace org (e.g. 'qwen', 'deepseek', 'internlm', 'baai')"},
                "since": {"type": "string", "description": "ISO datetime cutoff (default: 30 days ago)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results (up to 200)"},
            },
        },
    },
}
