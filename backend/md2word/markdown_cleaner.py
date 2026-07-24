from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI


@dataclass(frozen=True)
class MarkdownValidationIssue:
    line: int
    code: str
    message: str


@dataclass(frozen=True)
class MarkdownValidationResult:
    ok: bool
    issues: list[MarkdownValidationIssue] = field(default_factory=list)

    def format_for_llm(self) -> str:
        if self.ok:
            return "No validation errors."
        return "\n".join(
            f"- line {issue.line}: [{issue.code}] {issue.message}"
            for issue in self.issues
        )


@dataclass(frozen=True)
class MarkdownCleaningResult:
    markdown_text: str
    validation: MarkdownValidationResult
    rounds: int
    changed: bool
    source: str


class MarkdownCleaningError(ValueError):
    def __init__(self, validation: MarkdownValidationResult):
        super().__init__("Markdown cleaning failed validation:\n" + validation.format_for_llm())
        self.validation = validation


class MarkdownCleanerConfigError(ValueError):
    pass


class OpenAICompatibleMarkdownCleaner:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float):
        self.model = model
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    @classmethod
    def from_env(cls) -> "OpenAICompatibleMarkdownCleaner | None":
        api_key = os.getenv("MD2WORD_LLM_API_KEY", "").strip()
        model = (
            os.getenv("MD2WORD_LLM_CLEANER_MODEL", "").strip()
            or os.getenv("MD2WORD_LLM_MODEL", "").strip()
        )
        if not api_key or not model:
            return None

        base_url = os.getenv("MD2WORD_LLM_BASE_URL", "").strip()
        timeout_value = os.getenv("MD2WORD_LLM_CLEANER_TIMEOUT", "").strip()
        if not base_url:
            raise MarkdownCleanerConfigError("Missing MD2WORD_LLM_BASE_URL")
        if not timeout_value:
            raise MarkdownCleanerConfigError("Missing MD2WORD_LLM_CLEANER_TIMEOUT")
        timeout = float(timeout_value)
        return cls(base_url=base_url, api_key=api_key, model=model, timeout=timeout)

    def clean(self, md_text: str, validation_errors: str = "") -> str | None:
        prompt = (
            "请在不改变语义、不增删事实内容的前提下，整理下面整篇 Markdown。\n"
            "目标：让 Markdown 语法规范、结构清晰，并适合后续转换为 Word。\n\n"
            "硬性要求：\n"
            "1. 只输出整理后的 Markdown 正文，不要解释，不要使用 ```markdown 包裹整篇结果。\n"
            "2. 标题必须使用 ATX 标题语法，例如 '# 标题'、'## 标题'，井号后必须有一个空格。\n"
            "3. 保留原文语义、标题文本、段落内容、列表、表格、图片链接和代码块。\n"
            "4. 可以修复空行、列表缩进、表格分隔行、未闭合代码围栏等 Markdown 语法问题。\n"
            "5. 不要生成 Word 样式说明、不要加入新的章节、不要删除业务内容。\n"
            "6. 不要保留手写目录块；如果原文有“目录”及目录条目，只把真实正文内容整理为章节。\n"
            "7. '# ' 后面的内容只代表整篇文档标题，必须只出现一次，且必须作为第一个有效内容。\n"
            "8. 不要把“第一章”“一、项目背景”等章节标题写成 '# ...'；这些都必须降为 '## ...'。\n"
            "9. '## ' 是正文一级章节标题，例如 '## 一、项目背景'；'### ' 是二级小节，例如 '### （一）项目管理'；'#### ' 是三级小节。\n"
            "10. 不要使用超过四级的标题。\n"
            "11. 不要使用 Setext 标题、加粗、斜体、删除线、水平分割线或非图片超链接。\n"
            "12. 图片必须使用标准 Markdown 图片语法：![图注文本](relative/path.png)。\n"
            "13. 表格必须使用标准 Markdown 表格；表格标题必须放在表格上一行。\n"
            "14. 在文档标题 '# ...' 前不要保留项目名称、建设单位、目录或其他前置文本。\n"
        )
        if validation_errors:
            prompt += (
                "\n上一次结果没有通过语法检查。请修复这些错误：\n"
                f"{validation_errors}\n"
            )
        prompt += "\n原始 Markdown：\n" + md_text

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是 Markdown 规范化器。只输出修正后的 Markdown 内容。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )
        except (APIConnectionError, APITimeoutError, APIError, ValueError):
            return None

        try:
            content = response.choices[0].message.content or ""
        except (IndexError, AttributeError):
            return None
        return _strip_wrapping_markdown_fence(content.strip())


