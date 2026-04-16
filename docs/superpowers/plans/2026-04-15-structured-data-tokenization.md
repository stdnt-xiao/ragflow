# Structured Data Tokenization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让分词器将带单位数字、中文日期、货币金额、百分比、版本号等结构化数据识别为单个 token，而非拆散。

**Architecture:** 在 `RagTokenizer.tokenize()` 和 `fine_grained_tokenize()` 调用父类之前，用纯字母数字占位符（`ragprot0000`）替换所有需要保护的模式；父类完成分词后再还原占位符为原始词。所有逻辑集中在 `rag/nlp/rag_tokenizer.py` 一个文件中。

**Tech Stack:** Python 3.12, `re`（标准库）, `infinity.rag_tokenizer`（父类）, pytest

---

## File Map

| 操作 | 路径 | 职责 |
|---|---|---|
| 修改 | `rag/nlp/rag_tokenizer.py` | 增加保护模式列表、`_protect_patterns()`、`_restore_patterns()`，覆盖两个分词方法 |
| 新建 | `test/unit_test/rag/nlp/test_structured_tokenization.py` | 全部单元测试 |
| 新建 | `test/unit_test/rag/nlp/conftest.py` | Mock `common.settings`，使测试无需服务依赖 |

---

## Task 1: 测试基础设施

**Files:**
- Create: `test/unit_test/rag/nlp/conftest.py`

- [ ] **Step 1: 创建测试目录和 conftest.py**

```bash
mkdir -p test/unit_test/rag/nlp
touch test/unit_test/rag/nlp/__init__.py
```

创建 `test/unit_test/rag/nlp/conftest.py`：

```python
#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

"""
Mock common.settings so rag_tokenizer tests run without infrastructure.
"""

import sys
from unittest.mock import MagicMock

_modules_to_mock = [
    "common",
    "common.settings",
]

for mod_name in _modules_to_mock:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Default: use Elasticsearch engine (not Infinity), so tokenize() runs real logic
sys.modules["common.settings"].DOC_ENGINE_INFINITY = False
```

- [ ] **Step 2: 验证 conftest 能被 pytest 发现**

```bash
cd /path/to/ragflow
python -m pytest test/unit_test/rag/nlp/ --collect-only 2>&1 | head -20
```

预期：无报错，显示 `0 tests collected`（因为还没有测试文件）

- [ ] **Step 3: 提交**

```bash
git add test/unit_test/rag/nlp/
git commit -m "test: add conftest for rag/nlp tokenizer unit tests"
```

---

## Task 2: 为保护函数编写失败测试

**Files:**
- Create: `test/unit_test/rag/nlp/test_structured_tokenization.py`
- Reference: `rag/nlp/rag_tokenizer.py`（被测模块）

- [ ] **Step 1: 创建测试文件**

创建 `test/unit_test/rag/nlp/test_structured_tokenization.py`：

