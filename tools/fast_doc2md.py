#!/usr/bin/env python3
"""Fast local conversion of DOCX, XLSX, and PDF files to Markdown.

The converter favors deterministic, offline extraction. PDF scan detection samples
pages instead of reading the whole document. OCR is intentionally delegated to an
installed backend because OCR quality and language models vary by machine.
"""

from __future__ import annotations

import argparse
import html
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SUPPORTED = {".docx", ".xlsx", ".pdf"}


@dataclass
class PdfTableRegion:
    y0: float
    y1: float
    rows: list[list[str]]


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def markdown_cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("\r\n", "\n").replace("\r", "\n")
    return html.escape(text, quote=False).replace("|", "\\|").replace("\n", "<br>")


def markdown_table(rows: Iterable[Iterable[object]]) -> str:
    normalized: list[list[str]] = []
    width = 0
    for row in rows:
        cells = [markdown_cell(value) for value in row]
        while cells and not cells[-1]:
            cells.pop()
        if not any(cells):
            continue
        width = max(width, len(cells))
        normalized.append(cells)
    if len(normalized) < 2 or width < 2:
        return ""
    for row in normalized:
        row.extend([""] * (width - len(row)))
    lines = ["| " + " | ".join(normalized[0]) + " |"]
    lines.append("| " + " | ".join("---" for _ in range(width)) + " |")
    lines.extend("| " + " | ".join(row) + " |" for row in normalized[1:])
    return "\n".join(lines)


def convert_docx(input_path: Path, output_path: Path) -> None:
    pandoc = shutil.which("pandoc")
    if pandoc:
        media_dir = output_path.parent / f"{output_path.stem}_media"
        result = run(
            [
                pandoc,
                str(input_path),
                "--to=gfm",
                "--wrap=none",
                f"--extract-media={media_dir}",
            ]
        )
        if result.returncode == 0:
            output_path.write_text(result.stdout, encoding="utf-8")
            return

    from docx import Document

    document = Document(input_path)
    lines: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = paragraph.style.name if paragraph.style else ""
        if style.startswith("Heading"):
            raw_level = style.removeprefix("Heading").strip()
            level = min(max(int(raw_level), 1), 6) if raw_level.isdigit() else 1
            lines.append(f"{'#' * level} {text}")
        else:
            lines.append(text)
    output_path.write_text("\n\n".join(lines) + "\n", encoding="utf-8")


def nonempty_rows(rows: Iterable[tuple[object, ...]]) -> Iterable[list[str]]:
    for row in rows:
        cells = [markdown_cell(value) for value in row]
        while cells and not cells[-1]:
            cells.pop()
        if any(cells):
            yield cells


def convert_xlsx(input_path: Path, output_path: Path) -> None:
    import openpyxl

    workbook = openpyxl.load_workbook(input_path, read_only=True, data_only=True)
    with output_path.open("w", encoding="utf-8") as output:
        wrote_sheet = False
        for sheet in workbook.worksheets:
            rows = nonempty_rows(sheet.iter_rows(values_only=True))
            first = next(rows, None)
            if first is None:
                continue
            if wrote_sheet:
                output.write("\n---\n\n")
            wrote_sheet = True
            output.write(f"# Sheet: {sheet.title}\n\n")
            width = len(first)
            with tempfile.SpooledTemporaryFile(
                mode="w+", max_size=8 * 1024 * 1024, encoding="utf-8"
            ) as spool:
                for row in rows:
                    width = max(width, len(row))
                    spool.write(json.dumps(row, ensure_ascii=False) + "\n")
                first.extend([""] * (width - len(first)))
                output.write("| " + " | ".join(first) + " |\n")
                output.write("| " + " | ".join("---" for _ in range(width)) + " |\n")
                spool.seek(0)
                for line in spool:
                    row = json.loads(line)
                    row.extend([""] * (width - len(row)))
                    output.write("| " + " | ".join(row) + " |\n")
        if not wrote_sheet:
            output.write("*(File Excel trong)*\n")
    workbook.close()


def sample_page_indexes(total_pages: int, sample_size: int = 5) -> list[int]:
    if total_pages <= sample_size:
        return list(range(total_pages))
    return sorted({round(i * (total_pages - 1) / (sample_size - 1)) for i in range(sample_size)})


def pdf_is_scanned(input_path: Path, sample_size: int = 5) -> tuple[bool, dict[str, float]]:
    import fitz

    with fitz.open(input_path) as document:
        indexes = sample_page_indexes(len(document), sample_size)
        chars = 0
        image_only = 0
        for index in indexes:
            page = document[index]
            text = page.get_text("text").strip()
            chars += len(text)
            if len(text) < 50 and page.get_images(full=False):
                image_only += 1
    pages = max(len(indexes), 1)
    stats = {
        "sampled_pages": float(len(indexes)),
        "avg_chars": chars / pages,
        "image_only_ratio": image_only / pages,
    }
    return stats["avg_chars"] < 80 or stats["image_only_ratio"] > 0.5, stats


