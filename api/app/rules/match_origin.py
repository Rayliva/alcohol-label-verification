"""Compare a country of origin, ignoring how the statement is phrased.

Verify country of origin per 27 CFR 5.69.

The regulation requires the country to appear on the label. It does not
prescribe one wording, so applications write "PRODUCT OF ENGLAND" where the
label prints "ENGLAND", or the reverse. Comparing those as plain text fails a
compliant imported label over a convention — a false FAIL, which is the error
class this tool can least afford: it sends an agent to reject an application
that was fine, and teaches them the tool costs more time than it saves.

Only the preamble is forgiven. The country itself is compared by the ordinary
text matcher, so every other difference is judged exactly as it is elsewhere.
"""

from __future__ import annotations

import re
from dataclasses import replace

from app.rules.match_text import match_text
from app.rules.types import FieldResult

# The conventional openings. Deliberately a closed list: anything not named
# here is treated as part of the country and compared, rather than silently
# discarded.
_PREAMBLE = re.compile(
    r"^(?:a\s+)?"
    r"(?:product\s+of|produce\s+of|produced\s+in|distilled\s+in|made\s+in"
    r"|imported\s+from|bottled\s+in)\b[\s:,-]*",
    re.IGNORECASE,
)


def _without_preamble(value: str | None) -> str | None:
    """Drop a leading "product of"-style phrase, unless it is the whole value.

    "PRODUCT OF" on its own names no country. Reducing it to an empty string
    would let two such values match each other, inventing an agreement about a
    country neither one states.
    """
    if not value:
        return value
    stripped = _PREAMBLE.sub("", value).strip()
    return stripped or value


def match_origin(field: str, *, declared: str | None, detected: str | None) -> FieldResult:
    """Verify country of origin per 27 CFR 5.69."""
    result = match_text(
        field,
        declared=_without_preamble(declared),
        detected=_without_preamble(detected),
    )
    # The agent is shown what the application and the label actually say, not
    # the trimmed forms used for the comparison.
    return replace(result, declared=declared, detected=detected)
