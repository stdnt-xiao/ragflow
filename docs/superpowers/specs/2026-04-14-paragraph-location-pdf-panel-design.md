# 段落位置 PDF 高亮面板设计文档

**日期**：2026-04-14
**状态**：已批准，待实现

---

## 1. 背景与目标

知识库精确索引功能已在 chunk 内容中追加 `[paragraph_location: ...]` 坐标标签。当 LLM 在回答中保留这些标签（通过聊天 `precise_index` 开关）时，需要在前端将其渲染为可点击链接，点击后在右侧展开原始 PDF 并高亮对应段落。

---

## 2. 最终效果

1. LLM 回答中的数字（带位置标签）渲染为蓝色下划线链接，标签内容隐藏
2. 点击链接后，右侧展开 PDF 面板，自动定位到对应页码并高亮段落坐标区域
3. PDF 面板与聊天设置面板互斥：打开 PDF 面板时设置面板自动关闭

**渲染前（LLM 原始输出）：**
```
南宁机场 68.48%[paragraph_location: doc_id=abc123, page=4, x0=72, y0=486, x1=524, y1=558]
```

**渲染后：**
```
南宁机场 [68.48%]  ← 蓝色下划线，点击展开 PDF
```

---

## 3. 标签格式变更

### 3.1 新格式（增加 doc_id 字段）

```
[paragraph_location: doc_id=XXXX, page=N, x0=X0, y0=Y0, x1=X1, y1=Y1]
```

字段说明：
- `doc_id`：文档数据库 ID，与 `reference.doc_aggs[].doc_id` 一致
- `page`：1-indexed 页码
- `x0, y0`：段落左上角坐标（DeepDOC 3x zoom 像素）
- `x1, y1`：段落右下角坐标

### 3.2 解析正则

```
\[paragraph_location:\s*doc_id=([^,\]]+),\s*page=(\d+),\s*x0=([\d.]+),\s*y0=([\d.]+),\s*x1=([\d.]+),\s*y1=([\d.]+)\]
```

### 3.3 不兼容旧格式

旧格式（无 `doc_id`）不渲染为链接。用户需重新解析文档以生效。

---

## 4. 架构设计

### 4.1 后端改动（索引阶段）

**文件**：`rag/nlp/__init__.py`

`annotate_numbers(text, doc_id)` 新增 `doc_id` 参数，生成的标签从：
```
[paragraph_location: page=4, x0=72, y0=486, x1=524, y1=558]
```
变为：
```
[paragraph_location: doc_id=abc123, page=4, x0=72, y0=486, x1=524, y1=558]
```

`tokenize_chunks()` 新增 `doc_id: str` 参数，从调用方传入 `doc["id"]`，再转给 `annotate_numbers()`：

```python
# rag/nlp/__init__.py
def tokenize_chunks(chunks, doc, eng, pdf_parser, ..., precise_index=False):
    doc_id = doc.get("id", "")
    for ck in chunks:
        if precise_index and pdf_parser:
            ck = annotate_numbers(ck, doc_id=doc_id)
        ...
```

```python
def annotate_numbers(text: str, doc_id: str = "") -> str:
    # 生成标签时追加 doc_id
    tag = f"[paragraph_location: doc_id={doc_id}, page={page}, x0={x0}, y0={y0}, x1={x1}, y1={y1}]"
```

**测试**：更新 `test/test_annotate_numbers.py`，验证新格式包含 `doc_id` 字段。

### 4.2 前端数据结构

**新接口** `ParagraphLocationRef`（放在 `web/src/interfaces/database/chat.ts`）：

```typescript
export interface ParagraphLocationRef {
  doc_id: string;
  doc_name: string;   // 从 reference.doc_aggs 查找，找不到则用 doc_id 截断值
  page: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}
```

### 4.3 解析工具函数

**新文件** `web/src/utils/paragraph-location.ts`：

```typescript
const PARAGRAPH_LOCATION_RE =
  /([^\s\[\]]+)\[paragraph_location:\s*doc_id=([^,\]]+),\s*page=(\d+),\s*x0=([\d.]+),\s*y0=([\d.]+),\s*x1=([\d.]+),\s*y1=([\d.]+)\]/g;

export interface ParsedParagraphLocation {
  number: string;   // 数字+单位，如 "68.48%"
  doc_id: string;
  page: number;
  x0: number; y0: number;
  x1: number; y1: number;
}
```

### 4.4 MarkdownContent 渲染改动

**文件**：`web/src/components/markdown-content/index.tsx`

新增 prop `onParagraphLocationClick?: (ref: ParagraphLocationRef) => void`。

在 `renderReference()` 处理完 `##N$$` 引用之后，再对文本做一次 `reactStringReplace`，匹配 `NUMBER[paragraph_location: ...]` 模式，替换为：

