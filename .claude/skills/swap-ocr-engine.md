# Implement or switch an OCR engine

## When to use

Switching engines for local work, adding the on-prem adapter, or evaluating an alternative provider.

## The interface

```python
class OcrEngine(Protocol):
    def extract(self, image: bytes) -> OcrResult: ...
```

`OcrResult` carries text plus bounding boxes. **The boxes are not optional** — they produce the evidence crops (FR-13) and the proportional size check on the warning. An adapter that returns text alone cannot support the product.

## Adapters

| Adapter | `OCR_ENGINE` | Role |
|---|---|---|
| `CloudVisionEngine` | `cloud` | Default. Fast, strong on stylized type |
| `PaddleOcrEngine` | `paddle` | **Not written.** The on-prem answer to C-3; selecting it raises |
| `FakeOcrEngine` | `fake` | One built-in sample label for every image. Default in tests |

Switch with an env var:

```bash
OCR_ENGINE=fake uv run uvicorn app.main:app --reload    # no Cloud Vision account needed
OCR_ENGINE=cloud uv run uvicorn app.main:app --reload
```

## Why this interface exists

TTB's network blocks outbound traffic to many domains (C-3). That does not affect our hosted prototype — the evaluator's browser talks to our server, and our server makes its own outbound calls — but it would matter for a deployment inside their network.

Rather than hobble the prototype defensively, the adapter makes the constraint an architecture decision: an on-prem OCR engine is one adapter behind this `Protocol` rather than a rewrite. The adapter itself is not written, and the README says so — claim the seam, not the engine.

## Adding an adapter

1. Implement `OcrEngine` in `api/app/ocr/<name>.py`.
2. Register it in the factory keyed by the `OCR_ENGINE` value.
3. Add a contract test that runs the **same assertions as every other adapter** — same fixture image, same expected fields. All adapters must satisfy one shared test suite; that is what makes them genuinely swappable.
4. Normalize coordinates to the shared `BoundingBox` type. Providers differ (absolute pixels vs normalized 0–1, different origin corners) — convert at the adapter boundary, never downstream.
5. Document the setup in the README.

## Common pitfalls

- **Leaking provider types past the boundary.** If `rules/` or `evidence/` imports anything from a specific provider SDK, the abstraction is broken.
- **Different coordinate systems.** The most common source of crops that are subtly offset or vertically mirrored. Test the crop, don't just test the text.
- **Forgetting `FakeOcrEngine` when adding a field.** Tests silently drop the new field and pass for the wrong reason.
- **Building PaddleOCR outside the container.** Its native dependencies are why the API is containerized; expect a local install to be painful.
