"""Structured schema for fields extracted from a label.

`extra="forbid"` makes Pydantic emit `additionalProperties: false`, which
structured outputs requires. Every field is nullable and required — the model
must report a field as absent rather than omitting the key, so "missing from
the label" is a value we can reason about instead of a gap in the payload.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExtractedFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brand_name: str | None = Field(description="Brand name as printed on the label")
    class_type: str | None = Field(
        description="Class or type designation, e.g. 'Kentucky Straight Bourbon Whiskey'"
    )
    alcohol_content: str | None = Field(
        description="Alcohol content exactly as printed, e.g. '45% Alc./Vol. (90 Proof)'"
    )
    net_contents: str | None = Field(description="Net contents as printed, e.g. '750 mL'")
    bottler_address: str | None = Field(
        description="Name and address of the bottler, producer, or importer"
    )
    country_of_origin: str | None = Field(
        description="Country of origin if stated, otherwise null"
    )
    government_warning: str | None = Field(
        description=(
            "The full government health warning text exactly as printed, including "
            "the 'GOVERNMENT WARNING:' prefix. Transcribe character for character; "
            "do not correct spelling, punctuation, or capitalisation. Null if absent."
        )
    )

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        """JSON schema in the shape structured outputs expects."""
        return cls.model_json_schema()
