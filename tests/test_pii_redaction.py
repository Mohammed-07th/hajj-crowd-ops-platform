"""PII hashing and redaction.

The redaction tests matter more than they look: redaction runs *before*
embedding, so anything these tests miss ends up encoded into vectors in Qdrant
where no query-time filter can retract it.
"""

from __future__ import annotations

from src.governance.pii import hash_pii, redact_description


def test_hash_is_deterministic_for_the_same_salt():
    assert hash_pii("PIL-12345678", salt="s") == hash_pii("PIL-12345678", salt="s")


def test_hash_changes_with_the_salt():
    """An unsalted hash of a phone number is trivially reversible by enumeration."""
    assert hash_pii("+966512345678", salt="a") != hash_pii("+966512345678", salt="b")


def test_hash_is_not_reversible_to_the_input():
    value = "PIL-99887766"
    digest = hash_pii(value, salt="pepper")
    assert value not in digest
    assert len(digest) == 64


def test_nulls_stay_null():
    assert hash_pii(None) is None
    assert hash_pii("") is None
    assert redact_description(None) is None


def test_redacts_name_marker():
    text = "Heat exhaustion case, patient Name: Abdullah requires shaded triage"
    out = redact_description(text)
    assert "Abdullah" not in out
    assert "[REDACTED]" in out
    # Surrounding clinical detail must survive - redaction should not gut the text.
    assert "Heat exhaustion" in out


def test_redacts_phone_numbers():
    out = redact_description("Elderly woman lost, contact 0555123456 for family liaison")
    assert "0555123456" not in out
    assert "family liaison" in out


def test_redacts_international_phone_numbers():
    out = redact_description("Reporter reachable on +966512345678 all evening")
    assert "512345678" not in out
    assert "966" not in out


def test_redacts_long_digit_runs_such_as_pilgrim_refs():
    out = redact_description("Pilgrim ref 99887766 presented at the clinic")
    assert "99887766" not in out


def test_keeps_short_numbers_that_carry_operational_meaning():
    """Redaction must not destroy the facts the SOP retrieval depends on."""
    out = redact_description("Zamzam dispenser empty at station 4, level 2")
    assert "station 4" in out
    assert "level 2" in out


def test_arabic_name_marker_is_redacted():
    out = redact_description("بلاغ عن اسم: عبدالله بحاجة إلى مساعدة")
    assert "عبدالله" not in out
