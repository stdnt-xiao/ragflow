import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rag.nlp import annotate_numbers


DOC_ID = "doc_abc123"


def _tag(page, left, right, top, bottom):
    """Helper: build a PDF position tag as appears in chunk text."""
    return f"@@{page}\t{left}\t{right}\t{top}\t{bottom}##"


def _loc(page, left, top, right, bottom, doc_id=DOC_ID):
    """Helper: expected paragraph_location annotation string (new format with doc_id)."""
    return f"{{paragraph_location: doc_id={doc_id}, page={page}, x0={left}, y0={top}, x1={right}, y1={bottom}}}"


class TestAnnotateNumbers:

    def test_single_number_in_one_section(self):
        text = _tag(3, 100, 450, 200, 350) + "功率为 750 kW。"
        result = annotate_numbers(text, doc_id=DOC_ID)
        expected_loc = _loc(3, 100, 200, 450, 350)
        assert _tag(3, 100, 450, 200, 350) in result
        assert "750 kW" + expected_loc in result

    def test_pure_number_no_unit(self):
        text = _tag(1, 0, 200, 0, 100) + "数量为 42。"
        result = annotate_numbers(text, doc_id=DOC_ID)
        assert "42" + _loc(1, 0, 0, 200, 100) in result

    def test_decimal_number(self):
        text = _tag(2, 50, 400, 100, 250) + "功率因数 0.85"
        result = annotate_numbers(text, doc_id=DOC_ID)
        assert "0.85" + _loc(2, 50, 100, 400, 250) in result

    def test_multiple_numbers_same_section(self):
        text = _tag(3, 100, 450, 200, 350) + "电压 380 V，电流 20 A。"
        result = annotate_numbers(text, doc_id=DOC_ID)
        loc = _loc(3, 100, 200, 450, 350)
        assert "380 V" + loc in result
        assert "20 A" + loc in result

    def test_multiple_sections_different_coords(self):
        # naive_merge format: text THEN tag (tag follows its own section)
        tag1 = _tag(3, 100, 450, 200, 350)
        tag2 = _tag(3, 100, 450, 350, 500)
        text = "功率 750 kW" + tag1 + "电压 380 V" + tag2
        result = annotate_numbers(text, doc_id=DOC_ID)
        loc1 = _loc(3, 100, 200, 450, 350)
        loc2 = _loc(3, 100, 350, 450, 500)
        # look-ahead: each segment gets the coords of the tag that immediately follows it
        assert "750 kW" + loc1 in result
        assert "380 V" + loc2 in result

    def test_no_position_tags_returns_unchanged(self):
        text = "没有位置标签，数字 123 不应被标注。"
        result = annotate_numbers(text, doc_id=DOC_ID)
        assert result == text

    def test_text_before_tag_annotated_with_that_tags_coords(self):
        # naive_merge format: "sec1_text@@tag1##sec2_text"
        # look-ahead: text before a tag gets THAT tag's coordinates (the tag is its bounding box)
        text = "前缀文本 99" + _tag(1, 0, 100, 0, 50) + "后续 50 kW"
        result = annotate_numbers(text, doc_id=DOC_ID)
        loc = _loc(1, 0, 0, 100, 50)
        assert "99" + loc in result        # sec1 gets tag1's coords ✓
        assert "50 kW" + loc in result     # sec2 (after last tag) also gets tag1's coords ✓

    def test_percentage(self):
        text = _tag(1, 0, 300, 0, 100) + "效率 95%"
        result = annotate_numbers(text, doc_id=DOC_ID)
        assert "95%" + _loc(1, 0, 0, 300, 100) in result

    def test_empty_text_after_tag(self):
        text = _tag(1, 0, 100, 0, 50) + ""
        result = annotate_numbers(text, doc_id=DOC_ID)
        assert _tag(1, 0, 100, 0, 50) in result

    def test_doc_id_in_tag(self):
        """doc_id appears as first field in the annotation."""
        text = _tag(1, 0, 200, 0, 100) + "42"
        result = annotate_numbers(text, doc_id=DOC_ID)
        assert f"{{paragraph_location: doc_id={DOC_ID}," in result

    def test_empty_doc_id(self):
        """When doc_id is empty string, field is still written."""
        text = _tag(1, 0, 200, 0, 100) + "42"
        result = annotate_numbers(text, doc_id="")
        assert "{paragraph_location: doc_id=," in result
