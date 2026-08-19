from pathlib import Path

from backend.md2word import cli


def test_cli_lists_templates(capsys):
    assert cli.main(["--list-templates"]) == 0
    out = capsys.readouterr().out
    assert "reference" in out


def test_cli_converts_markdown_with_template(tmp_path: Path):
    md_path = tmp_path / "input.md"
    output_path = tmp_path / "output.docx"
    md_path.write_text("# 系统说明书\n\n## 概述\n\n正文\n", encoding="utf-8")

    assert cli.main(
        [
            "--md",
            str(md_path),
            "--output",
            str(output_path),
            "--template",
            "reference",
        ]
    ) == 0

    assert output_path.exists()
