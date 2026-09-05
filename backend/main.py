from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict
from pathlib import Path
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from backend.md2word.formalizer import FormalizeProgress, FormalizeResult, ProcessingMode, iter_formalize_markdown
from backend.md2word.workflow import convert_markdown_to_docx
from backend.md2word.template_registry import TEMPLATE_CHOICES, get_template_metadata, get_template_path

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

app = FastAPI(title="multi-app backend")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/md2word/templates")
def list_templates() -> list[dict[str, str | bool]]:
    templates: list[dict[str, str | bool]] = []
    for name, path in TEMPLATE_CHOICES.items():
        metadata = get_template_metadata(name)
        if metadata is None:
            continue
        payload = asdict(metadata)
        payload["ready"] = path.exists()
        templates.append(payload)
    return templates


@app.post("/api/md2word/formalize")
async def formalize_markdown_endpoint(
    markdown_file: UploadFile | None = File(None),
    file: UploadFile | None = File(None),
    mode: str = Form("baseline"),
) -> StreamingResponse:
    upload = _pick_upload(markdown_file=markdown_file, legacy_file=file)
    source_name, markdown_text = await _read_markdown_upload(upload)
    processing_mode = _coerce_processing_mode(mode)
    return StreamingResponse(
        _iter_formalize_stream(markdown_text=markdown_text, source_name=source_name, mode=processing_mode),
        media_type="application/x-ndjson",
    )


@app.post("/api/md2word/convert")
async def convert_markdown_endpoint(
    markdown_file: UploadFile | None = File(None),
    file: UploadFile | None = File(None),
    template_id: str = Form("reference"),
    template_name: str = Form(""),
    title: str = Form(""),
    document_title: str = Form(""),
    header_title: str = Form(""),
    output_name: str = Form(""),
    subtitle: str = Form(""),
    mode: str = Form("baseline"),
) -> Response:
    upload = _pick_upload(markdown_file=markdown_file, legacy_file=file)
    effective_template_id = _coerce_text(template_id) or _coerce_text(template_name) or "reference"
    template_path = get_template_path(effective_template_id)
    if template_path is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unknown_template",
                "message": f"Unknown template: {effective_template_id}",
                "available": list(TEMPLATE_CHOICES),
            },
        )
    if not template_path.exists():
        raise HTTPException(
            status_code=500,
            detail={"error": "template_missing", "message": f"Template not found: {template_path.name}"},
        )

    metadata = get_template_metadata(effective_template_id)
    source_name, markdown_text = await _read_markdown_upload(upload)
    processing_mode = _coerce_processing_mode(mode)
    effective_title = _coerce_text(title) or _coerce_text(document_title)
    supports_subtitle = metadata.supports_subtitle if metadata is not None else "short" in effective_template_id
    effective_subtitle = _coerce_text(subtitle) if supports_subtitle else ""
    _ = _coerce_text(header_title)

    with tempfile.TemporaryDirectory(prefix="md2word-") as tmpdir:
        tmp_dir = Path(tmpdir)
        source_path = tmp_dir / source_name
        source_path.write_text(markdown_text, encoding="utf-8")
        output_path = tmp_dir / f"{source_path.stem}.docx"
        result = convert_markdown_to_docx(
            source_path,
            output_path,
            document_title=effective_title,
            subtitle=effective_subtitle,
            template_path=template_path,
            mode=processing_mode,
        )
        content = result.output_path.read_bytes()

    requested_output_name = _coerce_text(output_name)
    download_name = _normalize_output_name(requested_output_name) if requested_output_name else _build_output_name(
        effective_title or result.document_title or source_path.stem
    )
    return Response(
        content=content,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": _content_disposition(download_name)},
    )


def main() -> None:
    uvicorn.run(
        "backend.main:app",
        host=os.getenv("MD2WORD_HOST", "0.0.0.0"),
        port=int(os.getenv("MD2WORD_PORT", "8000")),
        reload=os.getenv("MD2WORD_RELOAD", "").strip().lower() in {"1", "true", "yes"},
    )


def _pick_upload(markdown_file: UploadFile | None, legacy_file: UploadFile | None) -> UploadFile:
    upload = markdown_file or legacy_file
    if upload is None:
        raise HTTPException(status_code=400, detail={"error": "missing_markdown_file", "message": "Markdown file is required."})
    return upload


async def _read_markdown_upload(upload: UploadFile) -> tuple[str, str]:
    raw_name = Path(upload.filename or "input.md").name
    source_name = raw_name if raw_name.lower().endswith(".md") else f"{Path(raw_name).stem}.md"
    markdown_bytes = await upload.read()
    try:
        markdown_text = markdown_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_encoding", "message": str(exc)}) from exc
    return source_name, markdown_text


def _build_output_name(stem: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", stem).strip()
    return f"{cleaned or 'output'}.docx"


def _normalize_output_name(filename: str) -> str:
    normalized = filename.strip()
    if not normalized.lower().endswith(".docx"):
        normalized = f"{normalized}.docx"
    return _build_output_name(Path(normalized).stem)


def _coerce_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _content_disposition(filename: str) -> str:
    ascii_name = re.sub(r"[^\x20-\x7E]", "_", filename)
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'


async def _iter_formalize_stream(markdown_text: str, source_name: str, mode: ProcessingMode):
    for event in iter_formalize_markdown(markdown_text, source_path=Path(source_name), mode=mode):
        if isinstance(event, FormalizeProgress):
            yield _json_line(
                {
                    "type": "stage",
                    "step": event.name,
                    "message": event.message,
                }
            )
            continue
        yield _json_line(
            {
                "type": "result",
                "result": _build_formalize_payload(event, source_name),
            }
        )


def _build_formalize_payload(formalized: FormalizeResult, source_name: str) -> dict[str, str]:
    title = formalized.document_title or Path(source_name).stem
    return {
        "title": title,
        "header_title": title,
        "output_name": _build_output_name(title),
        "preview": formalized.markdown_text,
        "cleaned_markdown": formalized.markdown_text,
        "file_name": source_name,
    }


def _json_line(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def _coerce_processing_mode(value: object) -> ProcessingMode:
    mode = value.strip() if isinstance(value, str) else "baseline"
    if mode in {"baseline", "ai_enhanced"}:
        return mode
    raise HTTPException(
        status_code=400,
        detail={
            "error": "invalid_processing_mode",
            "message": f"Unsupported processing mode: {value}",
            "available": ["baseline", "ai_enhanced"],
        },
    )
