from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TemplateStyleProfile:
    paragraph: list[str]
    title: list[str]
    subtitle: list[str]
    headings: dict[int, list[str]]
    unordered_list: list[str]
    ordered_list: list[str]
    quote: list[str]
    tip_quote: list[str]
    note_quote: list[str]
    warning_quote: list[str]
    image: list[str]
    caption: list[str]
    table_caption: list[str]
    code_block: list[str]
    code_language: list[str]
    inline_code: list[str]
    table: list[str]
    table_header_paragraph: list[str]
    table_body_paragraph: list[str]


@dataclass(frozen=True)
class TemplateProfile:
    id: str
    label: str
    template_path: Path
    family: str
    variant: str
    supports_cover: bool = True
    supports_toc: bool = False
    header_uses_title: bool = False
    notes: str = ""
    styles: TemplateStyleProfile = field(default_factory=lambda: DEFAULT_STYLE_PROFILE)


_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_DEFAULT_TEMPLATE = Path(__file__).resolve().parent / "templates" / "reference.docx"


DEFAULT_STYLE_PROFILE = TemplateStyleProfile(
    paragraph=["Normal", "正文"],
    title=["Title", "标题", "封面标题"],
    subtitle=["Subtitle", "副标题", "封面副标题"],
    headings={
        1: ["Heading 1", "标题 1"],
        2: ["Heading 2", "标题 2"],
        3: ["Heading 3", "标题 3"],
        4: ["Heading 4", "标题 4"],
        5: ["Heading 5", "标题 5"],
        6: ["Heading 6", "标题 6"],
    },
    unordered_list=["列表-无序", "List Paragraph", "List"],
    ordered_list=["列表-有序", "List Paragraph", "List"],
    quote=["引用块", "Quote", "Intense Quote"],
    tip_quote=["提示块", "引用块", "Quote"],
    note_quote=["注意块", "引用块", "Quote"],
    warning_quote=["警告块", "引用块", "Intense Quote"],
    image=["图片", "Normal"],
    caption=["图注", "Caption", "Normal"],
    table_caption=["表注", "Caption", "Normal"],
    code_block=["代码块", "Normal"],
    code_language=["代码语言标记", "代码块", "Normal"],
    inline_code=["行内代码", "Default Paragraph Font"],
    table=["CyanScript Table", "Normal Table", "Table Grid"],
    table_header_paragraph=["表格-表头", "表格表头", "Normal"],
    table_body_paragraph=["表格-正文", "表格正文", "Normal"],
)


REFERENCE_STYLE_PROFILE = TemplateStyleProfile(
    paragraph=["Normal"],
    title=["Title"],
    subtitle=["Subtitle"],
    headings={
        1: ["Heading 1", "标题 1"],
        2: ["Heading 2", "标题 2"],
        3: ["Heading 3", "标题 3"],
        4: ["Heading 4", "标题 4"],
        5: ["Heading 5", "标题 5"],
        6: ["Heading 6", "标题 6"],
    },
    unordered_list=["Normal"],
    ordered_list=["Normal"],
    quote=["Normal"],
    tip_quote=["Normal"],
    note_quote=["Normal"],
    warning_quote=["Normal"],
    image=["Normal"],
    caption=["Caption", "Normal"],
    table_caption=["Caption", "Normal"],
    code_block=["Normal"],
    code_language=["Normal"],
    inline_code=["Strong", "Default Paragraph Font"],
    table=["Table Grid", "Normal Table"],
    table_header_paragraph=["Normal"],
    table_body_paragraph=["Normal"],
)


CLOUDBILITY_STYLE_PROFILE = TemplateStyleProfile(
    paragraph=["Cloudbility-正文", "Normal"],
    title=["Cloudbility-封面标题", "Title"],
    subtitle=["Subtitle"],
    headings={
        1: ["Heading 1"],
        2: ["Heading 2"],
        3: ["Heading 3"],
        4: ["Heading 4"],
        5: ["Heading 5"],
        6: ["Heading 6"],
    },
    unordered_list=["Cloudbility-列表样式1级", "Cloudbility-正文", "Normal"],
    ordered_list=["Cloudbility-列表样式1级", "Cloudbility-正文", "Normal"],
    quote=["Cloudbility-正文", "Normal"],
    tip_quote=["Cloudbility-正文", "Normal"],
    note_quote=["Cloudbility-正文", "Normal"],
    warning_quote=["Cloudbility-正文", "Normal"],
    image=["Cloudbility-图片", "Cloudbility-正文", "Normal"],
    caption=["Caption", "Cloudbility-正文", "Normal"],
    table_caption=["Caption", "Cloudbility-正文", "Normal"],
    code_block=["Cloudbility-代码", "Cloudbility-正文", "Normal"],
    code_language=["Cloudbility-代码", "Cloudbility-正文", "Normal"],
    inline_code=["Strong", "Default Paragraph Font"],
    table=["skybility-表格样式1", "Normal Table", "Table Grid"],
    table_header_paragraph=["Cloudbility-正文", "Normal"],
    table_body_paragraph=["Cloudbility-正文", "Normal"],
)


