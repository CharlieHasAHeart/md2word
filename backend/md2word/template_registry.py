from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MarkdownStyleMap:
    document_title: str | None
    heading_1: str | None
    heading_2: str | None
    heading_3: str | None
    body: str | None
    bullet_list: str | None
    bullet_list_2: str | None
    ordered_list: str | None
    ordered_list_2: str | None
    image: str | None
    image_caption: str | None
    code_block: str | None
    blockquote: str | None
    table: str | None


@dataclass(frozen=True)
class TemplateMetadata:
    id: str
    label: str
    notes: str
    family: str
    variant: str
    supports_cover: bool
    supports_toc: bool
    supports_subtitle: bool
    preview: str


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_CHOICES: dict[str, Path] = {
    "reference": TEMPLATE_DIR / "reference.docx",
    "cloudbility-long": TEMPLATE_DIR / "cloudbility-long-template.docx",
    "cloudbility-short": TEMPLATE_DIR / "cloudbility-short-template.docx",
    "yuanchuangli-long": TEMPLATE_DIR / "yuanchuangli-long-template.docx",
    "yuanchuangli-short": TEMPLATE_DIR / "yuanchuangli-short-template.docx",
}

DEFAULT_STYLE_MAP = MarkdownStyleMap(
    document_title="Title",
    heading_1="Heading 1",
    heading_2="Heading 2",
    heading_3="Heading 3",
    body="Normal",
    bullet_list="List Bullet",
    bullet_list_2="List Bullet 2",
    ordered_list="List Number",
    ordered_list_2="List Number 2",
    image=None,
    image_caption="Caption",
    code_block=None,
    blockquote="Quote",
    table="Table Grid",
)

BRANDED_STYLE_MAP = MarkdownStyleMap(
    document_title=None,
    heading_1="Heading 1",
    heading_2="Heading 2",
    heading_3="Heading 3",
    body="Cloudbility-正文",
    bullet_list="Cloudbility-列表样式1级",
    bullet_list_2="Cloudbility-列表样式2级",
    ordered_list="Cloudbility-列表样式1级",
    ordered_list_2="Cloudbility-列表样式2级",
    image="Cloudbility-图片",
    image_caption="Cloudbility-正文",
    code_block="Cloudbility-代码",
    blockquote="灰色文字",
    table="skybility-表格样式1",
)

REFERENCE_STYLE_MAP = MarkdownStyleMap(
    document_title=None,
    heading_1="Heading 1",
    heading_2="Heading 2",
    heading_3="Heading 3",
    body="Normal",
    bullet_list="列表-无序",
    bullet_list_2="列表-无序",
    ordered_list="列表-有序",
    ordered_list_2="列表-有序",
    image="图片",
    image_caption="图注",
    code_block="代码块",
    blockquote="引用块",
    table="CyanScript Table",
)

TEMPLATE_STYLE_MAPS: dict[str, MarkdownStyleMap] = {
    "reference": REFERENCE_STYLE_MAP,
    "cloudbility-long": BRANDED_STYLE_MAP,
    "cloudbility-short": BRANDED_STYLE_MAP,
    "yuanchuangli-long": BRANDED_STYLE_MAP,
    "yuanchuangli-short": BRANDED_STYLE_MAP,
}

TEMPLATE_METADATA: dict[str, TemplateMetadata] = {
    "reference": TemplateMetadata(
        id="reference",
        label="默认模板",
        notes="通用参考排版模板",
        family="reference",
        variant="reference",
        supports_cover=False,
        supports_toc=False,
        supports_subtitle=False,
        preview="/template-covers/reference.svg",
    ),
    "cloudbility-long": TemplateMetadata(
        id="cloudbility-long",
        label="Cloudbility 长模板",
        notes="封面与正文一体的长版模板",
        family="cloudbility",
        variant="long",
        supports_cover=True,
        supports_toc=True,
        supports_subtitle=False,
        preview="/template-covers/cloudbility-long.svg",
    ),
    "cloudbility-short": TemplateMetadata(
        id="cloudbility-short",
        label="Cloudbility 短模板",
        notes="需要副标题的短版模板",
        family="cloudbility",
        variant="short",
        supports_cover=True,
        supports_toc=False,
        supports_subtitle=True,
        preview="/template-covers/cloudbility-short.svg",
    ),
    "yuanchuangli-long": TemplateMetadata(
        id="yuanchuangli-long",
        label="源创力 长模板",
        notes="封面与正文一体的长版模板",
        family="yuanchuangli",
        variant="long",
        supports_cover=True,
        supports_toc=True,
        supports_subtitle=False,
        preview="/template-covers/yuanchuangli-long.svg",
    ),
    "yuanchuangli-short": TemplateMetadata(
        id="yuanchuangli-short",
        label="源创力 短模板",
        notes="需要副标题的短版模板",
        family="yuanchuangli",
        variant="short",
        supports_cover=True,
        supports_toc=False,
        supports_subtitle=True,
        preview="/template-covers/yuanchuangli-short.svg",
    ),
}


def get_template_path(template_name: str) -> Path | None:
    return TEMPLATE_CHOICES.get(template_name.strip())


def get_style_map(template_name: str) -> MarkdownStyleMap:
    return TEMPLATE_STYLE_MAPS.get(template_name.strip(), DEFAULT_STYLE_MAP)


def get_style_map_for_template_path(template_path: str | Path | None) -> MarkdownStyleMap:
    if template_path is None:
        return DEFAULT_STYLE_MAP
    resolved = Path(template_path).resolve()
    for template_name, path in TEMPLATE_CHOICES.items():
        if path.resolve() == resolved:
            return TEMPLATE_STYLE_MAPS.get(template_name, DEFAULT_STYLE_MAP)
    return DEFAULT_STYLE_MAP


def get_template_metadata(template_name: str) -> TemplateMetadata | None:
    return TEMPLATE_METADATA.get(template_name.strip())
