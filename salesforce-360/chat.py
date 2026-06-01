"""
Chat endpoint — bridges the web UI to Claude API with Salesforce tools.

Receives a user message, sends it to Claude with the 10 SF tools,
executes any tool calls against Salesforce, and returns the response.
"""

import json
import logging
import os
from typing import Any

import anthropic

from .tools import TOOLS

logger = logging.getLogger("sf-360-chat")

_client = None
MODEL = "claude-sonnet-4-6"
MAX_TURNS = 10


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set. Add it to your environment variables.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _build_tool_definitions() -> list[dict]:
    tools = []
    for name, meta in TOOLS.items():
        tools.append({
            "name": name,
            "description": meta["description"],
            "input_schema": meta["schema"],
        })
    return tools


SYSTEM_PROMPT = """You are a Salesforce assistant for a sales rep. You have access to their Salesforce org through 10 tools.

Your job is to answer their questions about their accounts, pipeline, deals, contacts, and daily priorities using the tools available. Be concise and actionable — this is a busy salesperson who wants answers, not essays.

When they ask a broad question like "what do I need to know today?", use today_briefing. When they ask about a specific account, use account_360. Chain tools together when needed — for example, if they ask about at-risk deals at a specific account, use at_risk_deals first, then account_360 for context.

Format responses for easy scanning:
- Use bullet points for lists
- Bold important numbers (deal amounts, dates, names)
- Lead with the most important information
- End with a suggested next action when appropriate

If a tool returns no results, say so directly — don't speculate about data that isn't there."""


async def handle_chat(messages: list[dict], conversation_history: list[dict] | None = None) -> dict:
    """Process a chat message through Claude with Salesforce tools.

    Returns {"response": str, "history": list} where history is the full
    conversation for maintaining state across turns.
    """
    client = _get_client()
    tools = _build_tool_definitions()

    if conversation_history:
        api_messages = conversation_history + messages
    else:
        api_messages = messages

    for _ in range(MAX_TURNS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=api_messages,
        )

        if response.stop_reason == "tool_use":
            api_messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    logger.info(f"Calling tool: {tool_name}({json.dumps(tool_input)[:200]})")

                    if tool_name in TOOLS:
                        try:
                            result = await TOOLS[tool_name]["fn"](**tool_input)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result, default=str),
                            })
                        except Exception as e:
                            logger.exception(f"Tool error: {tool_name}")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps({"error": str(e)}),
                                "is_error": True,
                            })
                    else:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps({"error": f"Unknown tool: {tool_name}"}),
                            "is_error": True,
                        })

            api_messages.append({"role": "user", "content": tool_results})
            continue

        text_parts = [b.text for b in response.content if hasattr(b, "text")]
        final_text = "\n".join(text_parts)

        api_messages.append({"role": "assistant", "content": response.content})

        return {
            "response": final_text,
            "history": api_messages,
        }

    return {
        "response": "I hit the maximum number of tool calls. Try a more specific question.",
        "history": api_messages,
    }
