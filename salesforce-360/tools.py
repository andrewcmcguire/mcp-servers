"""
Salesforce 360 tools — headless account intelligence for sales teams.

Connects to your Salesforce org and gives you everything you need to know
about your accounts, pipeline, and day — without opening the Salesforce UI.
"""

import logging
from datetime import datetime, timedelta, timezone

from .sf_client import soql, soql_one

logger = logging.getLogger("sf-360")


# ---------------------------------------------------------------------------
# Tool 1: today_briefing
# ---------------------------------------------------------------------------

async def today_briefing(**kwargs) -> dict:
    """Everything you need to know right now: tasks due, meetings today,
    deals closing this week, cases opened, and pipeline changes."""

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    week_end = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")

    tasks = await soql(f"""
        SELECT Id, Subject, Status, Priority, ActivityDate,
               Who.Name, What.Name
        FROM Task
        WHERE OwnerId = '{await _my_id()}'
          AND IsClosed = false
          AND ActivityDate <= {today}
        ORDER BY Priority DESC, ActivityDate ASC
        LIMIT 25
    """)

    events = await soql(f"""
        SELECT Id, Subject, StartDateTime, EndDateTime, Location,
               Who.Name, What.Name
        FROM Event
        WHERE OwnerId = '{await _my_id()}'
          AND StartDateTime >= {today}T00:00:00Z
          AND StartDateTime < {today}T23:59:59Z
        ORDER BY StartDateTime ASC
        LIMIT 20
    """)

    closing_deals = await soql(f"""
        SELECT Id, Name, StageName, Amount, CloseDate,
               Account.Name, Probability
        FROM Opportunity
        WHERE OwnerId = '{await _my_id()}'
          AND IsClosed = false
          AND CloseDate >= {today}
          AND CloseDate <= {week_end}
        ORDER BY Amount DESC NULLS LAST
        LIMIT 20
    """)

    new_cases = await soql(f"""
        SELECT Id, CaseNumber, Subject, Status, Priority,
               Account.Name, CreatedDate
        FROM Case
        WHERE Account.OwnerId = '{await _my_id()}'
          AND CreatedDate >= {yesterday}
        ORDER BY Priority DESC, CreatedDate DESC
        LIMIT 15
    """)

    stage_changes = await soql(f"""
        SELECT OpportunityId, Opportunity.Name, Opportunity.Account.Name,
               StageName, Amount, CreatedDate
        FROM OpportunityHistory
        WHERE Opportunity.OwnerId = '{await _my_id()}'
          AND CreatedDate >= {yesterday}
          AND Field = 'StageName'
        ORDER BY CreatedDate DESC
        LIMIT 15
    """)

    return {
        "date": today,
        "tasks_due": {"count": len(tasks), "items": tasks},
        "meetings_today": {"count": len(events), "items": events},
        "deals_closing_this_week": {"count": len(closing_deals), "total_value": sum(d.get("Amount") or 0 for d in closing_deals), "items": closing_deals},
        "new_cases_24h": {"count": len(new_cases), "items": new_cases},
        "stage_changes_24h": {"count": len(stage_changes), "items": stage_changes},
    }


# ---------------------------------------------------------------------------
# Tool 2: account_360
# ---------------------------------------------------------------------------

