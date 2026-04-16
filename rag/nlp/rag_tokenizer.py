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
# Additional complication: when precise_index=True, annotate_numbers() injects
# {paragraph_location: ...} annotations after each bare number BEFORE tokenize()
# is called, so "2024年1月" arrives as:
#   "2024{paragraph_location:...}年1{paragraph_location:...}月"
#
# Strategy: strip {paragraph_location:...} annotations at the start of
# tokenize() / fine_grained_tokenize() BEFORE pattern matching.
# These annotations are already preserved in content_with_weight (display field);
# content_ltks (search index field) does not need them.
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

# Matches {paragraph_location: ...} annotations injected by annotate_numbers().
_PARLOC_RE = re.compile(r'\{paragraph_location:[^}]*\}')

_PROTECT_PATTERNS: list[re.Pattern] = [
    # Priority 0: Table/figure title patterns — MUST come before date patterns so that
    # "2024年1月国内...统计表" is captured as a whole title before its date prefix
    # ("2024年1月") is extracted by a later priority.
    # The terminal keyword list is deliberately restrictive to avoid false positives
    # like "数据表明" or "情况表示".
    # 0a: Date-prefixed table titles  e.g. "2024年1月国内航空公司航班起飞正常统计表"
    # The multi-char terminal keywords (e.g. "统计表") are already specific enough;
    # no lookahead is needed and would incorrectly block "统计表显示数据" type contexts.
    re.compile(
        r'\d{4}\s?年\s?\d{1,2}\s?月[^\n，。！？；]{2,60}?'
        r'(?:统计表|汇总表|对比表|明细表|一览表|情况表|分析表|考核表|指标表|调控措施表)'
    ),
    # 0b: Date-prefixed figure titles  e.g. "2024年1月航班正常率折线图"
    re.compile(
        r'\d{4}\s?年\s?\d{1,2}\s?月[^\n，。！？；]{2,60}?'
        r'(?:折线图|柱状图|饼图|散点图|示意图|分布图|流程图|结构图)'
    ),
    # 0c: Pure-Chinese table titles without a leading date  e.g. "国内航空公司航班起飞正常统计表"
    re.compile(
        r'[\u4e00-\u9fff][^\n，。！？；]{1,50}?'
        r'(?:统计表|汇总表|对比表|明细表|一览表|情况表|分析表|考核表|指标表|调控措施表)'
    ),
    # 0d: Pure-Chinese figure titles  e.g. "全国航班正常率折线图"
    re.compile(
        r'[\u4e00-\u9fff][^\n，。！？；]{1,50}?'
        r'(?:折线图|柱状图|饼图|散点图|示意图|分布图|流程图|结构图)'
    ),
    # 0e: Attachment references  附表1  附图2
    re.compile(r'附[表图]\s*\d+'),
    # 0f: English figure/table references  Fig. 1  Figure 2.3  Table 4
    re.compile(r'(?:Fig\.?|Figure|Table)\s+\d+(?:\s*\.\s*\d+)?'),
    # ── END of Priority 0 ── patterns above this line are table/figure name detectors.
    # _PRIORITY_ZERO_END marks the slice boundary used by annotate_numbers() in table
    # mode to annotate ONLY table/figure names, skipping all numeric/date/unit patterns.
    # Priority 1: full datetime  2024年1月15日10时30分(20秒)
    # \s? between digits and Chinese chars handles optional spaces from PDF parsing
    re.compile(r'\d{4}\s?年\s?\d{1,2}\s?月\s?\d{1,2}\s?日\s?\d{1,2}\s?时\s?\d{1,2}\s?分(?:\s?\d{1,2}\s?秒)?'),
    # Priority 2: full date  2024年1月15日
    re.compile(r'\d{4}\s?年\s?\d{1,2}\s?月\s?\d{1,2}\s?日'),
    # Priority 3: year-month  2024年1月
    re.compile(r'\d{4}\s?年\s?\d{1,2}\s?月'),
    # Priority 4: month-day  1月15日
    re.compile(r'\d{1,2}\s?月\s?\d{1,2}\s?日'),
    # Priority 5: hour-minute(-second)  10时30分  /  10时30分20秒
    re.compile(r'\d{1,2}\s?时\s?\d{1,2}\s?分(?:\s?\d{1,2}\s?秒)?'),
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

# Number of patterns in _PROTECT_PATTERNS that belong to Priority 0
# (table/figure name detectors). annotate_numbers() uses this slice in table mode
# to annotate ONLY table/figure names, skipping all numeric/date/unit patterns.
_PRIORITY_ZERO_END: int = 6

_PLACEHOLDER_PREFIX = 'ragprot'


def _index_to_letters(n: int) -> str:
    """Encode an integer as a 4-letter base-26 suffix (a=0 … z=25).

    Using letters instead of digits ensures placeholders contain no digit
    sequences, preventing the NUMBER regex in annotate_numbers() from
    matching inside a placeholder and corrupting the restore step.
    """
    chars = []
    for _ in range(4):
        chars.append(chr(ord('a') + n % 26))
        n //= 26
    return ''.join(reversed(chars))


def _protect_patterns(text: str) -> tuple[str, dict[str, str]]:
    """Replace structured-data patterns with safe placeholders.

    Placeholders have the form ``ragprotXXXX`` where XXXX is a 4-letter
    base-26 suffix (e.g. ``ragprotaaaa``, ``ragprotaaab``).  All-letter
    suffixes guarantee that no digit sequence appears inside a placeholder,
    which prevents the NUMBER regex in ``annotate_numbers()`` from
    accidentally matching and modifying the placeholder.

    Args:
        text: Raw input text.

    Returns:
        (modified_text, protected_map) where protected_map maps each
        placeholder back to the original matched string.
    """
    protected: dict[str, str] = {}
    counter = [0]

    def replacer(m: re.Match) -> str:
        key = f'{_PLACEHOLDER_PREFIX}{_index_to_letters(counter[0])}'
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
        # Strip {paragraph_location:...} annotations injected by annotate_numbers()
        # before pattern matching. Location data is already stored in
        # content_with_weight; content_ltks (search index) should be clean text.
        line = _PARLOC_RE.sub('', line)
        line, protected = _protect_patterns(line)
        result = super().tokenize(line)
        return _restore_patterns(result, protected)

    def fine_grained_tokenize(self, tks: str) -> str:
        from common import settings  # moved from top of file to avoid circular import
        if settings.DOC_ENGINE_INFINITY:
            return tks
        tks = _PARLOC_RE.sub('', tks)
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
