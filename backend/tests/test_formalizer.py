from pathlib import Path

from backend.md2word.formalizer import (
    clean_body_noise,
    correct_heading_tree,
    extract_heading_tree,
    formalize_markdown,
    HeadingNode,
    inspect_image_refs,
    normalize_supported_markdown_syntax,
    rebuild_markdown_from_heading_tree,
    remove_ai_response_traces,
    load_formalizer_llm_config,
    review_wording_for_title,
)


def test_extract_and_correct_heading_tree_keeps_one_document_title():
    tree = extract_heading_tree(
        "## 目录\n\n"
        "# 系统说明书\n\n"
        "## 第一章 概述\n\n"
        "# 系统说明书\n\n"
        "## 第二章 功能\n"
    )

    corrected = correct_heading_tree(tree)

    assert len(corrected) == 1
    assert corrected[0].title == "系统说明书"
    assert [node.title for node in corrected[0].children] == ["第一章 概述", "第二章 功能"]


def test_correct_heading_tree_keeps_duplicate_title_children():
    tree = extract_heading_tree(
        "# 系统说明书\n\n"
        "## 第一章 概述\n\n"
        "# 系统说明书\n\n"
        "### 子节\n"
    )

    corrected = correct_heading_tree(tree)

    assert [node.title for node in corrected[0].children] == ["第一章 概述", "子节"]


def test_rebuild_markdown_from_heading_tree_keeps_original_heading_lines():
    tree = correct_heading_tree(extract_heading_tree("# 系统说明书\n\n## 概述\n\n正文\n"))

    rebuilt = rebuild_markdown_from_heading_tree("# 系统说明书\n\n## 概述\n\n正文\n", tree)

    assert rebuilt.startswith("# 系统说明书")
    assert "## 概述" in rebuilt


def test_rebuild_markdown_from_heading_tree_stops_before_unkept_later_heading():
    source = "# 系统说明书\n\n## 概述\n\n正文\n\n# Word 文档使用说明\n\n粘贴说明\n"
    tree = [HeadingNode(level=1, title="系统说明书", line=1, children=[HeadingNode(level=2, title="概述", line=3)])]

    rebuilt = rebuild_markdown_from_heading_tree(source, tree)

    assert "## 概述" in rebuilt
    assert "正文" in rebuilt
    assert "Word 文档使用说明" not in rebuilt
    assert "粘贴说明" not in rebuilt


def test_formalize_markdown_runs_steps_in_skill_order():
    result = formalize_markdown("# 系统说明书\n\n## 概述\n\n正文\n")

    assert [step.name for step in result.steps] == [
        "extract_heading_tree",
        "correct_heading_tree",
        "validate_heading_tree_json",
        "rebuild_markdown_from_heading_tree",
        "clean_body_noise",
        "inspect_image_refs",
        "normalize_supported_markdown_syntax",
        "remove_ai_response_traces",
        "review_wording_for_title",
    ]
    assert result.document_title == "系统说明书"


def test_formalize_markdown_keeps_documents_without_h1():
    result = formalize_markdown("## 概述\n\n正文\n")

    assert result.document_title == ""
    assert result.markdown_text.startswith("## 概述")
    assert result.markdown_text.endswith("\n")


def test_formalize_markdown_removes_catalog_and_duplicate_title_body():
    result = formalize_markdown(
        "# 系统说明书\n\n"
        "封面噪声\n\n"
        "## 目录\n\n"
        "目录内容\n\n"
        "## 第一章 概述\n\n"
        "正文\n\n"
        "# 系统说明书\n\n"
        "重复标题正文\n\n"
        "## 第二章 功能\n\n"
        "功能正文\n"
    )

    assert "封面噪声" not in result.markdown_text
    assert "## 目录" not in result.markdown_text
    assert "目录内容" not in result.markdown_text
    assert "重复标题正文" not in result.markdown_text
    assert "## 第一章 概述" in result.markdown_text
    assert "## 第二章 功能" in result.markdown_text


def test_clean_body_noise_preserves_code_regions():
    result = clean_body_noise("## 项目\\(概述\\)\n\n正文 A\\.B 和 `C\\.D`\n\n```md\n保留\\*代码\n```")

    assert "## 项目(概述)" in result
    assert "正文 A.B" in result
    assert "`C\\.D`" in result
    assert "保留\\*代码" in result


def test_inspect_image_refs_marks_unsupported_extensions(tmp_path: Path):
    md_path = tmp_path / "doc.md"

    refs, issues = inspect_image_refs("![图示](assets/diagram.svg)", source_path=md_path)

    assert len(refs) == 1
    assert refs[0].supported is False
    assert any(issue.code == "unsupported_image_extension" for issue in issues)


