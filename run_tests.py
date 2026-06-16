#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ملف اختبارات المشروع بالكامل من الصفر.
يفحص سيناريوهات التقسيم، الدمج الفردي والدفعي، التجميع، ونمط المجموع،
مفترضاً السلوك الطبيعي للسكربتات بحفظ المخرجات في مجلد المهارة (مساحة العمل).
"""

import json
import logging
import re
import shutil
import sys
import unittest
from pathlib import Path

# إعداد السجل
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

# المجلد الأساسي للمشروع
BASE_DIR = Path(__file__).parent

# استيراد الوظائف مباشرة للفحص الوظيفي
from split_text import split_text, count_words
import compile_summaries as cs


class TestSummarizationSkill(unittest.TestCase):
    
    def setUp(self):
        """تجهيز بيئة معزولة للاختبارات داخل مجلد المهارة."""
        self.test_dir = BASE_DIR / "test_run_workspace"
        self.test_dir.mkdir(exist_ok=True)
        
        # حماية وتخزين المسارات الحقيقية لإعادة توجيهها للاختبارات
        self.orig_all_parts = BASE_DIR / "all_parts"
        self.orig_summaries = BASE_DIR / "summaries"
        
        # إنشاء ملف نصي طويل للاختبار
        self.large_file = self.test_dir / "large_book.txt"
        self.large_text = (
            "بسم الله الرحمن الرحيم.\n"
            "شرح كتاب أصول الإيمان:\n"
            "• الفائدة الأولى: الإيمان بوجود الله تعالى.\n"
            "وهو الفطرة التي جبل الله عليها عباده.\n"
            "وليس كمثله شيء وهو السميع البصير.\n\n"
            "• الفائدة الثانية: الإيمان بكتبه ورسله.\n"
            "1- الكتب المنزلة من السماء هداية للبشر.\n"
            "2- الرسل مبشرون ومنذرون لئلا يكون للناس على الله حجة.\n"
            "وهذا الدين القيم هو صراط الله المستقيم.\n\n"
            "• الفائدة الثالثة: الإيمان باليوم الآخر.\n"
            "وهو دار الجزاء والحساب بعد الموت.\n"
        )
        self.large_file.write_text(self.large_text, encoding="utf-8")

    def tearDown(self):
        """تنظيف مجلدات الاختبارات بالكامل بعد كل تشغيل."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
        # تنظيف مجلدات المخرجات المخصصة للاختبارات لضمان بقاء مساحة العمل نظيفة
        for folder in ["all_parts", "summaries"]:
            folder_path = BASE_DIR / folder
            if folder_path.exists():
                shutil.rmtree(folder_path)
                
        # إزالة أي ملف مجمع ناتج
        for f in BASE_DIR.glob("*.md"):
            if "شرح_كتاب" in f.name or "كتاب_ملخصات" in f.name or "مجموع_رسائل" in f.name:
                f.unlink()

    def test_large_file_splits_into_correct_parts(self):
        """اختبار تقسيم ملف مفرد وتوزيع الأجزاء في مجلد المهارة."""
        logger.info("بدء اختبار تقسيم ملف مفرد...")
        
        # تشغيل التقسيم بحد أقصى 20 كلمة للجزء
        output_dir = BASE_DIR / "all_parts" / "large_book_parts"
        split_text(self.large_file, output_dir, max_words=20, force=True)
        
        # التحقق من إنشاء مجلد الأجزاء والملفات
        self.assertTrue(output_dir.exists(), "فشل إنشاء مجلد الأجزاء")
        
        # قراءة الميتادات والتحقق من صحتها
        metadata_file = output_dir / "metadata.json"
        self.assertTrue(metadata_file.exists(), "فشل إنشاء ملف الميتادات")
        
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
        self.assertEqual(metadata["total_words"], count_words(self.large_text))
        self.assertTrue(metadata["parts_count"] > 1, "لم يتم تقسيم النص إلى أجزاء متعددة")
        
        # فحص وجود الملفات المرقمة
        for part in metadata["parts"]:
            part_path = output_dir / part["file"]
            self.assertTrue(part_path.exists(), f"الملف المفرز {part['file']} غير موجود")
            part_content = part_path.read_text(encoding="utf-8")
            self.assertTrue("[تعليمات التلخيص - الجزء" in part_content, "البرومبت المساعد غير مدمج في الصدارة")

    def test_part_summaries_merge_and_clean_temp_dir(self):
        """اختبار دمج الأجزاء وتنظيفها وحفظ الملخص النهائي في مجلد summaries."""
        logger.info("بدء اختبار دمج الأجزاء الفردية مع خيار التنظيف...")
        
        # 1. تقسيم الملف
        output_dir = BASE_DIR / "all_parts" / "large_book_parts"
        split_text(self.large_file, output_dir, max_words=20, force=True)
        
        # 2. محاكاة تلخيص الأجزاء يدوياً بكتابة ملخص لكل جزء
        metadata_file = output_dir / "metadata.json"
        with open(metadata_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
            
        for idx, part in enumerate(meta["parts"]):
            part_path = output_dir / part["file"]
            # كتابة ملخص يحاكي أسلوب المهارة
            summary_path = part_path.with_name(part_path.stem + "_summary.md")
            summary_path.write_text(
                f"بسم الله الرحمن الرحيم.\n"
                f"شرح كتاب أصول الإيمان:\n"
                f"• تلخيص الجزء {idx+1}:\n"
                f"محتوى بليغ مقتضب {idx+1}.",
                encoding="utf-8"
            )
            
        # 3. تشغيل الدمج مع خيار التنظيف (clean=True)
        final_summary_file = BASE_DIR / "summaries" / "large_book_summary.md"
        cs.process_single_dir(output_dir, str(final_summary_file), strip_prompts=True, clean=True)
        
        # 4. التحقق من المخرجات
        self.assertTrue(final_summary_file.exists(), "لم يتم إنشاء ملف التلخيص المدمج النهائي")
        self.assertFalse(output_dir.exists(), "خيار التنظيف --clean لم يمسح مجلد الأجزاء المؤقت")
        
        # التحقق من أن البسملة والعنوان لم يتكررا سوى مرة واحدة
        content = final_summary_file.read_text(encoding="utf-8")
        self.assertEqual(content.count("بسم الله الرحمن الرحيم."), 1, "البسملة مكررة في الملف المدمج")
        self.assertEqual(content.count("شرح كتاب أصول الإيمان:"), 1, "العنوان مكرر في الملف المدمج")

    def test_compile_sorts_chapters_numerically_and_deduplicates(self):
        """اختبار تجميع الفصول المتعددة بالترتيب الحسابي وتنقية التكرارات."""
        logger.info("بدء اختبار تجميع الفصول والمستخلصات...")
        
        # 1. محاكاة وجود فصول مدمجة في مجلد summaries
        summaries_dir = BASE_DIR / "summaries"
        summaries_dir.mkdir(exist_ok=True)
        
        # كتابة 3 فصول بأرقام مبعثرة للتحقق من الترتيب الرقمي
        f2 = summaries_dir / "chapter_02_intro.md"
        f2.write_text("بسم الله الرحمن الرحيم.\nكتاب الفقه الميسر:\n(الفصل الثاني)\n• أحكام الطهارة والوضوء.", encoding="utf-8")
        
        f1 = summaries_dir / "chapter_01_intro.md"
        f1.write_text("بسم الله الرحمن الرحيم.\nكتاب الفقه الميسر:\n(الفصل الأول)\n• تعريف الفقه ومصادره الحاكمة.", encoding="utf-8")
        
        f3 = summaries_dir / "chapter_10_intro.md"
        f3.write_text("بسم الله الرحمن الرحيم.\nكتاب الفقه الميسر:\n(الفصل العاشر)\n• أحكام الحج والعمرة والزيارة.", encoding="utf-8")
        
        # 2. تشغيل التجميع
        compiled_file = BASE_DIR / "كتاب_الفقه_الميسر.md"
        cs.compile_summaries(summaries_dir, compiled_file, anthology=False)
        
        # 3. التحقق من التجميع
        self.assertTrue(compiled_file.exists(), "فشل تجميع ملف الفصول الموحد")
        
        compiled_content = compiled_file.read_text(encoding="utf-8")
        
        # التحقق من التطهير والفرز الرقمي الحسابي (الفصل 10 يظهر بعد الفصل 2)
        idx1 = compiled_content.find("الفصل الأول")
        idx2 = compiled_content.find("الفصل الثاني")
        idx3 = compiled_content.find("الفصل العاشر")
        
        self.assertTrue(idx1 < idx2 < idx3, "الترتيب الرقمي الذكي للفصول غير صحيح")
        self.assertEqual(compiled_content.count("بسم الله الرحمن الرحيم."), 1, "البسملة مكررة في التجميع")
        self.assertEqual(compiled_content.count("كتاب الفقه الميسر:"), 1, "العنوان الرئيسي مكرر في التجميع")

    def test_compile_anthology_preserves_independent_titles_and_bismillah(self):
        """اختبار تجميع التلخيصات بنمط المجموع (Anthology Mode)."""
        logger.info("بدء اختبار التجميع بنمط المجموع الموسوعي...")
        
        summaries_dir = BASE_DIR / "summaries"
        summaries_dir.mkdir(exist_ok=True)
        
        f1 = summaries_dir / "book_01.md"
        f1.write_text("بسم الله الرحمن الرحيم.\nكتاب التوحيد للشيخ محمد:\n• حقيقة التوحيد وأقسامه الثلاثة.", encoding="utf-8")
        
        f2 = summaries_dir / "book_02.md"
        f2.write_text("بسم الله الرحمن الرحيم.\nكتاب الأصول الثلاثة للشيخ محمد:\n• معرفة العبد ربه ودينه ونبيه.", encoding="utf-8")
        
        # تشغيل التجميع بنمط المجموع
        compiled_anthology = BASE_DIR / "مجموع_رسائل.md"
        cs.compile_summaries(summaries_dir, compiled_anthology, anthology=True)
        
        self.assertTrue(compiled_anthology.exists(), "فشل تجميع ملف المجموع")
        
        content = compiled_anthology.read_text(encoding="utf-8")
        
        # في نمط المجموع، يجب الحفاظ على بسملة وعنوان كل رسالة مستقلة
        self.assertEqual(content.count("بسم الله الرحمن الرحيم."), 3, "البسملة يجب أن تظهر 3 مرات في نمط المجموع (المقدمة الكلية + رسالتين)")
        self.assertTrue("كتاب التوحيد للشيخ محمد:" in content, "عنوان الرسالة الأولى مفقود")
        self.assertTrue("كتاب الأصول الثلاثة للشيخ محمد:" in content, "عنوان الرسالة الثانية مفقود")


if __name__ == "__main__":
    unittest.main()
