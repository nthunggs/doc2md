from __future__ import annotations

import gc
import tempfile
import tracemalloc
import unittest
from pathlib import Path

import fitz
import openpyxl

from tools.fast_doc2md import convert_pdf_digital, convert_xlsx, sample_page_indexes
from tools.verify_doc2md import verify


class Doc2MdTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="doc2md-test-")
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_borderless_pdf(self, path: Path) -> None:
        document = fitz.open()
        page = document.new_page()
        columns = [50, 180, 280, 380]
        rows = [
            ["Product", "Qty", "Price", "Status"],
            ["Whey", "10", "20.00", "OK"],
            ["Creatine", "12", "15.00", "OK"],
            ["Protein", "5", "40.00", "Hold"],
            ["Vitamin", "8", "12.00", "OK"],
        ]
        for row_index, row in enumerate(rows):
            y_position = 80 + row_index * 25
            for x_position, text in zip(columns, row):
                page.insert_text((x_position, y_position), text, fontsize=10)
        document.save(path)
        document.close()

    def make_text_pdf(self, path: Path, pages: int) -> None:
        document = fitz.open()
        for page_number in range(1, pages + 1):
            page = document.new_page()
            page.insert_text((50, 80), f"Page {page_number} legal text", fontsize=10)
        document.save(path)
        document.close()

    def test_sample_page_indexes_cover_document(self) -> None:
        self.assertEqual(sample_page_indexes(3), [0, 1, 2])
        self.assertEqual(sample_page_indexes(100), [0, 25, 50, 74, 99])

    def test_pdf_auto_renders_borderless_table(self) -> None:
        source = self.root / "borderless.pdf"
        output = self.root / "borderless.md"
        self.make_borderless_pdf(source)

        table_count = convert_pdf_digital(source, output, layout="auto")
        markdown = output.read_text(encoding="utf-8")

        self.assertEqual(table_count, 1)
        self.assertIn("| Product | Qty | Price | Status |", markdown)
        self.assertIn("| Creatine | 12 | 15.00 | OK |", markdown)
        self.assertIn("<!-- Page 1 -->", markdown)
        self.assertEqual(verify(output, require_pages=True, require_table=True)["status"], "ok")

    def test_pdf_fast_preserves_plain_text_path(self) -> None:
        source = self.root / "fast.pdf"
        output = self.root / "fast.md"
        self.make_borderless_pdf(source)

        table_count = convert_pdf_digital(source, output, layout="fast")
        markdown = output.read_text(encoding="utf-8")

        self.assertEqual(table_count, 0)
        self.assertNotIn("| Product |", markdown)
        self.assertIn("Product", markdown)

    def test_xlsx_has_no_nan_or_unnamed_headers(self) -> None:
        source = self.root / "form.xlsx"
        output = self.root / "form.md"
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Declaration"
        sheet.append([None, "Field", None, "Value"])
        sheet.append([None, "Importer", None, "Sports Plus"])
        sheet.append([None, "HS", None, "1806"])
        workbook.save(source)
        workbook.close()

        convert_xlsx(source, output)
        markdown = output.read_text(encoding="utf-8")

        self.assertNotIn("NaN", markdown)
        self.assertNotIn("Unnamed:", markdown)
        self.assertIn("Sports Plus", markdown)
        self.assertEqual(verify(output, require_table=True)["status"], "ok")

    def test_pdf_python_memory_is_near_constant(self) -> None:
        peaks: dict[int, int] = {}
        for page_count in (50, 200):
            source = self.root / f"memory-{page_count}.pdf"
            output = self.root / f"memory-{page_count}.md"
            self.make_text_pdf(source, page_count)
            gc.collect()
            tracemalloc.start()
            convert_pdf_digital(source, output, layout="fast")
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peaks[page_count] = peak

        self.assertLess(peaks[200] / max(peaks[50], 1), 2.5)


if __name__ == "__main__":
    unittest.main()
