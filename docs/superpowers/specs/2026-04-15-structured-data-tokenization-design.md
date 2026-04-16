# 结构化数据分词保护设计

**日期**：2026-04-15
**状态**：待实现
**作者**：xiaojian

---

## 问题描述

RAGFlow 的分词器在处理以下数据时，会将原本应作为整体的结构化数据拆散：

- **带单位的数字**：`50kg` → `50 kg`，`36.5°C` → `36 5 c`
- **中文日期**：`2024年1月` → `2024 年 1 月`
- **货币金额**：`¥1,280` → `1 280`
- **百分比**：`3.5%` → `3 5`
- **版本号**：`v1.0.0` → `v 1 0 0`

根本原因在父类 `infinity.rag_tokenizer.RagTokenizer.tokenize()` 的三个处理步骤：

1. `re.sub(r"\W+", " ", line)` — 将所有非字符（包括 `°`、`¥`、`%`）替换为空格
2. `_split_by_lang()` — 在中文与非中文边界切分（破坏 `2024年1月` 等日期）
3. NLTK `word_tokenize()` — 将 `50kg` 进一步拆分为 `50`、`kg`

---

## 解决方案：占位符保护法（方案A）

### 核心思路

在调用父类 `tokenize()` 之前，将需要保护的结构化数据替换为**纯字母数字占位符**，父类处理完成后再还原。

```
原始文本
  → _protect_patterns()  [提取并替换为 ragprotXXXX]
  → super().tokenize()   [父类完整管道处理]
  → _restore_patterns()  [还原占位符为原始词]
  → 输出分词结果
```

### 占位符格式

`ragprot` + 4位零补数字，例如：`ragprot0000`、`ragprot0001`

**安全性验证**（能否完整通过父类管道）：

| 管道步骤 | 效果 | 安全 |
|---|---|---|
| `re.sub(r"\W+", " ", ...)` | 全是 `\w` 字符，不受影响 | ✅ |
| `_strQ2B().lower()` | 已是小写，不变 | ✅ |
| `_split_by_lang()` | 非中文，作为整体处理 | ✅ |
| NLTK `word_tokenize` | 单个单词，不拆分 | ✅ |
| Snowball stemmer | 以数字结尾，不命中英文词规则 | ✅ |

---

## 保护模式定义

按**匹配优先级**从高到低排列（越具体的模式优先匹配）：

| 优先级 | 类别 | 示例 | 正则表达式 |
|---|---|---|---|
| 1 | 完整日期时间 | `2024年1月15日10时30分` | `\d{4}年\d{1,2}月\d{1,2}日\d{1,2}时\d{1,2}分(?:\d{1,2}秒)?` |
| 2 | 完整日期 | `2024年1月15日` | `\d{4}年\d{1,2}月\d{1,2}日` |
| 3 | 年月 | `2024年1月` | `\d{4}年\d{1,2}月` |
| 4 | 月日 | `1月15日` | `\d{1,2}月\d{1,2}日` |
| 5 | 时分秒 | `10时30分20秒` | `\d{1,2}时\d{1,2}分(?:\d{1,2}秒)?` |
| 6 | ISO/斜杠日期 | `2024-01-15`、`2024/01/15` | `\d{4}[-/]\d{2}[-/]\d{2}` |
| 7 | 货币（符号前缀） | `¥100`、`$50.00` | `[¥$€£₩]\d[\d,，]*(?:\.\d+)?` |
| 8 | 数字+中文单位 | `3.5万元`、`50千克` | 见下方详细说明 |
| 9 | 数字+英文/SI单位 | `50kg`、`100GB`、`3GHz` | 见下方详细说明 |
| 10 | 百分比/千分比 | `3.5%`、`5‰` | `\d[\d,，]*(?:\.\d+)?[%‰]` |
| 11 | 温度 | `36.5°C`、`-10℃` | `[-−]?\d+(?:\.\d+)?(?:°[CF]|℃|℉)` |
| 12 | 版本号 | `v1.0.0`、`V3.5` | `[vV]\d+(?:\.\d+)+` |

### 中文单位全集

```
万亿|十亿|亿万|千万|百万|十万|
千克|公里|毫升|毫米|厘米|千米|平方米|立方米|
亿|万|千|百|元|角|斤|两|米|升|吨|克|度|时|分|秒
```

正则（优先长单位）：
```
\d[\d,，]*(?:\.\d+)?(?:万亿|十亿|亿万|千万|百万|十万|千克|公里|毫升|毫米|厘米|千米|平方米|立方米|亿|万|千|百|元|角|斤|两|米|升|吨|克|度)
```

### 英文/SI 单位全集

```
GHz|MHz|kHz|kW|MW|GB|MB|KB|TB|PB|mL|ml|
kg|mg|km|cm|mm|Hz|kV|mV|mA|
[gGwWvVaAmMLl]（单字母单位，最后匹配）
```

正则：
```
\d[\d,，]*(?:\.\d+)?\s?(?:GHz|MHz|kHz|kW|MW|GB|MB|KB|TB|PB|mL|ml|kg|mg|km|cm|mm|Hz|kV|mV|mA|[gGwWvVaAL])(?![a-zA-Z])
```

---

## 修改范围

### 文件

**唯一修改文件**：`rag/nlp/rag_tokenizer.py`