def validate_markdown(md_text: str) -> MarkdownValidationResult:
    issues: list[MarkdownValidationIssue] = []
    lines = md_text.splitlines()

    if not md_text.strip():
        issues.append(MarkdownValidationIssue(1, "empty_document", "Markdown 内容为空。"))

    _validate_code_fences(lines, issues)
    _validate_first_content_is_h1(lines, issues)
    _validate_heading_lines(lines, issues)
    _validate_document_title_heading(lines, issues)
    _validate_list_lines(lines, issues)
    _validate_tables(lines, issues)

    return MarkdownValidationResult(ok=not issues, issues=issues)


def clean_markdown_with_llm_loop(
    md_text: str,
    cleaner: OpenAICompatibleMarkdownCleaner | None = None,
    max_rounds: int | None = None,
    use_env_cleaner: bool = True,
) -> MarkdownCleaningResult:
    cleaner = cleaner if cleaner is not None else (OpenAICompatibleMarkdownCleaner.from_env() if use_env_cleaner else None)
    if max_rounds is None:
        max_rounds_value = os.getenv("MD2WORD_MARKDOWN_CLEAN_MAX_ROUNDS", "").strip()
        if not max_rounds_value:
            raise MarkdownCleanerConfigError("Missing MD2WORD_MARKDOWN_CLEAN_MAX_ROUNDS")
        max_rounds = int(max_rounds_value)

    original = md_text
    current = normalize_markdown_headings(md_text)
    validation = validate_markdown(current)
    if cleaner is None:
        return MarkdownCleaningResult(
            markdown_text=current,
            validation=validation,
            rounds=0,
            changed=current != original,
            source="none",
        )

    last_errors = validation.format_for_llm() if not validation.ok else ""
    for round_no in range(1, max(1, max_rounds) + 1):
        cleaned = cleaner.clean(current, validation_errors=last_errors)
        if cleaned is None or not cleaned.strip():
            break
        current = normalize_markdown_headings(cleaned)
        validation = validate_markdown(current)
        if validation.ok:
            return MarkdownCleaningResult(
                markdown_text=current,
                validation=validation,
                rounds=round_no,
                changed=current != original,
                source="llm",
            )
        last_errors = validation.format_for_llm()

    if not validation.ok:
        raise MarkdownCleaningError(validation)

    return MarkdownCleaningResult(
        markdown_text=current,
        validation=validation,
        rounds=max_rounds,
        changed=current != original,
        source="llm",
    )


def _strip_wrapping_markdown_fence(text: str) -> str:
    match = re.match(r"^```(?:markdown|md)?\s*\n(?P<body>.*)\n```\s*$", text, flags=re.S | re.I)
    if match:
        return match.group("body").strip()
    return text


def normalize_markdown_headings(md_text: str) -> str:
    lines = md_text.splitlines(keepends=True)
    normalized: list[str] = []
    seen_document_title = False

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("# "):
            leading = line[: len(line) - len(stripped)]
            content = stripped[2:]
            if seen_document_title:
                line = f"{leading}## {content}"
            else:
                seen_document_title = True
        normalized.append(line)

    return "".join(normalized)


def _validate_code_fences(lines: list[str], issues: list[MarkdownValidationIssue]) -> None:
    open_fence: tuple[str, int] | None = None
    fence_re = re.compile(r"^\s*(`{3,}|~{3,})")
    for line_no, line in enumerate(lines, start=1):
        match = fence_re.match(line)
        if not match:
            continue
        marker = match.group(1)[0]
        length = len(match.group(1))
        if open_fence is None:
            open_fence = (marker * length, line_no)
            continue
        open_marker, _open_line = open_fence
        if marker == open_marker[0] and length >= len(open_marker):
            open_fence = None
    if open_fence is not None:
        issues.append(
            MarkdownValidationIssue(
                open_fence[1],
                "unclosed_code_fence",
                "代码块围栏没有闭合。",
            )
        )


