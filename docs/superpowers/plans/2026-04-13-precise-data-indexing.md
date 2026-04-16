# Precise Data Indexing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `precise_index` toggle to knowledge base parser config that appends `[paragraph_location: page=N, x0=X0, y0=Y0, x1=X1, y1=Y1]` after each number in PDF chunks.

**Architecture:** Add a boolean `precise_index` field to `ParserConfig`; when enabled, inject a new `annotate_numbers()` function call inside `tokenize_chunks()` before `remove_tag()`, leveraging existing PDF position tags (`@@page\tleft\tright\ttop\tbottom##`) that are still present in chunk text at that point.

**Tech Stack:** Python (pydantic, re), TypeScript/React (zod, shadcn Switch), i18n (en.ts / zh.ts)

---

## File Map

| File | Change |
|------|--------|
| `api/utils/validation_utils.py` | Add `precise_index: bool = False` to `ParserConfig` |
| `rag/nlp/__init__.py` | Add `annotate_numbers()` function; add `precise_index` param to `tokenize_chunks()` |
| `rag/app/naive.py` | Read `precise_index` from `parser_config`; pass to both `tokenize_chunks()` call sites |
| `web/src/interfaces/database/document.ts` | Add `precise_index?: boolean` to `IParserConfig` |
| `web/src/components/chunk-method-dialog/index.tsx` | Add `precise_index` to Zod schema and render `<PreciseIndexFormField>` |
| `web/src/components/chunk-method-dialog/use-default-parser-values.ts` | Add `precise_index: false` default |
| `web/src/components/precise-index-form-field.tsx` | New Switch component (follows `auto-keywords-form-field.tsx` pattern) |
| `web/src/locales/en.ts` | Add `preciseIndex` / `preciseIndexTip` to `knowledgeDetails` |
| `web/src/locales/zh.ts` | Add Chinese translations |
| `test/test_annotate_numbers.py` | Unit tests for `annotate_numbers()` |

---

## Task 1: Add `precise_index` to Backend Config

**Files:**
- Modify: `api/utils/validation_utils.py:387-402`

- [ ] **Step 1: Add field to ParserConfig**

  Open `api/utils/validation_utils.py`. Find the `ParserConfig` class (around line 387). Add `precise_index` as the last field before `ext`:

  ```python
  class ParserConfig(Base):
      auto_keywords: Annotated[int, Field(default=0, ge=0, le=32)]
      auto_questions: Annotated[int, Field(default=0, ge=0, le=10)]
      chunk_token_num: Annotated[int, Field(default=512, ge=1, le=2048)]
      delimiter: Annotated[str, Field(default=r"\n", min_length=1)]
      graphrag: Annotated[GraphragConfig, Field(default_factory=lambda: GraphragConfig(use_graphrag=False))]
      html4excel: Annotated[bool, Field(default=False)]
      layout_recognize: Annotated[str, Field(default="DeepDOC")]
      parent_child: Annotated[ParentChildConfig, Field(default_factory=lambda: ParentChildConfig(use_parent_child=False))]
      raptor: Annotated[RaptorConfig, Field(default_factory=lambda: RaptorConfig(use_raptor=False))]
      tag_kb_ids: Annotated[list[str], Field(default_factory=list)]
      topn_tags: Annotated[int, Field(default=1, ge=1, le=10)]
      filename_embd_weight: Annotated[float | None, Field(default=0.1, ge=0.0, le=1.0)]
      task_page_size: Annotated[int | None, Field(default=None, ge=1)]
      pages: Annotated[list[list[int]] | None, Field(default=None)]
      precise_index: Annotated[bool, Field(default=False)]
      ext: Annotated[dict, Field(default={})]
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add api/utils/validation_utils.py
  git commit -m "feat: add precise_index field to ParserConfig"
  ```

---

## Task 2: Implement `annotate_numbers()` and Update `tokenize_chunks()`

