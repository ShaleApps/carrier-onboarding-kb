"""Build a redacted, read-only inventory of questions in OME transcripts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import psycopg

_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d().\- ]{7,}\d)(?!\w)")
_LONG_NUMBER = re.compile(r"(?<!\w)\d{5,}(?!\w)")
_SPACE = re.compile(r"\s+")
_SPEAKER = re.compile(r"^(?P<speaker>[A-Za-z][A-Za-z _-]{0,30}):\s*(?P<body>.*)$")
_INTERROGATIVE = re.compile(
    r"^(?:who|what|when|where|why|how|can|could|do|does|did|is|are|am|was|were|will|would|should|may|might|have|has|hello is)\b",
    re.IGNORECASE,
)

_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("status_follow_up", ("status", "next step", "next steps", "update", "approved", "pending")),
    ("pay_rates_loads", ("pay", "rate", "gross", "earn", "load", "miles", "per day", "per week")),
    ("equipment_lanes", ("truck", "trailer", "equipment", "power only", "dry van", "lane", "where do you run")),
    ("onboarding_application", ("onboard", "application", "register", "sign up", "start working", "next steps")),
    ("insurance_rmis", ("rmis", "evident", "insurance", "coi", "certificate")),
    ("documents_compliance", ("w-9", "w9", "document", "license", "authority", "dot", "mc number")),
    ("training", ("training", "orientation", "course", "quiz")),
    ("payment_factoring", ("factoring", "payment", "paid", "invoice", "settlement", "deposit")),
    ("bonus_referral", ("bonus", "referral", "incentive")),
    ("support_contact", ("call", "phone", "contact", "help", "speak to someone", "who can")),
)


def redact(text: str) -> str:
    """Remove direct identifiers while retaining the wording needed for taxonomy work."""
    text = _EMAIL.sub("[email]", text)
    text = _PHONE.sub("[phone]", text)
    text = _LONG_NUMBER.sub("[number]", text)
    return _SPACE.sub(" ", text).strip()


def classify(question: str) -> str:
    lowered = question.lower()
    for category, terms in _CATEGORIES:
        if any(term in lowered for term in terms):
            return category
    return "unclassified"


def classify_kind(speaker: str, question: str) -> str:
    """Distinguish real carrier turns from scripted and quoted context."""
    lowered = question.lower()
    if any(marker in lowered for marker in (
        "prior cross-channel history", "email/inbound", "email/outbound",
        "sms/inbound", "sms/outbound", "plus ", "sent from my iphone",
    )):
        return "embedded_context"
    if speaker == "agent":
        return "agent_script"
    if speaker in {"carrier", "caller"}:
        return "carrier_question"
    return "unattributed_question"


def extract_questions(transcript: str) -> list[tuple[str, str]]:
    """Return (speaker, redacted question) pairs, without topic filtering."""
    result: list[tuple[str, str]] = []
    for raw_line in transcript.splitlines():
        line = _SPACE.sub(" ", raw_line).strip()
        if not line:
            continue
        match = _SPEAKER.match(line)
        speaker = match.group("speaker").lower() if match else "unknown"
        body = match.group("body") if match else line
        # Include explicit questions and question-shaped utterances lacking punctuation.
        if "?" not in body and not _INTERROGATIVE.match(body):
            continue
        question = redact(body)
        if question:
            result.append((speaker, question))
    return result


async def build_inventory(dsn: str, output: Path) -> dict[str, object]:
    async with await psycopg.AsyncConnection.connect(dsn) as connection, connection.cursor() as cursor:
        await cursor.execute(
            """SELECT call_record_id, case_key, transcript_text, created_at
               FROM public.recruiter_voice_transcript
               WHERE transcript_text IS NOT NULL AND btrim(transcript_text) <> ''
               ORDER BY created_at DESC NULLS LAST"""
        )
        rows = await cursor.fetchall()

    records: list[dict[str, object]] = []
    for call_record_id, case_key, transcript, created_at in rows:
        for speaker, question in extract_questions(transcript):
            records.append(
                {
                    "call_record_id": str(call_record_id),
                    "case_key": case_key or "unknown",
                    "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
                    "speaker": speaker,
                    "question": question,
                    "category": classify(question),
                    "kind": classify_kind(speaker, question),
                }
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "transcripts_scanned": len(rows),
        "question_utterances": len(records),
        "unique_questions": len({r["question"] for r in records}),
        "records": records,
    }
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/ome-question-inventory.json"))
    args = parser.parse_args()
    dsn = os.environ.get("OME_ANALYTICS_DSN") or os.environ.get("OME_DSN")
    if not dsn:
        parser.error("OME_ANALYTICS_DSN is required")
    payload = asyncio.run(build_inventory(dsn, args.output))
    counts = Counter(record["category"] for record in payload["records"])
    kinds = Counter(record["kind"] for record in payload["records"])
    print(f"scanned {payload['transcripts_scanned']} transcripts")
    print(f"extracted {payload['question_utterances']} question utterances")
    print(f"unique normalized questions: {payload['unique_questions']}")
    for kind, count in kinds.most_common():
        print(f"{kind}: {count}")
    for category, count in counts.most_common():
        print(f"{category}: {count}")


if __name__ == "__main__":
    main()
