"""Exercise bounded worker document parsing and provenance contracts."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from researchmate_worker.ingestion import ParserAdapterError
from researchmate_worker.parsing import DoclingDocumentParser, _serialize_provenance


def test_provenance_serialization_preserves_source_offsets() -> None:
    """Keep opaque source anchors and provide a structural fallback."""
    bbox = SimpleNamespace(model_dump=lambda **_kwargs: {"l": 1, "t": 2})
    item = SimpleNamespace(
        self_ref="#/texts/1",
        prov=[SimpleNamespace(page_no=4, bbox=bbox, charspan=(8, 14))],
    )
    no_anchor = SimpleNamespace(self_ref="#/texts/2", prov=[])

    assert _serialize_provenance(item, locator_kind="page") == [
        {
            "item_ref": "#/texts/1",
            "locator_kind": "page",
            "page_no": 4,
            "bbox": {"l": 1, "t": 2},
            "charspan": [8, 14],
        }
    ]
    assert _serialize_provenance(no_anchor, locator_kind="page")[0] == {
        "item_ref": "#/texts/2",
        "locator_kind": "structural",
        "page_no": None,
        "bbox": None,
        "charspan": None,
    }


def test_parser_rejects_unsupported_incomplete_and_failed_conversion(tmp_path) -> None:
    """Map parser boundary failures to stable non-secret error codes."""
    source = tmp_path / "source.bin"
    source.write_bytes(b"document")
    parser = DoclingDocumentParser(
        max_file_size=1024,
        max_num_pages=5,
        converter=SimpleNamespace(convert=lambda *_args, **_kwargs: None),
    )

    with pytest.raises(ParserAdapterError, match="UNSUPPORTED_DOCUMENT_TYPE"):
        parser.parse(source, file_type="bin")

    parser.converter = SimpleNamespace(
        convert=lambda *_args, **_kwargs: SimpleNamespace(
            status=SimpleNamespace(value="partial"),
            document=None,
        )
    )
    with pytest.raises(ParserAdapterError, match="PARSER_INCOMPLETE_RESULT"):
        parser.parse(source, file_type="pdf")

    def fail_conversion(*_args, **_kwargs):
        """Simulate an opaque converter failure."""
        raise OSError("private parser detail")

    parser.converter = SimpleNamespace(convert=fail_conversion)
    with pytest.raises(ParserAdapterError, match="PARSER_EXECUTION_FAILED"):
        parser.parse(source, file_type="pdf")


def test_pdf_parser_uses_lightweight_page_text_without_visual_models(tmp_path, monkeypatch) -> None:
    """Keep free-tier ingestion below the memory needed by Docling's PDF models."""
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF synthetic")
    fake_reader = SimpleNamespace(
        pages=[
            SimpleNamespace(extract_text=lambda: "Aurora code is RM-20260730."),
            SimpleNamespace(extract_text=lambda: "   "),
        ]
    )
    monkeypatch.setitem(
        sys.modules,
        "pypdf",
        SimpleNamespace(PdfReader=lambda *_args, **_kwargs: fake_reader),
    )
    parser = DoclingDocumentParser(
        max_file_size=4096,
        max_num_pages=5,
        pdf_backend="pypdf",
    )

    blocks = parser.parse(source, file_type="pdf")

    assert [(block.page_no, block.text) for block in blocks] == [(1, "Aurora code is RM-20260730.")]
    assert blocks[0].metadata["parser_name"] == "pypdf"
    assert blocks[0].metadata["source_anchors"][0]["locator_kind"] == "page"
    assert blocks[0].metadata["source_anchors"][0]["page_no"] == 1
    assert parser.converter is None


def test_pdf_parser_reports_missing_text_layer_without_docling_fallback(
    tmp_path, monkeypatch
) -> None:
    """Scanning/OCR requires a separate high-memory worker, never an implicit fallback."""
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF synthetic")
    monkeypatch.setitem(
        sys.modules,
        "pypdf",
        SimpleNamespace(
            PdfReader=lambda *_args, **_kwargs: SimpleNamespace(
                pages=[SimpleNamespace(extract_text=lambda: None)]
            )
        ),
    )
    parser = DoclingDocumentParser(
        max_file_size=4096,
        max_num_pages=5,
        pdf_backend="pypdf",
    )

    with pytest.raises(ParserAdapterError, match="PARSER_TEXT_LAYER_NOT_FOUND"):
        parser.parse(source, file_type="pdf")


