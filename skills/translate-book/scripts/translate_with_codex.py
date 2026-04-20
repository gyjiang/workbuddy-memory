#!/usr/bin/env python3
"""
Translate markdown chunks with `codex exec`, one chunk per subprocess.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


LANG_NAMES = {
    "zh": "简体中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
    "fr": "français",
    "de": "Deutsch",
    "es": "español",
}


def natural_sort_key(path: Path):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def discover_source_files(temp_dir: Path) -> list[Path]:
    chunk_files = [p for p in temp_dir.glob("chunk*.md") if not p.name.startswith("output_")]
    page_files = [p for p in temp_dir.glob("page*.md") if not p.name.startswith("output_")]
    return sorted({*chunk_files, *page_files}, key=natural_sort_key)


def build_prompt(content: str, target_lang_name: str) -> str:
    return f"""请把下面的 Markdown 内容翻译为{target_lang_name}。

要求：
1. 严格保留 Markdown 结构，包括标题、列表、引用、链接、图片、表格、代码块和公式。
2. 只翻译自然语言文本；不要修改链接地址、图片路径、HTML 标签、文件名、代码和公式语法。
3. 删除明显的页码、只有数字的独立行、孤立的空链接和无意义的反斜杠。
4. 如果原文已有 Markdown 标题，保留其层级；如果原文没有标记但明显是标题，可补充恰当的 Markdown 标题层级。
5. 术语翻译保持一致，语言自然、简洁，不要扩写。
6. 保留所有图片引用结构，alt 文本可以翻译，但路径和文件名不能改。
7. 只输出翻译后的 Markdown 正文，不要解释、不要代码围栏、不要任何额外前后缀。

待翻译内容如下：

{content}
"""


def run_codex(prompt: str, output_path: Path, model: str | None, timeout: int) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f"{output_path.stem}.", suffix=".tmp", dir=output_path.parent)
    os.close(fd)
    temp_path = Path(temp_name)

    cmd = [
        "codex",
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "-o",
        str(temp_path),
    ]
    if model:
        cmd.extend(["--model", model])

    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()
            detail = "\n".join(part for part in [stdout, stderr] if part)
            raise RuntimeError(detail or f"`{' '.join(cmd)}` exited with {proc.returncode}")

        translated = temp_path.read_text(encoding="utf-8")
        if not translated.strip():
            raise RuntimeError("codex returned empty output")

        temp_path.replace(output_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def translate_one(
    source_path: Path,
    output_path: Path,
    target_lang_name: str,
    model: str | None,
    timeout: int,
    retries: int,
) -> tuple[str, int]:
    content = source_path.read_text(encoding="utf-8")
    prompt = build_prompt(content, target_lang_name)
    last_error: Exception | None = None

    for attempt in range(1, retries + 2):
        try:
            run_codex(prompt, output_path, model=model, timeout=timeout)
            return source_path.name, output_path.stat().st_size
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt > retries:
                break

    raise RuntimeError(f"{source_path.name}: {last_error}") from last_error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate markdown chunks with Codex CLI")
    parser.add_argument("--temp-dir", required=True, help="Temp directory containing chunk files")
    parser.add_argument("--lang", default="zh", help="Target language code")
    parser.add_argument("--concurrency", type=int, default=4, help="Parallel Codex workers")
    parser.add_argument("--retries", type=int, default=1, help="Retries per chunk after the first attempt")
    parser.add_argument("--timeout", type=int, default=900, help="Per-chunk timeout in seconds")
    parser.add_argument("--model", default=None, help="Optional Codex model override")
    parser.add_argument("--overwrite", action="store_true", help="Recreate existing output_chunk files")
    parser.add_argument("--limit", type=int, default=None, help="Translate only the first N pending chunks")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    temp_dir = Path(args.temp_dir).resolve()
    target_lang_name = LANG_NAMES.get(args.lang, args.lang)

    if not temp_dir.is_dir():
        print(f"Temp directory not found: {temp_dir}", file=sys.stderr, flush=True)
        return 1

    source_files = discover_source_files(temp_dir)
    if not source_files:
        print(f"No chunk files found in {temp_dir}", file=sys.stderr, flush=True)
        return 1

    pending: list[tuple[Path, Path]] = []
    for source_path in source_files:
        output_path = source_path.with_name(f"output_{source_path.name}")
        if args.overwrite or not output_path.exists():
            pending.append((source_path, output_path))

    if args.limit is not None:
        pending = pending[: args.limit]

    print(f"Discovered {len(source_files)} source files", flush=True)
    print(f"Pending translation: {len(pending)} file(s)", flush=True)

    if not pending:
        return 0

    failures: list[str] = []
    completed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        future_map = {
            executor.submit(
                translate_one,
                source_path,
                output_path,
                target_lang_name,
                args.model,
                args.timeout,
                args.retries,
            ): source_path.name
            for source_path, output_path in pending
        }

        for future in concurrent.futures.as_completed(future_map):
            name = future_map[future]
            completed += 1
            try:
                _, size = future.result()
                print(f"[{completed}/{len(pending)}] OK   {name} -> {size} bytes", flush=True)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{name}: {exc}")
                print(f"[{completed}/{len(pending)}] FAIL {name}: {exc}", file=sys.stderr, flush=True)

    if failures:
        print("\nFailures:", file=sys.stderr, flush=True)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr, flush=True)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
