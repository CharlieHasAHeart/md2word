from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator
from urllib import error, request


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
CHINESE_SECTION_RE = re.compile(r"^[一二三四五六七八九十百千万零〇两]+[、.．]\s*")
PAREN_SECTION_RE = re.compile(r"^[（(]\s*[一二三四五六七八九十百千万零〇两]+\s*[)）]\s*")
ARABIC_SECTION_RE = re.compile(r"^\d+(?:\.\d+)*(?:\.)?(?:[、．.)）])?\s*")
CHAPTER_LABEL_RE = re.compile(r"^第\s*[一二三四五六七八九十百千万零〇两\d]+(?:章|节|部分|篇|卷)\s*")
PAREN_ARABIC_RE = re.compile(r"^[（(]\s*\d+(?:\.\d+)*\s*[)）]\s*")
LEADING_LIST_MARKER_RE = re.compile(r"^(?:[-*+]|[•·▪◦‣])\s+")
LEADING_PUNCTUATION_RE = re.compile(r"^(?:\.)+[ \t]*")
IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<target>[^)]+)\)")
IMAGE_LINK_RE = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<target>[^)]+)\)")
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
AI_TRACE_LLM_CONTEXT_BLOCKS = 1
LEXICAL_CLEANUP_MAX_ROUNDS = 3
AI_TRACE_LINE_RE = re.compile(
    r"^\s*(?:>\s*)*(?:以下是|下面是|当然[，,]|好的[，,]|我已(?:经)?|如需|如果你需要|希望这(?:能|可以)|Here is|Below is)\b.*$",
    flags=re.I,
)
AI_TRACE_NOTE_RE = re.compile(
    r"^\s*(?:>\s*)*\(?Note:\s*May contain AI-generated content\.?\)?\s*$",
    flags=re.I,
)
AI_TRACE_CANDIDATE_RE = re.compile(
    r"(?:如果你需要|继续输出|继续生成|AI-generated content|May contain AI-generated content|Here is|Below is|以下是|下面是|绘图提示词|prompt|提示词)",
    flags=re.I,
)


@dataclass(frozen=True)
class HeadingNode:
    level: int
    title: str
    line: int
    children: list["HeadingNode"] = field(default_factory=list)


@dataclass(frozen=True)
class ImageRef:
    line: int
    caption: str
    target: str
    resolved_path: str
    exists: bool
    supported: bool


@dataclass(frozen=True)
class FormalizeIssue:
    step: str
    code: str
    message: str
    line: int | None = None


@dataclass(frozen=True)
class FormalizeStep:
    name: str
    changed: bool
    issues: list[FormalizeIssue] = field(default_factory=list)


@dataclass(frozen=True)
class FormalizeResult:
    markdown_text: str
    document_title: str
    heading_tree: list[HeadingNode]
    images: list[ImageRef]
    steps: list[FormalizeStep]
    issues: list[FormalizeIssue]


@dataclass(frozen=True)
class FormalizeProgress:
    name: str
    message: str


@dataclass(frozen=True)
class FormalizerLLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout: float