def test_inspect_image_refs_resolves_relative_paths(tmp_path: Path):
    md_path = tmp_path / "doc.md"
    image_path = tmp_path / "images" / "screen.png"
    image_path.parent.mkdir()
    image_path.write_bytes(b"fake")

    refs, issues = inspect_image_refs("![截图](images/screen.png)\n\n[架构](missing.jpg)", source_path=md_path)

    assert len(refs) == 2
    assert refs[0].exists is True
    assert refs[0].supported is True
    assert refs[1].exists is False
    assert any(issue.code == "missing_image_file" for issue in issues)


def test_normalize_supported_markdown_syntax_handles_unsupported_forms():
    result, issues = normalize_supported_markdown_syntax(
        "标题\n---\n\n<div>正文</div>\n\n- [x] 已完成\n\n说明[^1]\n\n[^1]: 脚注\n\n>> 引用"
    )

    assert "## 标题" in result
    assert "正文" in result
    assert "- 已完成" in result
    assert "[^1]" not in result
    assert "> 引用" in result
    assert {issue.code for issue in issues} >= {
        "setext_heading_normalized",
        "unsupported_markdown_normalized",
        "unsupported_markdown_removed",
    }


def test_normalize_supported_markdown_syntax_removes_horizontal_rules():
    result, issues = normalize_supported_markdown_syntax("正文\n\n---\n\n下一段\n")

    assert "---" not in result
    assert "正文" in result
    assert "下一段" in result
    assert any(issue.code == "unsupported_markdown_removed" for issue in issues)


def test_normalize_supported_markdown_syntax_preserves_code_and_blockquotes():
    result, issues = normalize_supported_markdown_syntax(
        "```python\nprint('x')\n```\n\n> 正常引用\n\n- [ ] 待办\n"
    )

    assert "```python" in result
    assert "> 正常引用" in result
    assert "- 待办" in result
    assert any(issue.code == "unsupported_markdown_normalized" for issue in issues)


class StubLLM:
    def __init__(self):
        self.calls = []

    def rewrite(self, step_name: str, markdown_text: str, instruction: str = ""):
        self.calls.append((step_name, markdown_text, instruction))
        if step_name == "correct_heading_tree":
            return '[{"level": 1, "title": "标题", "line": 1, "children": []}]'
        return markdown_text


def test_llm_client_is_used_by_formalizer_hooks(tmp_path: Path):
    llm = StubLLM()

    result = formalize_markdown(
        "# 标题\n\n正文\\(噪声\\)\n\n![图示](missing.png)\n\n> > 引用\n",
        source_path=tmp_path / "doc.md",
        llm_client=llm,
    )

    assert llm.calls
    assert any(call[0] == "correct_heading_tree" for call in llm.calls)
    assert any(call[0] == "clean_body_noise" for call in llm.calls)
    assert any(call[0] == "inspect_image_refs" for call in llm.calls)
    assert any(call[0] == "normalize_supported_markdown_syntax" for call in llm.calls)
    assert any(call[0] == "remove_ai_response_traces" for call in llm.calls)
    assert any(call[0] == "review_wording_for_title" for call in llm.calls)
    assert result.markdown_text.startswith("# 标题")


def test_remove_ai_response_traces_can_be_called_directly_with_llm():
    llm = StubLLM()

    result = remove_ai_response_traces("以下是整理结果。\n\n正文", llm_client=llm)

    assert result.startswith("以下是整理结果。")
    assert any(call[0] == "remove_ai_response_traces" for call in llm.calls)


def test_review_wording_for_title_uses_llm_when_present():
    llm = StubLLM()

    result = review_wording_for_title("正文", "标题", llm_client=llm)

    assert result.endswith("\n")
    assert any(call[0] == "review_wording_for_title" for call in llm.calls)


def test_correct_heading_tree_prompt_requires_single_h1():
    llm = StubLLM()
    tree = extract_heading_tree("# 标题A\n\n# 标题B\n\n## 第一章 概述\n")

    correct_heading_tree(tree, llm_client=llm)

    prompt = next(call[2] for call in llm.calls if call[0] == "correct_heading_tree")
    assert "exactly one top-level # heading" in prompt
    assert "remove other # headings" in prompt


def test_load_formalizer_llm_config_returns_none_without_env(monkeypatch):
    monkeypatch.delenv("MD2WORD_FORMALIZER_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("MD2WORD_FORMALIZER_LLM_API_KEY", raising=False)
    monkeypatch.delenv("MD2WORD_FORMALIZER_LLM_MODEL", raising=False)
    monkeypatch.delenv("MD2WORD_FORMALIZER_LLM_TIMEOUT", raising=False)

    assert load_formalizer_llm_config() is None
