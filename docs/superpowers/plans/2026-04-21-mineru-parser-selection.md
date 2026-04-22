# MinerU PDF Parser Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add MinerU as a first-class built-in option in the PDF layout recognition dropdown, alongside DeepDoc, with a configurable server URL per document.

**Architecture:** Add `MinerU` to the `ParseDocumentType` const enum and the built-in options list in `layout-recognize-form-field.tsx`. The existing `MinerUOptionsFormField` already renders when `layout_recognize` contains "mineru" — no wiring change needed. Add a `mineru_server_url` input field to `MinerUOptionsFormField`. In the backend, extend `by_mineru` with a fallback that creates `MinerUParser` directly from `parser_config.mineru_server_url` when no tenant LLM model is configured.

**Tech Stack:** React, react-hook-form, i18next, Python (Flask backend), pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `web/src/components/layout-recognize-form-field.tsx` | Modify | Add `MinerU` to `ParseDocumentType` enum and built-in options list |
| `web/src/components/mineru-options-form-field.tsx` | Modify | Add `mineru_server_url` input field before existing options |
| `web/src/locales/en.ts` | Modify | Add `mineruServerUrl` and `mineruServerUrlTip` i18n keys |
| `web/src/locales/zh.ts` | Modify | Add Chinese translations for same keys |
| `rag/app/naive.py` | Modify | Add direct `MinerUParser` fallback in `by_mineru` |
| `test/unit_test/rag/app/test_by_mineru_direct.py` | Create | Unit tests for the new fallback path |

---

### Task 1: Add MinerU to built-in layout recognize options

**Files:**
- Modify: `web/src/components/layout-recognize-form-field.tsx`

- [ ] **Step 1: Add `MinerU` to `ParseDocumentType` enum**

Open `web/src/components/layout-recognize-form-field.tsx`. Locate the `ParseDocumentType` const enum (around line 19) and add `MinerU`:

```ts
export const enum ParseDocumentType {
  DeepDOC = 'DeepDOC',
  PlainText = 'Plain Text',
  Docling = 'Docling',
  TCADPParser = 'TCADP Parser',
  MinerU = 'MinerU',
}
```

- [ ] **Step 2: Add MinerU to the built-in options list**

In the same file, find the `options` useMemo (around line 48). The hardcoded array currently has `DeepDOC`, `PlainText`, `Docling`, `TCADPParser`. Add `MinerU` as the fifth entry:

```ts
const list = optionsWithoutLLM
  ? optionsWithoutLLM
  : [
      ParseDocumentType.DeepDOC,
      ParseDocumentType.PlainText,
      ParseDocumentType.Docling,
      ParseDocumentType.TCADPParser,
      ParseDocumentType.MinerU,
    ].map((x) => ({
      label: x === ParseDocumentType.PlainText ? t(camelCase(x)) : x,
      value: x,
    }));
```

- [ ] **Step 3: Verify `isMineruSelected` logic covers new enum value**

In `web/src/components/chunk-method-dialog/index.tsx`, confirm lines 189–191 already handle the new value:

```ts
const isMineruSelected =
  selectedTag?.toLowerCase().includes('mineru') ||
  layoutRecognize?.toLowerCase?.()?.includes('mineru');
```

`"MinerU".toLowerCase().includes('mineru')` is `true` — no change needed.

In `web/src/components/mineru-options-form-field.tsx`, confirm the guard already handles it:

```ts
const isMinerUSelected =
  layoutRecognize?.includes(LLMFactory.MinerU) ||
  layoutRecognize?.toLowerCase()?.includes('mineru');
```

`"MinerU".includes("MinerU")` is `true` — no change needed.

- [ ] **Step 4: Commit**

```bash
cd /Users/xiaojian/code/ragflow
git add web/src/components/layout-recognize-form-field.tsx
git commit -m "feat: add MinerU as built-in PDF layout recognition option"
```

---

### Task 2: Add Server URL field to MinerU options form

**Files:**
- Modify: `web/src/locales/en.ts`
- Modify: `web/src/locales/zh.ts`
- Modify: `web/src/components/mineru-options-form-field.tsx`

- [ ] **Step 1: Add i18n key to `en.ts`**

Open `web/src/locales/en.ts`. Find the `mineruOptions` block (around line 463). Add `mineruServerUrl` and `mineruServerUrlTip` **before** `mineruParseMethod`:

