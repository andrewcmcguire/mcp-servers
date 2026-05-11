# MCP Intelligence Servers

Six MCP servers querying a 1,470-source intelligence pipeline. SEC filings. AI lab releases. Earnings calls. Hiring signals. Government contracts. Infrastructure changes.

Connect Claude, Cursor, or any MCP-compatible agent. First 50 API keys free.

## Servers

| Server | Port | Tools | Description |
|--------|------|-------|-------------|
| **edgar-signals** | 8100 | 5 | SEC filings, insider trades, 8-K events, 13F holdings |
| **ai-labs** | 8101 | 5 | 60+ AI orgs — model releases, papers, GitHub activity |
| **earnings-intel** | 8102 | 5 | Earnings events, analyst revisions, movers, calendar |
| **govcon** | 8103 | 5 | Federal Register, congressional trades, lobbying, policy markets |
| **hiring-signals** | 8104 | 5 | Job postings across Greenhouse, Ashby, Lever — velocity, first-hires |
| **infra-signals** | 8105 | 5 | Cert transparency, GitHub releases, HuggingFace trending, MCP ecosystem |
| **gateway** | 8099 | — | API key requests, server directory, health checks |

30 tools. 60K+ data points. Streamable HTTP transport.

## Quick Start

### 1. Request a key

```bash
curl -X POST https://mcp.andrewcmcguire.com/mcp/request-key \
  -H "Content-Type: application/json" \
  -d '{"name": "Your Name", "email": "you@example.com", "use_case": "What you are building"}'
```

### 2. Connect

**Claude Desktop** — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hiring-signals": {
      "url": "https://mcp.andrewcmcguire.com:8104/mcp",
      "headers": {
        "Authorization": "Bearer mcp_your_key_here"
      }
    }
  }
}
```

**Python:**

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client(
    "https://mcp.andrewcmcguire.com:8104/mcp",
    headers={"Authorization": "Bearer mcp_your_key_here"}
) as (read_stream, write_stream, _):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("get_new_roles", {"company": "anthropic"})
```

### 3. Explore

```bash
# List all servers
curl https://mcp.andrewcmcguire.com/mcp/servers

# Health check
curl https://mcp.andrewcmcguire.com/mcp/health
```

## Self-Hosting

```bash
cp config.example.json config.json
# Edit config.json with your Postgres credentials

pip install -r requirements.txt

# Start all servers
cd mcp-servers
python run_all.py

# Or start individual servers
python run_all.py --only hiring-signals ai-labs

# Start the gateway
python gateway.py
```

## Architecture

- **Transport**: Streamable HTTP (works through Cloudflare tunnels, proxies, and firewalls)
- **Auth**: Bearer token with auto-registration, 100 req/day rate limit
- **Database**: Bitemporal PostgreSQL — all changes tracked as diffs
- **Inference**: Local LLM scoring via Qwen on RTX 3090

## Rate Limits

- 100 requests per day per key
- Maximum 50 keys
- No payment required

## License

MIT

## Author

Andrew McGuire — [andrewcmcguire.com](https://andrewcmcguire.com)
