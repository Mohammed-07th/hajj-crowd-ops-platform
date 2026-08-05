"""Reciprocal Rank Fusion, checked against hand-computed values.

    score(d) = SUM_i 1 / (k + rank_i(d)),  rank starting at 1, k = 60
"""

from __future__ import annotations

import pytest

from src.rag.retriever import reciprocal_rank_fusion, tokenize

K = 60


def _list(*chunk_ids: str) -> list[dict]:
    return [{"chunk_id": cid} for cid in chunk_ids]


def test_single_list_matches_hand_computation():
    fused = reciprocal_rank_fusion([_list("A", "B", "C")], k=K)
    assert fused["A"] == pytest.approx(1 / 61)
    assert fused["B"] == pytest.approx(1 / 62)
    assert fused["C"] == pytest.approx(1 / 63)


def test_document_in_both_lists_accumulates_both_terms():
    """B is rank 2 in the first list and rank 1 in the second.

        score(B) = 1/(60+2) + 1/(60+1) = 0.016129... + 0.016393... = 0.032522...
    """
    fused = reciprocal_rank_fusion([_list("A", "B"), _list("B", "A")], k=K)
    assert fused["B"] == pytest.approx(1 / 62 + 1 / 61)
    # 1/62 = 0.01612903..., 1/61 = 0.01639344..., sum = 0.03252247...
    assert fused["B"] == pytest.approx(0.03252247, abs=1e-8)
    # A is rank 1 then rank 2 - by symmetry the same total.
    assert fused["A"] == pytest.approx(fused["B"])


def test_agreement_beats_a_single_strong_hit():
    """The core RRF property.

    X is rank 1 in one list and absent from the other: 1/61 = 0.016393.
    Y is rank 2 in both lists:                  2 * 1/62 = 0.032258.
    Consensus wins, which is the behaviour RRF is chosen for.
    """
    fused = reciprocal_rank_fusion([_list("X", "Y"), _list("Z", "Y")], k=K)
    assert fused["Y"] == pytest.approx(2 / 62)
    assert fused["X"] == pytest.approx(1 / 61)
    assert fused["Y"] > fused["X"]


def test_absent_documents_are_not_penalised_only_omitted():
    fused = reciprocal_rank_fusion([_list("A"), _list("B")], k=K)
    assert set(fused) == {"A", "B"}
    assert fused["A"] == pytest.approx(1 / 61)
    assert fused["B"] == pytest.approx(1 / 61)


def test_k_damps_the_influence_of_top_ranks():
    """With k=0 rank 1 is worth double rank 2; with k=60 they are near-equal.

    This is precisely why k exists: without it one retriever's top hit
    dominates the fusion.
    """
    small_k = reciprocal_rank_fusion([_list("A", "B")], k=0)
    assert small_k["A"] / small_k["B"] == pytest.approx(2.0)

    large_k = reciprocal_rank_fusion([_list("A", "B")], k=K)
    assert large_k["A"] / large_k["B"] == pytest.approx(62 / 61, abs=1e-6)


def test_rank_1_plus_rank_3_narrowly_beats_rank_2_twice():
    """A surprising consequence of k=60, worth pinning down.

        A: rank 1 + rank 3 = 1/61 + 1/63 = 0.03226646
        B: rank 2 + rank 2 = 2/62         = 0.03225806

    Intuition says two middling ranks should beat one good and one poor, and
    with a small k they would. At k=60 the reciprocal curve is so flat that the
    single top-1 placement edges it - by 8e-6. This is the damping described in
    src/rag/retriever.py doing exactly what it is supposed to, and it is why RRF
    tolerates a retriever that returns a good hit the other misses entirely.
    """
    fused = reciprocal_rank_fusion([_list("A", "B", "C"), _list("C", "B", "A")], k=K)

    assert fused["A"] == pytest.approx(1 / 61 + 1 / 63)
    assert fused["B"] == pytest.approx(2 / 62)
    # Symmetric: A and C each take one rank-1 and one rank-3 placement.
    assert fused["A"] == pytest.approx(fused["C"])

    assert fused["A"] > fused["B"]
    assert fused["A"] - fused["B"] == pytest.approx(8.4e-6, abs=1e-6)

    ordered = sorted(fused, key=lambda d: fused[d], reverse=True)
    assert ordered[-1] == "B"


def test_empty_input_is_safe():
    assert reciprocal_rank_fusion([], k=K) == {}
    assert reciprocal_rank_fusion([[]], k=K) == {}


# --- tokenizer, which BM25 depends on -------------------------------------

def test_tokenizer_keeps_document_codes_intact():
    """Splitting SOP-CS-011 into three tokens destroys BM25's exact-match edge."""
    assert "sop-cs-011" in tokenize("Escalate under SOP-CS-011 immediately.")


def test_tokenizer_keeps_zone_codes_intact():
    assert "jam_bridge_l3" in tokenize("Evacuate JAM_BRIDGE_L3 first.")


def test_tokenizer_handles_arabic():
    tokens = tokenize("ما هي إجراءات الإخلاء؟")
    assert any("الإخلاء" in t for t in tokens)
