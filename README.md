# MCP Intelligence Servers

Seven MCP servers querying a 1,470-source intelligence pipeline. SEC filings. AI lab releases. Earnings calls with NLP deception scoring. Hiring signals. Government contracts. Infrastructure changes.

Connect Claude Code, Claude Desktop, Cursor, or any MCP-compatible agent. First 50 API keys free.

**Live endpoint:** `https://mcp.andrewcmcguire.com`

## Servers

| Server | Tools | Data Points | Description |
|--------|-------|-------------|-------------|
| **edgar-signals** | 5 | 32K+ | SEC filings, insider trades, Form D stealth fundraises, 8-K events, 13F holdings |
| **ai-labs** | 5 | 6K+ | 60+ AI orgs across HuggingFace, GitHub, arXiv, blogs — model releases, papers, research |
| **earnings-intel** | 5 | 13.7K+ | Earnings events, analyst revisions, earnings movers, NASDAQ calendar |
| **govcon** | 5 | 3.5K+ | Federal Register, congressional trades, lobbying disclosures, policy prediction markets |
| **hiring-signals** | 5 | 3.6K+ | Job postings across Greenhouse, Ashby, Lever — hiring velocity, first-hire detection |
| **infra-signals** | 5 | 1K+ | Cert transparency, GitHub releases, HuggingFace trending, MCP ecosystem tracking |
| **live-calls** | 8 | 27K+ | Live earnings call transcripts, NLP insights, deception scoring, real-time alerts |

38 tools. 60K+ data points. Streamable HTTP transport.

---

## Quick Start

### 1. Get your API key

```bash
curl -X POST https://mcp.andrewcmcguire.com/mcp/request-key \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Your Name",
    "email": "you@example.com",
    "use_case": "What you are building"
  }'
```

You'll get back a key like `mcp_abc123...` — save it.

### 2. Connect

All servers are accessed through a single gateway URL using the pattern:

```
https://mcp.andrewcmcguire.com/s/{server-name}/mcp
```

Replace `{server-name}` with: `edgar-signals`, `ai-labs`, `earnings-intel`, `govcon`, `hiring-signals`, `infra-signals`, or `live-calls`.

---

## Setup by Client

### Claude Code

Run these commands in your terminal to add servers globally (available in every session):

```bash
claude mcp add edgar-signals -s user \
  --transport http \
  --url "https://mcp.andrewcmcguire.com/s/edgar-signals/mcp" \
  --header "Authorization: Bearer YOUR_API_KEY"

claude mcp add ai-labs -s user \
  --transport http \
  --url "https://mcp.andrewcmcguire.com/s/ai-labs/mcp" \
  --header "Authorization: Bearer YOUR_API_KEY"

claude mcp add earnings-intel -s user \
  --transport http \
  --url "https://mcp.andrewcmcguire.com/s/earnings-intel/mcp" \
  --header "Authorization: Bearer YOUR_API_KEY"

claude mcp add govcon -s user \
  --transport http \
  --url "https://mcp.andrewcmcguire.com/s/govcon/mcp" \
  --header "Authorization: Bearer YOUR_API_KEY"

claude mcp add hiring-signals -s user \
  --transport http \
  --url "https://mcp.andrewcmcguire.com/s/hiring-signals/mcp" \
  --header "Authorization: Bearer YOUR_API_KEY"

claude mcp add infra-signals -s user \
  --transport http \
  --url "https://mcp.andrewcmcguire.com/s/infra-signals/mcp" \
  --header "Authorization: Bearer YOUR_API_KEY"

claude mcp add live-calls -s user \
  --transport http \
  --url "https://mcp.andrewcmcguire.com/s/live-calls/mcp" \
  --header "Authorization: Bearer YOUR_API_KEY"
```

Or add a project-level `.mcp.json` to any repo:

