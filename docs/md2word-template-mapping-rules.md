# MD2Word 五份模板 Markdown 映射规则

## 目标

这份文档只回答一件事：当前项目里 5 份 DOCX 模板，实际支持哪些 Markdown 语法，这些语法会被映射成哪些 DOCX 样式。

这份规则以当前代码实现为准，主要来源于：

- `backend/md2word/converter.py`
- `backend/md2word/template_profiles.py`

后续如果要把 LLM 输出规则、校验规则、以及 `title/content` 结构统一下来，应当先以这份文档作为基线。

## 模板清单

当前共有 5 份模板：

| 模板 ID | 模板名称 | 家族 | 版本 | 封面 | 目录 |
| --- | --- | --- | --- | --- | --- |
| `reference` | 当前内置模板 | builtin | reference | 是 | 是 |
| `cloudbility-long` | Cloudbility 长版 | cloudbility | long | 是 | 是 |
| `cloudbility-short` | Cloudbility 短版 | cloudbility | short | 是 | 否 |
| `yuanchuangli-long` | 源创力 长版 | yuanchuangli | long | 是 | 是 |
| `yuanchuangli-short` | 源创力 短版 | yuanchuangli | short | 是 | 否 |

## 先说结论

这 5 份模板的 Markdown 语法支持范围本质上是一套渲染逻辑，不是 5 套逻辑。

- 差异主要在 DOCX 样式名不同。
- `cloudbility-long` 和 `cloudbility-short` 使用同一套样式映射。
- `yuanchuangli-long` 和 `yuanchuangli-short` 使用同一套样式映射。
- 真正影响 Markdown 可写范围的是 `converter.py`，不是模板本身。

所以后续要“固定 Markdown 语法”，应该固定成一套共同子集，然后再让 5 份模板分别套用各自样式。

## 当前渲染管线

当前转换过程是：

1. Markdown 先经 `markdown(..., extensions=["extra"])` 转成 HTML。
2. 再由 `BeautifulSoup` 遍历顶层节点。
3. 每类 HTML 节点被映射成 DOCX 段落、表格、图片、代码块。
4. 最后按模板对应的 `TemplateStyleProfile` 套样式名。

这意味着规则必须同时满足两层：

- Markdown 必须能稳定被 Python Markdown `extra` 扩展解析。
- 解析后的 HTML 节点必须正好落入 `converter.py` 已处理的分支。

## 建议固定的 Markdown 语法子集

这是基于当前 5 份模板实际能力，建议固定下来的语法范围。

### 1. 标题

支持：

- ATX 标题：`#` 到 `######`
- 形式必须是 `# 标题`，井号后保留空格

不建议：

- Setext 标题，即：

```md
标题
===
```

原因：

- 渲染器只显式处理 `h1` 到 `h6`
- 统一要求 ATX 标题更容易校验和让 LLM 遵守

### 2. 普通段落

支持：

- 普通文本段落
- 段内混合普通文本和行内代码

限制：

- 普通超链接不会保留为可点击链接，只会退化为普通文本段落
- 粗体、斜体等强调语义当前没有独立样式映射，最终大多会退化为普通文字

### 3. 行内代码

支持：

- 反引号行内代码：`` `code` ``

效果：

- 会套用模板里的 `inline_code` 样式

### 4. 无序列表

支持：

- `- 项`
- `* 项`
- `+ 项`
- 支持嵌套

要求：

- 列表标记后必须有空格

### 5. 有序列表

支持：

- `1. 项`
- `1) 项`
- 支持嵌套

要求：

- 序号标记后必须有空格

说明：

- 有序列表在 DOCX 中会创建编号实例
- 无序列表主要依赖段落样式，不额外创建项目符号定义

### 6. 引用块

支持：

- Markdown 引用：`> 内容`

额外约定：

- 若引用行以 `提示:` 或 `提示：` 开头，使用提示样式
- 若引用行以 `注意:` 或 `注意：` 开头，使用注意样式
- 若引用行以 `警告:` 或 `警告：` 开头，使用警告样式
- 其他引用使用普通引用样式

### 7. 图片

支持：

- 标准 Markdown 图片：`![图注](path/to/image.png)`
- 指向图片文件的链接：`[图注](path/to/image.png)`

支持的扩展名：

- `.png`
- `.jpg`
- `.jpeg`
- `.gif`
- `.bmp`
- `.webp`

效果：

- 图片插入后使用模板的 `image` 样式
- 会自动生成图注，格式为 `图N 图注文本`
- 如果 `alt` 为空，则用文件名作为图注文本
- 如果文件不存在，会输出 `[图片缺失: 路径]`，并仍补一条图注

### 8. 表格

支持：

- 标准 Markdown 表格
- 依赖 `markdown extra` 解析成 `<table>`

示例：

```md
| 列1 | 列2 |
| --- | --- |
| A | B |
```

