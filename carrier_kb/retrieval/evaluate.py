from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import yaml

from carrier_kb.domain import Corpus
from carrier_kb.retrieval.repository import PostgresKnowledgeRepository
from carrier_kb.settings import Settings


async def evaluate(path: Path) -> list[dict[str, object]]:
    settings = Settings()
    repository = PostgresKnowledgeRepository(settings.kb_dsn, settings.kb_schema)
    cases = yaml.safe_load(path.read_text(encoding="utf-8")).get("questions", [])
    results = []
    for case in cases:
        evidence = await repository.search(case["question"], (Corpus(case["corpus"]),))
        text = "\n".join(item.body.lower() for item in evidence)
        terms = [term.lower() for term in case.get("expected_terms", [])]
        any_groups = [[term.lower() for term in group] for group in case.get("expected_any_terms", [])]
        found_any = [group for group in any_groups if any(term in text for term in group)]
        results.append({
            "id": case["id"],
            "matches": len(evidence),
            "citations": sum(len(item.citations) for item in evidence),
            "expected_terms_found": [term for term in terms if term in text],
            "expected_any_groups_found": len(found_any),
            "passed": bool(evidence) and all(term in text for term in terms) and len(found_any) == len(any_groups),
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Carrier KB retrieval")
    parser.add_argument("--questions", type=Path, default=Path("config/eval_questions.yaml"))
    args = parser.parse_args()
    results = asyncio.run(evaluate(args.questions))
    for result in results:
        print(result)
    passed = sum(bool(result["passed"]) for result in results)
    print(f"passed {passed}/{len(results)}")


if __name__ == "__main__":
    main()
