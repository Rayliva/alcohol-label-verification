"""The review queue, in memory.

Not persistence. The queue is seeded from recorded results at startup and lives
for the life of the process, which is the honest shape for a prototype that
stores nothing (PRD C-2). A restart returns it to the seeded state and loses
any uploads and decisions made since — the UI says so rather than implying
otherwise.

Seeded results are *recorded*, not recomputed. They came from the real pipeline
via samples/generate_results.py and are read from disk, so the queue renders
instantly on every boot and spends no OCR or model call to show a verdict it
already knows. Re-analysing 31 labels on every cold start would cost minutes
and money to arrive at the same answer.
"""

from __future__ import annotations

import json
import pathlib
import threading
import time
from dataclasses import dataclass
from typing import Any, Literal

SAMPLES = pathlib.Path(__file__).resolve().parent.parent / "samples"

Source = Literal["seeded", "uploaded"]


@dataclass
class Decision:
    action: Literal["approve", "reject", "override"]
    note: str
    decided_at: float
    decided_by: str


@dataclass
class QueueItem:
    id: str
    brand: str
    # What the agent declared on the COLA form, distinct from the row's own
    # id. It is what they will search for.
    application_id: str | None
    beverage_type: str
    # "pass" | "needs_review" | "fail" | "unreadable"
    outcome: str
    processing_ms: int | None
    source: Source
    received_at: float
    result: dict[str, Any] | None = None
    unreadable: dict[str, str] | None = None
    image_name: str | None = None
    decision: Decision | None = None

    def summary(self) -> dict[str, Any]:
        """What the queue table needs. Deliberately excludes the crops."""
        return {
            "id": self.id,
            "brand": self.brand,
            "application_id": self.application_id,
            "beverage_type": self.beverage_type,
            "outcome": self.outcome,
            "processing_ms": self.processing_ms,
            "source": self.source,
            "decision": None
            if self.decision is None
            else {
                "action": self.decision.action,
                "note": self.decision.note,
                "decided_by": self.decision.decided_by,
            },
        }


# Judgment first. A FAIL the tool is sure about still needs signing off, but a
# NEEDS_REVIEW is the row an agent is uniquely needed for — that is the work
# only a person can do, so it should not sit below work already settled.
# Unreadable comes next: also a human action, but a smaller one (ask for a
# better photograph). A decided row drops to the bottom, because it is done.
_ORDER = {"needs_review": 0, "unreadable": 1, "fail": 2, "pass": 3}


def _rank(item: QueueItem) -> tuple[int, int, float]:
    return (
        1 if item.decision else 0,
        _ORDER.get(item.outcome, 2),
        -item.received_at,
    )


class ReviewQueue:
    def __init__(self) -> None:
        self._items: dict[str, QueueItem] = {}
        self._lock = threading.Lock()
        self._seeded = False

    def seed(self) -> int:
        """Load the recorded results. Idempotent."""
        with self._lock:
            if self._seeded:
                return len(self._items)
            path = SAMPLES / "results.json"
            if path.exists():
                records = json.loads(path.read_text(encoding="utf-8"))
                for offset, record in enumerate(records):
                    item = _from_record(record, offset)
                    self._items[item.id] = item
            self._seeded = True
            return len(self._items)

    def list(self) -> list[QueueItem]:
        with self._lock:
            return sorted(self._items.values(), key=_rank)

    def get(self, item_id: str) -> QueueItem | None:
        with self._lock:
            return self._items.get(item_id)

    def add(self, item: QueueItem) -> QueueItem:
        with self._lock:
            self._items[item.id] = item
            return item

    def next_undecided(self) -> QueueItem | None:
        """The first undecided item in queue order — what "next" means to the UI."""
        with self._lock:
            undecided = [i for i in self._items.values() if i.decision is None]
            return min(undecided, key=_rank) if undecided else None

    def decide(self, item_id: str, *, action: str, note: str, by: str) -> QueueItem | None:
        with self._lock:
            item = self._items.get(item_id)
            if item is None:
                return None
            item.decision = Decision(
                action=action,  # type: ignore[arg-type]
                note=note,
                decided_at=time.time(),
                decided_by=by,
            )
            return item


def _from_record(record: dict[str, Any], offset: int) -> QueueItem:
    result = record.get("result")
    declared = record.get("declared") or {}
    brand = declared.get("brand_name") or record["id"]
    if record.get("unreadable") or result is None:
        outcome, processing_ms = "unreadable", None
    else:
        outcome = result["overall"]
        processing_ms = result["processing_ms"]
    return QueueItem(
        id=record["id"],
        brand=brand,
        # Seeded rows answer to their record id; there is no separate COLA
        # number in the seed data to show or search.
        application_id=None,
        beverage_type=record.get("beverage_type", "spirits"),
        outcome=outcome,
        processing_ms=processing_ms,
        source="seeded",
        # Negative offset because _rank sorts newest-first (-received_at):
        # real uploads carry a large epoch time and land first, and seeded
        # rows keep manifest order behind them instead of reversing it.
        received_at=float(-offset),
        result=result,
        unreadable=record.get("unreadable"),
        image_name=record.get("image"),
    )


queue = ReviewQueue()
