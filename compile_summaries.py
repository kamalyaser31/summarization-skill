#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
السكربت الموحد لتجهيز التلخيصات وتجميع فصول الكتب.
يجمع السكربت بين:
1. دمج أجزاء الملفات المقسمة (Merge Mode) مع تنظيف البرومبتات والبسملة المكررة.
2. تجميع فصول الملخصات المفرقة (Compile Mode) في كتاب واحد بالترتيب الحسابي وتنقية التكرارات.
"""

import argparse
import logging
import re
import shutil
import sys
from pathlib import Path

from utils import read_file_with_fallback_encoding

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



def strip_prompt(text: str) -> str:
    """حذف تعليمات التلخيص (Prompt) من بداية النص."""
    return PROMPT_PATTERN.sub('', text, count=1).strip()


def find_summary_files(input_dir: Path) -> list[Path]:
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

    if part_files:
        part_files.sort(key=lambda x: x[0])
        part_numbers = [x[0] for x in part_files]
        expected = list(range(1, len(part_files) + 1))
        if part_numbers != expected:
            raise ValueError(f"فجوة في أرقام ملفات الأجزاء الأصلية: {part_numbers}")
        return [f for _, f in part_files]

    return []


def clean_part_content(text: str, is_first: bool, main_title: str = None) -> tuple[str, str]:
    """تنظيف أجزاء الملخصات وإزالة البسملة والعناوين المكررة."""
    text = strip_prompt(text).strip()
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
                
        return "\n".join(lines).strip(), extracted_title


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
            text = text.strip()

        if text:
            parts.append(text)

    return "\n\n".join(parts)


def process_single_dir(input_path: Path, output_path_str: str, strip_prompts: bool, clean: bool):
    """دمج أجزاء مجلد واحد وحفظ التلخيص المدمج النهائي."""
    files = find_summary_files(input_path)
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
        summaries_dir = Path(__file__).parent / "summaries"
        original_name = input_path.name.replace("_parts", "")
        output_file = summaries_dir / f"{original_name}_summary.md"

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(merged_text, encoding="utf-8")
    logger.info("تم حفظ الملف المدمج في: %s", output_file.name)

    # مسح مجلد الأجزاء المؤقت
    if clean:
        try:
            shutil.rmtree(input_path)
            logger.info("تم تنظيف وحذف مجلد الأجزاء المؤقت: %s", input_path.name)
        except Exception as e:
            logger.warning("فشل حذف مجلد الأجزاء %s: %s", input_path.name, e)


def process_batch_merge(input_path: Path, output_path_str: str, strip_prompts: bool, clean: bool):
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
        dest_folder = Path(__file__).parent / "summaries"
        if rel_parts_dir.parent != Path("."):
            dest_file = dest_folder / rel_parts_dir.parent / f"{original_stem}_summary.md"
        else:
            dest_file = dest_folder / f"{original_stem}_summary.md"

        logger.info("[%d/%d] دمج أجزاء: %s -> %s", idx + 1, len(metadata_files), rel_parts_dir, dest_file.name)
        process_single_dir(parts_dir, str(dest_file), strip_prompts, clean)

    if clean:
        try:
            # لا نُقيِّد الحذف باسم المجلد لأن المستخدم قد يمرر أي مسار جامع
            if input_path.exists():
                shutil.rmtree(input_path)
                logger.info("تم مسح وتنظيف المجلد الجامع «%s» بالكامل.", input_path.name)
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
        final_output_file = Path(__file__).parent / f"{sanitized_title}.md"

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
        default=str(Path(__file__).parent / "summaries"),
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
            process_single_dir(input_path, args.output, not args.keep_prompts, args.clean)
        else:
            logger.info("دمج أجزاء دفعي في مجلد: %s", input_path.name)
            process_batch_merge(input_path, args.output, not args.keep_prompts, args.clean)
    else:
        logger.info("تجميع فصول التلخيصات في مجلد: %s", input_path.name)
        compile_summaries(input_path, output_path, args.anthology)
