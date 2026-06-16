#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ملف اختبارات مشروع تلخيص النصوص الطويلة وتجميع الكتب بالكامل.
يتضمن اختبارات شاملة لوظائف التقسيم، الدمج الفردي والدفعي، التجميع،
وأنماط التشغيل المختلفة والواجهات البرمجية وتكامل سطر الأوامر (CLI).
"""

import json
import logging
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

# إعداد السجل تماشياً مع المعايير القياسية
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

# المجلد الأساسي للمشروع
BASE_DIR = Path(__file__).parent

# استيراد الوظائف مباشرة للفحص البرميجي
from split_text import (
    count_words,
    read_file_with_fallback_encoding as split_read_encoding,
    split_long_line,
    find_split_point,
    split_text,
)
import compile_summaries as cs


class TestSummarizationSkill(unittest.TestCase):

    def setUp(self):
        """تهيئة بيئة معزولة ونظيفة للاختبارات داخل مساحة العمل."""
        self.test_workspace = BASE_DIR / "test_run_workspace"
        self.test_workspace.mkdir(exist_ok=True)
        
        # إنشاء مسار للملف النصي الأصلي للاختبار
        self.sample_txt = self.test_workspace / "sample_text.txt"
        self.sample_content = (
            "بسم الله الرحمن الرحيم.\n"
            "كتاب التوحيد وشروحه:\n"
            "• الباب الأول: فضيلة التوحيد وما يكفر من الذنوب.\n"
            "التوحيد هو إفراد الله سبحانه بالعبادة والربوبية والأسماء والصفات.\n"
            "وهو الغاية التي خلق الله الخلق لأجلها كما في قوله تعالى وما خلقت الجن والإنس إلا ليعبدون.\n\n"
            "• الباب الثاني: الدعاء إلى شهادة أن لا إله إلا الله.\n"
            "الدعوة إلى التوحيد سبيل الأنبياء والمرسلين وأتباعهم بإحسان.\n"
            "وقد مكث النبي صلى الله عليه وسلم يدعو الناس في مكة ثلاث عشرة سنة.\n\n"
            "• الباب الثالث: الخوف من الشرك.\n"
            "الشرك أعظم ذنب عصي الله به وهو محبط للأعمال بالكلية.\n"
            "فلا يغفر الله لمن مات عليه ويغفر ما دون ذلك لمن يشاء.\n"
        )
        self.sample_txt.write_text(self.sample_content, encoding="utf-8")

    def tearDown(self):
        """تنظيف كامل لمخلفات الاختبارات لضمان نقاء مساحة العمل."""
        if self.test_workspace.exists():
            shutil.rmtree(self.test_workspace)
            
        # إزالة المجلدات المشتركة الناتجة عن الاختبارات
        for folder in ["all_parts", "summaries"]:
            folder_path = BASE_DIR / folder
            if folder_path.exists():
                shutil.rmtree(folder_path)
                
        # مسح أي ملفات مدمجة ناتجة في مساحة العمل
        for file in BASE_DIR.glob("*.md"):
            if "كتاب_التوحيد" in file.name or "مجموع_رسائل" in file.name or "sample_text" in file.name:
                file.unlink()

    def test_word_count_accurate(self):
        """فحص دقة عد الكلمات للنصوص العربية والإنجليزية."""
        logger.info("بدء اختبار دقة عد الكلمات...")
        text_ar = "الحمد لله رب العالمين"
        text_en = "Hello world from python test suite"
        self.assertEqual(count_words(text_ar), 4)
        self.assertEqual(count_words(text_en), 6)

    def test_encoding_fallback_works(self):
        """التحقق من عمل نظام قراءة الملفات بمختلف الترميزات عند الفشل."""
        logger.info("بدء اختبار ترميز الملفات والارتداد التلقائي...")
        
        # 1. إنشاء ملف بترميز UTF-8
        utf8_file = self.test_workspace / "utf8.txt"
        utf8_file.write_text("نص بترميز يوتيف", encoding="utf-8")
        self.assertIn("يوتيف", split_read_encoding(utf8_file))
        
        # 2. إنشاء ملف بترميز CP1256
        cp1256_file = self.test_workspace / "cp1256.txt"
        cp1256_file.write_text("نص بترميز ويندوز", encoding="cp1256")
        self.assertIn("ويندوز", split_read_encoding(cp1256_file))

    def test_split_long_line_correctly(self):
        """التحقق من تجزئة السطور الطويلة جداً دون فقدان النص الأصلي."""
        logger.info("بدء اختبار تجزئة السطور الطويلة جداً...")
        long_line = "جملة أولى. جملة ثانية؟ جملة ثالثة! جملة رابعة"
        segments = split_long_line(long_line, max_words=2)
        # يجب أن تُقسم الجمل إلى مقاطع فرعية
        self.assertTrue(len(segments) >= 3)
        # يجب أن يتطابق النص المجمع تماماً مع الأصل
        self.assertEqual("".join(segments), long_line)

    def test_find_split_point_priorities(self):
        """التحقق من أولويات نقاط القطع (العناوين ثم الفقرات ثم الجمل)."""
        logger.info("بدء اختبار أولويات نقاط القطع...")
        
        # نص يحتوي على سطر فارغ (حد فقرة) يسبقه كلام
        text = "سطر أول كلمة كلمة كلمة.\n\nسطر ثان كلمة كلمة كلمة."
        split_idx = find_split_point(text, max_words=6)
        # يجب أن يفضل القطع عند السطر الفارغ (حد فقرة)
        self.assertEqual(text[:split_idx].strip(), "سطر أول كلمة كلمة كلمة.")

    def test_find_split_point_avoids_code_blocks_and_tables(self):
        """التحقق من أن منطق التقسيم يتجنب القطع داخل الجداول والكتل البرمجية."""
        logger.info("بدء اختبار تجنب القطع داخل الجداول والكتل البرمجية...")
        
        table_text = (
            "البداية هنا.\n"
            "| العمود الأول | العمود الثاني |\n"
            "|---|---|\n"
            "| خلية 1 | خلية 2 |\n"
            "هذا سطر بعد الجدول.\n"
            "النهاية هنا."
        )
        
        # 1. إذا كان حد الكلمات صغيراً (مثلاً 5 كلمات)، يجب أن يقطع قبل الجدول
        split_idx_small = find_split_point(table_text, max_words=5)
        self.assertEqual(split_idx_small, table_text.find("| العمود الأول"))
        
        # 2. إذا كان حد الكلمات كافياً لاحتواء الجدول (مثلاً 20 كلمة)، يجب أن يقطع بعد الجدول
        split_idx_large = find_split_point(table_text, max_words=20)
        self.assertTrue(split_idx_large > table_text.find("| خلية 1 | خلية 2 |"))

        # 3. التحقق من تجنب القطع داخل الكتل البرمجية
        code_text = (
            "البداية هنا.\n"
            "```python\n"
            "def foo():\n"
            "    print('hello')\n"
            "```\n"
            "النهاية هنا."
        )
        # يجب ألا يقطع داخل الكتلة البرمجية، بل يقطع قبلها
        split_idx_code = find_split_point(code_text, max_words=6)
        self.assertEqual(split_idx_code, code_text.find("```python"))

    def test_split_text_single_file_and_metadata(self):
        """التحقق من تقسيم ملف مفرد وإنشاء ملف الميتادات بالأجزاء المناسبة."""
        logger.info("بدء اختبار تقسيم ملف مفرد وتدقيق ميتادات الأجزاء...")
        
        output_dir = self.test_workspace / "parts"
        split_text(self.sample_txt, output_dir, max_words=25, force=True)
        
        # فحص تولد الأجزاء وملف metadata.json
        metadata_file = output_dir / "metadata.json"
        self.assertTrue(metadata_file.exists())
        
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
        self.assertEqual(metadata["total_words"], count_words(self.sample_content))
        self.assertTrue(metadata["parts_count"] > 1)
        
        # فحص تضمين تعليمات التلخيص
        first_part = output_dir / metadata["parts"][0]["file"]
        self.assertTrue(first_part.exists())
        content = first_part.read_text(encoding="utf-8")
        self.assertIn("[تعليمات التلخيص - الجزء 1 من", content)

    def test_split_text_checkpointing(self):
        """التحقق من عدم تكرار تقسيم الملفات إذا لم تتغير المدخلات (الاستئناف)."""
        logger.info("بدء اختبار آلية الاستئناف وتجنب تكرار الكتابة...")
        
        output_dir = self.test_workspace / "checkpoint_parts"
        split_text(self.sample_txt, output_dir, max_words=25, force=True)
        
        # حفظ تاريخ تعديل الملف الأول
        metadata_file = output_dir / "metadata.json"
        with open(metadata_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        first_part_path = output_dir / meta["parts"][0]["file"]
        orig_mtime = first_part_path.stat().st_mtime
        
        # تشغيل التقسيم مرة أخرى بدون خيار force
        split_text(self.sample_txt, output_dir, max_words=25, force=False)
        self.assertEqual(first_part_path.stat().st_mtime, orig_mtime)
        
        # تشغيل التقسيم مرة أخرى مع خيار force
        # ننتظر قليلاً للتأكد من تغير الوقت المتاح بالنظام
        import time
        time.sleep(0.1)
        split_text(self.sample_txt, output_dir, max_words=25, force=True)
        self.assertNotEqual(first_part_path.stat().st_mtime, orig_mtime)

    def test_detect_mode_correct(self):
        """التحقق من الكشف التلقائي الذكي لوضع التشغيل (Auto Mode Detection)."""
        logger.info("بدء اختبار كشف أوضاع التشغيل تلقائياً...")
        
        # وضع الدمج (وجود ميتادات في المجلد)
        merge_dir = self.test_workspace / "merge_dir"
        merge_dir.mkdir()
        (merge_dir / "metadata.json").write_text("{}", encoding="utf-8")
        self.assertEqual(cs.detect_mode(merge_dir), "merge")
        
        # وضع التجميع (عدم وجود ميتادات)
        compile_dir = self.test_workspace / "compile_dir"
        compile_dir.mkdir()
        self.assertEqual(cs.detect_mode(compile_dir), "compile")

    def test_merge_files_deduplicates_titles_and_bismillah(self):
        """التحقق من إزالة البسملة والعناوين المكررة عند دمج الأجزاء."""
        logger.info("بدء اختبار إزالة البسملة والعناوين المكررة...")
        
        parts_dir = self.test_workspace / "merge_parts"
        parts_dir.mkdir()
        
        # إنشاء ميتادات محاكاة وملفي أجزاء ملخصة
        meta = {
            "source": "dummy.txt",
            "total_words": 100,
            "parts_count": 2,
            "max_words_per_part": 50,
            "parts": [
                {"file": "dummy_part_01.md", "words": 50},
                {"file": "dummy_part_02.md", "words": 50}
            ]
        }
        with open(parts_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f)
            
        p1 = parts_dir / "dummy_part_01_summary.md"
        p1.write_text(
            "[تعليمات التلخيص - الجزء 1 من 2]\n---\n"
            "بسم الله الرحمن الرحيم.\n"
            "شرح كتاب الأصول الثلاثة:\n"
            "الملخص الأول هنا.",
            encoding="utf-8"
        )
        
        p2 = parts_dir / "dummy_part_02_summary.md"
        p2.write_text(
            "[تعليمات التلخيص - الجزء 2 من 2]\n---\n"
            "بسم الله الرحمن الرحيم.\n"
            "شرح كتاب الأصول الثلاثة:\n"
            "الملخص الثاني هنا.",
            encoding="utf-8"
        )
        
        output_summary = self.test_workspace / "final_summary.md"
        cs.process_single_dir(parts_dir, str(output_summary), strip_prompts=True, clean=False)
        
        content = output_summary.read_text(encoding="utf-8")
        # البسملة والعنوان يجب ألا يظهرا سوى مرة واحدة فقط
        self.assertEqual(content.count("بسم الله الرحمن الرحيم."), 1)
        self.assertEqual(content.count("شرح كتاب الأصول الثلاثة:"), 1)
        self.assertNotIn("[تعليمات التلخيص", content)

    def test_compile_mode_chapter_sorting_and_deduplication(self):
        """التحقق من الفرز الحسابي للفصول وتطهير البسملة والعناوين المكررة."""
        logger.info("بدء اختبار تجميع الفصول مع الترتيب الحسابي الذكي...")
        
        compile_dir = self.test_workspace / "compile_chapters"
        compile_dir.mkdir()
        
        # كتابة ملفات الفصل 2، الفصل 1، والفصل 10
        f2 = compile_dir / "chap_02.md"
        f2.write_text("بسم الله الرحمن الرحيم.\nكتاب الفوائد:\n(الفصل الثاني)\nمحتوى الفصل الثاني.", encoding="utf-8")
        
        f1 = compile_dir / "chap_01.md"
        f1.write_text("بسم الله الرحمن الرحيم.\nكتاب الفوائد:\n(الفصل الأول)\nمحتوى الفصل الأول.", encoding="utf-8")
        
        f3 = compile_dir / "chap_10.md"
        f3.write_text("بسم الله الرحمن الرحيم.\nكتاب الفوائد:\n(الفصل العاشر)\nمحتوى الفصل العاشر.", encoding="utf-8")
        
        output_file = self.test_workspace / "كتاب_الفوائد_مجمع.md"
        cs.compile_summaries(compile_dir, output_file, anthology=False)
        
        content = output_file.read_text(encoding="utf-8")
        
        # التأكد من الترتيب الرقمي السليم (الفصل العاشر يأتي بعد الثاني)
        idx1 = content.find("الفصل الأول")
        idx2 = content.find("الفصل الثاني")
        idx10 = content.find("الفصل العاشر")
        self.assertTrue(idx1 < idx2 < idx10)
        
        # البسملة وعنوان الكتاب الرئيسي يظهران مرة واحدة فقط
        self.assertEqual(content.count("بسم الله الرحمن الرحيم."), 1)
        self.assertEqual(content.count("كتاب الفوائد:"), 1)

    def test_compile_mode_anthology(self):
        """التحقق من تجميع التلخيصات بنمط المجموع (Anthology Mode)."""
        logger.info("بدء اختبار التجميع بنمط المجموع...")
        
        compile_dir = self.test_workspace / "anthology_dir"
        compile_dir.mkdir()
        
        f1 = compile_dir / "resala_01.md"
        f1.write_text("بسم الله الرحمن الرحيم.\nالرسالة الأولى:\nمحتوى الرسالة الأولى.", encoding="utf-8")
        
        f2 = compile_dir / "resala_02.md"
        f2.write_text("بسم الله الرحمن الرحيم.\nالرسالة الثانية:\nمحتوى الرسالة الثانية.", encoding="utf-8")
        
        output_file = self.test_workspace / "مجموع_رسائل.md"
        cs.compile_summaries(compile_dir, output_file, anthology=True)
        
        content = output_file.read_text(encoding="utf-8")
        
        # في نمط المجموع، يتم الحفاظ على البسملة والعناوين المستقلة لجميع الرسائل
        self.assertEqual(content.count("بسم الله الرحمن الرحيم."), 3) # المقدمة العامة + رسالتين
        self.assertIn("الرسالة الأولى:", content)
        self.assertIn("الرسالة الثانية:", content)
        self.assertIn("---", content)

    def test_split_text_cli_execution(self):
        """التحقق من سلامة تشغيل واجهة CLI لسكربت split_text.py عبر subprocess."""
        logger.info("بدء اختبار تشغيل واجهة CLI لسكربت التقسيم...")
        
        output_dir = self.test_workspace / "cli_parts"
        cmd = [
            sys.executable,
            str(BASE_DIR / "split_text.py"),
            str(self.sample_txt),
            "-o", str(output_dir),
            "--max-words", "25",
            "-f"
        ]
        
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0)
        self.assertTrue((output_dir / "metadata.json").exists())

    def test_compile_summaries_cli_execution(self):
        """التحقق من سلامة تشغيل واجهة CLI لسكربت compile_summaries.py عبر subprocess."""
        logger.info("بدء اختبار تشغيل واجهة CLI لسكربت التجميع والدمج الموحد...")
        
        # 1. تقسيم النص أولاً للحصول على أجزاء للدمج
        parts_dir = self.test_workspace / "cli_merge_parts"
        split_text(self.sample_txt, parts_dir, max_words=25, force=True)
        
        # محاكاة التلخيص بكتابة ملفات تلخيص الأجزاء
        for f in parts_dir.glob("*_part_*.md"):
            summary_f = f.parent / f.name.replace(".md", "_summary.md")
            summary_f.write_text(
                "بسم الله الرحمن الرحيم.\n"
                "كتاب التوحيد وشروحه:\n"
                f"تلخيص الجزء {f.name}:\n"
                "محتوى التلخيص الفرعي.",
                encoding="utf-8"
            )
            
        # 2. تشغيل السكربت الموحد عبر CLI لدمج الأجزاء
        final_summary = self.test_workspace / "cli_merged_final.md"
        cmd = [
            sys.executable,
            str(BASE_DIR / "compile_summaries.py"),
            str(parts_dir),
            "-o", str(final_summary),
            "--mode", "merge",
            "-c"
        ]
        
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0)
        self.assertTrue(final_summary.exists())
        # خيار -c / --clean يجب أن يمسح مجلد الأجزاء
        self.assertFalse(parts_dir.exists())


if __name__ == "__main__":
    unittest.main()
