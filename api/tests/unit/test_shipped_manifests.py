"""The batch spreadsheets we ship match the images they sit beside.

Both exist so an agent can run a batch test by selecting a folder's images
and the CSV in the same folder. A row that names a missing image, or an
image no row claims, is exactly the "nothing is matching" report this test
exists to prevent.
"""

from __future__ import annotations

import pathlib

import pytest

from app.batch.manifest import parse, preflight

REPO = pathlib.Path(__file__).resolve().parents[3]

SHIPPED = [
    REPO / "api" / "app" / "samples" / "batch-manifest.csv",
    REPO / "samples" / "batch" / "batch-manifest.csv",
]


@pytest.mark.parametrize("csv_path", SHIPPED, ids=lambda p: str(p.parent.relative_to(REPO)))
def test_every_row_matches_an_image_beside_it(csv_path: pathlib.Path) -> None:
    rows = parse(csv_path.read_bytes(), csv_path.name)
    images = [p.name for p in csv_path.parent.glob("*.jpg")]
    report = preflight(rows, images)
    assert report.problems == (), [p.detail for p in report.problems]
    assert len(report.matched) == len(rows) == len(images)
    assert report.ready
