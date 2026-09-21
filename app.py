"""
app.py

Personal Paper Recommendation System — a Streamlit app that surfaces
recent papers relevant to a fixed list of research topics (see topics.py),
pulling metadata from arXiv and, optionally, citation counts from
Semantic Scholar.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

Deploy: push this repo to GitHub and deploy on Streamlit Community Cloud
(streamlit.io/cloud), same as the conformal prediction and GPReg apps.
See README.md for details, including how to add a Semantic Scholar API
key for a higher rate limit.
"""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from sources.arxiv_client import Paper, fetch_papers_for_topics
from sources.semantic_scholar_client import enrich_papers
from sources.summarizer import SummarizerError, summarize_abstract
from topics import RESEARCH_TOPICS, Topic

st.set_page_config(page_title="Paper Recommendations", page_icon="📄", layout="wide")


@st.cache_data(ttl=3600, show_spinner=False)
def _get_recommendations(
    topic_names: tuple[str, ...],
    max_results_per_topic: int,
    enrich: bool,
    api_key: str | None,
) -> dict[str, list[Paper]]:
    """
    Cached fetch-and-enrich pipeline. Cached on its arguments, so changing
    any sidebar control triggers a fresh fetch; leaving everything the
    same re-uses the cached result for an hour instead of hitting the
    APIs again on every Streamlit rerun.
    """
    selected_topics = [t for t in RESEARCH_TOPICS if t.name in topic_names]
    results = fetch_papers_for_topics(
        selected_topics, max_results_per_topic=max_results_per_topic
    )
    if enrich:
        for papers in results.values():
            enrich_papers(papers, api_key=api_key)
    return results


def _merge_and_dedupe(results: dict[str, list[Paper]]) -> list[Paper]:
    """
    Flatten the per-topic results into one list, deduplicated by arXiv id.
    A paper that matched more than one topic keeps all of those topic
    names (comma-joined) in its `topic` field, so nothing is lost by
    merging — it just shows up once instead of once per matching topic.
    """
    merged: dict[str, Paper] = {}
    matched_topics: dict[str, set[str]] = {}

    for topic_name, papers in results.items():
        for paper in papers:
            key = paper.arxiv_id
            if key not in merged:
                merged[key] = paper
                matched_topics[key] = set()
            matched_topics[key].add(topic_name)

    for key, paper in merged.items():
        paper.topic = ", ".join(sorted(matched_topics[key]))

    return list(merged.values())


def _split_by_year(papers: list[Paper]) -> tuple[list[Paper], list[Paper]]:
    """Split into (this year's papers, everything from previous years)."""
    current_year = datetime.now(timezone.utc).year
    this_year = [p for p in papers if p.published.year == current_year]
    previous_years = [p for p in papers if p.published.year != current_year]
    return this_year, previous_years


def _sort_papers(papers: list[Paper], sort_mode: str) -> list[Paper]:
    if sort_mode == "Most cited":
        return sorted(papers, key=lambda p: (p.citation_count or 0), reverse=True)
    return sorted(papers, key=lambda p: p.published, reverse=True)  # "Most recent"


@st.cache_data(ttl=86400, show_spinner=False)
def _cached_summary(arxiv_id: str, title: str, abstract: str, api_key: str) -> str:
    """
    Thin cache wrapper around summarize_abstract, keyed by the paper's own
    content rather than the Paper object (which isn't hashable the way
    st.cache_data needs). Cached for a day since an abstract's summary
    never changes — no reason to pay for the same summary twice.
    """
    fake_paper = Paper(
        title=title,
        authors=[],
        abstract=abstract,
        published=datetime.now(timezone.utc),
        arxiv_id=arxiv_id,
        arxiv_url="",
    )
    return summarize_abstract(fake_paper, api_key=api_key)


