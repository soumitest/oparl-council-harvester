"""Domain filter: data-centre and substation signals.

German compounds ("Rechenzentrumsstandort", "Umspannwerkserweiterung") are why
we match on substrings of the lower-cased text instead of whole words.
"""
from __future__ import annotations

# Order does not matter; results are returned sorted and de-duplicated.
KEYWORDS: tuple[str, ...] = (
    # data centres
    "rechenzentrum",
    "rechenzentren",
    "data center",
    "data centre",
    "datacenter",
    "datacentre",
    "datenzentrum",
    "serverfarm",
    "server farm",
    # substations / grid
    "umspannwerk",
    "umspannanlage",
    "umspannstation",
    "trafostation",
    "transformatorenstation",
    "transformatorstation",
    "schaltanlage",
    "hochspannung",
    "höchstspannung",
    "110-kv",
    "110 kv",
    "380-kv",
    "380 kv",
)


# Known false positives: the municipal IT provider "ekom21 - Kommunales Gebietsrechenzentrum
# Hessen" appears in many council papers (elections of delegates, fees...) and is not a
# data-centre project. These phrases are removed before matching.
EXCLUDE_PHRASES: tuple[str, ...] = (
    "kommunales gebietsrechenzentrum",
    "gebietsrechenzentrum",
)


def match_keywords(*texts: str | None, keywords: tuple[str, ...] = KEYWORDS) -> list[str]:
    haystack = " ".join(t for t in texts if t).lower()
    for phrase in EXCLUDE_PHRASES:
        haystack = haystack.replace(phrase, " ")
    return sorted({k for k in keywords if k in haystack})
