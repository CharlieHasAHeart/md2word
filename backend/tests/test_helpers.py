from backend import main


def test_derive_title_uses_first_markdown_heading():
    assert main.derive_title('# Markdown 标题\n\n内容', 'demo.md') == 'Markdown 标题'


def test_derive_title_falls_back_to_file_stem():
    assert main.derive_title('没有一级标题', 'fallback-name.md') == 'fallback-name'


def test_cleanup_temp_file_ignores_missing_file(tmp_path):
    missing = tmp_path / 'missing.docx'
    main.cleanup_temp_file(str(missing))
    assert not missing.exists()