def _render_paper(paper: Paper, anthropic_api_key: str | None) -> None:
    authors = ", ".join(paper.authors[:6])
    if len(paper.authors) > 6:
        authors += ", et al."

    st.markdown(f"#### [{paper.title}]({paper.arxiv_url})")

    meta_bits = [authors, paper.published.strftime("%b %d, %Y")]
    if paper.topic:
        meta_bits.append(paper.topic)
    st.caption(" · ".join(meta_bits))

    badge_bits = []
    if paper.citation_count is not None:
        badge_bits.append(f"**{paper.citation_count}** citations")
    if paper.venue:
        badge_bits.append(paper.venue)
    if badge_bits:
        st.caption(" · ".join(badge_bits))

    with st.expander("Abstract"):
        st.write(paper.abstract)

    summary_key = f"summary_{paper.arxiv_id}"
    button_col, _ = st.columns([1, 4])
    with button_col:
        summarize_clicked = st.button(
            "🔎 Quick summary", key=f"summarize_button_{paper.arxiv_id}"
        )

    if summarize_clicked:
        if not anthropic_api_key:
            st.warning(
                "Add an Anthropic API key in the sidebar to enable quick summaries."
            )
        else:
            with st.spinner("Summarizing..."):
                try:
                    st.session_state[summary_key] = _cached_summary(
                        paper.arxiv_id, paper.title, paper.abstract, anthropic_api_key
                    )
                except SummarizerError as exc:
                    st.session_state[summary_key] = None
                    st.error(f"Couldn't summarize this paper: {exc}")

    if st.session_state.get(summary_key):
        st.info(st.session_state[summary_key])

    links = [f"[arXiv]({paper.arxiv_url})"]
    if paper.semantic_scholar_url:
        links.append(f"[Semantic Scholar]({paper.semantic_scholar_url})")
    st.markdown(" &nbsp;|&nbsp; ".join(links))

    st.divider()


def main() -> None:
    st.title("📄 Personal Paper Recommendation System")
    st.write(
        "Recent papers from arXiv across a fixed set of research areas — "
        "Gaussian process modeling, uncertainty quantification, computer "
        "model calibration, Bayesian inference, and active learning — "
        "optionally enriched with Semantic Scholar citation counts."
    )

    with st.sidebar:
        st.header("Settings")

        topic_names = st.multiselect(
            "Research topics",
            options=[t.name for t in RESEARCH_TOPICS],
            default=[t.name for t in RESEARCH_TOPICS],
        )

        max_results_per_topic = st.slider(
            "Papers per topic", min_value=3, max_value=20, value=8
        )

        sort_mode = st.radio("Sort by", options=["Most recent", "Most cited"], index=0)

        enrich = st.checkbox(
            "Fetch citation counts from Semantic Scholar",
            value=True,
            help=(
                "Adds a Semantic Scholar lookup per paper. Slower (roughly "
                "1 second per paper) and subject to Semantic Scholar's rate "
                "limit — turn this off for a faster, arXiv-only view."
            ),
        )

        s2_api_key = None
        if enrich:
            secret_key = st.secrets.get("SEMANTIC_SCHOLAR_API_KEY", None)
            s2_api_key = secret_key or st.text_input(
                "Semantic Scholar API key (optional)",
                type="password",
                help="Raises the rate limit. Leave blank to use the shared unauthenticated limit.",
            )

        st.divider()
        st.caption(
            "Optional: enables the '🔎 Quick summary' button on each paper "
            "(calls the Anthropic API — costs a small amount of API credit "
            "per summary, only when you click it)."
        )
        anthropic_secret = st.secrets.get("ANTHROPIC_API_KEY", None)
        anthropic_api_key = anthropic_secret or st.text_input(
            "Anthropic API key (optional)", type="password"
        )

        fetch_clicked = st.button("Get recommendations", type="primary")

    if not topic_names:
        st.info("Select at least one research topic in the sidebar to get started.")
        return

    if not fetch_clicked and "results" not in st.session_state:
        st.info("Choose your settings in the sidebar, then click **Get recommendations**.")
        return

    if fetch_clicked:
        with st.spinner("Fetching papers..."):
            st.session_state["results"] = _get_recommendations(
                tuple(topic_names), max_results_per_topic, enrich, s2_api_key or None
            )

    results = st.session_state.get("results", {})
    all_papers = _merge_and_dedupe(results)
    this_year, previous_years = _split_by_year(all_papers)

    for label, papers in [("This Year", this_year), ("Previous Years", previous_years)]:
        st.header(label)
        if not papers:
            st.write("No papers found in this group for the current settings.")
            continue
        for paper in _sort_papers(papers, sort_mode):
            _render_paper(paper, anthropic_api_key or None)