**Files:**
- Modify: `rag/nlp/__init__.py:302-327`
- Create: `test/test_annotate_numbers.py`

### Step 2a: Write failing tests first

- [ ] **Step 1: Create test file**

  Create `test/test_annotate_numbers.py`:

  ```python
  import pytest
  import sys, os
  sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

  from rag.nlp import annotate_numbers


  def _tag(page, left, right, top, bottom):
      """Helper: build a PDF position tag as appears in chunk text."""
      return f"@@{page}\t{left}\t{right}\t{top}\t{bottom}##"


  def _loc(page, left, top, right, bottom):
      """Helper: expected paragraph_location annotation string."""
      return f"[paragraph_location: page={page}, x0={left}, y0={top}, x1={right}, y1={bottom}]"


  class TestAnnotateNumbers:

      def test_single_number_in_one_section(self):
          text = _tag(3, 100, 450, 200, 350) + "功率为 750 kW。"
          result = annotate_numbers(text)
          expected_loc = _loc(3, 100, 200, 450, 350)
          # Position tag preserved, number annotated
          assert _tag(3, 100, 450, 200, 350) in result
          assert "750 kW" + expected_loc in result

      def test_pure_number_no_unit(self):
          text = _tag(1, 0, 200, 0, 100) + "数量为 42。"
          result = annotate_numbers(text)
          assert "42" + _loc(1, 0, 0, 200, 100) in result

      def test_decimal_number(self):
          text = _tag(2, 50, 400, 100, 250) + "功率因数 0.85"
          result = annotate_numbers(text)
          assert "0.85" + _loc(2, 50, 100, 400, 250) in result

      def test_multiple_numbers_same_section(self):
          text = _tag(3, 100, 450, 200, 350) + "电压 380 V，电流 20 A。"
          result = annotate_numbers(text)
          loc = _loc(3, 100, 200, 450, 350)
          assert "380 V" + loc in result
          assert "20 A" + loc in result

      def test_multiple_sections_different_coords(self):
          tag1 = _tag(3, 100, 450, 200, 350)
          tag2 = _tag(3, 100, 450, 350, 500)
          text = tag1 + "功率 750 kW" + tag2 + "电压 380 V"
          result = annotate_numbers(text)
          loc1 = _loc(3, 100, 200, 450, 350)
          loc2 = _loc(3, 100, 350, 450, 500)
          assert "750 kW" + loc1 in result
          assert "380 V" + loc2 in result

      def test_no_position_tags_returns_unchanged(self):
          text = "没有位置标签，数字 123 不应被标注。"
          result = annotate_numbers(text)
          assert result == text

      def test_text_before_first_tag_not_annotated(self):
          text = "前缀文本 99" + _tag(1, 0, 100, 0, 50) + "后续 50 kW"
          result = annotate_numbers(text)
          # "99" comes before any tag → no annotation
          assert "99[paragraph_location" not in result
          # "50 kW" comes after tag → annotated
          assert "50 kW" + _loc(1, 0, 0, 100, 50) in result

      def test_percentage(self):
          text = _tag(1, 0, 300, 0, 100) + "效率 95%"
          result = annotate_numbers(text)
          assert "95%" + _loc(1, 0, 0, 300, 100) in result

      def test_empty_text_after_tag(self):
          text = _tag(1, 0, 100, 0, 50) + ""
          result = annotate_numbers(text)
          # No crash, position tag preserved
          assert _tag(1, 0, 100, 0, 50) in result
  ```

- [ ] **Step 2: Run tests to confirm they fail**

  ```bash
  cd /Users/xiaojian/code/ragflow
  source .venv/bin/activate
  python -m pytest test/test_annotate_numbers.py -v 2>&1 | head -30
  ```

  Expected: `ImportError: cannot import name 'annotate_numbers' from 'rag.nlp'`

### Step 2b: Implement `annotate_numbers()` and update `tokenize_chunks()`

