from __future__ import annotations

import os
import re
import tempfile
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel

from backend.md2word.env_loader import load_dotenv
from backend.md2word import convert_markdown_to_docx
from backend.md2word.markdown_cleaner import clean_markdown_with_llm_loop
from backend.md2word.template_profiles import list_template_profiles

load_dotenv()

logger = logging.getLogger(__name__)

TOOLS = [
    {
        'id': 'md2word',
        'label': 'MD2Word',
        'icon': '/icons/md2word.svg',
        'description': 'Markdown 转 Word 工具',
    }
]


class TemplateItem(BaseModel):
    id: str
    label: str
    notes: str
    ready: bool
    family: str
    variant: str
    supports_cover: bool
    supports_toc: bool
    preview: str


class ToolItem(BaseModel):
    id: str
    label: str
    icon: str
    description: str


class AnalyzeResult(BaseModel):
    title: str
    header_title: str
    output_name: str
    preview: str
    cleaned_markdown: str
    file_name: str
    subtitle: str = ''
    agent_used: bool = False
    accepted: bool = False
    rounds: int = 0
    source: str = 'none'
    issues_before: list[str] = []
    issues_after: list[str] = []
    plan_summary: str = ''
    review_summary: str = ''


app = FastAPI(title='Workspace API')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def derive_title(md_text: str, file_name: str) -> str:
    match = re.search(r'^#\s+(.+?)\s*$', md_text, flags=re.M)
    if match:
        return match.group(1).strip()
    return Path(file_name).stem


def cleanup_temp_file(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


@app.get('/api/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/api/tools', response_model=list[ToolItem])
def get_tools() -> list[ToolItem]:
    return [ToolItem(**tool) for tool in TOOLS]


@app.get('/api/md2word/templates', response_model=list[TemplateItem])
def get_md2word_templates() -> list[TemplateItem]:
    items: list[TemplateItem] = []
    for profile in list_template_profiles():
        ready = profile.template_path.exists()
        items.append(
            TemplateItem(
                id=profile.id,
                label=profile.label,
                notes=profile.notes,
                ready=ready,
                family=profile.family,
                variant=profile.variant,
                supports_cover=profile.supports_cover,
                supports_toc=profile.supports_toc,
                preview=f'/template-covers/{profile.id}.svg',
            )
        )
    return items


@app.post('/api/md2word/analyze', response_model=AnalyzeResult)
async def analyze_md2word(markdown_file: UploadFile = File(...)):
    file_name = markdown_file.filename or 'input.md'
    content = await markdown_file.read()
    md_text = content.decode('utf-8', errors='ignore')
    try:
        cleaning_result = clean_markdown_with_llm_loop(md_text)
    except Exception as exc:
        logger.exception("Failed to clean Markdown during analyze")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cleaned_markdown = cleaning_result.markdown_text
    title = derive_title(cleaned_markdown, file_name)
    output_name = f'{Path(file_name).stem}.docx'
    return AnalyzeResult(
        title=title,
        header_title=title,
        output_name=output_name,
        preview=cleaned_markdown[:12000],
        cleaned_markdown=cleaned_markdown,
        file_name=file_name,
        subtitle='',
        agent_used=getattr(cleaning_result, 'agent_used', False),
        accepted=getattr(cleaning_result, 'accepted', False),
        rounds=getattr(cleaning_result, 'rounds', 0),
        source=getattr(cleaning_result, 'source', 'none'),
        issues_before=[issue.code for issue in getattr(cleaning_result, 'issues_before', [])],
        issues_after=[issue.code for issue in getattr(cleaning_result, 'issues_after', [])],
        plan_summary=getattr(cleaning_result, 'plan_summary', ''),
        review_summary=getattr(cleaning_result, 'review_summary', ''),
    )


@app.post('/api/md2word/convert')
async def convert_md2word(
    markdown_file: UploadFile = File(...),
    template_id: str = Form(...),
    title: str = Form(''),
    header_title: str = Form(''),
    output_name: str = Form(''),
):
    profiles = {profile.id: profile for profile in list_template_profiles()}
    profile = profiles.get(template_id)
    if profile is None:
        raise HTTPException(status_code=400, detail='Unknown template id')
    if not profile.template_path.exists():
        raise HTTPException(status_code=400, detail='Template file is missing')

    suffix = Path(markdown_file.filename or 'input.md').suffix or '.md'
    with tempfile.TemporaryDirectory(prefix='md2word-web-') as tmpdir:
        md_path = Path(tmpdir) / f'input{suffix}'
        out_name = output_name.strip() or 'result.docx'
        if not out_name.lower().endswith('.docx'):
            out_name += '.docx'
        output_path = Path(tmpdir) / out_name

        content = await markdown_file.read()
        md_path.write_bytes(content)

        try:
            convert_markdown_to_docx(
                md_path=str(md_path),
                template_path=str(profile.template_path),
                output_path=str(output_path),
                title=title or header_title,
                clean_markdown=False,
            )
        except Exception as exc:
            logger.exception("Failed to convert Markdown to DOCX")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        with tempfile.NamedTemporaryFile(prefix='md2word-download-', suffix='.docx', delete=False) as persisted_file:
            persisted = Path(persisted_file.name)
        persisted.write_bytes(output_path.read_bytes())
        return FileResponse(
            persisted,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            filename=out_name,
            background=BackgroundTask(cleanup_temp_file, str(persisted)),
        )


def main() -> None:
    import uvicorn

    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8000'))
    uvicorn.run('backend.main:app', host=host, port=port, reload=False)


if __name__ == '__main__':
    main()