def _validate_first_content_is_h1(lines: list[str], issues: list[MarkdownValidationIssue]) -> None:
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("# "):
            issues.append(
                MarkdownValidationIssue(
                    line_no,
                    "content_before_first_h1",
                    "第一个有效内容必须是一级标题，不能在第一个章节标题前保留前置文本。",
                )
            )
        return


def _validate_heading_lines(lines: list[str], issues: list[MarkdownValidationIssue]) -> None:
    for line_no, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            continue
        if stripped.startswith("#######"):
            issues.append(MarkdownValidationIssue(line_no, "heading_too_deep", "标题层级不能超过 6 级。"))
            continue
        match = re.match(r"^(#{1,6})(.*)$", stripped)
        if match and match.group(2) and not match.group(2).startswith(" "):
            issues.append(MarkdownValidationIssue(line_no, "heading_missing_space", "标题井号后必须有空格。"))
            continue
        if re.match(r"^#{1,6}\s*$", stripped):
            issues.append(MarkdownValidationIssue(line_no, "empty_heading", "标题不能为空。"))


def _validate_document_title_heading(lines: list[str], issues: list[MarkdownValidationIssue]) -> None:
    h1_count = 0
    chapter_like_re = re.compile(
        r"^#\s+(?:第[一二三四五六七八九十百千万\d]+章|[一二三四五六七八九十]+、|\d+[.．、])"
    )
    for line_no, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if not stripped.startswith("# "):
            continue
        h1_count += 1
        if h1_count > 1:
            issues.append(
                MarkdownValidationIssue(
                    line_no,
                    "multiple_document_titles",
                    "整篇文档只能有一个 '# ' 文档标题，正文一级章节必须使用 '## '。",
                )
            )
        if chapter_like_re.match(stripped):
            issues.append(
                MarkdownValidationIssue(
                    line_no,
                    "chapter_used_as_document_title",
                    "'# ' 只能表示整篇文档标题，章节标题如“第一章”“一、”必须使用 '## '。",
                )
            )


def _validate_list_lines(lines: list[str], issues: list[MarkdownValidationIssue]) -> None:
    unordered_re = re.compile(r"^\s*[-+*]\S")
    ordered_re = re.compile(r"^\s*\d+[.)]\S")
    for line_no, line in enumerate(lines, start=1):
        if unordered_re.match(line):
            issues.append(MarkdownValidationIssue(line_no, "list_missing_space", "无序列表标记后必须有空格。"))
        if ordered_re.match(line):
            issues.append(MarkdownValidationIssue(line_no, "ordered_list_missing_space", "有序列表标记后必须有空格。"))


def _validate_tables(lines: list[str], issues: list[MarkdownValidationIssue]) -> None:
    idx = 0
    while idx < len(lines):
        if not _looks_like_table_separator(lines[idx]):
            idx += 1
            continue

        separator_line_no = idx + 1
        if idx == 0 or "|" not in lines[idx - 1]:
            issues.append(MarkdownValidationIssue(separator_line_no, "table_missing_header", "表格分隔行缺少表头。"))
            idx += 1
            continue

        expected_cells = _table_cell_count(lines[idx - 1])
        separator_cells = _table_cell_count(lines[idx])
        if expected_cells != separator_cells:
            issues.append(
                MarkdownValidationIssue(
                    separator_line_no,
                    "table_separator_mismatch",
                    "表格分隔行列数必须与表头一致。",
                )
            )

        row_idx = idx + 1
        while row_idx < len(lines) and "|" in lines[row_idx].strip():
            if lines[row_idx].strip() and _table_cell_count(lines[row_idx]) != expected_cells:
                issues.append(
                    MarkdownValidationIssue(
                        row_idx + 1,
                        "table_row_mismatch",
                        "表格正文行列数必须与表头一致。",
                    )
                )
            row_idx += 1
        idx = row_idx


def _looks_like_table_separator(line: str) -> bool:
    stripped = line.strip()
    if "|" not in stripped or "-" not in stripped:
        return False
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    return bool(cells) and all(re.match(r"^:?-{3,}:?$", cell) for cell in cells)


def _table_cell_count(line: str) -> int:
    return len(line.strip().strip("|").split("|"))