```python
#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

"""
Unit tests for structured data tokenization protection.

These tests verify that _protect_patterns() and _restore_patterns()
correctly identify and preserve structured data as single tokens.
"""

import pytest
from rag.nlp.rag_tokenizer import _protect_patterns, _restore_patterns


# ── _protect_patterns 基础行为 ─────────────────────────────────────────────────

class TestProtectPatterns:

    def test_returns_tuple_of_text_and_dict(self):
        text, protected = _protect_patterns("hello world")
        assert isinstance(text, str)
        assert isinstance(protected, dict)

    def test_plain_text_unchanged(self):
        text, protected = _protect_patterns("普通文本没有特殊数据")
        assert text == "普通文本没有特殊数据"
        assert protected == {}

    # ── 日期时间 ──────────────────────────────────────────────────────────────

    def test_full_datetime(self):
        text, protected = _protect_patterns("会议在2024年1月15日10时30分举行")
        assert "2024年1月15日10时30分" not in text
        assert len(protected) == 1
        assert "2024年1月15日10时30分" in protected.values()

    def test_full_date(self):
        text, protected = _protect_patterns("截止日期2024年12月31日")
        assert "2024年12月31日" not in text
        assert "2024年12月31日" in protected.values()

    def test_year_month(self):
        text, protected = _protect_patterns("2024年1月发布")
        assert "2024年1月" not in text
        assert "2024年1月" in protected.values()

    def test_month_day(self):
        text, protected = _protect_patterns("1月15日截止")
        assert "1月15日" not in text
        assert "1月15日" in protected.values()

    def test_hour_minute(self):
        text, protected = _protect_patterns("下午3时30分开始")
        assert "3时30分" not in text
        assert "3时30分" in protected.values()

    def test_hour_minute_second(self):
        text, protected = _protect_patterns("精确到10时30分20秒")
        assert "10时30分20秒" not in text
        assert "10时30分20秒" in protected.values()

    def test_iso_date_hyphen(self):
        text, protected = _protect_patterns("到期日2024-01-15")
        assert "2024-01-15" not in text
        assert "2024-01-15" in protected.values()

    def test_iso_date_slash(self):
        text, protected = _protect_patterns("到期日2024/01/15")
        assert "2024/01/15" not in text
        assert "2024/01/15" in protected.values()

    # ── 货币 ──────────────────────────────────────────────────────────────────

    def test_rmb_symbol(self):
        text, protected = _protect_patterns("售价¥1,280")
        assert "¥1,280" not in text
        assert "¥1,280" in protected.values()

    def test_dollar_symbol(self):
        text, protected = _protect_patterns("价格$50.00")
        assert "$50.00" not in text
        assert "$50.00" in protected.values()

    def test_euro_symbol(self):
        text, protected = _protect_patterns("费用€200")
        assert "€200" not in text
        assert "€200" in protected.values()

    # ── 数字+中文单位 ──────────────────────────────────────────────────────────

    def test_wan(self):
        text, protected = _protect_patterns("销售额3.5万元")
        assert "3.5万" not in text
        assert any("3.5万" in v for v in protected.values())

    def test_qianke(self):
        text, protected = _protect_patterns("重量50千克")
        assert "50千克" not in text
        assert "50千克" in protected.values()

    def test_gongli(self):
        text, protected = _protect_patterns("距离100公里")
        assert "100公里" not in text
        assert "100公里" in protected.values()

    def test_yi(self):
        text, protected = _protect_patterns("市值2亿")
        assert "2亿" not in text
        assert "2亿" in protected.values()

    # ── 数字+英文/SI单位 ──────────────────────────────────────────────────────

    def test_kg(self):
        text, protected = _protect_patterns("重量50kg")
        assert "50kg" not in text
        assert "50kg" in protected.values()

    def test_ghz(self):
        text, protected = _protect_patterns("频率3GHz")
        assert "3GHz" not in text
        assert "3GHz" in protected.values()

    def test_gb(self):
        text, protected = _protect_patterns("内存100GB")
        assert "100GB" not in text
        assert "100GB" in protected.values()

    def test_km(self):
        text, protected = _protect_patterns("距离50km")
        assert "50km" not in text
        assert "50km" in protected.values()

    # ── 百分比/千分比 ──────────────────────────────────────────────────────────

    def test_percent(self):
        text, protected = _protect_patterns("增长率3.5%")
        assert "3.5%" not in text
        assert "3.5%" in protected.values()

    def test_permille(self):
        text, protected = _protect_patterns("误差5‰")
        assert "5‰" not in text
        assert "5‰" in protected.values()

    # ── 温度 ──────────────────────────────────────────────────────────────────

    def test_celsius_symbol(self):
        text, protected = _protect_patterns("温度36.5°C")
        assert "36.5°C" not in text
        assert "36.5°C" in protected.values()

    def test_celsius_chinese(self):
        text, protected = _protect_patterns("零下10℃")
        assert "10℃" not in text
        assert "10℃" in protected.values()

    def test_negative_temperature(self):
        text, protected = _protect_patterns("气温-10℃")
        assert "-10℃" not in text
        assert "-10℃" in protected.values()

    # ── 版本号 ──────────────────────────────────────────────────────────────

    def test_version_lowercase(self):
        text, protected = _protect_patterns("版本v1.0.0已发布")
        assert "v1.0.0" not in text
        assert "v1.0.0" in protected.values()

    def test_version_uppercase(self):
        text, protected = _protect_patterns("版本V3.5已发布")
        assert "V3.5" not in text
        assert "V3.5" in protected.values()

    # ── 多模式共存 ────────────────────────────────────────────────────────────

    def test_multiple_patterns_in_one_sentence(self):
        text, protected = _protect_patterns("2024年1月售价¥100增长3.5%")
        assert "2024年1月" not in text
        assert "¥100" not in text
        assert "3.5%" not in text
        assert len(protected) == 3

    def test_placeholder_format(self):
        """占位符必须是纯小写字母+数字，能安全通过父类管道。"""
        import re
        text, protected = _protect_patterns("2024年1月售价¥100")
        for key in protected:
            assert re.match(r'^ragprot\d{4}$', key), f"Invalid placeholder format: {key}"


# ── _restore_patterns ─────────────────────────────────────────────────────────

class TestRestorePatterns:

    def test_restores_single_placeholder(self):
        protected = {"ragprot0000": "2024年1月"}
        result = _restore_patterns("发布时间 ragprot0000 已确认", protected)
        assert result == "发布时间 2024年1月 已确认"

    def test_restores_multiple_placeholders(self):
        protected = {
            "ragprot0000": "2024年1月",
            "ragprot0001": "¥100",
        }
        result = _restore_patterns("ragprot0000 售价 ragprot0001", protected)
        assert result == "2024年1月 售价 ¥100"

    def test_empty_protected_returns_text_unchanged(self):
        result = _restore_patterns("普通文本", {})
        assert result == "普通文本"

    def test_round_trip(self):
        """protect 后 restore 必须还原原始文本。"""
        original = "2024年1月温度-10℃售价¥1,280增长3.5%"
        modified, protected = _protect_patterns(original)
        restored = _restore_patterns(modified, protected)
        assert restored == original


# ── RagTokenizer.tokenize() 集成行为 ─────────────────────────────────────────

class TestRagTokenizerIntegration:
    """
    验证 tokenize() 输出中结构化数据作为单个 token 出现。
    注意：tokenize() 输出是空格分隔的 token 字符串。
    """

    @pytest.fixture(autouse=True)
    def tokenizer(self):
        from rag.nlp.rag_tokenizer import tokenizer as _tokenizer
        self.tokenizer = _tokenizer

    def _tokens(self, text: str) -> list[str]:
        return self.tokenizer.tokenize(text).split()

    def test_year_month_is_single_token(self):
        tokens = self._tokens("2024年1月发布")
        assert "2024年1月" in tokens

    def test_celsius_is_single_token(self):
        tokens = self._tokens("温度36.5°C")
        assert "36.5°C" in tokens

    def test_percent_is_single_token(self):
        tokens = self._tokens("增长率3.5%")
        assert "3.5%" in tokens

    def test_kg_is_single_token(self):
        tokens = self._tokens("重量50kg")
        assert "50kg" in tokens

    def test_version_is_single_token(self):
        tokens = self._tokens("版本v1.0.0")
        assert "v1.0.0" in tokens

    def test_plain_text_still_tokenizes(self):
        """普通中文文本不受影响，正常分词。"""
        tokens = self._tokens("人工智能技术")
        assert len(tokens) > 0
        # 不应返回整句作为单个 token
        assert "人工智能技术" not in tokens or len(tokens) > 1
```

