#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
سكربت تجميع فصول التلخيص المفرقة في ملف md واحد موحد.
يزيل تكرار البسملة والعناوين الرئيسية، وينشئ عناوين فصول ديناميكية ومرتبة رقمياً.
"""

import argparse
import logging
import re
import sys
from pathlib import Path

# إعداد السجل تماشياً مع معايير المشروع
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

# علامة البسملة القياسية المحددة في المهارة
BISMILLAH = "بسم الله الرحمن الرحيم."

# نمط العناوين الفرعية للفصول لاستخلاص اسم الفصل بين قوسين
CHAPTER_TITLE_PATTERN = re.compile(
    r"\((الفصل\s+[^\)]+|الباب\s+[^\)]+|الجزء\s+[^\)]+|المبحث\s+[^\)]+)\)",
    re.IGNORECASE
)


def read_file_with_fallback_encoding(file_path: Path) -> str:
    """قراءة الملف مع تجربة ترميزات متعددة تفادياً لأخطاء فك الترميز."""
    encodings = ["utf-8", "utf-8-sig", "cp1256", "latin-1"]
    for enc in encodings:
        try:
            return file_path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    # ملاذ أخير تفادياً للانهيار
    try:
        logger.warning("فشلت جميع الترميزات؛ سيتم قراءة الملف %s بترميز utf-8 مع استبدال البايتات التالفة.", file_path.name)
        return file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise ValueError(f"تعذر قراءة الملف {file_path} باستخدام الترميزات المتاحة: {e}")


def extract_numbers(filename: str) -> list[int]:
    """استخلاص الأرقام من اسم الملف للمقارنة الحسابية الصحيحة."""
    return [int(s) for s in re.findall(r"\d+", filename)]


def smart_sort_key(file_path: Path):
    """مفتاح فرز يعتمد على الأرقام أولاً لتجنب الترتيب الهجائي الخاطئ (مثل 10 قبل 2)."""
    return (extract_numbers(file_path.name), file_path.name.lower())


def clean_and_parse_summary(file_path: Path, is_first: bool, parent_title: str = None) -> tuple[str, str, list[str]]:
    """
    تحليل ملف التلخيص واستخلاص العناوين وتنظيف التكرار.
    يرجع: (العنوان_الرئيسي_المكتشف، عنوان_الفصل_المكتشف، خطوط_المحتوى_المنظفة)
    """
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
    for l in non_empty_lines[:4]:  # فحص أول 4 أسطر فقط
        if l == BISMILLAH or (extracted_parent_title and (l == extracted_parent_title or l == extracted_parent_title + ":")):
            continue
        match = CHAPTER_TITLE_PATTERN.search(l)
        if match:
            chapter_title = match.group(1)
            break

    # إذا لم يُعثر على نمط للفصل، يتم تهذيب اسم الملف ليكون هو عنوان الفصل
    if not chapter_title:
        clean_stem = file_path.stem.replace("_summary", "").replace("_parts", "").replace("_part", "")
        clean_stem = re.sub(r'[\s_-]+', ' ', clean_stem).strip()
        chapter_title = clean_stem if clean_stem else "قسم فرعي"

    # 3. تنظيف محتوى التلخيص
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue

        # تخطي البسملة المكررة
        if stripped == BISMILLAH:
            continue

        # تخطي العنوان الرئيسي المكرر
        if extracted_parent_title and (stripped == extracted_parent_title or stripped == extracted_parent_title + ":"):
            continue

        # تخطي السطر الذي يحتوي على عنوان الفصل فقط
        if chapter_title and (stripped == chapter_title or stripped == f"\t{chapter_title}:" or stripped == f"{chapter_title}:"):
            continue

        # تخطي سطر الترويسة المكرر للفصل
        if chapter_title and f"({chapter_title})" in stripped and (stripped.endswith(":") or "شرح" in stripped or "كتاب" in stripped):
            continue

        cleaned_lines.append(line)

    return extracted_parent_title, chapter_title, cleaned_lines


def compile_summaries(input_dir: Path, output_file_path: Path = None):
    """تجميع الملخصات وتنقيتها وكتابة الملف الموحد الكلي."""
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error("مجلد المدخلات غير موجود أو ليس مجلداً: %s", input_dir)
        sys.exit(1)

    # البحث عن ملفات التلخيص بالامتداد md في المجلد وفروعه
    summary_files = [f for f in input_dir.glob("**/*.md") if f.is_file()]
    if not summary_files:
        logger.error("لم يتم العثور على أي ملفات تلخيص md في %s", input_dir)
        sys.exit(1)

    # الترتيب الرقمي الذكي
    summary_files.sort(key=smart_sort_key)
    logger.info("تم العثور على %d ملفات تلخيص وسيتم تجميعها بالترتيب الحسابي:", len(summary_files))
    for f in summary_files:
        logger.info("  - %s", f.name)

    parent_title = None
    chapters_content = []

    for idx, file_path in enumerate(summary_files):
        logger.info("معالجة وتصفية الملف: %s", file_path.name)
        is_first = (idx == 0)
        parent_title, chapter_name, cleaned_lines = clean_and_parse_summary(file_path, is_first, parent_title)

        # إضافة اسم الفصل كعنوان فرعي مزاح بـ Tab ليتناسب مع هيكلية المهارة
        chapters_content.append(f"\t{chapter_name}:")
        chapters_content.extend(cleaned_lines)
        chapters_content.append("")  # سطر فارغ للفصل بين الفصول

    # بناء رأس التلخيص المجمع
    final_title = parent_title if parent_title else "كتاب ملخصات مجمعة"
    compiled_parts = [
        BISMILLAH,
        f"{final_title}:",
        ""  # سطر فارغ بعد العنوان الرئيسي
    ]
    compiled_parts.extend(chapters_content)

    # تحديد مسار المخرج
    if output_file_path:
        final_output_file = output_file_path
    else:
        # اشتقاق اسم ملف المخرج من العنوان الرئيسي وحفظه في المجلد الأب
        sanitized_title = re.sub(r'[\\/*?:"<>|]', "", final_title)
        sanitized_title = re.sub(r'\s+', '_', sanitized_title).strip("_")
        final_output_file = input_dir.parent / f"{sanitized_title}.md"

    # كتابة الملف النهائي الموحد
    final_output_file.parent.mkdir(parents=True, exist_ok=True)
    final_content = "\n".join(compiled_parts)
    final_output_file.write_text(final_content, encoding="utf-8")
    logger.info("تم بنجاح تجميع الملفات وحفظ الملف الموحد في: %s", final_output_file)


def main():
    parser = argparse.ArgumentParser(description="تجميع ملخصات الفصول في ملف md واحد موحد.")
    parser.add_argument(
        "-i", "--input-dir",
        type=str,
        default="summaries",
        help="مسار مجلد الملخصات (الافتراضي: summaries)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="مسار ملف المخرج النهائي (الافتراضي: مستخلص تلقائياً في المجلد الأب)"
    )
    args = parser.parse_args()

    input_path = Path(args.input_dir)
    output_path = Path(args.output) if args.output else None

    compile_summaries(input_path, output_path)


if __name__ == "__main__":
    main()
