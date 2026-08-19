from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from backend.md2word.workflow import convert_markdown_to_docx
from backend.md2word.template_registry import TEMPLATE_CHOICES, get_template_path

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

app = FastAPI(title="multi-app backend")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/md2word/templates")
def list_templates() -> dict[str, list[dict[str, str]]]:
    return {
        "templates": [
            {
                "name": name,
                "filename": path.name,
            }
            for name, path in TEMPLATE_CHOICES.items()
        ]
    }


@app.post("/api/md2word/convert")
async def convert_markdown_endpoint(
    file: UploadFile = File(...),
    template_name: str = Form("reference"),
    document_title: str = Form(""),
    subtitle: str = Form(""),
) -> Response:
    template_path = get_template_path(template_name)
    if template_path is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unknown_template",
                "message": f"Unknown template: {template_name}",
                "available": list(TEMPLATE_CHOICES),
            },
        )
    if not template_path.exists():
        raise HTTPException(
            status_code=500,
            detail={"error": "template_missing", "message": f"Template not found: {template_path.name}"},
        )

    raw_name = Path(file.filename or "input.md").name
    source_name = raw_name if raw_name.lower().endswith(".md") else f"{Path(raw_name).stem}.md"
    markdown_bytes = await file.read()
    try:
        markdown_text = markdown_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_encoding", "message": str(exc)}) from exc

    with tempfile.TemporaryDirectory(prefix="md2word-") as tmpdir:
        tmp_dir = Path(tmpdir)
        source_path = tmp_dir / source_name
        source_path.write_text(markdown_text, encoding="utf-8")
        output_path = tmp_dir / f"{source_path.stem}.docx"
        result = convert_markdown_to_docx(
            source_path,
            output_path,
            document_title=document_title,
            subtitle=subtitle,
            template_path=template_path,
        )
        content = result.output_path.read_bytes()

    download_name = _build_download_name(document_title or result.document_title or source_path.stem)
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


def _build_download_name(stem: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", stem).strip()
    return f"{cleaned or 'output'}.docx"


def _content_disposition(filename: str) -> str:
    ascii_name = re.sub(r"[^\x20-\x7E]", "_", filename)
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'
