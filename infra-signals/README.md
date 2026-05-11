# Infra Signals MCP Server

Web infrastructure and AI adoption intelligence over MCP/SSE.

**Port:** 8105

## Tools

| Tool | Description |
|------|-------------|
| `get_llmstxt_adoption` | Domains with /llms.txt files |
| `get_bot_blocks` | Domains blocking AI bots in robots.txt |
| `get_cert_changes` | Certificate transparency log changes |
| `get_dns_changes` | DNS/MX record changes |
| `get_infra_summary` | Full infrastructure profile for a domain |

## Usage

```bash
python -m mcp-servers.infra-signals.server
```

Connect via SSE at `http://localhost:8105/sse` with `Authorization: Bearer mcp_<key>`.