- [ ] **Step 2: 运行测试，确认全部失败**

```bash
cd /path/to/ragflow
python -m pytest test/unit_test/rag/nlp/test_structured_tokenization.py -v 2>&1 | head -40
```

预期：`ImportError: cannot import name '_protect_patterns' from 'rag.nlp.rag_tokenizer'`（函数尚未实现）

- [ ] **Step 3: 提交测试文件**

```bash
git add test/unit_test/rag/nlp/test_structured_tokenization.py
git commit -m "test: add failing tests for structured data tokenization protection"
```

---

## Task 3: 实现保护模式列表和辅助函数

**Files:**
- Modify: `rag/nlp/rag_tokenizer.py`

- [ ] **Step 1: 替换 `rag/nlp/rag_tokenizer.py` 完整内容**

```python
#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import re
import infinity.rag_tokenizer

# ── Structured-data protection ────────────────────────────────────────────────
#
# Problem: the parent tokenizer pipeline destroys structured data like
# "2024年1月", "50kg", "36.5°C" by:
#   1. re.sub(r"\W+", " ", line)  — strips °, ¥, %, etc.
#   2. _split_by_lang()           — splits at Chinese/non-Chinese boundaries
#   3. NLTK word_tokenize()       — splits "50kg" → ["50", "kg"]
#
# Solution: before calling super().tokenize(), replace protected patterns with
# pure-alphanumeric placeholders (ragprot0000 … ragprot9999) that survive the
# entire pipeline unchanged, then restore them in the result string.
#
# Placeholder safety proof:
#   re.sub(r"\W+", " ", ...)  → all \w chars, unaffected          ✓
#   _strQ2B().lower()          → already lowercase, unchanged       ✓
#   _split_by_lang()           → non-Chinese, kept as one chunk     ✓
#   NLTK word_tokenize         → single word token                  ✓
#   Snowball stemmer            → digit suffix, no English rule hit  ✓

_PROTECT_PATTERNS: list[re.Pattern] = [
    # Priority 1: full datetime  2024年1月15日10时30分(20秒)
    re.compile(r'\d{4}年\d{1,2}月\d{1,2}日\d{1,2}时\d{1,2}分(?:\d{1,2}秒)?'),
    # Priority 2: full date  2024年1月15日
    re.compile(r'\d{4}年\d{1,2}月\d{1,2}日'),
    # Priority 3: year-month  2024年1月
    re.compile(r'\d{4}年\d{1,2}月'),
    # Priority 4: month-day  1月15日
    re.compile(r'\d{1,2}月\d{1,2}日'),
    # Priority 5: hour-minute(-second)  10时30分  /  10时30分20秒
    re.compile(r'\d{1,2}时\d{1,2}分(?:\d{1,2}秒)?'),
    # Priority 6: ISO / slash date  2024-01-15  2024/01/15
    re.compile(r'\d{4}[-/]\d{2}[-/]\d{2}'),
    # Priority 7: currency with prefix symbol  ¥100  $50.00  €200  £30  ₩500
    re.compile(r'[¥$€£₩]\d[\d,，]*(?:\.\d+)?'),
    # Priority 8: number + Chinese unit (longer units first to avoid partial match)
    re.compile(
        r'\d[\d,，]*(?:\.\d+)?'
        r'(?:万亿|十亿|亿万|千万|百万|十万|千克|公里|毫升|毫米|厘米|千米|平方米|立方米'
        r'|亿|万|千|百|元|角|斤|两|米|升|吨|克|度)'
    ),
    # Priority 9: number + multi-char SI/English unit (longer first)
    re.compile(
        r'\d[\d,，]*(?:\.\d+)?\s?'
        r'(?:GHz|MHz|kHz|kW|MW|GB|MB|KB|TB|PB|mL|ml|kg|mg|km|cm|mm|Hz|kV|mV|mA)'
        r'(?![a-zA-Z])'
    ),
    # Priority 9b: number + single-letter SI unit  50g  100W  5V  2A  10L
    re.compile(r'\d[\d,，]*(?:\.\d+)?\s?[gGwWvVaAL](?![a-zA-Z])'),
    # Priority 10: percentage / per-mille  3.5%  5‰
    re.compile(r'\d[\d,，]*(?:\.\d+)?[%‰]'),
    # Priority 11: temperature  36.5°C  -10℃  98.6°F  -10℉
    re.compile(r'[-−]?\d+(?:\.\d+)?(?:°[CF]|℃|℉)'),
    # Priority 12: version number  v1.0.0  V3.5
    re.compile(r'[vV]\d+(?:\.\d+)+'),
]

_PLACEHOLDER_PREFIX = 'ragprot'


def _protect_patterns(text: str) -> tuple[str, dict[str, str]]:
    """Replace structured-data patterns with safe placeholders.

    Args:
        text: Raw input text.

    Returns:
        (modified_text, protected_map) where protected_map maps each
        placeholder back to the original matched string.
    """
    protected: dict[str, str] = {}
    counter = [0]

    def replacer(m: re.Match) -> str:
        key = f'{_PLACEHOLDER_PREFIX}{counter[0]:04d}'
        protected[key] = m.group()
        counter[0] += 1
        return key

    for pat in _PROTECT_PATTERNS:
        text = pat.sub(replacer, text)
    return text, protected


def _restore_patterns(text: str, protected: dict[str, str]) -> str:
    """Restore placeholders to their original strings.

    Args:
        text:      Tokenized text that may contain ragprotXXXX placeholders.
        protected: Map from placeholder → original string.

    Returns:
        Text with all placeholders replaced by the originals.
    """
    for key, original in protected.items():
        text = text.replace(key, original)
    return text


# ── Tokenizer ─────────────────────────────────────────────────────────────────

class RagTokenizer(infinity.rag_tokenizer.RagTokenizer):

    def tokenize(self, line: str) -> str:
        from common import settings  # moved from top of file to avoid circular import
        if settings.DOC_ENGINE_INFINITY:
            return line
        line, protected = _protect_patterns(line)
        result = super().tokenize(line)
        return _restore_patterns(result, protected)

    def fine_grained_tokenize(self, tks: str) -> str:
        from common import settings  # moved from top of file to avoid circular import
        if settings.DOC_ENGINE_INFINITY:
            return tks
        tks, protected = _protect_patterns(tks)
        result = super().fine_grained_tokenize(tks)
        return _restore_patterns(result, protected)


# ── Module-level helpers (re-exported from parent) ────────────────────────────

def is_chinese(s):
    return infinity.rag_tokenizer.is_chinese(s)


def is_number(s):
    return infinity.rag_tokenizer.is_number(s)


def is_alphabet(s):
    return infinity.rag_tokenizer.is_alphabet(s)


def naive_qie(txt):
    return infinity.rag_tokenizer.naive_qie(txt)


tokenizer = RagTokenizer()
tokenize = tokenizer.tokenize
fine_grained_tokenize = tokenizer.fine_grained_tokenize
tag = tokenizer.tag
freq = tokenizer.freq
tradi2simp = tokenizer._tradi2simp
strQ2B = tokenizer._strQ2B
```

