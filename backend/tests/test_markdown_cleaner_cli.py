import json
from pathlib import Path
from types import SimpleNamespace

from backend.md2word import markdown_cleaner_cli


def test_cli_writes_cleaned_markdown_body_and_meta(monkeypatch, tmp_path):
    input_path = tmp_path / "input.md"
    input_path.write_text("# 原始标题\n\n正文\n", encoding="utf-8")
    output_path = tmp_path / "cleaned.md"
    body_output_path = tmp_path / "body.md"
    meta_output_path = tmp_path / "meta.json"

    monkeypatch.setattr(
        markdown_cleaner_cli,
        "clean_markdown_with_llm_loop",
        lambda md_text, max_rounds=None, use_env_cleaner=True: SimpleNamespace(
            markdown_text="# 清洗后标题\n\n## 一级章节\n\n正文",
            body_markdown="## 一级章节\n\n正文",
            document_title="清洗后标题",
            agent_used=True,
            accepted=True,
            rounds=2,
            source="agent",
            changed=True,
            review_summary="语义结构复核通过。",
            issues_before=[],
            issues_after=[],
            trace=[],
        ),
    )

    exit_code = markdown_cleaner_cli.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--body-output",
            str(body_output_path),
            "--meta-output",
            str(meta_output_path),
        ]
    )

    assert exit_code == 0
    assert output_path.read_text(encoding="utf-8") == "# 清洗后标题\n\n## 一级章节\n\n正文"
    assert body_output_path.read_text(encoding="utf-8") == "## 一级章节\n\n正文"
    meta = json.loads(meta_output_path.read_text(encoding="utf-8"))
    assert meta["document_title"] == "清洗后标题"
    assert meta["accepted"] is True


def test_cli_prints_to_stdout_when_output_missing(monkeypatch, tmp_path, capsys):
    input_path = tmp_path / "input.md"
    input_path.write_text("# 原始标题\n\n正文\n", encoding="utf-8")

    monkeypatch.setattr(
        markdown_cleaner_cli,
        "clean_markdown_with_llm_loop",
        lambda md_text, max_rounds=None, use_env_cleaner=True: SimpleNamespace(
            markdown_text="# 清洗后标题\n\n## 一级章节\n\n正文",
            body_markdown="## 一级章节\n\n正文",
            document_title="清洗后标题",
            agent_used=True,
            accepted=True,
            rounds=1,
            source="agent",
            changed=True,
            review_summary="语义结构复核通过。",
            issues_before=[],
            issues_after=[],
            trace=[],
        ),
    )

    exit_code = markdown_cleaner_cli.main(["--input", str(input_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "# 清洗后标题" in captured.out
    assert captured.err == ""


def test_cli_compare_output_writes_all_artifacts(monkeypatch, tmp_path):
    input_path = tmp_path / "input.md"
    input_path.write_text("# 原始标题\n\n正文\n", encoding="utf-8")
    compare_dir = tmp_path / "compare"

    monkeypatch.setattr(
        markdown_cleaner_cli,
        "clean_markdown_with_llm_loop",
        lambda md_text, max_rounds=None, use_env_cleaner=True: SimpleNamespace(
            markdown_text="# 清洗后标题\n\n## 一级章节\n\n正文",
            body_markdown="## 一级章节\n\n正文",
            document_title="清洗后标题",
            agent_used=True,
            accepted=True,
            rounds=1,
            source="agent",
            changed=True,
            review_summary="语义结构复核通过。",
            issues_before=[],
            issues_after=[],
            trace=[],
        ),
    )

    exit_code = markdown_cleaner_cli.main(
        [
            "--input",
            str(input_path),
            "--compare-output",
            str(compare_dir),
        ]
    )

    assert exit_code == 0
    assert (compare_dir / "original.md").read_text(encoding="utf-8") == "# 原始标题\n\n正文\n"
    assert (compare_dir / "cleaned.md").read_text(encoding="utf-8") == "# 清洗后标题\n\n## 一级章节\n\n正文"
    assert (compare_dir / "body.md").read_text(encoding="utf-8") == "## 一级章节\n\n正文"
    meta = json.loads((compare_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["document_title"] == "清洗后标题"


def test_cli_returns_error_for_missing_input(tmp_path, capsys):
    missing_path = tmp_path / "missing.md"

    exit_code = markdown_cleaner_cli.main(["--input", str(missing_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Markdown not found" in captured.err
