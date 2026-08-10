"""The extraction request carries what it must, explicitly.

Two parameters on this call have defaults that would change behaviour silently
if omitted, and both have cost this project measurable accuracy or latency.
"""

from __future__ import annotations

from app.extraction.client import EXTRACTION_TEMPERATURE, _request_kwargs


class TestRequestParameters:
    def test_thinking_is_always_explicit_on_a_model_that_supports_it(self) -> None:
        # On Opus 5 the default is ON; on the previous generation it was OFF.
        # An omitted parameter inherits a default that has already changed once.
        kwargs = _request_kwargs("claude-opus-5", "disabled", "low")
        assert kwargs["thinking"] == {"type": "disabled"}

    def test_thinking_is_omitted_only_where_the_model_rejects_it(self) -> None:
        kwargs = _request_kwargs("claude-haiku-4-5", "disabled", "low")
        assert "thinking" not in kwargs

    def test_temperature_is_pinned_to_zero(self) -> None:
        # A compliance tool that returns two different verdicts for the same
        # label on two runs cannot be defended.
        for model in ("claude-haiku-4-5", "claude-opus-5"):
            assert _request_kwargs(model, "disabled", "low")["temperature"] == 0.0
        assert EXTRACTION_TEMPERATURE == 0.0

    def test_effort_is_sent_only_where_the_model_accepts_it(self) -> None:
        assert (
            "effort" not in _request_kwargs("claude-haiku-4-5", "disabled", "low")["output_config"]
        )
        assert (
            _request_kwargs("claude-opus-5", "disabled", "low")["output_config"]["effort"] == "low"
        )
