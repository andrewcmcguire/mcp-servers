# GovCon MCP Server

Government contracting and federal spending intelligence over MCP/SSE.

**Port:** 8103

## Tools

| Tool | Description |
|------|-------------|
| `search_contracts` | USAspending contract search by keyword, NAICS, amount |
| `get_new_awards` | Recent federal contract awards |
| `search_grants` | Grants.gov search |
| `get_federal_register` | Federal Register notices, rules, proposed rules |
| `get_sam_opportunities` | SAM.gov active solicitations |

## Usage

```bash
python -m mcp-servers.govcon.server
```

Connect via SSE at `http://localhost:8103/sse` with `Authorization: Bearer mcp_<key>`.
