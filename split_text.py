"""
سكربت تقسيم النصوص الطويلة لمهارة التلخيص.
يقسم النص إلى أجزاء ضمن السعة الفعالة (3000-5000 كلمة)
ويولّد Prompt جاهزاً للصق في بداية كل جزء.
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

# الحد الأقصى للكلمات في الجزء الواحد
MAX_WORDS = 4000
# الحد الأدنى المقبول قبل فتح جزء جديد
MIN_WORDS_FOR_NEW_PART = 500

PROMPT_TEMPLATE = """\
[تعليمات التلخيص - الجزء {current} من {total}]
لخّص هذا الجزء وفق مهارة التلخيص المثبتة في تعليمات النظام.
{continuation_note}
---
"""

FIRST_PART_NOTE = "هذا هو الجزء الأول؛ ابدأ بالبسملة والعنوان الرئيسي."
CONTINUATION_NOTE = "هذا استكمال للتلخيص السابق؛ تابع من حيث انتهيت دون تكرار البسملة أو العنوان."
LAST_PART_NOTE = "هذا هو الجزء الأخير؛ اختم التلخيص بالخلاصة إن وُجدت."


def count_words(text: str) -> int:
    """عدّ كلمات النص."""
    return len(text.split())


def find_split_point(text: str, max_words: int) -> int:
    """
    إيجاد أفضل نقطة قطع في النص ضمن حد الكلمات.
    يبحث عن أقرب حد طبيعي بهذا الترتيب:
    1- عنوان فرعي (سطر يبدأ بـ # أو Tab)
    2- فقرة (سطر فارغ مزدوج)
    3- سطر فارغ مفرد
    4- نهاية جملة (نقطة)
    """
    words = text.split()
    if len(words) <= max_words:
        return len(text)

    # تقسيم النص إلى أسطر
    lines = text.splitlines(keepends=True)
    current_words = 0
    split_index = 0
    best_split = -1
    best_split_words = 0

    for idx, line in enumerate(lines):
        line_words = count_words(line)
        if current_words + line_words > max_words:
            break

        current_words += line_words
        split_index += len(line)

        # التحقق من جودة النقطة الحالية للقطع
        if idx < len(lines) - 1:
            next_line = lines[idx + 1]
            # 1. عنوان فرعي
            if next_line.startswith('#') or next_line.startswith('\t'):
                best_split = split_index
                best_split_words = current_words
            # 2. فقرة فارغة
            elif line.strip() == '' or next_line.strip() == '':
                if best_split == -1 or next_line.strip() == '':
                    best_split = split_index
                    best_split_words = current_words

    if best_split != -1 and best_split_words >= MIN_WORDS_FOR_NEW_PART:
        return best_split

    if current_words > 0:
        return split_index

    return len(text)


def split_text(input_file: Path, output_dir: Path, max_words: int = MAX_WORDS):
    """تقسيم النص وحفظ الأجزاء."""
    content = input_file.read_text(encoding="utf-8")
    total_words = count_words(content)

    logger.info("حجم الملف الكلي: %d كلمة", total_words)

    if total_words <= max_words:
        logger.info("الملف ضمن السعة الفعالة، لن يتم تقسيمه.")
        parts = [content]
    else:
        parts = []
        remaining = content
        while count_words(remaining) > max_words:
            split_idx = find_split_point(remaining, max_words)
            part = remaining[:split_idx]
            parts.append(part)
            remaining = remaining[split_idx:]
        if remaining:
            if parts and count_words(remaining) < MIN_WORDS_FOR_NEW_PART:
                parts[-1] += remaining
            else:
                parts.append(remaining)

    total_parts = len(parts)
    logger.info("تقسيم النص إلى %d جزءاً.", total_parts)

    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_parts = []

    for i, part in enumerate(parts):
        current_part = i + 1
        if current_part == 1:
            note = FIRST_PART_NOTE
        elif current_part == total_parts:
            note = LAST_PART_NOTE
        else:
            note = CONTINUATION_NOTE

        header = PROMPT_TEMPLATE.format(
            current=current_part,
            total=total_parts,
            continuation_note=note
        )

        part_name = f"{input_file.stem}_part_{current_part:02d}.md"
        part_path = output_dir / part_name
        part_path.write_text(header + part, encoding="utf-8")

        words_count = count_words(part)
        metadata_parts.append({
            "file": str(part_path.absolute()),
            "words": words_count
        })
        logger.info("حفظ الجزء %d في: %s (%d كلمة)", current_part, part_name, words_count)

    metadata = {
        "source": str(input_file.absolute()),
        "total_words": total_words,
        "parts_count": total_parts,
        "max_words_per_part": max_words,
        "parts": metadata_parts,
        "merged_output": str((output_dir / "summary_final.md").absolute()),
        "merged_words": 0
    }

    with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    logger.info("تم حفظ ملف الميتادات في: %s", output_dir / "metadata.json")


def main():
    parser = argparse.ArgumentParser(description="تقسيم النصوص الطويلة لمهارة التلخيص.")
    parser.add_argument("input", type=str, help="مسار الملف النصي المراد تقسيمه (.txt أو .md)")
    parser.add_argument("-o", "--output", type=str, default=None, help="مجلد المخرجات")
    parser.add_argument("--max-words", type=int, default=MAX_WORDS, help="الحد الأقصى للكلمات في الجزء الواحد")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("الملف غير موجود: %s", args.input)
        sys.exit(1)

    # إذا لم يُحدد مجلد المخرجات، يتم الحفظ في مجلد بجانب الملف الأصلي باسم <اسم_الملف>_parts
    if args.output is None:
        output_dir = input_path.parent / f"{input_path.stem}_parts"
    else:
        output_dir = Path(args.output)

    split_text(input_path, output_dir, args.max_words)


if __name__ == "__main__":
    main()