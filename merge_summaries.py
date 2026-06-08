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
PROMPT_PATTERN = re.compile(
    r'^\[تعليمات التلخيص.*?\]\s*.*?---\s*',
    re.DOTALL | re.MULTILINE,
)


def strip_prompt(text: str) -> str:
    """حذف تعليمات التلخيص (Prompt) من بداية النص."""
    return PROMPT_PATTERN.sub('', text, count=1).strip()


def find_summary_files(input_dir: Path) -> list[Path]:
    """
    إيجاد ملفات التلخيص المرقمة في المجلد.
    يبحث عن ملفات بنمط *_part_NN.md ويرتبها بالترتيب.
    """
    pattern = re.compile(r'_part_(\d+)\.md$', re.IGNORECASE)
    files = []
    for f in input_dir.iterdir():
        if f.is_file() and pattern.search(f.name):
            match = pattern.search(f.name)
            part_num = int(match.group(1))
            files.append((part_num, f))

    files.sort(key=lambda x: x[0])
    return [f for _, f in files]


def merge_files(files: list[Path], strip_prompts: bool = True) -> str:
    """دمج محتويات الملفات في نص واحد."""
    parts = []
    for i, f in enumerate(files):
        logger.info("  قراءة الجزء %d: %s", i + 1, f.name)
        text = f.read_text(encoding="utf-8")

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
        logger.error("لم يتم العثور على ملفات تلخيص مرقمة بنمط *_part_NN.md في المجلد.")
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
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            metadata["merged_output"] = str(output_file.absolute())
            metadata["merged_words"] = len(merged_text.split())
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            logger.info("تم تحديث ملف الميتادات.")
        except Exception as e:
            logger.warning("فشل تحديث ملف الميتادات: %s", e)


if __name__ == "__main__":
    main()