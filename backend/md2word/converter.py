from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches

from .formalizer import SUPPORTED_IMAGE_EXTENSIONS


def render_markdown_to_document(
    doc: Document,
    md_text: str,
    source_path: str | Path | None = None,
    anchor=None,
    body_style_name: str | None = None,
) -> None:
    base_dir = Path(source_path).resolve().parent if source_path else Path.cwd()
    figure_index = 0
    lines = md_text.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading_match:
            level = min(len(heading_match.group(1)), 4)
            _move_before_anchor(doc.add_heading(heading_match.group(2).strip(), level=level), anchor)
            index += 1
            continue

        image_match = re.match(r"^!\[(?P<caption>[^\]]*)\]\((?P<target>[^)]+)\)\s*$", stripped)
        if image_match:
            figure_index += 1
            _add_image_or_placeholder(
                doc,
                base_dir,
                image_match.group("target"),
                image_match.group("caption"),
                figure_index,
                anchor=anchor,
            )
            index += 1
            continue

        unordered_match = re.match(r"^\s*[-+*]\s+(.+?)\s*$", line)
        if unordered_match:
            _move_before_anchor(_add_paragraph(doc, unordered_match.group(1).strip(), body_style_name), anchor)
            index += 1
            continue

        ordered_match = re.match(r"^\s*\d+[.)]\s+(.+?)\s*$", line)
        if ordered_match:
            _move_before_anchor(_add_paragraph(doc, ordered_match.group(1).strip(), body_style_name), anchor)
            index += 1
            continue

        _move_before_anchor(_add_paragraph(doc, stripped, body_style_name), anchor)
        index += 1


def _add_image_or_placeholder(
    doc: Document,
    base_dir: Path,
    target: str,
    caption: str,
    figure_index: int,
    anchor=None,
    body_style_name: str | None = None,
) -> None:
    clean_target = target.strip().strip("<>")
    image_path = Path(clean_target)
    if not image_path.is_absolute():
        image_path = base_dir / clean_target

    if image_path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS and image_path.exists():
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run()
        run.add_picture(str(image_path), width=Inches(5.8))
        _move_before_anchor(paragraph, anchor)
    else:
        _move_before_anchor(_add_paragraph(doc, f"[图片缺失: {clean_target}]", body_style_name), anchor)

    caption_text = clean_image_caption(caption, image_path)
    caption_paragraph = _add_paragraph(doc, f"图{figure_index} {caption_text}".rstrip(), body_style_name)
    caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _move_before_anchor(caption_paragraph, anchor)


def clean_image_caption(caption: str, image_path: str | Path) -> str:
    text = caption.strip()
    text = re.sub(r"^(?:图\s*\d+|图片|截图|Figure\s*\d+)\s*[:：.、-]?\s*", "", text, flags=re.I).strip()
    if not text and caption.strip() in {"图片", "截图"}:
        return caption.strip()
    if not text or text.lower() in {"image", "img", "figure", "screenshot", "photo", "picture"}:
        return Path(image_path).stem
    return text


def _replace_template_placeholders(doc: Document, mapping: dict[str, str]) -> None:
    for paragraph in _iter_paragraph_elements(doc):
        _replace_tokens_in_paragraph_element(paragraph, mapping)


def _iter_paragraph_elements(doc: Document):
    yield from doc._element.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")
    for section in doc.sections:
        for part in (section.header, section.footer):
            yield from part._element.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")


def _replace_tokens_in_paragraph_element(paragraph, mapping: dict[str, str]) -> None:
    text_nodes = paragraph.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
    if not text_nodes:
        return
    full_text = "".join(node.text or "" for node in text_nodes)
    replaced = full_text
    for key, value in mapping.items():
        replaced = replaced.replace(key, value)
        spaced_key = key.replace("{{", "{{ ").replace("}}", " }}")
        replaced = replaced.replace(spaced_key, value)
    if replaced == full_text:
        return
    text_nodes[0].text = replaced
    for node in text_nodes[1:]:
        node.text = ""


def _find_body_placeholder(doc: Document, token: str):
    for paragraph in _iter_paragraph_elements(doc):
        if token in _paragraph_text_element(paragraph):
            return paragraph
    return None


def _paragraph_text_element(paragraph) -> str:
    return "".join(
        node.text or ""
        for node in paragraph.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
    )


def _move_before_anchor(paragraph, anchor) -> None:
    if anchor is not None:
        anchor.addprevious(paragraph._element)


def _add_paragraph(doc: Document, text: str, style: str | None):
    if not style:
        return doc.add_paragraph(text)
    try:
        return doc.add_paragraph(text, style=style)
    except KeyError:
        return doc.add_paragraph(text)


def _remove_paragraphs_containing_token(doc: Document, token: str) -> None:
    for paragraph in list(_iter_paragraph_elements(doc)):
        if token in _paragraph_text_element(paragraph):
            parent = paragraph.getparent()
            if parent is not None:
                parent.remove(paragraph)


def _replace_textbox_placeholder(doc: Document, token: str, value: str) -> None:
    if not value:
        return
    for paragraph in _iter_textbox_paragraph_elements(doc):
        if token in _paragraph_text_element(paragraph):
            _set_paragraph_text(paragraph, value)
            return


def _iter_textbox_paragraph_elements(doc: Document):
    yield from doc._element.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}txbxContent/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")
    for section in doc.sections:
        for part in (section.header, section.footer):
            yield from part._element.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}txbxContent/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")


def _set_paragraph_text(paragraph, text: str) -> None:
    text_nodes = paragraph.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
    if not text_nodes:
        return
    text_nodes[0].text = text
    for node in text_nodes[1:]:
        node.text = ""


def _resolve_body_style_name(doc: Document) -> str | None:
    return "Cloudbility-正文" if "Cloudbility-正文" in doc.styles else None


def _strip_document_title_heading(md_text: str) -> str:
    lines = md_text.splitlines()
    output: list[str] = []
    skipped = False
    for line in lines:
        if not skipped and re.match(r"^#\s+.+?\s*$", line):
            skipped = True
            continue
        output.append(line)
    return "\n".join(output).strip("\n") + ("\n" if output else "")


def _shift_heading_levels(md_text: str, offset: int) -> str:
    if offset == 0:
        return md_text
    output: list[str] = []
    for line in md_text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            output.append(line)
            continue
        level = len(match.group(1)) + offset
        level = max(1, min(6, level))
        output.append(f"{'#' * level} {match.group(2).strip()}")
    return "\n".join(output).rstrip("\n") + ("\n" if output else "")


__all__ = [
    "clean_image_caption",
    "render_markdown_to_document",
]