```json
{
  "mcpServers": {
    "edgar-signals": {
      "type": "url",
      "url": "https://mcp.andrewcmcguire.com/s/edgar-signals/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    },
    "ai-labs": {
      "type": "url",
      "url": "https://mcp.andrewcmcguire.com/s/ai-labs/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    },
    "earnings-intel": {
      "type": "url",
      "url": "https://mcp.andrewcmcguire.com/s/earnings-intel/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    },
    "govcon": {
      "type": "url",
      "url": "https://mcp.andrewcmcguire.com/s/govcon/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    },
    "hiring-signals": {
      "type": "url",
      "url": "https://mcp.andrewcmcguire.com/s/hiring-signals/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    },
    "infra-signals": {
      "type": "url",
      "url": "https://mcp.andrewcmcguire.com/s/infra-signals/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    },
    "live-calls": {
      "type": "url",
      "url": "https://mcp.andrewcmcguire.com/s/live-calls/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    }
  }
}
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "edgar-signals": {
      "url": "https://mcp.andrewcmcguire.com/s/edgar-signals/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    },
    "ai-labs": {
      "url": "https://mcp.andrewcmcguire.com/s/ai-labs/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    },
    "earnings-intel": {
      "url": "https://mcp.andrewcmcguire.com/s/earnings-intel/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    },
    "govcon": {
      "url": "https://mcp.andrewcmcguire.com/s/govcon/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    },
    "hiring-signals": {
      "url": "https://mcp.andrewcmcguire.com/s/hiring-signals/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    },
    "infra-signals": {
      "url": "https://mcp.andrewcmcguire.com/s/infra-signals/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    },
    "live-calls": {
      "url": "https://mcp.andrewcmcguire.com/s/live-calls/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json` in your project root — same format as Claude Desktop above.

