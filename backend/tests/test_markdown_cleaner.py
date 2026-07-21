from backend.md2word.markdown_cleaner import (
    MarkdownCleaningError,
    clean_markdown_with_llm_loop,
    validate_markdown,
)


class FakeCleaner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def clean(self, md_text: str, validation_errors: str = ""):
        self.calls.append((md_text, validation_errors))
        return self.responses.pop(0)


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


def test_validate_markdown_rejects_chapter_as_document_title():
    result = validate_markdown("# 第一章 项目概述\n\n正文")

    assert not result.ok
    assert any(issue.code == "chapter_used_as_document_title" for issue in result.issues)


def test_validate_markdown_rejects_multiple_document_titles():
    result = validate_markdown("# 文档标题\n\n## 一、一级章节\n\n# 第二个标题\n\n正文")

    assert not result.ok
    assert any(issue.code == "multiple_document_titles" for issue in result.issues)


def test_validate_markdown_rejects_content_before_first_h1():
    result = validate_markdown("项目名称：示例项目\n\n# 第一章 项目概述\n\n正文")

    assert not result.ok
    assert any(issue.code == "content_before_first_h1" for issue in result.issues)


def test_clean_markdown_loop_returns_original_without_llm():
    result = clean_markdown_with_llm_loop("#标题", cleaner=None, max_rounds=2, use_env_cleaner=False)

    assert result.markdown_text == "#标题"
    assert result.rounds == 0
    assert result.source == "none"
    assert not result.validation.ok


def test_clean_markdown_loop_feedbacks_validation_errors_until_valid():
    cleaner = FakeCleaner([
        "#标题\n\n正文",
        "# 标题\n\n正文",
    ])

    result = clean_markdown_with_llm_loop("#标题\n\n正文", cleaner=cleaner, max_rounds=2)

    assert result.validation.ok
    assert result.markdown_text == "# 标题\n\n正文"
    assert result.rounds == 2
    assert len(cleaner.calls) == 2
    assert "heading_missing_space" in cleaner.calls[1][1]


def test_clean_markdown_loop_raises_after_max_rounds():
    cleaner = FakeCleaner(["#标题"])

    try:
        clean_markdown_with_llm_loop("#标题", cleaner=cleaner, max_rounds=1)
    except MarkdownCleaningError as exc:
        assert "heading_missing_space" in exc.validation.format_for_llm()
    else:
        raise AssertionError("Expected MarkdownCleaningError")
