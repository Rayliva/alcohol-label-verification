"""Strip differences that carry no meaning.

Step one of fuzzy matching. This stage is deterministic and does all the
heavy lifting: most real-world mismatches — case, curly quotes, doubled
spaces, a trailing period — disappear here, before any similarity score is
computed. Scoring only sees what genuinely differs.

Never use this on the government warning beyond whitespace. That check is
character-exact by statute (27 CFR 16.21), and folding case here would pass
the title-case violation this product exists to catch.
"""

from __future__ import annotations

import re
import unicodedata

# Typographic variants that mean the same thing as their ASCII equivalent.
_CHAR_SUBSTITUTIONS = {
    "‘": "'",  # left single quote
    "’": "'",  # right single quote / apostrophe
    "‚": "'",
    "‛": "'",
    "“": '"',  # left double quote
    "”": '"',  # right double quote
    "„": '"',
    "–": "-",  # en dash
    "—": "-",  # em dash
    "―": "-",  # horizontal bar
    "−": "-",  # minus sign
    "…": "...",  # ellipsis
}

# Dropped only from the end of the string. Interior punctuation is preserved:
# "A.B.C. Distillery" must not collapse into something matching "ABCD istillery".
_TRAILING_PUNCTUATION = ".,;:!?-·"

_WHITESPACE = re.compile(r"\s+")


def normalize(value: str | None) -> str:
    """Return `value` with meaningless formatting differences removed.

    >>> normalize("STONE'S THROW") == normalize("Stone's Throw")
    True
    >>> normalize("Old Tom") == normalize("New Tom")
    False
    """
    if not value:
        return ""

    # NFKD splits accented characters into base + combining mark, and folds
    # compatibility forms such as the non-breaking space into plain ASCII.
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))

    for source, replacement in _CHAR_SUBSTITUTIONS.items():
        text = text.replace(source, replacement)

    text = text.casefold()
    text = _WHITESPACE.sub(" ", text).strip()
    text = text.rstrip(_TRAILING_PUNCTUATION).strip()

    return text


def normalize_whitespace_only(value: str | None) -> str:
    """Collapse whitespace and trim. Nothing else.

    The government warning comparison uses this: a line break on the artwork
    is a layout artefact, but a changed word or a lowercased letter is a
    violation. See app/rules/warning.py.
    """
    if not value:
        return ""
    return _WHITESPACE.sub(" ", value).strip()