### Python SDK

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client(
    "https://mcp.andrewcmcguire.com/s/edgar-signals/mcp",
    headers={"Authorization": "Bearer YOUR_API_KEY"}
) as (read_stream, write_stream, _):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("search_filings", {"query": "artificial intelligence", "form_type": "form4"})
```

---

## Example Prompts

Once connected, just ask in natural language. Here are real queries you can run:

### SEC / Edgar Signals

> "Find AI companies that filed Form D in the last 14 days with no press coverage"

> "Show me insider trading clusters — tickers where 3+ insiders traded in the last 30 days"

> "Get all 8-K filings with item 5.02 (officer departures) this week"

> "What 13F institutional holdings were filed for NVDA this quarter?"

### AI Lab Tracking

> "What did DeepSeek, Qwen, and Mistral ship this week?"

> "Show me all arxiv papers on reasoning and agents from the last 7 days"

> "Get Anthropic's GitHub activity — new repos, releases, and commits"

> "What models are trending on HuggingFace right now?"

### Earnings Intelligence

> "Which stocks moved 10%+ on earnings this month?"

> "Show me analyst downgrades in the last 2 weeks"

> "What's on the earnings calendar for next week?"

> "Find all earnings events for TSLA in the last 90 days"

### Government / Regulatory

> "Congressional stock trades in AI companies this quarter"

> "What executive orders were published this month?"

> "Show lobbying activity related to cryptocurrency"

> "What do prediction markets say about upcoming tariff decisions?"

### Hiring Signals

> "Companies that posted their first ML Engineer role this month"

> "Show me Anthropic's hiring velocity over the last 90 days"

> "Search for all Rust engineer roles posted in the last 30 days"

> "Give me a complete hiring snapshot for SpaceX"

### Infrastructure / Ecosystem

> "NVIDIA GitHub releases this month"

> "Show certificate transparency events for openai.com — any new subdomains?"

> "What's happening in the MCP ecosystem — spec changes, SDK updates?"

> "Get trending HuggingFace models and datasets"

### Live Earnings Calls

> "Which CEOs showed high deception scores on their last earnings call?"

> "Get the full transcript for NVDA's most recent earnings call"

> "Show me all calls with signal scores above 0.8 — strong bullish or bearish"

> "Search earnings call transcripts for mentions of 'tariff' or 'supply chain'"

> "What earnings calls are coming up this week that have webcast URLs?"

> "Give me the master call directory for all FAANG companies with transcripts"

### Multi-Server Queries

> "Cross-reference: companies where insiders are selling AND the CEO showed high deception on their last earnings call"

> "Find AI companies that are hiring aggressively, just filed Form D, and have no press coverage"

> "Which companies had earnings beats of 10%+ AND are being bought by Congress members?"

---

## Full Tool Reference

### edgar-signals

| Tool | Description |
|------|-------------|
| `search_filings` | Search SEC filing diffs by keyword, form type, ticker. Covers 25K+ Form 4s, 4K+ 8-Ks, 10-Qs, 10-Ks, 13Fs |
| `get_insider_trades` | Insider trading from Form 4 + Unusual Whales. Filter by ticker |
| `get_insider_clusters` | Detect clusters of insider activity — tickers with 3+ trades in a window |
| `get_8k_events` | Material event filings. Filter by item type (1.01, 2.01, 5.02, 7.01, 8.01) |
| `get_13f_holdings` | Institutional holdings from 13F filings ($100M+ AUM managers) |

### ai-labs

| Tool | Description |
|------|-------------|
| `get_lab_activity` | Activity across 60+ AI orgs — models, papers, blogs, GitHub. Filter by org |
| `get_daily_papers` | arXiv papers: cs.LG, cs.AI, cs.CL, cs.CV, stat.ML, q-fin. Filter by topic |
| `search_research` | Full-text search across all AI papers, blogs, and announcements |
| `get_github_activity` | GitHub repos from xAI, Anthropic, SpaceX, Databricks, CoreWeave, Scale AI |
| `get_model_releases` | HuggingFace model uploads from 52 international AI orgs |

### earnings-intel

| Tool | Description |
|------|-------------|
| `get_earnings_events` | Earnings beats, misses, and scheduled calls. 6K+ synthetic signals |
| `get_analyst_revisions` | Upgrades, downgrades, price target changes. 9.8K+ signals |
| `search_earnings` | Full-text search across earnings events and analyst data |
| `get_earnings_movers` | Stocks with significant earnings-driven moves. Filter by min % change |
| `get_earnings_schedule` | NASDAQ earnings calendar — upcoming and recent dates |

### govcon

| Tool | Description |
|------|-------------|
| `get_federal_register` | Federal Register notices, rules, and executive orders (190+ entries) |
| `get_congressional_trades` | STOCK Act disclosures + Capitol Trades. 2.1K+ trade signals |
| `get_lobbying_activity` | LDA filings, contributions, OpenFEC data |
| `get_policy_markets` | Kalshi (600) + Polymarket (140) regulatory prediction markets |
| `search_regulatory` | Full-text search across all government/regulatory sources |

### hiring-signals

| Tool | Description |
|------|-------------|
| `get_new_roles` | New job postings across Greenhouse, Ashby, Lever ATS platforms |
| `detect_first_hire` | Companies posting their first role in a function (e.g., first ML Engineer) |
| `get_hiring_velocity` | Weekly posting rate for a company — acceleration/deceleration trends |
| `search_roles` | Full-text search across all job postings by title or keyword |
| `get_company_snapshot` | Complete hiring snapshot — open roles, categories, recent postings |

### infra-signals

| Tool | Description |
|------|-------------|
| `get_github_releases` | Releases from NVIDIA, Anthropic, Google DeepMind, Meta, vLLM, LangChain, etc. |
| `get_trending_models` | Trending models and datasets on HuggingFace with rank changes |
| `get_cert_transparency` | TLS certificate events for AI companies — new subdomains, infra changes |
| `get_mcp_ecosystem` | MCP spec, Python/TS SDKs, official servers, community activity |
| `search_infra` | Full-text search across all infrastructure and ecosystem signals |

### live-calls

| Tool | Description |
|------|-------------|
| `get_call_insights` | NLP-extracted insights: sentiment, deception scores, guidance, signal scores, key quotes |
| `get_transcripts` | Earnings call transcripts with metadata. Set `include_text=true` for full text |
| `get_deception_signals` | Calls where deception probability exceeds threshold (Larcker-Zakolyukina markers) |
| `get_live_alerts` | Real-time alerts from live call monitoring (signal_score >= 0.70) |
| `get_upcoming_calls` | Scheduled earnings calls with webcast URLs, EPS/revenue estimates |
| `search_call_content` | Full-text search across transcripts and NLP insights |
| `get_call_monitor_status` | Status of live call monitoring — active transcriptions, chunk progress |
| `get_call_directory` | Master directory: 26K+ calls, 5,192 tickers, linked transcripts and insights |

---

## Gateway Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Gateway info |
| `/mcp/request-key` | POST | Request an API key |
| `/mcp/servers` | GET | List all servers with connection info |
| `/mcp/health` | GET | Aggregate health check (all 7 servers) |
| `/s/{server}/mcp` | POST/GET/DELETE | Proxy to individual MCP server |

## Architecture

- **Transport**: Streamable HTTP — works through Cloudflare tunnels, proxies, and firewalls
- **Auth**: Bearer token with auto-registration, 100 req/day rate limit
- **Database**: Bitemporal PostgreSQL — all changes tracked as diffs with temporal validity
- **NLP Pipeline**: Earnings call deception scoring using Larcker-Zakolyukina linguistic markers
- **Infrastructure**: Cloudflare Tunnel to gateway, gateway proxies to 7 backend servers

## Self-Hosting

```bash
git clone https://github.com/andrewcmcguire/mcp-servers.git
cd mcp-servers

cp config.example.json config.json
# Edit config.json with your Postgres credentials

pip install -r requirements.txt

# Start all servers
python run_all.py

# Or specific servers
python run_all.py --only edgar-signals ai-labs live-calls

# Start the gateway (port 8099)
python gateway.py
```

## Rate Limits

- 100 requests per day per key
- Maximum 50 keys
- No payment required

## License

MIT

## Author

Andrew McGuire — [andrewcmcguire.com](https://andrewcmcguire.com)
