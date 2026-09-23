"""Ingestion: turning outside information into simulator inputs."""

from .news import (
    ELO_DELTA_TABLE,
    Classification,
    Classifier,
    Extraction,
    KeywordClassifier,
    NewsItem,
    ReviewPolicy,
    TypeSafeClassifier,
    elo_delta,
    extract,
    to_roster_event,
)

__all__ = [
    "ELO_DELTA_TABLE", "Classification", "Classifier", "Extraction",
    "KeywordClassifier", "NewsItem", "ReviewPolicy", "TypeSafeClassifier",
    "elo_delta", "extract", "to_roster_event",
]