```tsx
<span
  className="text-[rgb(59,130,246)] underline cursor-pointer"
  onClick={() => onParagraphLocationClick?.({
    doc_id,
    doc_name: reference?.doc_aggs?.find(d => d.doc_id === doc_id)?.doc_name ?? doc_id.slice(0, 8),
    page: Number(page),
    x0: Number(x0), y0: Number(y0),
    x1: Number(x1), y1: Number(y1),
  })}
>
  {number}
</span>
```

### 4.5 Prop Drilling 路径

```
chat/index.tsx
  activeParagraphRef: ParagraphLocationRef | null
  setActiveParagraphRef: (ref: ParagraphLocationRef | null) => void
    ↓ onParagraphLocationClick={setActiveParagraphRef}
  SingleChatBox
    ↓ onParagraphLocationClick
  MessageItem
    ↓ onParagraphLocationClick
  MarkdownContent
    → 调用 onParagraphLocationClick(ref)
```

### 4.6 ParagraphLocationPdfPanel 组件

**新文件**：`web/src/components/paragraph-location-pdf-panel/index.tsx`

参照 `EntityPdfPanel`，将 `ParagraphLocationRef` 转换为 `IHighlight`：

```typescript
function paragraphRefToHighlight(
  ref: ParagraphLocationRef,
  pageWidth: number,
  pageHeight: number,
): IHighlight {
  return {
    id: `ploc-${ref.doc_id}-${ref.page}`,
    comment: { text: `p.${ref.page}`, emoji: '' },
    position: {
      boundingRect: {
        x1: ref.x0, y1: ref.y0,
        x2: ref.x1, y2: ref.y1,
        width: pageWidth, height: pageHeight,
        pageNumber: ref.page,
      },
      rects: [...],
      pageNumber: ref.page,
    },
    content: { text: '' },
  };
}
```

使用 `useGetDocumentUrl(ref.doc_id)` 获取 PDF URL，`PdfPreview` 展示并高亮。

### 4.7 chat/index.tsx 布局改动

```tsx
// 新增 state
const [activeParagraphRef, setActiveParagraphRef] = useState<ParagraphLocationRef | null>(null);

// 布局
<CardContent className="flex p-0 h-full">
  <Card>
    <SingleChatBox
      ...
      onParagraphLocationClick={setActiveParagraphRef}
    />
  </Card>
  <ParagraphLocationPdfPanel
    locationRef={activeParagraphRef}
    onClose={() => setActiveParagraphRef(null)}
  />
  <ChatSettings
    hasSingleChatBox={hasSingleChatBox}
    forceClose={!!activeParagraphRef}
  />
</CardContent>
```

`ChatSettings` 新增 `forceClose?: boolean` prop：当值变为 `true` 时，调用 `setVisible(false)`（通过 `useEffect` 监听）。

---

## 5. 变更文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `rag/nlp/__init__.py` | 修改 | `annotate_numbers()` 增加 `doc_id` 参数；`tokenize_chunks()` 传入 `doc["id"]` |
| `test/test_annotate_numbers.py` | 修改 | 更新测试，验证新标签格式含 `doc_id` |
| `web/src/interfaces/database/chat.ts` | 修改 | 新增 `ParagraphLocationRef` 接口 |
| `web/src/utils/paragraph-location.ts` | 新增 | 解析工具函数和正则 |
| `web/src/components/markdown-content/index.tsx` | 修改 | 新增 `onParagraphLocationClick` prop；渲染可点击链接 |
| `web/src/components/message-item/index.tsx` | 修改 | 新增 `onParagraphLocationClick` prop，向下传递 |
| `web/src/components/paragraph-location-pdf-panel/index.tsx` | 新增 | PDF 面板组件 |
| `web/src/pages/next-chats/chat/chat-box/single-chat-box.tsx` | 修改 | 新增 `onParagraphLocationClick` prop，向下传递 |
| `web/src/pages/next-chats/chat/app-settings/chat-settings.tsx` | 修改 | 新增 `forceClose` prop |
| `web/src/pages/next-chats/chat/index.tsx` | 修改 | 状态管理 + 渲染 `ParagraphLocationPdfPanel` |

---

## 6. 测试要点

1. 开启知识库精确索引并重新解析 PDF → chunk 中 `doc_id` 字段正确写入
2. 开启聊天 `precise_index` → 发问 → LLM 回答中数字显示为蓝色下划线
3. 点击数字 → 右侧 PDF 面板展开，正确页码，段落高亮
4. 同时打开设置面板时点击数字 → 设置面板自动关闭
5. 关闭 PDF 面板 → 回到正常布局
6. 旧格式标签（无 `doc_id`）→ 普通文本，不渲染为链接

---

## 7. 边界情况

| 情况 | 处理 |
|------|------|
| `doc_id` 在 `reference.doc_aggs` 中找不到 | `doc_name` 显示 `doc_id` 前8位 |
| `doc_id` 对应文档已删除 | `useGetDocumentUrl` 返回空，面板显示空白 |
| 旧格式标签（无 `doc_id`）| 不匹配新正则，渲染为普通文本 |
| 同一消息多次点击不同数字 | `setActiveParagraphRef` 直接替换，面板更新到新位置 |
