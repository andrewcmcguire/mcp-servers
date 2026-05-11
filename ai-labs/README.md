# AI Labs MCP Server

AI research and model release intelligence over MCP/SSE.

**Port:** 8101

## Tools

| Tool | Description |
|------|-------------|
| `get_lab_activity` | HuggingFace model releases by org (52 intl orgs) |
| `get_daily_papers` | HuggingFace daily papers feed |
| `search_research` | Semantic Scholar + OpenAlex search |
| `get_package_trends` | npm/PyPI/crates.io download trends |
| `get_framework_metrics` | GitHub trending + Stack Overflow activity |

## Usage

```bash
python -m mcp-servers.ai-labs.server
```

Connect via SSE at `http://localhost:8101/sse` with `Authorization: Bearer mcp_<key>`.
