from __future__ import annotations

import argparse
from pathlib import Path

from backend.md2word.workflow import convert_markdown_to_docx
from backend.md2word.template_registry import TEMPLATE_CHOICES, get_template_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert Markdown to Word with md2word templates.")
    parser.add_argument("--md", required=False, help="Source Markdown file.")
    parser.add_argument("--output", required=False, help="Output .docx file.")
    parser.add_argument("--template", default="reference", help="Template name.")
    parser.add_argument("--title", default="", help="Document title.")
    parser.add_argument("--subtitle", default="", help="Document subtitle.")
    parser.add_argument("--list-templates", action="store_true", help="List available templates and exit.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_templates:
        for name, path in TEMPLATE_CHOICES.items():
            print(f"{name}\t{path.name}")
        return 0

    if not args.md or not args.output:
        parser.error("--md and --output are required unless --list-templates is used")

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
        document_title=args.title,
        subtitle=args.subtitle,
        template_path=template_path,
    )
    print(result.output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