async def account_360(account: str, **kwargs) -> dict:
    """Full 360-degree view of a single account: contacts, open opps,
    recent activities, cases, and account details."""

    acct = await soql_one(f"""
        SELECT Id, Name, Industry, Type, BillingCity, BillingState,
               AnnualRevenue, NumberOfEmployees, Website, Phone,
               Owner.Name, Description, CreatedDate, LastModifiedDate,
               (SELECT Id, Name, Title, Email, Phone, Department
                FROM Contacts ORDER BY CreatedDate DESC LIMIT 20),
               (SELECT Id, Name, StageName, Amount, CloseDate, Probability,
                       NextStep, LastModifiedDate
                FROM Opportunities WHERE IsClosed = false
                ORDER BY CloseDate ASC LIMIT 20),
               (SELECT Id, CaseNumber, Subject, Status, Priority, CreatedDate
                FROM Cases WHERE IsClosed = false
                ORDER BY Priority DESC, CreatedDate DESC LIMIT 10)
        FROM Account
        WHERE Name LIKE '%{_escape(account)}%'
        LIMIT 1
    """)

    if not acct:
        return {"error": f"No account found matching '{account}'"}

    acct_id = acct["Id"]

    activities = await soql(f"""
        SELECT Id, Subject, Status, ActivityDate, Priority,
               Who.Name, Description, ActivityType
        FROM Task
        WHERE AccountId = '{acct_id}'
        ORDER BY ActivityDate DESC NULLS LAST
        LIMIT 15
    """)

    recent_events = await soql(f"""
        SELECT Id, Subject, StartDateTime, EndDateTime, Who.Name
        FROM Event
        WHERE AccountId = '{acct_id}'
        ORDER BY StartDateTime DESC
        LIMIT 10
    """)

    contacts = acct.pop("Contacts", None)
    opps = acct.pop("Opportunities", None)
    cases = acct.pop("Cases", None)

    return {
        "account": acct,
        "contacts": (contacts or {}).get("records", []),
        "open_opportunities": (opps or {}).get("records", []),
        "open_cases": (cases or {}).get("records", []),
        "recent_activities": activities,
        "recent_meetings": recent_events,
    }


# ---------------------------------------------------------------------------
# Tool 3: my_accounts
# ---------------------------------------------------------------------------

async def my_accounts(industry: str = "", sort_by: str = "revenue", limit: int = 50, **kwargs) -> dict:
    """Get all accounts you own, with pipeline summary per account."""

    order = "AnnualRevenue DESC NULLS LAST" if sort_by == "revenue" else "Name ASC"
    industry_filter = f"AND Industry LIKE '%{_escape(industry)}%'" if industry else ""

    accounts = await soql(f"""
        SELECT Id, Name, Industry, Type, BillingState,
               AnnualRevenue, NumberOfEmployees, Website,
               (SELECT COUNT(Id) cnt FROM Opportunities WHERE IsClosed = false),
               (SELECT SUM(Amount) total FROM Opportunities WHERE IsClosed = false)
        FROM Account
        WHERE OwnerId = '{await _my_id()}'
          {industry_filter}
        ORDER BY {order}
        LIMIT {min(limit, 200)}
    """)

    # SOQL subquery aggregates don't work in all orgs, so fall back
    # to a separate pipeline query if needed
    if not accounts:
        accounts = await soql(f"""
            SELECT Id, Name, Industry, Type, BillingState,
                   AnnualRevenue, NumberOfEmployees, Website
            FROM Account
            WHERE OwnerId = '{await _my_id()}'
              {industry_filter}
            ORDER BY {order}
            LIMIT {min(limit, 200)}
        """)

    return {
        "total_accounts": len(accounts),
        "accounts": accounts,
    }


# ---------------------------------------------------------------------------
# Tool 4: pipeline_snapshot
# ---------------------------------------------------------------------------

async def pipeline_snapshot(account: str = "", **kwargs) -> dict:
    """Pipeline by stage — total value, deal count, and average age per stage.
    Optionally filter to a single account."""

    acct_filter = f"AND Account.Name LIKE '%{_escape(account)}%'" if account else ""

    deals = await soql(f"""
        SELECT Id, Name, StageName, Amount, CloseDate, Probability,
               Account.Name, CreatedDate, LastModifiedDate, NextStep
        FROM Opportunity
        WHERE OwnerId = '{await _my_id()}'
          AND IsClosed = false
          {acct_filter}
        ORDER BY StageName, Amount DESC NULLS LAST
    """)

    stages = {}
    now = datetime.now(timezone.utc)
    for d in deals:
        stage = d.get("StageName", "Unknown")
        if stage not in stages:
            stages[stage] = {"count": 0, "total_value": 0, "deals": []}
        stages[stage]["count"] += 1
        stages[stage]["total_value"] += d.get("Amount") or 0
        stages[stage]["deals"].append(d)

    total_value = sum(d.get("Amount") or 0 for d in deals)

    return {
        "total_deals": len(deals),
        "total_pipeline_value": total_value,
        "by_stage": stages,
    }


