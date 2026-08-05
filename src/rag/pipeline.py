"""End-to-end ask: hybrid retrieve -> rerank -> generate with citations."""

from __future__ import annotations

import argparse
import json
import sys

from config.settings import settings
from src.rag.generator import Answer, generate
from src.rag.reranker import rerank
from src.rag.retriever import hybrid_search


def ask(question: str, use_cache: bool = True) -> Answer:
    fused, _ = hybrid_search(question, settings.retrieve_top_k)
    top = rerank(question, fused, settings.rerank_top_k)
    return generate(question, top, use_cache=use_cache)


def main() -> int:
    ap = argparse.ArgumentParser(description="Ask the operations copilot")
    ap.add_argument("question")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    answer = ask(args.question, use_cache=not args.no_cache)
    print(json.dumps(answer.to_dict(), indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
