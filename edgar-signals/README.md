# EDGAR Signals MCP Server

SEC filing intelligence over MCP/SSE.

**Port:** 8100

## Tools

| Tool | Description |
|------|-------------|
| `search_filings` | Full-text search across EDGAR diffs by keyword, form type, ticker |
| `get_stealth_fundraises` | Form D filings with no press coverage |
| `get_insider_clusters` | Clustered insider buys/sells from Form 4 |
| `get_language_drift` | 10-K/10-Q text changes between filings |
| `get_8k_triggers` | Item-level 8-K events (departures, material agreements, etc.) |
| `get_bdc_stress` | BDC 10-Q monitors for private credit signals |

## Usage

```bash
python -m mcp-servers.edgar-signals.server
```

Connect via SSE at `http://localhost:8100/sse` with `Authorization: Bearer mcp_<key>`.