YUANCHUANGLI_STYLE_PROFILE = TemplateStyleProfile(
    paragraph=["Cloudbility-正文", "Normal"],
    title=["Cloudbility-封面标题", "Title"],
    subtitle=["Subtitle"],
    headings={
        1: ["Heading 1"],
        2: ["Heading 2"],
        3: ["Heading 3"],
        4: ["Heading 4"],
        5: ["Heading 5"],
        6: ["Heading 6"],
    },
    unordered_list=["Cloudbility-列表样式1级", "Cloudbility-正文", "Normal"],
    ordered_list=["Cloudbility-列表样式1级", "Cloudbility-正文", "Normal"],
    quote=["Cloudbility-正文", "Normal"],
    tip_quote=["Cloudbility-正文", "Normal"],
    note_quote=["Cloudbility-正文", "Normal"],
    warning_quote=["Cloudbility-正文", "Normal"],
    image=["Cloudbility-图片", "Cloudbility-正文", "Normal"],
    caption=["Caption", "Cloudbility-正文", "Normal"],
    table_caption=["Caption", "Cloudbility-正文", "Normal"],
    code_block=["Cloudbility-代码", "Cloudbility-正文", "Normal"],
    code_language=["Cloudbility-代码", "Cloudbility-正文", "Normal"],
    inline_code=["Strong", "Default Paragraph Font"],
    table=["skybility-表格样式1", "Normal Table", "Table Grid"],
    table_header_paragraph=["Cloudbility-正文", "Normal"],
    table_body_paragraph=["Cloudbility-正文", "Normal"],
)


TEMPLATE_PROFILES: dict[str, TemplateProfile] = {
    "reference": TemplateProfile(
        id="reference",
        label="当前内置模板",
        template_path=_DEFAULT_TEMPLATE,
        family="builtin",
        variant="reference",
        supports_cover=True,
        supports_toc=True,
        header_uses_title=True,
        notes="当前默认内置模板",
        styles=REFERENCE_STYLE_PROFILE,
    ),
    "cloudbility-long": TemplateProfile(
        id="cloudbility-long",
        label="Cloudbility 长版",
        template_path=_TEMPLATE_DIR / "cloudbility-long-template.docx",
        family="cloudbility",
        variant="long",
        supports_cover=True,
        supports_toc=True,
        header_uses_title=False,
        notes="已改造成可渲染模板。",
        styles=CLOUDBILITY_STYLE_PROFILE,
    ),
    "cloudbility-short": TemplateProfile(
        id="cloudbility-short",
        label="Cloudbility 短版",
        template_path=_TEMPLATE_DIR / "cloudbility-short-template.docx",
        family="cloudbility",
        variant="short",
        supports_cover=True,
        supports_toc=False,
        header_uses_title=False,
        notes="已改造成可渲染模板。",
        styles=CLOUDBILITY_STYLE_PROFILE,
    ),
    "yuanchuangli-long": TemplateProfile(
        id="yuanchuangli-long",
        label="源创力 长版",
        template_path=_TEMPLATE_DIR / "yuanchuangli-long-template.docx",
        family="yuanchuangli",
        variant="long",
        supports_cover=True,
        supports_toc=True,
        header_uses_title=False,
        notes="已改造成可渲染模板。",
        styles=YUANCHUANGLI_STYLE_PROFILE,
    ),
    "yuanchuangli-short": TemplateProfile(
        id="yuanchuangli-short",
        label="源创力 短版",
        template_path=_TEMPLATE_DIR / "yuanchuangli-short-template.docx",
        family="yuanchuangli",
        variant="short",
        supports_cover=True,
        supports_toc=False,
        header_uses_title=False,
        notes="已改造成可渲染模板。",
        styles=YUANCHUANGLI_STYLE_PROFILE,
    ),
}


def get_template_profile(template_id: str) -> TemplateProfile:
    try:
        return TEMPLATE_PROFILES[template_id]
    except KeyError as exc:
        raise KeyError(f"Unknown template profile: {template_id}") from exc


def list_template_profiles() -> list[TemplateProfile]:
    return list(TEMPLATE_PROFILES.values())


def get_template_profile_by_path(template_path: str | Path) -> TemplateProfile:
    resolved = Path(template_path).resolve()
    for profile in TEMPLATE_PROFILES.values():
        if profile.template_path.resolve() == resolved:
            return profile
    return TEMPLATE_PROFILES["reference"]
