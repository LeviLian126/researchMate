"""Normalize parser package metadata and provenance without loading conversion models."""

from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError, version
from typing import Any

LOGGER = logging.getLogger(__name__)


def _normalized_archive_member(member: str) -> str:
    return member.replace("\\", "/").lstrip("/").casefold()


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