- [ ] **Step 3: Add `annotate_numbers()` to `rag/nlp/__init__.py`**

  Find `tokenize_chunks` (around line 302). **Above** it, add the new function. The file already has `import re` at line 22, so no new import needed.

  Add this function immediately before `def tokenize_chunks`:

  ```python
  def annotate_numbers(text: str) -> str:
      """
      Scan a PDF chunk text that contains position tags (@@page\\tleft\\tright\\ttop\\tbottom##)
      and append [paragraph_location: page=N, x0=X0, y0=Y0, x1=X1, y1=Y1] after each number
      (with optional unit) found in each section.

      Position tags are preserved so that downstream remove_tag() still works correctly.
      Text appearing before the first position tag is left unannotated (no known coordinates).

      Coordinate mapping from tag fields:
        left  → x0,  top    → y0
        right → x1,  bottom → y1
      """
      POS_TAG = re.compile(r'@@(\d+)\t([\d.]+)\t([\d.]+)\t([\d.]+)\t([\d.]+)##')
      NUMBER = re.compile(
          r'(?<!\d)'
          r'\d[\d,，]*(?:[.。]\d+)?'
          r'(?:\s*[a-zA-Z°%℃℉μΩkKmMgGwWvVaA]+)?'
      )

      result = []
      prev_end = 0
      current_box = None  # [page, x0(left), y0(top), x1(right), y1(bottom)]

      for tag in POS_TAG.finditer(text):
          seg = text[prev_end:tag.start()]
          if current_box is not None and seg:
              loc = (
                  f'[paragraph_location: page={current_box[0]}, '
                  f'x0={current_box[1]}, y0={current_box[2]}, '
                  f'x1={current_box[3]}, y1={current_box[4]}]'
              )
              seg = NUMBER.sub(lambda m, l=loc: m.group() + l, seg)
          result.append(seg)
          result.append(tag.group())  # preserve position tag for remove_tag()

          p, l, r, t, b = tag.groups()
          current_box = [int(p), int(float(l)), int(float(t)), int(float(r)), int(float(b))]
          prev_end = tag.end()

      # Process remaining text after last position tag
      seg = text[prev_end:]
      if current_box is not None and seg:
          loc = (
              f'[paragraph_location: page={current_box[0]}, '
              f'x0={current_box[1]}, y0={current_box[2]}, '
              f'x1={current_box[3]}, y1={current_box[4]}]'
          )
          seg = NUMBER.sub(lambda m, l=loc: m.group() + l, seg)
      result.append(seg)

      return ''.join(result)
  ```

- [ ] **Step 4: Update `tokenize_chunks()` signature and body**

  Find `def tokenize_chunks(chunks, doc, eng, pdf_parser=None, child_delimiters_pattern=None):` (around line 302). Replace the function definition and the `if pdf_parser:` block:

  **Old signature:**
  ```python
  def tokenize_chunks(chunks, doc, eng, pdf_parser=None, child_delimiters_pattern=None):
  ```

  **New signature:**
  ```python
  def tokenize_chunks(chunks, doc, eng, pdf_parser=None, child_delimiters_pattern=None, precise_index=False):
  ```

  **Old `if pdf_parser:` block:**
  ```python
          if pdf_parser:
              try:
                  d["image"], poss = pdf_parser.crop(ck, need_position=True)
                  add_positions(d, poss)
                  ck = pdf_parser.remove_tag(ck)
              except NotImplementedError:
                  pass
  ```

  **New `if pdf_parser:` block:**
  ```python
          if pdf_parser:
              try:
                  d["image"], poss = pdf_parser.crop(ck, need_position=True)
                  add_positions(d, poss)
                  if precise_index:
                      ck = annotate_numbers(ck)
                  ck = pdf_parser.remove_tag(ck)
              except NotImplementedError:
                  pass
  ```