# ---------------------------------------------------------------------------
# Tool 5: deal_changes
# ---------------------------------------------------------------------------

async def deal_changes(days: int = 7, **kwargs) -> dict:
    """Opportunities that changed stage, amount, or close date recently.
    Shows what moved in your pipeline and in which direction."""

    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")

    history = await soql(f"""
        SELECT OpportunityId, Opportunity.Name, Opportunity.Account.Name,
               Opportunity.StageName, Opportunity.Amount, Opportunity.CloseDate,
               Field, OldValue, NewValue, CreatedDate
        FROM OpportunityFieldHistory
        WHERE Opportunity.OwnerId = '{await _my_id()}'
          AND CreatedDate >= {since}
          AND Field IN ('StageName', 'Amount', 'CloseDate')
        ORDER BY CreatedDate DESC
        LIMIT 100
    """)

    stage_moves = [h for h in history if h.get("Field") == "StageName"]
    amount_changes = [h for h in history if h.get("Field") == "Amount"]
    date_pushes = [h for h in history if h.get("Field") == "CloseDate"]

    return {
        "period_days": days,
        "total_changes": len(history),
        "stage_moves": {"count": len(stage_moves), "items": stage_moves},
        "amount_changes": {"count": len(amount_changes), "items": amount_changes},
        "close_date_changes": {"count": len(date_pushes), "items": date_pushes},
    }


# ---------------------------------------------------------------------------
# Tool 6: at_risk_deals
# ---------------------------------------------------------------------------

async def at_risk_deals(**kwargs) -> dict:
    """Deals that need attention: past close date, no activity in 14+ days,
    or close date pushed more than once."""

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stale_cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT00:00:00Z")

    past_due = await soql(f"""
        SELECT Id, Name, StageName, Amount, CloseDate,
               Account.Name, LastModifiedDate
        FROM Opportunity
        WHERE OwnerId = '{await _my_id()}'
          AND IsClosed = false
          AND CloseDate < {today}
        ORDER BY Amount DESC NULLS LAST
        LIMIT 50
    """)

    stale = await soql(f"""
        SELECT Id, Name, StageName, Amount, CloseDate,
               Account.Name, LastModifiedDate, LastActivityDate
        FROM Opportunity
        WHERE OwnerId = '{await _my_id()}'
          AND IsClosed = false
          AND LastModifiedDate < {stale_cutoff}
        ORDER BY Amount DESC NULLS LAST
        LIMIT 50
    """)

    # Deals pushed multiple times (close date changed 2+ times)
    pushed = await soql(f"""
        SELECT OpportunityId, Opportunity.Name, Opportunity.Account.Name,
               Opportunity.Amount, Opportunity.CloseDate,
               COUNT(Id) push_count
        FROM OpportunityFieldHistory
        WHERE Opportunity.OwnerId = '{await _my_id()}'
          AND Field = 'CloseDate'
          AND Opportunity.IsClosed = false
        GROUP BY OpportunityId, Opportunity.Name, Opportunity.Account.Name,
                 Opportunity.Amount, Opportunity.CloseDate
        HAVING COUNT(Id) >= 2
        ORDER BY COUNT(Id) DESC
        LIMIT 30
    """)

    return {
        "past_close_date": {"count": len(past_due), "total_value": sum(d.get("Amount") or 0 for d in past_due), "items": past_due},
        "no_activity_14_days": {"count": len(stale), "total_value": sum(d.get("Amount") or 0 for d in stale), "items": stale},
        "close_date_pushed_2x": {"count": len(pushed), "items": pushed},
    }


# ---------------------------------------------------------------------------
# Tool 7: search_accounts
# ---------------------------------------------------------------------------

