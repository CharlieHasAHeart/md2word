from pathlib import Path
from types import SimpleNamespace

from backend.md2word import converter
from backend.md2word.converter import strip_document_title_heading


def test_strip_document_title_heading_removes_first_h1_only():
    md_text = "# 文档标题\n\n## 一、项目背景\n\n正文\n\n### （一）项目管理\n"

    assert strip_document_title_heading(md_text) == "## 一、项目背景\n\n正文\n\n### （一）项目管理"


def test_strip_document_title_heading_keeps_markdown_without_h1_title():
    md_text = "## 一、项目背景\n\n正文"

    assert strip_document_title_heading(md_text) == md_text


def test_convert_uses_cleaning_result_body_and_title(monkeypatch, tmp_path):
    md_path = tmp_path / "input.md"
    md_path.write_text("# 原始标题\n\n# 第一章 项目概述\n\n正文\n", encoding="utf-8")
    template_path = tmp_path / "template.docx"
    template_path.write_bytes(b"fake-template")
    output_path = tmp_path / "output.docx"

    monkeypatch.setattr(
        converter,
        "clean_markdown_with_llm_loop",
        lambda _md: SimpleNamespace(
            markdown_text="# 清洗后标题\n\n## 第一章 项目概述\n\n正文\n",
            document_title="清洗后标题",
            body_markdown="## 第一章 项目概述\n\n正文",
        ),
    )

    render_calls = {}

    class FakeTemplate:
        def __init__(self, _template_path):
            self.docx = SimpleNamespace(settings=SimpleNamespace(element=[]))

        def new_subdoc(self):
            return SimpleNamespace(part=SimpleNamespace())

        def render(self, context):
            render_calls["context"] = context

        def save(self, path):
            Path(path).write_bytes(b"fake-docx")

    monkeypatch.setattr(converter, "DocxTemplate", FakeTemplate)
    monkeypatch.setattr(converter, "cleanup_placeholder_paragraph", lambda *_args: None)
    monkeypatch.setattr(converter, "remove_empty_subtitle_paragraph", lambda *_args: None)
    monkeypatch.setattr(converter, "update_fields_on_open", lambda *_args: None)
    monkeypatch.setattr(converter, "render_markdown_to_subdoc", lambda _subdoc, _md_path, body_md_text, **kwargs: render_calls.update({"body_md_text": body_md_text, "heading_level_offset": kwargs["heading_level_offset"]}))
    monkeypatch.setattr(converter, "get_template_profile_by_path", lambda _path: SimpleNamespace(styles=SimpleNamespace(subtitle=[])))

    result = converter.convert_markdown_to_docx(
        md_path=str(md_path),
        template_path=str(template_path),
        output_path=str(output_path),
        title="",
        clean_markdown=True,
    )

    assert result == str(output_path)
    assert render_calls["body_md_text"] == "## 第一章 项目概述\n\n正文"
    assert render_calls["heading_level_offset"] == -1
    assert render_calls["context"]["title"] == "清洗后标题"
