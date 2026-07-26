from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

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
class MarkdownAgentReview:
    accepted: bool
    summary: str
    retry_focus: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MarkdownAgentRound:
    index: int
    rewrite_summary: str
    review_summary: str
    validation_ok: bool
    issue_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MarkdownCleaningResult:
    markdown_text: str
    validation: MarkdownValidationResult
    rounds: int
    changed: bool
    source: str
    agent_used: bool = False
    accepted: bool = False
    issues_before: list[MarkdownValidationIssue] = field(default_factory=list)
    issues_after: list[MarkdownValidationIssue] = field(default_factory=list)
    plan_summary: str = ""
    review_summary: str = ""
    trace: list[MarkdownAgentRound] = field(default_factory=list)
    document_title: str = ""
    body_markdown: str = ""


class MarkdownCleaningError(ValueError):
    def __init__(self, validation: MarkdownValidationResult):
        super().__init__("Markdown cleaning failed validation:\n" + validation.format_for_llm())
        self.validation = validation


class MarkdownCleanerConfigError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedMarkdown:
    full_markdown: str
    document_title: str
    body_markdown: str


@lru_cache(maxsize=1)
def load_agent_reference_markdown() -> str:
    reference_path = Path(__file__).with_name("agent_reference.md")
    return reference_path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def load_allowed_syntax_reference() -> str:
    return _load_reference_section("允许语法")


@lru_cache(maxsize=1)
def load_example_template_reference() -> str:
    return _load_reference_section("示例模板")


def _load_reference_section(section_title: str) -> str:
    text = load_agent_reference_markdown()
    allowed_marker = "## 允许语法"
    example_marker = "## 示例模板"

    if section_title == "允许语法":
        if allowed_marker not in text:
            return ""
        _, remainder = text.split(allowed_marker, 1)
        if example_marker in remainder:
            body, _ = remainder.split(example_marker, 1)
            return body.strip()
        return remainder.strip()

    if section_title == "示例模板":
        if example_marker not in text:
            return ""
        _, remainder = text.split(example_marker, 1)
        return remainder.strip()

    return ""


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
        return self.rewrite(md_text, review_feedback=validation_errors)

    def rewrite(self, md_text: str, review_feedback: str = "") -> str | None:
        allowed_syntax = load_allowed_syntax_reference()
        example_template = load_example_template_reference()
        prompt = (
            "你是 Markdown 转 Word 预处理 Agent 的重写阶段。\n"
            "你的职责是根据允许语法和示例模板，直接修复输入 Markdown，使其更适合后续 Word 转换。\n"
            "这一步只做结构和语法改写，不做语义审查，不扩写内容，不删改事实。\n\n"
            "硬性要求：\n"
            "1. 只输出整理后的 Markdown 正文，不要解释，不要使用 ```markdown 包裹整篇结果。\n"
            "2. '# ' 只能表示整篇文档标题。\n"
            "3. 正文章节必须从 '## ' 开始，子节最多到 '#### '。\n"
            "4. 修复标题空格、列表空格、表格列数、代码围栏、图片语法和目录块问题。\n"
            "5. 去掉正文标题里的编号前缀，只保留章节标题文本，例如把 '## 第一章 项目概述' 改成 '## 项目概述'，把 '### 1.1 核心问题' 改成 '### 核心问题'。\n"
            "6. 不要把“项目名称：”“建设单位：”这类标题前噪音保留在正文中。\n"
            "7. 不要输出 Word 样式说明，不要加入新的业务章节。\n\n"
            "允许语法：\n"
            f"{allowed_syntax}\n\n"
            "示例模板：\n"
            f"{example_template}\n"
        )
        if review_feedback:
            prompt += f"\n上轮复核意见：\n{review_feedback}\n"
        prompt += f"\n原始 Markdown：\n{md_text}"
        content = self._request(
            system_prompt="你是 Markdown 重写器。只输出修正后的 Markdown 内容。",
            user_prompt=prompt,
        )
        if not content:
            return None
        return _strip_wrapping_markdown_fence(content.strip())

    def review(self, original_md: str, candidate_md: str) -> MarkdownAgentReview:
        allowed_syntax = load_allowed_syntax_reference()
        example_template = load_example_template_reference()
        prompt = (
            "你是 Markdown 转 Word 预处理 Agent 的复核阶段。\n"
            "你的职责是检查候选 Markdown 的语义结构是否合理，而不是做语法校验。\n"
            "重点检查：\n"
            "1. '# ' 是否只用于文档标题。\n"
            "2. 正文一级章节是否错误地写成 '# 第一章 ...' 这类文档标题级别。\n"
            "3. 正文标题里的编号前缀是否已经去掉，例如“第一章”“一、”“1.”“1.1”不应保留在标题文本中。\n"
            "4. 标题前噪音如“项目名称：”“建设单位：”是否错误保留在正文中。\n"
            "5. 标题层级语义是否仍符合示例模板。\n\n"
            "如果可以继续进入后处理，输出：DECISION: ACCEPT\n"
            "如果不可以，输出：DECISION: RETRY\n"
            "然后输出：SUMMARY: 一句话说明\n"
            "再输出 0 到多条以 '- ' 开头的修复重点。\n\n"
            "允许语法：\n"
            f"{allowed_syntax}\n\n"
            "示例模板：\n"
            f"{example_template}\n\n"
            f"原文：\n{original_md}\n\n"
            f"候选 Markdown：\n{candidate_md}"
        )
        content = self._request(
            system_prompt="你是 Markdown 语义结构复核器。只输出 DECISION、SUMMARY 和修复重点。",
            user_prompt=prompt,
        )
        return _parse_review_response(content)

    def _request(self, system_prompt: str, user_prompt: str) -> str | None:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
            )
        except (APIConnectionError, APITimeoutError, APIError, ValueError):
            return None

        try:
            return (response.choices[0].message.content or "").strip()
        except (IndexError, AttributeError):
            return None


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


