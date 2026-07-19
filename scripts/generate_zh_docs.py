from __future__ import annotations

import os
import posixpath
import re
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from deep_translator import GoogleTranslator

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

SOURCE_PAGES = (
    Path("index.html"),
    Path("product/index.html"),
    Path("architecture/index.html"),
    Path("contracts/data/index.html"),
    Path("contracts/api/index.html"),
)

SKIP_TAGS = {"code", "pre", "script", "style", "kbd", "samp", "var"}
TRANSLATABLE_ATTRIBUTES = ("aria-label", "title", "placeholder", "data-title", "data-detail")
URL_ATTRIBUTES = ("href", "src")
MAX_BATCH_CHARS = 2600
MAX_BATCH_ITEMS = 18


def is_translatable(text: str) -> bool:
    stripped = text.strip()
    if not stripped or not re.search(r"[A-Za-z]", stripped):
        return False
    if re.fullmatch(r"[A-Za-z0-9_./:@+\-#?=&%<>()[\]{}'\"|* ]+", stripped):
        words = stripped.split()
        if len(words) <= 2 and any(ch in stripped for ch in "_./:@#?=&%<>{}[]()"):
            return False
    return True


def translate_batches(texts: list[str]) -> list[str]:
    if not texts:
        return []

    translator = GoogleTranslator(source="en", target="zh-CN")
    translated: list[str] = []
    cursor = 0

    while cursor < len(texts):
        batch: list[str] = []
        size = 0
        while cursor + len(batch) < len(texts) and len(batch) < MAX_BATCH_ITEMS:
            candidate = texts[cursor + len(batch)]
            projected = size + len(candidate)
            if batch and projected > MAX_BATCH_CHARS:
                break
            batch.append(candidate)
            size = projected

        last_error: Exception | None = None
        for attempt in range(5):
            try:
                pieces = translator.translate_batch(batch)
                if not isinstance(pieces, list) or len(pieces) != len(batch):
                    raise RuntimeError(
                        f"Translation batch mismatch: expected {len(batch)}, got {len(pieces) if isinstance(pieces, list) else type(pieces)}"
                    )
                translated.extend(str(piece) for piece in pieces)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                time.sleep(2 ** attempt)
        if last_error is not None:
            raise RuntimeError(f"Translation failed near item {cursor}: {last_error}") from last_error
        cursor += len(batch)

    return translated


def preserve_spacing(original: str, translated: str) -> str:
    leading = original[: len(original) - len(original.lstrip())]
    trailing = original[len(original.rstrip()) :]
    return f"{leading}{translated.strip()}{trailing}"


def collect_text_targets(soup: BeautifulSoup) -> tuple[list[NavigableString], list[str]]:
    nodes: list[NavigableString] = []
    texts: list[str] = []
    for node in soup.find_all(string=True):
        if isinstance(node, Comment):
            continue
        parent = node.parent
        if not isinstance(parent, Tag) or parent.name in SKIP_TAGS:
            continue
        value = str(node)
        if is_translatable(value):
            nodes.append(node)
            texts.append(value.strip())
    return nodes, texts


def collect_attribute_targets(soup: BeautifulSoup) -> tuple[list[tuple[Tag, str]], list[str]]:
    targets: list[tuple[Tag, str]] = []
    texts: list[str] = []
    for tag in soup.find_all(True):
        for attribute in TRANSLATABLE_ATTRIBUTES:
            value = tag.get(attribute)
            if isinstance(value, str) and is_translatable(value):
                targets.append((tag, attribute))
                texts.append(value)
    return targets, texts


def rewrite_url(value: str, source_rel: Path, output_rel: Path) -> str:
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or value.startswith(("#", "mailto:", "tel:", "javascript:")):
        return value

    source_dir = source_rel.parent.as_posix()
    output_dir = output_rel.parent.as_posix()
    resolved = posixpath.normpath(posixpath.join(source_dir, parsed.path))

    if resolved in {page.as_posix() for page in SOURCE_PAGES}:
        resolved = posixpath.join("zh", resolved)

    relative = posixpath.relpath(resolved, output_dir or ".")
    if parsed.path.endswith("/") and not relative.endswith("/"):
        relative += "/"
    return urlunsplit(("", "", relative, parsed.query, parsed.fragment))


def structure_signature(soup: BeautifulSoup) -> tuple[list[str], list[str], int, int, int]:
    return (
        [tag.name for tag in soup.find_all(True)],
        [str(tag["id"]) for tag in soup.find_all(id=True)],
        len(soup.find_all("tr")),
        len(soup.find_all("details")),
        len(soup.find_all("a")),
    )


def translate_page(source_rel: Path) -> Path:
    source_path = DOCS / source_rel
    output_rel = Path("zh") / source_rel
    output_path = DOCS / output_rel

    source_html = source_path.read_text(encoding="utf-8")
    source_soup = BeautifulSoup(source_html, "html.parser")
    soup = BeautifulSoup(source_html, "html.parser")
    if soup.html is None:
        raise RuntimeError(f"Missing html element: {source_path}")
    soup.html["lang"] = "zh-CN"

    nodes, node_texts = collect_text_targets(soup)
    for node, translated in zip(nodes, translate_batches(node_texts), strict=True):
        node.replace_with(preserve_spacing(str(node), translated))

    attributes, attribute_texts = collect_attribute_targets(soup)
    for (tag, attribute), translated in zip(
        attributes, translate_batches(attribute_texts), strict=True
    ):
        tag[attribute] = translated.strip()

    for tag in soup.find_all(True):
        for attribute in URL_ATTRIBUTES:
            value = tag.get(attribute)
            if isinstance(value, str):
                tag[attribute] = rewrite_url(value, source_rel, output_rel)

    if structure_signature(source_soup) != structure_signature(soup):
        raise RuntimeError(f"Structural parity failed for {source_rel}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "<!DOCTYPE html>\n" + str(soup), encoding="utf-8", newline="\n"
    )
    return output_path


def main() -> None:
    if os.environ.get("CI") != "true":
        print("Generating full Chinese documentation from the English source pages.")
    for path in (translate_page(page) for page in SOURCE_PAGES):
        print(path.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
