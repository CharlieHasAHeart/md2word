from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches

from .formalizer import SUPPORTED_IMAGE_EXTENSIONS, formalize_markdown


@dataclass(frozen=True)
class ConversionResult:
    output_path: Path
    document_title: str
    markdown_text: str


def convert_markdown_to_docx(
    md_path: str | Path,
    output_path: str | Path,
    document_title: str = "",
) -> ConversionResult:
    source = Path(md_path)
    target = Path(output_path)
    md_text = source.read_text(encoding="utf-8")
    formalized = formalize_markdown(md_text, source_path=source)
    title = document_title.strip() or formalized.document_title or source.stem

    doc = Document()
    if title:
        heading = doc.add_heading(title, level=0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    render_markdown_to_document(doc, formalized.markdown_text, source)

    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(target)
    return ConversionResult(output_path=target, document_title=title, markdown_text=formalized.markdown_text)


def render_markdown_to_document(doc: Document, md_text: str, source_path: str | Path | None = None) -> None:
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
            doc.add_heading(heading_match.group(2).strip(), level=level)
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
            )
            index += 1
            continue

        unordered_match = re.match(r"^\s*[-+*]\s+(.+?)\s*$", line)
        if unordered_match:
            doc.add_paragraph(unordered_match.group(1).strip(), style="List Bullet")
            index += 1
            continue

        ordered_match = re.match(r"^\s*\d+[.)]\s+(.+?)\s*$", line)
        if ordered_match:
            doc.add_paragraph(ordered_match.group(1).strip(), style="List Number")
            index += 1
            continue

        doc.add_paragraph(stripped)
        index += 1


def _add_image_or_placeholder(
    doc: Document,
    base_dir: Path,
    target: str,
    caption: str,
    figure_index: int,
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
    else:
        doc.add_paragraph(f"[图片缺失: {clean_target}]")

    caption_text = clean_image_caption(caption, image_path)
    caption_paragraph = doc.add_paragraph(f"图{figure_index} {caption_text}".rstrip())
    caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER


def clean_image_caption(caption: str, image_path: str | Path) -> str:
    text = caption.strip()
    text = re.sub(r"^(?:图\s*\d+|图片|截图|Figure\s*\d+)\s*[:：.、-]?\s*", "", text, flags=re.I).strip()
    if not text and caption.strip() in {"图片", "截图"}:
        return caption.strip()
    if not text or text.lower() in {"image", "img", "figure", "screenshot", "photo", "picture"}:
        return Path(image_path).stem
    return text
