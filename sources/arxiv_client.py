"""
sources/arxiv_client.py

Minimal client for the arXiv API (https://export.arxiv.org/api).

No API key is required. The API returns an Atom XML feed; we parse it with
the standard-library xml.etree.ElementTree rather than pulling in an extra
dependency like feedparser.
"""

from __future__ import annotations

import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

from topics import Topic

ARXIV_API_URL = "http://export.arxiv.org/api/query"

# Atom / arXiv XML namespaces used when parsing the response.
_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


@dataclass
class Paper:
    """A single paper, normalized across arXiv and (optionally) Semantic Scholar."""

    title: str
    authors: list[str]
    abstract: str
    published: datetime
    arxiv_id: str
    arxiv_url: str
    categories: list[str] = field(default_factory=list)
    topic: str = ""
    # Filled in later by the Semantic Scholar enrichment step, if a match is found.
    citation_count: int | None = None
    semantic_scholar_url: str | None = None
    venue: str | None = None


def _build_search_query(topic: Topic) -> str:
    """Combine a topic's free-text query with its arXiv category restriction."""
    category_clause = " OR ".join(f"cat:{cat}" for cat in topic.arxiv_categories)
    return f"{topic.arxiv_query} AND ({category_clause})"


def _parse_entry(entry: ET.Element, topic_name: str) -> Paper:
    def text(tag: str) -> str:
        el = entry.find(f"atom:{tag}", _NAMESPACES)
        return el.text.strip() if el is not None and el.text else ""

    title = " ".join(text("title").split())  # collapse internal newlines/whitespace
    abstract = " ".join(text("summary").split())

    authors = [
        (author.find("atom:name", _NAMESPACES).text or "").strip()
        for author in entry.findall("atom:author", _NAMESPACES)
    ]

    published_raw = text("published")
    published = (
        datetime.strptime(published_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if published_raw
        else datetime.now(timezone.utc)
    )

    arxiv_url = text("id")
    arxiv_id = arxiv_url.rsplit("/abs/", 1)[-1] if "/abs/" in arxiv_url else arxiv_url

    categories = [
        cat.attrib.get("term", "")
        for cat in entry.findall("atom:category", _NAMESPACES)
        if cat.attrib.get("term")
    ]

    return Paper(
        title=title,
        authors=authors,
        abstract=abstract,
        published=published,
        arxiv_id=arxiv_id,
        arxiv_url=arxiv_url,
        categories=categories,
        topic=topic_name,
    )


def _keyword_matches(paper: Paper, keywords: tuple[str, ...]) -> bool:
    """Lightweight relevance filter: does the title or abstract mention any keyword?"""
    if not keywords:
        return True
    haystack = f"{paper.title} {paper.abstract}".lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def fetch_papers_for_topic(
    topic: Topic,
    max_results: int = 15,
    sort_by: str = "submittedDate",
    sort_order: str = "descending",
    timeout: float = 10.0,
) -> list[Paper]:
    """
    Fetch and parse papers from arXiv for a single Topic.

    Raises requests.RequestException on network failure; callers should
    catch this so one failing topic doesn't take down the whole page.
    """
    params = {
        "search_query": _build_search_query(topic),
        "start": 0,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    root = ET.fromstring(response.text)
    entries = root.findall("atom:entry", _NAMESPACES)

    papers = [_parse_entry(entry, topic.name) for entry in entries]
    return [p for p in papers if _keyword_matches(p, topic.keywords)]


def fetch_papers_for_topics(
    topics: list[Topic],
    max_results_per_topic: int = 15,
    request_delay_seconds: float = 3.0,
) -> dict[str, list[Paper]]:
    """
    Fetch papers for multiple topics, one arXiv request per topic.

    arXiv asks API users to wait a few seconds between requests, so this
    sleeps between calls rather than firing them concurrently.
    """
    results: dict[str, list[Paper]] = {}
    for i, topic in enumerate(topics):
        if i > 0:
            time.sleep(request_delay_seconds)
        try:
            results[topic.name] = fetch_papers_for_topic(
                topic, max_results=max_results_per_topic
            )
        except requests.RequestException:
            results[topic.name] = []
    return results
