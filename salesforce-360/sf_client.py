"""
Salesforce REST API client — async wrapper around simple-salesforce.

Handles authentication (username/password + security token or OAuth2)
and provides async SOQL query execution.
"""

import asyncio
import logging
import os
from functools import lru_cache
from typing import Any

from simple_salesforce import Salesforce

logger = logging.getLogger("sf-360")

_sf_instance = None


def _get_sf() -> Salesforce:
    global _sf_instance
    if _sf_instance is not None:
        return _sf_instance

    username = os.environ.get("SF_USERNAME", "")
    password = os.environ.get("SF_PASSWORD", "")
    security_token = os.environ.get("SF_SECURITY_TOKEN", "")
    domain = os.environ.get("SF_DOMAIN", "login")
    instance_url = os.environ.get("SF_INSTANCE_URL", "")
    access_token = os.environ.get("SF_ACCESS_TOKEN", "")

    if access_token and instance_url:
        _sf_instance = Salesforce(instance_url=instance_url, session_id=access_token)
    elif username and password:
        _sf_instance = Salesforce(
            username=username,
            password=password,
            security_token=security_token,
            domain=domain,
        )
    else:
        raise RuntimeError(
            "Salesforce credentials not configured. Set SF_USERNAME + SF_PASSWORD + SF_SECURITY_TOKEN, "
            "or SF_ACCESS_TOKEN + SF_INSTANCE_URL as environment variables."
        )

    logger.info(f"Connected to Salesforce: {_sf_instance.sf_instance}")
    return _sf_instance


async def soql(query: str) -> list[dict[str, Any]]:
    sf = _get_sf()
    result = await asyncio.to_thread(sf.query_all, query)
    records = result.get("records", [])
    for r in records:
        r.pop("attributes", None)
    return records


async def soql_one(query: str) -> dict[str, Any] | None:
    rows = await soql(query)
    return rows[0] if rows else None


async def get_current_user_id() -> str:
    sf = _get_sf()
    identity = await asyncio.to_thread(lambda: sf.restful("", {}))
    return identity.get("user_id", "")


def get_sf_instance_url() -> str:
    sf = _get_sf()
    return f"https://{sf.sf_instance}"