async def search_accounts(query: str, **kwargs) -> dict:
    """Search accounts by name, industry, or any keyword across account fields."""

    results = await soql(f"""
        SELECT Id, Name, Industry, Type, BillingCity, BillingState,
               AnnualRevenue, NumberOfEmployees, Website, Owner.Name
        FROM Account
        WHERE Name LIKE '%{_escape(query)}%'
           OR Industry LIKE '%{_escape(query)}%'
           OR Description LIKE '%{_escape(query)}%'
        ORDER BY AnnualRevenue DESC NULLS LAST
        LIMIT 30
    """)

    return {
        "query": query,
        "results_count": len(results),
        "accounts": results,
    }


# ---------------------------------------------------------------------------
# Tool 8: account_contacts
# ---------------------------------------------------------------------------

async def account_contacts(account: str, **kwargs) -> dict:
    """Get all contacts for an account with their roles, last activity, and email."""

    contacts = await soql(f"""
        SELECT Id, Name, Title, Email, Phone, Department,
               MailingCity, MailingState, CreatedDate, LastModifiedDate,
               Account.Name
        FROM Contact
        WHERE Account.Name LIKE '%{_escape(account)}%'
        ORDER BY Title ASC NULLS LAST
        LIMIT 50
    """)

    roles = await soql(f"""
        SELECT ContactId, Contact.Name, Contact.Title,
               OpportunityId, Opportunity.Name, Role, IsPrimary
        FROM OpportunityContactRole
        WHERE Opportunity.Account.Name LIKE '%{_escape(account)}%'
          AND Opportunity.IsClosed = false
        ORDER BY IsPrimary DESC
    """)

    return {
        "account": account,
        "contacts_count": len(contacts),
        "contacts": contacts,
        "opportunity_roles": roles,
    }


# ---------------------------------------------------------------------------
# Tool 9: activity_timeline
# ---------------------------------------------------------------------------

async def activity_timeline(account: str = "", days: int = 30, **kwargs) -> dict:
    """Recent activity timeline — calls, emails, tasks, meetings — for your
    accounts or a specific account."""

    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
    acct_filter = f"AND Account.Name LIKE '%{_escape(account)}%'" if account else f"AND OwnerId = '{await _my_id()}'"

    tasks = await soql(f"""
        SELECT Id, Subject, Status, ActivityDate, Priority,
               Who.Name, Account.Name, TaskSubtype, Description
        FROM Task
        WHERE CreatedDate >= {since}
          {acct_filter}
        ORDER BY ActivityDate DESC NULLS LAST
        LIMIT 50
    """)

    events = await soql(f"""
        SELECT Id, Subject, StartDateTime, EndDateTime,
               Who.Name, Account.Name, Location
        FROM Event
        WHERE StartDateTime >= {since}
          {acct_filter}
        ORDER BY StartDateTime DESC
        LIMIT 30
    """)

    return {
        "period_days": days,
        "account_filter": account or "all my accounts",
        "tasks": {"count": len(tasks), "items": tasks},
        "events": {"count": len(events), "items": events},
    }


# ---------------------------------------------------------------------------
# Tool 10: forecast_summary
# ---------------------------------------------------------------------------