- [ ] **Step 5: Run tests to confirm they pass**

  ```bash
  cd /Users/xiaojian/code/ragflow
  source .venv/bin/activate
  python -m pytest test/test_annotate_numbers.py -v
  ```

  Expected: all 9 tests PASS

- [ ] **Step 6: Commit**

  ```bash
  git add rag/nlp/__init__.py test/test_annotate_numbers.py
  git commit -m "feat: add annotate_numbers() and precise_index support to tokenize_chunks()"
  ```

---

## Task 3: Pass `precise_index` Through `naive.py`

**Files:**
- Modify: `rag/app/naive.py` (lines ~740-752 for setup, ~1047 and ~1059 for call sites)

- [ ] **Step 1: Read `precise_index` from `parser_config` in `chunk()`**

  Find the block around line 740 where other `parser_config.get()` calls happen (near `table_context_size`, `image_context_size`). Add `precise_index` extraction right after those lines:

  Find this pattern:
  ```python
  table_context_size = max(0, int(parser_config.get("table_context_size", 0) or 0))
  image_context_size = max(0, int(parser_config.get("image_context_size", 0) or 0))
  ```

  Add immediately after:
  ```python
  precise_index = bool(parser_config.get("precise_index", False))
  ```

- [ ] **Step 2: Pass `precise_index` to first `tokenize_chunks()` call (around line 1047)**

  Find:
  ```python
      res.extend(tokenize_chunks(chunks, doc, is_english, pdf_parser, child_delimiters_pattern=child_deli))
  ```
  (the one inside the `else:` branch following `tokenize_chunks_with_images`)

  Replace with:
  ```python
      res.extend(tokenize_chunks(chunks, doc, is_english, pdf_parser, child_delimiters_pattern=child_deli, precise_index=precise_index))
  ```

- [ ] **Step 3: Pass `precise_index` to second `tokenize_chunks()` call (around line 1059)**

  Find the second occurrence:
  ```python
      res.extend(tokenize_chunks(chunks, doc, is_english, pdf_parser, child_delimiters_pattern=child_deli))
  ```

  Replace with:
  ```python
      res.extend(tokenize_chunks(chunks, doc, is_english, pdf_parser, child_delimiters_pattern=child_deli, precise_index=precise_index))
  ```

- [ ] **Step 4: Verify the changes look correct**

  ```bash
  grep -n "precise_index" /Users/xiaojian/code/ragflow/rag/app/naive.py
  ```

  Expected output (3 lines):
  ```
  74X:  precise_index = bool(parser_config.get("precise_index", False))
  104X:  res.extend(tokenize_chunks(chunks, doc, is_english, pdf_parser, child_delimiters_pattern=child_deli, precise_index=precise_index))
  105X:  res.extend(tokenize_chunks(chunks, doc, is_english, pdf_parser, child_delimiters_pattern=child_deli, precise_index=precise_index))
  ```

- [ ] **Step 5: Smoke-test import (no syntax errors)**

  ```bash
  cd /Users/xiaojian/code/ragflow
  source .venv/bin/activate
  python -c "from rag.app.naive import chunk; print('OK')"
  ```

  Expected: `OK`

- [ ] **Step 6: Commit**

  ```bash
  git add rag/app/naive.py
  git commit -m "feat: pass precise_index from parser_config to tokenize_chunks() in naive.py"
  ```

---

## Task 4: Frontend TypeScript Type

**Files:**
- Modify: `web/src/interfaces/database/document.ts:34-61`

- [ ] **Step 1: Add `precise_index` to `IParserConfig` interface**

  Find `export interface IParserConfig {` (line 34). Add `precise_index` after `enable_metadata`:

  **Old closing of interface:**
  ```typescript
    enable_metadata?: boolean;
  }
  ```

  **New:**
  ```typescript
    enable_metadata?: boolean;
    precise_index?: boolean;
  }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add web/src/interfaces/database/document.ts
  git commit -m "feat: add precise_index to IParserConfig TypeScript interface"
  ```

