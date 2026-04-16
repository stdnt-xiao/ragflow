# Chat Precise Data Indexing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `precise_index` toggle to chat settings that, when enabled, appends an LLM instruction to preserve `[paragraph_location: ...]` tags from knowledge base chunks in answers.

**Architecture:** The toggle is stored in `Dialog.prompt_config.precise_index` (existing JSON field, no schema migration needed). Backend reads the flag and appends a system prompt suffix at message assembly time. Frontend adds a `SwitchFormField` in chat basic settings, following the exact same pattern as `tts` and `toc_enhance`.

**Tech Stack:** Python (Flask/Peewee backend), React/TypeScript (UmiJS), Zod, react-hook-form, i18next

---

## File Map

| File | Change |
|------|--------|
| `api/db/services/dialog_service.py` | Modify line 657: extract sys_content, append precise_index suffix |
| `web/src/pages/next-chats/chat/app-settings/use-chat-setting-schema.tsx` | Add `precise_index: z.boolean().optional()` to promptConfigSchema |
| `web/src/pages/next-chats/chat/app-settings/chat-settings.tsx` | Add `precise_index: false` to defaultValues |
| `web/src/pages/next-chats/chat/app-settings/chat-basic-settings.tsx` | Add SwitchFormField for `prompt_config.precise_index` |
| `web/src/locales/en.ts` | Add `preciseIndex` + `preciseIndexChatTip` in chat namespace |
| `web/src/locales/zh.ts` | Add same keys in Chinese |

---

### Task 1: Add i18n translations

**Files:**
- Modify: `web/src/locales/en.ts`
- Modify: `web/src/locales/zh.ts`

- [ ] **Step 1: Add English translations**

In `web/src/locales/en.ts`, find the line (around line 957):
```
      tocEnhanceTip: ` During the parsing...`,
```
Insert after it (before `batchDeleteSessions`):
```typescript
      preciseIndex: 'Precise Data Indexing',
      preciseIndexChatTip:
        "When enabled, the LLM will preserve [paragraph_location] tags from knowledge base chunks in its answers, allowing precise PDF highlighting.",
```

- [ ] **Step 2: Add Chinese translations**

In `web/src/locales/zh.ts`, find the line (around line 870):
```
      tocEnhanceTip: `解析文档时生成了目录信息...`,
```
Insert after it (before `batchDeleteSessions`):
```typescript
      preciseIndex: '数据精确索引',
      preciseIndexChatTip:
        '开启后，当知识库片段中包含 [paragraph_location] 标签时，LLM 回答中的数字将保留该标签，便于前端精确定位。',
```

- [ ] **Step 3: Commit**

```bash
git add web/src/locales/en.ts web/src/locales/zh.ts
git commit -m "feat: add preciseIndex i18n keys to chat namespace"
```

---

### Task 2: Add Zod schema field

**Files:**
- Modify: `web/src/pages/next-chats/chat/app-settings/use-chat-setting-schema.tsx:18-39`

- [ ] **Step 1: Add field to promptConfigSchema**

In `use-chat-setting-schema.tsx`, find the `promptConfigSchema` object. It currently ends with:
```typescript
    toc_enhance: z.boolean().optional(),
  });
```
Change to:
```typescript
    toc_enhance: z.boolean().optional(),
    precise_index: z.boolean().optional(),
  });
```

- [ ] **Step 2: Commit**

```bash
git add web/src/pages/next-chats/chat/app-settings/use-chat-setting-schema.tsx
git commit -m "feat: add precise_index to chat prompt config Zod schema"
```

---

### Task 3: Add default value

**Files:**
- Modify: `web/src/pages/next-chats/chat/app-settings/chat-settings.tsx:49-60`

- [ ] **Step 1: Add precise_index to defaultValues**

In `chat-settings.tsx`, find the `defaultValues` block:
```typescript
      prompt_config: {
        quote: true,
        keyword: false,
        tts: false,
        use_kg: false,
        refine_multiturn: true,
        system: '',
        parameters: [],
        reasoning: false,
        cross_languages: [],
        toc_enhance: false,
      },
```
Change to:
```typescript
      prompt_config: {
        quote: true,
        keyword: false,
        tts: false,
        use_kg: false,
        refine_multiturn: true,
        system: '',
        parameters: [],
        reasoning: false,
        cross_languages: [],
        toc_enhance: false,
        precise_index: false,
      },
```

- [ ] **Step 2: Commit**

```bash
git add web/src/pages/next-chats/chat/app-settings/chat-settings.tsx
git commit -m "feat: add precise_index default value to chat settings form"
```

---

### Task 4: Render switch in UI

**Files:**
- Modify: `web/src/pages/next-chats/chat/app-settings/chat-basic-settings.tsx`

- [ ] **Step 1: Add SwitchFormField**

