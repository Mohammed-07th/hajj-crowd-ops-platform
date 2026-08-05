"""PII handling: hashing for the lakehouse, redaction for the vector store.

Two different treatments, for two different reasons.

**Hashing (silver).** `pilgrim_ref` and `reporter_phone` are replaced with
`sha256(value + PII_SALT)` and the raw columns are dropped. Hashing rather than
deleting preserves the one analytical property that matters - you can still
count distinct reporters and spot a single person raising twenty requests -
without keeping the identifier. The salt is what stops the hash being reversible
by rainbow table: the phone-number space is small enough to enumerate.

**Redaction (vector store).** `description` is free text that may contain names
and phone numbers. It is redacted *before embedding*, not filtered at query
time, because an embedding is derived from its source text and can leak
information about it. Once a name has been embedded, the vector carries traces
of that name into the index; no query-time filter can retract it. Redaction has
to happen upstream of the encoder or it has not happened at all.
"""

from __future__ import annotations

import hashlib
import re

from config.settings import settings

# Phone numbers: international (+9665...) and local runs of digits.
_PHONE_RE = re.compile(r"(\+?\d[\d\s\-()]{7,}\d)")
# Any long digit run - pilgrim refs, document numbers, ID numbers.
_LONG_DIGITS_RE = re.compile(r"\b\d{6,}\b")
# "Name: Abdullah" and Arabic equivalent - everything after the marker up to
# punctuation that ends the clause.
_NAME_RE = re.compile(r"(?:\bName\s*:|\bاسم\s*:)\s*[^,.;\n]*", re.IGNORECASE)


def hash_pii(value: str | None, salt: str | None = None) -> str | None:
    """Salted SHA-256. Returns None for None so nulls stay nulls."""
    if value is None or value == "":
        return None
    salt = settings.pii_salt if salt is None else salt
    return hashlib.sha256((value + salt).encode("utf-8")).hexdigest()


def redact_description(text: str | None) -> str | None:
    """Strip names, phone numbers and long digit runs from free text.

    Order matters: the name marker is removed first, because a name clause can
    itself contain digits that the later patterns would only partially mask.
    """
    if text is None:
        return None
    redacted = _NAME_RE.sub("Name: [REDACTED]", text)
    redacted = _PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    redacted = _LONG_DIGITS_RE.sub("[REDACTED_ID]", redacted)
    return redacted
