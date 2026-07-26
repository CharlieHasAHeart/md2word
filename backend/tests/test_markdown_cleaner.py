from backend.md2word.markdown_cleaner import (
    MarkdownCleaningError,
    MarkdownAgentReview,
    clean_markdown_with_llm_loop,
    load_agent_reference_markdown,
    load_allowed_syntax_reference,
    load_example_template_reference,
    normalize_markdown_headings,
    prepare_markdown_for_conversion,
    validate_conversion_body_markdown,
    validate_markdown,
)


class FakeCleaner:
    def __init__(self, rewrites, reviews=None):
        self.rewrites = list(rewrites)
        self.reviews = list(reviews or [])
        self.calls = []

    def rewrite(self, md_text: str, review_feedback: str = ""):
        self.calls.append((md_text, review_feedback))
        return self.rewrites.pop(0)

    def review(self, original_md: str, candidate_md: str):
        if self.reviews:
            return self.reviews.pop(0)
        return MarkdownAgentReview(
            accepted=True,
            summary="语义结构复核通过。",
        )


class SpyCleaner(FakeCleaner):
    def __init__(self):
        super().__init__(rewrites=[])
        self.requests = []

    def rewrite(self, md_text: str, review_feedback: str = ""):
        prompt = (
            f"{load_allowed_syntax_reference()}\n\n"
            f"{load_example_template_reference()}\n\n"
            f"{md_text}\n\n"
            f"{review_feedback}"
        )
        self.requests.append(("rewriter", prompt))
        return "# 文档标题\n\n## 一级章节\n\n正文"

    def review(self, original_md: str, candidate_md: str):
        prompt = (
            f"{load_allowed_syntax_reference()}\n\n"
            f"{load_example_template_reference()}\n\n"
            f"{original_md}\n\n"
            f"{candidate_md}"
        )
        self.requests.append(("reviewer", prompt))
        return MarkdownAgentReview(
            accepted=True,
            summary="语义结构复核通过。",
        )


def test_load_agent_reference_markdown_returns_source_reference():
    reference = load_agent_reference_markdown()

    assert "# MD2Word Agent Reference" in reference
    assert "## 允许语法" in reference
    assert "## 示例模板" in reference


def test_reference_sections_are_split():
    allowed = load_allowed_syntax_reference()
    example = load_example_template_reference()

    assert "### 标题" in allowed
    assert "# 文档标题" in example
    assert "## 一级章节一" in example


def test_validate_markdown_reports_common_syntax_errors():
    result = validate_markdown("#标题\n\n-列表项\n\n```python\nprint('x')\n")

    assert not result.ok
    assert {issue.code for issue in result.issues} >= {
        "content_before_first_h1",
        "heading_missing_space",
        "list_missing_space",
        "unclosed_code_fence",
    }


def test_validate_markdown_accepts_headings_with_space():
    result = validate_markdown("# 文档标题\n\n## 一、一级章节\n\n正文")

    assert result.ok


def test_prepare_markdown_for_conversion_extracts_title_and_body():
    prepared = prepare_markdown_for_conversion("# 文档标题\n\n## 一级章节\n\n正文\n")

    assert prepared.document_title == "文档标题"
    assert prepared.body_markdown == "## 一级章节\n\n正文"


def test_prepare_markdown_for_conversion_demotes_body_h1_headings():
    prepared = prepare_markdown_for_conversion("# 文档标题\n\n# 第一章 项目概述\n\n正文\n")

    assert prepared.document_title == "文档标题"
    assert prepared.body_markdown == "## 第一章 项目概述\n\n正文"


def test_validate_conversion_body_markdown_rejects_h1_in_body():
    result = validate_conversion_body_markdown("# 第一章 项目概述\n\n正文")

    assert not result.ok
    assert any(issue.code == "body_contains_h1" for issue in result.issues)


def test_clean_markdown_loop_returns_conversion_gate_result_without_llm():
    result = clean_markdown_with_llm_loop("# 文档标题\n\n## 一级章节\n\n正文", cleaner=None, max_rounds=2, use_env_cleaner=False)

    assert result.rounds == 0
    assert result.source == "none"
    assert result.accepted
    assert result.document_title == "文档标题"
    assert result.body_markdown == "## 一级章节\n\n正文"
    assert result.validation.ok


def test_clean_markdown_loop_rewrites_until_body_validation_passes():
    cleaner = FakeCleaner([
        "# 文档标题\n\n## 一级章节\n\n| 列1 | 列2 |\n| --- |\n| A | B |\n",
        "# 文档标题\n\n## 一级章节\n\n| 列1 | 列2 |\n| --- | --- |\n| A | B |\n",
    ])

    result = clean_markdown_with_llm_loop("#标题\n\n正文", cleaner=cleaner, max_rounds=2)

    assert result.accepted
    assert result.validation.ok
    assert result.rounds == 2
    assert "table_separator_mismatch" in cleaner.calls[1][1]
    assert result.body_markdown == "## 一级章节\n\n| 列1 | 列2 |\n| --- | --- |\n| A | B |"


def test_clean_markdown_loop_raises_after_max_rounds():
    cleaner = FakeCleaner(["# 文档标题\n\n## 一级章节\n\n| 列1 | 列2 |\n| --- |\n| A | B |\n"])

    try:
        clean_markdown_with_llm_loop("#标题", cleaner=cleaner, max_rounds=1)
    except MarkdownCleaningError as exc:
        assert "table_separator_mismatch" in exc.validation.format_for_llm()
    else:
        raise AssertionError("Expected MarkdownCleaningError")


def test_normalize_markdown_headings_demotes_additional_h1_headings():
    result = normalize_markdown_headings("# 文档标题\n\n# 第一章 项目概述\n\n# 第二章 建设内容\n")

    assert result == "# 文档标题\n\n## 第一章 项目概述\n\n## 第二章 建设内容"


def test_agent_prompts_include_both_reference_sections():
    cleaner = SpyCleaner()

    result = clean_markdown_with_llm_loop("#标题\n\n正文", cleaner=cleaner, max_rounds=1)

    assert result.accepted
    assert cleaner.requests
    assert all("### 标题" in prompt for _, prompt in cleaner.requests)
    assert all("## 一级章节一" in prompt for _, prompt in cleaner.requests)