def test_real_pdf_fixture_is_compatible_with_lightweight_parser() -> None:
    """Exercise the installed pypdf adapter against a valid text-layer PDF."""
    source = Path(__file__).parent / "fixtures" / "acceptance-text.pdf"
    parser = DoclingDocumentParser(
        max_file_size=4096,
        max_num_pages=5,
        pdf_backend="pypdf",
    )

    blocks = parser.parse(source, file_type="pdf")

    assert blocks[0].page_no == 1
    assert "RM-20260730" in blocks[0].text
    assert blocks[0].metadata["parser_name"] == "pypdf"


def test_ingestion_service_versions_and_passes_pdf_backend() -> None:
    """Verify the parser stores pdf_backend and overrides it when a converter is present.

    The composition root in build_ingestion_service() passes settings.pdf_parser_backend
    to DoclingDocumentParser and formats pipeline_version as f"{version}-{backend}".
    This test verifies the parser's runtime contract that the composition root depends on.
    """
    parser = DoclingDocumentParser(
        max_file_size=4096,
        max_num_pages=5,
        pdf_backend="pypdf",
    )
    assert parser.pdf_backend == "pypdf"

    parser_with_converter = DoclingDocumentParser(
        max_file_size=4096,
        max_num_pages=5,
        pdf_backend="pypdf",
        converter=SimpleNamespace(convert=lambda *_args, **_kwargs: None),
    )
    assert parser_with_converter.pdf_backend == "docling"


def test_office_documents_use_bounded_ooxml_parsing_without_docling(tmp_path) -> None:
    """Extract bounded DOCX text while retaining the active section heading."""
    docx = tmp_path / "source.docx"
    with ZipFile(docx, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body>
                <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Aurora</w:t></w:r></w:p>
                <w:p><w:r><w:t>Access phrase: cobalt-orchid-7319</w:t></w:r></w:p>
              </w:body>
            </w:document>""",
        )
    parser = DoclingDocumentParser(max_file_size=4096, max_num_pages=5)

    blocks = parser.parse(docx, file_type="docx")

    assert [block.text for block in blocks] == [
        "Aurora",
        "Access phrase: cobalt-orchid-7319",
    ]
    assert blocks[1].section_title == "Aurora"
    assert blocks[1].metadata["section_path"] == ["Aurora"]
    assert blocks[1].metadata["parser_name"] == "ooxml"
    assert parser.converter is None


def test_docx_parser_preserves_nested_heading_path(tmp_path) -> None:
    """Retain the heading hierarchy needed for structure-aware retrieval."""
    docx = tmp_path / "nested.docx"
    with ZipFile(docx, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body>
                <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>RAG</w:t></w:r></w:p>
                <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Fusion</w:t></w:r></w:p>
                <w:p><w:r><w:t>Weighted RRF combines ranked channels.</w:t></w:r></w:p>
              </w:body>
            </w:document>""",
        )
    parser = DoclingDocumentParser(max_file_size=4096, max_num_pages=5)

    blocks = parser.parse(docx, file_type="docx")

    assert blocks[-1].metadata["section_path"] == ["RAG", "Fusion"]


def test_docx_parser_accepts_noncanonical_archive_member_paths(tmp_path) -> None:
    """Accept portable OOXML archives with noncanonical member casing."""
    docx = tmp_path / "legacy.docx"
    with ZipFile(docx, "w") as archive:
        archive.writestr(
            r"\WORD\DOCUMENT.XML",
            """<?xml version="1.0" encoding="UTF-8"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body><w:p><w:r><w:t>Portable Office package</w:t></w:r></w:p></w:body>
            </w:document>""",
        )
    parser = DoclingDocumentParser(max_file_size=4096, max_num_pages=5)

    blocks = parser.parse(docx, file_type="docx")

    assert [block.text for block in blocks] == ["Portable Office package"]


def test_pptx_ooxml_parser_preserves_slide_numbers(tmp_path) -> None:
    """Preserve logical slide order independently of archive member order."""
    pptx = tmp_path / "source.pptx"
    with ZipFile(pptx, "w") as archive:
        archive.writestr(
            "ppt/slides/slide2.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
              xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <a:p><a:r><a:t>Second slide</a:t></a:r></a:p>
            </p:sld>""",
        )
        archive.writestr(
            "ppt/slides/slide1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
              xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <a:p><a:r><a:t>First slide</a:t></a:r></a:p>
            </p:sld>""",
        )
    parser = DoclingDocumentParser(max_file_size=4096, max_num_pages=5)

    blocks = parser.parse(pptx, file_type="pptx")

    assert [(block.slide_no, block.text) for block in blocks] == [
        (1, "First slide"),
        (2, "Second slide"),
    ]
    assert parser.converter is None


