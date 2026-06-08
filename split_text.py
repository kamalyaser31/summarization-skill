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


def count_words(text: str) -> int:
    """عدّ كلمات النص."""
    return len(text.split())


def split_long_line(line: str, max_words: int) -> list[str]:
    """
    تجزئة السطر الطويل جداً إلى أسطر فرعية دون تغيير أي حرف أو مسافة
    لضمان تطابق الفهارس الكلي للنص الأصلي وحماية صحة مسافات الكلمات.
    """
    sub_segments = []
    start = 0
    # نجد المسافات التي تلي علامات الوقف مباشرة لتقسيم السطر بناءً عليها
    for match in re.finditer(r'(?<=[.؟!?])\s+', line):
        end = match.end()
        sub_segments.append(line[start:end])
        start = end
    if start < len(line):
        sub_segments.append(line[start:])

    final_segments = []
    for seg in sub_segments:
        if count_words(seg) > max_words:
            # إذا كانت الجملة الواحدة أطول من السعة، نقسمها كل max_words كلمة كخيار أخير
            words_in_seg = seg.split()
            seg_start = 0
            word_count = 0
            for match in re.finditer(r'\s+', seg):
                word_count += 1
                if word_count >= max_words:
                    seg_end = match.end()
                    final_segments.append(seg[seg_start:seg_end])
                    seg_start = seg_end
                    word_count = 0
            if seg_start < len(seg):
                final_segments.append(seg[seg_start:])
        else:
            final_segments.append(seg)

    return final_segments


def find_split_point(text: str, max_words: int) -> int:
    """
    إيجاد أفضل نقطة قطع في النص ضمن حد الكلمات.
    يبحث عن أقرب حد طبيعي بهذا الترتيب الحاكم:
    1- عنوان فرعي (سطر يبدأ بـ # أو Tab في السطر التالي).
    2- حد فقرة (سطر فارغ).
    3- نهاية جملة (علامة وقف عربية أو إنجليزية في نهاية السطر).
    4- نهاية سطر عادي (فصل السطور).
    """
    words = text.split()
    if len(words) <= max_words:
        return len(text)

    # تقسيم النص إلى أسطر مع الحفاظ على نهاياتها لعدم الإخلال بالمواقع
    raw_lines = text.splitlines(keepends=True)
    lines = []

    # معالجة استباقية للسطور الضخمة (مثل ملفات السطر الواحد) لتفادي انهيار الفحص سطر بسطر
    for line in raw_lines:
        if count_words(line) > max_words:
            lines.extend(split_long_line(line, max_words))
        else:
            lines.append(line)

    current_words = 0
    split_index = 0

    # متغيرات لتتبع جودة نقاط القطع المرشحة وموقعها
    best_heading_split = -1
    heading_words = 0

    best_paragraph_split = -1
    paragraph_words = 0

    best_sentence_split = -1
    sentence_words = 0

    best_line_split = -1
    line_words_count = 0

    # علامات الوقف الشائعة لنهاية الجمل
    sentence_endings = ('.', '؟', '!', '?')

    for idx, line in enumerate(lines):
        line_words = count_words(line)
        # نقف فوراً إذا كان السطر التالي يتجاوز الحد الأقصى المسموح به
        if current_words + line_words > max_words:
            break

        current_words += line_words
        split_index += len(line)

        # 1. التحقق من وجود عنوان فرعي في السطر التالي (أعلى مستويات الفصل الدلالي)
        if idx < len(lines) - 1:
            next_line = lines[idx + 1]
            if next_line.startswith('#') or next_line.startswith('\t'):
                best_heading_split = split_index
                heading_words = current_words
                continue

        # 2. التحقق من حدود الفقرات (سطر فارغ يمثل فاصلاً طبيعياً بين الأفكار)
        if line.strip() == '':
            best_paragraph_split = split_index
            paragraph_words = current_words
            continue
        if idx < len(lines) - 1 and lines[idx + 1].strip() == '':
            best_paragraph_split = split_index
            paragraph_words = current_words
            continue

        # 3. التحقق من نهاية الجملة (القطع عند نقطة أو استفهام يمنع بتر المعنى في السطور المتصلة)
        # نُجرد الأقواس وعلامات الاقتباس الختامية الشائعة لعدم حجب علامة الوقف الأساسية
        stripped_line = line.strip()
        punctuation_check = stripped_line.rstrip(')"\'»]}`”’')
        if punctuation_check and punctuation_check[-1] in sentence_endings:
            best_sentence_split = split_index
            sentence_words = current_words
            continue

        # 4. نهاية السطر (أضعف نقاط القطع المقبولة لتفادي بتر الكلمة الواحدة)
        best_line_split = split_index
        line_words_count = current_words

    # نقوم باختيار النقطة الأعلى جودة التي تجاوزت الحد الأدنى لكي لا تتشظى الملفات
    if best_heading_split != -1 and heading_words >= MIN_WORDS_FOR_NEW_PART:
        return best_heading_split

    if best_paragraph_split != -1 and paragraph_words >= MIN_WORDS_FOR_NEW_PART:
        return best_paragraph_split

    if best_sentence_split != -1 and sentence_words >= MIN_WORDS_FOR_NEW_PART:
        return best_sentence_split

    # إذا تعذر العثور على أي نقطة تستوفي الحد الأدنى، نتغاضى عن هذا الشرط
    # ونختار أفضل نقطة قطع متوفرة تفادياً لعملية القطع العشوائي العنيف
    if best_heading_split != -1:
        return best_heading_split
    if best_paragraph_split != -1:
        return best_paragraph_split
    if best_sentence_split != -1:
        return best_sentence_split
    if best_line_split != -1:
        return best_line_split

    # في حال استعصى وجود أي سطر مناسب (سطر واحد ضخم يتجاوز السعة)، نقطع عند حد الكلمات
    if current_words > 0:
        return split_index

    return len(text)


def split_text(input_file: Path, output_dir: Path, max_words: int = MAX_WORDS):
    """تقسيم النص وحفظ الأجزاء."""
    content = read_file_with_fallback_encoding(input_file)
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
            "file": part_name,
            "words": words_count
        })
        logger.info("حفظ الجزء %d في: %s (%d كلمة)", current_part, part_name, words_count)

    metadata = {
        "source": str(input_file.absolute()),
        "total_words": total_words,
        "parts_count": total_parts,
        "max_words_per_part": max_words,
        "parts": metadata_parts,
        "merged_output": "summary_final.md",
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