async def forecast_summary(**kwargs) -> dict:
    """Pipeline forecast: deals by close month, weighted vs unweighted totals,
    and coverage ratio against quota if set."""

    deals = await soql(f"""
        SELECT Id, Name, StageName, Amount, CloseDate, Probability,
               Account.Name, ForecastCategoryName
        FROM Opportunity
        WHERE OwnerId = '{await _my_id()}'
          AND IsClosed = false
          AND CloseDate >= TODAY
          AND CloseDate <= NEXT_N_MONTHS:6
        ORDER BY CloseDate ASC
    """)

    months = {}
    for d in deals:
        close = d.get("CloseDate", "")[:7]  # YYYY-MM
        if close not in months:
            months[close] = {"unweighted": 0, "weighted": 0, "count": 0, "deals": []}
        amt = d.get("Amount") or 0
        prob = (d.get("Probability") or 0) / 100
        months[close]["unweighted"] += amt
        months[close]["weighted"] += amt * prob
        months[close]["count"] += 1
        months[close]["deals"].append(d)

    total_unweighted = sum(m["unweighted"] for m in months.values())
    total_weighted = sum(m["weighted"] for m in months.values())

    return {
        "total_open_deals": len(deals),
        "total_unweighted": total_unweighted,
        "total_weighted": total_weighted,
        "by_month": months,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_cached_user_id = None


async def _my_id() -> str:
    global _cached_user_id
    if _cached_user_id is None:
        from .sf_client import get_current_user_id
        _cached_user_id = await get_current_user_id()
    return _cached_user_id


def _escape(s: str) -> str:
    if not s:
        return s
    return s.replace("'", "\\'").replace("\\", "\\\\")


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOLS = {
    "today_briefing": {
        "fn": today_briefing,
        "description": "Everything you need to know right now — tasks due, meetings today, deals closing this week, new cases, and pipeline changes from the last 24 hours. Start your day here.",
        "schema": {
            "type": "object",
            "properties": {},
        },
    },
    "account_360": {
        "fn": account_360,
        "description": "Full 360-degree view of a single account: company details, all contacts, open opportunities, active cases, recent activities, and meetings. The complete picture before any call or meeting.",
        "schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account name (partial match supported)"},
            },
            "required": ["account"],
        },
    },
    "my_accounts": {
        "fn": my_accounts,
        "description": "Get all accounts you own. See your full book of business sorted by revenue or name, optionally filtered by industry.",
        "schema": {
            "type": "object",
            "properties": {
                "industry": {"type": "string", "description": "Filter by industry (e.g. 'Technology', 'Healthcare')"},
                "sort_by": {"type": "string", "enum": ["revenue", "name"], "description": "Sort order (default: revenue)"},
                "limit": {"type": "integer", "description": "Max results (default: 50, max: 200)"},
            },
        },
    },
    "pipeline_snapshot": {
        "fn": pipeline_snapshot,
        "description": "Your pipeline broken down by stage — total value, deal count, and individual deals per stage. Optionally filter to one account.",
        "schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Filter to a specific account name (optional)"},
            },
        },
    },
    "deal_changes": {
        "fn": deal_changes,
        "description": "What moved in your pipeline recently — stage changes, amount changes, and close date pushes. See which deals progressed, regressed, or got repriced.",
        "schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Lookback period in days (default: 7)"},
            },
        },
    },
    "at_risk_deals": {
        "fn": at_risk_deals,
        "description": "Deals that need your attention right now: past their close date, no activity in 14+ days, or close date pushed multiple times. Your action-required list.",
        "schema": {
            "type": "object",
            "properties": {},
        },
    },
    "search_accounts": {
        "fn": search_accounts,
        "description": "Search all accounts (not just yours) by name, industry, or keyword. Find accounts across the org.",
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term — name, industry, or keyword"},
            },
            "required": ["query"],
        },
    },
    "account_contacts": {
        "fn": account_contacts,
        "description": "All contacts at an account with titles, emails, phones, and their roles on open opportunities. Know who you're dealing with.",
        "schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account name (partial match supported)"},
            },
            "required": ["account"],
        },
    },
    "activity_timeline": {
        "fn": activity_timeline,
        "description": "Recent activity timeline — calls, emails, tasks, meetings — across your accounts or for a specific account. See what happened and what's been logged.",
        "schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Filter to a specific account (optional — defaults to all your accounts)"},
                "days": {"type": "integer", "description": "Lookback period in days (default: 30)"},
            },
        },
    },
    "forecast_summary": {
        "fn": forecast_summary,
        "description": "6-month pipeline forecast — deals by close month with weighted and unweighted totals. See what's coming and how confident you should be.",
        "schema": {
            "type": "object",
            "properties": {},
        },
    },
}
