"""Tiny dependency-free BM25 over markdown sections.

Cloud Ollama has no embedding models, and BM25 is deterministic and needs no service.
"""
import math
import re
from collections import Counter
from pathlib import Path

# Access control by location: customer-facing retrieval only ever indexes `corpus/`.
# `corpus_internal/` (agent-only data such as the ticket export) is never loaded here.
CORPUS_DIR = Path(__file__).parent / "corpus"
INTERNAL_DIR = Path(__file__).parent / "corpus_internal"


_STOP = {"the", "a", "an", "is", "are", "do", "does", "how", "what", "my", "i", "to", "of",
         "and", "or", "you", "your", "can", "it", "in", "for", "on", "me", "we", "have", "if"}


def _stem(t: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if t.endswith(suf) and len(t) - len(suf) >= 4:
            return t[: -len(suf)]
    return t


def _tokens(text: str) -> list[str]:
    return [_stem(t) for t in re.findall(r"[a-z0-9$]+", text.lower()) if t not in _STOP]


def load_chunks(corpus_dir: Path = CORPUS_DIR) -> list[str]:
    """One chunk per '## ' section, prefixed with its document title."""
    chunks = []
    for path in sorted(corpus_dir.glob("*.md")):
        title, *sections = re.split(r"(?m)^## ", path.read_text())
        title = title.strip()
        for sec in sections:
            chunks.append(f"{title}\n## {sec.strip()}")
    return chunks


class BM25:
    def __init__(self, chunks: list[str], k1: float = 1.5, b: float = 0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.docs = [Counter(_tokens(c)) for c in chunks]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lens) / len(chunks)
        df = Counter(t for d in self.docs for t in d)
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 3) -> list[str]:
        q = _tokens(query)
        scored = []
        for i, d in enumerate(self.docs):
            s = 0.0
            for t in q:
                if t in d:
                    tf = d[t]
                    s += self.idf[t] * tf * (self.k1 + 1) / (
                        tf + self.k1 * (1 - self.b + self.b * self.lens[i] / self.avg)
                    )
            scored.append((s, i))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [self.chunks[i] for s, i in scored[:k] if s > 0]