def validate_conversion_body_markdown(md_text: str) -> MarkdownValidationResult:
    issues: list[MarkdownValidationIssue] = []
    lines = md_text.splitlines()

    if not md_text.strip():
        issues.append(MarkdownValidationIssue(1, "empty_body", "正文内容为空。"))

    _validate_code_fences(lines, issues)
    _validate_heading_lines(lines, issues)
    _validate_body_heading_lines(lines, issues)
    _validate_body_prefix_noise(lines, issues)
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
    initial_validation = validate_markdown(md_text)

    if cleaner is None:
        prepared = prepare_markdown_for_conversion(md_text)
        validation = validate_conversion_body_markdown(prepared.body_markdown)
        return MarkdownCleaningResult(
            markdown_text=prepared.full_markdown,
            validation=validation,
            rounds=0,
            changed=prepared.full_markdown != original,
            source="none",
            agent_used=False,
            accepted=validation.ok,
            issues_before=initial_validation.issues,
            issues_after=validation.issues,
            plan_summary="",
            review_summary="",
            trace=[],
            document_title=prepared.document_title,
            body_markdown=prepared.body_markdown,
        )

    current = md_text
    review_feedback = ""
    trace: list[MarkdownAgentRound] = []
    last_review = MarkdownAgentReview(accepted=False, summary="等待首次复核。", retry_focus=[])
    last_prepared = prepare_markdown_for_conversion(current)
    last_validation = validate_conversion_body_markdown(last_prepared.body_markdown)

    for round_no in range(1, max(1, max_rounds) + 1):
        rewritten = _rewrite_markdown(cleaner, current, review_feedback)
        if rewritten is None or not rewritten.strip():
            break

        review = _review_candidate(cleaner, original, rewritten)
        prepared = prepare_markdown_for_conversion(rewritten)
        validation = validate_conversion_body_markdown(prepared.body_markdown)
        trace.append(
            MarkdownAgentRound(
                index=round_no,
                rewrite_summary="根据参考模板重写 Markdown。",
                review_summary=review.summary,
                validation_ok=validation.ok,
                issue_codes=[issue.code for issue in validation.issues],
            )
        )
        current = rewritten
        last_review = review
        last_prepared = prepared
        last_validation = validation

        if review.accepted and validation.ok:
            return MarkdownCleaningResult(
                markdown_text=prepared.full_markdown,
                validation=validation,
                rounds=round_no,
                changed=prepared.full_markdown != original,
                source="agent",
                agent_used=True,
                accepted=True,
                issues_before=initial_validation.issues,
                issues_after=validation.issues,
                plan_summary="",
                review_summary=review.summary,
                trace=trace,
                document_title=prepared.document_title,
                body_markdown=prepared.body_markdown,
            )

        review_feedback = _format_review_feedback(review, validation)

    if not last_validation.ok:
        raise MarkdownCleaningError(last_validation)

    return MarkdownCleaningResult(
        markdown_text=last_prepared.full_markdown,
        validation=last_validation,
        rounds=len(trace),
        changed=last_prepared.full_markdown != original,
        source="agent",
        agent_used=True,
        accepted=last_review.accepted and last_validation.ok,
        issues_before=initial_validation.issues,
        issues_after=last_validation.issues,
        plan_summary="",
        review_summary=last_review.summary,
        trace=trace,
        document_title=last_prepared.document_title,
        body_markdown=last_prepared.body_markdown,
    )


def prepare_markdown_for_conversion(md_text: str) -> PreparedMarkdown:
    normalized = normalize_markdown_headings(md_text)
    document_title = extract_document_title(normalized)
    body_markdown = strip_document_title_heading(normalized)
    body_markdown = demote_body_h1_headings(body_markdown)
    body_markdown = strip_body_heading_prefixes(body_markdown)
    full_markdown = normalized
    return PreparedMarkdown(
        full_markdown=full_markdown,
        document_title=document_title,
        body_markdown=body_markdown,
    )


