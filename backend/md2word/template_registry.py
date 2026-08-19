from __future__ import annotations

from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_CHOICES: dict[str, Path] = {
    "reference": TEMPLATE_DIR / "reference.docx",
    "cloudbility-long": TEMPLATE_DIR / "cloudbility-long-template.docx",
    "cloudbility-short": TEMPLATE_DIR / "cloudbility-short-template.docx",
    "yuanchuangli-long": TEMPLATE_DIR / "yuanchuangli-long-template.docx",
    "yuanchuangli-short": TEMPLATE_DIR / "yuanchuangli-short-template.docx",
}


def get_template_path(template_name: str) -> Path | None:
    return TEMPLATE_CHOICES.get(template_name.strip())
