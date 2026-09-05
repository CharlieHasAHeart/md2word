import json
from pathlib import Path

from backend.md2word.document_schema import export_markdown_document


def test_export_markdown_document_builds_baseline_block_payload(tmp_path: Path):
    image_path = tmp_path / "images" / "screen.png"
    image_path.parent.mkdir()
    image_path.write_bytes(b"fake")

    payload = export_markdown_document(
        "# 1. 系统说明书\n\n"
        "标题下说明\n"
        "第二行说明\n\n"
        "功能概述\n"
        "---\n\n"
        "- [x] 已完成项目\n"
        "- 子项 A\n\n"
        "1. 第一步\n"
        "2. 第二步\n\n"
        "> 引用一\n"
        "> 引用二\n\n"
        "```python\n"
        "print('x')\n"
        "```\n\n"
        "| 字段 | 说明 |\n"
        "| --- | --- |\n"
        "| title | 文档标题 |\n\n"
        "![截图](images/screen.png)\n",
        source_path=tmp_path / "input.md",
    )

    assert payload["schema_version"] == "1.0.0"
    assert payload["document_title"] == "系统说明书"
    assert payload["source"] == {
        "path": str(tmp_path / "input.md"),
        "mode": "baseline",
    }

    blocks = payload["blocks"]
    assert [block["type"] for block in blocks] == [
        "heading",
        "paragraph",
        "paragraph",
        "heading",
        "unordered_list",
        "ordered_list",
        "blockquote",
        "code_block",
        "table",
        "image",
    ]

    assert blocks[0]["text"] == "系统说明书"
    assert blocks[3]["text"] == "功能概述"
    assert blocks[4]["items"] == [
        {"text": "已完成项目", "level": 1},
        {"text": "子项A", "level": 1},
    ]
    assert blocks[5]["items"] == [
        {"text": "第一步", "level": 1},
        {"text": "第二步", "level": 1},
    ]
    assert blocks[6]["text"] == "引用一\n引用二"
    assert blocks[7]["fence"] == "```"
    assert blocks[7]["language"] == "python"
    assert blocks[7]["text"] == "print('x')"
    assert blocks[8]["header"] == ["字段", "说明"]
    assert blocks[8]["rows"] == [["title", "文档标题"]]
    assert blocks[9]["caption"] == "截图"
    assert blocks[9]["target"] == "images/screen.png"
    assert blocks[9]["exists"] is True
    assert blocks[9]["supported"] is True


def test_export_markdown_document_supports_ai_enhanced_mode(tmp_path: Path):
    payload = export_markdown_document(
        "# 系统说明书\n\n"
        "封面噪声\n\n"
        "## 目录\n\n"
        "目录内容\n\n"
        "## 第一章 概述\n\n"
        "正文\n",
        source_path=tmp_path / "input.md",
        mode="ai_enhanced",
    )

    assert payload["source"]["mode"] == "ai_enhanced"
    assert [block["type"] for block in payload["blocks"]] == ["heading", "heading", "paragraph"]
    assert [block["text"] for block in payload["blocks"] if "text" in block] == ["系统说明书", "概述", "正文"]


def test_markdown_document_schema_file_is_valid_json():
    schema_path = Path("backend/md2word/docs/markdown-document-schema.json")
    parsed = json.loads(schema_path.read_text(encoding="utf-8"))

    assert parsed["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert parsed["properties"]["blocks"]["items"]["$ref"] == "#/$defs/block"
