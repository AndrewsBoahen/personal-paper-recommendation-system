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

import streamlit as st

from sources.arxiv_client import Paper, fetch_papers_for_topics
from sources.semantic_scholar_client import enrich_papers
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


def _sort_papers(papers: list[Paper], sort_mode: str) -> list[Paper]:
    if sort_mode == "Most cited":
        return sorted(papers, key=lambda p: (p.citation_count or 0), reverse=True)
    return sorted(papers, key=lambda p: p.published, reverse=True)  # "Most recent"


def _render_paper(paper: Paper) -> None:
    authors = ", ".join(paper.authors[:6])
    if len(paper.authors) > 6:
        authors += ", et al."

    st.markdown(f"#### [{paper.title}]({paper.arxiv_url})")

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
