---
title: MinerU PDF Parser Selection
date: 2026-04-21
status: approved
---

# MinerU PDF 解析器选择功能设计

## 背景

RAGFlow 目前支持 MinerU 作为 PDF 解析后端，但在 UI 上只能通过"OCR 模型提供商"列表间接选择，体验不直观。KnowFlow 将 DeepDoc 和 MinerU 并列为一等选项供用户直接切换。本功能将这一体验引入 RAGFlow dev 分支。

## 目标

在分块方法配置对话框的"Layout Recognition"下拉框中，将 MinerU 作为内置选项直接暴露，与 DeepDOC 并列，并支持配置本地或远程 MinerU 服务地址。

## 范围

- **不在范围内**：知识库级别的全局解析器设置、MinerU 服务的 Docker 部署方案、新增后端字段

## 架构

### 数据流

```
用户选择 "MinerU"（layout_recognize 下拉框）
    ↓
parser_config.layout_recognize = "MinerU"
    ↓
MinerUOptionsFormField 自动显示（通过 includes('mineru') 检测触发）
    ↓
用户可选填：server_url / parse_method / language / formula / table
    ↓
提交 → parser_config 存入 DB Document 记录
    ↓
后端 normalize_layout_recognizer("MinerU") → layout_recognizer = "mineru"
    ↓
PARSERS["mineru"] → by_mineru(**kwargs) → MinerUParser(server_url=...)
```

### 关键设计决策

- **复用 `layout_recognize` 字段**：无需新增 DB 字段或后端字段，MinerU 与 DeepDOC 用同一字段区分
- **后端零改动**：后端已支持 `layout_recognize="MinerU"` 和 `mineru_server_url` 透传
- **Server URL 可选**：留空时后端使用 `MINERU_APISERVER` 环境变量默认值

## 前端改动

### 1. `layout-recognize-form-field.tsx`

在 `ParseDocumentType` const enum 中新增：

```ts
MinerU = 'MinerU',
```

在内置选项列表中加入 MinerU（排在 TCADPParser 之后），无 Experimental 标签。

### 2. `mineru-options-form-field.tsx`

在现有选项之前新增 **Server URL** 可选输入框：

| 字段 | 类型 | 说明 |
|------|------|------|
| `mineru_server_url` | 文本输入（可选） | MinerU API 地址，留空使用服务端默认 |
| `mineru_parse_method` | 下拉 auto/txt/ocr | 已有 |
| `mineru_lang` | 下拉语言列表 | 已有 |
| `mineru_formula_enable` | 开关 | 已有 |
| `mineru_table_enable` | 开关 | 已有 |

### 3. 不需要改动的文件

- `chunk-method-dialog/index.tsx`：`isMineruSelected` 逻辑已覆盖新内置选项
- 后端所有文件：已支持完整流程

## 边界情况

| 情况 | 处理方式 |
|------|---------|
| Server URL 格式错误 | 后端调用失败，错误显示在任务日志中 |
| Server URL 留空 | 使用 `MINERU_APISERVER` 环境变量 |
| 已通过 OCR 提供商选中 MinerU 的文档 | `isMinerUSelected` 检测逻辑不变，继续兼容 |
| 非 PDF 文档 | Layout Recognize 字段不显示，不受影响 |

## 测试要点

1. 下拉框出现 "MinerU" 选项，无 Experimental 标签
2. 选中 MinerU 后 MinerU Options 面板自动展开
3. Server URL 留空时，文档解析使用服务端默认地址
4. Server URL 填写后，解析请求发往指定地址
5. 切换回 DeepDOC，MinerU Options 面板隐藏
6. 通过 OCR 提供商选中 MinerU 的旧配置不受影响
