#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
حزمة اختبارات شاملة لمهارة التلخيص العام والمحاكاة الأسلوبية وسكربتاتها المساعدة.
تتحقق الاختبارات من سلوكيات التقسيم، والاستئناف بالبصمات، والدمج، وفحص الجودة، وتكامل سطر الأوامر (CLI).
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
SCRIPTS_DIR = BASE_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import compile_summaries as cs  # noqa: E402
from split_text import (  # noqa: E402
    count_words,
    find_split_point,
    read_file_with_fallback_encoding as split_read_encoding,
    split_long_line,
    split_text,
)


class TestSummarizationSkill(unittest.TestCase):
    """حزمة الاختبارات السلوكية لمهارة التلخيص وسكربتاتها وفق معايير test-guard."""

    def setUp(self):
        """تهيئة بيئة اختبار معزولة ونظيفة داخل مجلد مؤقت مستقل."""
        self.test_workspace = BASE_DIR / "test_run_workspace"
        self.test_workspace.mkdir(exist_ok=True)

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
        """تطهير وإزالة بيئة الاختبار المعزولة لضمان نقاء مساحة العمل."""
        if self.test_workspace.exists():
            shutil.rmtree(self.test_workspace, ignore_errors=True)

    def test_word_count_with_arabic_and_english_returns_accurate_totals(self):
        """فحص دقة عد الكلمات للنصوص العربية والإنجليزية."""
        self.assertEqual(count_words("الحمد لله رب العالمين"), 4)
        self.assertEqual(count_words("Hello world from python test suite"), 6)

    def test_encoding_fallback_with_cp1256_and_utf8_reads_successfully(self):
        """التحقق من عمل نظام قراءة الملفات بترميز UTF-8 و CP1256."""
        utf8_file = self.test_workspace / "utf8.txt"
        utf8_file.write_text("نص بترميز يوتيف", encoding="utf-8")
        self.assertIn("يوتيف", split_read_encoding(utf8_file))

        cp1256_file = self.test_workspace / "cp1256.txt"
        cp1256_file.write_text("نص بترميز ويندوز", encoding="cp1256")
        self.assertIn("ويندوز", split_read_encoding(cp1256_file))

    def test_split_long_line_with_multiple_sentences_preserves_text_and_splits(self):
        """التحقق من تجزئة السطور الطويلة جداً دون فقدان أي حرف أو مسافة."""
        long_line = "جملة أولى. جملة ثانية؟ جملة ثالثة! جملة رابعة"
        segments = split_long_line(long_line, max_words=2)
        self.assertTrue(len(segments) >= 3)
        self.assertEqual("".join(segments), long_line)

    def test_find_split_point_with_paragraph_boundary_prefers_paragraph(self):
        """التحقق من أولويات نقاط القطع عند حدود الفقرات."""
        text = "سطر أول كلمة كلمة كلمة.\n\nسطر ثان كلمة كلمة كلمة."
        split_idx = find_split_point(text, max_words=6)
        self.assertEqual(text[:split_idx].strip(), "سطر أول كلمة كلمة كلمة.")

    def test_find_split_point_with_tables_and_code_avoids_inner_splits(self):
        """التحقق من تجنب القطع العشوائي داخل الجداول والكتل البرمجية."""
        table_text = (
            "البداية هنا.\n"
            "| العمود الأول | العمود الثاني |\n"
            "|---|---|\n"
            "| خلية 1 | خلية 2 |\n"
            "هذا سطر بعد الجدول.\n"
            "النهاية هنا."
        )
        split_idx_small = find_split_point(table_text, max_words=5)
        self.assertEqual(split_idx_small, table_text.find("| العمود الأول"))

        split_idx_large = find_split_point(table_text, max_words=20)
        self.assertTrue(split_idx_large > table_text.find("| خلية 1 | خلية 2 |"))

        code_text = (
            "البداية هنا.\n"
            "```python\n"
            "def foo():\n"
            "    print('hello')\n"
            "```\n"
            "النهاية هنا."
        )
        split_idx_code = find_split_point(code_text, max_words=6)
        self.assertEqual(split_idx_code, code_text.find("```python"))

    def test_split_text_with_single_file_creates_parts_and_valid_metadata(self):
        """التحقق من تقسيم ملف مفرد وإنشاء ملف metadata.json السليم."""
        output_dir = self.test_workspace / "parts"
        split_text(self.sample_txt, output_dir, max_words=25, force=True, min_words=5)

        metadata_file = output_dir / "metadata.json"
        self.assertTrue(metadata_file.exists())
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

        self.assertEqual(metadata["total_words"], count_words(self.sample_content))
        self.assertEqual(metadata["min_words_for_new_part"], 5)
        self.assertIn("source_fingerprint", metadata)
        self.assertTrue(metadata["parts_count"] > 1)

        first_part = output_dir / metadata["parts"][0]["file"]
        self.assertTrue(first_part.exists())
        self.assertIn(
            "[تعليمات التلخيص - الجزء 1 من", first_part.read_text(encoding="utf-8")
        )

    def test_split_text_with_existing_valid_parts_skips_reprocessing(self):
        """التحقق من آلية الاستئناف وتخطي تكرار التقسيم عند مطابقة الأصل."""
        output_dir = self.test_workspace / "checkpoint_parts"
        split_text(self.sample_txt, output_dir, max_words=25, force=True, min_words=5)

        meta = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
        first_part = output_dir / meta["parts"][0]["file"]
        orig_mtime = first_part.stat().st_mtime

        split_text(self.sample_txt, output_dir, max_words=25, force=False, min_words=5)
        self.assertEqual(first_part.stat().st_mtime, orig_mtime)

    def test_split_text_checkpoint_with_content_change_updates_fingerprint(self):
        """التحقق من أن بصمة الاستئناف تكشف تغير المحتوى ولو بقي عدد الكلمات متطابقاً."""
        source = self.test_workspace / "stale_source.txt"
        source.write_text("كلمة أولى. كلمة ثانية. كلمة ثالثة.", encoding="utf-8")
        output_dir = self.test_workspace / "stale_parts"
        split_text(source, output_dir, max_words=2, force=True, min_words=1)

        old_meta = json.loads(
            (output_dir / "metadata.json").read_text(encoding="utf-8")
        )
        old_hash = old_meta["source_fingerprint"]["sha256"]

        source.write_text("عبارة بديلة. كلمة ثانية. كلمة ثالثة.", encoding="utf-8")
        split_text(source, output_dir, max_words=2, force=False, min_words=1)

        new_meta = json.loads(
            (output_dir / "metadata.json").read_text(encoding="utf-8")
        )
        self.assertNotEqual(new_meta["source_fingerprint"]["sha256"], old_hash)

    def test_split_text_with_empty_or_whitespace_file_handles_gracefully(self):
        """التحقق من معالجة الملفات الفارغة دون انهيار العملية."""
        empty_file = self.test_workspace / "empty.txt"
        empty_file.write_text("   \n\n  ", encoding="utf-8")
        out_dir = self.test_workspace / "empty_parts"
        split_text(empty_file, out_dir, max_words=10, force=True, min_words=2)

        self.assertTrue((out_dir / "metadata.json").exists())
        meta = json.loads((out_dir / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["parts_count"], 1)

    def test_merge_files_with_multiple_parts_deduplicates_bismillah_and_title(self):
        """التحقق من إزالة البسملة والعناوين المكررة عند دمج الأجزاء."""
        parts_dir = self.test_workspace / "merge_parts"
        parts_dir.mkdir()
        meta = {
            "source": "dummy.txt",
            "total_words": 100,
            "parts_count": 2,
            "max_words_per_part": 50,
            "parts": [
                {"file": "dummy_part_01.md", "words": 50},
                {"file": "dummy_part_02.md", "words": 50},
            ],
        }
        (parts_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")

        p1 = (
            "[تعليمات التلخيص - الجزء 1 من 2]\n---\n"
            "بسم الله الرحمن الرحيم.\n"
            "شرح كتاب الأصول الثلاثة:\n"
            "الملخص الأول هنا."
        )
        p2 = (
            "[تعليمات التلخيص - الجزء 2 من 2]\n---\n"
            "بسم الله الرحمن الرحيم.\n"
            "شرح كتاب الأصول الثلاثة:\n"
            "الملخص الثاني هنا."
        )
        (parts_dir / "dummy_part_01_summary.md").write_text(p1, encoding="utf-8")
        (parts_dir / "dummy_part_02_summary.md").write_text(p2, encoding="utf-8")

        output_summary = self.test_workspace / "final_summary.md"
        cs.process_single_dir(parts_dir, str(output_summary), clean=False)

        content = output_summary.read_text(encoding="utf-8")
        self.assertEqual(content.count("بسم الله الرحمن الرحيم."), 1)
        self.assertEqual(content.count("شرح كتاب الأصول الثلاثة:"), 1)
        self.assertNotIn("[تعليمات التلخيص", content)

    def test_merge_files_with_later_part_preserves_internal_heading_indent(self):
        """التحقق من حفظ ترويسات العناوين الداخلية للأجزاء اللاحقة."""
        parts_dir = self.test_workspace / "merge_heading_parts"
        parts_dir.mkdir()
        (parts_dir / "metadata.json").write_text(
            json.dumps({"parts_count": 2}), encoding="utf-8"
        )
        (parts_dir / "dummy_part_01_summary.md").write_text(
            "بسم الله الرحمن الرحيم.\n# شرح كتاب الاختبار:\n## المقدمة:\nنص أول.",
            encoding="utf-8",
        )
        (parts_dir / "dummy_part_02_summary.md").write_text(
            "بسم الله الرحمن الرحيم.\n# شرح كتاب الاختبار:\n## العنوان الثاني:\nنص ثان.",
            encoding="utf-8",
        )

        output_summary = self.test_workspace / "heading_summary.md"
        cs.process_single_dir(parts_dir, str(output_summary), clean=False)
        self.assertIn(
            "\n## العنوان الثاني:", output_summary.read_text(encoding="utf-8")
        )

    def test_merge_files_without_summary_files_logs_and_skips(self):
        """التحقق من عدم إنشاء ملف مخرج عند غياب ملفات التلخيص."""
        parts_dir = self.test_workspace / "merge_raw_parts"
        parts_dir.mkdir()
        (parts_dir / "dummy_part_01.md").write_text("نص خام", encoding="utf-8")
        out_summary = self.test_workspace / "raw_out.md"
        cs.process_single_dir(parts_dir, str(out_summary), clean=False)
        self.assertFalse(out_summary.exists())

    def test_clean_flag_deletes_parts_dir_and_preserves_non_parts_dir(self):
        """التحقق من حذف المجلد المنتهي بـ _parts والإبقاء على ما سواه عند تفعيل التنظيف."""
        parts_dir = self.test_workspace / "merge_delete_parts"
        parts_dir.mkdir()
        (parts_dir / "dummy_part_01_summary.md").write_text(
            "بسم الله الرحمن الرحيم.\n# شرح كتاب الاختبار:\n## باب:\nنص.",
            encoding="utf-8",
        )
        out1 = self.test_workspace / "out1.md"
        cs.process_single_dir(parts_dir, str(out1), clean=True)
        self.assertFalse(parts_dir.exists())

        safe_dir = self.test_workspace / "other_folder"
        safe_dir.mkdir()
        (safe_dir / "dummy_part_01_summary.md").write_text(
            "بسم الله الرحمن الرحيم.\n# شرح كتاب الاختبار:\n## باب:\nنص.",
            encoding="utf-8",
        )
        out2 = self.test_workspace / "out2.md"
        cs.process_single_dir(safe_dir, str(out2), clean=True)
        self.assertTrue(safe_dir.exists())

    def test_audit_summary_text_with_flawed_text_reports_all_issues(self):
        """التحقق من كشف ملاحظات التنسيق الأساسية عند وجود عيوب هيكلية حقيقية."""
        bad_text = (
            "مقدمة غير مسبوقة بالبسملة:\n"
            "[تعليمات التلخيص - الجزء 1 من 1]\n"
            "جملة أولى. جملة ثانية.\n"
            "وتحدث الشيخ عن باقي المباحث...\n"
        )
        issues = cs.audit_summary_text(bad_text)
        self.assertTrue(any("البسملة" in issue for issue in issues))
        self.assertTrue(any("تعليمات التلخيص" in issue for issue in issues))
        self.assertTrue(any("استمرار بعد نقطة" in issue for issue in issues))
        self.assertTrue(any("علامات حذف" in issue for issue in issues))

    def test_audit_summary_text_with_clean_valid_summary_returns_no_issues(self):
        """التحقق من أن التلخيص المستوفي لكافة الضوابط يجتاز الفحص دون ملاحظات."""
        valid_text = (
            "بسم الله الرحمن الرحيم.\n"
            "# شرح كتاب التوحيد للشيخ فلان:\n"
            "## الباب الأول في فضيلة التوحيد:\n"
            "• الفائدة الأولى.\n"
            "1- الوجه الأول.\n"
            "وهو إفراد الله بالعبادة.\n"
        )
        issues = cs.audit_summary_text(valid_text)
        self.assertEqual(issues, [])

    def test_audit_summary_text_permits_tab_indentation_and_discourse_markers(self):
        """التحقق من قبول مسافة Tab في العناوين والفوائد الإثرائية وعبارات التوجيه البياني."""
        tabbed_text = (
            "بسم الله الرحمن الرحيم.\n"
            "# شرح كتاب التوحيد:\n"
            "\tفوائد إثرائية:\n"
            "• الفائدة الأولى.\n"
            "وجه الدلالة:\n"
            "أن الشرك محبط للعمل.\n"
        )
        self.assertEqual(cs.audit_summary_text(tabbed_text), [])

    def test_audit_summary_text_tolerates_quranic_citations_and_multiple_bismillah_in_body(
        self,
    ):
        """التحقق من قبول عزو الآيات القرآنية مثل [2:255] وورود البسملة داخل نصوص الاقتباس."""
        text_with_verses = (
            "بسم الله الرحمن الرحيم.\n"
            "# تفسير آيات الأحكام:\n"
            "• في سورة البقرة [2:255] بيان آية الكرسي.\n"
            "• كتب النبي صلى الله عليه وسلم: «بسم الله الرحمن الرحيم. من محمد رسول الله».\n"
            "• انظر المسألة في المرجع (1:15).\n"
        )
        self.assertEqual(cs.audit_summary_text(text_with_verses), [])

    def test_audit_summary_text_tolerates_natural_arabic_prose_and_citations(self):
        """التحقق من عدم اعتراض السكربت تعسفاً على النثر الطبيعي والشواهد القرآنية والاختصارات."""
        natural_text = (
            "بسم الله الرحمن الرحيم.\n"
            "# مدارسة سورة هود للشيخ فلان\n"
            "## الباب الأول:\n"
            "قال تعالى:\n"
            "{أَلاَّ تَعْبُدُوا إِلاَّ اللَّهَ... وَإِن تَوَلَّوْا فَإِنِّي أَخَافُ}.\n"
            "م: تصريف وجوه إثبات البعث في القرآن:\n"
            "• الفائدة الأولى في ص. 15 من الكتاب.\n"
            "هذه الكلمات تدور حول حقيقة واحدة؛ وهي الإسلام لله واتباع هدي رسله:\n"
            "1- التوحيد الخالص.\n"
        )
        issues = cs.audit_summary_text(natural_text)
        self.assertEqual(issues, [])

    def test_split_text_cli_with_valid_file_exits_zero_and_creates_parts(self):
        """التحقق من سلامة تشغيل واجهة CLI لسكربت split_text.py."""
        output_dir = self.test_workspace / "cli_parts"
        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "split_text.py"),
            str(self.sample_txt),
            "-o",
            str(output_dir),
            "--max-words",
            "25",
            "--min-words",
            "5",
            "-f",
        ]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        self.assertEqual(res.returncode, 0)
        self.assertTrue((output_dir / "metadata.json").exists())

    def test_compile_summaries_cli_with_parts_dir_merges_and_cleans_parts(self):
        """التحقق من سلامة تشغيل واجهة CLI لدمج الأجزاء وتنظيف المجلد المؤقت."""
        parts_dir = self.test_workspace / "cli_merge_parts"
        split_text(self.sample_txt, parts_dir, max_words=25, force=True, min_words=5)

        for f in parts_dir.glob("*_part_*.md"):
            summary_f = f.parent / f.name.replace(".md", "_summary.md")
            summary_f.write_text(
                f"بسم الله الرحمن الرحيم.\nكتاب التوحيد وشروحه:\nتلخيص الجزء {f.name}:\nمحتوى التلخيص الفرعي.",
                encoding="utf-8",
            )

        final_summary = self.test_workspace / "cli_merged_final.md"
        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "compile_summaries.py"),
            str(parts_dir),
            "-o",
            str(final_summary),
            "-c",
        ]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        self.assertEqual(res.returncode, 0)
        self.assertTrue(final_summary.exists())
        self.assertFalse(parts_dir.exists())


if __name__ == "__main__":
    unittest.main()
