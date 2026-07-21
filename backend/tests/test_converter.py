from backend.md2word.converter import strip_document_title_heading


def test_strip_document_title_heading_removes_first_h1_only():
    md_text = "# 文档标题\n\n## 一、项目背景\n\n正文\n\n### （一）项目管理\n"

    assert strip_document_title_heading(md_text) == "## 一、项目背景\n\n正文\n\n### （一）项目管理"


def test_strip_document_title_heading_keeps_markdown_without_h1_title():
    md_text = "## 一、项目背景\n\n正文"

    assert strip_document_title_heading(md_text) == md_text
