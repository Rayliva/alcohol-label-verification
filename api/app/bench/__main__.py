"""Phase 0 latency spike.

Answers three questions before any UI is built:
  1. Which model, on latency AND extraction accuracy.
  2. Does thinking-off beat adaptive-at-low-effort.
  3. Where does the time actually go.

Reports p50 and p95 — the PRD target is p95 < 5s, and a good mean with a bad
tail still fails the agent's experience. See .claude/rules/measure-dont-claim.md

Usage:
    python -m app.bench --models claude-haiku-4-5,claude-opus-5 --n 8
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

from app.extraction.client import extract_from_text
from app.extraction.schema import ExtractedFields

# Stand-in for OCR output until Cloud Vision credentials land. Token count and
# shape are realistic; only the OCR stage latency is still unknown.
SAMPLE_OCR_TEXT = """OLD TOM DISTILLERY
Kentucky Straight Bourbon Whiskey
45% Alc./Vol. (90 Proof)
750 mL
Bottled by Old Tom Distillery, Bardstown, Kentucky
GOVERNMENT WARNING: (1) According to the Surgeon General, women should not \
drink alcoholic beverages during pregnancy because of the risk of birth defects. \
(2) Consumption of alcoholic beverages impairs your ability to drive a car or \
operate machinery, and may cause health problems."""

EXPECTED = ExtractedFields(
    brand_name="OLD TOM DISTILLERY",
    class_type="Kentucky Straight Bourbon Whiskey",
    alcohol_content="45% Alc./Vol. (90 Proof)",
    net_contents="750 mL",
    bottler_address="Bottled by Old Tom Distillery, Bardstown, Kentucky",
    country_of_origin=None,
    government_warning=(
        "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
        "drink alcoholic beverages during pregnancy because of the risk of birth "
        "defects. (2) Consumption of alcoholic beverages impairs your ability to "
        "drive a car or operate machinery, and may cause health problems."
    ),
)

SCORED_FIELDS = (
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "bottler_address",
    "government_warning",
)


@dataclass
class Arm:
    model: str
    thinking: str
    latencies: list[float] = field(default_factory=list)
    exact_fields: int = 0
    total_fields: int = 0
    output_tokens: int = 0
    cache_reads: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.model} / thinking={self.thinking}"

    def p(self, pct: float) -> float:
        if not self.latencies:
            return float("nan")
        ordered = sorted(self.latencies)
        idx = min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))
        return ordered[idx]

    @property
    def accuracy(self) -> float:
        return self.exact_fields / self.total_fields if self.total_fields else 0.0


def score(actual: ExtractedFields) -> tuple[int, int]:
    """Exact-match count over the scored fields."""
    hits = sum(
        1
        for name in SCORED_FIELDS
        if (getattr(actual, name) or "").strip() == (getattr(EXPECTED, name) or "").strip()
    )
    return hits, len(SCORED_FIELDS)


def run_arm(model: str, thinking: str, n: int, warmup: int) -> Arm:
    arm = Arm(model=model, thinking=thinking)

    for _ in range(warmup):
        try:
            extract_from_text(SAMPLE_OCR_TEXT, model=model, thinking=thinking)  # type: ignore[arg-type]
        except Exception as exc:
            arm.errors.append(f"warmup: {type(exc).__name__}: {exc}")
            return arm

    for _ in range(n):
        try:
            result = extract_from_text(SAMPLE_OCR_TEXT, model=model, thinking=thinking)  # type: ignore[arg-type]
        except Exception as exc:
            arm.errors.append(f"{type(exc).__name__}: {exc}")
            continue
        arm.latencies.append(result.latency_ms)
        hits, total = score(result.fields)
        arm.exact_fields += hits
        arm.total_fields += total
        arm.output_tokens = result.output_tokens
        arm.cache_reads.append(result.cache_read_tokens)

    return arm


def report(arms: list[Arm], n: int, warmup: int) -> None:
    print()
    print(f"Phase 0 spike — n={n} measured per arm, {warmup} warmup call(s) discarded")
    print("Target: p95 < 5000ms for the FULL pipeline. This measures the LLM leg only;")
    print("OCR (~300-800ms per vendor docs, unverified) is not yet included.")
    print()
    header = (
        f"{'arm':44} {'p50':>7} {'p95':>7} {'min':>7} {'max':>7} {'acc':>6} {'out':>5} {'cache':>6}"
    )
    print(header)
    print("-" * len(header))
    for arm in arms:
        if arm.errors and not arm.latencies:
            print(f"{arm.label:44} {'ERROR':>7}  {arm.errors[0][:60]}")
            continue
        cached = "yes" if any(c > 0 for c in arm.cache_reads) else "NO"
        print(
            f"{arm.label:44} "
            f"{arm.p(50):>7.0f} {arm.p(95):>7.0f} "
            f"{min(arm.latencies):>7.0f} {max(arm.latencies):>7.0f} "
            f"{arm.accuracy:>6.0%} {arm.output_tokens:>5} {cached:>6}"
        )
    print()

    ok = [a for a in arms if a.latencies and a.p(95) < 5000]
    if ok:
        best = min(ok, key=lambda a: (round(1 - a.accuracy, 2), a.p(95)))
        print(f"Under target: {', '.join(a.label for a in ok)}")
        print(f"Best on accuracy then p95: {best.label}")
    else:
        print("NO ARM MEETS p95 < 5000ms on the LLM leg alone.")
        print("Per docs/build-loop.md Phase 0: stop and redesign before building UI.")

    for arm in arms:
        for err in arm.errors[:2]:
            print(f"  ! {arm.label}: {err[:140]}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.bench")
    parser.add_argument(
        "--models",
        default="claude-haiku-4-5,claude-sonnet-5,claude-opus-5",
        help="comma-separated model ids",
    )
    parser.add_argument("--thinking", default="disabled", help="comma-separated: disabled,adaptive")
    parser.add_argument("--n", type=int, default=8, help="measured runs per arm")
    parser.add_argument("--warmup", type=int, default=1, help="discarded runs per arm")
    args = parser.parse_args()

    arms = [
        run_arm(model.strip(), thinking.strip(), args.n, args.warmup)
        for model in args.models.split(",")
        for thinking in args.thinking.split(",")
    ]
    report(arms, args.n, args.warmup)
    return 0


if __name__ == "__main__":
    sys.exit(main())
