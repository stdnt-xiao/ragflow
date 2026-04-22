"""
Tests for MinerUParser._transfer_to_sections — position tag embedding in "raw" mode.

Isolated: no GPU, no MinerU binary needed.
We instantiate only the methods under test via object.__new__().
"""
import re

from deepdoc.parser.mineru_parser import MinerUParser, MinerUContentType

POS_TAG_RE = re.compile(r"@@[\d-]+\t[\d.]+\t[\d.]+\t[\d.]+\t[\d.]+##")


def _make_parser() -> MinerUParser:
    """Return a bare parser instance without calling __init__."""
    return object.__new__(MinerUParser)


def _text_output(text="hello", page=1, bbox=(10.0, 20.0, 200.0, 40.0)):
    """Minimal MinerU content-list block for a text element."""
    return {
        "type": MinerUContentType.TEXT,
        "text": text,
        "page_idx": page - 1,        # 0-based in MinerU output
        "bbox": list(bbox),           # [x0, top, x1, bottom] in 0-1000 range
        "page_size": [1000, 1000],    # width, height — used by _line_tag
    }


class TestTransferToSectionsRawMode:
    """parse_method="raw" (default) — position tag must be embedded in text."""

    def test_section_contains_position_tag(self):
        parser = _make_parser()
        outputs = [_text_output("Some value 42")]
        sections = parser._transfer_to_sections(outputs, parse_method="raw")

        assert len(sections) == 1
        sec_text, _ = sections[0]
        assert POS_TAG_RE.search(sec_text), (
            "position tag @@…## must be embedded in section text for raw mode"
        )

    def test_returns_2_tuple(self):
        parser = _make_parser()
        outputs = [_text_output()]
        sections = parser._transfer_to_sections(outputs, parse_method="raw")

        assert len(sections) == 1
        assert len(sections[0]) == 2, "raw mode must return 2-tuple (text, tag)"

    def test_multiple_blocks_all_have_tags(self):
        parser = _make_parser()
        outputs = [_text_output(f"block {i}", page=i + 1) for i in range(3)]
        sections = parser._transfer_to_sections(outputs, parse_method="raw")

        assert len(sections) == 3
        for i, (sec_text, _) in enumerate(sections):
            assert POS_TAG_RE.search(sec_text), (
                f"block {i} missing position tag in text"
            )


class TestTransferToSectionsPaperMode:
    """parse_method="paper" — already working, must stay unchanged."""

    def test_section_contains_position_tag(self):
        parser = _make_parser()
        outputs = [_text_output("Some value 42")]
        sections = parser._transfer_to_sections(outputs, parse_method="paper")

        assert len(sections) == 1
        sec_text, _ = sections[0]
        assert POS_TAG_RE.search(sec_text)
