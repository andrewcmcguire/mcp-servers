"""
Async database pool for MCP servers.
Uses asyncpg with connection-level search_path initialization.
"""

import asyncpg
from typing import Optional

from .config import get_postgres_config

_pool: Optional[asyncpg.Pool] = None


async def _init_connection(conn: asyncpg.Connection):
    await conn.execute("SET search_path TO fin45, public")


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        pg = get_postgres_config()
        _pool = await asyncpg.create_pool(
            host=pg["host"],
            port=pg["port"],
            database=pg["database"],
            user=pg.get("user", "postgres"),
            password=pg.get("password", ""),
            min_size=2,
            max_size=10,
            init=_init_connection,
        )
    return _pool


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def fetch(query: str, *args, limit: int = 100) -> list[dict]:
    """Execute a query and return results as list of dicts."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows[:limit]]


async def fetchrow(query: str, *args) -> Optional[dict]:
    """Execute a query and return a single row as dict."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def fetchval(query: str, *args):
    """Execute a query and return a single value."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)