def _page_has_table_signal(page: Any) -> bool:
    lines: list[list[tuple]] = []
    words_by_position = sorted(page.get_text("words"), key=lambda item: (item[1], item[0]))
    for word in words_by_position:
        for line in reversed(lines[-3:]):
            if abs(line[0][1] - word[1]) <= 3:
                line.append(word)
                break
        else:
            lines.append([word])
    multi_cell_lines = 0
    nonempty_lines = 0
    for words in lines:
        if not words:
            continue
        nonempty_lines += 1
        words.sort(key=lambda item: item[0])
        cells = 1
        previous_x1 = words[0][2]
        for word in words[1:]:
            if word[0] - previous_x1 > 18:
                cells += 1
            previous_x1 = max(previous_x1, word[2])
        if cells >= 3:
            multi_cell_lines += 1
    return multi_cell_lines >= 4 and multi_cell_lines / max(nonempty_lines, 1) >= 0.12


def _table_rows(table: Any) -> list[list[str]]:
    return [
        [str(cell or "").replace("\r", "").replace("\n", " ").strip() for cell in row]
        for row in table.extract()
    ]


def _numeric_cell_count(row: list[str]) -> int:
    return sum(any(character.isdigit() for character in cell) for cell in row if cell)


def _borderless_table_regions(page: Any) -> list[PdfTableRegion]:
    finder = page.find_tables(strategy="text", min_words_vertical=3)
    regions: list[PdfTableRegion] = []
    for table in finder.tables:
        rows = _table_rows(table)
        if len(rows) < 4:
            continue
        nonempty_indexes = [index for index, row in enumerate(rows) if any(row)]
        cursor = 0
        while cursor < len(nonempty_indexes):
            header_index = nonempty_indexes[cursor]
            header = rows[header_index]
            if sum(bool(cell) for cell in header) < 3:
                cursor += 1
                continue

            data_indexes: list[int] = []
            misses = 0
            for row_index in nonempty_indexes[cursor + 1 :]:
                if row_index - header_index > 40:
                    break
                row = rows[row_index]
                nonempty = sum(bool(cell) for cell in row)
                numeric = _numeric_cell_count(row)
                is_data = nonempty >= 2 and numeric >= 1
                if is_data:
                    data_indexes.append(row_index)
                    misses = 0
                else:
                    misses += 1
                    if misses >= 2:
                        break
            if len(data_indexes) < 3:
                cursor += 1
                continue

            end_index = data_indexes[-1]
            selected = [row for row in rows[header_index : end_index + 1] if any(row)]
            if markdown_table(selected):
                regions.append(
                    PdfTableRegion(
                        y0=float(table.rows[header_index].bbox[1]),
                        y1=float(table.rows[end_index].bbox[3]),
                        rows=selected,
                    )
                )
            cursor = nonempty_indexes.index(end_index) + 1
    return regions


def _ruled_table_regions(page: Any) -> list[PdfTableRegion]:
    regions: list[PdfTableRegion] = []
    for table in page.find_tables().tables:
        rows = _table_rows(table)
        if markdown_table(rows):
            regions.append(
                PdfTableRegion(
                    y0=float(table.bbox[1]),
                    y1=float(table.bbox[3]),
                    rows=rows,
                )
            )
    return regions


def _page_table_regions(page: Any, layout: str) -> list[PdfTableRegion]:
    if layout == "fast":
        return []
    regions = _ruled_table_regions(page)
    if regions:
        return sorted(regions, key=lambda region: region.y0)
    if layout == "tables" or _page_has_table_signal(page):
        return sorted(_borderless_table_regions(page), key=lambda region: region.y0)
    return []


def _render_pdf_page(page: Any, layout: str) -> tuple[str, int]:
    regions = _page_table_regions(page, layout)
    if not regions:
        return page.get_text("text", sort=True).strip(), 0

    chunks: list[str] = []
    cursor = float(page.rect.y0)
    for region in regions:
        if region.y0 > cursor:
            clip = (page.rect.x0, cursor, page.rect.x1, region.y0 - 0.5)
            text = page.get_text("text", clip=clip, sort=True).strip()
            if text:
                chunks.append(text)
        table = markdown_table(region.rows)
        if table:
            chunks.append(table)
        cursor = max(cursor, region.y1 + 0.5)
    if cursor < page.rect.y1:
        clip = (page.rect.x0, cursor, page.rect.x1, page.rect.y1)
        text = page.get_text("text", clip=clip, sort=True).strip()
        if text:
            chunks.append(text)
    return "\n\n".join(chunks).strip(), len(regions)


