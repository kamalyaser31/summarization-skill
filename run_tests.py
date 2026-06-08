#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
سكربت الاختبار الآلي لمهارة التلخيص.
يقوم بإنشاء سيناريو متكامل للتحقق من وظائف التقسيم والدمج ودقة المعالجة.
"""

import json
import logging
import shutil
import sys
from pathlib import Path

# إعداد السجل تماشياً مع معايير المشروع
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

# استيراد الوظائف مباشرة لاختبارها برمجياً
try:
    from split_text import split_text, count_words
    from merge_summaries import find_summary_files, merge_files
except ImportError as e:
    logger.error("فشل استيراد السكربتات الأساسية؛ تأكد من وجودها في نفس المسار: %s", e)
    sys.exit(1)


def generate_dummy_text(words_count: int) -> str:
    """توليد نص عربي تجريبي يحتوي على عناوين وفقرات وعلامات وقف."""
    paragraphs = []
    current_words = 0
    paragraph_index = 1

    # استهلال النص
    paragraphs.append("# كتاب الفوائد التجريبية للمختبر:")
    paragraphs.append("بسم الله الرحمن الرحيم. هذا نص تجريبي طويل لغرض اختبار وظائف تقسيم النصوص.")

    while current_words < words_count:
        paragraphs.append(f"\tالعنوان الفرعي رقم {paragraph_index}:")
        
        # جملة تنتهي بعلامة وقف عربية
        sentence_1 = f"هذه هي الجملة الأولى في الفقرة رقم {paragraph_index} لبيان أهمية الاختبار والدقة في كتابة البرمجيات."
        # جملة تنتهي بنقطة متبوعة بقوس ختامي لاختبار دقة الكشف
        sentence_2 = "إن إرساء معايير واضحة يحمي النظام من التداعي العشوائي (كما هو مقرر في الفهرست)."
        # جملة تنتهي بعلامة استفهام متبوعة بعلامة تنصيص ختامية لاختبار التجاهل الذكي لعلامات الاقتباس
        sentence_3 = "فهل يستوي الذين يعلمون والذين لا يعلمون؟»"
        
        paragraph_text = f"{sentence_1}\n{sentence_2}\n{sentence_3}"
        paragraphs.append(paragraph_text)
        
        current_words += len(paragraph_text.split())
        paragraph_index += 1

    return "\n\n".join(paragraphs)


def run_test_scenario():
    """تنفيذ سيناريو الاختبار المتكامل."""
    workspace_dir = Path(__file__).parent
    test_dir = workspace_dir / "test_run_temp"
    
    # تنظيف أي آثار سابقة لضمان حياد الاختبار
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)

    input_file = test_dir / "test_book.txt"
    output_parts_dir = test_dir / "test_book_parts"

    try:
        logger.info("1. توليد النص العربي التجريبي وحفظه...")
        # نولد نصاً يحتوي على 1300 كلمة تقريباً
        dummy_text = generate_dummy_text(1300)
        input_file.write_text(dummy_text, encoding="utf-8")
        total_dummy_words = count_words(dummy_text)
        logger.info("  تم حفظ الملف التجريبي (%d كلمة).", total_dummy_words)

        logger.info("2. اختبار تقسيم النص (split_text)...")
        # نقسم بحد أقصى 600 كلمة للجزء لتفعيل منطق التقسيم
        split_text(input_file, output_parts_dir, max_words=600)

        # التحقق من الملفات الناتجة
        metadata_file = output_parts_dir / "metadata.json"
        if not metadata_file.exists():
            raise AssertionError("إخفاق: لم يتم إنشاء ملف metadata.json")

        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        logger.info("  مخرجات التقسيم: %d أجزاء.", metadata["parts_count"])
        if metadata["parts_count"] < 2:
            raise AssertionError("إخفاق: يجب تقسيم النص إلى جزأين على الأقل.")

        # التحقق من إدراج التوجيهات ونسبية مسارات الملفات
        for part in metadata["parts"]:
            # التحقق من أن المسار نسبي وغير مطلق
            if Path(part["file"]).is_absolute():
                raise AssertionError(f"إخفاق بنيوي: المسار المخزن مطلق وليس نسبياً: {part['file']}")
                
            part_path = output_parts_dir / part["file"]
            part_content = part_path.read_text(encoding="utf-8")
            if "[تعليمات التلخيص" not in part_content:
                raise AssertionError(f"إخفاق: التوجيه السياقي غير موجود في الملف: {part_path.name}")
        logger.info("  تم التحقق من صحة وجود التوجيهات السياقية ونسبية المسارات في الميتادات.")

        logger.info("2.ب اختبار السطر الواحد الضخم (Single-line file)...")
        single_line_file = test_dir / "single_line.txt"
        # سطر واحد يحتوي على 1200 كلمة مفصولة بمسافات ونقاط
        single_line_text = "هذا سطر واحد طويل جداً لغرض الاختبار المباشر. " * 200
        single_line_file.write_text(single_line_text, encoding="utf-8")
        single_line_parts_dir = test_dir / "single_line_parts"
        split_text(single_line_file, single_line_parts_dir, max_words=100)
        # التحقق من أن السطر تم تقسيمه إلى أجزاء متعددة
        with open(single_line_parts_dir / "metadata.json", "r", encoding="utf-8") as f:
            single_line_metadata = json.load(f)
        logger.info("  مخرجات تقسيم السطر الواحد: %d أجزاء.", single_line_metadata["parts_count"])
        if single_line_metadata["parts_count"] < 2:
            raise AssertionError("إخفاق: فشل تقسيم السطر الواحد الضخم.")
        logger.info("  تم تقسيم السطر الواحد الضخم بنجاح تام.")

        logger.info("3. محاكاة إنشاء الملخصات المخصصة (*_part_NN_summary.md)...")
        # نقوم بمحاكاة تلخيص الأجزاء عبر إزالة التوجيهات وإضافة لاحقة تلخيصية
        for part in metadata["parts"]:
            part_path = output_parts_dir / part["file"]
            # محاكاة حفظ التلخيص باسم ملف يحمل اللاحقة _summary.md
            summary_path = part_path.with_name(part_path.stem + "_summary.md")
            
            part_text = part_path.read_text(encoding="utf-8")
            # تنظيف التوجيه لمحاكاة التلخيص النظيف
            import re
            clean_text = re.sub(r'^\[تعليمات التلخيص.*?\]\s*.*?---\s*', '', part_text, flags=re.DOTALL | re.MULTILINE).strip()
            
            # كتابة محتوى التلخيص
            summary_path.write_text(f"بسم الله الرحمن الرحيم.\nتلخيص الجزء:\n{clean_text}", encoding="utf-8")
            logger.info("  تمت محاكاة التلخيص وحفظه في: %s", summary_path.name)

        logger.info("4. اختبار دمج الأجزاء الملخصة المخصصة (merge_summaries)...")
        # نستدعي دمج الملفات مع تمرير مجلد الأجزاء
        summary_files = find_summary_files(output_parts_dir)
        
        # يجب أن يطابق ملفات الملخصات المخصصة _summary.md فقط
        for f in summary_files:
            if not f.name.endswith("_summary.md"):
                raise AssertionError(f"إخفاق: تم التقاط ملف غير ملخص للدمج: {f.name}")
        
        logger.info("  تم التحقق من اختيار ملفات الملخصات المخصصة حصراً وتجاهل الأصول.")

        merged_output = output_parts_dir / "summary_final.md"
        merged_text = merge_files(summary_files, strip_prompts=True)
        merged_output.write_text(merged_text, encoding="utf-8")

        # تحديث الميتادات بنسق نسبي
        metadata["merged_output"] = merged_output.name
        metadata["merged_words"] = len(merged_text.split())
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info("  تم الدمج بنجاح وحفظ الملف النهائي في: %s", merged_output.name)
        logger.info("  عدد كلمات الملف النهائي المدمج: %d كلمة.", metadata["merged_words"])

        if metadata["merged_words"] == 0:
            raise AssertionError("إخفاق: الملف المدمج فارغ.")

        # التحقق من أن مسار المخرج المدمج نسبي في الميتادات
        with open(metadata_file, "r", encoding="utf-8") as f:
            updated_metadata = json.load(f)
        if Path(updated_metadata["merged_output"]).is_absolute():
            raise AssertionError("إخفاق: مسار المخرج المدمج في الميتادات مطلق وليس نسبياً.")

        logger.info("4.ب اختبار كشف الفجوات في التسلسل (Sequence Gap Detection)...")
        # نقوم بحذف جزء من المنتصف لمحاكاة فجوة
        dummy_summary_to_delete = output_parts_dir / f"{input_file.stem}_part_01_summary.md"
        if dummy_summary_to_delete.exists():
            dummy_summary_to_delete.unlink()
            logger.info("  تم حذف الجزء الأول مؤقتاً لمحاكاة الفجوة الرقمية.")
            try:
                find_summary_files(output_parts_dir)
                raise AssertionError("إخفاق: لم يتم اكتشاف الفجوة الرقمية في التسلسل.")
            except ValueError as ve:
                logger.info("  تم اكتشاف الفجوة الرقمية بنجاح ومنع الدمج المبتور: %s", ve)

        logger.info("=== نجحت جميع الاختبارات بنجاح تام! ===")

    except Exception as e:
        logger.error("إخفاق الاختبار: %s", e)
        raise e
    finally:
        # تنظيف المجلد المؤقت بعد انتهاء الاختبار
        if test_dir.exists():
            shutil.rmtree(test_dir)
            logger.info("تم تنظيف مجلد الاختبار المؤقت.")


if __name__ == "__main__":
    run_test_scenario()
