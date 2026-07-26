from pathlib import Path
from types import SimpleNamespace

from backend.md2word import markdown_cleaner_regression_cli


def test_load_case_names_defaults_to_expected_directories(monkeypatch, tmp_path):
    expected_dir = tmp_path / "expected"
    (expected_dir / "case-a").mkdir(parents=True)
    (expected_dir / "case-b").mkdir(parents=True)
    (expected_dir / "note.txt").write_text("x", encoding="utf-8")

    monkeypatch.setattr(markdown_cleaner_regression_cli, "EXPECTED_DIR", expected_dir)

    case_names = markdown_cleaner_regression_cli.load_case_names(None)

    assert case_names == ["case-a", "case-b"]


def test_load_case_names_prefers_requested_cases():
    case_names = markdown_cleaner_regression_cli.load_case_names(["a", "b"])

    assert case_names == ["a", "b"]


def test_case_mode_uses_strict_for_semantic_cases():
    assert markdown_cleaner_regression_cli.case_mode("semantic-title-prefix-noise") == "strict"
    assert markdown_cleaner_regression_cli.case_mode("syntax-heading-list-fence-errors") == "structural"
    assert markdown_cleaner_regression_cli.case_mode("combined-syntax-and-semantic-mixed") == "structural"


def test_compare_structural_checks_core_guards():
    result = SimpleNamespace(
        document_title="标题",
        accepted=True,
        issues_after=[],
        body_markdown="## 项目概述\n\n正文",
    )

    failures = markdown_cleaner_regression_cli.compare_structural(
        result,
        {"document_title": "标题", "accepted": True},
    )

    assert failures == []


def test_compare_structural_rejects_numbering_and_noise():
    result = SimpleNamespace(
        document_title="标题",
        accepted=True,
        issues_after=[],
        body_markdown="项目名称：示例\n\n## 第一章 项目概述\n\n正文",
    )

    failures = markdown_cleaner_regression_cli.compare_structural(
        result,
        {"document_title": "标题", "accepted": True},
    )

    assert "body heading still has numbering prefix" in failures
    assert "body still has prefix noise" in failures
