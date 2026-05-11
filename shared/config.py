"""
Configuration loader for MCP servers.
Reads config.json from the intelligence-ingest root directory.
"""

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.json"

_config = None


def get_config() -> dict:
    global _config
    if _config is None:
        _config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    return _config


def get_postgres_config() -> dict:
    return get_config()["postgres"]