---

## Task 5: Frontend i18n Strings

**Files:**
- Modify: `web/src/locales/en.ts`
- Modify: `web/src/locales/zh.ts`

- [ ] **Step 1: Add English strings**

  In `web/src/locales/en.ts`, find the `knowledgeDetails` section (around `autoQuestions` / `autoQuestionsTip`). Add after `autoQuestionsTip`:

  Find:
  ```typescript
      autoQuestions: 'Auto-question',
      autoQuestionsTip: `Automatically extract N questions for each chunk`,
  ```

  Add after:
  ```typescript
      preciseIndex: 'Precise Data Indexing',
      preciseIndexTip: 'When enabled, a [paragraph_location] tag is appended after each number in PDF chunks, recording the exact bounding box of the containing paragraph. Only affects PDF documents.',
  ```

- [ ] **Step 2: Add Chinese strings**

  In `web/src/locales/zh.ts`, find the `knowledgeDetails` section (around `autoQuestions` / `autoQuestionsTip`). Add after `autoQuestionsTip`:

  Find:
  ```typescript
      autoQuestions: '自动问题提取',
      autoQuestionsTip: `利用在"配置"中指定的索引模型 对知识库的每个文本块提取 N 个问题`,
  ```

  Add after:
  ```typescript
      preciseIndex: '数据精确索引',
      preciseIndexTip: '开启后，解析 PDF 时每个数字后追加其所在段落的坐标标签 [paragraph_location]，便于精确溯源。仅对 PDF 文档生效。',
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add web/src/locales/en.ts web/src/locales/zh.ts
  git commit -m "feat: add precise_index i18n strings"
  ```

---

## Task 6: Frontend UI Component

**Files:**
- Create: `web/src/components/precise-index-form-field.tsx`
- Modify: `web/src/components/chunk-method-dialog/index.tsx`
- Modify: `web/src/components/chunk-method-dialog/use-default-parser-values.ts`

### Step 6a: Create the Switch component

- [ ] **Step 1: Create `precise-index-form-field.tsx`**

  Create `web/src/components/precise-index-form-field.tsx` (follows the `html4excel` toggle pattern):

  ```tsx
  import { useTranslate } from '@/hooks/common-hooks';
  import { FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
  import { Switch } from '@/components/ui/switch';
  import { useFormContext } from 'react-hook-form';
  import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
  import { CircleHelp } from 'lucide-react';

  export function PreciseIndexFormField() {
    const { t } = useTranslate('knowledgeDetails');
    const form = useFormContext();

    return (
      <FormField
        control={form.control}
        name="parser_config.precise_index"
        render={({ field }) => (
          <FormItem className="flex flex-row items-center justify-between">
            <div className="flex items-center gap-1">
              <FormLabel>{t('preciseIndex')}</FormLabel>
              <Tooltip>
                <TooltipTrigger asChild>
                  <CircleHelp className="size-3.5 cursor-pointer text-text-sub-title" />
                </TooltipTrigger>
                <TooltipContent>{t('preciseIndexTip')}</TooltipContent>
              </Tooltip>
            </div>
            <FormControl>
              <Switch
                checked={field.value ?? false}
                onCheckedChange={field.onChange}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  }
  ```

  > **Note:** If the existing toggle components (e.g., `ExcelToHtmlFormField`) use a different pattern (e.g., Ant Design Switch instead of shadcn), mirror that pattern exactly. Check `web/src/components/excel-to-html-form-field.tsx` for reference.

### Step 6b: Add Zod schema field and default value

- [ ] **Step 2: Add to Zod schema in `chunk-method-dialog/index.tsx`**

  Find `html4excel: z.boolean().optional(),` (around line 122). Add `precise_index` immediately after:

  **Old:**
  ```typescript
          html4excel: z.boolean().optional(),
  ```

  **New:**
  ```typescript
          html4excel: z.boolean().optional(),
          precise_index: z.boolean().optional(),
  ```

