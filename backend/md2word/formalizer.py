from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib import error, request


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<target>[^)]+)\)")
IMAGE_LINK_RE = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<target>[^)]+)\)")
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


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


def load_formalizer_llm_config() -> FormalizerLLMConfig | None:
    base_url = os.getenv("MD2WORD_FORMALIZER_LLM_BASE_URL", "").strip()
    api_key = os.getenv("MD2WORD_FORMALIZER_LLM_API_KEY", "").strip()
    model = os.getenv("MD2WORD_FORMALIZER_LLM_MODEL", "").strip()
    timeout_value = os.getenv("MD2WORD_FORMALIZER_LLM_TIMEOUT", "").strip()
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
    llm_client = llm_client if llm_client is not None else FormalizerLLMClient.from_env()
    steps: list[FormalizeStep] = []
    issues: list[FormalizeIssue] = []

    prepared_source = drop_duplicate_document_title_noise(md_text)
    extracted_tree = extract_heading_tree(prepared_source)
    steps.append(FormalizeStep(name="extract_heading_tree", changed=False))

    corrected_tree = correct_heading_tree(extracted_tree, llm_client=llm_client)
    steps.append(
        FormalizeStep(
            name="correct_heading_tree",
            changed=_heading_tree_payload(extracted_tree) != _heading_tree_payload(corrected_tree),
        )
    )

    tree_issues = validate_heading_tree_json(corrected_tree)
    issues.extend(tree_issues)
    steps.append(FormalizeStep(name="validate_heading_tree_json", changed=False, issues=tree_issues))

    before = md_text
    current = rebuild_markdown_from_heading_tree(prepared_source, corrected_tree)
    steps.append(FormalizeStep(name="rebuild_markdown_from_heading_tree", changed=current != before))

    before = current
    current = clean_body_noise(current, llm_client=llm_client)
    steps.append(FormalizeStep(name="clean_body_noise", changed=current != before))

    image_refs, image_issues = inspect_image_refs(current, source_path=source_path, llm_client=llm_client)
    issues.extend(image_issues)
    steps.append(FormalizeStep(name="inspect_image_refs", changed=False, issues=image_issues))

    before = current
    current, syntax_issues = normalize_supported_markdown_syntax(current, llm_client=llm_client)
    issues.extend(syntax_issues)
    steps.append(FormalizeStep(name="normalize_supported_markdown_syntax", changed=current != before, issues=syntax_issues))

    before = current
    current = remove_ai_response_traces(current, llm_client=llm_client)
    steps.append(FormalizeStep(name="remove_ai_response_traces", changed=current != before))

    before = current
    current = review_wording_for_title(current, extract_document_title(current), llm_client=llm_client)
    steps.append(FormalizeStep(name="review_wording_for_title", changed=current != before))

    return FormalizeResult(
        markdown_text=current,
        document_title=extract_document_title(current),
        heading_tree=corrected_tree,
        images=image_refs,
        steps=steps,
        issues=issues,
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
    rewritten = rewrite_with_llm(
        llm_client,
        "correct_heading_tree",
        json.dumps(_heading_tree_payload(nodes), ensure_ascii=False),
        "Correct the heading tree JSON. Keep exactly one top-level # heading as the document title. Choose the title that matches the article content, keep semantic headings, keep numbering, and remove other # headings, including title variants and appendix-like notes such as usage instructions. Ignore non-content headings such as 目录.",
    )
    if rewritten is not None:
        parsed = _parse_heading_tree_response(rewritten)
        if parsed is not None:
            return parsed

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
    rewritten = rewrite_with_llm(
        llm_client,
        "clean_body_noise",
        md_text,
        "Remove visible backslash escapes from ordinary prose only. Keep required syntax, code blocks, inline code, file paths, and URLs.",
    )
    if rewritten is not None:
        md_text = rewritten
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
        cleaned.append(_replace_outside_inline_code(line, lambda text: escape_re.sub(r"\1", text)))

    return "".join(cleaned).strip("\n") + "\n"


def inspect_image_refs(
    md_text: str,
    source_path: str | Path | None = None,
    llm_client: FormalizerLLMClient | None = None,
) -> tuple[list[ImageRef], list[FormalizeIssue]]:
    rewritten = rewrite_with_llm(
        llm_client,
        "inspect_image_refs",
        md_text,
        "Review image captions and target references. Return Markdown with improved captions if needed, but do not remove images or change structure.",
    )
    if rewritten is not None:
        md_text = rewritten
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
    rewritten = rewrite_with_llm(
        llm_client,
        "normalize_supported_markdown_syntax",
        md_text,
        "Normalize unsupported Markdown syntax into supported Markdown. Remove HTML blocks, footnotes, task list syntax, definition lists, and nested blockquotes. Keep headings, paragraphs, lists, tables, images, and fences.",
    )
    if rewritten is not None:
        md_text = rewritten
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
    rewritten = rewrite_with_llm(
        llm_client,
        "remove_ai_response_traces",
        md_text,
        "Remove obvious AI response traces such as framing phrases, explanatory prefaces, and self-referential completion language. Keep the document content only.",
    )
    if rewritten is not None:
        md_text = rewritten
    trace_re = re.compile(
        r"^\s*(?:以下是|下面是|当然[，,]|好的[，,]|我已(?:经)?|如需|如果你需要|希望这(?:能|可以)|Here is|Below is)\b.*$",
        flags=re.I,
    )
    lines = [line for line in md_text.splitlines() if not trace_re.match(line)]
    return _normalize_blank_lines("\n".join(lines)).rstrip() + "\n"


def review_wording_for_title(
    md_text: str,
    document_title: str,
    llm_client: FormalizerLLMClient | None = None,
) -> str:
    if not document_title:
        return md_text
    rewritten = rewrite_with_llm(
        llm_client,
        "review_wording_for_title",
        md_text,
        f"Review the wording only so it better matches the document title: {document_title}. Do not change facts, section order, or structure.",
    )
    if rewritten is not None:
        md_text = rewritten
    return _normalize_blank_lines(md_text).rstrip() + "\n"


def extract_document_title(md_text: str) -> str:
    for line in md_text.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return ""


def iter_heading_nodes(nodes: list[HeadingNode]):
    for node in nodes:
        yield node
        yield from iter_heading_nodes(node.children)


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
    normalized = re.sub(r"\s+", "", title).strip("：:")
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

    output.append(source_lines[node.line - 1].rstrip())
    children = sorted(node.children, key=lambda item: item.line)
    cursor = node.line + 1

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
        if re.match(rf"^#\s+{re.escape(title)}\s*$", line):
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