```ts
mineruOptions: 'MinerU options',
mineruServerUrl: 'Server URL',
mineruServerUrlTip:
  'MinerU API server URL (e.g. http://localhost:8000). Leave blank to use the globally configured MinerU service.',
mineruParseMethod: 'Parse method',
```

- [ ] **Step 2: Add i18n key to `zh.ts`**

Open `web/src/locales/zh.ts`. Find the `mineruOptions` block (around line 414). Add the same two keys before `mineruParseMethod`:

```ts
mineruOptions: 'MinerU 选项',
mineruServerUrl: '服务器 URL',
mineruServerUrlTip:
  'MinerU API 服务器地址（例如 http://localhost:8000）。留空则使用全局配置的 MinerU 服务。',
mineruParseMethod: '解析方法',
```

- [ ] **Step 3: Add Server URL input to `MinerUOptionsFormField`**

Open `web/src/components/mineru-options-form-field.tsx`. Add the `Input` import and insert the server URL field as the first item inside the returned JSX, before the `mineru_parse_method` field.

Add import at the top of the file (after existing imports):

```ts
import { Input } from '@/components/ui/input';
```

Replace the opening `<div className="space-y-4 border-l-2 ...">` content to add the server URL field first:

```tsx
return (
  <div className="space-y-4 border-l-2 border-primary/30 pl-4 ml-2">
    <div className="text-sm font-medium text-text-secondary">
      {t('knowledgeConfiguration.mineruOptions', 'MinerU Options')}
    </div>

    <RAGFlowFormItem
      name={buildName('mineru_server_url')}
      label={t('knowledgeConfiguration.mineruServerUrl', 'Server URL')}
      tooltip={t(
        'knowledgeConfiguration.mineruServerUrlTip',
        'MinerU API server URL (e.g. http://localhost:8000). Leave blank to use the globally configured MinerU service.',
      )}
      horizontal={true}
    >
      {(field) => (
        <Input
          {...field}
          value={field.value || ''}
          placeholder="http://localhost:8000"
        />
      )}
    </RAGFlowFormItem>

    <RAGFlowFormItem
      name={buildName('mineru_parse_method')}
      label={t('knowledgeConfiguration.mineruParseMethod', 'Parse Method')}
      tooltip={t(
        'knowledgeConfiguration.mineruParseMethodTip',
        'Method for parsing PDF: auto (automatic detection), txt (text extraction), ocr (optical character recognition)',
      )}
      horizontal={true}
    >
      {(field) => (
        <RAGFlowSelect
          value={field.value || 'auto'}
          onChange={field.onChange}
          options={parseMethodOptions}
          placeholder={t('common.selectPlaceholder', 'Select value')}
        />
      )}
    </RAGFlowFormItem>

    <RAGFlowFormItem
      name={buildName('mineru_lang')}
      label={t('knowledgeConfiguration.mineruLanguage', 'Language')}
      tooltip={t(
        'knowledgeConfiguration.mineruLanguageTip',
        'Preferred OCR language for MinerU.',
      )}
      horizontal={true}
    >
      {(field) => (
        <RAGFlowSelect
          value={field.value || 'English'}
          onChange={field.onChange}
          options={languageOptions}
          placeholder={t('common.selectPlaceholder', 'Select value')}
        />
      )}
    </RAGFlowFormItem>

    <RAGFlowFormItem
      name={buildName('mineru_formula_enable')}
      label={t(
        'knowledgeConfiguration.mineruFormulaEnable',
        'Formula Recognition',
      )}
      tooltip={t(
        'knowledgeConfiguration.mineruFormulaEnableTip',
        'Enable formula recognition. Note: This may not work correctly for Cyrillic documents.',
      )}
      horizontal={true}
      labelClassName="!mb-0"
    >
      {(field) => (
        <Switch
          checked={field.value ?? true}
          onCheckedChange={field.onChange}
        />
      )}
    </RAGFlowFormItem>

    <RAGFlowFormItem
      name={buildName('mineru_table_enable')}
      label={t(
        'knowledgeConfiguration.mineruTableEnable',
        'Table Recognition',
      )}
      tooltip={t(
        'knowledgeConfiguration.mineruTableEnableTip',
        'Enable table recognition and extraction.',
      )}
      horizontal={true}
      labelClassName="!mb-0"
    >
      {(field) => (
        <Switch
          checked={field.value ?? true}
          onCheckedChange={field.onChange}
        />
      )}
    </RAGFlowFormItem>
  </div>
);
```

