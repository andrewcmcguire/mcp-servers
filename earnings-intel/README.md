# Earnings Intel MCP Server

Earnings call and transcript intelligence over MCP/SSE.

**Port:** 8102

## Tools

| Tool | Description |
|------|-------------|
| `get_earnings_schedule` | Upcoming earnings with webcast URLs |
| `get_transcript` | Speaker-level transcript segments |
| `search_transcripts` | Full-text search across all transcripts |
| `get_vendor_mentions` | Which companies mentioned a specific vendor |
| `get_guidance_signals` | Raised/lowered guidance, CFO language signals |

## Usage

```bash
python -m mcp-servers.earnings-intel.server
```

Connect via SSE at `http://localhost:8102/sse` with `Authorization: Bearer mcp_<key>`.
