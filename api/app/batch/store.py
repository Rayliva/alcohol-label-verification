"""In-memory job store and worker pool.

Not persistence. A job lives for the life of the process, which is the honest
shape for a prototype that stores nothing (PRD C-2). The dict sits behind a
small interface so it can become Redis if this ever needs more than one worker,
and the README says plainly that a restart loses in-flight jobs.

Progress is determinate throughout — "47 of 200 checked", never a spinner — and
the estimate of time remaining is computed from measured throughput rather than
a constant (.claude/rules/measure-dont-claim.md).

See docs/specs/batch.md 2.2 and 2.3
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Literal

from app.errors import LabelVerificationError

State = Literal["pending", "running", "stopped", "finished"]

# Eight at a time: enough to keep a 200-label run inside a coffee break, few
# enough not to trip the OCR provider's rate limit.
DEFAULT_CONCURRENCY = 8


@dataclass
class LabelOutcome:
    """One label's place in the run, whatever happened to it."""

    application_id: str
    image: str
    outcome: str
    payload: dict[str, Any]


@dataclass
class Job:
    id: str
    total: int
    results: list[LabelOutcome] = field(default_factory=list)
    state: State = "pending"
    started_at: float = field(default_factory=time.perf_counter)
    problems: list[dict[str, str]] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def done(self) -> int:
        return len(self.results)

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def stop(self) -> None:
        self._stop.set()

    def record(self, outcome: LabelOutcome) -> None:
        with self._lock:
            self.results.append(outcome)

    def counts(self, results: list[LabelOutcome] | None = None) -> dict[str, int]:
        """Tally one consistent view of the results, not two.

        Taking a fresh copy here while the caller holds an older one lets a
        progress screen show "12 of 300 checked" beside filter chips adding up
        to 93. The counts have to come from the same snapshot as the number.
        """
        tally = {"pass": 0, "needs_review": 0, "fail": 0, "unreadable": 0, "error": 0}
        for result in results if results is not None else list(self.results):
            tally[result.outcome] = tally.get(result.outcome, 0) + 1
        return tally

    def snapshot(self) -> dict[str, Any]:
        """Everything a progress screen needs, safe to read mid-run."""
        results = list(self.results)
        elapsed = time.perf_counter() - self.started_at
        per_label = elapsed / len(results) if results else None
        remaining = self.total - len(results)
        return {
            "job_id": self.id,
            "state": self.state,
            "done": len(results),
            "total": self.total,
            "elapsed_seconds": round(elapsed, 1),
            # Measured, not assumed. None until there is something to measure.
            "seconds_per_label": round(per_label, 2) if per_label else None,
            "estimated_seconds_remaining": (
                round(per_label * remaining, 1) if per_label and remaining > 0 else 0
            ),
            "counts": self.counts(results),
            "problems": list(self.problems),
            # The full per-label report, evidence crops and all, stays out of
            # this. A progress screen polls every second and needs six fields
            # per row; carrying the whole report made a 300-label snapshot
            # about 21 MB and re-sent it on every tick. GET .../label/{index}
            # serves one label's report when a row is opened.
            "results": [
                {
                    "application_id": result.application_id,
                    "image": result.image,
                    "outcome": result.outcome,
                    **{key: value for key, value in result.payload.items() if key != "label"},
                }
                for result in results
            ],
        }


class JobStore:
    """Every job this process knows about."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, total: int, problems: list[dict[str, str]] | None = None) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], total=total, problems=problems or [])
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)


store = JobStore()


def run_job(
    job: Job,
    work: list[tuple[str, str, bytes, Mapping[str, Any]]],
    check: Callable[[bytes, Mapping[str, Any]], tuple[str, dict[str, Any]]],
    concurrency: int = DEFAULT_CONCURRENCY,
) -> None:
    """Check every item, recording each result as it lands.

    One failing label never stops the run. An unreadable image is a result in
    its own bucket, not an error — "we could not read this" is not "this label
    is non-compliant" (PRD FR-3) — and anything else is recorded against its
    application id with the reason, so the agent can see which one and why.
    """
    job.state = "running"

    def one(item: tuple[str, str, bytes, Mapping[str, Any]]) -> None:
        application_id, image_name, image_bytes, declared = item
        if job.stopping:
            return
        try:
            outcome, payload = check(image_bytes, declared)
        except LabelVerificationError as exc:
            outcome, payload = "error", {"error": exc.as_dict()}
        except Exception as exc:
            # The reason travels with the row. "RuntimeError" tells an agent
            # nothing; "ANTHROPIC_API_KEY is not set" tells them everything,
            # and 300 rows all saying the former is 300 wasted minutes.
            outcome, payload = (
                "error",
                {
                    "error": {
                        "code": "label_failed",
                        "message": f"This label could not be checked: {exc}",
                        "what_to_do": "Check it on its own to see the full reason.",
                    }
                },
            )
        job.record(
            LabelOutcome(
                application_id=application_id,
                image=image_name,
                outcome=outcome,
                payload=payload,
            )
        )

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        list(pool.map(one, work))

    job.state = "stopped" if job.stopping else "finished"
