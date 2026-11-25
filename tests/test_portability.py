from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import fitz
import openpyxl
from docx import Document

from tools.fast_doc2md import convert_pdf_ocr, pdf_is_scanned
from tools.verify_doc2md import verify

ROOT = Path(__file__).resolve().parents[1]


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="doc2md-portability-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "Tài liệu có khoảng trắng"
        self.root.mkdir()

    def text_pdf(self, path):
        with fitz.open() as document:
            for number in (1, 2):
                page = document.new_page()
                page.insert_text((50, 80), f"Document text page {number}")
            document.save(path)

    def test_cli_handles_unicode_paths_and_preserves_sources(self):
        docx = self.root / "Tài liệu Word.docx"
        document = Document()
        document.add_heading("Tiêu đề kiểm thử", 1)
        document.add_paragraph("Nội dung tiếng Việt trong tài liệu kiểm thử.")
        document.save(docx)
        xlsx = self.root / "Bảng tính.xlsx"
        workbook = openpyxl.Workbook()
        workbook.active.append(["Sản phẩm", "Số lượng"])
        workbook.active.append(["Kiểm thử", 5])
        workbook.save(xlsx)
        workbook.close()
        pdf = self.root / "Văn bản PDF.pdf"
        self.text_pdf(pdf)
        output = self.root / "Kết quả"
        for source in (docx, xlsx, pdf):
            with self.subTest(source=source.suffix):
                original = hashlib.sha256(source.read_bytes()).digest()
                if os.name == "nt":
                    command = f'cmd.exe /d /s /c ""{ROOT / "doc2md.cmd"}" "{source}" -o "{output}""'
                else:
                    command = [sys.executable, "-B", str(ROOT / "tools/fast_doc2md.py"), str(source), "-o", str(output)]
                result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stderr)
                target = output / f"{source.stem}.md"
                self.assertEqual(verify(target)["status"], "ok")
                if source.suffix == ".docx":
                    self.assertIn("tiếng Việt", target.read_text(encoding="utf-8"))
                repeated = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
                self.assertNotEqual(repeated.returncode, 0)
                self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), original)
                if os.name == "nt":
                    checked = subprocess.run(f'cmd.exe /d /s /c ""{ROOT / "verify-doc2md.cmd"}" "{target}""', capture_output=True, text=True, encoding="utf-8")
                    self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_short_digital_pdf_does_not_require_ocr(self):
        source = self.root / "short.pdf"
        self.text_pdf(source)
        scanned, statistics = pdf_is_scanned(source)
        self.assertFalse(scanned)
        self.assertLess(statistics["avg_chars"], 80)

    def test_ocr_keeps_page_markers_without_poppler_or_sidecar_overwrite(self):
        source = self.root / "scan.pdf"
        self.text_pdf(source)
        output = self.root / "scan.md"
        sidecar = self.root / "scan.ocr.pdf"
        sidecar.write_bytes(b"existing user file")
        intermediate = []

        def fake_ocr(command):
            temporary_pdf = Path(command[-1])
            intermediate.append(temporary_pdf)
            temporary_pdf.write_bytes(source.read_bytes())
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("tools.fast_doc2md.find_executable", return_value="ocrmypdf.exe"), patch("tools.fast_doc2md.run", side_effect=fake_ocr):
            convert_pdf_ocr(source, output)
        self.assertEqual(verify(output, require_pages=True)["page_markers"], 2)
        self.assertEqual(sidecar.read_bytes(), b"existing user file")
        self.assertTrue(intermediate)
        self.assertFalse(intermediate[0].parent.exists())

    def test_ocr_failure_cleans_temporary_files(self):
        intermediate = []

        def fail_ocr(command):
            path = Path(command[-1])
            intermediate.append(path)
            path.write_bytes(b"partial OCR output")
            return subprocess.CompletedProcess(command, 1, "", "missing language data")

        with patch("tools.fast_doc2md.find_executable", return_value="ocrmypdf.exe"), patch("tools.fast_doc2md.run", side_effect=fail_ocr):
            with self.assertRaisesRegex(RuntimeError, "missing language data"):
                convert_pdf_ocr(self.root / "scan.pdf", self.root / "scan.md")
        self.assertFalse(intermediate[0].parent.exists())

    @unittest.skipUnless(os.environ.get("DOC2MD_TEST_OCR") == "1", "Opt-in real Tesseract/OCRmyPDF integration")
    def test_real_scanned_pdf_ocr(self):
        source = self.root / "Bản scan.pdf"
        with fitz.open() as text_document, fitz.open() as scan:
            page = text_document.new_page()
            for line in range(20):
                page.insert_text((40, 50 + line * 35), "DOC2MD WINDOWS OCR validation document", fontsize=20)
            image = page.get_pixmap(dpi=150)
            scan.new_page().insert_image(page.rect, pixmap=image)
            scan.save(source)
        output = self.root / "Bản scan.md"
        original = hashlib.sha256(source.read_bytes()).digest()
        convert_pdf_ocr(source, output)
        self.assertEqual(verify(output, require_pages=True, min_words=20)["status"], "ok")
        self.assertIn("WINDOWS", output.read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), original)


if __name__ == "__main__":
    unittest.main()