- [ ] **Step 4: Commit**

```bash
cd /Users/xiaojian/code/ragflow
git add web/src/components/mineru-options-form-field.tsx \
        web/src/locales/en.ts \
        web/src/locales/zh.ts
git commit -m "feat: add server URL field to MinerU options form"
```

---

### Task 3: Backend fallback — create MinerUParser directly from parser_config

**Files:**
- Create: `test/unit_test/rag/app/test_by_mineru_direct.py`
- Modify: `rag/app/naive.py`

- [ ] **Step 1: Write the failing tests**

Create `test/unit_test/rag/app/test_by_mineru_direct.py`:

```python
"""Tests for by_mineru direct server URL fallback path."""
import pytest
from unittest.mock import patch, MagicMock, call


def test_by_mineru_uses_parser_config_server_url_when_no_model():
    """by_mineru creates MinerUParser directly when parser_config.mineru_server_url is set and no tenant model exists."""
    from rag.app.naive import by_mineru

    fake_sections = [("text content", "pos_tag")]
    fake_tables = []

    mock_parser_instance = MagicMock()
    mock_parser_instance.parse_pdf.return_value = (fake_sections, fake_tables)

    with patch("deepdoc.parser.mineru_parser.MinerUParser", return_value=mock_parser_instance) as mock_cls:
        sections, tables, parser = by_mineru(
            filename="test.pdf",
            binary=b"fake pdf content",
            parser_config={"mineru_server_url": "http://localhost:8000"},
        )

    mock_cls.assert_called_once_with(mineru_api="http://localhost:8000")
    assert sections == fake_sections
    assert tables == fake_tables
    assert parser is mock_parser_instance


def test_by_mineru_returns_none_without_any_server_config():
    """by_mineru returns (None, None, None) and calls callback when no model or server URL."""
    from rag.app.naive import by_mineru

    mock_callback = MagicMock()

    with patch.dict("os.environ", {}, clear=True):
        # Ensure MINERU_APISERVER is not set
        import os
        os.environ.pop("MINERU_APISERVER", None)

        sections, tables, parser = by_mineru(
            filename="test.pdf",
            binary=b"fake",
            callback=mock_callback,
            parser_config={},
        )

    assert sections is None
    assert tables is None
    assert parser is None
    mock_callback.assert_called_once_with(-1, "MinerU not found.")


def test_by_mineru_parser_config_url_takes_effect_over_missing_env():
    """parser_config.mineru_server_url works even when MINERU_APISERVER env var is absent."""
    from rag.app.naive import by_mineru

    mock_parser_instance = MagicMock()
    mock_parser_instance.parse_pdf.return_value = ([], [])

    import os
    os.environ.pop("MINERU_APISERVER", None)

    with patch("deepdoc.parser.mineru_parser.MinerUParser", return_value=mock_parser_instance):
        sections, tables, parser = by_mineru(
            filename="test.pdf",
            binary=b"fake",
            parser_config={"mineru_server_url": "http://custom-server:9000"},
        )

    assert parser is mock_parser_instance
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/xiaojian/code/ragflow
source .venv/bin/activate
PYTHONPATH=$(pwd) pytest test/unit_test/rag/app/test_by_mineru_direct.py -v 2>&1 | tail -20
```

Expected: FAIL — `MinerUParser` import not found inside `by_mineru`, or wrong `(None, None, None)` returned.

- [ ] **Step 3: Implement the fallback in `by_mineru`**

Open `rag/app/naive.py`. Find the `by_mineru` function (line 101). Replace the tail of the function — currently lines 146–148:

```python
    if callback:
        callback(-1, "MinerU not found.")
    return None, None, None
```

with:

```python
    # Fallback: create MinerUParser directly from parser_config or env var
    parser_config = kwargs.get("parser_config", {})
    mineru_api = parser_config.get("mineru_server_url", "") or os.environ.get("MINERU_APISERVER", "")
    if mineru_api:
        from deepdoc.parser.mineru_parser import MinerUParser
        pdf_parser = MinerUParser(mineru_api=mineru_api)
        sections, tables = pdf_parser.parse_pdf(
            filepath=filename,
            binary=binary,
            callback=callback,
            parse_method=parse_method,
            lang=lang,
            **kwargs,
        )
        return sections, tables, pdf_parser

    if callback:
        callback(-1, "MinerU not found.")
    return None, None, None
```

