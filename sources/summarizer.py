"""
sources/summarizer.py

Generates a short "main idea" summary of a paper's abstract using the
Anthropic API. This is deliberately on-demand (triggered per paper by a
button in the UI), not run automatically for every fetched paper — the
abstract is already shown in full, and summarizing everything up front
would burn API credits on papers the user never actually opens.
"""

from __future__ import annotations

import requests

from sources.arxiv_client import Paper

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"  # fast/cheap: fine for a 1-2 sentence summary

_SYSTEM_PROMPT = (
    "You summarize academic paper abstracts for a researcher scanning many "
    "papers quickly. Given a title and abstract, respond with ONLY a 1-2 "
    "sentence plain-language summary of the paper's main idea and "
    "contribution. No preamble, no restating the title verbatim, no markdown."
)


class SummarizerError(Exception):
    """Raised when the Anthropic API call fails or returns no usable text."""


def summarize_abstract(
    paper: Paper,
    api_key: str,
    model: str = DEFAULT_MODEL,
    timeout: float = 20.0,
) -> str:
    """
    Call the Anthropic API to produce a short main-idea summary of a
    paper's abstract. Raises SummarizerError on any failure (missing
    abstract, network error, empty response) so the caller can show a
    friendly message instead of a raw traceback.
    """
    if not paper.abstract:
        raise SummarizerError("This paper has no abstract to summarize.")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 150,
        "system": _SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": f"Title: {paper.title}\n\nAbstract: {paper.abstract}",
            }
        ],
    }

    try:
        response = requests.post(
            ANTHROPIC_API_URL, headers=headers, json=payload, timeout=timeout
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise SummarizerError(f"Request to the summarizer failed: {exc}") from exc

    blocks = data.get("content", [])
    text = " ".join(
        block.get("text", "") for block in blocks if block.get("type") == "text"
    ).strip()
    if not text:
        raise SummarizerError("The summarizer returned no text.")
    return text