- [ ] **Step 2: 运行 _protect_patterns 和 _restore_patterns 测试**

```bash
python -m pytest test/unit_test/rag/nlp/test_structured_tokenization.py::TestProtectPatterns \
                 test/unit_test/rag/nlp/test_structured_tokenization.py::TestRestorePatterns \
                 -v
```

预期：所有 `TestProtectPatterns` 和 `TestRestorePatterns` 测试 **PASS**

- [ ] **Step 3: 提交**

```bash
git add rag/nlp/rag_tokenizer.py
git commit -m "feat: protect structured data patterns in tokenizer using placeholder substitution"
```

---

## Task 4: 运行集成测试并验证

**Files:**
- Test: `test/unit_test/rag/nlp/test_structured_tokenization.py`（`TestRagTokenizerIntegration`）

- [ ] **Step 1: 运行全部测试**

```bash
python -m pytest test/unit_test/rag/nlp/test_structured_tokenization.py -v
```

预期：全部测试 **PASS**。若 `TestRagTokenizerIntegration` 中某些测试失败（因环境缺少分词字典），跳过集成类（见 Step 2）。

- [ ] **Step 2: 若集成测试因字典缺失报错，添加 skip 标记**

如果报错类似 `Dictionary huqie.txt not found`，在测试文件的 `TestRagTokenizerIntegration` 类上添加：

