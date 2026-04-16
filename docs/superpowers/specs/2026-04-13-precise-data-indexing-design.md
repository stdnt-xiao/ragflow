# 数据精确索引功能设计文档

**日期**：2026-04-13
**更新**：2026-04-14（功能验证完成，补充实现细节）
**状态**：已实现并验证

---

## 1. 背景与目标

在知识库文档解析时，数字（如参数值、测量值、统计数据）是高价值信息，但传统 RAG 检索无法追溯数字在原文中的精确位置。

**目标**：在知识库配置中新增"数据精确索引"功能开关。开启后，PDF 文档解析生成 chunk 时，每个数字（如有单位则视为整体）后面追加其所在段落的位置标签，格式为：

```
[paragraph_location: page=N, x0=X0, y0=Y0, x1=X1, y1=Y1]
```

使 LLM 在 RAG 问答时能精确溯源数字来源的段落坐标，方便前端在原始 PDF 上高亮定位。

---

## 2. 范围与限制

- **支持格式**：仅 PDF（其他格式无可靠段落坐标数据，`pdf_parser` 为 None 时自动跳过）
- **支持解析器**：Naive（General）解析器
- **位置精度**：段落级（section 级），即数字所在 PDF 段落块的边界框
- **坐标系**：PDF 解析坐标（像素，DeepDOC 默认 3x zoom），字段含义：
  - `page`：1-indexed 页码
  - `x0, y0`：段落左上角坐标
  - `x1, y1`：段落右下角坐标
- **默认值**：`false`，关闭时完全跳过，无性能影响

---

## 3. 标注格式与示例

### 3.1 标签格式

```
[paragraph_location: page=3, x0=100, y0=200, x1=450, y1=350]
```

- 标准英文字段名，LLM 语义理解准确
- 方括号界定，不与正文混淆
- 解析正则：`\[paragraph_location:\s*page=(\d+),\s*x0=([\d.]+),\s*y0=([\d.]+),\s*x1=([\d.]+),\s*y1=([\d.]+)\]`

### 3.2 实际验证示例

来源文档：`关于2024年2月份航班正常考核指标和相关调控措施的通报.pdf`

**原始 PDF 文本段落**（page=4，某坐标区域）：
> 南宁机场68.48%、合肥机场68.98%、三亚机场71.39%

**标注后的 chunk `content_with_weight`**：
```
南宁机场68.48%[paragraph_location: page=4, x0=72, y0=486, x1=524, y1=558]、
合肥机场68.98%[paragraph_location: page=4, x0=72, y0=486, x1=524, y1=558]、
三亚机场71.39%[paragraph_location: page=4, x0=72, y0=486, x1=524, y1=558]
```

> 同一段落内多个数字共享相同的坐标（`x0/y0/x1/y1` 相同），不同段落坐标不同。

### 3.3 数字匹配规则

| 类型 | 示例 | 是否匹配 |
|------|------|---------|
| 整数 | `42` | ✅ |
| 小数 | `0.85` | ✅ |
| 带单位（英文） | `750 kW`、`380 V`、`20 A` | ✅ |
| 百分比 | `95%`、`68.48%` | ✅ |
| 千分位 | `1,450` | ✅ |
| 中文数字（千、万） | `三千` | ❌（当前不覆盖，可后续扩展） |

---

## 4. 架构设计

### 4.1 数据流

```
KB 设置（precise_index: true）
    ↓ 保存到 Knowledgebase.parser_config
Re-parse 触发
    ↓ task_executor 创建任务
    ↓ 合并 kb_parser_config.precise_index → merged_parser_config
    ↓ chunker.chunk(parser_config=merged_parser_config)
naive.py → chunk()
    ↓ precise_index = parser_config.get("precise_index", False)
    ↓ tokenize_chunks(..., precise_index=precise_index)
rag/nlp/__init__.py → tokenize_chunks()
    ↓ if precise_index: ck = annotate_numbers(ck)   ← 在 remove_tag 之前
    ↓ ck = pdf_parser.remove_tag(ck)
    ↓ tokenize(d, ck, eng)
写入 Elasticsearch: content_with_weight 含 [paragraph_location: ...]
```

### 4.2 配置层

**`api/utils/validation_utils.py`** — `ParserConfig` 新增字段：

```python
precise_index: Annotated[bool, Field(default=False)]
```

存储在 `Knowledgebase.parser_config` JSON 字段中，无需数据库 schema 迁移。

**重要设计决策**：`precise_index` 是 KB 级别配置，但任务创建时使用的是文档自身的 `parser_config`（不含 KB 级配置）。因此在 `task_executor.py` 中显式合并：

```python
# task_executor.py - chunk 调用前
kb_overrides = {
    k: v for k, v in task.get("kb_parser_config", {}).items()
    if k in ("precise_index",) and k not in task["parser_config"]
}
merged_parser_config = {**kb_overrides, **task["parser_config"]}
cks = await thread_pool_exec(
    chunker.chunk,
    ...
    parser_config=merged_parser_config,
)
```

