"""
sources/semantic_scholar_client.py

Enriches Paper objects (already fetched from arXiv) with data from the
Semantic Scholar Graph API: citation count, venue, and a Semantic Scholar
URL. Matching is done by title search since arXiv and Semantic Scholar
don't share a common ID for every paper.

The unauthenticated Semantic Scholar API is rate-limited (roughly 100
requests per 5 minutes at the time of writing). An optional API key
raises that limit substantially — see README.md for how to supply one.
"""

from __future__ import annotations

import time

import requests

from sources.arxiv_client import Paper

SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,citationCount,venue,url"


def _normalize(title: str) -> str:
    return " ".join(title.lower().split())


def _best_match(candidates: list[dict], target_title: str) -> dict | None:
    """Pick the candidate whose title matches most closely (exact match preferred)."""
    target = _normalize(target_title)
    for candidate in candidates:
        if _normalize(candidate.get("title", "")) == target:
            return candidate
    # Fall back to the top result if nothing matches exactly — Semantic
    # Scholar's own relevance ranking is usually reasonable for this.
    return candidates[0] if candidates else None


def enrich_paper(paper: Paper, api_key: str | None = None, timeout: float = 10.0) -> None:
    """
    Look up a single paper on Semantic Scholar and fill in citation_count,
    venue, and semantic_scholar_url on it in place. Silently leaves those
    fields as None if no match is found or the request fails — enrichment
    is a nice-to-have, not a hard requirement for the app to function.
    """
    headers = {"x-api-key": api_key} if api_key else {}
    params = {"query": paper.title, "fields": FIELDS, "limit": 3}

    try:
        response = requests.get(
            SEARCH_URL, params=params, headers=headers, timeout=timeout
        )
        if response.status_code == 429:
            return  # rate-limited; skip enrichment for this paper rather than retry
        response.raise_for_status()
        data = response.json().get("data", [])
    except requests.RequestException:
        return

    match = _best_match(data, paper.title)
    if not match:
        return

    paper.citation_count = match.get("citationCount")
    paper.venue = match.get("venue") or None
    paper.semantic_scholar_url = match.get("url")


def enrich_papers(
    papers: list[Paper],
    api_key: str | None = None,
    request_delay_seconds: float = 1.1,
) -> None:
    """
    Enrich a list of papers in place, pausing briefly between requests to
    stay well under the unauthenticated rate limit. For a large result
    set this can take a while (~1 second per paper) — call it on a
    capped/paginated subset rather than every result at once.
    """
    for i, paper in enumerate(papers):
        if i > 0:
            time.sleep(request_delay_seconds)
        enrich_paper(paper, api_key=api_key)
