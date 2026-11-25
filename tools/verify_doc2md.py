#!/usr/bin/env python3
"""Validate Markdown produced by fast_doc2md.py."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ERROR_MARKERS = (
    "ERROR:",
    "Loi OCR",
    "Khong render",
    "Apple Vision did not recognize",
)
NO_TEXT_MARKER = "Trang khong co lop van ban; can OCR"


def table_width(line: str) -> int:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return 0
    return len(re.split(r"(?<!\\)\|", stripped)) - 2


def verify(
    path: Path,
    min_words: int = 1,
    require_pages: bool = False,
    require_table: bool = False,
) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors = [marker for marker in ERROR_MARKERS if marker in text]
    warnings = [NO_TEXT_MARKER] if NO_TEXT_MARKER in text else []
    words = len(text.split())
    page_markers = len(re.findall(r"<!-- Page \d+ -->", text))

    table_count = 0
    table_widths: list[int] = []
    current_widths: list[int] = []
    for line in lines + [""]:
        width = table_width(line)
        if width:
            current_widths.append(width)
            continue
        if current_widths:
            table_count += 1
            table_widths.extend(current_widths)
            if len(set(current_widths)) != 1:
                errors.append("inconsistent-table-width")
            current_widths = []

    if words < min_words:
        errors.append(f"word-count<{min_words}")
    if require_pages and page_markers == 0:
        errors.append("missing-page-markers")
    if require_table and table_count == 0:
        errors.append("missing-markdown-table")

    return {
        "path": str(path),
        "status": "ok" if not errors else "failed",
        "bytes": path.stat().st_size,
        "words": words,
        "page_markers": page_markers,
        "tables": table_count,
        "table_rows": len(table_widths),
        "warnings": warnings,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--min-words", type=int, default=1)
    parser.add_argument("--require-pages", action="store_true")
    parser.add_argument("--require-table", action="store_true")
    args = parser.parse_args()

    result = verify(
        args.input.expanduser().resolve(),
        min_words=args.min_words,
        require_pages=args.require_pages,
        require_table=args.require_table,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
