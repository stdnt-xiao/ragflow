# MinerU 精确索引兼容 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 MinerU 默认解析模式（"raw"）下精确索引（`precise_index`）失效的问题，使 `annotate_numbers()` 能在 MinerU chunk 文本中找到位置标签并注入 `{paragraph_location: …}`。

**Architecture:** 在 `_transfer_to_sections()` 的 "raw" 分支，将位置标签（`@@page\tx0\tx1\ty0\ty1##`）拼入 section 文本，与 "paper" 模式对齐。其余处理链（`naive_merge` → `tokenize_chunks` → `annotate_numbers` → `remove_tag`）无需改动。

**Tech Stack:** Python 3.12, pytest

---

### Task 1: 为 `_transfer_to_sections` 写失败测试

**Files:**
- Create: `test/unit_test/deepdoc/parser/test_mineru_transfer_to_sections.py`

- [ ] **Step 1: 创建测试目录及 `__init__.py`**

```bash
mkdir -p /Users/xiaojian/code/ragflow/test/unit_test/deepdoc/parser
touch /Users/xiaojian/code/ragflow/test/unit_test/deepdoc/parser/__init__.py
touch /Users/xiaojian/code/ragflow/test/unit_test/deepdoc/__init__.py
```

- [ ] **Step 2: 写测试文件**

新建 `test/unit_test/deepdoc/parser/test_mineru_transfer_to_sections.py`：

```python
"""
Tests for MinerUParser._transfer_to_sections — position tag embedding in "raw" mode.

Isolated: no GPU, no MinerU binary needed.
We instantiate only the methods under test via object.__new__().
"""
import re
import sys
from unittest.mock import MagicMock

# ── Mock heavy deps so the module can be imported without GPU/CUDA ──────────
for _m in [
    "torch", "transformers", "magic_pdf", "magic_pdf.data",
    "magic_pdf.data.data_reader_writer", "magic_pdf.pipe",
    "magic_pdf.pipe.UNIPipe", "magic_pdf.model", "magic_pdf.libs",
]:
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

from deepdoc.parser.mineru_parser import MinerUParser, MinerUContentType  # noqa: E402

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
```

- [ ] **Step 3: 运行测试，确认失败**

```bash
cd /Users/xiaojian/code/ragflow
uv run pytest test/unit_test/deepdoc/parser/test_mineru_transfer_to_sections.py -v 2>&1 | tail -20
```

期望输出：`FAILED … AssertionError: position tag @@…## must be embedded in section text for raw mode`

- [ ] **Step 4: Commit 测试**

```bash
git add test/unit_test/deepdoc/parser/
git commit -m "test: add failing tests for MinerU raw mode position tag embedding"
```

---

### Task 2: 实现修复

**Files:**
- Modify: `deepdoc/parser/mineru_parser.py:580-585`

- [ ] **Step 1: 修改 `_transfer_to_sections` 的 "raw" 分支**

定位 `deepdoc/parser/mineru_parser.py` 第 580-585 行：

```python
# 修改前（第 585 行）
            else:
                sections.append((section, self._line_tag(output)))
```

改为：

```python
# 修改后
            else:
                tag = self._line_tag(output)
                sections.append((section + tag, tag))
```

完整上下文（第 580-586 行修改后）：

```python
            if section and parse_method in {"manual", "pipeline"}:
                sections.append((section, output["type"], self._line_tag(output)))
            elif section and parse_method == "paper":
                sections.append((section + self._line_tag(output), output["type"]))
            else:
                tag = self._line_tag(output)
                sections.append((section + tag, tag))
        return sections
```

- [ ] **Step 2: 运行测试，确认通过**

```bash
cd /Users/xiaojian/code/ragflow
uv run pytest test/unit_test/deepdoc/parser/test_mineru_transfer_to_sections.py -v 2>&1 | tail -20
```

期望输出：所有测试 `PASSED`

- [ ] **Step 3: 运行全量单元测试，确认无回归**

```bash
cd /Users/xiaojian/code/ragflow
uv run pytest test/unit_test/ -v 2>&1 | tail -30
```

期望输出：所有测试通过，无新失败。

- [ ] **Step 4: Commit 修复**

```bash
git add deepdoc/parser/mineru_parser.py
git commit -m "fix: embed position tag in MinerU raw mode sections for precise_index support"
```
