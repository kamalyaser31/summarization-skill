"""
سكربت دمج الأجزاء الملخصة في ملف واحد نهائي.
يقرأ ملفات التلخيص المرقمة بالترتيب ويدمجها في ملف موحد،
مع حذف تعليمات التلخيص (Prompt) من بداية كل جزء.
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

# نمط تعليمات التلخيص المراد حذفها من بداية كل جزء
# نستخدم \A لضمان المطابقة في بداية الملف حصراً تفادياً لحذف نصوص مشابهة في المتن
PROMPT_PATTERN = re.compile(
    r'\A\[تعليمات التلخيص.*?\]\s*.*?---\s*',
    re.DOTALL,
)


def read_file_with_fallback_encoding(file_path: Path) -> str:
    """
    قراءة الملف النصي مع محاولة استخدام عدة ترميزات شائعة.
    يُجرب السكربت ترميز UTF-8 أولاً تماشياً مع المعايير الحديثة، ثم يرتد إلى
    ترميز cp1256 العربي لبيئات Windows الشائعة لتفادي أخطاء فك الترميز.
    """
    encodings = ["utf-8", "utf-8-sig", "cp1256", "latin-1"]
    for enc in encodings:
        try:
            return file_path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"تعذر قراءة الملف {file_path} باستخدام الترميزات المتاحة.")


def strip_prompt(text: str) -> str:
    """حذف تعليمات التلخيص (Prompt) من بداية النص."""
    return PROMPT_PATTERN.sub('', text, count=1).strip()


def find_summary_files(input_dir: Path) -> list[Path]:
    """
    إيجاد ملفات التلخيص المرقمة في المجلد.
    يبحث أولاً عن ملفات الملخصات بالنمط *_part_NN_summary.md ويرتبها بالترتيب،
    فإن لم يجدها، يبحث بالنمط الافتراضي للأجزاء *_part_NN.md.
    ويتحقق بدقة من تسلسل الأرقام واكتمالها لعدم دمج ملفات ناقصة.
    """
    # نمط ملفات الملخصات وهو الأولوية الأولى
    summary_pattern = re.compile(r'_part_(\d+)_summary\.md$', re.IGNORECASE)
    # نمط ملفات الأجزاء الأصلية وهو الأولوية الثانية كخيار بديل
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

    # إذا وجدنا ملفات ملخصات، نتحقق من تسلسلها
    if summary_files:
        summary_files.sort(key=lambda x: x[0])
        part_numbers = [x[0] for x in summary_files]
        expected_sequence = list(range(1, len(summary_files) + 1))
        if part_numbers != expected_sequence:
            logger.error("خطأ بنيوي: تسلسل أرقام الأجزاء غير مكتمل أو يحتوي على فجوات: %s", part_numbers)
            raise ValueError(f"تسلسل ملفات الملخصات غير متصل. الأجزاء الموجودة: {part_numbers}")
        logger.info("تم العثور على ملفات الملخصات بنمط (*_part_NN_summary.md) متسلسلة بلا فجوات.")
        return [f for _, f in summary_files]

    # غير ذلك نرتد للمطابقة الافتراضية للأجزاء ونتحقق من تسلسلها أيضاً
    if part_files:
        part_files.sort(key=lambda x: x[0])
        part_numbers = [x[0] for x in part_files]
        expected_sequence = list(range(1, len(part_files) + 1))
        if part_numbers != expected_sequence:
            logger.error("خطأ بنيوي: تسلسل أرقام الأجزاء الأصلية غير مكتمل أو يحتوي على فجوات: %s", part_numbers)
            raise ValueError(f"تسلسل ملفات الأجزاء الأصلية غير متصل. الأجزاء الموجودة: {part_numbers}")
        logger.info("لم نجد ملخصات مخصصة؛ سنعتمد ملفات الأجزاء الأصلية (*_part_NN.md) متسلسلة بلا فجوات.")
        return [f for _, f in part_files]

    return []


def merge_files(files: list[Path], strip_prompts: bool = True) -> str:
    """دمج محتويات الملفات في نص واحد."""
    parts = []
    for i, f in enumerate(files):
        logger.info("  قراءة الجزء %d: %s", i + 1, f.name)
        text = read_file_with_fallback_encoding(f)

        if strip_prompts:
            text = strip_prompt(text)

        if text:
            parts.append(text)

    return "\n\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="دمج الأجزاء الملخصة في ملف واحد نهائي.")
    parser.add_argument("input_dir", type=str, help="مجلد الأجزاء الملخصة")
    parser.add_argument("-o", "--output", type=str, default=None, help="مسار ملف المخرج النهائي")
    parser.add_argument("--keep-prompts", action="store_true", help="الإبقاء على تعليمات الـ Prompt دون حذفها")
    args = parser.parse_args()

    input_path = Path(args.input_dir)
    if not input_path.exists() or not input_path.is_dir():
        logger.error("المجلد غير موجود: %s", args.input_dir)
        sys.exit(1)

    files = find_summary_files(input_path)
    if not files:
        logger.error("لم يتم العثور على ملفات تلخيص مرقمة بنمط *_part_NN_summary.md أو *_part_NN.md في المجلد.")
        sys.exit(1)

    logger.info("تم العثور على %d ملفات للدمج.", len(files))
    merged_text = merge_files(files, not args.keep_prompts)

    output_file = Path(args.output) if args.output else input_path / "summary_final.md"

    output_file.write_text(merged_text, encoding="utf-8")
    logger.info("تم حفظ الملف المدمج النهائي في: %s", output_file)

    # تحديث ملف الميتادات إن وجد
    metadata_path = input_path / "metadata.json"
    if metadata_path.exists():
        try:
            content = read_file_with_fallback_encoding(metadata_path)
            metadata = json.loads(content)
            # نجعله نسبياً بالنسبة للمجلد لتسهيل النقل والمنقولية
            metadata["merged_output"] = output_file.name
            metadata["merged_words"] = len(merged_text.split())
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            logger.info("تم تحديث ملف الميتادات بنجاح.")
        except Exception as e:
            logger.warning("فشل تحديث ملف الميتادات: %s", e)


if __name__ == "__main__":
    main()