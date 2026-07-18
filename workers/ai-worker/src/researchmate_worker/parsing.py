from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from pathlib import Path
from typing import Any

from researchmate_worker.ingestion import ParsedBlock, ParserAdapterError


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def _serialize_provenance(item: Any, *, locator_kind: str) -> list[dict[str, Any]]:
    anchors = []
    for provenance in item.prov:
        anchors.append(
            {
                "item_ref": item.self_ref,
                "locator_kind": locator_kind,
                "page_no": provenance.page_no,
                "bbox": provenance.bbox.model_dump(mode="json"),
                # This is an opaque backend source offset, not an item.text slice.
                "charspan": list(provenance.charspan),
            }
        )
    if not anchors:
        anchors.append(
            {
                "item_ref": item.self_ref,
                "locator_kind": "structural",
                "page_no": None,
                "bbox": None,
                "charspan": None,
            }
        )
    return anchors


class DoclingDocumentParser:
    """Docling boundary that preserves source anchors and never invents DOCX pages."""

    def __init__(
        self,
        *,
        max_file_size: int,
        max_num_pages: int,
        artifacts_path: Path | None = None,
        converter: Any | None = None,
    ) -> None:
        self.max_file_size = max_file_size
        self.max_num_pages = max_num_pages
        if converter is None:
            try:
                from docling.datamodel.base_models import InputFormat
                from docling.datamodel.pipeline_options import PdfPipelineOptions
                from docling.document_converter import DocumentConverter, PdfFormatOption
            except ImportError as exc:
                raise ParserAdapterError("PARSER_NOT_INSTALLED") from exc
            pdf_options = PdfPipelineOptions(
                artifacts_path=artifacts_path,
                enable_remote_services=False,
            )
            converter = DocumentConverter(
                allowed_formats=[InputFormat.PDF, InputFormat.DOCX, InputFormat.PPTX],
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
                },
            )
        self.converter = converter

    def parse(self, source: Path, *, file_type: str) -> list[ParsedBlock]:
        if file_type not in {"pdf", "docx", "pptx"}:
            raise ParserAdapterError("UNSUPPORTED_DOCUMENT_TYPE")
        try:
            from docling.datamodel.base_models import DocumentStream
            from docling_core.types.doc import ContentLayer, TableItem, TextItem

            result = self.converter.convert(
                DocumentStream(name=source.name, stream=BytesIO(source.read_bytes())),
                raises_on_error=False,
                max_file_size=self.max_file_size,
                max_num_pages=self.max_num_pages,
            )
        except ParserAdapterError:
            raise
        except Exception as exc:
            raise ParserAdapterError("PARSER_EXECUTION_FAILED") from exc
        if getattr(result.status, "value", str(result.status)) != "success":
            raise ParserAdapterError("PARSER_INCOMPLETE_RESULT")

        document = result.document
        locator_kind = "slide" if file_type == "pptx" else "page"
        parser_metadata = {
            "parser_name": "docling",
            "parser_version": _package_version("docling"),
            "parser_core_version": _package_version("docling-core"),
        }
        blocks: list[ParsedBlock] = []
        active_section: str | None = None
        try:
            items = document.iterate_items(
                with_groups=False,
                traverse_pictures=False,
                included_content_layers={ContentLayer.BODY},
            )
            for ordinal, (item, level) in enumerate(items):
                if isinstance(item, TextItem):
                    item_text = item.text.strip()
                elif isinstance(item, TableItem):
                    item_text = item.export_to_markdown(doc=document).strip()
                else:
                    continue
                if not item_text:
                    continue
                label = getattr(item.label, "value", str(item.label))
                if label in {"title", "section_header"}:
                    active_section = item_text
                anchors = _serialize_provenance(item, locator_kind=locator_kind)
                primary_page = anchors[0]["page_no"]
                blocks.append(
                    ParsedBlock(
                        text=item_text,
                        page_no=primary_page if file_type == "pdf" else None,
                        slide_no=primary_page if file_type == "pptx" else None,
                        section_title=active_section,
                        metadata={
                            **parser_metadata,
                            "source_item_ref": item.self_ref,
                            "source_ordinal": ordinal,
                            "source_label": label,
                            "source_level": level,
                            "source_anchors": anchors,
                        },
                    )
                )
        except Exception as exc:
            raise ParserAdapterError("PARSER_OUTPUT_INVALID") from exc
        return blocks
