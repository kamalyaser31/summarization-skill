#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
السكربت الموحد لتجهيز التلخيصات وتجميع فصول الكتب.
يجمع السكربت بين:
1. دمج أجزاء الملفات المقسمة (Merge Mode) مع تنظيف البرومبتات والبسملة المكررة.
2. تجميع فصول الملخصات المفرقة (Compile Mode) في كتاب واحد بالترتيب الحسابي وتنقية التكرارات.
"""

import argparse
import json
import logging
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from utils import read_file_with_fallback_encoding, get_workspace_root

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# إعداد السجل تماشياً مع المعايير القياسية للمشروع
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

# الثوابت القياسية
BISMILLAH = "بسم الله الرحمن الرحيم."
# مقيَّد بـ \A لضمان المطابقة من بداية النص فحسب؛ و MULTILINE لمطابقة سطر --- المستقل بدقة
PROMPT_PATTERN = re.compile(
    r'\A\[تعليمات التلخيص[^\]]*\].*?^---[ \t]*\n?',
    re.DOTALL | re.MULTILINE
)
CHAPTER_TITLE_PATTERN = re.compile(
    r"\((الفصل\s+[^\)]+|الباب\s+[^\)]+|الجزء\s+[^\)]+|المبحث\s+[^\)]+)\)",
    re.IGNORECASE
)
TIMESTAMP_PATTERN = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")




def strip_prompt(text: str) -> str:
    """حذف تعليمات التلخيص (Prompt) من بداية النص."""
    return PROMPT_PATTERN.sub('', text, count=1)


def trim_outer_blank_lines(text: str) -> str:
    """حذف الأسطر الفارغة الخارجية فقط مع الحفاظ على إزاحة أول سطر حقيقي."""
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def find_summary_files(input_dir: Path, allow_raw_parts: bool = False) -> list[Path]:
    """إيجاد ملفات الأجزاء وتأكيد تسلسلها وخلوها من فجوات الأرقام."""
    summary_pattern = re.compile(r'_part_(\d+)_summary\.md$', re.IGNORECASE)
    part_pattern = re.compile(r'_part_(\d+)\.md$', re.IGNORECASE)

    summary_files = []
    part_files = []

    for f in input_dir.iterdir():
        if f.is_file():
            if summary_pattern.search(f.name):
                match = summary_pattern.search(f.name)
                part_num = int(match.group(1))
                summary_files.append((part_num, f))
            elif part_pattern.search(f.name):
                match = part_pattern.search(f.name)
                part_num = int(match.group(1))
                part_files.append((part_num, f))

    if summary_files:
        summary_files.sort(key=lambda x: x[0])
        part_numbers = [x[0] for x in summary_files]
        expected = list(range(1, len(summary_files) + 1))
        if part_numbers != expected:
            raise ValueError(f"فجوة في أرقام ملفات الملخصات: {part_numbers}")
        return [f for _, f in summary_files]

    if part_files and allow_raw_parts:
        part_files.sort(key=lambda x: x[0])
        part_numbers = [x[0] for x in part_files]
        expected = list(range(1, len(part_files) + 1))
        if part_numbers != expected:
            raise ValueError(f"فجوة في أرقام ملفات الأجزاء الأصلية: {part_numbers}")
        return [f for _, f in part_files]

    if part_files:
        raise ValueError("وجدنا أجزاء أصلية فقط دون ملفات تلخيص. أنشئ ملفات *_summary.md أو استخدم --allow-raw-parts صراحة.")

    return []


def clean_part_content(text: str, is_first: bool, main_title: str = None) -> tuple[str, str]:
    """تنظيف أجزاء الملخصات وإزالة البسملة والعناوين المكررة."""
    text = trim_outer_blank_lines(strip_prompt(text))
    if not text:
        return "", main_title

    lines = text.splitlines()
    non_empty_lines = [line.strip() for line in lines if line.strip()]

    extracted_title = main_title

    if is_first:
        temp_title = None
        if non_empty_lines:
            if non_empty_lines[0] == BISMILLAH:
                if len(non_empty_lines) > 1:
                    temp_title = non_empty_lines[1]
            else:
                temp_title = non_empty_lines[0]
        
        if temp_title and (temp_title.endswith(":") or "شرح" in temp_title or "كتاب" in temp_title):
            extracted_title = temp_title
            logger.info("تم استخلاص العنوان الرئيسي للتلخيص: '%s'", extracted_title)
        return text, extracted_title
    else:
        changed = True
        while changed and lines:
            changed = False
            first_line = lines[0].strip()
            if not first_line:
                lines.pop(0)
                changed = True
                continue
            
            if first_line == BISMILLAH:
                lines.pop(0)
                changed = True
                continue
                
            if extracted_title and (first_line == extracted_title or first_line == extracted_title.strip(":")):
                lines.pop(0)
                changed = True
                continue
                
        return trim_outer_blank_lines("\n".join(lines)), extracted_title


def merge_files(files: list[Path], strip_prompts: bool = True) -> str:
    """دمج ملفات الأجزاء في نص متصل واحد."""
    parts = []
    main_title = None
    for i, f in enumerate(files):
        logger.info("  قراءة الجزء %d: %s", i + 1, f.name)
        text = read_file_with_fallback_encoding(f)

        if strip_prompts:
            is_first = (i == 0)
            text, main_title = clean_part_content(text, is_first, main_title)
        else:
            text = trim_outer_blank_lines(text)

        if text:
            parts.append(text)

    return "\n\n".join(parts)


def audit_summary_text(text: str) -> list[str]:
    """فحص تنسيق الملخص النهائي وفق القواعد العملية لمهارة التلخيص."""
    issues = []
    lines = text.splitlines()
    non_empty = [line for line in lines if line.strip()]

    if text.count(BISMILLAH) != 1:
        issues.append("يجب أن تظهر البسملة مرة واحدة فقط.")

    title_line_no = None
    title_text = None
    for line in non_empty:
        stripped = line.strip()
        if stripped == BISMILLAH:
            continue
        if stripped.endswith(":") and not stripped.startswith(("•", "-", "*")) and not re.match(r"^\d+[-.)]", stripped):
            title_line_no = lines.index(line) + 1
            title_text = stripped
            break
    if title_line_no is None:
        issues.append("تعذر تحديد عنوان رئيسي واحد بعد البسملة.")
    elif sum(1 for line in lines if line.strip() == title_text) != 1:
        issues.append("يجب أن يظهر العنوان الرئيسي مرة واحدة فقط.")

    if PROMPT_PATTERN.search(text) or "[تعليمات التلخيص" in text:
        issues.append("توجد بقايا من تعليمات التلخيص داخل الملف النهائي.")

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped == BISMILLAH:
            continue
        if (
            stripped.endswith(":")
            and line_no != title_line_no
            and not line.startswith("\t")
            and not stripped.startswith(("•", "-", "*"))
            and not re.match(r"^\d+[-.)]", stripped)
        ):
            issues.append(f"عنوان داخلي بلا Tab في السطر {line_no}: {stripped}")

        if re.search(r"\.\s+\S", line):
            issues.append(f"يوجد استمرار بعد نقطة في السطر {line_no}.")

        if TIMESTAMP_PATTERN.search(line):
            issues.append(f"يوجد طابع زمني في السطر {line_no}.")

    return issues


def audit_and_log(text: str, strict_audit: bool):
    issues = audit_summary_text(text)
    if not issues:
        logger.info("اجتاز الملف النهائي فحص التنسيق.")
        return

    for issue in issues:
        logger.warning("فحص التنسيق: %s", issue)
    if strict_audit:
        raise ValueError("فشل فحص التنسيق الصارم للملف النهائي.")


def update_merge_metadata(input_path: Path, output_file: Path, merged_text: str):
    """تحديث metadata.json بعد الدمج الناجح إن وجد."""
    metadata_path = input_path / "metadata.json"
    if not metadata_path.exists():
        return

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        metadata["merged_output"] = str(output_file)
        metadata["merged_words"] = len(merged_text.split())
        metadata["merged_at"] = datetime.now(timezone.utc).isoformat()
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("تعذر تحديث ملف الميتادات بعد الدمج: %s", e)


def is_safe_generated_parts_dir(path: Path) -> bool:
    """التأكد من أن مسار الحذف مجلد أجزاء مولد داخل all_parts."""
    try:
        resolved = path.resolve()
        generated_root = (get_workspace_root() / "all_parts").resolve()
        return resolved.is_relative_to(generated_root) and resolved.name.endswith("_parts")
    except OSError:
        return False


def process_single_dir(
    input_path: Path,
    output_path_str: str,
    strip_prompts: bool,
    clean: bool,
    strict_audit: bool = False,
    allow_raw_parts: bool = False,
):
    """دمج أجزاء مجلد واحد وحفظ التلخيص المدمج النهائي."""
    files = find_summary_files(input_path, allow_raw_parts=allow_raw_parts)
    if not files:
        logger.warning("لم يتم العثور على أجزاء للدمج في %s", input_path.name)
        return

    merged_text = merge_files(files, strip_prompts)
    if not merged_text:
        logger.warning("الملف المدمج الناتج فارغ: %s", input_path.name)
        return

    # تحديد مسار المخرج النهائي (افتراضياً في مجلد summaries بمجلد المهارة)
    if output_path_str:
        output_file = Path(output_path_str)
    else:
        summaries_dir = get_workspace_root() / "summaries"
        original_name = input_path.name.replace("_parts", "")
        output_file = summaries_dir / f"{original_name}_summary.md"

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(merged_text, encoding="utf-8")
    logger.info("تم حفظ الملف المدمج في: %s", output_file.name)
    update_merge_metadata(input_path, output_file, merged_text)
    audit_and_log(merged_text, strict_audit)

    # مسح مجلد الأجزاء المؤقت
    if clean:
        if is_safe_generated_parts_dir(input_path):
            try:
                shutil.rmtree(input_path)
                logger.info("تم تنظيف وحذف مجلد الأجزاء المؤقت: %s", input_path.name)
            except Exception as e:
                logger.warning("فشل حذف مجلد الأجزاء %s: %s", input_path.name, e)
        else:
            logger.warning("تجاوزنا حذف %s لأنه ليس مجلد أجزاء مولداً داخل all_parts.", input_path)


def process_batch_merge(
    input_path: Path,
    output_path_str: str,
    strip_prompts: bool,
    clean: bool,
    strict_audit: bool = False,
    allow_raw_parts: bool = False,
    clean_root: bool = False,
):
    """البحث عن ملفات الأجزاء ودمجها دفعياً."""
    metadata_files = list(input_path.glob("**/metadata.json"))
    if not metadata_files:
        logger.error("لم يتم العثور على ملفات ميتادات (metadata.json) صالحة داخل المجلد.")
        sys.exit(1)

    logger.info("تم الكشف عن مجلد دفعي. وجدنا %d ملفات ميتادات صالحة للدمج.", len(metadata_files))
    metadata_files.sort()

    for idx, meta_file in enumerate(metadata_files):
        parts_dir = meta_file.parent
        rel_parts_dir = parts_dir.relative_to(input_path)
        
        original_stem = parts_dir.name.replace("_parts", "")
        
        # تحديد وجهة الحفظ في مجلد summaries بمجلد المهارة
        dest_folder = get_workspace_root() / "summaries"
        if rel_parts_dir.parent != Path("."):
            dest_file = dest_folder / rel_parts_dir.parent / f"{original_stem}_summary.md"
        else:
            dest_file = dest_folder / f"{original_stem}_summary.md"

        logger.info("[%d/%d] دمج أجزاء: %s -> %s", idx + 1, len(metadata_files), rel_parts_dir, dest_file.name)
        process_single_dir(parts_dir, str(dest_file), strip_prompts, clean, strict_audit, allow_raw_parts)

    if clean_root:
        try:
            generated_root = (get_workspace_root() / "all_parts").resolve()
            resolved_input = input_path.resolve()
            if (
                input_path.exists()
                and resolved_input.is_relative_to(generated_root)
                and not any(input_path.iterdir())
            ):
                shutil.rmtree(input_path)
                logger.info("تم مسح وتنظيف المجلد الجامع «%s» بالكامل.", input_path.name)
            else:
                logger.warning("لم نحذف المجلد الجامع لأنه ليس فارغاً أو ليس داخل all_parts.")
        except Exception as e:
            logger.warning("فشل حذف المجلد الجامع: %s", e)


def extract_numbers(filename: str) -> list[int]:
    """استخلاص الأرقام من اسم الملف للمقارنة الحسابية الصحيحة."""
    return [int(s) for s in re.findall(r"\d+", filename)]


def smart_sort_key(file_path: Path):
    """مفتاح فرز يعتمد على الأرقام أولاً لتجنب الترتيب الهجائي الخاطئ."""
    return (extract_numbers(file_path.name), file_path.name.lower())


def clean_and_parse_summary(file_path: Path, is_first: bool, parent_title: str = None, anthology: bool = False) -> tuple[str, str, list[str]]:
    """تحليل ملف التلخيص واستخلاص العناوين وتنظيف التكرار."""
    content = read_file_with_fallback_encoding(file_path)
    lines = content.splitlines()
    non_empty_lines = [l.strip() for l in lines if l.strip()]

    extracted_parent_title = parent_title

    # 1. استخلاص العنوان الرئيسي من أول ملف
    if is_first and non_empty_lines:
        first_line = non_empty_lines[0]
        if first_line == BISMILLAH:
            if len(non_empty_lines) > 1:
                extracted_parent_title = non_empty_lines[1]
        else:
            extracted_parent_title = first_line

        if extracted_parent_title:
            extracted_parent_title = extracted_parent_title.strip(":")

    # 2. استخلاص اسم الفصل
    chapter_title = None
    for l in non_empty_lines[:4]:
        if l == BISMILLAH or (extracted_parent_title and (l == extracted_parent_title or l == extracted_parent_title + ":")):
            continue
        match = CHAPTER_TITLE_PATTERN.search(l)
        if match:
            chapter_title = match.group(1)
            break

    if not chapter_title:
        clean_stem = file_path.stem.replace("_summary", "").replace("_parts", "").replace("_part", "")
        clean_stem = re.sub(r'[\s_-]+', ' ', clean_stem).strip()
        chapter_title = clean_stem if clean_stem else "قسم فرعي"

    # 3. تنظيف محتوى التلخيص
    cleaned_lines = []
    # يُستخدم في نمط المجموع فحسب، لتتبع أول بسملة/عنوان تم الاحتفاظ بهما داخل كل ملف
    has_kept_bismillah = False
    has_kept_title = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue

        if stripped == BISMILLAH:
            if anthology:
                if not has_kept_bismillah:
                    cleaned_lines.append(line)
                    has_kept_bismillah = True
            continue

        if extracted_parent_title and (stripped == extracted_parent_title or stripped == extracted_parent_title + ":"):
            if anthology:
                if not has_kept_title:
                    cleaned_lines.append(line)
                    has_kept_title = True
            continue

        if chapter_title and (stripped == chapter_title or stripped == f"\t{chapter_title}:" or stripped == f"{chapter_title}:"):
            continue

        if chapter_title and f"({chapter_title})" in stripped and (stripped.endswith(":") or "شرح" in stripped or "كتاب" in stripped):
            continue

        cleaned_lines.append(line)

    return extracted_parent_title, chapter_title, cleaned_lines


def compile_summaries(input_dir: Path, output_file_path: Path = None, anthology: bool = False):
    """تجميع الملخصات المفرقة في ملف واحد موحد وحفظه في مجلد المهارة."""
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error("مجلد المدخلات غير موجود أو ليس مجلداً: %s", input_dir)
        sys.exit(1)

    summary_files = [f for f in input_dir.glob("**/*.md") if f.is_file()]
    if not summary_files:
        logger.error("لم يتم العثور على أي ملفات تلخيص md في %s", input_dir)
        sys.exit(1)

    summary_files.sort(key=smart_sort_key)
    logger.info("تم العثور على %d ملفات تلخيص وتجميعها بالترتيب الحسابي:", len(summary_files))

    parent_title = None
    chapters_content = []

    for idx, file_path in enumerate(summary_files):
        logger.info("معالجة وتصفية الملف: %s", file_path.name)
        is_first = (idx == 0)
        parent_title, chapter_name, cleaned_lines = clean_and_parse_summary(file_path, is_first, parent_title, anthology)

        if anthology:
            if idx > 0:
                chapters_content.append("---")
                chapters_content.append("")
        else:
            chapters_content.append(f"\t{chapter_name}:")
            
        chapters_content.extend(cleaned_lines)
        chapters_content.append("")

    if anthology:
        final_title = f"مجموع رسائل ومصنفات {input_dir.parent.name if input_dir.parent else 'المجموع'}"
    else:
        final_title = parent_title if parent_title else "كتاب ملخصات مجمعة"
        
    compiled_parts = [
        BISMILLAH,
        f"{final_title}:",
        ""
    ]
    compiled_parts.extend(chapters_content)

    # تحديد مسار المخرج
    if output_file_path:
        final_output_file = output_file_path
    else:
        sanitized_title = re.sub(r'[\\/*?:"<>|]', "", final_title)
        sanitized_title = re.sub(r'\s+', '_', sanitized_title).strip("_")
        final_output_file = get_workspace_root() / f"{sanitized_title}.md"

    final_output_file.parent.mkdir(parents=True, exist_ok=True)
    final_content = "\n".join(compiled_parts)
    final_output_file.write_text(final_content, encoding="utf-8")
    logger.info("تم بنجاح تجميع الملفات وحفظ الملف الموحد في: %s", final_output_file)


def detect_mode(input_path: Path) -> str:
    """الكشف التلقائي الذكي لوضع التشغيل بناءً على محتويات مجلد المدخلات."""
    if not input_path.exists():
        return "compile"
        
    if input_path.is_file():
        return "compile"
        
    if (input_path / "metadata.json").exists():
        return "merge"
        
    metadata_files = list(input_path.glob("**/metadata.json"))
    if metadata_files:
        return "merge"
        
    return "compile"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="السكربت الموحد لتجهيز وتجميع التلخيصات.")
    parser.add_argument(
        "input_dir",
        type=str,
        nargs="?",
        default=str(get_workspace_root() / "summaries"),
        help="مجلد المدخلات (الافتراضي: summaries في مجلد المهارة)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="مسار ملف أو مجلد المخرج النهائي"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["merge", "compile", "auto"],
        default="auto",
        help="وضع التشغيل: merge (دمج أجزاء) أو compile (تجميع فصول) أو auto (كشف تلقائي)"
    )
    parser.add_argument(
        "-c", "--clean",
        action="store_true",
        help="مسح مجلد الأجزاء بعد نجاح الدمج لتوفير المساحة"
    )
    parser.add_argument(
        "--clean-root",
        action="store_true",
        help="حذف المجلد الجامع بعد الدمج فقط إذا كان فارغاً وداخل all_parts"
    )
    parser.add_argument(
        "--allow-raw-parts",
        action="store_true",
        help="السماح بدمج ملفات الأجزاء الأصلية عند غياب ملفات *_summary.md"
    )
    parser.add_argument(
        "--strict-audit",
        action="store_true",
        help="إنهاء التشغيل بخطأ إذا فشل فحص تنسيق الملف النهائي"
    )
    parser.add_argument(
        "--keep-prompts",
        action="store_true",
        help="الإبقاء على تعليمات الـ Prompt دون حذفها"
    )
    parser.add_argument(
        "-a", "--anthology",
        action="store_true",
        help="تفعيل نمط المجموع لدمج المصنفات المستقلة"
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input_dir)

    if not input_path.exists():
        logger.error("مسار المدخلات غير موجود: %s", args.input_dir)
        sys.exit(1)

    mode = args.mode
    if mode == "auto":
        mode = detect_mode(input_path)
        logger.info("تم الكشف تلقائياً عن وضع التشغيل: %s", mode)

    output_path = Path(args.output) if args.output else None

    if mode == "merge":
        is_single = (input_path / "metadata.json").exists()
        if is_single:
            logger.info("دمج أجزاء ملف مفرد في: %s", input_path.name)
            process_single_dir(
                input_path,
                args.output,
                not args.keep_prompts,
                args.clean,
                strict_audit=args.strict_audit,
                allow_raw_parts=args.allow_raw_parts,
            )
        else:
            logger.info("دمج أجزاء دفعي في مجلد: %s", input_path.name)
            process_batch_merge(
                input_path,
                args.output,
                not args.keep_prompts,
                args.clean,
                strict_audit=args.strict_audit,
                allow_raw_parts=args.allow_raw_parts,
                clean_root=args.clean_root,
            )
    else:
        logger.info("تجميع فصول التلخيصات في مجلد: %s", input_path.name)
        compile_summaries(input_path, output_path, args.anthology)
