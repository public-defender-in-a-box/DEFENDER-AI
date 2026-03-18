"""Claude API wrapper — all LLM calls go through here."""

import json
from typing import Any

import anthropic

from src.config import settings


client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


async def call_llm(
    prompt: str,
    system: str = (
        "You are a legal analysis AI assistant for a public defender's office."
        " Always return valid JSON."
    ),
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Call Claude and parse the JSON response.

    All agent LLM calls go through this function for centralized
    logging, error handling, and token tracking.
    """
    response = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text

    # Extract JSON from response (handle markdown code blocks)
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    return json.loads(text.strip())
