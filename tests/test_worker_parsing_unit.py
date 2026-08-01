"""Exercise bounded worker document parsing and provenance contracts."""
from __future__ import annotations

import sys
from inspect import getsource
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from researchmate_worker import tasks
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
        parser.parse(source, file_type="txt")

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


def test_pdf_parser_uses_lightweight_page_text_without_visual_models(
    tmp_path, monkeypatch
) -> None:
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

    assert [(block.page_no, block.text) for block in blocks] == [
        (1, "Aurora code is RM-20260730.")
    ]
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
    """Keep parser backend and pipeline versions in the ingestion composition root."""
    source = getsource(tasks.build_ingestion_service)

    assert "pdf_backend=settings.pdf_parser_backend" in source
    assert "settings.parser_pipeline_version" in source
    assert "settings.pdf_parser_backend" in source


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
    assert blocks[1].metadata["parser_name"] == "ooxml"
    assert parser.converter is None


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


