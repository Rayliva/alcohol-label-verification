# Error handling

Failures name their cause. Silent failures are asserted against at boot.

## The rule

1. **No generic failure reaches a user.** Every error surfaced in the UI says what went wrong and what to do about it.
2. **Unreadable images report why** — glare, blur, resolution, cropping, angle — not "processing failed" (FR-15).
3. **Assert silent assumptions at startup.** Where a misconfiguration would degrade behavior without erroring, check it at boot and fail loudly.
4. **Catch specific exceptions.** Never a bare `except:`; never a single broad handler that flattens retryable and permanent failures together.
5. **Errors crossing the API boundary are typed** — a Pydantic error model with a machine-readable code and a human-readable message, not a bare 500.

## Why

Two reasons, both from the brief. An agent who gets "processing failed" learns nothing and rejects the label — the tool has made their job slower, which is precisely Dave's objection. And several failure modes in this stack are *silent*: an undersized prompt stops caching with no error, an omitted `thinking` parameter costs seconds with no error, a missing system library only surfaces at deploy. Assertions convert those into loud, early failures.

## Examples

**Do** — name the cause and the remedy:

```python
raise UnreadableImageError(
    code="glare_obscures_text",
    message="Glare covers the lower third of the label. "
            "Re-photograph without direct light on the bottle.",
)
```

**Do** — assert at boot:

```python
if response.usage.cache_read_input_tokens == 0:
    raise StartupError(
        f"Prompt cache not engaging for {settings.extraction_model}. "
        f"System prompt is likely below the model's minimum cacheable prefix."
    )
```

**Don't:**

```python
try:
    result = pipeline.run(image)
except Exception:
    return {"error": "Could not process label"}
```

Three failures at once: bare catch, generic message, no code.

**Don't** — return `NEEDS_REVIEW` as a disguise for a crash. A verdict means the check ran. If it didn't, that is an error, and conflating the two silently degrades every accuracy number we publish.