### 4.3 处理层

**核心函数** `annotate_numbers(text: str) -> str`（`rag/nlp/__init__.py`）：

```python
def annotate_numbers(text: str) -> str:
    """
    扫描含位置标签（@@page\tleft\tright\ttop\tbottom##）的 chunk 文本，
    在每个数字（含可选单位）后追加 [paragraph_location: ...] 标签。

    位置标签在处理后保留，供下游 remove_tag() 正常处理。
    首个位置标签之前的文本不作标注（无已知坐标）。

    坐标字段映射（PDF 解析 tag → paragraph_location）：
      left  → x0,  top  → y0
      right → x1,  bottom → y1
    """
```

关键设计：
- **标签格式**：DeepDOC PDF 解析产生 `@@page\tleft\tright\ttop\tbottom##` 位置标签，此时仍存在于 chunk 文本中
- **注入时机**：在 `remove_tag()` 之前调用，确保位置标签可读；`remove_tag()` 调用后位置标签被移除，只留下 `[paragraph_location: ...]` 注解
- **坐标转换**：tag 字段顺序为 `left, right, top, bottom`；输出字段顺序为 `x0(left), y0(top), x1(right), y1(bottom)`

**调用链路**：

```python
# naive.py → chunk()
precise_index = bool(parser_config.get("precise_index", False))
# ... 两处调用均传入
res.extend(tokenize_chunks(
    chunks, doc, is_english, pdf_parser,
    child_delimiters_pattern=child_deli,
    precise_index=precise_index
))
```

### 4.4 前端层

遵循 `ExcelToHtmlFormField` 组件模式，新增 `PreciseIndexFormField`：

```tsx
// web/src/components/precise-index-form-field.tsx
export function PreciseIndexFormField() {
  const form = useFormContext();
  const { t } = useTranslate('knowledgeDetails');

  return (
    <FormField
      control={form.control}
      name="parser_config.precise_index"
      render={({ field }) => (
        <FormItem className="items-center space-y-0">
          <FormLabel tooltip={t('preciseIndexTip')}>
            {t('preciseIndex')}
          </FormLabel>
          <Switch checked={field.value ?? false} onCheckedChange={field.onChange} />
        </FormItem>
      )}
    />
  );
}
```

渲染位置：
- `web/src/pages/dataset/dataset-setting/configuration/naive.tsx` — 知识库设置页
- `web/src/components/chunk-method-dialog/index.tsx` — 文档 chunk 方法弹窗

**前端保存链路修复点**（实现时踩坑）：

`use-knowledge-request.ts` 中 `extractParserConfigExt()` 通过显式解构区分已知字段和扩展字段，新字段必须手动列入，否则落入 `ext` 子对象导致保存路径错误：

```typescript
const {
  ...,
  precise_index,  // 必须显式列出
  ext,
  ...parserExt
} = parserConfig;
return { ..., precise_index, ext: { ...ext, ...parserExt } };
```

同理，`form-schema.ts`（Zod schema）和 `index.tsx`（defaultValues）均需补充该字段，否则表单提交时被 strip 或回填时被覆盖为默认值。

i18n：

| key | zh-CN | en-US |
|-----|-------|-------|
| `preciseIndex` | 数据精确索引 | Precise Data Indexing |
| `preciseIndexTip` | 开启后，解析 PDF 时每个数字后追加其所在段落的坐标标签 [paragraph_location]，便于精确溯源。仅对 PDF 文档生效。 | When enabled, a [paragraph_location] tag is appended after each number in PDF chunks, recording the exact bounding box of the containing paragraph. Only affects PDF documents. |

---

## 5. 变更文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `api/utils/validation_utils.py` | 修改 | `ParserConfig` 新增 `precise_index: Annotated[bool, Field(default=False)]` |
| `rag/nlp/__init__.py` | 修改 | 新增 `annotate_numbers()` 函数；`tokenize_chunks()` 新增 `precise_index` 参数 |
| `rag/app/naive.py` | 修改 | `chunk()` 读取 `precise_index`，传入两处 `tokenize_chunks()` 调用 |
| `rag/svr/task_executor.py` | 修改 | chunk 调用前合并 `kb_parser_config.precise_index` 到文档 `parser_config` |
| `web/src/interfaces/database/document.ts` | 修改 | `IParserConfig` 新增 `precise_index?: boolean` |
| `web/src/locales/en.ts` | 修改 | 新增 `preciseIndex` / `preciseIndexTip` |
| `web/src/locales/zh.ts` | 修改 | 新增中文翻译 |
| `web/src/components/precise-index-form-field.tsx` | 新增 | Switch 组件 |
| `web/src/components/chunk-method-dialog/index.tsx` | 修改 | Zod schema + 渲染组件 |
| `web/src/components/chunk-method-dialog/use-default-parser-values.ts` | 修改 | 默认值 `precise_index: false` |
| `web/src/pages/dataset/dataset-setting/configuration/naive.tsx` | 修改 | 知识库设置页渲染组件 |
| `web/src/pages/dataset/dataset-setting/form-schema.ts` | 修改 | Zod schema 新增字段（防止 strip） |
| `web/src/pages/dataset/dataset-setting/index.tsx` | 修改 | defaultValues 新增字段（防止回填覆盖） |
| `web/src/hooks/use-knowledge-request.ts` | 修改 | `extractParserConfigExt` 显式列出 `precise_index` |
| `test/test_annotate_numbers.py` | 新增 | 9 个单元测试，覆盖各类数字格式和边界情况 |

