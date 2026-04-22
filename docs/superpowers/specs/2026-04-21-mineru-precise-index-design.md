# MinerU 精确索引兼容性修复设计

**日期**: 2026-04-21  
**状态**: 待实现  
**范围**: `deepdoc/parser/mineru_parser.py` — 单文件单行改动

---

## 背景

RAGFlow 支持用 MinerU 解析 PDF，同时为 naive 解析器实现了"精确索引"（`precise_index`）功能——在 chunk 文本中注入 `{paragraph_location: …}` 标签，供前端定位到 PDF 对应段落。

精确索引的处理链：

```
tokenize_chunks() → annotate_numbers() → 扫描 @@page\tx0\tx1\ty0\ty1## 标签 → 注入 {paragraph_location: …}
```

`annotate_numbers()` 要求位置标签**嵌入在 chunk 文本内**，找不到则静默跳过。

---

## 问题

MinerU 的 `_transfer_to_sections()` 按 `parse_method` 返回不同结构：

| parse_method | 返回格式 | 位置标签位置 |
|---|---|---|
| `"paper"` | `(text + tag, type)` | **嵌入文本** ✓ |
| `"raw"`（默认） | `(text, tag)` | **独立元素** ✗ |
| `"manual"` / `"pipeline"` | `(text, type, tag)` | 独立元素 ✗ |

默认模式 `"raw"` 下，位置标签作为 tuple 第二元素返回，`naive_merge()` 将其解包为 `pos` 但不拼入文本。`annotate_numbers()` 收到的 chunk 文本里没有 `@@…##` 标签，精确索引完全失效。

---

## 方案

**仅修改 `mineru_parser.py` 的 `_transfer_to_sections()` 中 "raw" 分支（line 585）**，将位置标签同时嵌入文本：

```python
# 修改前（line 585）
sections.append((section, self._line_tag(output)))

# 修改后
tag = self._line_tag(output)
sections.append((section + tag, tag))
```

### 为什么这样改是安全的

1. **仍是 2-tuple**：`naive_merge()` 用 `for sec, pos in sections` 解包，格式不变。
2. **标签会被清除**：`tokenize_chunks()` 最终调用 `pdf_parser.remove_tag(ck)`，存储的 chunk 文本干净。
3. **`crop()` 同样受益**：内部 `extract_positions()` 也从文本中读取 `@@…##`，嵌入后坐标提取同样生效。
4. **`pos` 保留原值**：其他可能消费 `pos` 的代码路径不受影响。
5. **与 "paper" 模式对齐**：该模式已验证可正常工作，逻辑一致。

### 不在本次范围内

- `"manual"` / `"pipeline"` 返回 3-tuple 的问题（会导致 `naive_merge()` 解包失败，是独立 bug）。
- 前端、API、数据库结构无任何变更。

---

## 测试验证

1. 用 MinerU 解析一份多页 PDF，知识库开启 `precise_index=True`。
2. 在聊天中提问，LLM 回答中包含数值型引用。
3. 验证回答文本中出现 `{paragraph_location: …}` 标签，点击能定位到 PDF 对应页。
4. 确认 chunk 存储内容（`content_with_weight`）中不含残留 `@@…##` 标签。

---

## 文件变更

| 文件 | 改动 |
|---|---|
| `deepdoc/parser/mineru_parser.py` | `_transfer_to_sections()` line 585，1 行修改 |
