"""Recursive chunking for SOP documents.

Strategy: split on Markdown headings first, then paragraphs, then sentences -
descending only as far as necessary to fit the budget. Target 512 tokens with
64 tokens of overlap (12.5%).

Why recursive and not the alternatives
--------------------------------------
- **Fixed-size** splits mid-table and mid-sentence. These documents are mostly
  threshold tables; a chunk containing "| 90% - 94% | CRITICAL |" with the
  header row severed is worse than useless, because it retrieves confidently and
  answers wrongly.
- **Sentence** chunking produces fragments too small to carry context. "The SOC
  Controller authorises." retrieves well and means nothing without the row it
  came from.
- **Semantic** chunking (embedding-similarity boundaries) is the sophisticated
  option, but these documents already carry explicit human-authored structure in
  their headings. Inferring boundaries statistically when the author wrote them
  down is spending compute to approximate information already present.
- **Recursive** follows that authored structure and only falls back to finer
  splits when a section genuinely exceeds the budget. Each chunk lands on a
  section boundary, so it arrives with its heading attached.

Every chunk carries its `section_heading` in the embedded text as well as in
metadata. A table row is meaningless without knowing which procedure and which
section it belongs to, and the embedding should see that context too.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import tiktoken

from config.settings import REPO_ROOT

TARGET_TOKENS = 512
OVERLAP_TOKENS = 64

_ENCODER = tiktoken.get_encoding("cl100k_base")

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
_SENTENCE_RE = re.compile(r"(?<=[.!?؟])\s+")


def count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


@dataclass
class Chunk:
    text: str
    doc_code: str
    doc_title: str
    section_heading: str
    chunk_index: int
    source_path: str
    token_count: int = 0
    chunk_id: str = field(default="")

    def __post_init__(self) -> None:
        if not self.token_count:
            self.token_count = count_tokens(self.text)
        if not self.chunk_id:
            self.chunk_id = f"{self.doc_code}::{self.chunk_index}"

    def to_payload(self) -> dict:
        return asdict(self)


def parse_front_matter(raw: str) -> tuple[dict, str]:
    match = _FRONT_MATTER_RE.match(raw)
    if not match:
        return {}, raw
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, raw[match.end():]


def split_into_sections(body: str) -> list[tuple[str, str]]:
    """Return [(heading, section_text)] following the document's own headings."""
    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        return [("", body.strip())]

    sections: list[tuple[str, str]] = []
    preamble = body[: matches[0].start()].strip()
    if preamble:
        sections.append(("", preamble))

    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[match.end():end].strip()
        if text:
            sections.append((heading, text))
    return sections


def _pack(units: list[str], target: int, overlap: int) -> list[str]:
    """Greedily pack units into <=target-token groups with a token overlap tail."""
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for unit in units:
        unit_tokens = count_tokens(unit)
        if current and current_tokens + unit_tokens > target:
            chunks.append("\n\n".join(current))
            # Carry a tail of the previous chunk forward so a fact split across
            # a boundary is retrievable from either side.
            tail: list[str] = []
            tail_tokens = 0
            for prev in reversed(current):
                prev_tokens = count_tokens(prev)
                if tail_tokens + prev_tokens > overlap:
                    break
                tail.insert(0, prev)
                tail_tokens += prev_tokens
            current = [*tail, unit]
            current_tokens = tail_tokens + unit_tokens
        else:
            current.append(unit)
            current_tokens += unit_tokens

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def chunk_section(heading: str, text: str) -> list[str]:
    """Split one section, descending only as far as the budget requires."""
    if count_tokens(text) <= TARGET_TOKENS:
        return [text]

    # Level 2: paragraphs. Table rows are kept with their neighbours because a
    # Markdown table is a single paragraph block.
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    oversized = [p for p in paragraphs if count_tokens(p) > TARGET_TOKENS]
    if not oversized:
        return _pack(paragraphs, TARGET_TOKENS, OVERLAP_TOKENS)

    # Level 3: sentences, but only inside the paragraphs that need it.
    units: list[str] = []
    for paragraph in paragraphs:
        if count_tokens(paragraph) <= TARGET_TOKENS:
            units.append(paragraph)
        else:
            units.extend(s.strip() for s in _SENTENCE_RE.split(paragraph) if s.strip())
    return _pack(units, TARGET_TOKENS, OVERLAP_TOKENS)


def chunk_document(path: Path) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)
    doc_code = meta.get("doc_code", path.stem.upper())
    doc_title = meta.get("doc_title", path.stem.replace("_", " ").title())

    chunks: list[Chunk] = []
    index = 0
    for heading, section_text in split_into_sections(body):
        for piece in chunk_section(heading, section_text):
            # The heading travels INSIDE the embedded text, not only in
            # metadata: a bare table row does not encode which procedure it
            # belongs to, and the embedding must see that.
            text = f"[{doc_code}] {doc_title}\n## {heading}\n\n{piece}" if heading \
                else f"[{doc_code}] {doc_title}\n\n{piece}"
            chunks.append(Chunk(
                text=text,
                doc_code=doc_code,
                doc_title=doc_title,
                section_heading=heading,
                chunk_index=index,
                source_path=str(path.relative_to(REPO_ROOT)),
            ))
            index += 1
    return chunks


def chunk_corpus(sop_dir: Path | None = None) -> list[Chunk]:
    sop_dir = sop_dir or (REPO_ROOT / "data" / "sop")
    chunks: list[Chunk] = []
    for path in sorted(sop_dir.glob("*.md")):
        chunks.extend(chunk_document(path))
    return chunks


if __name__ == "__main__":
    all_chunks = chunk_corpus()
    tokens = [c.token_count for c in all_chunks]
    print(f"documents: {len({c.doc_code for c in all_chunks})}")
    print(f"chunks   : {len(all_chunks)}")
    print(f"tokens   : min={min(tokens)} max={max(tokens)} "
          f"mean={sum(tokens) / len(tokens):.0f} target={TARGET_TOKENS}")
    print()
    for code in sorted({c.doc_code for c in all_chunks}):
        doc_chunks = [c for c in all_chunks if c.doc_code == code]
        print(f"  {code:<12} {len(doc_chunks):>3} chunks  "
              f"{sum(c.token_count for c in doc_chunks):>5} tokens")