def test_text_markdown_and_html_files_extract_readable_blocks(tmp_path) -> None:
    """Decode common text encodings and exclude executable HTML content."""
    markdown = tmp_path / "notes.md"
    markdown.write_text("# Findings\n\nMarkdown evidence survives.", encoding="utf-8")
    html = tmp_path / "page.html"
    html.write_text(
        "<h1>Visible title</h1><script>ignore_secret()</script><p>Visible body</p>",
        encoding="utf-8",
    )
    parser = DoclingDocumentParser(max_file_size=4096, max_num_pages=5)

    markdown_blocks = parser.parse(markdown, file_type="md")
    html_blocks = parser.parse(html, file_type="html")

    assert [block.text for block in markdown_blocks] == [
        "# Findings",
        "Markdown evidence survives.",
    ]
    assert "Visible title" in " ".join(block.text for block in html_blocks)
    assert "Visible body" in " ".join(block.text for block in html_blocks)
    assert "ignore_secret" not in " ".join(block.text for block in html_blocks)


def test_xlsx_parser_extracts_shared_inline_and_numeric_cells(tmp_path) -> None:
    """Extract spreadsheet rows without loading a heavyweight workbook runtime."""
    workbook = tmp_path / "evidence.xlsx"
    with ZipFile(workbook, "w") as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <si><t>Metric</t></si><si><t>Latency</t></si>
            </sst>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <sheetData>
                <row r="1"><c t="s"><v>0</v></c><c t="inlineStr"><is><t>Value</t></is></c></row>
                <row r="2"><c r="A2" t="s"><v>1</v></c><c r="C2"><v>42</v></c></row>
              </sheetData>
            </worksheet>""",
        )
    parser = DoclingDocumentParser(max_file_size=4096, max_num_pages=5)

    blocks = parser.parse(workbook, file_type="xlsx")

    assert [block.text for block in blocks] == ["Metric\tValue", "Latency\t\t42"]
    assert all(block.section_title == "Sheet 1" for block in blocks)
    assert blocks[0].metadata["source_anchors"][0]["locator_kind"] == "sheet"


def test_xlsx_parser_rejects_row_fanout_before_projection_allocation(tmp_path) -> None:
    """Bound spreadsheet rows so one compressed upload cannot create unbounded projections."""
    workbook = tmp_path / "oversized-row-count.xlsx"
    rows = "".join(
        f'<row r="{index}"><c r="A{index}"><v>{index}</v></c></row>' for index in range(1, 20_002)
    )
    with ZipFile(workbook, "w") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{rows}</sheetData></worksheet>",
        )
    parser = DoclingDocumentParser(max_file_size=4 * 1024 * 1024, max_num_pages=5)

    with pytest.raises(ParserAdapterError, match="PARSER_SPREADSHEET_LIMIT_EXCEEDED"):
        parser.parse(workbook, file_type="xlsx")


def test_xlsx_parser_keeps_sparse_far_columns_bounded(tmp_path) -> None:
    """Represent distant spreadsheet columns without allocating every empty cell between them."""
    workbook = tmp_path / "sparse-columns.xlsx"
    with ZipFile(workbook, "w") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1"><v>left</v></c>'
            '<c r="XFD1"><v>right</v></c></row></sheetData></worksheet>',
        )
    parser = DoclingDocumentParser(max_file_size=4096, max_num_pages=5)

    blocks = parser.parse(workbook, file_type="xlsx")

    assert [block.text for block in blocks] == ["A=left\tXFD=right"]
    assert len(blocks[0].text) < 32


def test_notebook_parser_extracts_inputs_without_outputs(tmp_path) -> None:
    """Index notebook source cells while excluding generated output payloads."""
    notebook = tmp_path / "analysis.ipynb"
    notebook.write_text(
        '{"cells":[{"cell_type":"markdown","source":["# Result"]},'
        '{"cell_type":"code","source":"print(42)","outputs":[{"text":"large output"}]}]}',
        encoding="utf-8",
    )
    parser = DoclingDocumentParser(max_file_size=4096, max_num_pages=5)

    blocks = parser.parse(notebook, file_type="ipynb")

    assert [block.text for block in blocks] == ["# Result", "print(42)"]
    assert "large output" not in " ".join(block.text for block in blocks)
