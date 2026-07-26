from __future__ import annotations

import argparse
import json
from pathlib import Path

from .markdown_cleaner import MarkdownCleaningError, clean_markdown_with_llm_loop


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "markdown_cleaner"
EXPECTED_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "markdown_cleaner_expected"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run markdown cleaner regression cases against expected cleaned/body outputs."
    )
    parser.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="Optional list of case basenames to run. Defaults to every case in markdown_cleaner_expected.",
    )
    parser.add_argument(
        "--compare-output-root",
        default=None,
        help="Optional directory to store compare-output artifacts for each case.",
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


def load_case_names(requested_cases: list[str] | None) -> list[str]:
    if requested_cases:
        return requested_cases
    return sorted(item.name for item in EXPECTED_DIR.iterdir() if item.is_dir())


def normalize_markdown_for_compare(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def case_mode(case_name: str) -> str:
    if case_name.startswith("semantic-"):
        return "strict"
    return "structural"


def body_has_heading_number_prefix(body_markdown: str) -> bool:
    for line in body_markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith(("## ", "### ", "#### ")):
            continue
        title_text = stripped.split(" ", 1)[1].strip()
        if (
            title_text.startswith("第")
            or re_match_any(
                title_text,
                [
                    r"^[一二三四五六七八九十百千万]+、",
                    r"^\d+(?:\.\d+)*[.．、]?\s+",
                ],
            )
        ):
            return True
    return False


def body_has_prefix_noise(body_markdown: str) -> bool:
    return re_match_any(
        body_markdown,
        [
            r"(?m)^\s*(项目名称|建设单位|客户名称|申报单位|目录)\s*[：:]",
        ],
    )


def re_match_any(text: str, patterns: list[str]) -> bool:
    import re

    return any(re.search(pattern, text) for pattern in patterns)


def compare_strict(
    result,
    expected_cleaned: str,
    expected_body: str,
    expected_meta: dict[str, object],
) -> list[str]:
    failures: list[str] = []
    if normalize_markdown_for_compare(result.markdown_text) != normalize_markdown_for_compare(expected_cleaned):
        failures.append("cleaned.md mismatch")
    if normalize_markdown_for_compare(result.body_markdown) != normalize_markdown_for_compare(expected_body):
        failures.append("body.md mismatch")
    if result.document_title != expected_meta["document_title"]:
        failures.append("document_title mismatch")
    if result.accepted is not expected_meta["accepted"]:
        failures.append("accepted mismatch")
    return failures


def compare_structural(
    result,
    expected_meta: dict[str, object],
) -> list[str]:
    failures: list[str] = []
    if result.document_title != expected_meta["document_title"]:
        failures.append("document_title mismatch")
    if result.accepted is not expected_meta["accepted"]:
        failures.append("accepted mismatch")
    if result.issues_after:
        failures.append("issues_after not empty")
    if not result.body_markdown.strip():
        failures.append("body.md empty")
    if body_has_heading_number_prefix(result.body_markdown):
        failures.append("body heading still has numbering prefix")
    if body_has_prefix_noise(result.body_markdown):
        failures.append("body still has prefix noise")
    return failures


def run_case(case_name: str, compare_output_root: Path | None, max_rounds: int | None, use_env_cleaner: bool) -> tuple[bool, list[str]]:
    fixture_path = FIXTURE_DIR / f"{case_name}.md"
    expected_case_dir = EXPECTED_DIR / case_name
    expected_cleaned = (expected_case_dir / "cleaned.md").read_text(encoding="utf-8")
    expected_body = (expected_case_dir / "body.md").read_text(encoding="utf-8")
    expected_meta = json.loads((expected_case_dir / "meta.json").read_text(encoding="utf-8"))
    md_text = fixture_path.read_text(encoding="utf-8")

    result = clean_markdown_with_llm_loop(
        md_text,
        max_rounds=max_rounds,
        use_env_cleaner=use_env_cleaner,
    )

    if compare_output_root is not None:
        case_dir = compare_output_root / case_name
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "original.md").write_text(md_text, encoding="utf-8")
        (case_dir / "cleaned.md").write_text(result.markdown_text, encoding="utf-8")
        (case_dir / "body.md").write_text(result.body_markdown, encoding="utf-8")
        (case_dir / "meta.json").write_text(
            json.dumps(
                {
                    "document_title": result.document_title,
                    "accepted": result.accepted,
                    "rounds": result.rounds,
                    "issues_after": [issue.code for issue in result.issues_after],
                    "review_summary": result.review_summary,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    mode = case_mode(case_name)
    if mode == "strict":
        failures = compare_strict(result, expected_cleaned, expected_body, expected_meta)
    else:
        failures = compare_structural(result, expected_meta)
    return (not failures, failures)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    compare_output_root = Path(args.compare_output_root) if args.compare_output_root else None
    if compare_output_root is not None:
        compare_output_root.mkdir(parents=True, exist_ok=True)

    case_names = load_case_names(args.cases)
    failed_cases: list[tuple[str, list[str]]] = []

    for case_name in case_names:
        try:
            ok, failures = run_case(
                case_name,
                compare_output_root=compare_output_root,
                max_rounds=args.max_rounds,
                use_env_cleaner=not args.no_llm,
            )
        except MarkdownCleaningError as exc:
            failed_cases.append((case_name, [str(exc)]))
            print(f"{case_name}: FAIL (cleaning error)")
            continue
        except Exception as exc:
            failed_cases.append((case_name, [f"unexpected error: {exc}"]))
            print(f"{case_name}: FAIL (unexpected error)")
            continue

        if ok:
            print(f"{case_name}: PASS")
        else:
            failed_cases.append((case_name, failures))
            print(f"{case_name}: FAIL ({', '.join(failures)})")

    if failed_cases:
        print("\nFailures:")
        for case_name, failures in failed_cases:
            print(f"- {case_name}: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
