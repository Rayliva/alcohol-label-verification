"""Field identification: OCR text (or an image) -> structured fields.

Two paths:

  extract_from_text   the hot path. The model sees text, never pixels.
  extract_from_image  the escalation path for degraded images.

`thinking` is always passed explicitly. On Opus 5 the default is ON; on the
previous generation it was OFF. A call site that omits it inherits a default
that has already changed once, silently, at the cost of seconds.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import anthropic

from app.config import settings
from app.extraction.schema import ExtractedFields

SYSTEM_PROMPT = """\
You extract label information for TTB alcohol beverage label compliance review.

You are given the text read from a label by OCR. Return the requested fields \
exactly as they appear on the label.

Rules:
- Transcribe verbatim. Do not correct spelling, punctuation, capitalisation, \
or spacing. A label that reads "Government Warning" in title case must be \
returned in title case; a label reading "GOVERNMENT WARNING" must be returned \
in capitals. Downstream compliance checks depend on the exact characters.
- If a field does not appear on the label, return null. Never guess, infer, or \
supply a value from general knowledge about the brand.
- The government warning must be transcribed in full, including its numbered \
clauses, exactly as printed.
- OCR output may contain artefacts and odd line breaks. Reconstruct the reading \
order, but never invent characters that are not present.
"""


@dataclass
class ExtractionResult:
    fields: ExtractedFields
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    model: str


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.require_anthropic_key())


# Model generations expose different request surfaces. Haiku 4.5 predates the
# effort parameter and adaptive thinking, and rejects both with a 400. Encode
# the difference here rather than at each call site.
def _supports_effort(model: str) -> bool:
    return not model.startswith("claude-haiku")


def _supports_adaptive_thinking(model: str) -> bool:
    return not model.startswith("claude-haiku")


def _output_config(model: str, effort: str) -> dict[str, Any]:
    config: dict[str, Any] = {
        "format": {"type": "json_schema", "schema": ExtractedFields.json_schema()}
    }
    if _supports_effort(model):
        config["effort"] = effort
    return config


def _thinking(model: str, mode: str) -> dict[str, Any] | None:
    """Explicit thinking configuration, or None to omit the parameter.

    Never omit on a model that supports adaptive thinking: on Opus 5 the
    default is ON and on the previous generation it was OFF, so an omitted
    parameter inherits a default that has already changed once.

    "disabled" is accepted only at effort "high" or below; pairing it with
    xhigh/max returns a 400. We never exceed "high".
    """
    if not _supports_adaptive_thinking(model):
        # Older generation: thinking off means omitting the parameter.
        return None
    return {"type": "disabled"} if mode == "disabled" else {"type": "adaptive"}


def _request_kwargs(model: str, thinking_mode: str, effort: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"output_config": _output_config(model, effort)}
    thinking = _thinking(model, thinking_mode)
    if thinking is not None:
        kwargs["thinking"] = thinking
    return kwargs


def _parse(response: Any, model: str, elapsed_ms: float) -> ExtractionResult:
    text = next(b.text for b in response.content if b.type == "text")
    usage = response.usage
    return ExtractionResult(
        fields=ExtractedFields.model_validate(json.loads(text)),
        latency_ms=elapsed_ms,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        model=model,
    )


def extract_from_text(
    ocr_text: str,
    *,
    model: str | None = None,
    thinking: Literal["disabled", "adaptive"] | None = None,
    effort: str | None = None,
    cache_system: bool = True,
) -> ExtractionResult:
    """Hot path: structured fields from OCR text."""
    model = model or settings.extraction_model
    thinking_mode = thinking or settings.extraction_thinking
    effort_level = effort or settings.extraction_effort

    system: list[dict[str, Any]] = [{"type": "text", "text": SYSTEM_PROMPT}]
    if cache_system:
        system[0]["cache_control"] = {"type": "ephemeral", "ttl": "1h"}

    started = time.perf_counter()
    response = _client().messages.create(
        model=model,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": f"Label text:\n\n{ocr_text}"}],
        **_request_kwargs(model, thinking_mode, effort_level),
    )
    return _parse(response, model, (time.perf_counter() - started) * 1000)


def extract_from_image(
    image_path: Path,
    *,
    model: str | None = None,
    thinking: Literal["disabled", "adaptive"] | None = None,
    effort: str | None = None,
) -> ExtractionResult:
    """Escalation path: structured fields straight from the image."""
    model = model or settings.vision_fallback_model
    thinking_mode = thinking or settings.extraction_thinking
    effort_level = effort or settings.extraction_effort

    data = base64.standard_b64encode(image_path.read_bytes()).decode()
    started = time.perf_counter()
    response = _client().messages.create(
        model=model,
        max_tokens=2048,
        system=[{"type": "text", "text": SYSTEM_PROMPT}],
        **_request_kwargs(model, thinking_mode, effort_level),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": data,
                        },
                    },
                    {"type": "text", "text": "Extract the label fields."},
                ],
            }
        ],
    )
    return _parse(response, model, (time.perf_counter() - started) * 1000)
