from __future__ import annotations

import re
from unicodedata import normalize

STOPWORDS = {
    "a",
    "an",
    "and",
    "the",
    "to",
    "for",
    "of",
    "in",
    "on",
    "vs",
    "how",
    "what",
    "is",
    "are",
    "with",
    "from",
    "into",
    "your",
    "my",
    "docs",
    "doc",
}


def slugify(value: str) -> str:
    value = normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "page"


def tokenize(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", value.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def first_paragraph(markdown: str) -> str:
    for block in re.split(r"\n\s*\n", markdown):
        line = block.strip()
        if not line or line.startswith("#") or line.startswith("```") or line.startswith("<"):
            continue
        line = re.sub(r"[*_`>#\\[-]", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            return line[:240]
    return ""


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def overlap_score(query: str, *fields: str) -> float:
    q = tokenize(query)
    if not q:
        return 0.0
    hay = tokenize(" ".join(fields))
    score = jaccard(q, hay)
    joined = " ".join(fields).lower()
    if query.lower() in joined:
        score = max(score, 0.92)
    else:
        hits = sum(1 for token in q if token in hay)
        score = max(score, hits / max(len(q), 1) * 0.7)
    return round(score, 3)
