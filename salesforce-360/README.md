# Salesforce 360 MCP Server

Headless Salesforce intelligence for sales teams. Connect Claude, Cursor, or any MCP agent directly to your Salesforce org. No UI, no tabs, no clicking — just ask.

> "What do I need to know today?"

> "Give me a full 360 on Acme Corp before my call at 2pm"

> "Which of my deals are at risk right now?"

## What It Does

This MCP server connects to your Salesforce org and gives you everything a sales rep needs — without opening Salesforce. 10 tools that cover your entire workflow:

| Tool | What It Gives You |
|------|-------------------|
| `today_briefing` | Tasks due, meetings today, deals closing this week, new cases, pipeline changes |
| `account_360` | Full account view: contacts, opps, cases, activities, meetings — one command |
| `my_accounts` | Your entire book of business sorted by revenue, filterable by industry |
| `pipeline_snapshot` | Pipeline by stage with totals — see where every deal sits |
| `deal_changes` | What moved this week: stage changes, amount changes, close date pushes |
| `at_risk_deals` | Deals past close date, stale 14+ days, or pushed multiple times |
| `search_accounts` | Find any account across the org by name, industry, or keyword |
| `account_contacts` | All contacts at an account with titles, emails, and opportunity roles |
| `activity_timeline` | Recent calls, emails, tasks, meetings for your accounts |
| `forecast_summary` | 6-month pipeline forecast with weighted and unweighted totals by month |

## Setup

### 1. Create a Salesforce Connected App (one time)

In Salesforce Setup:
1. Search "App Manager" → New Connected App
2. Enable OAuth Settings
3. Callback URL: `https://login.salesforce.com/services/oauth2/callback`
4. Scopes: `api`, `refresh_token`
5. Save and note the Consumer Key and Consumer Secret

### 2. Get Your Security Token

1. Salesforce → Settings → My Personal Information → Reset My Security Token
2. Check your email for the token

### 3. Set Environment Variables

```bash
# Mac / Linux
export SF_USERNAME="you@company.com"
export SF_PASSWORD="yourpassword"
export SF_SECURITY_TOKEN="your_security_token"
export ANTHROPIC_API_KEY="sk-ant-..."    # Required for the chat web app

# Windows PowerShell
$env:SF_USERNAME = "you@company.com"
$env:SF_PASSWORD = "yourpassword"
$env:SF_SECURITY_TOKEN = "your_security_token"
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Or for sandbox orgs, also set:
```bash
export SF_DOMAIN="test"
```

### 4. Install & Run

```bash
pip install simple-salesforce anthropic mcp starlette uvicorn

git clone https://github.com/andrewcmcguire/mcp-servers.git
cd mcp-servers

python -m salesforce-360.server
```

You'll see:
```
Starting salesforce-360 on port 8107
Chat UI: http://localhost:8107
MCP endpoint: http://localhost:8107/mcp
```

### 5. Use It

**Option A: Chat Web App (recommended for salespeople)**

Open [http://localhost:8107](http://localhost:8107) in your browser. You get a chat interface — just type your questions. No setup beyond what you already did.

Quick action buttons are built in:
- **Today's briefing** — tasks, meetings, deals closing, pipeline changes
- **Pipeline** — your pipeline by stage
- **At-risk deals** — deals that need attention
- **Forecast** — weighted/unweighted forecast by month
- **Deal changes** — what moved this week

**Option B: Claude Code**
```bash
claude mcp add salesforce-360 -s user \
  --transport http \
  --url "http://localhost:8107/mcp"
```

**Option C: Claude Desktop** — add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "salesforce-360": {
      "url": "http://localhost:8107/mcp"
    }
  }
}
```

**Option D: Cursor** — add to `.cursor/mcp.json` (same format as Claude Desktop).

No gateway API key needed — it runs locally with your Salesforce credentials. The chat web app uses your Anthropic API key to power the conversation.

---

## Playbooks

### Morning Kickoff

Start every day here. One prompt, full picture.

> "Run my today briefing. Then for any deal closing this week over $50K, give me the account 360 so I can prep."

### Pre-Meeting Prep

Never walk into a call unprepared.

> "I have a meeting with Acme Corp in 30 minutes. Give me their full 360 — who are the contacts, what deals are open, any cases or recent activity I should know about?"

### Pipeline Review

Weekly pipeline inspection.

> "Show me my pipeline snapshot. Then show me deal changes from the last 7 days — what moved forward, what slipped, what got repriced? Finally, show me all at-risk deals."

### Account Planning

Deep-dive into your territory.

> "Show me all my accounts sorted by revenue. For my top 5 by ARR, give me the activity timeline for the last 30 days. Which ones haven't had any activity? Those are the ones I need to reach out to."

### Forecast Prep

Manager asking for your commit? Here's your answer.

> "Run my forecast summary. For anything closing this month, show me the deal changes — have close dates been pushed? What's the weighted vs unweighted total? Flag any deals I'm counting on that have been pushed more than once."

### Find the Right Contact

Need to reach the economic buyer?

> "Get all contacts at Acme Corp. Who has a VP or Director title? What opportunities are they attached to and what's their role? Give me their email and phone."

### Territory Gap Analysis

Figure out where you're underweight.

> "Show me my accounts grouped by industry. Which industries have the most accounts but the least pipeline? Where should I be spending more time?"

### New Rep Ramp

Just inherited a territory? Get up to speed in 5 minutes.

> "Show me all my accounts. For each one with open pipeline over $100K, give me the 360 view — I need to understand every deal, every contact, every recent activity. Summarize: which accounts need attention this week?"

---

## How It Works

This server runs locally on your machine (or your team's server). It uses the `simple-salesforce` Python library to authenticate and query your Salesforce org via SOQL. All queries run as the authenticated user, so you only see what your Salesforce permissions allow.

```
Claude Code / Claude Desktop / Cursor
    ↓ MCP protocol (Streamable HTTP)
salesforce-360 server (localhost:8107)
    ↓ SOQL via REST API
Your Salesforce Org
```

No data leaves your machine. No third-party services. Your Salesforce data stays between your client and your org.

## Requirements

- Python 3.10+
- `simple-salesforce` >= 1.12
- `mcp` >= 1.0
- `starlette` + `uvicorn`
- Salesforce org with API access enabled

## License

MIT
