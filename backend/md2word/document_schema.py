from __future__ import annotations

from pathlib import Path

from . import converter
from .formalizer import FormalizeResult, ProcessingMode, formalize_markdown, inspect_image_refs


def export_markdown_document(
    md_text: str,
    source_path: str | Path | None = None,
    mode: ProcessingMode = "baseline",
) -> dict:
    formalized = formalize_markdown(md_text, source_path=source_path, mode=mode)
    return build_document_payload(formalized, source_path=source_path, mode=mode)


def build_document_payload(
    formalized: FormalizeResult,
    source_path: str | Path | None = None,
    mode: ProcessingMode = "baseline",
) -> dict:
    image_refs = formalized.images
    if not image_refs:
        image_refs, _ = inspect_image_refs(formalized.markdown_text, source_path=source_path)

    lines = formalized.markdown_text.splitlines()
    blocks: list[dict] = []
    index = 0
    next_id = 1

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        fence_match = converter.FENCE_RE.match(line)
        if fence_match:
            block, index = _parse_code_block(lines, index, line, fence_match.group(1), next_id)
            blocks.append(block)
            next_id += 1
            continue

        if converter._is_markdown_table_block(lines, index):
            block, index = _parse_table_block(lines, index, next_id)
            blocks.append(block)
            next_id += 1
            continue

        heading_match = converter.HEADING_RE.match(line)
        if heading_match:
            blocks.append(
                {
                    "type": "heading",
                    "id": _block_id(next_id),
                    "source_line_start": index + 1,
                    "source_line_end": index + 1,
                    "level": len(heading_match.group(1)),
                    "text": heading_match.group(2).strip(),
                }
            )
            next_id += 1
            index += 1
            continue

        image_match = converter.IMAGE_RE.match(stripped)
        if image_match:
            blocks.append(_parse_image_block(image_refs, index + 1, image_match.group("caption"), image_match.group("target"), next_id))
            next_id += 1
            index += 1
            continue

        if converter.BLOCKQUOTE_RE.match(line):
            block, index = _parse_blockquote_block(lines, index, next_id)
            blocks.append(block)
            next_id += 1
            continue

        if converter.UNORDERED_LIST_RE.match(line):
            block, index = _parse_unordered_list_block(lines, index, next_id)
            blocks.append(block)
            next_id += 1
            continue

        if converter.ORDERED_LIST_RE.match(line):
            block, index = _parse_ordered_list_block(lines, index, next_id)
            blocks.append(block)
            next_id += 1
            continue

        blocks.append(
            {
                "type": "paragraph",
                "id": _block_id(next_id),
                "source_line_start": index + 1,
                "source_line_end": index + 1,
                "text": stripped,
            }
        )
        next_id += 1
        index += 1

    source: dict[str, str] = {"mode": mode}
    if source_path is not None:
        source["path"] = str(source_path)

    return {
        "schema_version": "1.0.0",
        "document_title": formalized.document_title,
        "source": source,
        "blocks": blocks,
    }


def _parse_code_block(
    lines: list[str],
    start_index: int,
    opener_line: str,
    fence_marker: str,
    block_number: int,
) -> tuple[dict, int]:
    opener = fence_marker[0]
    language = opener_line.strip()[len(fence_marker) :].strip()
    code_lines: list[str] = []
    index = start_index + 1
    while index < len(lines):
        line = lines[index]
        if converter.FENCE_RE.match(line) and line.strip()[0] == opener:
            return (
                {
                    "type": "code_block",
                    "id": _block_id(block_number),
                    "source_line_start": start_index + 1,
                    "source_line_end": index + 1,
                    "fence": fence_marker[:3],
                    "language": language,
                    "text": "\n".join(code_lines),
                },
                index + 1,
            )
        code_lines.append(line)
        index += 1
    return (
        {
            "type": "code_block",
            "id": _block_id(block_number),
            "source_line_start": start_index + 1,
            "source_line_end": len(lines),
            "fence": fence_marker[:3],
            "language": language,
            "text": "\n".join(code_lines),
        },
        index,
    )


def _parse_table_block(lines: list[str], start_index: int, block_number: int) -> tuple[dict, int]:
    rows, next_index = converter._consume_markdown_table(lines, start_index)
    header = rows[0] if rows else []
    body = rows[1:] if len(rows) > 1 else []
    return (
        {
            "type": "table",
            "id": _block_id(block_number),
            "source_line_start": start_index + 1,
            "source_line_end": next_index,
            "header": header,
            "rows": body,
        },
        next_index,
    )


def _parse_image_block(
    image_refs,
    line_number: int,
    caption: str,
    target: str,
    block_number: int,
) -> dict:
    block = {
        "type": "image",
        "id": _block_id(block_number),
        "source_line_start": line_number,
        "source_line_end": line_number,
        "caption": caption.strip(),
        "target": target.strip().strip("<>"),
    }

    image_ref = next((ref for ref in image_refs if ref.line == line_number and ref.target == block["target"]), None)
    if image_ref is not None:
        block["resolved_path"] = image_ref.resolved_path
        block["exists"] = image_ref.exists
        block["supported"] = image_ref.supported

    return block


def _parse_blockquote_block(lines: list[str], start_index: int, block_number: int) -> tuple[dict, int]:
    output: list[str] = []
    index = start_index
    while index < len(lines):
        match = converter.BLOCKQUOTE_RE.match(lines[index])
        if not match:
            break
        output.append(match.group(1).strip())
        index += 1
    return (
        {
            "type": "blockquote",
            "id": _block_id(block_number),
            "source_line_start": start_index + 1,
            "source_line_end": index,
            "text": "\n".join(output).strip(),
        },
        index,
    )


def _parse_unordered_list_block(lines: list[str], start_index: int, block_number: int) -> tuple[dict, int]:
    items: list[dict] = []
    index = start_index
    while index < len(lines):
        match = converter.UNORDERED_LIST_RE.match(lines[index])
        if not match:
            break
        items.append(
            {
                "text": match.group("text").strip(),
                "level": converter._list_level(match.group("indent")),
            }
        )
        index += 1
    return (
        {
            "type": "unordered_list",
            "id": _block_id(block_number),
            "source_line_start": start_index + 1,
            "source_line_end": index,
            "items": items,
        },
        index,
    )


def _parse_ordered_list_block(lines: list[str], start_index: int, block_number: int) -> tuple[dict, int]:
    parsed_items, next_index = converter._consume_ordered_list_block(lines, start_index, allow_blank_lines=True)
    items = [{"text": text, "level": level} for level, text in parsed_items]
    return (
        {
            "type": "ordered_list",
            "id": _block_id(block_number),
            "source_line_start": start_index + 1,
            "source_line_end": next_index,
            "items": items,
        },
        next_index,
    )


def _block_id(block_number: int) -> str:
    return f"blk_{block_number:04d}"


__all__ = [
    "build_document_payload",
    "export_markdown_document",
]