```python
pytest.importorskip("infinity.rag_tokenizer", reason="需要分词字典，跳过集成测试")
```

或在类定义前加：

```python
@pytest.mark.skipif(
    not os.path.exists("/usr/share/infinity/resource/rag/huqie.txt"),
    reason="分词字典不存在，跳过集成测试"
)
class TestRagTokenizerIntegration:
    ...
```

同时在文件顶部加 `import os`。

- [ ] **Step 3: 再次运行确认**

```bash
python -m pytest test/unit_test/rag/nlp/test_structured_tokenization.py -v
```

预期：全部 PASS（或集成类 SKIPPED，其余全 PASS）

- [ ] **Step 4: 提交**

```bash
git add test/unit_test/rag/nlp/test_structured_tokenization.py
git commit -m "test: finalize structured tokenization unit tests with integration skip guard"
```

---

## Task 5: 快速人工冒烟验证

**Files:** 无需修改

- [ ] **Step 1: 用 Python REPL 验证核心效果**

```bash
cd /path/to/ragflow
export PYTHONPATH=$(pwd)
python - <<'EOF'
import sys
from unittest.mock import MagicMock
sys.modules['common'] = MagicMock()
sys.modules['common.settings'] = MagicMock()
sys.modules['common.settings'].DOC_ENGINE_INFINITY = False

from rag.nlp.rag_tokenizer import _protect_patterns, _restore_patterns

cases = [
    "2024年1月发布",
    "温度36.5°C",
    "增长率3.5%",
    "重量50kg",
    "版本v1.0.0",
    "售价¥1,280",
    "到期2024-01-15",
    "2024年1月售价¥100增长3.5%",   # 多模式
    "普通文本没有特殊数据",            # 无模式，应原样返回
]

for c in cases:
    modified, protected = _protect_patterns(c)
    restored = _restore_patterns(modified, protected)
    status = "✅" if restored == c else "❌"
    print(f"{status} '{c}' → {len(protected)} 保护词 → 还原: '{restored}'")
EOF
```

