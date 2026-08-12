"""Which OCR block a detected value is attributed to.

The evidence crop is the product's answer to "did we misread it?", so the
block behind it has to be the place the value actually sits. Audit finding C3
recorded two ways it could be the wrong place; the 006 sample made one of them
visible: the brand crop showed the bottler line.
"""

from __future__ import annotations

from app.ocr.base import BoundingBox, OcrResult, TextBlock
from app.pipeline.measure import find_block

pytestmark = []


def block(text: str, x: int, y: int, width: int = 400, height: int = 40) -> TextBlock:
    return TextBlock(
        text=text,
        box=BoundingBox(x=x, y=y, width=width, height=height),
        confidence=0.96,
    )


def ocr(*blocks: TextBlock) -> OcrResult:
    return OcrResult(
        full_text="\n".join(b.text for b in blocks),
        blocks=blocks,
        image_width=1400,
        image_height=2000,
        engine="test",
        latency_ms=0.0,
    )


class TestTitleSplitAcrossBlocks:
    """The 006 sample: a two-line title loses its crop to the bottler line.

    OCR returns the big brand as two blocks, "OLD TOM" and "DISTILLERY", so no
    single block contains the full phrase except the bottler line, which
    mentions the distillery by name. The blocks that together ARE the value
    must beat a line that merely contains it.
    """

    def test_the_title_blocks_beat_a_line_that_mentions_the_brand(self) -> None:
        result = ocr(
            block("OLD TOM", 300, 100),
            block("DISTILLERY", 300, 150),
            block("DISTILLED AND BOTTLED BY OLD TOM DISTILLERY, BARDSTOWN, KENTUCKY", 100, 900),
        )

        found = find_block(result, "OLD TOM DISTILLERY")

        assert found is not None
        # The merged title region sits at the top of the label; the bottler
        # line sits at the bottom. The crop must show the title.
        assert found.box.y == 100
        assert found.box.bottom == 190

    def test_a_line_break_swallowed_by_ocr_still_matches(self) -> None:
        # Cloud Vision joins wrapped lines without a space: the two-line title
        # comes back as one block reading "OLD TOMDISTILLERY". Matching on
        # space-collapsed text could never find it, and the brand's evidence
        # crop fell through to the bottler line, which mentions the name.
        title = block("OLD TOMDISTILLERY", 300, 100)
        result = ocr(
            title,
            block("DISTILLED AND BOTTLED BY OLD TOM DISTILLERY, BARDSTOWN,KENTUCKY", 100, 900),
        )

        assert find_block(result, "OLD TOM DISTILLERY") is title

    def test_an_exact_block_still_wins_outright(self) -> None:
        result = ocr(
            block("OLD TOM DISTILLERY", 300, 100),
            block("DISTILLED AND BOTTLED BY OLD TOM DISTILLERY, BARDSTOWN, KENTUCKY", 100, 900),
        )

        found = find_block(result, "OLD TOM DISTILLERY")

        assert found is not None
        assert found.box.y == 100

    def test_two_values_printed_on_one_line_share_that_line(self) -> None:
        # "45% Alc./Vol. (90 Proof) . 750 mL" is one printed line, so it is the
        # honest evidence region for both fields. Sharing is not a defect.
        line = block("45% Alc./Vol. (90 Proof) . 750 mL", 300, 800)
        result = ocr(block("OLD TOM", 300, 100), line)

        assert find_block(result, "750 mL") is line
        assert find_block(result, "45% Alc./Vol. (90 Proof)") is line


class TestReconstructionIsNotFragile:
    def test_a_stray_fragment_does_not_defeat_the_merge(self) -> None:
        # A junk OCR fragment whose squashed text happens to sit inside the
        # needle ("TOMD") must not veto the reconstruction from the real title
        # blocks. Review finding, 2026-08-11.
        result = ocr(
            block("OLD TOM", 300, 100),
            block("DISTILLERY", 300, 150),
            block("TOMD", 900, 1200, width=60),
            block("DISTILLED AND BOTTLED BY OLD TOM DISTILLERY, BARDSTOWN", 100, 900),
        )

        found = find_block(result, "OLD TOM DISTILLERY")

        assert found is not None
        assert found.box.y == 100
        assert found.box.bottom == 190

    def test_an_exact_block_beats_a_shorter_containing_block(self) -> None:
        # Exactness is checked across every candidate, not only the shortest:
        # a block whose raw text is shorter only because it carries no spaces
        # must not shadow the block that IS the value.
        exact = block("OLD  TOM \nDISTILLERY ", 300, 100)
        result = ocr(block("OLDTOMDISTILLERY.", 100, 900), exact)

        assert find_block(result, "OLD TOM DISTILLERY") is exact


class TestLastResortFallback:
    """C3: half the words was too loose a bar for a claim about evidence."""

    def test_one_shared_word_of_two_is_not_evidence(self) -> None:
        # "TABLE WINE" against a block mentioning a table of contents: one word
        # of two matched, and the crop was an unrelated line presented as the
        # place the value came from.
        result = ocr(block("SEE THE TABLE ON THE BACK", 100, 500))

        assert find_block(result, "TABLE WINE") is None

    def test_most_words_in_one_block_is_still_evidence(self) -> None:
        # OCR mangling one word out of several must not cost the crop: the
        # block genuinely is where the value sits.
        target = block("DISTILLED AND B0TTLED BY OLD TOM", 100, 500)
        result = ocr(block("OLD TOM", 300, 100, width=120), target)

        assert find_block(result, "DISTILLED AND BOTTLED BY OLD TOM") is target
