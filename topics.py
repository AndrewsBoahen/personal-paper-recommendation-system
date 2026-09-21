"""
topics.py

Fixed research-topic definitions for the paper recommendation system.

Each topic maps to:
  - a human-readable name (shown in the UI)
  - an arXiv search query (arXiv's query syntax: ti:, abs:, cat:, AND/OR/ANDNOT)
  - the arXiv categories to restrict results to
  - a short list of keywords used as a lightweight relevance filter on
    top of whatever arXiv's own search returns (arXiv's search is a fairly
    blunt full-text match, so this keyword pass helps keep results on-topic)

This list is intentionally hard-coded (per the "fixed topic list" design
decision) rather than user-editable at runtime. To add, remove, or tune a
topic, edit RESEARCH_TOPICS directly.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Topic:
    name: str
    arxiv_query: str
    arxiv_categories: tuple[str, ...]
    keywords: tuple[str, ...] = field(default_factory=tuple)


RESEARCH_TOPICS: list[Topic] = [
    Topic(
        name="Gaussian Process & Surrogate Modeling",
        arxiv_query=(
            "(ti:\"Gaussian process\" OR abs:\"Gaussian process\" OR "
            "ti:\"surrogate model\" OR abs:\"surrogate model\")"
        ),
        arxiv_categories=("stat.ML", "stat.ME", "stat.CO"),
        keywords=(
            "gaussian process",
            "surrogate model",
            "emulator",
            "kriging",
            "kernel",
        ),
    ),
    Topic(
        name="Uncertainty Quantification",
        arxiv_query=(
            "(ti:\"uncertainty quantification\" OR abs:\"uncertainty quantification\" "
            "OR ti:\"predictive uncertainty\")"
        ),
        arxiv_categories=("stat.ML", "stat.ME", "stat.CO", "stat.AP"),
        keywords=(
            "uncertainty quantification",
            "predictive uncertainty",
            "calibrated uncertainty",
            "credible interval",
            "confidence interval",
        ),
    ),
    Topic(
        name="Computer Model Calibration",
        arxiv_query=(
            "(ti:\"computer model calibration\" OR abs:\"computer model calibration\" "
            "OR ti:calibration AND abs:\"computer experiment\")"
        ),
        arxiv_categories=("stat.ME", "stat.AP", "stat.CO"),
        keywords=(
            "calibration",
            "computer experiment",
            "model discrepancy",
            "simulator",
            "inverse problem",
        ),
    ),
    Topic(
        name="Bayesian Inference & Computation",
        arxiv_query=(
            "(ti:\"Bayesian inference\" OR abs:\"Bayesian inference\" OR "
            "ti:\"Markov chain Monte Carlo\" OR abs:MCMC)"
        ),
        arxiv_categories=("stat.ME", "stat.CO", "stat.ML"),
        keywords=(
            "bayesian inference",
            "posterior",
            "mcmc",
            "variational inference",
            "markov chain monte carlo",
        ),
    ),
    Topic(
        name="Active Learning & Bayesian Optimization",
        arxiv_query=(
            "(ti:\"active learning\" OR abs:\"active learning\" OR "
            "ti:\"Bayesian optimization\" OR abs:\"Bayesian optimization\")"
        ),
        arxiv_categories=("stat.ML", "cs.LG"),
        keywords=(
            "active learning",
            "bayesian optimization",
            "acquisition function",
            "sequential design",
            "experimental design",
        ),
    ),
]


def get_topic_by_name(name: str) -> Topic | None:
    """Look up a Topic by its display name. Returns None if not found."""
    for topic in RESEARCH_TOPICS:
        if topic.name == name:
            return topic
    return None
