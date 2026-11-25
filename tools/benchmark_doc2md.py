#!/usr/bin/env python3
"""Benchmark the existing doc2md script against tools/fast_doc2md.py."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import subprocess
import tempfile
import time
from pathlib import Path


def count_output(path: Path) -> tuple[int, int, str]:
    if not path.exists():
        return 0, 0, ""
    content = path.read_bytes()
    text = content.decode("utf-8", errors="replace")
    return len(content), len(text.split()), hashlib.sha256(content).hexdigest()[:12]


def benchmark(command: list[str], output_path: Path, repeats: int) -> dict[str, object]:
    timings: list[float] = []
    last_result: subprocess.CompletedProcess[str] | None = None
    for _ in range(repeats):
        output_path.unlink(missing_ok=True)
        started = time.perf_counter()
        last_result = subprocess.run(command, capture_output=True, text=True, check=False)
        timings.append(time.perf_counter() - started)
        if last_result.returncode != 0:
            break
    size, words, digest = count_output(output_path)
    assert last_result is not None
    return {
        "status": "ok" if last_result.returncode == 0 and size else "failed",
        "median_seconds": round(statistics.median(timings), 4),
        "runs": len(timings),
        "bytes": size,
        "words": words,
        "sha256_12": digest,
        "stderr_tail": last_result.stderr.strip()[-300:],
        "stdout_tail": last_result.stdout.strip()[-300:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc2md", type=Path, required=True)
    parser.add_argument("--fast", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--kind", choices=("docx", "xlsx", "pdf-digital", "pdf-auto"), required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--fast-pdf-layout", choices=("fast", "auto", "tables"), default="fast"
    )
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    temp_root = Path(tempfile.mkdtemp(prefix="doc2md-bench-"))
    try:
        old_dir = temp_root / "old"
        fast_dir = temp_root / "fast"
        old_dir.mkdir()
        fast_dir.mkdir()
        old_output = old_dir / f"{args.input.stem}.md"
        fast_output = fast_dir / f"{args.input.stem}.md"

        old_command = ["python3", str(args.doc2md), str(args.input), "-o", str(old_dir), "--overwrite"]
        fast_command = [
            "python3",
            str(args.fast),
            str(args.input),
            "-o",
            str(fast_dir),
            "--overwrite",
        ]
        if args.kind == "pdf-digital":
            old_command.append("--force-digital")
            fast_command.extend(
                ["--pdf-mode", "digital", "--pdf-layout", args.fast_pdf_layout]
            )
        elif args.kind == "pdf-auto":
            fast_command.extend(["--pdf-layout", args.fast_pdf_layout])

        results = {
            "input": str(args.input),
            "kind": args.kind,
            "repeats_requested": args.repeats,
            "doc2md": benchmark(old_command, old_output, args.repeats),
            "fast_doc2md": benchmark(fast_command, fast_output, args.repeats),
        }
        old_time = results["doc2md"]["median_seconds"]
        fast_time = results["fast_doc2md"]["median_seconds"]
        results["speedup"] = round(old_time / fast_time, 2) if fast_time else None
        rendered = json.dumps(results, ensure_ascii=False, indent=2)
        print(rendered)
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(rendered + "\n", encoding="utf-8")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