- [ ] **Step 3: Add default value in `use-default-parser-values.ts`**

  Find `html4excel: false,` in the `defaultParserValues` object. Add `precise_index: false` immediately after:

  **Old:**
  ```typescript
        html4excel: false,
  ```

  **New:**
  ```typescript
        html4excel: false,
        precise_index: false,
  ```

### Step 6c: Render the component in the dialog

- [ ] **Step 4: Import and render `PreciseIndexFormField` in `chunk-method-dialog/index.tsx`**

  At the top of the file, add import alongside other form field imports:
  ```typescript
  import { PreciseIndexFormField } from '@/components/precise-index-form-field';
  ```

  Find the `{selectedTag === DocumentParserType.Naive && (` block (around line 359):

  **Old:**
  ```tsx
                  {selectedTag === DocumentParserType.Naive && (
                    <>
                      <EnableTocToggle />
                      <ImageContextWindow />
                    </>
                  )}
  ```

  **New:**
  ```tsx
                  {selectedTag === DocumentParserType.Naive && (
                    <>
                      <EnableTocToggle />
                      <ImageContextWindow />
                      <PreciseIndexFormField />
                    </>
                  )}
  ```

- [ ] **Step 5: Build to check for TypeScript errors**

  ```bash
  cd /Users/xiaojian/code/ragflow/web
  npm run build 2>&1 | tail -20
  ```

  Expected: build succeeds with no TypeScript errors.

- [ ] **Step 6: Commit**

  ```bash
  git add web/src/components/precise-index-form-field.tsx \
          web/src/components/chunk-method-dialog/index.tsx \
          web/src/components/chunk-method-dialog/use-default-parser-values.ts
  git commit -m "feat: add PreciseIndexFormField UI component and wire into chunk-method-dialog"
  ```

---

## Task 7: End-to-End Verification

Use the existing knowledge base `0efb6fe2371f11f1abb057d22c83ac4b` at `http://localhost:9222`.

- [ ] **Step 1: Start dev services**

  Backend and frontend must be running. Confirm at `http://localhost:9222`.

- [ ] **Step 2: Enable the toggle**

  1. Navigate to the knowledge base settings
  2. Open the Parser Config dialog (Naive / General parser)
  3. Toggle **数据精确索引** ON
  4. Save the configuration

- [ ] **Step 3: Re-parse a PDF document**

  Select a PDF document in the knowledge base and click "Re-parse" (or trigger parsing). Wait for status to reach 100%.

- [ ] **Step 4: Inspect chunk content**

  Use the RAGFlow chunk viewer or the API to inspect generated chunks:

  ```bash
  curl -s "http://localhost:9222/api/v1/chunk/list" \
    -H "Authorization: Bearer <your-token>" \
    -d '{"doc_ids": ["<doc_id>"], "page": 1, "size": 5}' \
    | python3 -m json.tool | grep -A2 "content_with_weight"
  ```

  **Expected:** Chunks from PDF sections containing numbers should show:
  ```
  "额定功率 750 kW[paragraph_location: page=3, x0=100, y0=200, x1=450, y1=350]"
  ```

- [ ] **Step 5: Verify coordinate sanity**

  - `page` ≥ 1
  - `x0 < x1`, `y0 < y1`
  - Multiple numbers in the same PDF section share identical coordinates
  - Numbers in different sections have different coordinates

- [ ] **Step 6: Verify toggle OFF produces no annotations**

  Disable the toggle, re-parse the same document, inspect chunks. Expected: no `[paragraph_location: ...]` in `content_with_weight`.

- [ ] **Step 7: Final commit (if any cleanup needed)**

  ```bash
  git add -p  # stage any cleanup changes
  git commit -m "fix: precise_index end-to-end verification cleanup"
  ```