class FormalizerLLMClient:
    def __init__(self, config: FormalizerLLMConfig):
        self.config = config

    @classmethod
    def from_env(cls) -> "FormalizerLLMClient | None":
        config = load_formalizer_llm_config()
        return cls(config) if config is not None else None

    def rewrite(self, step_name: str, markdown_text: str, instruction: str = "") -> str | None:
        payload = {
            "model": self.config.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": "You are a Markdown formalizer."},
                {
                    "role": "user",
                    "content": "\n\n".join(
                        [
                            f"Step: {step_name}",
                            instruction.strip(),
                            "Return Markdown or JSON only.",
                            markdown_text,
                        ]
                    ).strip(),
                },
            ],
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self.config.base_url.rstrip("/") + "/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.config.timeout) as response:
                parsed = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
            return None
        try:
            content = parsed["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None
        content = (content or "").strip()
        return content or None


FORMALIZE_STAGE_MESSAGES = {
    "clean_body_noise": "正在清理正文噪音",
    "drop_duplicate_document_title_noise": "正在清理重复标题",
    "extract_heading_tree": "正在提取标题结构",
    "correct_heading_tree": "正在修正标题层级",
    "validate_heading_tree_json": "正在校验标题结构",
    "rebuild_markdown_from_heading_tree": "正在重建正文结构",
    "inspect_image_refs": "正在检查图片引用",
    "normalize_supported_markdown_syntax": "正在规范 Markdown 语法",
    "remove_ai_response_traces": "正在移除 AI 痕迹",
    "finalize_markdown_cleanup": "正在执行最终清理",
}


def load_formalizer_llm_config() -> FormalizerLLMConfig | None:
    base_url = os.getenv("MD2WORD_LLM_BASE_URL", "").strip()
    api_key = os.getenv("MD2WORD_LLM_API_KEY", "").strip()
    model = os.getenv("MD2WORD_LLM_MODEL", "").strip()
    timeout_value = os.getenv("MD2WORD_LLM_CLEANER_TIMEOUT", "").strip()
    if not base_url or not api_key or not model or not timeout_value:
        return None
    return FormalizerLLMConfig(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout=float(timeout_value),
    )


def rewrite_with_llm(
    llm_client: FormalizerLLMClient | None,
    step_name: str,
    markdown_text: str,
    instruction: str,
) -> str | None:
    if llm_client is None:
        return None
    return llm_client.rewrite(step_name, markdown_text, instruction=instruction)


def formalize_markdown(
    md_text: str,
    source_path: str | Path | None = None,
    llm_client: FormalizerLLMClient | None = None,
) -> FormalizeResult:
    result: FormalizeResult | None = None
    for event in iter_formalize_markdown(md_text, source_path=source_path, llm_client=llm_client):
        if isinstance(event, FormalizeResult):
            result = event
    if result is None:
        raise RuntimeError("Formalize pipeline did not produce a result.")
    return result


def iter_formalize_markdown(
    md_text: str,
    source_path: str | Path | None = None,
    llm_client: FormalizerLLMClient | None = None,
) -> Iterator[FormalizeProgress | FormalizeResult]:
    llm_client = llm_client if llm_client is not None else FormalizerLLMClient.from_env()
    steps: list[FormalizeStep] = []
    issues: list[FormalizeIssue] = []

    yield _formalize_progress("clean_body_noise")
    before = md_text
    current = clean_body_noise(md_text, llm_client=llm_client)
    steps.append(FormalizeStep(name="clean_body_noise", changed=current != before))

    yield _formalize_progress("drop_duplicate_document_title_noise")
    prepared_source = drop_duplicate_document_title_noise(current)

    yield _formalize_progress("extract_heading_tree")
    extracted_tree = extract_heading_tree(prepared_source)
    steps.append(FormalizeStep(name="extract_heading_tree", changed=False))

    yield _formalize_progress("correct_heading_tree")
    corrected_tree = correct_heading_tree(extracted_tree, llm_client=llm_client)
    steps.append(
        FormalizeStep(
            name="correct_heading_tree",
            changed=_heading_tree_payload(extracted_tree) != _heading_tree_payload(corrected_tree),
        )
    )

    yield _formalize_progress("validate_heading_tree_json")
    tree_issues = validate_heading_tree_json(corrected_tree)
    issues.extend(tree_issues)
    steps.append(FormalizeStep(name="validate_heading_tree_json", changed=False, issues=tree_issues))

    yield _formalize_progress("rebuild_markdown_from_heading_tree")
    before = md_text
    current = rebuild_markdown_from_heading_tree(prepared_source, corrected_tree)
    steps.append(FormalizeStep(name="rebuild_markdown_from_heading_tree", changed=current != before))

    yield _formalize_progress("inspect_image_refs")
    image_refs, image_issues = inspect_image_refs(current, source_path=source_path, llm_client=llm_client)
    issues.extend(image_issues)
    steps.append(FormalizeStep(name="inspect_image_refs", changed=False, issues=image_issues))

    yield _formalize_progress("normalize_supported_markdown_syntax")
    before = current
    current, syntax_issues = normalize_supported_markdown_syntax(current, llm_client=llm_client)
    issues.extend(syntax_issues)
    steps.append(FormalizeStep(name="normalize_supported_markdown_syntax", changed=current != before, issues=syntax_issues))

    yield _formalize_progress("remove_ai_response_traces")
    before = current
    current = remove_ai_response_traces(current, llm_client=llm_client)
    steps.append(FormalizeStep(name="remove_ai_response_traces", changed=current != before))

    yield _formalize_progress("finalize_markdown_cleanup")
    before = current
    current = finalize_markdown_cleanup(current, llm_client=llm_client)
    steps.append(FormalizeStep(name="finalize_markdown_cleanup", changed=current != before))

    yield FormalizeResult(
        markdown_text=current,
        document_title=extract_document_title(current),
        heading_tree=corrected_tree,
        images=image_refs,
        steps=steps,
        issues=issues,
    )


def _formalize_progress(step_name: str) -> FormalizeProgress:
    return FormalizeProgress(
        name=step_name,
        message=FORMALIZE_STAGE_MESSAGES[step_name],
    )


def extract_heading_tree(md_text: str) -> list[HeadingNode]:
    roots: list[HeadingNode] = []
    stack: list[HeadingNode] = []

    for line_no, line in enumerate(md_text.splitlines(), start=1):
        match = HEADING_RE.match(line)
        if not match:
            continue
        node = HeadingNode(level=len(match.group(1)), title=match.group(2).strip(), line=line_no, children=[])
        while stack and stack[-1].level >= node.level:
            stack.pop()
        if stack:
            stack[-1].children.append(node)
        else:
            roots.append(node)
        stack.append(node)

    return roots


def correct_heading_tree(
    nodes: list[HeadingNode],
    llm_client: FormalizerLLMClient | None = None,
) -> list[HeadingNode]:
    fallback = _correct_heading_tree_locally(nodes)
    if not _should_try_llm_for_heading_tree(nodes):
        return fallback
    rewritten = rewrite_with_llm(
        llm_client,
        "correct_heading_tree",
        json.dumps(_heading_tree_payload(nodes), ensure_ascii=False),
        "Correct the heading tree JSON. Keep exactly one top-level # heading as the document title. Choose the title that matches the article content, keep semantic headings, and remove other # headings, including title variants and appendix-like notes such as usage instructions. Ignore non-content headings such as 目录. Normalize every heading title by stripping all numbering-like prefixes before returning JSON. The heading text itself must not start with sequence numbers, chapter numbers, or list markers. Remove prefixes such as 1., 1.2, .4, （一）, (1), 第1章, 第一章, and bullet/list markers. Return clean title text only.",
    )
    if rewritten is not None:
        parsed = _parse_heading_tree_response(rewritten)
        if parsed is not None:
            return parsed
    return fallback


def _correct_heading_tree_locally(nodes: list[HeadingNode]) -> list[HeadingNode]:
    first_h1 = next((node for node in iter_heading_nodes(nodes) if node.level == 1), None)
    if first_h1 is None:
        return _filter_non_content_headings(nodes, document_title="")

    children: list[HeadingNode] = []
    for node in nodes:
        if node.line < first_h1.line:
            continue
        if node.line == first_h1.line:
            children.extend(_filter_non_content_headings(node.children, first_h1.title))
            continue
        if _is_non_content_heading(node.title):
            continue
        if node.level == 1:
            children.extend(_filter_non_content_headings(node.children, first_h1.title))
            continue
        children.append(HeadingNode(level=node.level, title=node.title, line=node.line, children=_filter_non_content_headings(node.children, first_h1.title)))

    return [HeadingNode(level=first_h1.level, title=first_h1.title, line=first_h1.line, children=children)]


def validate_heading_tree_json(nodes: list[HeadingNode]) -> list[FormalizeIssue]:
    payload = _heading_tree_payload(nodes)
    try:
        json.loads(json.dumps(payload, ensure_ascii=False))
    except (TypeError, ValueError) as exc:
        return [
            FormalizeIssue(
                step="validate_heading_tree_json",
                code="invalid_heading_tree_json",
                message=f"Corrected heading tree is not JSON serializable: {exc}",
            )
        ]
    return []


def rebuild_markdown_from_heading_tree(md_text: str, tree: list[HeadingNode]) -> str:
    source_lines = md_text.splitlines()
    if not source_lines or not tree:
        return md_text.strip("\n") + ("\n" if md_text.strip() else "")

    root = tree[0]
    section_end = _section_end_for_corrected_tree(source_lines, tree)
    rebuilt: list[str] = []
    _rebuild_node(root, source_lines, rebuilt, section_end=section_end, skip_body=True)
    return _normalize_blank_lines("\n".join(rebuilt)).rstrip() + "\n"


def clean_body_noise(md_text: str, llm_client: FormalizerLLMClient | None = None) -> str:
    return _stabilize_lexical_cleanup(md_text)


def finalize_markdown_cleanup(md_text: str, llm_client: FormalizerLLMClient | None = None) -> str:
    cleaned = _stabilize_lexical_cleanup(md_text)
    return _normalize_document_heading_lines(cleaned)


def _stabilize_lexical_cleanup(md_text: str) -> str:
    current = md_text
    for _ in range(LEXICAL_CLEANUP_MAX_ROUNDS):
        updated = _clean_body_noise_pass(current)
        if updated == current:
            return updated
        current = updated
    return current


def _clean_body_noise_pass(md_text: str) -> str:
    escape_re = re.compile(r"\\([+\-*/.()[\]{}])")
    cleaned: list[str] = []
    in_fence = False
    fence_char = ""

    for line in md_text.splitlines(keepends=True):
        fence_match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence_match:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
            elif marker[0] == fence_char:
                in_fence = False
                fence_char = ""
            cleaned.append(line)
            continue
        if in_fence:
            cleaned.append(line)
            continue
        cleaned.append(
            _replace_outside_inline_code(
                line,
                lambda text: _strip_strong_emphasis_markers(escape_re.sub(r"\1", text)),
            )
        )

    return _with_trailing_newline(_normalize_blank_lines("".join(cleaned)))


def inspect_image_refs(
    md_text: str,
    source_path: str | Path | None = None,
    llm_client: FormalizerLLMClient | None = None,
) -> tuple[list[ImageRef], list[FormalizeIssue]]:
    base_dir = Path(source_path).resolve().parent if source_path else Path.cwd()
    refs: list[ImageRef] = []
    issues: list[FormalizeIssue] = []

    for line_no, line in enumerate(md_text.splitlines(), start=1):
        for caption, target in _iter_image_targets(line):
            clean_target = target.strip().strip("<>")
            resolved = Path(clean_target)
            if not resolved.is_absolute():
                resolved = base_dir / clean_target
            supported = resolved.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
            exists = resolved.exists()
            refs.append(
                ImageRef(
                    line=line_no,
                    caption=caption.strip(),
                    target=clean_target,
                    resolved_path=str(resolved),
                    exists=exists,
                    supported=supported,
                )
            )
            if not supported:
                issues.append(
                    FormalizeIssue(
                        step="inspect_image_refs",
                        code="unsupported_image_extension",
                        message=f"Unsupported image extension: {clean_target}",
                        line=line_no,
                    )
                )
            elif not exists:
                issues.append(
                    FormalizeIssue(
                        step="inspect_image_refs",
                        code="missing_image_file",
                        message=f"Image file does not exist: {clean_target}",
                        line=line_no,
                    )
                )

    return refs, issues


def normalize_supported_markdown_syntax(
    md_text: str,
    llm_client: FormalizerLLMClient | None = None,
) -> tuple[str, list[FormalizeIssue]]:
    issues: list[FormalizeIssue] = []
    output: list[str] = []
    pending_plain_line: tuple[int, str] | None = None
    in_fence = False
    fence_char = ""

    lines = md_text.splitlines()
    for line_no, line in enumerate(lines, start=1):
        fence_match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence_match:
            _flush_pending_plain_line(output, pending_plain_line)
            pending_plain_line = None
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
            elif marker[0] == fence_char:
                in_fence = False
                fence_char = ""
            output.append(line)
            continue

        if in_fence:
            output.append(line)
            continue

        if pending_plain_line is not None:
            pending_line_no, pending_text = pending_plain_line
            if re.match(r"^\s*=+\s*$", line):
                output.append(f"# {pending_text.strip()}")
                issues.append(_syntax_issue("setext_heading_normalized", pending_line_no))
                pending_plain_line = None
                continue
            if re.match(r"^\s*-{3,}\s*$", line):
                output.append(f"## {pending_text.strip()}")
                issues.append(_syntax_issue("setext_heading_normalized", pending_line_no))
                pending_plain_line = None
                continue
            if _contains_footnote_marker(pending_text) or _contains_footnote_marker(line):
                pending_text = _strip_footnote_markers(pending_text)
                issues.append(_syntax_issue("unsupported_markdown_removed", pending_line_no))
            output.append(pending_text)
            pending_plain_line = None

        if re.match(r"^\s*[-*_]{3,}\s*$", line):
            issues.append(_syntax_issue("unsupported_markdown_removed", line_no))
            continue

        if _is_setext_candidate(line):
            pending_plain_line = (line_no, line)
            continue

        normalized_line = _normalize_one_supported_syntax_line(line)
        if normalized_line is None:
            issues.append(_syntax_issue("unsupported_markdown_removed", line_no))
            continue
        if normalized_line != line:
            issues.append(_syntax_issue("unsupported_markdown_normalized", line_no))
        if _contains_footnote_marker(normalized_line):
            normalized_line = _strip_footnote_markers(normalized_line)
            issues.append(_syntax_issue("unsupported_markdown_removed", line_no))
        output.append(normalized_line)

    _flush_pending_plain_line(output, pending_plain_line)
    return _normalize_blank_lines("\n".join(output)).rstrip() + "\n", issues


def remove_ai_response_traces(md_text: str, llm_client: FormalizerLLMClient | None = None) -> str:
    cleaned_blocks: list[str] = []
    for block, use_llm in _split_markdown_sections_for_ai_cleanup(md_text):
        decision = _classify_ai_trace_block(block, llm_client=llm_client) if use_llm else None
        if decision is not None:
            action = decision.get("action", "")
            if action == "drop":
                continue
            if action == "rewrite":
                rewritten = decision.get("content", "")
                if isinstance(rewritten, str) and rewritten.strip():
                    block = rewritten
        block = _remove_ai_trace_block_with_rules(block)
        if block.strip():
            cleaned_blocks.append(block.strip("\n"))
    return _normalize_blank_lines("\n\n".join(cleaned_blocks)).rstrip() + "\n"


def extract_document_title(md_text: str) -> str:
    for line in md_text.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return strip_heading_numbering(match.group(1))
    return ""


def iter_heading_nodes(nodes: list[HeadingNode]):
    for node in nodes:
        yield node
        yield from iter_heading_nodes(node.children)


def _should_try_llm_for_heading_tree(nodes: list[HeadingNode]) -> bool:
    heading_count = sum(1 for _ in iter_heading_nodes(nodes))
    if heading_count == 0 or heading_count > 12:
        return False

    h1_titles = [strip_heading_numbering(node.title) for node in iter_heading_nodes(nodes) if node.level == 1]
    distinct_h1_titles = {title for title in h1_titles if title}
    if len(distinct_h1_titles) > 1:
        return True

    return any(_is_non_content_heading(node.title) for node in iter_heading_nodes(nodes))


def _filter_non_content_headings(nodes: list[HeadingNode], document_title: str) -> list[HeadingNode]:
    kept: list[HeadingNode] = []
    for node in nodes:
        if _is_non_content_heading(node.title):
            continue
        kept.append(
            HeadingNode(
                level=node.level,
                title=node.title,
                line=node.line,
                children=_filter_non_content_headings(node.children, document_title),
            )
        )
    return kept


def _is_non_content_heading(title: str) -> bool:
    normalized = re.sub(r"\s+", "", strip_heading_numbering(title)).strip("：:")
    return normalized in {"目录"} or "使用说明" in normalized


def _heading_tree_payload(nodes: list[HeadingNode]) -> list[dict]:
    return [asdict(node) for node in nodes]


def _parse_heading_tree_response(text: str | None) -> list[HeadingNode] | None:
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        nodes = payload.get("tree", payload)
    else:
        nodes = payload
    try:
        return [_parse_heading_node(node) for node in nodes]
    except (TypeError, KeyError, ValueError):
        return None


def _parse_heading_node(node: dict) -> HeadingNode:
    children = node.get("children") or []
    return HeadingNode(
        level=int(node["level"]),
        title=str(node["title"]),
        line=int(node["line"]),
        children=[_parse_heading_node(child) for child in children],
    )


def _rebuild_node(
    node: HeadingNode,
    source_lines: list[str],
    output: list[str],
    section_end: int,
    skip_body: bool = False,
) -> None:
    if node.line < 1 or node.line > len(source_lines):
        return

    output.append(_normalize_heading_line(source_lines[node.line - 1].rstrip()))
    children = sorted(node.children, key=lambda item: item.line)
    cursor = node.line + 1

    if skip_body:
        if children:
            if not _has_heading_in_range(source_lines, cursor, children[0].line - 1):
                _append_body_range(output, source_lines, cursor, children[0].line - 1)
        else:
            _append_body_range(output, source_lines, cursor, section_end)

    for index, child in enumerate(children):
        child_end = section_end
        if index + 1 < len(children):
            child_end = min(child_end, children[index + 1].line - 1)
        if not skip_body:
            _append_body_range(output, source_lines, cursor, child.line - 1)
        _rebuild_node(child, source_lines, output, child_end, skip_body=False)
        cursor = child_end + 1

    if not skip_body:
        _append_body_range(output, source_lines, cursor, section_end)


def _append_body_range(output: list[str], source_lines: list[str], start_line: int, end_line: int) -> None:
    for line_no in range(start_line, end_line + 1):
        if line_no < 1 or line_no > len(source_lines):
            continue
        line = source_lines[line_no - 1]
        if not HEADING_RE.match(line):
            output.append(line.rstrip())


def _has_heading_in_range(source_lines: list[str], start_line: int, end_line: int) -> bool:
    for line_no in range(start_line, end_line + 1):
        if line_no < 1 or line_no > len(source_lines):
            continue
        if HEADING_RE.match(source_lines[line_no - 1]):
            return True
    return False


def _section_end_for_corrected_tree(source_lines: list[str], tree: list[HeadingNode]) -> int:
    kept_heading_lines = {node.line for node in iter_heading_nodes(tree) if node.line > 0}
    if not kept_heading_lines:
        return len(source_lines)

    last_kept_heading_line = max(kept_heading_lines)
    for line_no, line in enumerate(source_lines, start=1):
        if line_no > last_kept_heading_line and line_no not in kept_heading_lines and HEADING_RE.match(line):
            return line_no - 1
    return len(source_lines)


def _replace_outside_inline_code(line: str, replacer) -> str:
    parts = line.split("`")
    for index in range(0, len(parts), 2):
        parts[index] = replacer(parts[index])
    return "`".join(parts)


def _strip_strong_emphasis_markers(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", lambda match: match.group(1).strip(), text)
    text = re.sub(r"__(.+?)__", lambda match: match.group(1).strip(), text)
    return text


def _normalize_document_heading_lines(md_text: str) -> str:
    normalized: list[str] = []
    in_fence = False
    fence_char = ""

    for line in md_text.splitlines(keepends=True):
        fence_match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence_match:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
            elif marker[0] == fence_char:
                in_fence = False
                fence_char = ""
            normalized.append(line)
            continue
        if in_fence:
            normalized.append(line)
            continue

        line_ending = "\n" if line.endswith("\n") else ""
        content = line[:-1] if line_ending else line
        normalized.append(_normalize_heading_line(content) + line_ending)

    return _with_trailing_newline(_normalize_blank_lines("".join(normalized)))


def _iter_image_targets(line: str):
    consumed_spans: list[tuple[int, int]] = []
    for match in IMAGE_RE.finditer(line):
        consumed_spans.append(match.span())
        yield match.group("alt"), match.group("target")

    for match in IMAGE_LINK_RE.finditer(line):
        if any(start <= match.start() < end for start, end in consumed_spans):
            continue
        target = match.group("target")
        if Path(target.strip().strip("<>")).suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
            yield match.group("text"), target


def _is_setext_candidate(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(("#", "-", "*", "+", ">", "|", "```", "~~~", "<")):
        return False
    if re.match(r"^\d+[.)]\s+", stripped):
        return False
    return True


def _normalize_one_supported_syntax_line(line: str) -> str | None:
    stripped = line.strip()
    if re.match(r"^\[\^[^\]]+\]:", stripped):
        return None
    line = re.sub(r"\[\^[^\]]+\]", "", line)
    line = re.sub(r"^(\s*)[-+*]\s+\[[ xX]\]\s+", r"\1- ", line)
    line = re.sub(r"^(\s*)>{2,}\s*", r"\1> ", line)
    if re.search(r"</?[\w:-]+(?:\s[^>]*)?>", line):
        line = re.sub(r"</?[\w:-]+(?:\s[^>]*)?>", "", line)
    return line if line.strip() else ""


def _syntax_issue(code: str, line: int) -> FormalizeIssue:
    return FormalizeIssue(
        step="normalize_supported_markdown_syntax",
        code=code,
        message=code.replace("_", " "),
        line=line,
    )


def _flush_pending_plain_line(output: list[str], pending: tuple[int, str] | None) -> None:
    if pending is not None:
        output.append(pending[1])


def _normalize_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.replace("\r\n", "\n").replace("\r", "\n"))


def _with_trailing_newline(text: str) -> str:
    stripped = text.strip("\n")
    return stripped + ("\n" if stripped else "")


def _split_markdown_sections_for_ai_cleanup(md_text: str) -> list[tuple[str, bool]]:
    normalized = md_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    heading_lines = [index for index, line in enumerate(lines) if HEADING_RE.match(line)]
    if not heading_lines:
        stripped = normalized.strip()
        return _split_section_for_ai_cleanup(stripped, use_llm=True) if stripped else []

    sections: list[tuple[str, bool]] = []
    first_heading = heading_lines[0]
    if any(line.strip() for line in lines[:first_heading]):
        prefix = "\n".join(lines[:first_heading]).strip("\n")
        if prefix.strip():
            sections.append((prefix, False))

    for position, start in enumerate(heading_lines):
        end = heading_lines[position + 1] if position + 1 < len(heading_lines) else len(lines)
        block = "\n".join(lines[start:end]).strip("\n")
        if not block.strip():
            continue
        sections.extend(_split_section_for_ai_cleanup(block, use_llm=position == len(heading_lines) - 1))
    return sections


def _split_section_for_ai_cleanup(block: str, use_llm: bool) -> list[tuple[str, bool]]:
    if not use_llm:
        return [(block, False)]

    paragraph_blocks = _split_markdown_paragraph_blocks(block)
    candidate_start = _find_ai_trace_candidate_start(paragraph_blocks)
    if candidate_start is None:
        return [(block, False)]

    prefix = "\n\n".join(paragraph_blocks[:candidate_start]).strip("\n")
    tail = "\n\n".join(paragraph_blocks[candidate_start:]).strip("\n")
    sections: list[tuple[str, bool]] = []
    if prefix:
        sections.append((prefix, False))
    if tail:
        sections.append((tail, True))
    return sections


def _split_markdown_paragraph_blocks(block: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in block.split("\n"):
        if line.strip():
            current.append(line)
            continue
        if current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def _find_ai_trace_candidate_start(paragraph_blocks: list[str]) -> int | None:
    candidate_indices = [index for index, block in enumerate(paragraph_blocks) if _is_ai_trace_candidate_block(block)]
    if not candidate_indices:
        return None
    return max(0, candidate_indices[0] - AI_TRACE_LLM_CONTEXT_BLOCKS)


def _classify_ai_trace_block(
    block: str,
    llm_client: FormalizerLLMClient | None = None,
) -> dict[str, str] | None:
    if llm_client is None:
        return None
    rewritten = rewrite_with_llm(
        llm_client,
        "remove_ai_response_traces",
        block,
        (
            "Classify whether this Markdown block is an AI response trace. "
            "Return JSON only with keys action, reason, and content. "
            "action must be one of keep, drop, or rewrite. "
            "Use drop for assistant framing, offer-to-continue text, prompt-generation offers, "
            "meta notes such as May contain AI-generated content, and self-referential completion language. "
            "Use rewrite only when the block mixes useful document content with removable AI framing. "
            "Use keep for normal document content. Preserve Markdown syntax in content."
        ),
    )
    if not rewritten:
        return None
    try:
        payload = json.loads(rewritten)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    action = payload.get("action")
    if action not in {"keep", "drop", "rewrite"}:
        return None
    result = {"action": str(action), "reason": str(payload.get("reason", ""))}
    content = payload.get("content")
    if isinstance(content, str):
        result["content"] = content
    return result


def _is_ai_trace_candidate_block(block: str) -> bool:
    lines = block.splitlines()
    if any(AI_TRACE_LINE_RE.match(line) or AI_TRACE_NOTE_RE.match(line) for line in lines):
        return True
    if any(line.lstrip().startswith(">") for line in lines):
        return True
    return bool(AI_TRACE_CANDIDATE_RE.search(block))


def _remove_ai_trace_block_with_rules(block: str) -> str:
    blank_quote_re = re.compile(r"^\s*(?:>\s*)+$")
    lines = block.splitlines()
    meaningful_lines = [line for line in lines if line.strip()]
    if meaningful_lines and all(
        AI_TRACE_LINE_RE.match(line) or AI_TRACE_NOTE_RE.match(line) or blank_quote_re.match(line)
        for line in meaningful_lines
    ):
        return ""

    cleaned: list[str] = []
    removed_trace_block = False
    for line in lines:
        if AI_TRACE_LINE_RE.match(line) or AI_TRACE_NOTE_RE.match(line):
            removed_trace_block = True
            continue
        if removed_trace_block and blank_quote_re.match(line):
            continue
        removed_trace_block = False
        cleaned.append(line)
    return "\n".join(cleaned).strip("\n")


def _contains_footnote_marker(text: str) -> bool:
    return bool(re.search(r"\[\^[^\]]+\]", text))


def _strip_footnote_markers(text: str) -> str:
    return re.sub(r"\[\^[^\]]+\]", "", text)


def drop_duplicate_document_title_noise(md_text: str) -> str:
    title = extract_document_title(md_text)
    if not title:
        return md_text

    lines = md_text.splitlines()
    title_seen = False
    output: list[str] = []
    skip_body = False

    for line in lines:
        if re.match(rf"^#\s+{re.escape(title)}\s*$", _normalize_heading_line(line)):
            if title_seen:
                skip_body = True
                continue
            title_seen = True
            output.append(line)
            continue

        if skip_body:
            if HEADING_RE.match(line):
                skip_body = False
                output.append(line)
            continue

        output.append(line)

    return _normalize_blank_lines("\n".join(output)).rstrip() + "\n"


def strip_heading_numbering(title: str) -> str:
    value = title.strip()
    patterns = (
        CHAPTER_LABEL_RE,
        PAREN_SECTION_RE,
        PAREN_ARABIC_RE,
        CHINESE_SECTION_RE,
        ARABIC_SECTION_RE,
        LEADING_LIST_MARKER_RE,
        LEADING_PUNCTUATION_RE,
    )
    while True:
        previous = value
        for pattern in patterns:
            value = pattern.sub("", value).strip()
        if value == previous:
            break
    return value


def _normalize_heading_line(line: str) -> str:
    match = HEADING_RE.match(line)
    if not match:
        return line
    title = strip_heading_numbering(match.group(2))
    return f"{match.group(1)} {title}" if title else line
