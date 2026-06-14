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
    from merge_summaries import find_summary_files, merge_files, read_file_with_fallback_encoding
    from compile_summaries import compile_summaries
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

        logger.info("5. اختبار حماية الكتل البرمجية والجداول من التقطيع...")
        struct_test_file = test_dir / "struct_test.md"
        struct_test_content = (
            "هذا نص تمهيدي يحتوي على بعض الكلمات.\n"
            "```python\n"
            "def test():\n"
            "    print('code block content line 1')\n"
            "    print('code block content line 2')\n"
            "```\n"
            "هذا نص متوسط بين الجدول والكود.\n"
            "| العمود الأول | العمود الثاني |\n"
            "|---|---|\n"
            "| قيمة 1 | قيمة 2 |\n"
            "نص ختامي بعد الجدول."
        )
        struct_test_file.write_text(struct_test_content, encoding="utf-8")
        struct_output_dir = test_dir / "struct_parts"
        
        # نقسم بحد أقصى 15 كلمة للجزء، مما يضطر السكربت للقطع
        split_text(struct_test_file, struct_output_dir, max_words=15)
        
        # نقرأ الأجزاء الناتجة ونتاكد من عدم قطع الكتل
        with open(struct_output_dir / "metadata.json", "r", encoding="utf-8") as f:
            struct_metadata = json.load(f)
            
        logger.info("  تم تقسيم نص الهياكل إلى %d أجزاء.", struct_metadata["parts_count"])
        for part in struct_metadata["parts"]:
            part_path = struct_output_dir / part["file"]
            part_text = part_path.read_text(encoding="utf-8")
            
            # نتحقق من الكتل البرمجية: إذا وجدنا وسم البدء ``` فيجب أن نجد وسم الإغلاق في ذات الجزء
            start_ticks = part_text.count("```python")
            end_ticks = part_text.count("```") - start_ticks # لأن ```python يحتوي على ```
            if start_ticks != end_ticks:
                raise AssertionError(f"إخفاق: تم قطع الكتلة البرمجية في الجزء: {part['file']}")
                
            # نتحقق من الجدول: لا يجب أن يحتوي الجزء على أسطر جدول مقطوعة من صفوف الهيدر
            # إذا وجدنا صف الهيدر |---|---|, فيجب أن نجد بقية أسطر الجدول معه
            if "|---|---|" in part_text:
                if "قيمة 1" not in part_text:
                    raise AssertionError(f"إخفاق: تم قطع الجدول في الجزء: {part['file']}")
        logger.info("  نجح اختبار حماية الجداول والكتل البرمجية بنجاح.")

        logger.info("6. اختبار إزالة البسملة والعناوين المكررة تلقائياً عند الدمج...")
        dup_output_dir = test_dir / "dup_parts"
        dup_output_dir.mkdir(parents=True, exist_ok=True)
        
        part_1_content = (
            "[تعليمات التلخيص - الجزء 1 من 2]\n"
            "هذا هو الجزء الأول؛ ابدأ بالبسملة والعنوان الرئيسي.\n"
            "---\n"
            "بسم الله الرحمن الرحيم.\n"
            "شرح كتاب النحو الواضح:\n"
            "• فائدة النحو صون اللسان عن الخطأ."
        )
        part_2_content = (
            "[تعليمات التلخيص - الجزء 2 من 2]\n"
            "هذا استكمال للتلخيص السابق؛ تابع من حيث انتهيت دون تكرار البسملة أو العنوان.\n"
            "---\n"
            "بسم الله الرحمن الرحيم.\n"
            "شرح كتاب النحو الواضح:\n"
            "• وفائدة الصرف معرفة بنية الكلمة."
        )
        
        (dup_output_dir / "test_book_part_01_summary.md").write_text(part_1_content, encoding="utf-8")
        (dup_output_dir / "test_book_part_02_summary.md").write_text(part_2_content, encoding="utf-8")
        
        summary_files_dup = find_summary_files(dup_output_dir)
        merged_text_dup = merge_files(summary_files_dup, strip_prompts=True)
        
        # نتحقق من أن البسملة والعنوان ذُكرا مرة واحدة فقط في النص المدمج
        bismillah_count = merged_text_dup.count("بسم الله الرحمن الرحيم.")
        title_count = merged_text_dup.count("شرح كتاب النحو الواضح:")
        
        logger.info("  عدد البسملات في المدمج: %d، عدد العناوين: %d", bismillah_count, title_count)
        if bismillah_count != 1:
            raise AssertionError(f"إخفاق: البسملة مكررة في المدمج ({bismillah_count} مرات).")
        if title_count != 1:
            raise AssertionError(f"إخفاق: العنوان الرئيسي مكرر في المدمج ({title_count} مرات).")
        logger.info("  نجح اختبار إزالة التكرار تلقائياً بنجاح تام.")

        logger.info("7. اختبار متانة قراءة الملفات تالفة الترميز...")
        corrupt_file = test_dir / "corrupt_encoding.txt"
        # كتابة بايتات غير صالحة بترميز utf-8
        corrupt_file.write_bytes(b"\xe2\x28\xa1\xff\xfe\x00")
        
        try:
            read_content = read_file_with_fallback_encoding(corrupt_file)
            logger.info("  تمت قراءة الملف التالف بنجاح دون انهيار. طول النص: %d", len(read_content))
            if not read_content:
                raise AssertionError("إخفاق: النص المقروء فارغ.")
        except Exception as e:
            raise AssertionError(f"إخفاق: انهار السكربت عند قراءة ملف تالف الترميز: {e}")
        logger.info("  نجح اختبار متانة الترميز.")

        logger.info("8. اختبار التقسيم والدمج والتنظيف والتجميع للمجلدات دفعياً...")
        batch_src_dir = test_dir / "batch_src"
        batch_src_dir.mkdir(parents=True, exist_ok=True)
        
        # إنشاء هيكل شجري من المجلدات والملفات النصية
        (batch_src_dir / "chapter_01.txt").write_text("بسم الله الرحمن الرحيم.\nشرح كتاب أصول الإيمان:\n• أصل الإيمان بالله تعالى هو الركن الأول.", encoding="utf-8")
        (batch_src_dir / "chapter_02.txt").write_text("بسم الله الرحمن الرحيم.\nشرح كتاب أصول الإيمان:\n• وأصل الإيمان بالملائكة الكرام المطهرين.", encoding="utf-8")
        
        sub_folder = batch_src_dir / "sub_folder"
        sub_folder.mkdir(parents=True, exist_ok=True)
        (sub_folder / "chapter_03.md").write_text("بسم الله الرحمن الرحيم.\nشرح كتاب أصول الإيمان:\n• وأصل الإيمان بالكتب السماوية المنزلة.", encoding="utf-8")
        
        import subprocess
        
        # تقسيم المجلد تراجعياً
        split_cmd = [sys.executable, "split_text.py", str(batch_src_dir), "-r", "--max-words", "20"]
        logger.info("  تشغيل أمر التقسيم: %s", " ".join(split_cmd))
        subprocess.run(split_cmd, check=True)
        
        # التحقق من إنشاء مجلد all_parts وهيكله الشجري
        all_parts_dir = batch_src_dir / "all_parts"
        if not all_parts_dir.exists():
            raise AssertionError("إخفاق: لم يتم إنشاء المجلد الجامع all_parts")
            
        part_1_folder = all_parts_dir / "chapter_01_parts"
        part_3_folder = all_parts_dir / "sub_folder" / "chapter_03_parts"
        
        if not part_1_folder.exists() or not part_3_folder.exists():
            raise AssertionError("إخفاق: لم يتم محاكاة الهيكل الشجري للملفات في all_parts")
            
        logger.info("  تم التحقق من نجاح التقسيم الدفعي وإنشاء مجلد all_parts وهيكله الشجري.")

        # 1.ب اختبار الاستئناف والتحقق على مستوى الأجزاء (Part-level Checkpointing)
        part_1_file = part_1_folder / "chapter_01_part_01.md"
        if not part_1_file.exists():
            raise AssertionError("إخفاق: لم يتم العثور على الجزء الأول للفصل الأول")
        
        # كتابة نص مخصص في الجزء الأول لمحاكاة تعديل يدوي أو حفظ مسبق
        part_1_file.write_text("CUSTOM_PART_CONTENT", encoding="utf-8")
        
        # تشغيل التقسيم مرة أخرى بدون --force
        logger.info("  إعادة تشغيل التقسيم بدون --force للتحقق من استئناف الأجزاء...")
        subprocess.run(split_cmd, check=True)
        
        # التأكد من أنه تم تجاوز إعادة التقسيم وبقاء النص المخصص
        if part_1_file.read_text(encoding="utf-8") != "CUSTOM_PART_CONTENT":
            raise AssertionError("إخفاق: تم التعديل على ملف الأجزاء المكتملة مسبقاً بالرغم من عدم استخدام --force")
        logger.info("  نجح فحص تجاوز إعادة التقسيم وحفظ الأجزاء المكتملة بنجاح.")

        # تشغيل التقسيم مع خيار --force
        logger.info("  تشغيل التقسيم مع --force لإجبار إعادة المعالجة...")
        subprocess.run(split_cmd + ["--force"], check=True)
        
        # التأكد من إعادة الكتابة وزوال النص المخصص
        if part_1_file.read_text(encoding="utf-8") == "CUSTOM_PART_CONTENT":
            raise AssertionError("إخفاق: لم يتم إعادة تقسيم الملفات بالرغم من استخدام خيار --force")
        logger.info("  نجح فحص إجبار إعادة التقسيم باستخدام --force بنجاح.")

        # 1.ج اختبار الاستئناف على مستوى الملف (File-level Resume)
        # إنشاء ملف تلخيص نهائي لمحاكاة اكتمال العمل
        summaries_dir_test = batch_src_dir / "summaries"
        summaries_dir_test.mkdir(parents=True, exist_ok=True)
        dummy_summary = summaries_dir_test / "chapter_02.md"
        dummy_summary.write_text("DUMMY_SUMMARY_CONTENT", encoding="utf-8")
        
        # حذف مجلد الأجزاء المقابل للتأكد من عدم إنشائه مجدداً
        part_2_folder = all_parts_dir / "chapter_02_parts"
        if part_2_folder.exists():
            shutil.rmtree(part_2_folder)
            
        # تشغيل التقسيم مرة أخرى بدون --force
        logger.info("  تشغيل التقسيم للتحقق من تخطي الملفات المكتملة تلخيصاتها...")
        subprocess.run(split_cmd, check=True)
        
        # التأكد من عدم إنشاء مجلد الأجزاء مجدداً لتخطي الملف
        if part_2_folder.exists():
            raise AssertionError("إخفاق: تم تقسيم الملف بالرغم من وجود ملخص نهائي مكتمل وصالح")
        logger.info("  نجح فحص تخطي الملف المكتمل تلخيصه مسبقاً.")

        # تشغيل التقسيم مع خيار --force
        logger.info("  تشغيل التقسيم مع --force للتحقق من إجبار إعادة تقسيم الملف المكتمل...")
        subprocess.run(split_cmd + ["--force"], check=True)
        
        # التأكد من إعادة إنشاء المجلد وتجزئة الملف
        if not part_2_folder.exists():
            raise AssertionError("إخفاق: لم يتم إعادة تقسيم الملف المكتمل بالرغم من تمرير خيار --force")
        logger.info("  نجح فحص إجبار معالجة الملفات المكتملة مسبقاً.")
        
        # 2. محاكاة تلخيص الأجزاء في المجلد الجامع
        metadata_files = list(all_parts_dir.glob("**/metadata.json"))
        for meta_file in metadata_files:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            for part in meta["parts"]:
                part_path = meta_file.parent / part["file"]
                part_text = part_path.read_text(encoding="utf-8")
                clean_text = re.sub(r'^\[تعليمات التلخيص.*?\]\s*.*?---\s*', '', part_text, flags=re.DOTALL | re.MULTILINE).strip()
                summary_path = part_path.with_name(part_path.stem + "_summary.md")
                summary_path.write_text(f"بسم الله الرحمن الرحيم.\nشرح كتاب أصول الإيمان:\n• تلخيص:\n{clean_text}", encoding="utf-8")
                
        logger.info("  تمت محاكاة تلخيص الأجزاء وحفظها في المجلدات الفرعية.")
        
        # 3. اختبار دمج المجلدات دفعياً مع خيار التنظيف الشامل
        merge_cmd = [sys.executable, "merge_summaries.py", str(all_parts_dir), "-c"]
        logger.info("  تشغيل أمر الدمج: %s", " ".join(merge_cmd))
        subprocess.run(merge_cmd, check=True)
        
        # التحقق من إنشاء مجلد summaries وهيكله الشجري
        summaries_dir = batch_src_dir / "summaries"
        if not summaries_dir.exists():
            raise AssertionError("إخفاق: لم يتم إنشاء مجلد summaries")
            
        summary_1 = summaries_dir / "chapter_01.md"
        summary_3 = summaries_dir / "sub_folder" / "chapter_03.md"
        
        if not summary_1.exists() or not summary_3.exists():
            raise AssertionError("إخفاق: لم يتم العثور على الملخصات المدمجة شجرياً في summaries")
            
        # التحقق من التنظيف الشامل وحذف all_parts بالكامل
        if all_parts_dir.exists():
            raise AssertionError("إخفاق: خيار --clean لم يقم بحذف مجلد all_parts بالكامل")
            
        logger.info("  تم التحقق من نجاح الدمج الدفعي شجرياً وزوال مجلد all_parts بالكامل.")
        
        # 4. اختبار تجميع الملخصات وتنقيتها رقمياً بالترتيب الحسابي
        compile_cmd = [sys.executable, "compile_summaries.py", "-i", str(summaries_dir)]
        logger.info("  تشغيل أمر التجميع: %s", " ".join(compile_cmd))
        subprocess.run(compile_cmd, check=True)
        
        compiled_file = batch_src_dir / "شرح_كتاب_أصول_الإيمان.md"
        if not compiled_file.exists():
            raise AssertionError(f"إخفاق: لم يتم إنشاء ملف التجميع الموحد: {compiled_file}")
            
        compiled_content = compiled_file.read_text(encoding="utf-8")
        
        bismillah_cnt = compiled_content.count("بسم الله الرحمن الرحيم.")
        title_cnt = compiled_content.count("شرح كتاب أصول الإيمان:")
        
        logger.info("  عدد البسملات في المجمع: %d، عدد العناوين: %d", bismillah_cnt, title_cnt)
        if bismillah_cnt != 1:
            raise AssertionError(f"إخفاق: البسملة مكررة في المجمع ({bismillah_cnt} مرات)")
        if title_cnt != 1:
            raise AssertionError(f"إخفاق: العنوان الرئيسي مكرر في المجمع ({title_cnt} مرات)")
            
        # التحقق من الفرز الرقمي الحسابي للفصول
        idx1 = compiled_content.find("chapter 01:")
        idx2 = compiled_content.find("chapter 02:")
        idx3 = compiled_content.find("chapter 03:")
        
        logger.info("  مواقع الفصول في الملف المجمع: %d, %d, %d", idx1, idx2, idx3)
        if not (idx1 < idx2 < idx3):
            raise AssertionError("إخفاق: ترتيب فصول التجميع رقمياً غير صحيح.")
            
        logger.info("  نجح اختبار التجميع الديناميكي والفرز الحسابي بنجاح باهر.")

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
