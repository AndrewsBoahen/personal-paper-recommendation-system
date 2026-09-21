# Personal Paper Recommendation System

A Streamlit app that surfaces recent papers relevant to a fixed set of
research areas — Gaussian process modeling, uncertainty quantification,
computer model calibration, Bayesian inference, and active learning —
pulled from [arXiv](https://arxiv.org) and optionally enriched with
citation counts and venue from [Semantic Scholar](https://www.semanticscholar.org).

## How it works

- **Topics are fixed, not free-text.** `topics.py` defines five research
  areas, each with an arXiv search query, category restriction, and a
  short keyword list used as a second relevance pass. Edit that file to
  add, remove, or retune a topic — the app itself doesn't expose a
  free-text search box by design.
- **arXiv** (`sources/arxiv_client.py`) is the primary source: no API key
  needed, and it's queried per-topic with a short delay between requests
  (arXiv asks API users to avoid hammering it).
- **Semantic Scholar** (`sources/semantic_scholar_client.py`) is an
  optional enrichment step: for each paper, it searches Semantic Scholar
  by title and attaches citation count, venue, and a Semantic Scholar
  link if a match is found. This is slower (~1 request/paper) and
  subject to Semantic Scholar's rate limit, so it can be toggled off in
  the sidebar for a faster, arXiv-only view.
- Results are cached for an hour (`st.cache_data(ttl=3600)`) so
  navigating the sidebar doesn't re-hit the APIs on every rerun.

## Project structure

```
paper-recommender/
├── app.py                              # Streamlit UI and orchestration
├── topics.py                           # Fixed research-topic definitions
├── sources/
│   ├── arxiv_client.py                 # arXiv API + XML parsing
│   └── semantic_scholar_client.py      # Semantic Scholar enrichment
├── requirements.txt
└── README.md
```

## Papers view: This Year / Previous Years

Papers from your selected topics are merged into one deduplicated list
(a paper matching more than one topic shows up once, tagged with all the
topics it matched) and split into two sections by publication year:
**This Year** and **Previous Years**. Sort order (most recent / most
cited) applies within each section independently.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy

Push this to its own GitHub repo, then deploy on
[Streamlit Community Cloud](https://streamlit.io/cloud) — same setup as
the [conformal prediction app](https://andrewsboahenmyconformalprediction.streamlit.app/)
and GPReg's Streamlit interface. Once it's live, add the URL to
`demo` in `_portfolio/paper-recommendation-system.md` on the main site
so the project card links to it.

### Optional: Semantic Scholar API key

The unauthenticated Semantic Scholar API is rate-limited (roughly 100
requests per 5 minutes at the time of writing), which is enough for
casual use but can get slow with several topics × many papers ×
enrichment all enabled. To raise the limit:

1. Request a free key at the
   [Semantic Scholar API page](https://www.semanticscholar.org/product/api).
2. On Streamlit Community Cloud, add it under **App settings → Secrets**:
   ```toml
   SEMANTIC_SCHOLAR_API_KEY = "your-key-here"
   ```
3. Locally, create `.streamlit/secrets.toml` with the same line (this
   file is gitignored — see below).

The app reads the key automatically if present; otherwise the sidebar
lets you paste one in for that session, and falls back to the shared
unauthenticated limit if left blank.

## Customizing the topic list

Edit `RESEARCH_TOPICS` in `topics.py`. Each `Topic` needs:

- `name` — shown in the UI as a section header
- `arxiv_query` — arXiv search syntax (`ti:`, `abs:`, `AND`/`OR`)
- `arxiv_categories` — arXiv category codes to restrict to (e.g. `stat.ML`)
- `keywords` — a short tuple used as a lightweight relevance filter on
  top of arXiv's own (fairly blunt) search matching

## Known limitations

- A paper relevant to two topics (e.g. both "Gaussian Process" and
  "Uncertainty Quantification") will appear once under each topic's
  section rather than being deduplicated — this is intentional for now,
  since which section it's filed under is itself informative, but could
  be changed in `app.py`'s rendering loop if a single deduplicated feed
  is preferred later.
- Semantic Scholar matching is by title string, so a paper whose arXiv
  and Semantic Scholar titles differ (e.g. after a revision) may not get
  enriched — it just falls back to the arXiv-only fields in that case.
