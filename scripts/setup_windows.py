"""Create a project-local environment; no administrator rights or activation needed."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import venv

ROOT = Path(__file__).resolve().parents[1]
TESSDATA_COMMIT = "87416418657359cb625c412a48b6e1d6d41c29bd"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr", action="store_true", help="Install OCRmyPDF and eng/vie/osd language data (needs internet)")
    args = parser.parse_args()
    if sys.version_info < (3, 10) or (args.ocr and sys.version_info < (3, 11)):
        print("Please install Python 3.12 and run setup-windows.cmd again.", file=sys.stderr)
        return 2
    tessdata = None
    if args.ocr and os.name == "nt":
        located = shutil.which("tesseract")
        candidates = ([Path(located)] if located else []) + [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR/tesseract.exe"
        ]
        for candidate in candidates:
            possible = candidate.parent / "tessdata"
            if candidate.is_file() and (possible / "configs/hocr").is_file():
                tessdata = possible
                break
        if tessdata is None:
            print("Install Tesseract (including tessdata/configs) first, then rerun setup-windows.cmd --ocr. See docs/windows.md.", file=sys.stderr)
            return 2
    environment = ROOT / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    try:
        if not python.is_file():
            venv.EnvBuilder(with_pip=True).create(environment)
        # Existing environments may have been made with an older Python.
        check = "import sys;sys.exit(0 if sys.version_info >= " + ("(3,11)" if args.ocr else "(3,10)") + " else 2)"
        if subprocess.run([str(python), "-c", check], check=False).returncode:
            print("Existing .venv uses an older Python. Rename it, then rerun setup with Python 3.12.", file=sys.stderr)
            return 2
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)
        if args.ocr:
            subprocess.run([str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements-ocr.txt")], check=True)
            data = environment / "share" / "tessdata"
            data.mkdir(parents=True, exist_ok=True)
            # TESSDATA_PREFIX redirects config lookup too, not just models.
            # Retain the installed engine's hocr/pdf/txt configuration files.
            if tessdata:
                for folder in ("configs", "tessconfigs"):
                    if (tessdata / folder).is_dir():
                        shutil.copytree(tessdata / folder, data / folder, dirs_exist_ok=True)
            for language in ("eng", "vie", "osd"):
                target = data / f"{language}.traineddata"
                temporary = target.with_suffix(".part")
                try:
                    url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{TESSDATA_COMMIT}/{language}.traineddata"
                    with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as output:
                        shutil.copyfileobj(response, output)
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
            print("OCR packages and language data installed. Tesseract must also be installed: see docs/windows.md.")
        print('Ready: doc2md.cmd "C:\\path\\document.pdf" -o output')
        return 0
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
