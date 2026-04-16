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

import os
import re
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

    # ── 版本号 ────────────────────────────────────────────────────────────────

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
        """占位符后缀必须是纯字母（无数字），防止 NUMBER regex 误匹配占位符内部。"""
        text, protected = _protect_patterns("2024年1月售价¥100")
        for key in protected:
            assert re.match(r'^ragprot[a-z]{4}$', key), f"Invalid placeholder format: {key}"


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

_HUQIE_PATH = "/usr/share/infinity/resource/rag/huqie.txt"

@pytest.mark.skipif(
    not os.path.exists(_HUQIE_PATH),
    reason="分词字典不存在，跳过集成测试"
)
class TestRagTokenizerIntegration:
    """
    验证 tokenize() 输出中结构化数据作为单个 token 出现。
    注意：tokenize() 输出是空格分隔的 token 字符串。
    """

    @pytest.fixture(autouse=True)
    def setup_tokenizer(self):
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
        assert "人工智能技术" not in tokens or len(tokens) > 1
