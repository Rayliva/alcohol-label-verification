"""Measure what an agent actually waits for.

Hits a running instance with real corpus labels and reports the distribution,
because the PRD names p95 and a mean would hide the tail that made the last
vendor pilot fail (.claude/rules/measure-dont-claim.md).

    python -m app.bench.latency --base https://... --count 20
    python -m app.bench.latency --base http://127.0.0.1:8000 --batch 200

Everything it prints carries the date, the target, and the sample size, so a
number can never be quoted without the conditions it was measured under.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
IMAGES = REPO_ROOT / "corpus" / "out"
EXPECTED = REPO_ROOT / "corpus" / "fixtures" / "expected.json"


def _labels(count: int, tiers: tuple[int, ...] = (1, 2, 5)) -> list[dict]:
    payload = json.loads(EXPECTED.read_text(encoding="utf-8"))
    usable = [
        entry
        for entry in payload["labels"]
        if entry["tier"] in tiers and entry["beverage_type"] == "spirits"
    ]
    return usable[:count]


def _multipart(fields: dict[str, str], image_name: str, image: bytes) -> tuple[bytes, str]:
    boundary = "----labelcheckbench"
    parts: list[bytes] = []
    for name, value in fields.items():
        if value is None:
            continue
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; '
        f'filename="{image_name}"\r\nContent-Type: image/png\r\n\r\n'.encode()
    )
    parts.append(image)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _one(base: str, entry: dict) -> tuple[float, str, dict]:
    image = (IMAGES / entry["image"]).read_bytes()
    fields = {
        "beverage_type": entry["beverage_type"],
        "application_id": entry["id"],
        **{k: v for k, v in entry["application"].items() if v},
    }
    body, content_type = _multipart(fields, entry["image"], image)
    request = urllib.request.Request(
        f"{base}/api/verify", data=body, headers={"Content-Type": content_type}
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read())
    elapsed = (time.perf_counter() - started) * 1000
    return elapsed, payload.get("overall", "?"), payload.get("stage_ms", {})


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return ordered[index]


def single(base: str, count: int, concurrency: int) -> None:
    entries = _labels(count)
    if not entries:
        sys.exit(f"No corpus images in {IMAGES}. Run corpus/generate.py --all first.")

    print(f"Target      {base}")
    print(f"Labels      {len(entries)} (concurrency {concurrency})")

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(lambda entry: _one(base, entry), entries))
    wall = time.perf_counter() - started

    latencies = [result[0] for result in results]
    stages: dict[str, list[float]] = {}
    for _, _, stage_ms in results:
        for name, value in stage_ms.items():
            stages.setdefault(name, []).append(value)

    print()
    print(f"p50         {statistics.median(latencies):8.0f} ms")
    print(f"p95         {_percentile(latencies, 0.95):8.0f} ms")
    print(f"min / max   {min(latencies):8.0f} / {max(latencies):.0f} ms")
    print(f"wall clock  {wall:8.1f} s")
    print()
    print("Median per stage, server-side:")
    for name in ("decode_ms", "quality_ms", "ocr_ms", "extraction_ms", "rules_ms", "crops_ms"):
        if name in stages:
            print(f"  {name:<14} {statistics.median(stages[name]):7.0f} ms")


def batch(base: str, count: int) -> None:
    """Throughput: does a peak-season batch finish, with progress visible?"""
    entries = _labels(count, tiers=(1, 2, 5))
    while len(entries) < count:  # permute to reach the requested size
        entries = entries + entries
    entries = entries[:count]

    boundary = "----labelcheckbatch"
    parts: list[bytes] = []
    header = (
        "application_id,image,beverage_type,brand_name,class_type,"
        "alcohol_content,net_contents,bottler_address,country_of_origin\n"
    )
    rows = [header]
    seen: dict[str, int] = {}
    for index, entry in enumerate(entries, start=1):
        seen[entry["image"]] = seen.get(entry["image"], 0) + 1
        name = entry["image"]
        application = entry["application"]
        rows.append(
            ",".join(
                [
                    f"APP-{index:05d}",
                    name,
                    entry["beverage_type"],
                    *[
                        '"' + (application.get(key) or "").replace('"', '""') + '"'
                        for key in (
                            "brand_name",
                            "class_type",
                            "alcohol_content",
                            "net_contents",
                            "bottler_address",
                            "country_of_origin",
                        )
                    ],
                ]
            )
            + "\n"
        )

    for name in sorted({entry["image"] for entry in entries}):
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="images"; '
            f'filename="{name}"\r\nContent-Type: image/png\r\n\r\n'.encode()
        )
        parts.append((IMAGES / name).read_bytes())
        parts.append(b"\r\n")
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="manifest"; '
        f'filename="manifest.csv"\r\nContent-Type: text/csv\r\n\r\n'.encode()
    )
    parts.append("".join(rows).encode())
    parts.append(f"\r\n--{boundary}--\r\n".encode())

    request = urllib.request.Request(
        f"{base}/api/batch",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=300) as response:
        job = json.loads(response.read())

    print(f"Target      {base}")
    print(f"Matched     {job['matched_count']} of {job['row_count']} rows")

    last = -1
    while True:
        with urllib.request.urlopen(f"{base}/api/batch/{job['job_id']}", timeout=60) as response:
            progress = json.loads(response.read())
        if progress["done"] != last:
            print(
                f"  {progress['done']:>4} of {progress['total']} checked "
                f"({progress['elapsed_seconds']:.0f}s elapsed)"
            )
            last = progress["done"]
        if progress["state"] in ("finished", "stopped"):
            break
        time.sleep(2)

    wall = time.perf_counter() - started
    print()
    print(f"Completed   {progress['done']} of {progress['total']} in {wall:.0f}s")
    print(f"Throughput  {progress['done'] / wall * 60:.1f} labels per minute")
    print(f"Counts      {progress['counts']}")


def accuracy(base: str) -> None:
    """End-to-end accuracy: real OCR, real extraction, real verdicts.

    The offline suite holds OCR and extraction perfect so a wrong verdict is
    attributable to a rule. This one measures what an agent would actually get,
    and the README publishes both rather than letting the flattering figure
    stand for the product.
    """
    payload = json.loads(EXPECTED.read_text(encoding="utf-8"))
    entries = [
        entry
        for entry in payload["labels"]
        if entry["tier"] <= 5 and entry["scored"] and entry["expected_overall"] != "unreadable"
    ]

    scored = 0
    wrong: list[str] = []
    unreadable: list[str] = []

    def check(entry: dict) -> tuple[dict, dict | None]:
        image = (IMAGES / entry["image"]).read_bytes()
        fields = {
            "beverage_type": entry["beverage_type"],
            "application_id": entry["id"],
            **{k: v for k, v in entry["application"].items() if v},
        }
        body, content_type = _multipart(fields, entry["image"], image)
        request = urllib.request.Request(
            f"{base}/api/verify", data=body, headers={"Content-Type": content_type}
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    return entry, json.loads(response.read())
            except Exception:
                if attempt == 2:
                    return entry, None
                time.sleep(2 * (attempt + 1))
        return entry, None

    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for entry, result in pool.map(check, entries):
            if result is None:
                failed.append(entry["id"])
                continue
            if result["overall"] == "unreadable":
                unreadable.append(entry["id"])
                continue
            actual = {field["field"]: field["verdict"] for field in result["fields"]}
            for name, expected in entry["expected_fields"].items():
                if name not in actual:
                    continue
                scored += 1
                if actual[name] != expected:
                    wrong.append(f"{entry['id']}.{name}: expected {expected}, got {actual[name]}")

    print(f"Target      {base}")
    print(f"Labels      {len(entries)} scored, {len(unreadable)} came back unreadable")
    print(f"Verdicts    {scored}")
    print(f"Requests    {len(failed)} could not be completed: {failed}" if failed else "")
    print(f"Accuracy    {(scored - len(wrong)) / scored:.1%}" if scored else "no verdicts")
    for line in wrong:
        print(f"  wrong: {line}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--batch", type=int, default=0)
    parser.add_argument("--accuracy", action="store_true")
    args = parser.parse_args()

    print(f"Measured    {time.strftime('%Y-%m-%d %H:%M')}")
    if args.accuracy:
        accuracy(args.base)
    elif args.batch:
        batch(args.base, args.batch)
    else:
        single(args.base, args.count, args.concurrency)


if __name__ == "__main__":
    main()
