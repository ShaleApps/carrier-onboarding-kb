from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from carrier_kb.domain import Corpus

SourceKind = Literal["google_drive", "slack", "lohi_view", "static_file", "front_csv"]


@dataclass(frozen=True)
class SourceDefinition:
    id: str
    kind: SourceKind
    corpus: Corpus
    owner: str
    refresh: str
    file_ids: tuple[str, ...] = ()
    channel_ids: tuple[str, ...] = ()
    view: str | None = None
    path: str | None = None
    chunk_chars: int = 12000


def load_registry(path: Path) -> list[SourceDefinition]:
    raw = yaml.safe_load(path.read_text()) or {}
    out: list[SourceDefinition] = []
    seen: set[str] = set()
    for source in raw.get("sources", []):
        source_id = source["id"]
        if source_id in seen:
            raise ValueError(f"duplicate source id: {source_id}")
        seen.add(source_id)
        kind = source["kind"]
        corpus = Corpus(source["visibility"])
        if kind == "google_drive" and not source.get("file_ids"):
            raise ValueError(f"{source_id}: Google Drive source needs file_ids")
        if kind == "slack" and not source.get("channel_ids"):
            raise ValueError(f"{source_id}: Slack source needs channel_ids")
        if kind == "lohi_view" and not source.get("view"):
            raise ValueError(f"{source_id}: LoHi source needs a named view")
        if kind in {"static_file", "front_csv"} and not source.get("path"):
            raise ValueError(f"{source_id}: file source needs a path")
        chunk_chars = int(source.get("chunk_chars", 12000))
        if chunk_chars < 1000 or chunk_chars > 50000:
            raise ValueError(f"{source_id}: chunk_chars must be between 1000 and 50000")
        out.append(SourceDefinition(
            id=source_id, kind=kind, corpus=corpus, owner=source["owner"], refresh=source["refresh"],
            file_ids=tuple(source.get("file_ids", [])), channel_ids=tuple(source.get("channel_ids", [])),
            view=source.get("view"), path=source.get("path"), chunk_chars=chunk_chars,
        ))
    return out
