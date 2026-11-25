---
name: doc2md
description: Convert local DOCX, XLSX, digital PDF and scanned PDF files to Markdown and verify the result using the bundled offline tools.
---

# Doc2MD

Use `tools/fast_doc2md.py` relative to this skill directory. Read `README.md` for dependencies, backend selection and limitations.

1. Resolve the requested input and output paths. Preserve source documents.
2. Run `python3 <skill-dir>/tools/fast_doc2md.py <input> -o <output-dir>`.
3. Use default `--pdf-mode auto` unless the PDF type is known. Default `--pdf-layout fast` favors speed; use `auto` for digital tables/forms or `tables` for explicit table inspection. Layout selection does not reconstruct tables from scan images.
4. Add `--overwrite` only when the user explicitly requests replacing an existing output.
5. Verify using `python3 <skill-dir>/tools/verify_doc2md.py <result.md>`. Add `--require-table` when tables were requested. Add `--require-pages` for PDF output; all three PDF backends now insert page markers.
6. Inspect beginning/end and any requested tables. Report OCR warnings or gaps accurately. Verification is not proof of complete extraction.
7. The CLI accepts DOCX, XLSX and PDF only. For legacy DOC/XLS, use WPS Office to save a converted copy first, preserving the original.
8. Copy into a vault, library or external service only when requested. Never include source documents, credentials or conversion output in a code publication.

On Windows, follow `docs/windows.md` and prefer the `.cmd` wrappers; use `setup-windows.cmd --ocr` plus Tesseract for scan OCR.
