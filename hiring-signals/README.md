# Hiring Signals MCP Server

Job posting and labor market intelligence over MCP/SSE.

**Port:** 8104

## Tools

| Tool | Description |
|------|-------------|
| `get_new_roles` | New job postings across ATS platforms (Lever, Ashby, Greenhouse) |
| `detect_first_hire` | Companies posting their first ML/AI/Security role |
| `get_hiring_velocity` | Rate of new postings over time |
| `get_tech_stack_signals` | Job postings mentioning specific tech |
| `get_labor_data` | DOL H-1B, PERM, WARN act data |

## Usage

```bash
python -m mcp-servers.hiring-signals.server
```

Connect via SSE at `http://localhost:8104/sse` with `Authorization: Bearer mcp_<key>`.