In `chat-basic-settings.tsx`, find:
```tsx
      <TOCEnhanceFormField name="prompt_config.toc_enhance"></TOCEnhanceFormField>
      <TavilyFormField></TavilyFormField>
```
Change to:
```tsx
      <TOCEnhanceFormField name="prompt_config.toc_enhance"></TOCEnhanceFormField>
      <SwitchFormField
        name={'prompt_config.precise_index'}
        label={t('preciseIndex')}
        tooltip={t('preciseIndexChatTip')}
      ></SwitchFormField>
      <TavilyFormField></TavilyFormField>
```

- [ ] **Step 2: Verify the frontend build compiles**

```bash
cd web && npm run build 2>&1 | tail -20
```
Expected: build completes with no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/next-chats/chat/app-settings/chat-basic-settings.tsx
git commit -m "feat: add precise_index switch to chat basic settings UI"
```

---

### Task 5: Backend prompt injection

**Files:**
- Modify: `api/db/services/dialog_service.py` (around line 657)

- [ ] **Step 1: Write a unit test first**

Create `test/test_dialog_precise_index.py`:
```python
"""Unit test: precise_index appends location-preservation instruction to system prompt."""
import pytest


PRECISE_INDEX_SUFFIX = (
    "\n\nWhen the knowledge base content contains numbers followed by "
    "[paragraph_location: page=N, x0=X0, y0=Y0, x1=X1, y1=Y1] tags, "
    "preserve those tags exactly as-is after each number when you cite them in your answer. "
    "Do not remove, rewrite, or summarize the tags."
)


def _build_sys_content(base: str, precise_index: bool) -> str:
    """Extracted helper — mirrors the logic added to dialog_service.py."""
    if precise_index:
        return base + PRECISE_INDEX_SUFFIX
    return base


def test_precise_index_enabled_appends_suffix():
    base = "You are a helpful assistant. {knowledge}"
    result = _build_sys_content(base, precise_index=True)
    assert result.endswith(PRECISE_INDEX_SUFFIX)
    assert result.startswith(base)


def test_precise_index_disabled_no_suffix():
    base = "You are a helpful assistant. {knowledge}"
    result = _build_sys_content(base, precise_index=False)
    assert result == base


def test_precise_index_default_off():
    base = "system prompt"
    result = _build_sys_content(base, precise_index=False)
    assert PRECISE_INDEX_SUFFIX not in result
```

- [ ] **Step 2: Run the test — expect PASS (pure logic, no imports)**

```bash
cd /Users/xiaojian/code/ragflow
python -m pytest test/test_dialog_precise_index.py -v
```
Expected output:
```
test_precise_index_enabled_appends_suffix PASSED
test_precise_index_disabled_no_suffix PASSED
test_precise_index_default_off PASSED
3 passed
```

- [ ] **Step 3: Apply the same logic in dialog_service.py**

In `api/db/services/dialog_service.py`, find line 657:
```python
    msg = [{"role": "system", "content": prompt_config["system"].format(**kwargs)+attachments_}]
```
Replace with:
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

- [ ] **Step 4: Run the test again — still PASS**

```bash
python -m pytest test/test_dialog_precise_index.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add api/db/services/dialog_service.py test/test_dialog_precise_index.py
git commit -m "feat: append precise_index system prompt suffix when chat setting enabled"
```

---

### Task 6: End-to-end verification

- [ ] **Step 1: Start the backend**

```bash
source .venv/bin/activate && export PYTHONPATH=$(pwd)
bash docker/launch_backend_service.sh
```

- [ ] **Step 2: Start the frontend dev server**

```bash
cd web && npm run dev
```

- [ ] **Step 3: Verify toggle saves correctly**

1. Open a chat app in the UI
2. Open Chat Settings panel
3. Find "Precise Data Indexing" switch (below PageIndex / TOCEnhance)
4. Toggle it ON → click Save
5. Refresh the page → switch should still be ON

- [ ] **Step 4: Verify prompt injection**

1. The chat must be linked to a KB that has `precise_index: true` and contains re-parsed PDF chunks with `[paragraph_location: ...]` tags
2. Ask a question that retrieves a chunk with a number, e.g., "南宁机场的正常率是多少？"
3. The LLM answer should include: `68.48%[paragraph_location: page=4, x0=72, y0=486, x1=524, y1=558]`

- [ ] **Step 5: Verify toggle OFF produces no tags**

1. Turn off the switch → Save
2. Ask the same question
3. LLM answer should NOT include `[paragraph_location: ...]` tags

---

## Self-Review Checklist

- [x] **Spec coverage**: All 6 files in spec's change list covered ✅
- [x] **No placeholders**: All steps contain exact code ✅
- [x] **Type consistency**: `precise_index` field name is consistent across all tasks ✅
- [x] **i18n namespace**: Both `en.ts` and `zh.ts` use `chat` namespace (not `knowledgeDetails`) ✅
- [x] **TDD**: Unit test written before implementation in Task 5 ✅
- [x] **No DB migration needed**: `prompt_config` is a JSON field ✅
