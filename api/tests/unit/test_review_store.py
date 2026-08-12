"""The review queue's next-undecided pointer.

The decision response tells the UI where to go next, in the queue's own sort
order, so "next" means the same thing on every screen.
"""

from __future__ import annotations

import pytest

from app.review.store import QueueItem, ReviewQueue


def item(item_id: str, *, outcome: str = "pass", received_at: float = 0.0) -> QueueItem:
    return QueueItem(
        id=item_id,
        brand=item_id,
        beverage_type="spirits",
        outcome=outcome,
        processing_ms=1000,
        source="seeded",
        received_at=received_at,
    )


@pytest.fixture()
def fresh() -> ReviewQueue:
    queue = ReviewQueue()
    queue.add(item("settled", outcome="pass"))
    queue.add(item("judgment", outcome="needs_review"))
    queue.add(item("confident-fail", outcome="fail"))
    return queue


class TestNextUndecided:
    def test_the_next_item_is_the_queues_own_first_undecided(self, fresh: ReviewQueue) -> None:
        # needs_review sorts first, so it is also what "next" means.
        assert fresh.next_undecided().id == "judgment"

    def test_a_decided_item_is_no_longer_next(self, fresh: ReviewQueue) -> None:
        fresh.decide("judgment", action="approve", note="", by="agent")
        assert fresh.next_undecided().id == "confident-fail"

    def test_no_undecided_items_means_no_next(self, fresh: ReviewQueue) -> None:
        for item_id in ("settled", "judgment", "confident-fail"):
            fresh.decide(item_id, action="approve", note="", by="agent")
        assert fresh.next_undecided() is None
