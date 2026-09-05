import json
from pathlib import Path

from backend.md2word.formalizer import (
    FORMALIZE_STAGE_MESSAGES,
    correct_heading_tree,
    extract_heading_tree,
    formalize_markdown,
    iter_formalize_markdown,
    HeadingNode,
    inspect_image_refs,
    normalize_blank_lines,
    normalize_heading_lines,
    normalize_escaped_characters,
    normalize_inline_spacing,
    normalize_supported_markdown_syntax,
    rebuild_markdown_from_heading_tree,
    remove_ai_response_traces,
    load_formalizer_llm_config,
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


def test_rebuild_markdown_from_heading_tree_keeps_intro_body_under_root_title():
    source = "# 系统说明书\n\n导语正文\n\n## 概述\n\n分节正文\n"
    tree = correct_heading_tree(extract_heading_tree(source))

    rebuilt = rebuild_markdown_from_heading_tree(source, tree)

    assert "# 系统说明书" in rebuilt
    assert "导语正文" in rebuilt
    assert "## 概述" in rebuilt
    assert "分节正文" in rebuilt


def test_formalize_markdown_runs_steps_in_skill_order():
    result = formalize_markdown("# 系统说明书\n\n## 概述\n\n正文\n")

    assert [step.name for step in result.steps] == [
        "normalize_escaped_characters",
        "normalize_supported_markdown_syntax",
        "normalize_heading_lines",
        "normalize_blank_lines",
        "normalize_inline_spacing",
        "extract_heading_tree",
        "correct_heading_tree",
        "validate_heading_tree_json",
        "rebuild_markdown_from_heading_tree",
        "inspect_image_refs",
        "remove_ai_response_traces",
    ]
    assert result.document_title == "系统说明书"


def test_iter_formalize_markdown_reports_eleven_stage_messages_before_result():
    events = list(iter_formalize_markdown("# 系统说明书\n\n## 概述\n\n正文\n"))

    stage_names = [event.name for event in events[:-1]]
    assert stage_names == [
        "normalize_escaped_characters",
        "normalize_supported_markdown_syntax",
        "normalize_heading_lines",
        "normalize_blank_lines",
        "normalize_inline_spacing",
        "extract_heading_tree",
        "correct_heading_tree",
        "validate_heading_tree_json",
        "rebuild_markdown_from_heading_tree",
        "inspect_image_refs",
        "remove_ai_response_traces",
    ]
    assert len(stage_names) == 11
    assert [event.message for event in events[:-1]] == [FORMALIZE_STAGE_MESSAGES[name] for name in stage_names]
    assert hasattr(events[-1], "markdown_text")


def test_formalize_markdown_strips_heading_numbering():
    result = formalize_markdown("# 1. 系统说明书\n\n## 一、项目背景\n\n### 2.1 原创方案\n")

    assert result.document_title == "系统说明书"
    assert "# 系统说明书" in result.markdown_text
    assert "## 项目背景" in result.markdown_text
    assert "### 原创方案" in result.markdown_text
    assert "1. 系统说明书" not in result.markdown_text
    assert "一、项目背景" not in result.markdown_text


def test_formalize_markdown_strips_escaped_arabic_heading_numbering():
    result = formalize_markdown("# 标题\n\n### 9\\.4 第四层【材料领域高阶通用技术成果】\n\n正文\n")

    assert "### 第四层【材料领域高阶通用技术成果】" in result.markdown_text
    assert "9\\.4 第四层" not in result.markdown_text
    assert ".4 第四层" not in result.markdown_text


def test_formalize_markdown_strips_mixed_heading_numbering_variants():
    result = formalize_markdown(
        "# 标题\n\n"
        "## 第一章 项目背景\n\n"
        "### （一）建设目标\n\n"
        "#### (1) 交付范围\n\n"
        "##### 2.3.1 核心模块\n\n"
        "###### - 附加说明\n"
    )

    assert "## 项目背景" in result.markdown_text
    assert "### 建设目标" in result.markdown_text
    assert "#### 交付范围" in result.markdown_text
    assert "##### 核心模块" in result.markdown_text
    assert "###### 附加说明" in result.markdown_text
    assert "第一章 项目背景" not in result.markdown_text
    assert "（一）建设目标" not in result.markdown_text
    assert "(1) 交付范围" not in result.markdown_text
    assert "2.3.1 核心模块" not in result.markdown_text


def test_formalize_markdown_keeps_documents_without_h1():
    result = formalize_markdown("## 概述\n\n正文\n")

    assert result.document_title == ""
    assert result.markdown_text.startswith("## 概述")
    assert result.markdown_text.endswith("\n")


def test_formalize_markdown_removes_catalog_and_keeps_duplicate_title_body():
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
    assert "重复标题正文" in result.markdown_text
    assert "## 概述" in result.markdown_text
    assert "## 功能" in result.markdown_text


def test_normalize_escaped_characters_preserves_code_regions():
    result = normalize_escaped_characters("## 项目\\(概述\\)\n\n正文 A\\.B 和 `C\\.D`\n\n```md\n保留\\*代码\n```")

    assert "## 项目(概述)" in result
    assert "正文 A.B" in result
    assert "`C\\.D`" in result
    assert "保留\\*代码" in result


def test_normalize_escaped_characters_preserves_strong_emphasis_markers_in_prose():
    result = normalize_escaped_characters(
        "1. **React‑Generator 候选生成体系**：正文\n\n`**保留代码**`\n\n```md\n**保留围栏代码**\n```"
    )

    assert "**React‑Generator 候选生成体系**：正文" in result
    assert "`**保留代码**`" in result
    assert "**保留围栏代码**" in result


def test_normalize_escaped_characters_preserves_loose_strong_emphasis_markers_in_prose():
    result = normalize_escaped_characters("正文 **“生成即伴随验证” 的可验证材料数字化工具体系 **\n")

    assert "正文 **“生成即伴随验证” 的可验证材料数字化工具体系 **" in result


def test_normalize_heading_lines_strips_heading_numbering():
    result = normalize_heading_lines("# 1. 标题\n\n## （一）概述\n")

    assert result.startswith("# 标题")
    assert "## 概述" in result


def test_normalize_blank_lines_collapses_runs_and_keeps_trailing_newline():
    result = normalize_blank_lines("第一段\n\n\n\n第二段")

    assert result == "第一段\n\n第二段\n"


def test_normalize_blank_lines_treats_whitespace_only_lines_as_blank():
    result = normalize_blank_lines("第一段\n   \n\t\n第二段\n")

    assert result == "第一段\n\n第二段\n"


def test_normalize_inline_spacing_removes_spaces_between_cjk_and_ascii_text():
    result = normalize_inline_spacing(
        "# 标题 OpenAI 接口\n\n正文 API 测试 ( v1.0 ) 与 C++ 模块。\n\n- 列表 HTTP 请求\n\n`保留 API test`\n"
    )

    assert "# 标题OpenAI接口" in result
    assert "正文API测试(v1.0)与C++模块。" in result
    assert "- 列表HTTP请求" in result
    assert "`保留 API test`" in result


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


def test_normalize_supported_markdown_syntax_strips_strong_emphasis_in_prose():
    result, issues = normalize_supported_markdown_syntax(
        "正文 **重点说明**\n\n__另一段强调__\n\n`**保留行内代码**`\n"
    )

    assert "正文 重点说明" in result
    assert "另一段强调" in result
    assert "**重点说明**" not in result
    assert "__另一段强调__" not in result
    assert "`**保留行内代码**`" in result
    assert any(issue.code == "unsupported_markdown_normalized" for issue in issues)


class StubLLM:
    def __init__(self):
        self.calls = []

    def rewrite(self, step_name: str, markdown_text: str, instruction: str = ""):
        self.calls.append((step_name, markdown_text, instruction))
        if step_name == "correct_heading_tree":
            return '[{"level": 1, "title": "标题", "line": 1, "children": []}]'
        if step_name == "remove_ai_response_traces":
            if "如果你需要" in markdown_text or "AI-generated content" in markdown_text or "以下是整理结果" in markdown_text:
                cleaned_lines = []
                for line in markdown_text.splitlines():
                    if "如果你需要" in line or "AI-generated content" in line or "以下是整理结果" in line:
                        continue
                    if line.strip() == ">":
                        continue
                    cleaned_lines.append(line)
                cleaned = "\n".join(cleaned_lines).strip()
                if cleaned:
                    return json.dumps({"action": "rewrite", "reason": "ai_trace", "content": cleaned}, ensure_ascii=False)
                return '{"action":"drop","reason":"ai_trace"}'
            return '{"action":"keep","reason":"content"}'
        return markdown_text


class RewriteEscapedTailLLM:
    def rewrite(self, step_name: str, markdown_text: str, instruction: str = ""):
        if step_name == "correct_heading_tree":
            return None
        if step_name == "remove_ai_response_traces":
            return json.dumps(
                {
                    "action": "rewrite",
                    "reason": "ai_trace",
                    "content": "### 9\\.4 第四层\n\n\\*\\*保留正文\\*\\*",
                },
                ensure_ascii=False,
            )
        return None


def test_llm_client_is_used_by_formalizer_hooks(tmp_path: Path):
    llm = StubLLM()

    result = formalize_markdown(
        "# 标题A\n\n正文\\(噪声\\)\n\n# 标题B\n\n![图示](missing.png)\n\n> 如果你需要，我可以继续输出更多内容\n",
        source_path=tmp_path / "doc.md",
        llm_client=llm,
    )

    assert llm.calls
    assert any(call[0] == "correct_heading_tree" for call in llm.calls)
    assert all(call[0] != "normalize_escaped_characters" for call in llm.calls)
    assert all(call[0] != "inspect_image_refs" for call in llm.calls)
    assert all(call[0] != "normalize_supported_markdown_syntax" for call in llm.calls)
    assert result.markdown_text.startswith("# 标题")


def test_formalize_markdown_keeps_ai_trace_rewrite_output_without_final_cleanup():
    result = formalize_markdown(
        "# 标题\n\n## 尾节\n\n> 如果你需要，我可以继续输出更多内容\n",
        llm_client=RewriteEscapedTailLLM(),
    )

    assert "### 9\\.4 第四层" in result.markdown_text
    assert "\\*\\*保留正文\\*\\*" in result.markdown_text


def test_correct_heading_tree_skips_llm_for_large_tree():
    llm = StubLLM()
    tree = extract_heading_tree(
        "# 标题\n\n"
        + "\n".join(f"## 第{i}节 内容{i}" for i in range(1, 15))
        + "\n"
    )

    correct_heading_tree(tree, llm_client=llm)

    assert all(call[0] != "correct_heading_tree" for call in llm.calls)


def test_remove_ai_response_traces_can_be_called_directly_with_llm():
    llm = StubLLM()

    result = remove_ai_response_traces("以下是整理结果。\n\n正文", llm_client=llm)

    assert "以下是整理结果。" not in result
    assert result.startswith("正文")
    assert any(call[0] == "remove_ai_response_traces" for call in llm.calls)


def test_remove_ai_response_traces_llm_can_drop_blockquote_trace_block():
    llm = StubLLM()

    result = remove_ai_response_traces(
        "正文\n\n> 如果你需要，我可以继续输出 8 个 UI 页面的 AI 绘图提示词。\n>\n> (Note: May contain AI-generated content.)\n",
        llm_client=llm,
    )

    assert "如果你需要" not in result
    assert "AI-generated content" not in result
    assert "正文" in result
    assert any(call[0] == "remove_ai_response_traces" for call in llm.calls)


def test_remove_ai_response_traces_only_sends_last_section_to_llm():
    llm = StubLLM()

    result = remove_ai_response_traces(
        "# 第一节\n\n"
        "保留内容\n\n"
        "## 第二节\n\n"
        "段落一\n\n"
        "段落二\n\n"
        "段落三\n\n"
        "段落四\n\n"
        "段落五\n\n"
        "段落六\n\n"
        "正常内容\n\n"
        "> (Note: May contain AI-generated content.)\n",
        llm_client=llm,
    )

    ai_calls = [call for call in llm.calls if call[0] == "remove_ai_response_traces"]
    assert len(ai_calls) == 1
    assert ai_calls[0][1].startswith("正常内容")
    assert "# 第一节" in result
    assert "保留内容" in result
    assert "第二节" in result
    assert "段落一" in result
    assert "段落六" in result


def test_remove_ai_response_traces_removes_blockquote_ai_fragments():
    result = remove_ai_response_traces(
        "正文\n\n> 如果你需要，我可以继续输出 8 个 UI 页面的 AI 绘图提示词。\n>\n> (Note: May contain AI-generated content.)\n"
    )

    assert "如果你需要" not in result
    assert "AI-generated content" not in result
    assert "\n>\n" not in result
    assert "正文" in result


def test_correct_heading_tree_prompt_requires_single_h1():
    llm = StubLLM()
    tree = extract_heading_tree("# 标题A\n\n# 标题B\n\n## 第一章 概述\n")

    correct_heading_tree(tree, llm_client=llm)

    prompt = next(call[2] for call in llm.calls if call[0] == "correct_heading_tree")
    assert "exactly one top-level # heading" in prompt
    assert "remove other # headings" in prompt
    assert "Normalize every heading title by stripping all numbering-like prefixes" in prompt
    assert "1.2" in prompt
    assert "第1章" in prompt
    assert "9\\.4" not in prompt


def test_load_formalizer_llm_config_returns_none_without_env(monkeypatch):
    monkeypatch.delenv("MD2WORD_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("MD2WORD_LLM_API_KEY", raising=False)
    monkeypatch.delenv("MD2WORD_LLM_MODEL", raising=False)
    monkeypatch.delenv("MD2WORD_LLM_CLEANER_TIMEOUT", raising=False)

    assert load_formalizer_llm_config() is None