def convert_pdf_digital(input_path: Path, output_path: Path, layout: str = "fast") -> int:
    import fitz

    table_count = 0
    with fitz.open(input_path) as document, output_path.open("w", encoding="utf-8") as output:
        for page_number, page in enumerate(document, start=1):
            text, page_tables = _render_pdf_page(page, layout)
            table_count += page_tables
            if output.tell():
                output.write("\n\n---\n\n")
            content = text or "*(Trang khong co lop van ban; can OCR)*"
            output.write(f"<!-- Page {page_number} -->\n\n{content}\n")
    return table_count


def convert_pdf_ocr(input_path: Path, output_path: Path) -> None:
    ocrmypdf = shutil.which("ocrmypdf")
    pdftotext = shutil.which("pdftotext")
    if ocrmypdf and pdftotext:
        searchable_pdf = output_path.with_suffix(".ocr.pdf")
        result = run(
            [
                ocrmypdf,
                "--skip-text",
                "--deskew",
                "--rotate-pages",
                "--language",
                "vie+eng",
                str(input_path),
                str(searchable_pdf),
            ]
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "OCR failed")
        extracted = run([pdftotext, "-layout", "-enc", "UTF-8", str(searchable_pdf), "-"])
        if extracted.returncode != 0:
            raise RuntimeError(extracted.stderr.strip() or "Text extraction after OCR failed")
        output_path.write_text(extracted.stdout, encoding="utf-8")
        searchable_pdf.unlink(missing_ok=True)
        return

    if platform.system() == "Darwin" and shutil.which("swiftc"):
        helper_source = Path(__file__).with_name("vision_ocr.swift")
        helper_binary = Path("/tmp/law-agent-vision-ocr")
        if not helper_source.exists():
            raise RuntimeError(f"Missing OCR helper: {helper_source}")
        if not helper_binary.exists() or helper_binary.stat().st_mtime < helper_source.stat().st_mtime:
            compile_result = run(
                [
                    shutil.which("swiftc") or "swiftc",
                    "-module-cache-path",
                    "/tmp/law-agent-swift-module-cache",
                    "-O",
                    str(helper_source),
                    "-o",
                    str(helper_binary),
                ]
            )
            if compile_result.returncode != 0:
                raise RuntimeError(compile_result.stderr.strip() or "Unable to compile Apple Vision OCR helper")
        ocr_result = run([str(helper_binary), str(input_path), str(output_path)])
        if ocr_result.returncode != 0:
            raise RuntimeError(ocr_result.stderr.strip() or "Apple Vision OCR failed")
        return

    raise RuntimeError("PDF scan requires OCRmyPDF or macOS Apple Vision")


def convert(
    input_path: Path,
    output_dir: Path,
    pdf_mode: str,
    overwrite: bool = False,
    pdf_layout: str = "fast",
) -> tuple[Path, str]:
    suffix = input_path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"Unsupported format: {suffix}")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{input_path.stem}.md"
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {output_path}; pass --overwrite to replace it")

    try:
        if suffix == ".docx":
            convert_docx(input_path, output_path)
            mode = "docx"
        elif suffix == ".xlsx":
            convert_xlsx(input_path, output_path)
            mode = "xlsx"
        else:
            if pdf_mode == "auto":
                scanned, stats = pdf_is_scanned(input_path)
                mode = "ocr" if scanned else "digital"
                print(
                    f"PDF sample: {int(stats['sampled_pages'])} pages, "
                    f"{stats['avg_chars']:.1f} chars/page, "
                    f"{stats['image_only_ratio']:.0%} image-only",
                    file=sys.stderr,
                )
            else:
                mode = pdf_mode
            if mode == "ocr":
                convert_pdf_ocr(input_path, output_path)
            else:
                table_count = convert_pdf_digital(input_path, output_path, pdf_layout)
                print(
                    f"PDF layout: {pdf_layout}, {table_count} table(s) rendered",
                    file=sys.stderr,
                )
    except Exception:
        output_path.unlink(missing_ok=True)
        raise
    return output_path, mode


def main() -> int:
    parser = argparse.ArgumentParser(description="Fast offline document-to-Markdown converter")
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output-dir", type=Path)
    parser.add_argument("--pdf-mode", choices=("auto", "digital", "ocr"), default="auto")
    parser.add_argument(
        "--pdf-layout",
        choices=("fast", "auto", "tables"),
        default="fast",
        help="PDF digital layout mode: fast text, auto table detection, or forced table detection",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        parser.error(f"File not found: {input_path}")
    output_dir = (args.output_dir or input_path.parent).expanduser().resolve()
    try:
        output_path, mode = convert(
            input_path,
            output_dir,
            args.pdf_mode,
            args.overwrite,
            args.pdf_layout,
        )
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"{output_path}\tmode={mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
