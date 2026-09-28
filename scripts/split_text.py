#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
سكربت تقسيم النصوص الطويلة لمهارة التلخيص.
يقسم الملف إلى أجزاء ضمن السعة الفعالة مع الحفاظ على الحدود الطبيعية للفقرات والجمل.
"""

import argparse
import hashlib
import json
import logging
import re
import sys
from pathlib import Path

from utils import get_workspace_root, read_file_with_fallback_encoding

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

MAX_WORDS = 1000
MIN_WORDS_FOR_NEW_PART = 500

PROMPT_TEMPLATE = """\
[تعليمات التلخيص - الجزء {current} من {total}]
لخّص هذا الجزء وفق مهارة التلخيص المثبتة في تعليمات النظام.
{continuation_note}
---
"""

FIRST_PART_NOTE = "هذا هو الجزء الأول؛ ابدأ بالبسملة والعنوان الرئيسي."
CONTINUATION_NOTE = (
    "هذا استكمال للتلخيص السابق؛ تابع من حيث انتهيت دون تكرار البسملة أو العنوان."
)
LAST_PART_NOTE = "هذا هو الجزء الأخير؛ اختم التلخيص بالخلاصة إن وُجدت."


def count_words(text: str) -> int:
    """عدّ كلمات النص."""
    return len(text.split())


def _split_segment_by_words(seg: str, max_words: int) -> list[str]:
    """تجزئة المقطع الواحد إذا تجاوز حد الكلمات كخيار أخير."""
    seg_start = word_count = 0
    segments = []
    for match in re.finditer(r"\s+", seg):
        word_count += 1
        if word_count >= max_words:
            seg_end = match.end()
            segments.append(seg[seg_start:seg_end])
            seg_start, word_count = seg_end, 0
    if seg_start < len(seg):
        segments.append(seg[seg_start:])
    return segments


def split_long_line(line: str, max_words: int) -> list[str]:
    """تجزئة السطور الطويلة جداً مع الحفاظ الكامل على نصوص ومسافات الأصل."""
    sub_segments, start = [], 0
    for match in re.finditer(r"(?<=[.؟!?])\s+", line):
        end = match.end()
        sub_segments.append(line[start:end])
        start = end
    if start < len(line):
        sub_segments.append(line[start:])

    final_segments = []
    for seg in sub_segments:
        if count_words(seg) > max_words:
            final_segments.extend(_split_segment_by_words(seg, max_words))
        else:
            final_segments.append(seg)
    return final_segments


def source_fingerprint(input_file: Path) -> dict:
    """إنشاء بصمة ثابتة للملف الأصلي لمطابقة التغييرات بدقة."""
    stat = input_file.stat()
    digest = hashlib.sha256()
    with open(input_file, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "sha256": digest.hexdigest(),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _prepare_scan_lines(text: str, max_words: int) -> list[str]:
    """تجهيز سطور النص وتفكيك السطور الضخمة استباقياً."""
    lines = []
    for line in text.splitlines(keepends=True):
        if count_words(line) > max_words:
            lines.extend(split_long_line(line, max_words))
        else:
            lines.append(line)
    return lines


def _detect_line_candidate(
    idx: int, lines: list[str], line: str, words: int, split_idx: int
) -> tuple[str, int, int]:
    """كشف نوع وجودة نقطة القطع للسطر الحالي."""
    next_line = lines[idx + 1] if idx < len(lines) - 1 else ""
    if next_line.startswith(("#", "\t")):
        return ("heading", split_idx, words)
    if not line.strip() or not next_line.strip():
        return ("paragraph", split_idx, words)
    clean = line.strip().rstrip(")\"'»]}`”’")
    if (
        clean
        and clean[-1] in (".", "؟", "!", "?")
        and not next_line.strip().startswith("|")
    ):
        return ("sentence", split_idx, words)
    if not next_line.strip().startswith("|"):
        return ("line", split_idx, words)
    return ("none", split_idx, words)


def _pick_best_split(
    candidates: dict[str, tuple[int, int]], min_words: int, default_split: int
) -> int:
    """اختيار نقطة القطع الأعلى رتبة الملتزمة بالحد الأدنى للكلمات أولاً."""
    for kind in ("heading", "paragraph", "sentence"):
        if kind in candidates and candidates[kind][1] >= min_words:
            return candidates[kind][0]
    for kind in ("heading", "paragraph", "sentence", "line"):
        if kind in candidates:
            return candidates[kind][0]
    return default_split


def _collect_candidates(
    lines: list[str], max_words: int
) -> tuple[dict[str, tuple[int, int]], int]:
    """جمع نقاط القطع المرشحة من السطور وحساب الكلمات."""
    current_words = split_idx = 0
    inside_code = False
    candidates: dict[str, tuple[int, int]] = {}
    for idx, line in enumerate(lines):
        if current_words + count_words(line) > max_words:
            break
        inside_code = (
            not inside_code if re.match(r"^\s*(```|~~~)", line) else inside_code
        )
        current_words += count_words(line)
        split_idx += len(line)
        if not inside_code and not line.strip().startswith("|"):
            kind, s_idx, w = _detect_line_candidate(
                idx, lines, line, current_words, split_idx
            )
            if kind != "none":
                candidates[kind] = (s_idx, w)
    return candidates, split_idx if current_words > 0 else 0


def find_split_point(
    text: str, max_words: int, min_words: int = MIN_WORDS_FOR_NEW_PART
) -> int:
    """إيجاد أفضل نقطة قطع طبيعية ضمن السعة المحددة."""
    if count_words(text) <= max_words:
        return len(text)
    lines = _prepare_scan_lines(text, max_words)
    candidates, fallback_idx = _collect_candidates(lines, max_words)
    return _pick_best_split(candidates, min_words, fallback_idx or len(text))


def _is_parts_cache_valid(
    output_dir: Path, total_words: int, max_words: int, min_words: int, fp: dict
) -> bool:
    """فحص ما إذا كانت الأجزاء المولدة سابقاً سليمة ومطابقة للملف الأصلي."""
    meta_path = output_dir / "metadata.json"
    if not meta_path.exists():
        return False
    try:
        m = json.loads(meta_path.read_text(encoding="utf-8"))
        fp_match = m.get("source_fingerprint", {}).get("sha256") == fp["sha256"]
        params_match = (
            m.get("total_words") == total_words
            and m.get("max_words_per_part") == max_words
            and m.get("min_words_for_new_part") == min_words
        )
        files_exist = all((output_dir / p["file"]).exists() for p in m.get("parts", []))
        return fp_match and params_match and files_exist
    except (OSError, json.JSONDecodeError, KeyError):
        return False


def _generate_text_partitions(
    content: str, max_words: int, min_words: int
) -> list[str]:
    """تقطيع النص إلى شرائح متتابعة متوافقة مع حدود الكلمات."""
    if count_words(content) <= max_words:
        return [content]
    parts, remaining = [], content
    while count_words(remaining) > max_words:
        split_idx = find_split_point(remaining, max_words, min_words)
        parts.append(remaining[:split_idx])
        remaining = remaining[split_idx:]
    if remaining:
        if parts and count_words(remaining) < min_words:
            parts[-1] += remaining
        else:
            parts.append(remaining)
    return parts


def _write_parts_files(stem: str, output_dir: Path, parts: list[str]) -> list[dict]:
    """كتابة ملفات الأجزاء مع تضمين ترويسة التوجيه المناسبة لكل جزء."""
    output_dir.mkdir(parents=True, exist_ok=True)
    meta_parts = []
    total = len(parts)
    for i, part in enumerate(parts):
        curr = i + 1
        note = (
            FIRST_PART_NOTE
            if curr == 1
            else (LAST_PART_NOTE if curr == total else CONTINUATION_NOTE)
        )
        hdr = PROMPT_TEMPLATE.format(current=curr, total=total, continuation_note=note)
        fname = f"{stem}_part_{curr:02d}.md"
        (output_dir / fname).write_text(hdr + part, encoding="utf-8")
        meta_parts.append({"file": fname, "words": count_words(part)})
    return meta_parts


def _build_metadata_dict(
    input_file: Path, words: int, parts: list[dict], max_w: int, min_w: int, fp: dict
) -> dict:
    """بناء قاموس البيانات الوصفية للأجزاء المقسمة."""
    root = get_workspace_root()
    src = (
        str(input_file.relative_to(root))
        if input_file.is_relative_to(root)
        else str(input_file)
    )
    return {
        "source": src,
        "total_words": words,
        "source_fingerprint": fp,
        "parts_count": len(parts),
        "max_words_per_part": max_w,
        "min_words_for_new_part": min_w,
        "parts": parts,
    }


def _write_metadata(
    input_file: Path,
    out_dir: Path,
    words: int,
    parts: list[dict],
    max_w: int,
    min_w: int,
    fp: dict,
):
    """حفظ البيانات الوصفية للأجزاء في ملف metadata.json."""
    meta = _build_metadata_dict(input_file, words, parts, max_w, min_w, fp)
    try:
        with open(out_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except OSError as err:
        logger.error("تعذر حفظ metadata.json: %s", err)


def _execute_split_and_save(
    input_file: Path, out_dir: Path, content: str, max_w: int, min_w: int, fp: dict
):
    """تنفيذ عملية التجزئة وكتابة ملفات الأجزاء وبيانات الميتادات."""
    parts = _generate_text_partitions(content, max_w, min_w)
    logger.info("تقسيم النص إلى %d جزءاً للملف %s.", len(parts), input_file.name)
    meta_parts = _write_parts_files(input_file.stem, out_dir, parts)
    _write_metadata(
        input_file, out_dir, count_words(content), meta_parts, max_w, min_w, fp
    )


def split_text(
    input_file: Path,
    output_dir: Path,
    max_words: int = MAX_WORDS,
    force: bool = False,
    min_words: int = MIN_WORDS_FOR_NEW_PART,
):
    """المنسق العام لتقسيم النص وحفظ أجزائه وملف ميتاداته."""
    content = read_file_with_fallback_encoding(input_file)
    total_words, fp = count_words(content), source_fingerprint(input_file)
    if not force and _is_parts_cache_valid(
        output_dir, total_words, max_words, min_words, fp
    ):
        logger.info(
            "أجزاء الملف «%s» منشأة مسبقاً، تقرر تجاوز إعادة التقسيم.", input_file.name
        )
        return
    _execute_split_and_save(input_file, output_dir, content, max_words, min_words, fp)


def _build_cli_parser() -> argparse.ArgumentParser:
    """بناء قارئ وسائط سطر الأوامر."""
    p = argparse.ArgumentParser(description="تقسيم النصوص الطويلة لمهارة التلخيص.")
    p.add_argument("input", help="مسار الملف النصي أو مجلد المعالجة")
    p.add_argument("-o", "--output", help="مجلد مخرجات الأجزاء المقسمة (اختياري)")
    p.add_argument(
        "--max-words", type=int, default=MAX_WORDS, help="الحد الأقصى للكلمات بالجزء"
    )
    p.add_argument(
        "--min-words",
        type=int,
        default=MIN_WORDS_FOR_NEW_PART,
        help="الحد الأدنى لفتح جزء",
    )
    p.add_argument("-f", "--force", action="store_true", help="فرض إعادة التقسيم")
    return p


def _batch_split_directory(input_dir: Path, max_w: int, min_w: int, force: bool):
    """معالجة المجلدات النصية دفعياً مع الاستئناف الذكي."""
    files = sorted(
        f for f in input_dir.rglob("*") if f.is_file() and f.suffix in (".txt", ".md")
    )
    if not files:
        logger.warning("لا توجد ملفات نصية في المجلد.")
        return
    for f in files:
        rel = f.relative_to(input_dir)
        dest = get_workspace_root() / "all_parts" / rel.parent / f"{f.stem}_parts"
        split_text(f, dest, max_w, force=force, min_words=min_w)


def main():
    """نقطة الدخول الرئيسية لسطر الأوامر."""
    args = _build_cli_parser().parse_args()
    inp = Path(args.input)
    if not inp.exists():
        logger.error("المسار غير موجود: %s", args.input)
        sys.exit(1)
    if inp.is_dir():
        _batch_split_directory(inp, args.max_words, args.min_words, args.force)
    else:
        out = (
            Path(args.output)
            if args.output
            else get_workspace_root() / "all_parts" / f"{inp.stem}_parts"
        )
        split_text(inp, out, args.max_words, force=args.force, min_words=args.min_words)


if __name__ == "__main__":
    main()
