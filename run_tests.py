#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ملف اختبارات مشروع تلخيص النصوص الطويلة وتجميع الكتب بالكامل.
يتضمن اختبارات شاملة لوظائف التقسيم، الدمج الفردي والدفعي، التجميع،
وأنماط التشغيل المختلفة والواجهات البرمجية وتكامل سطر الأوامر (CLI).
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# إعداد السجل تماشياً مع المعايير القياسية
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

# المجلد الأساسي للمشروع
BASE_DIR = Path(__file__).parent
TEST_ARTIFACT_PREFIXES = ("sample_text", "dummy", "large_book", "cli_", "merge_", "checkpoint_", "stale_")

# استيراد الوظائف مباشرة للفحص البرميجي بعد تهيئة مسار البحث
sys.path.insert(0, str(BASE_DIR / ".agents" / "skills" / "summarization_skill" / "scripts"))

from split_text import (
    count_words,
    read_file_with_fallback_encoding as split_read_encoding,
    split_long_line,
    find_split_point,
    split_text,
)
import compile_summaries as cs



class TestSummarizationSkill(unittest.TestCase):

    def clean_shared_test_artifacts(self):
        """تنظيف مخلفات الاختبارات من المجلدات المشتركة دون حذف ملفات المستخدم."""
        for folder in ["all_parts", "summaries"]:
            folder_path = BASE_DIR / folder
            if folder_path.exists():
                for item in sorted(folder_path.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                    if item.exists() and item.name.startswith(TEST_ARTIFACT_PREFIXES):
                        try:
                            if item.is_dir():
                                shutil.rmtree(item)
                            else:
                                item.unlink()
                        except Exception:
                            pass

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
            
        self.clean_shared_test_artifacts()
                
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
        split_text(self.sample_txt, output_dir, max_words=25, force=True, min_words=5)
        
        # فحص تولد الأجزاء وملف metadata.json
        metadata_file = output_dir / "metadata.json"
        self.assertTrue(metadata_file.exists())
        
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
        self.assertEqual(metadata["total_words"], count_words(self.sample_content))
        self.assertEqual(metadata["min_words_for_new_part"], 5)
        self.assertIn("source_fingerprint", metadata)
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
        split_text(self.sample_txt, output_dir, max_words=25, force=True, min_words=5)
        
        # حفظ تاريخ تعديل الملف الأول
        metadata_file = output_dir / "metadata.json"
        with open(metadata_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        first_part_path = output_dir / meta["parts"][0]["file"]
        orig_mtime = first_part_path.stat().st_mtime
        
        # تشغيل التقسيم مرة أخرى بدون خيار force
        split_text(self.sample_txt, output_dir, max_words=25, force=False, min_words=5)
        self.assertEqual(first_part_path.stat().st_mtime, orig_mtime)
        
        # تشغيل التقسيم مرة أخرى مع خيار force
        # ننتظر قليلاً للتأكد من تغير الوقت المتاح بالنظام
        import time
        time.sleep(0.1)
        split_text(self.sample_txt, output_dir, max_words=25, force=True, min_words=5)
        self.assertNotEqual(first_part_path.stat().st_mtime, orig_mtime)

    def test_split_text_checkpoint_detects_same_word_count_change(self):
        """التحقق من أن البصمة تكشف تغير المحتوى ولو بقي عدد الكلمات كما هو."""
        logger.info("بدء اختبار بصمة الاستئناف عند تساوي عدد الكلمات...")

        source = self.test_workspace / "stale_source.txt"
        source.write_text("كلمة أولى. كلمة ثانية. كلمة ثالثة.", encoding="utf-8")
        output_dir = self.test_workspace / "stale_parts"
        split_text(source, output_dir, max_words=2, force=True, min_words=1)

        metadata_file = output_dir / "metadata.json"
        with open(metadata_file, "r", encoding="utf-8") as f:
            old_meta = json.load(f)
        old_hash = old_meta["source_fingerprint"]["sha256"]

        source.write_text("عبارة بديلة. كلمة ثانية. كلمة ثالثة.", encoding="utf-8")
        split_text(source, output_dir, max_words=2, force=False, min_words=1)

        with open(metadata_file, "r", encoding="utf-8") as f:
            new_meta = json.load(f)
        self.assertNotEqual(new_meta["source_fingerprint"]["sha256"], old_hash)

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

    def test_merge_preserves_tabbed_heading_from_later_parts(self):
        """التحقق من حفظ Tab في أول عنوان داخلي للجزء الثاني بعد الدمج."""
        parts_dir = self.test_workspace / "merge_tab_parts"
        parts_dir.mkdir()
        (parts_dir / "metadata.json").write_text(json.dumps({"parts_count": 2}, ensure_ascii=False), encoding="utf-8")
        (parts_dir / "dummy_part_01_summary.md").write_text(
            "بسم الله الرحمن الرحيم.\nشرح كتاب الاختبار:\n\tالمقدمة:\nنص أول.",
            encoding="utf-8",
        )
        (parts_dir / "dummy_part_02_summary.md").write_text(
            "بسم الله الرحمن الرحيم.\nشرح كتاب الاختبار:\n\tالعنوان الثاني:\nنص ثان.",
            encoding="utf-8",
        )

        output_summary = self.test_workspace / "tabbed_summary.md"
        cs.process_single_dir(parts_dir, str(output_summary), strip_prompts=True, clean=False)

        content = output_summary.read_text(encoding="utf-8")
        self.assertIn("\n\tالعنوان الثاني:", content)

    def test_merge_requires_summary_files_by_default(self):
        """التحقق من منع دمج الأجزاء الأصلية raw بطريق الخطأ."""
        parts_dir = self.test_workspace / "merge_raw_parts"
        parts_dir.mkdir()
        (parts_dir / "metadata.json").write_text("{}", encoding="utf-8")
        (parts_dir / "dummy_part_01.md").write_text("نص خام", encoding="utf-8")

        with self.assertRaises(ValueError):
            cs.process_single_dir(parts_dir, str(self.test_workspace / "raw.md"), strip_prompts=True, clean=False)

    def test_merge_updates_metadata(self):
        """التحقق من تحديث الميتادات بعد الدمج الناجح."""
        parts_dir = self.test_workspace / "merge_meta_parts"
        parts_dir.mkdir()
        (parts_dir / "metadata.json").write_text(json.dumps({"merged_output": None, "merged_words": None}, ensure_ascii=False), encoding="utf-8")
        (parts_dir / "dummy_part_01_summary.md").write_text(
            "بسم الله الرحمن الرحيم.\nشرح كتاب الاختبار:\n\tباب:\nنص.",
            encoding="utf-8",
        )

        output_summary = self.test_workspace / "meta_summary.md"
        cs.process_single_dir(parts_dir, str(output_summary), strip_prompts=True, clean=False)
        metadata = json.loads((parts_dir / "metadata.json").read_text(encoding="utf-8"))

        self.assertEqual(metadata["merged_output"], str(output_summary))
        self.assertIsInstance(metadata["merged_words"], int)
        self.assertIn("merged_at", metadata)

    def test_clean_does_not_delete_arbitrary_parent_folder(self):
        """التحقق من أن خيار التنظيف لا يحذف مجلداً خارج all_parts."""
        parts_dir = self.test_workspace / "merge_safe_parts"
        parts_dir.mkdir()
        (parts_dir / "metadata.json").write_text("{}", encoding="utf-8")
        (parts_dir / "dummy_part_01_summary.md").write_text(
            "بسم الله الرحمن الرحيم.\nشرح كتاب الاختبار:\n\tباب:\nنص.",
            encoding="utf-8",
        )
        output_summary = self.test_workspace / "safe_summary.md"

        cs.process_single_dir(parts_dir, str(output_summary), strip_prompts=True, clean=True)

        self.assertTrue(parts_dir.exists())
        self.assertTrue(output_summary.exists())

    def test_teardown_keeps_existing_summaries(self):
        """التحقق من أن تنظيف الاختبارات لا يحذف ملخصات مستخدم غير مملوكة للاختبار."""
        summaries_dir = BASE_DIR / "summaries"
        summaries_dir.mkdir(exist_ok=True)
        user_file = summaries_dir / "__user_cleanup_guard_do_not_delete__.md"
        suffix = 1
        while user_file.exists():
            user_file = summaries_dir / f"__user_cleanup_guard_do_not_delete_{suffix}.md"
            suffix += 1
        test_file = summaries_dir / "sample_text_cleanup_probe.md"
        user_file.write_text("ملف مستخدم", encoding="utf-8")
        test_file.write_text("ملف اختبار", encoding="utf-8")
        self.addCleanup(lambda: user_file.exists() and user_file.unlink())

        self.clean_shared_test_artifacts()

        self.assertTrue(user_file.exists())
        self.assertFalse(test_file.exists())

    def test_audit_summary_text_reports_format_issues(self):
        """التحقق من فحص التنسيق للحالات الأساسية."""
        bad_text = (
            "بسم الله الرحمن الرحيم.\n"
            "بسم الله الرحمن الرحيم.\n"
            "شرح كتاب الاختبار:\n"
            "[تعليمات التلخيص - الجزء 1 من 1]\n"
            "عنوان داخلي:\n"
            "جملة أولى. جملة ثانية.\n"
            "00:12\n"
        )
        issues = cs.audit_summary_text(bad_text)
        self.assertTrue(any("البسملة" in issue for issue in issues))
        self.assertTrue(any("تعليمات التلخيص" in issue for issue in issues))
        self.assertTrue(any("Tab" in issue for issue in issues))
        self.assertTrue(any("استمرار بعد نقطة" in issue for issue in issues))
        self.assertTrue(any("طابع زمني" in issue for issue in issues))

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
            str(BASE_DIR / ".agents" / "skills" / "summarization_skill" / "scripts" / "split_text.py"),
            str(self.sample_txt),
            "-o", str(output_dir),
            "--max-words", "25",
            "--min-words", "5",
            "-f"
        ]
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        self.assertEqual(res.returncode, 0)
        self.assertTrue((output_dir / "metadata.json").exists())

    def test_compile_summaries_cli_execution(self):
        """التحقق من سلامة تشغيل واجهة CLI لسكربت compile_summaries.py عبر subprocess."""
        logger.info("بدء اختبار تشغيل واجهة CLI لسكربت التجميع والدمج الموحد...")
        
        # 1. تقسيم النص أولاً للحصول على أجزاء للدمج
        parts_dir = BASE_DIR / "all_parts" / "cli_merge_parts"
        if parts_dir.exists():
            shutil.rmtree(parts_dir)
        split_text(self.sample_txt, parts_dir, max_words=25, force=True, min_words=5)
        
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
            str(BASE_DIR / ".agents" / "skills" / "summarization_skill" / "scripts" / "compile_summaries.py"),
            str(parts_dir),
            "-o", str(final_summary),
            "--mode", "merge",
            "-c"
        ]
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        self.assertEqual(res.returncode, 0)
        self.assertTrue(final_summary.exists())
        # خيار -c / --clean يجب أن يمسح مجلد الأجزاء
        self.assertFalse(parts_dir.exists())


if __name__ == "__main__":
    unittest.main()