额外约定：

- 如果表格前一段单独成行，且匹配 `表 1 标题` 这种形式，会被识别为表注
- 表注正则是：`^表\\s*\\d+\\s+.+`

效果：

- 表格整体套用模板 `table` 样式
- 表头单元格段落套用 `table_header_paragraph`
- 表体单元格段落套用 `table_body_paragraph`
- 若存在表注，则使用 `table_caption` 样式并居中

### 9. 代码块

支持：

- 围栏代码块：

```md
```python
print("hello")
```
```

- 也支持 `~~~`

效果：

- 代码语言若可识别，会额外生成一行 `语言：Python`
- 该语言行使用 `code_language` 样式
- 代码正文逐行输出，每行一个段落，使用 `code_block` 样式

当前内置语言格式化映射：

- `py` / `python` -> `Python`
- `js` / `javascript` -> `JavaScript`
- `ts` / `typescript` -> `TypeScript`
- `json` -> `JSON`
- `yaml` / `yml` -> `YAML`
- `bash` -> `Bash`
- `sh` / `shell` -> `Shell`

### 10. 直接不建议纳入固定规则的语法

虽然 Markdown 解析器可能能识别，但当前 5 份模板没有稳定、明确、独立的 DOCX 样式收益，不建议纳入固定规则：

- 普通超链接
- 粗体
- 斜体
- 删除线
- 水平分割线
- HTML 原生标签
- 任务列表
- 脚注

原因不是“绝对不能出现”，而是“即使出现，也不会得到稳定、可控、模板一致的样式结果”。

## 统一语法到 DOCX 类型映射表

| Markdown 语法 | HTML 节点 | DOCX 输出类型 | 使用的样式类别 |
| --- | --- | --- | --- |
| `#` 到 `######` 标题 | `h1` 到 `h6` | 标题段落 | `headings[level]` |
| 普通段落 | `p` | 正文段落 | `paragraph` |
| 行内代码 | `code`（段内） | 段内 run | `inline_code` |
| 无序列表 | `ul > li` | 列表段落 | `unordered_list` |
| 有序列表 | `ol > li` | 列表段落 + 编号 | `ordered_list` |
| 普通引用 | `blockquote` | 引用段落 | `quote` |
| 提示引用 | `blockquote` | 引用段落 | `tip_quote` |
| 注意引用 | `blockquote` | 引用段落 | `note_quote` |
| 警告引用 | `blockquote` | 引用段落 | `warning_quote` |
| 图片 | `img` 或图片链接 | 图片段落 | `image` |
| 图注 | 图片后自动追加 | 图注段落 | `caption` |
| 表格标题 | 表格前一段匹配 `表 N 标题` | 表注段落 | `table_caption` |
| 表格 | `table` | Word 表格 | `table` |
| 表头单元格文字 | `th` / 首行表头 | 单元格段落 | `table_header_paragraph` |
| 表体单元格文字 | `td` | 单元格段落 | `table_body_paragraph` |
| 代码语言行 | 围栏代码块语言标识 | 普通段落 | `code_language` |
| 代码正文 | `pre > code` | 多个代码段落 | `code_block` |

## 5 份模板的样式映射明细

下面是每个样式类别在 5 份模板中的实际样式名候选。

### 1. `reference`

| 样式类别 | 样式名候选 |
| --- | --- |
| `paragraph` | `Normal` |
| `title` | `Title` |
| `subtitle` | `Subtitle` |
| `headings.1-6` | `Heading 1` 到 `Heading 6`，兼容 `标题 1` 到 `标题 6` |
| `unordered_list` | `Normal` |
| `ordered_list` | `Normal` |
| `quote` / `tip_quote` / `note_quote` / `warning_quote` | `Normal` |
| `image` | `Normal` |
| `caption` | `Caption`, `Normal` |
| `table_caption` | `Caption`, `Normal` |
| `code_block` | `Normal` |
| `code_language` | `Normal` |
| `inline_code` | `Strong`, `Default Paragraph Font` |
| `table` | `Table Grid`, `Normal Table` |
| `table_header_paragraph` | `Normal` |
| `table_body_paragraph` | `Normal` |

### 2. `cloudbility-long`