预期输出（全部 ✅）：
```
✅ '2024年1月发布' → 1 保护词 → 还原: '2024年1月发布'
✅ '温度36.5°C' → 1 保护词 → 还原: '温度36.5°C'
✅ '增长率3.5%' → 1 保护词 → 还原: '增长率3.5%'
✅ '重量50kg' → 1 保护词 → 还原: '重量50kg'
✅ '版本v1.0.0' → 1 保护词 → 还原: '版本v1.0.0'
✅ '售价¥1,280' → 1 保护词 → 还原: '售价¥1,280'
✅ '到期2024-01-15' → 1 保护词 → 还原: '到期2024-01-15'
✅ '2024年1月售价¥100增长3.5%' → 3 保护词 → 还原: '2024年1月售价¥100增长3.5%'
✅ '普通文本没有特殊数据' → 0 保护词 → 还原: '普通文本没有特殊数据'
```

- [ ] **Step 2: 最终提交（如有未提交内容）**

```bash
git status
# 若有未提交文件：
git add -p
git commit -m "chore: final cleanup for structured tokenization feature"
```

---

## 向后兼容说明

> ⚠️ 新 token 形态（如 `2024年1月` 作为单个 token）与旧索引不同。
> **已入库的文档需要重新解析/重新索引**才能享受到改进效果。
> 查询侧无需额外操作，同步生效。
