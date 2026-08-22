from __future__ import annotations

import argparse
from pathlib import Path

from backend.md2word.workflow import convert_markdown_to_docx
from backend.md2word.template_registry import TEMPLATE_CHOICES, get_template_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert one Markdown file to one Word file with a selected template.")
    parser.add_argument("--md", required=True, help="Source Markdown file.")
    parser.add_argument("--output", required=True, help="Output .docx file.")
    parser.add_argument("--template", required=True, choices=sorted(TEMPLATE_CHOICES), help="Template name.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    md_path = Path(args.md).resolve()
    output_path = Path(args.output).resolve()
    template_path = get_template_path(args.template)
    if template_path is None:
        parser.error(f"Unknown template: {args.template}")
    if not md_path.exists():
        parser.error(f"Markdown file not found: {md_path}")
    if not template_path.exists():
        parser.error(f"Template not found: {template_path}")

    result = convert_markdown_to_docx(
        md_path,
        output_path,
        template_path=template_path,
    )
    print(result.output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
