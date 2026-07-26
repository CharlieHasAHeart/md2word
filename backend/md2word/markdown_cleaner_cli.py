from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .markdown_cleaner import MarkdownCleaningError, clean_markdown_with_llm_loop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the md2word markdown agent cleanup flow and output the cleaned markdown."
    )
    parser.add_argument("-i", "--input", required=True, help="Path to the source Markdown file")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Path to write the cleaned Markdown. Defaults to stdout when omitted.",
    )
    parser.add_argument(
        "--body-output",
        default=None,
        help="Optional path to write the prepared body-only Markdown used by the converter.",
    )
    parser.add_argument(
        "--meta-output",
        default=None,
        help="Optional path to write JSON metadata about the cleanup result.",
    )
    parser.add_argument(
        "--compare-output",
        default=None,
        help="Optional directory to write original.md, cleaned.md, body.md, and meta.json together.",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help="Override MD2WORD_MARKDOWN_CLEAN_MAX_ROUNDS for this run.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable the environment LLM cleaner and run only the local normalization/gating logic.",
    )
    return parser


def serialize_result(result) -> dict[str, object]:
    return {
        "agent_used": result.agent_used,
        "accepted": result.accepted,
        "rounds": result.rounds,
        "source": result.source,
        "changed": result.changed,
        "document_title": result.document_title,
        "review_summary": result.review_summary,
        "issues_before": [
            {"line": issue.line, "code": issue.code, "message": issue.message}
            for issue in result.issues_before
        ],
        "issues_after": [
            {"line": issue.line, "code": issue.code, "message": issue.message}
            for issue in result.issues_after
        ],
        "trace": [
            {
                "index": round_item.index,
                "rewrite_summary": round_item.rewrite_summary,
                "review_summary": round_item.review_summary,
                "validation_ok": round_item.validation_ok,
                "issue_codes": round_item.issue_codes,
            }
            for round_item in result.trace
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Markdown not found: {input_path}", file=sys.stderr)
        return 1

    md_text = input_path.read_text(encoding="utf-8")

    try:
        result = clean_markdown_with_llm_loop(
            md_text,
            max_rounds=args.max_rounds,
            use_env_cleaner=not args.no_llm,
        )
    except MarkdownCleaningError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    compare_output_dir = Path(args.compare_output) if args.compare_output else None
    if compare_output_dir is not None:
        compare_output_dir.mkdir(parents=True, exist_ok=True)
        (compare_output_dir / "original.md").write_text(md_text, encoding="utf-8")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.markdown_text, encoding="utf-8")
    else:
        sys.stdout.write(result.markdown_text)
        if result.markdown_text and not result.markdown_text.endswith("\n"):
            sys.stdout.write("\n")

    if args.body_output:
        body_output_path = Path(args.body_output)
        body_output_path.parent.mkdir(parents=True, exist_ok=True)
        body_output_path.write_text(result.body_markdown, encoding="utf-8")
    if compare_output_dir is not None:
        (compare_output_dir / "cleaned.md").write_text(result.markdown_text, encoding="utf-8")
        (compare_output_dir / "body.md").write_text(result.body_markdown, encoding="utf-8")

    if args.meta_output:
        meta_output_path = Path(args.meta_output)
        meta_output_path.parent.mkdir(parents=True, exist_ok=True)
        meta_output_path.write_text(
            json.dumps(serialize_result(result), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if compare_output_dir is not None:
        (compare_output_dir / "meta.json").write_text(
            json.dumps(serialize_result(result), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
