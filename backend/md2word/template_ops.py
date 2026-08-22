from __future__ import annotations


def replace_template_placeholders(doc, mapping: dict[str, str]) -> None:
    for paragraph in _iter_paragraph_elements(doc):
        _replace_tokens_in_paragraph_element(paragraph, mapping)


def find_body_placeholder(doc, token: str):
    for paragraph in _iter_paragraph_elements(doc):
        if token in _paragraph_text(paragraph):
            return paragraph
    return None


def remove_paragraphs_containing_token(doc, token: str) -> None:
    for paragraph in list(_iter_paragraph_elements(doc)):
        if token in _paragraph_text(paragraph):
            parent = paragraph.getparent()
            if parent is not None:
                parent.remove(paragraph)


def replace_textbox_placeholder(doc, token: str, value: str) -> None:
    if not value:
        return
    for paragraph in _iter_textbox_paragraph_elements(doc):
        if token in _paragraph_text(paragraph):
            _set_paragraph_text(paragraph, value)
            return


def _iter_paragraph_elements(doc):
    yield from doc._element.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")
    for section in doc.sections:
        for part in (section.header, section.footer):
            yield from part._element.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")


def _replace_tokens_in_paragraph_element(paragraph, mapping: dict[str, str]) -> None:
    text_nodes = paragraph.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
    if not text_nodes:
        return
    full_text = "".join(node.text or "" for node in text_nodes)
    replaced = full_text
    for key, value in mapping.items():
        replaced = replaced.replace(key, value)
        spaced_key = key.replace("{{", "{{ ").replace("}}", " }}")
        replaced = replaced.replace(spaced_key, value)
    if replaced == full_text:
        return
    text_nodes[0].text = replaced
    for node in text_nodes[1:]:
        node.text = ""


def _paragraph_text(paragraph) -> str:
    return "".join(
        node.text or ""
        for node in paragraph.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
    )


def _iter_textbox_paragraph_elements(doc):
    yield from doc._element.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}txbxContent/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")
    for section in doc.sections:
        for part in (section.header, section.footer):
            yield from part._element.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}txbxContent/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")


def _set_paragraph_text(paragraph, text: str) -> None:
    text_nodes = paragraph.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
    if not text_nodes:
        return
    text_nodes[0].text = text
    for node in text_nodes[1:]:
        node.text = ""
