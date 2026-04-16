# 聊天数据精确索引适配设计文档

**日期**：2026-04-14
**状态**：已批准，待实现

---

## 1. 背景与目标

知识库（KB）层面的"数据精确索引"功能已实现（见 `2026-04-13-precise-data-indexing-design.md`）：
PDF 文档解析时，每个数字后追加 `[paragraph_location: page=N, x0=X0, y0=Y0, x1=X1, y1=Y1]` 标签，存入 Elasticsearch 的 `content_with_weight` 字段。

**目标**：在聊天设置中新增独立的"数据精确索引"开关。开启后，自动向 LLM 系统提示词末尾追加指令，使 LLM 在回答中引用知识库数字时，原样保留数字后面的 `[paragraph_location: ...]` 标签。

---

## 2. 范围与限制

- **作用对象**：仅影响 Dialog（聊天应用）级别的 RAG 问答，不影响 Agent
- **触发条件**：`Dialog.prompt_config.precise_index == true`
- **与 KB 设置的关系**：相互独立。KB 的 `precise_index` 控制索引阶段标注；Chat 的 `precise_index` 控制推理阶段提示。两者通常需同时开启才能产生效果，但各自独立管理。
- **默认值**：`false`，关闭时无任何影响

---

## 3. 实现方案

### 3.1 后端

**文件**：`api/db/services/dialog_service.py`

在系统消息拼装处（当前第 657 行附近）追加提示词：

```python
sys_content = prompt_config["system"].format(**kwargs) + attachments_
if prompt_config.get("precise_index", False):
    sys_content += (
        "\n\nWhen the knowledge base content contains numbers followed by "
        "[paragraph_location: page=N, x0=X0, y0=Y0, x1=X1, y1=Y1] tags, "
        "preserve those tags exactly as-is after each number when you cite them in your answer. "
        "Do not remove, rewrite, or summarize the tags."
    )
msg = [{"role": "system", "content": sys_content}]
```

无需数据库 schema 迁移，`Dialog.prompt_config` 为 JSON 字段，直接扩展。

### 3.2 前端

共 4 处改动：

| 文件 | 改动内容 |
|------|---------|
| `web/src/pages/next-chats/chat/app-settings/use-chat-setting-schema.tsx` | `promptConfigSchema` 新增 `precise_index: z.boolean().optional()` |
| `web/src/pages/next-chats/chat/app-settings/chat-settings.tsx` | `defaultValues.prompt_config` 新增 `precise_index: false` |
| `web/src/pages/next-chats/chat/app-settings/chat-basic-settings.tsx` | 渲染 `SwitchFormField`，name=`prompt_config.precise_index` |
| `web/src/locales/zh.ts` 和 `web/src/locales/en.ts` | 新增 i18n 翻译 |

### 3.3 i18n

| key | zh-CN | en-US |
|-----|-------|-------|
| `preciseIndex` | 数据精确索引 | Precise Data Indexing |
| `preciseIndexChatTip` | 开启后，当知识库片段中包含 [paragraph_location] 标签时，LLM 回答中的数字将保留该标签，便于前端精确定位 | When enabled, the LLM will preserve [paragraph_location] tags from knowledge base chunks in its answers, allowing precise PDF highlighting |

> 注：`preciseIndex` key 已在知识库设置的 i18n 中定义（`knowledgeDetails` namespace），聊天设置使用 `chat` namespace，需在 chat namespace 下单独添加。

---

## 4. 数据流

```
用户开启聊天设置中的「数据精确索引」开关
    ↓ 保存到 Dialog.prompt_config.precise_index = true
聊天问答触发
    ↓ dialog_service.py 读取 prompt_config
    ↓ precise_index == true → 追加系统提示词
LLM 收到含精确索引指令的系统提示词
    ↓ 知识库片段中含 [paragraph_location: ...] 标签
LLM 回答中保留数字后的 [paragraph_location: ...] 标签
    ↓ 前端解析标签，在 PDF 上高亮定位
```

---

## 5. 变更文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `api/db/services/dialog_service.py` | 修改 | 系统消息拼装时，若 `precise_index` 为 true，追加保留标签指令 |
| `web/src/pages/next-chats/chat/app-settings/use-chat-setting-schema.tsx` | 修改 | Zod schema 新增 `precise_index` 字段 |
| `web/src/pages/next-chats/chat/app-settings/chat-settings.tsx` | 修改 | defaultValues 新增 `precise_index: false` |
| `web/src/pages/next-chats/chat/app-settings/chat-basic-settings.tsx` | 修改 | 渲染 `SwitchFormField` 开关 |
| `web/src/locales/zh.ts` | 修改 | chat namespace 新增 `preciseIndex` / `preciseIndexChatTip` |
| `web/src/locales/en.ts` | 修改 | chat namespace 新增英文翻译 |

---

## 6. 测试要点

1. 聊天设置中开启开关 → 保存 → 刷新后开关状态保持（验证前端保存链路）
2. 开启后发起问答，检查 LLM 返回内容：关联 KB 已开启精确索引的 PDF 文档，数字后应含 `[paragraph_location: ...]`
3. 关闭开关后问答，验证标签不再保留
4. 未关联 KB 或 KB 未开启精确索引时，即使 Chat 开关开启，LLM 回答中不应出现幻觉标签

---

## 7. 注意事项

- 前端保存链路无需像 KB 设置那样做特殊的 `extractParserConfigExt` 处理，聊天设置直接使用 `prompt_config` 对象序列化，不存在字段落入 `ext` 的问题
- 追加的提示词使用英文，因为 LLM 对英文指令理解更一致
- `preciseIndex` 在 `knowledgeDetails` namespace 已有翻译，聊天设置属于 `chat` namespace，需独立添加，避免 namespace 混用