The full `by_mineru` function after edit (lines 101–162):

```python
def by_mineru(
    filename,
    binary=None,
    from_page=0,
    to_page=100000,
    lang="Chinese",
    callback=None,
    pdf_cls=None,
    parse_method: str = "raw",
    mineru_llm_name: str | None = None,
    tenant_id: str | None = None,
    **kwargs,
):
    pdf_parser = None
    if tenant_id:
        if not mineru_llm_name:
            try:
                from api.db.services.tenant_llm_service import TenantLLMService

                env_name = TenantLLMService.ensure_mineru_from_env(tenant_id)
                candidates = TenantLLMService.query(tenant_id=tenant_id, llm_factory="MinerU", model_type=LLMType.OCR)
                if candidates:
                    mineru_llm_name = candidates[0].llm_name
                elif env_name:
                    mineru_llm_name = env_name
            except Exception as e:  # best-effort fallback
                logging.warning(f"fallback to env mineru: {e}")

        if mineru_llm_name:
            try:
                ocr_model_config = get_model_config_by_type_and_name(tenant_id, LLMType.OCR, mineru_llm_name)
                ocr_model = LLMBundle(tenant_id=tenant_id, model_config=ocr_model_config, lang=lang)
                pdf_parser = ocr_model.mdl
                sections, tables = pdf_parser.parse_pdf(
                    filepath=filename,
                    binary=binary,
                    callback=callback,
                    parse_method=parse_method,
                    lang=lang,
                    **kwargs,
                )
                return sections, tables, pdf_parser
            except Exception as e:
                logging.error(f"Failed to parse pdf via LLMBundle MinerU ({mineru_llm_name}): {e}")

    # Fallback: create MinerUParser directly from parser_config or env var
    parser_config = kwargs.get("parser_config", {})
    mineru_api = parser_config.get("mineru_server_url", "") or os.environ.get("MINERU_APISERVER", "")
    if mineru_api:
        from deepdoc.parser.mineru_parser import MinerUParser
        pdf_parser = MinerUParser(mineru_api=mineru_api)
        sections, tables = pdf_parser.parse_pdf(
            filepath=filename,
            binary=binary,
            callback=callback,
            parse_method=parse_method,
            lang=lang,
            **kwargs,
        )
        return sections, tables, pdf_parser

    if callback:
        callback(-1, "MinerU not found.")
    return None, None, None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/xiaojian/code/ragflow
PYTHONPATH=$(pwd) pytest test/unit_test/rag/app/test_by_mineru_direct.py -v 2>&1 | tail -20
```

Expected output:
```
PASSED test_by_mineru_uses_parser_config_server_url_when_no_model
PASSED test_by_mineru_returns_none_without_any_server_config
PASSED test_by_mineru_parser_config_url_takes_effect_over_missing_env
3 passed
```

- [ ] **Step 5: Run existing MinerU tests to check no regression**

```bash
cd /Users/xiaojian/code/ragflow
PYTHONPATH=$(pwd) pytest test/unit_test/deepdoc/parser/test_mineru_transfer_to_sections.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/xiaojian/code/ragflow
git add test/unit_test/rag/app/test_by_mineru_direct.py rag/app/naive.py
git commit -m "feat: add direct MinerUParser fallback in by_mineru for parser_config server URL"
```

---

### Task 4: Manual verification

- [ ] **Step 1: Start frontend dev server**

```bash
cd /Users/xiaojian/code/ragflow/web
npm run dev
```

- [ ] **Step 2: Open a knowledge base, click chunk method settings on a PDF document**

Verify:
1. "PDF parser" (layout_recognize) dropdown now shows "MinerU" as the 5th built-in option (no "Experimental" badge)
2. Selecting "MinerU" causes the MinerU Options panel to appear below the dropdown
3. MinerU Options shows: Server URL (text input), Parse Method, Language, Formula Recognition, Table Recognition
4. Server URL field is optional — leaving it blank saves without error
5. Switching back to "DeepDOC" hides the MinerU Options panel
6. Selecting MinerU via the OCR provider list (old path) still works

- [ ] **Step 3: Verify saved config round-trip**

Save with MinerU + a custom server URL. Re-open the dialog and confirm the URL is still populated.
