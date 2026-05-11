"""
Bearer token authentication and rate limiting.

API keys are stored in the mcp_api_keys table. For development, any key
matching the pattern 'mcp_*' is accepted. Rate limit: 100 requests/day per key.
Max 50 keys total.
"""

import re
from datetime import date
from typing import Optional

from .db import get_pool

_DEV_KEY_PATTERN = re.compile(r"^mcp_.+$")
DAILY_LIMIT = 100
MAX_KEYS = 50

_keys_table_ready = False


async def _ensure_keys_table():
    """Create mcp_api_keys table if it doesn't exist."""
    global _keys_table_ready
    if _keys_table_ready:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS public.mcp_api_keys (
                api_key TEXT PRIMARY KEY,
                owner TEXT,
                created_at TIMESTAMPTZ DEFAULT now(),
                daily_count INT DEFAULT 0,
                last_used DATE DEFAULT CURRENT_DATE
            )
        """)
    _keys_table_ready = True


async def validate_bearer_token(api_key: str) -> Optional[str]:
    """
    Validate key and increment counter.
    Returns None if OK, error string otherwise.
    """
    try:
        await _ensure_keys_table()
    except Exception:
        if _DEV_KEY_PATTERN.match(api_key):
            return None
        return "Database unavailable"

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT daily_count, last_used FROM public.mcp_api_keys WHERE api_key = $1",
            api_key,
        )

        today = date.today()

        if row is None:
            if _DEV_KEY_PATTERN.match(api_key):
                key_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM public.mcp_api_keys"
                )
                if key_count >= MAX_KEYS:
                    return f"Maximum API keys reached ({MAX_KEYS}). No new keys available."
                await conn.execute(
                    """INSERT INTO public.mcp_api_keys (api_key, owner, daily_count, last_used)
                       VALUES ($1, 'dev', 1, $2)
                       ON CONFLICT (api_key) DO NOTHING""",
                    api_key, today,
                )
                return None
            return "Invalid API key"

        daily_count = row["daily_count"]
        last_used = row["last_used"]

        if last_used is None or last_used < today:
            daily_count = 0

        if daily_count >= DAILY_LIMIT:
            return f"Rate limit exceeded ({DAILY_LIMIT}/day)"

        await conn.execute(
            """UPDATE public.mcp_api_keys
               SET daily_count = $1, last_used = $2
               WHERE api_key = $3""",
            daily_count + 1, today, api_key,
        )
        return None
