#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
السكربت الموحد لتجهيز ودمج أجزاء التلخيصات المقسمة (Merge Mode).
يقوم بـ:
1. ترتيب ودمج أجزاء الملفات المقسمة حسابياً.
2. تطهير تعليمات التلخيص والبسملة والعناوين المكررة.
3. التدقيق في التنسيق والهيكل العام واكتشاف العيوب التنسيقية.
4. التنظيف الآمن لمجلد الأجزاء المؤقت بعد تمام الدمج.
"""

import argparse
import logging
import re
import shutil
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

BISMILLAH = "بسم الله الرحمن الرحيم."
PROMPT_PATTERN = re.compile(
    r"\A\[تعليمات التلخيص[^\]]*\].*?^---[ \t]*\n?", re.DOTALL | re.MULTILINE
)


def strip_prompt(text: str) -> str:
    """حذف تعليمات التلخيص من بداية النص."""
    return PROMPT_PATTERN.sub("", text, count=1)


def trim_outer_blank_lines(text: str) -> str:
    """حذف الأسطر الفارغة الخارجية مع الحفاظ على الإزاحات الداخلية."""
    lines = text.splitlines()
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end])


def _collect_numbered_files(
    input_dir: Path, pattern: re.Pattern
) -> list[tuple[int, Path]]:
    """استكشاف وفرز الملفات المرقمة بنمط regex محدد."""
    result = []
    for f in input_dir.iterdir():
        if f.is_file():
            match = pattern.search(f.name)
            if match:
                result.append((int(match.group(1)), f))
    result.sort(key=lambda x: x[0])
    return result


def _validate_part_sequence(pairs: list[tuple[int, Path]], label: str) -> list[Path]:
    """ترتيب ملفات الأجزاء حسابياً مع تسجيل تنبيه عند وجود فجوات."""
    numbers = [x[0] for x in pairs]
    expected = list(range(numbers[0], numbers[0] + len(pairs))) if numbers else []
    if numbers != expected:
        logger.warning("تنبيه: توجد فجوة أو عدم اتساق في أرقام %s: %s", label, numbers)
    return [p[1] for p in pairs]


def find_summary_files(input_dir: Path) -> list[Path]:
    """إيجاد ملفات أجزاء التلخيص وترتيبها حسابياً."""
    s_pattern = re.compile(
        r"(?:_part_|_جزء_|part_|جزء|^)(\d+)_summary\.md$", re.IGNORECASE
    )
    summaries = _collect_numbered_files(input_dir, s_pattern)
    if summaries:
        return _validate_part_sequence(summaries, "ملفات الملخصات")
    return []


def _extract_main_title(non_empty_lines: list[str]) -> str | None:
    """استخلاص العنوان الرئيسي من أول سطر غير مفرغ بعد البسملة."""
    if not non_empty_lines:
        return None
    first = non_empty_lines[0]
    line = (
        non_empty_lines[1] if first == BISMILLAH and len(non_empty_lines) > 1 else first
    )
    return line.strip() if line != BISMILLAH else None


def _clean_subsequent_lines(lines: list[str], title: str | None) -> list[str]:
    """تطهير البسملة والعنوان المكررين من الأجزاء اللاحقة."""
    idx = 0
    raw_t = title.lstrip("#").strip().rstrip(":") if title else None
    while idx < len(lines):
        s = lines[idx].strip()
        raw_s = s.lstrip("#").strip().rstrip(":")
        if not s or s == BISMILLAH or (raw_t and raw_s == raw_t):
            idx += 1
        else:
            break
    return lines[idx:]


def clean_part_content(
    text: str, is_first: bool, main_title: str | None = None
) -> tuple[str, str | None]:
    """تنظيف أجزاء الملخصات وإزالة البسملة والعناوين المكررة."""
    text = trim_outer_blank_lines(strip_prompt(text))
    if not text:
        return "", main_title
    lines = text.splitlines()
    non_empty = [line.strip() for line in lines if line.strip()]
    if is_first:
        extracted = _extract_main_title(non_empty) or main_title
        if extracted:
            logger.info("تم استخلاص العنوان الرئيسي للتلخيص: '%s'", extracted)
        return text, extracted
    cleaned = _clean_subsequent_lines(lines, main_title)
    return trim_outer_blank_lines("\n".join(cleaned)), main_title


def merge_files(files: list[Path]) -> str:
    """دمج ملفات الأجزاء في نص متصل واحد بعد تنظيف البرومبتات والعناوين المكررة."""
    parts = []
    main_title = None
    for i, f in enumerate(files):
        logger.info("  قراءة الجزء %d: %s", i + 1, f.name)
        text = read_file_with_fallback_encoding(f)
        text, main_title = clean_part_content(text, i == 0, main_title)
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _audit_headers(lines: list[str]) -> tuple[list[str], int | None, str | None]:
    """تدقيق استهلال الملف بالبسملة والعنوان الرئيسي دون تقييد متنه."""
    issues = []
    non_empty = [(i + 1, line.strip()) for i, line in enumerate(lines) if line.strip()]
    if not non_empty:
        return ["الملف فارغ تماماً."], None, None
    if non_empty[0][1] != BISMILLAH:
        issues.append("يجب أن يستفتح الملف بالبسملة: 'بسم الله الرحمن الرحيم.'")
    title_line_no, title_text = None, None
    if non_empty[0][1] == BISMILLAH and len(non_empty) > 1:
        title_line_no, title_text = non_empty[1]
    elif non_empty[0][1] != BISMILLAH:
        title_line_no, title_text = non_empty[0]
    if title_line_no is None:
        issues.append("تعذر تحديد عنوان رئيسي بعد البسملة.")
    return issues, title_line_no, title_text


def _strip_brackets_and_quotes(line: str) -> str:
    """تجريد كافة أنواع الأقواس والتنصيصات لصيانة نصوص الاستشهاد."""
    patterns = (
        r"\{[^}]*\}",
        r"«[^»]*»",
        r"[﴿﴾][^﴿﴾]*[﴿﴾]",
        r"\([^)]*\)",
        r"\[[^\]]*\]",
        r"\"[^\"]*\"",
        r"\'[^\']*\'",
    )
    res = line
    for pat in patterns:
        res = re.sub(pat, "", res)
    return res


def _has_unsplit_sentence(line: str) -> bool:
    """التحقق من وجود استمرار غير مبرر لجملة بعد نقطة خارج الاختصارات."""
    stripped = _strip_brackets_and_quotes(line)
    stripped = re.sub(r"\b(?:ص|ج|د|الخ|هـ|م|ط|ت|ق|تحـ|رقم)\.\s+", "", stripped)
    stripped = re.sub(r"\.{2,}", "", stripped)
    stripped = re.sub(r"\b[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b", "", stripped)
    return bool(re.search(r"[^\d\s\.]\.\s+\S", stripped))


def _has_forbidden_ellipsis(line: str) -> bool:
    """التحقق من وجود نقط متتالية خارج الشواهد والاقتباسات."""
    stripped = _strip_brackets_and_quotes(line)
    return "..." in stripped or bool(re.search(r"\.{2,}", stripped))


def _audit_line(no: int, line: str, title_no: int | None, issues: list[str]):
    """فحص سلامة السطر المنفرد من العيوب التنسيقية الهيكلية."""
    s = line.strip()
    if not s or s == BISMILLAH or no == title_no:
        return
    if _has_unsplit_sentence(line):
        issues.append(f"يوجد استمرار بعد نقطة في السطر {no}.")
    if _has_forbidden_ellipsis(line):
        issues.append(f"توجد علامات حذف متتالية (...) في السطر {no}.")


def audit_summary_text(text: str) -> list[str]:
    """فحص تنسيق الملخص النهائي وفق القواعد المعتمدة."""
    lines = text.splitlines()
    issues, title_no, _ = _audit_headers(lines)
    if PROMPT_PATTERN.search(text) or "[تعليمات التلخيص" in text:
        issues.append("توجد بقايا من تعليمات التلخيص داخل الملف النهائي.")
    for no, line in enumerate(lines, start=1):
        _audit_line(no, line, title_no, issues)
    return issues


def audit_and_log(text: str, strict_audit: bool):
    """تسجيل ملاحظات فحص التنسيق وإثارة خطأ عند التدقيق الصارم."""
    issues = audit_summary_text(text)
    if not issues:
        logger.info("اجتاز الملف النهائي فحص التنسيق.")
        return
    for issue in issues:
        logger.warning("فحص التنسيق: %s", issue)
    if strict_audit:
        raise ValueError("فشل فحص التنسيق الصارم للملف النهائي.")


def _cleanup_parts_dir(input_path: Path, clean: bool):
    """حذف مجلد الأجزاء إذا كان التنظيف مفعلاً ومساره مجلد أجزاء مؤقت."""
    if not clean:
        return
    if input_path.is_dir() and input_path.name.endswith("_parts"):
        try:
            shutil.rmtree(input_path)
            logger.info("تم تنظيف وحذف مجلد الأجزاء المؤقت: %s", input_path.name)
        except OSError as e:
            logger.warning("فشل حذف مجلد الأجزاء %s: %s", input_path.name, e)


def _save_and_audit(out_file: Path, text: str, strict: bool):
    """حفظ التلخيص المدمج والتدقيق التنسيقي الصارم."""
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(text, encoding="utf-8")
    logger.info("تم حفظ الملف المدمج في: %s", out_file.name)
    audit_and_log(text, strict)


def _resolve_single_dest(input_path: Path, output_path_str: str | None) -> Path:
    """تحديد مسار حفظ الملخص المدمج لمجلد مفرد."""
    if output_path_str:
        return Path(output_path_str)
    stem = input_path.name.replace("_parts", "")
    return get_workspace_root() / "summaries" / f"{stem}_summary.md"


def process_single_dir(
    input_path: Path,
    output_path_str: str | None = None,
    clean: bool = False,
    strict_audit: bool = False,
):
    """دمج أجزاء مجلد واحد وحفظ التلخيص المدمج النهائي."""
    files = find_summary_files(input_path)
    if not files:
        logger.warning("لم يتم العثور على أجزاء للدمج في %s", input_path.name)
        return
    text = merge_files(files)
    if text:
        dest = _resolve_single_dest(input_path, output_path_str)
        _save_and_audit(dest, text, strict_audit)
        _cleanup_parts_dir(input_path, clean)


def _merge_batch_item(
    idx: int,
    total: int,
    mf: Path,
    inp: Path,
    out_str: str | None,
    clean: bool,
    strict: bool,
):
    """دمج مجلد أجزاء مفرد ضمن الدفعة وتحديد مسار مخرجه."""
    p_dir = mf.parent
    rel_parent = p_dir.relative_to(inp).parent
    stem = p_dir.name.replace("_parts", "")
    base = Path(out_str) if out_str else get_workspace_root() / "summaries"
    dest = base / rel_parent / f"{stem}_summary.md"
    logger.info("[%d/%d] دمج أجزاء: %s -> %s", idx + 1, total, p_dir.name, dest.name)
    process_single_dir(p_dir, str(dest), clean, strict)


def process_batch_merge(
    input_path: Path,
    output_path_str: str | None = None,
    clean: bool = False,
    strict_audit: bool = False,
):
    """البحث عن مجلدات الأجزاء ودمجها دفعياً."""
    meta_files = sorted(input_path.glob("**/metadata.json"))
    if not meta_files:
        logger.error("لم يتم العثور على ملفات ميتادات (metadata.json) داخل المجلد.")
        sys.exit(1)
    for idx, mf in enumerate(meta_files):
        _merge_batch_item(
            idx, len(meta_files), mf, input_path, output_path_str, clean, strict_audit
        )


def _build_cli_parser() -> argparse.ArgumentParser:
    """بناء قارئ وسائط سطر الأوامر لدمج التلخيصات."""
    p = argparse.ArgumentParser(
        description="السكربت الموحد لدمج أجزاء التلخيصات وتطهيرها."
    )
    p.add_argument(
        "input_dir",
        nargs="?",
        default=str(get_workspace_root() / "all_parts"),
        help="مجلد الأجزاء الملخصة (الافتراضي: all_parts)",
    )
    p.add_argument(
        "-o", "--output", help="مسار ملف المخرج النهائي المدمج أو مجلد المخرجات"
    )
    p.add_argument(
        "-c",
        "--clean",
        action="store_true",
        help="حذف مجلد الأجزاء المؤقت بعد نجاح الدمج",
    )
    p.add_argument(
        "--strict-audit",
        action="store_true",
        help="إنهاء التشغيل بخطأ عند وجود ملاحظات حرجة",
    )
    return p


def main():
    """نقطة الدخول الرئيسية لسطر الأوامر."""
    args = _build_cli_parser().parse_args()
    inp = Path(args.input_dir)
    if not inp.exists():
        logger.error("مسار المدخلات غير موجود: %s", args.input_dir)
        sys.exit(1)
    if (inp / "metadata.json").exists() or inp.name.endswith("_parts"):
        process_single_dir(inp, args.output, args.clean, args.strict_audit)
    else:
        process_batch_merge(inp, args.output, args.clean, args.strict_audit)


if __name__ == "__main__":
    main()