---

## 6. 测试验证

### 6.1 单元测试

```bash
python -m pytest test/test_annotate_numbers.py -v
# 9 passed in 0.90s
```

覆盖场景：单数字、纯数字、小数、多数字同段落、多段落不同坐标、无位置标签、首个标签前的文本、百分比、标签后空文本。

### 6.2 端到端验证

**测试知识库**：`0efb6fe2371f11f1abb057d22c83ac4b`

验证步骤：
1. 知识库设置 → 开启「数据精确索引」→ 保存
2. 确认数据库已保存：`SELECT parser_config FROM knowledgebase WHERE id='...'` → 含 `"precise_index": true`
3. 对 PDF 文档点「Re-parse」
4. Kibana Dev Tools 查询：

```json
GET /ragflow_*/_search
{
  "size": 5,
  "_source": ["content_with_weight", "docnm_kwd"],
  "query": { "match_all": {} }
}
```

5. 验证 `content_with_weight` 中数字后含 `[paragraph_location: ...]`

**验证通过**：已在 `关于2024年2月份航班正常考核指标和相关调控措施的通报.pdf` 上完成验证，百分比数字（如 `68.48%`、`71.39%`）均正确追加了段落位置标签。

---

## 7. 边界情况

| 情况 | 处理方式 |
|------|---------|
| 非 PDF 文档 | `pdf_parser` 为 None → 跳过 `annotate_numbers`，无标注 |
| chunk 文本无位置标签 | `current_box` 保持 None，数字不标注，文本原样返回 |
| 首个标签之前的文本 | 无已知坐标，不标注 |
| 数字后无单位 | 正则只匹配数字主体，正常标注 |
| `precise_index=False`（默认） | 完全跳过 `annotate_numbers`，无性能影响 |
| 中文单位（千、万、米等） | 当前正则不覆盖，后续可扩展 NUMBER 正则 |
| 表格 chunk | 表格内容不走 `tokenize_chunks`，不受影响 |
| XGBoost 模型兼容性 | `updown_concat_xgb.model` 已从旧 binary 格式转换为 UBJ 格式（兼容 XGBoost 3.x） |

---

## 8. 实现踩坑记录

> 供后续类似功能参考。

### 8.1 task_executor 未启动

**现象**：文档提交解析后，进度永远停在"N tasks ahead in queue"。

**原因**：`dev-restart.sh` 只启动了 `ragflow_server.py`，未启动 `task_executor.py`。

**修复**：`dev-restart.sh` 加入 task_executor 启动命令。

### 8.2 XGBoost 模型格式不兼容

**现象**：PDF 解析报错 `Failed to load model: updown_concat_xgb.model. The binary format has been deprecated in 1.6 and removed in 3.1`。

**原因**：项目内置模型文件为旧 XGBoost binary 格式，但安装的 XGBoost 为 3.2.0。

**修复**：用 XGBoost 3.0 临时环境加载旧模型并重存为 UBJ 格式。原文件备份为 `.bak_binary`。

### 8.3 precise_index 不随 Re-parse 生效

**现象**：KB 配置保存了 `precise_index: true`，但解析后 chunk 无标注。

**原因**：任务创建时使用文档自身的 `parser_config`（从文档记录读取），KB 级的 `precise_index` 不在其中。

**修复**：`task_executor.py` 在调用 `chunker.chunk()` 前，将 `kb_parser_config` 中的 `precise_index` 合并到 `parser_config`。

### 8.4 前端配置保存后被还原

**现象**：UI 开启开关保存，刷新后开关恢复为关闭状态。

**根本原因**（三处）：

1. `use-knowledge-request.ts` 的 `extractParserConfigExt()` 未列出 `precise_index`，导致字段落入 `ext` 子对象，后端接收到错误路径
2. `form-schema.ts` Zod schema 未定义该字段，表单提交时 strip
3. `index.tsx` `defaultValues` 未定义该字段，回填时被覆盖为 `undefined`

**教训**：在 RAGFlow 前端新增 `parser_config` 字段时，需同时更新以下 4 处：
- `IParserConfig` 接口（TypeScript 类型）
- `extractParserConfigExt()`（保存序列化）
- Zod `formSchema`（表单验证）
- `defaultValues`（初始值/回填兜底）