def extract_document_title(md_text: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", md_text, flags=re.M)
    if match:
        return match.group(1).strip()
    return ""


def strip_document_title_heading(md_text: str) -> str:
    lines = md_text.splitlines()
    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        if line.lstrip().startswith("# "):
            remaining = lines[:idx] + lines[idx + 1 :]
            while remaining and not remaining[0].strip():
                remaining.pop(0)
            return "\n".join(remaining).strip("\n")
        return md_text.strip("\n")
    return md_text.strip("\n")


def demote_body_h1_headings(md_text: str) -> str:
    lines = md_text.splitlines(keepends=True)
    normalized: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("# "):
            leading = line[: len(line) - len(stripped)]
            line = f"{leading}## {stripped[2:]}"
        normalized.append(line)
    return "".join(normalized).strip("\n")


def strip_body_heading_prefixes(md_text: str) -> str:
    lines = md_text.splitlines(keepends=True)
    normalized: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        match = re.match(r"^(#{2,4})\s+(.+?)\s*$", stripped)
        if not match:
            normalized.append(line)
            continue
        hashes = match.group(1)
        title_text = match.group(2).strip()
        title_text = _strip_heading_prefix_text(title_text)
        leading = line[: len(line) - len(stripped)]
        normalized.append(f"{leading}{hashes} {title_text}\n" if line.endswith("\n") else f"{leading}{hashes} {title_text}")
    return "".join(normalized).strip("\n")


def _strip_heading_prefix_text(text: str) -> str:
    patterns = [
        r"^第[一二三四五六七八九十百千万\d]+章\s+",
        r"^[一二三四五六七八九十百千万]+、\s*",
        r"^\d+(?:\.\d+)*[.．、]?\s+",
    ]
    current = text.strip()
    changed = True
    while changed:
        changed = False
        for pattern in patterns:
            next_text = re.sub(pattern, "", current).strip()
            if next_text != current:
                current = next_text
                changed = True
    return current or text.strip()


def _rewrite_markdown(
    cleaner: OpenAICompatibleMarkdownCleaner,
    md_text: str,
    review_feedback: str,
) -> str | None:
    if hasattr(cleaner, "rewrite"):
        try:
            return cleaner.rewrite(md_text, review_feedback=review_feedback)  # type: ignore[misc]
        except TypeError:
            pass
    if hasattr(cleaner, "clean"):
        return cleaner.clean(md_text, validation_errors=review_feedback)  # type: ignore[misc]
    return None


def _review_candidate(
    cleaner: OpenAICompatibleMarkdownCleaner,
    original_md: str,
    candidate_md: str,
) -> MarkdownAgentReview:
    if hasattr(cleaner, "review"):
        try:
            review = cleaner.review(original_md, candidate_md)  # type: ignore[misc]
        except TypeError:
            review = None
        if isinstance(review, MarkdownAgentReview):
            return review
    return MarkdownAgentReview(
        accepted=True,
        summary="语义结构复核通过。",
        retry_focus=[],
    )


def _format_review_feedback(
    review: MarkdownAgentReview,
    validation: MarkdownValidationResult,
) -> str:
    lines = [review.summary]
    lines.extend(f"- {item}" for item in review.retry_focus)
    if not validation.ok:
        lines.append("正文 Markdown 语法校验未通过：")
        lines.append(validation.format_for_llm())
    return "\n".join(lines)


def _parse_review_response(text: str | None) -> MarkdownAgentReview:
    if not text:
        return MarkdownAgentReview(
            accepted=False,
            summary="复核阶段没有返回有效结果。",
            retry_focus=[],
        )

    accepted = bool(re.search(r"DECISION:\s*ACCEPT", text))
    summary_match = re.search(r"SUMMARY:\s*(.+)", text)
    summary = summary_match.group(1).strip() if summary_match else "复核阶段没有给出总结。"
    retry_focus = [line[2:].strip() for line in text.splitlines() if line.startswith("- ")]
    return MarkdownAgentReview(
        accepted=accepted,
        summary=summary,
        retry_focus=retry_focus,
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

    return "".join(normalized).strip("\n")


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


def _validate_body_heading_lines(lines: list[str], issues: list[MarkdownValidationIssue]) -> None:
    for line_no, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if stripped.startswith("# "):
            issues.append(
                MarkdownValidationIssue(
                    line_no,
                    "body_contains_h1",
                    "正文中不能保留 '# ' 标题，正文一级章节必须使用 '## '。",
                )
            )


def _validate_body_prefix_noise(lines: list[str], issues: list[MarkdownValidationIssue]) -> None:
    noise_re = re.compile(r"^\s*(项目名称|建设单位|客户名称|申报单位|目录)\s*[：:]")
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if noise_re.match(stripped):
            issues.append(
                MarkdownValidationIssue(
                    line_no,
                    "body_prefix_noise",
                    "正文中不应保留项目名称、建设单位或目录等标题前噪音。",
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
