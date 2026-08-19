from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from .converter import (
    _find_body_placeholder,
    _remove_paragraphs_containing_token,
    _replace_template_placeholders,
    _replace_textbox_placeholder,
    _resolve_body_style_name,
    _shift_heading_levels,
    _strip_document_title_heading,
    render_markdown_to_document,
)
from .formalizer import formalize_markdown


@dataclass(frozen=True)
class ConversionResult:
    output_path: Path
    document_title: str
    markdown_text: str


def convert_markdown_to_docx(
    md_path: str | Path,
    output_path: str | Path,
    document_title: str = "",
    subtitle: str = "",
    template_path: str | Path | None = None,
) -> ConversionResult:
    source = Path(md_path)
    target = Path(output_path)
    md_text = source.read_text(encoding="utf-8")
    formalized = formalize_markdown(md_text, source_path=source)
    title = document_title.strip() or formalized.document_title or source.stem

    if template_path is None:
        doc = Document()
        heading = doc.add_heading(title, level=0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        render_markdown_to_document(doc, formalized.markdown_text, source)
    else:
        doc = Document(str(template_path))
        _replace_textbox_placeholder(doc, "{{document_title}}", title)
        if subtitle.strip():
            _replace_textbox_placeholder(doc, "{{subtitle}}", subtitle.strip())
        _replace_template_placeholders(
            doc,
            {
                "{{document_title}}": title,
                "{{title}}": title,
                "{{subtitle}}": subtitle.strip(),
            },
        )
        anchor = _find_body_placeholder(doc, "{{main_content}}")
        if anchor is None:
            raise ValueError("Template placeholder {{main_content}} was not found.")
        body_markdown = _strip_document_title_heading(formalized.markdown_text)
        body_markdown = _shift_heading_levels(body_markdown, -1)
        render_markdown_to_document(
            doc,
            body_markdown,
            source,
            anchor=anchor,
            body_style_name=_resolve_body_style_name(doc),
        )
        _remove_paragraphs_containing_token(doc, "{{main_content}}")

    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(target)
    return ConversionResult(output_path=target, document_title=title, markdown_text=formalized.markdown_text)