增加约 70 行代码：
- 模块级：编译后的保护模式列表 `_PROTECT_PATTERNS`
- 模块级函数：`_protect_patterns(text)` → `(text, protected_map)`
- 模块级函数：`_restore_patterns(text, protected_map)` → `text`
- 类方法覆盖：`RagTokenizer.tokenize()` 增加 protect/restore 包装
- 类方法覆盖：`RagTokenizer.fine_grained_tokenize()` 增加 protect/restore 包装

### 影响路径

```
文档索引：tokenize_chunks() → tokenize() → rag_tokenizer.tokenize()  ✅ 受益
查询解析：FulltextQueryer.question() → rag_tokenizer.tokenize()      ✅ 受益
Infinity 引擎：提前 return line，完全不受影响                         ✅ 安全
```

### 向后兼容

- 新 token 形态（`2024年1月` 作为单个 token）与旧索引不同
- **已入库文档需重新索引**才能享受新效果
- 查询侧同步生效，不需要额外操作

---

## 预期效果

| 输入 | 当前输出 | 修改后输出 |
|---|---|---|
| `温度为36.5°C` | `温度 为 36 5 c` | `温度 为 36.5°C` |
| `2024年1月发布` | `2024 年 1 月 发布` | `2024年1月 发布` |
| `1月15日截止` | `1 月 15 日 截止` | `1月15日 截止` |
| `售价¥1,280元` | `售价 1 280 元` | `售价 ¥1,280 发布` |
| `速度50km` | `速度 50 km` | `速度 50km` |
| `版本v1.0.0` | `版本 v 1 0 0` | `版本 v1.0.0` |
| `增长率3.5%` | `增长率 3 5` | `增长率 3.5%` |
| `2024-01-15到期` | `2024 01 15 到期` | `2024-01-15 到期` |

---

## 实现骨架

```python
# rag/nlp/rag_tokenizer.py

import re
import infinity.rag_tokenizer

# ── 保护模式（按优先级排列，优先长/具体模式）──────────────────────────────────
_PROTECT_PATTERNS = [
    # 日期时间
    re.compile(r'\d{4}年\d{1,2}月\d{1,2}日\d{1,2}时\d{1,2}分(?:\d{1,2}秒)?'),
    re.compile(r'\d{4}年\d{1,2}月\d{1,2}日'),
    re.compile(r'\d{4}年\d{1,2}月'),
    re.compile(r'\d{1,2}月\d{1,2}日'),
    re.compile(r'\d{1,2}时\d{1,2}分(?:\d{1,2}秒)?'),
    re.compile(r'\d{4}[-/]\d{2}[-/]\d{2}'),
    # 货币
    re.compile(r'[¥$€£₩]\d[\d,，]*(?:\.\d+)?'),
    # 数字+中文单位
    re.compile(
        r'\d[\d,，]*(?:\.\d+)?'
        r'(?:万亿|十亿|亿万|千万|百万|十万|千克|公里|毫升|毫米|厘米|千米|平方米|立方米'
        r'|亿|万|千|百|元|角|斤|两|米|升|吨|克|度)'
    ),
    # 数字+英文/SI单位
    re.compile(
        r'\d[\d,，]*(?:\.\d+)?\s?'
        r'(?:GHz|MHz|kHz|kW|MW|GB|MB|KB|TB|PB|mL|ml|kg|mg|km|cm|mm|Hz|kV|mV|mA)'
        r'(?![a-zA-Z])'
    ),
    re.compile(r'\d[\d,，]*(?:\.\d+)?\s?[gGwWvVaAL](?![a-zA-Z])'),
    # 百分比/千分比
    re.compile(r'\d[\d,，]*(?:\.\d+)?[%‰]'),
    # 温度
    re.compile(r'[-−]?\d+(?:\.\d+)?(?:°[CF]|℃|℉)'),
    # 版本号
    re.compile(r'[vV]\d+(?:\.\d+)+'),
]

_PLACEHOLDER_PREFIX = 'ragprot'


def _protect_patterns(text: str) -> tuple[str, dict[str, str]]:
    """将受保护模式替换为占位符，返回 (修改后文本, {占位符: 原始词})。"""
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
    """将占位符还原为原始词。"""
    for key, original in protected.items():
        text = text.replace(key, original)
    return text


class RagTokenizer(infinity.rag_tokenizer.RagTokenizer):

    def tokenize(self, line: str) -> str:
        from common import settings
        if settings.DOC_ENGINE_INFINITY:
            return line
        line, protected = _protect_patterns(line)
        result = super().tokenize(line)
        return _restore_patterns(result, protected)

    def fine_grained_tokenize(self, tks: str) -> str:
        from common import settings
        if settings.DOC_ENGINE_INFINITY:
            return tks
        tks, protected = _protect_patterns(tks)
        result = super().fine_grained_tokenize(tks)
        return _restore_patterns(result, protected)
```

---

## 测试计划

1. **单元测试**：为每种保护模式编写输入/输出断言
2. **边界测试**：
   - 同一句中多个保护模式（`2024年1月售价¥100`）
   - 嵌套/相邻模式（`100~200kg`）
   - 无保护模式的普通文本（确保无副作用）
3. **Infinity 引擎测试**：确认 `DOC_ENGINE_INFINITY=true` 时行为不变
4. **集成测试**：文档上传→检索，验证含单位数字的检索准确性提升