if __name__ == "__main__":
    main()
    meta_bits = [authors, paper.published.strftime("%b %d, %Y")]
    if paper.categories:
        meta_bits.append(", ".join(paper.categories[:3]))
    st.caption(" · ".join(meta_bits))

    badge_bits = []
    if paper.citation_count is not None:
        badge_bits.append(f"**{paper.citation_count}** citations")
    if paper.venue:
        badge_bits.append(paper.venue)
    if badge_bits:
        st.caption(" · ".join(badge_bits))

    with st.expander("Abstract"):
        st.write(paper.abstract)

    links = [f"[arXiv]({paper.arxiv_url})"]
    if paper.semantic_scholar_url:
        links.append(f"[Semantic Scholar]({paper.semantic_scholar_url})")
    st.markdown(" &nbsp;|&nbsp; ".join(links))

    st.divider()


def main() -> None:
    st.title("📄 Personal Paper Recommendation System")
    st.write(
        "Recent papers from arXiv across a fixed set of research areas — "
        "Gaussian process modeling, uncertainty quantification, computer "
        "model calibration, Bayesian inference, and active learning — "
        "optionally enriched with Semantic Scholar citation counts."
    )

    with st.sidebar:
        st.header("Settings")

        topic_names = st.multiselect(
            "Research topics",
            options=[t.name for t in RESEARCH_TOPICS],
            default=[t.name for t in RESEARCH_TOPICS],
        )

        max_results_per_topic = st.slider(
            "Papers per topic", min_value=3, max_value=20, value=8
        )

        sort_mode = st.radio("Sort by", options=["Most recent", "Most cited"], index=0)

        enrich = st.checkbox(
            "Fetch citation counts from Semantic Scholar",
            value=True,
            help=(
                "Adds a Semantic Scholar lookup per paper. Slower (roughly "
                "1 second per paper) and subject to Semantic Scholar's rate "
                "limit — turn this off for a faster, arXiv-only view."
            ),
        )

        api_key = None
        if enrich:
            secret_key = st.secrets.get("SEMANTIC_SCHOLAR_API_KEY", None)
            api_key = secret_key or st.text_input(
                "Semantic Scholar API key (optional)",
                type="password",
                help="Raises the rate limit. Leave blank to use the shared unauthenticated limit.",
            )

        fetch_clicked = st.button("Get recommendations", type="primary")

    if not topic_names:
        st.info("Select at least one research topic in the sidebar to get started.")
        return

    if not fetch_clicked and "results" not in st.session_state:
        st.info("Choose your settings in the sidebar, then click **Get recommendations**.")
        return

    if fetch_clicked:
        with st.spinner("Fetching papers..."):
            st.session_state["results"] = _get_recommendations(
                tuple(topic_names), max_results_per_topic, enrich, api_key or None
            )

    results = st.session_state.get("results", {})

    for topic_name in topic_names:
        papers = results.get(topic_name, [])
        st.header(topic_name)
        if not papers:
            st.write("No papers found for this topic in the current window.")
            continue
        for paper in _sort_papers(papers, sort_mode):
            _render_paper(paper)


if __name__ == "__main__":
    main()