| 样式类别 | 样式名候选 |
| --- | --- |
| `paragraph` | `Cloudbility-正文`, `Normal` |
| `title` | `Cloudbility-封面标题`, `Title` |
| `subtitle` | `Subtitle` |
| `headings.1-6` | `Heading 1` 到 `Heading 6` |
| `unordered_list` | `Cloudbility-列表样式1级`, `Cloudbility-正文`, `Normal` |
| `ordered_list` | `Cloudbility-列表样式1级`, `Cloudbility-正文`, `Normal` |
| `quote` / `tip_quote` / `note_quote` / `warning_quote` | `Cloudbility-正文`, `Normal` |
| `image` | `Cloudbility-图片`, `Cloudbility-正文`, `Normal` |
| `caption` | `Caption`, `Cloudbility-正文`, `Normal` |
| `table_caption` | `Caption`, `Cloudbility-正文`, `Normal` |
| `code_block` | `Cloudbility-代码`, `Cloudbility-正文`, `Normal` |
| `code_language` | `Cloudbility-代码`, `Cloudbility-正文`, `Normal` |
| `inline_code` | `Strong`, `Default Paragraph Font` |
| `table` | `skybility-表格样式1`, `Normal Table`, `Table Grid` |
| `table_header_paragraph` | `Cloudbility-正文`, `Normal` |
| `table_body_paragraph` | `Cloudbility-正文`, `Normal` |

### 3. `cloudbility-short`

`cloudbility-short` 与 `cloudbility-long` 的样式映射完全相同，只有模板文件本身和是否带目录不同。

### 4. `yuanchuangli-long`

当前代码中，`yuanchuangli-long` 复用了与 Cloudbility 相同的一组样式候选：

| 样式类别 | 样式名候选 |
| --- | --- |
| `paragraph` | `Cloudbility-正文`, `Normal` |
| `title` | `Cloudbility-封面标题`, `Title` |
| `subtitle` | `Subtitle` |
| `headings.1-6` | `Heading 1` 到 `Heading 6` |
| `unordered_list` | `Cloudbility-列表样式1级`, `Cloudbility-正文`, `Normal` |
| `ordered_list` | `Cloudbility-列表样式1级`, `Cloudbility-正文`, `Normal` |
| `quote` / `tip_quote` / `note_quote` / `warning_quote` | `Cloudbility-正文`, `Normal` |
| `image` | `Cloudbility-图片`, `Cloudbility-正文`, `Normal` |
| `caption` | `Caption`, `Cloudbility-正文`, `Normal` |
| `table_caption` | `Caption`, `Cloudbility-正文`, `Normal` |
| `code_block` | `Cloudbility-代码`, `Cloudbility-正文`, `Normal` |
| `code_language` | `Cloudbility-代码`, `Cloudbility-正文`, `Normal` |
| `inline_code` | `Strong`, `Default Paragraph Font` |
| `table` | `skybility-表格样式1`, `Normal Table`, `Table Grid` |
| `table_header_paragraph` | `Cloudbility-正文`, `Normal` |
| `table_body_paragraph` | `Cloudbility-正文`, `Normal` |

这意味着当前“源创力”模板在代码层面并没有独立样式映射定义。

### 5. `yuanchuangli-short`

`yuanchuangli-short` 与 `yuanchuangli-long` 的样式映射完全相同，只有模板文件本身和是否带目录不同。

## 目前已经暴露出的规则边界

### 1. 标题规则和正文规则混在一起

当前清洗逻辑默认：

- 第一个 `#` 是整篇文档标题
- 后续章节要降为 `##`

但渲染器本身其实支持一般性的 `h1` 到 `h6`，说明“标题提取规则”和“正文标题样式映射规则”现在还是耦合的。

### 2. 模板差异主要是样式，不是语法

所以“5 份模板需要 5 套 Markdown 规则”这件事在当前代码里并不成立。

更准确地说：

- 需要 1 套固定 Markdown 语法子集
- 再加 5 份模板的样式映射表

### 3. 源创力模板还没有独立风格配置

`yuanchuangli` 当前直接复用 `Cloudbility` 样式候选，这是一个实现层面的现实，不是设计层面的理想状态。

如果后续想让 5 份模板真正各自独立，`template_profiles.py` 里需要把源创力单独拆出来。

## 建议作为后续规则冻结版本的候选

如果下一步要先“冻结 md 语法”，我建议先冻结成下面这一版：

- 标题：仅允许 ATX 标题
- 正文：普通段落
- 行内代码：允许
- 列表：允许无序 / 有序 / 嵌套
- 引用：允许，并支持 `提示/注意/警告` 前缀分流
- 图片：仅允许标准图片语法
- 表格：仅允许标准 Markdown 表格
- 表注：固定为 `表 N 标题`
- 代码块：仅允许围栏代码块
- 不纳入正式规则：普通链接、粗体、斜体、删除线、水平线、脚注、任务列表、原生 HTML

这套规则和现有渲染器最接近，也最容易变成：

- LLM 提示词
- 校验器
- `title/content` 结构化输出协议

## 下一步建议

如果继续往下做，顺序建议是：

1. 先确认这份文档里的固定语法子集是否就是你要的那一版。
2. 再把“文档标题”从 Markdown 正文里拆出去，独立成 `title` 字段。
3. 之后再把 LLM 输出和校验输入统一成 `{"title": "...", "content": "..."}`。
4. 最后再用这份规则文档反推新的提示词和校验规则。
