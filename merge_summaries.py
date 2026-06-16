"""
سكربت دمج الأجزاء الملخصة في ملف واحد نهائي.
يقرأ ملفات التلخيص المرقمة بالترتيب ويدمجها في ملف موحد،
مع حذف تعليمات التلخيص (Prompt) من بداية كل جزء.
"""

import argparse
import json
import logging
import re
import shutil
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
    وملاذاً أخيراً، يقرأ النص بترميز UTF-8 مع استبدال البايتات التالفة تفادياً للانهيار.
    """
    encodings = ["utf-8", "utf-8-sig", "cp1256", "latin-1"]
    for enc in encodings:
        try:
            return file_path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    try:
        logger.warning("فشلت جميع الترميزات؛ سيتم قراءة الملف %s بترميز utf-8 مع استبدال البايتات التالفة.", file_path.name)
        return file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise ValueError(f"تعذر قراءة الملف {file_path} باستخدام الترميزات المتاحة: {e}")


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


def clean_part_content(text: str, is_first: bool, main_title: str = None) -> tuple[str, str]:
    """
    تنظيف محتوى الجزء.
    إذا كان الجزء الأول: يستخلص العنوان الرئيسي إن وجد.
    إذا كان جزءاً تالياً: يزيل البسملة المكررة والعنوان الرئيسي المكرر من الصدارة.
    """
    # 1. إزالة البرومبت
    text = strip_prompt(text).strip()
    if not text:
        return "", main_title

    lines = text.splitlines()
    non_empty_lines = [line.strip() for line in lines if line.strip()]

    # تحديد البسملة القياسية
    bismillah = "بسم الله الرحمن الرحيم."

    extracted_title = main_title

    if is_first:
        # استخلاص العنوان الرئيسي من الجزء الأول
        # قد تكون البسملة هي السطر الأول، والعنوان هو السطر الثاني
        temp_title = None
        if non_empty_lines:
            if non_empty_lines[0] == bismillah:
                if len(non_empty_lines) > 1:
                    temp_title = non_empty_lines[1]
            else:
                temp_title = non_empty_lines[0]
        
        # نتحقق من أن العنوان يطابق نسق العناوين المتوقع (ينتهي بنقطتين أو يحتوي على شرح/كتاب)
        if temp_title and (temp_title.endswith(":") or "شرح" in temp_title or "كتاب" in temp_title):
            extracted_title = temp_title
            logger.info("تم استخلاص العنوان الرئيسي للتلخيص: '%s'", extracted_title)
        return text, extracted_title
    else:
        # تنظيف الأجزاء اللاحقة
        changed = True
        while changed and lines:
            changed = False
            first_line = lines[0].strip()
            if not first_line:
                lines.pop(0)
                changed = True
                continue
            
            # إزالة البسملة المكررة في الصدارة
            if first_line == bismillah:
                lines.pop(0)
                changed = True
                continue
                
            # إزالة العنوان الرئيسي المكرر
            if extracted_title and (first_line == extracted_title or first_line == extracted_title.strip(":")):
                lines.pop(0)
                changed = True
                continue
                
        return "\n".join(lines).strip(), extracted_title


def merge_files(files: list[Path], strip_prompts: bool = True) -> str:
    """دمج محتويات الملفات في نص واحد."""
    parts = []
    main_title = None
    for i, f in enumerate(files):
        logger.info("  قراءة الجزء %d: %s", i + 1, f.name)
        text = read_file_with_fallback_encoding(f)

        if strip_prompts:
            is_first = (i == 0)
            text, main_title = clean_part_content(text, is_first, main_title)
        else:
            text = text.strip()

        if text:
            parts.append(text)

    return "\n\n".join(parts)


def process_single_dir(input_path: Path, output_path_str: str, strip_prompts: bool, clean: bool):
    """دمج أجزاء ملف واحد وتحديث ميتاداته وتأمين حفظه."""
    files = find_summary_files(input_path)
    if not files:
        logger.warning("لم يتم العثور على أجزاء للدمج في %s", input_path.name)
        return

    merged_text = merge_files(files, strip_prompts)
    if not merged_text:
        logger.warning("الملف المدمج الناتج فارغ: %s", input_path.name)
        return

    # تحديد مسار المخرج
    if output_path_str:
        output_file = Path(output_path_str)
    else:
        # المخرج الافتراضي داخل مجلد الأجزاء
        output_file = input_path / "summary_final.md"
        
    # إذا تم تفعيل خيار clean وكان الملف المخرج يقع داخل مجلد الأجزاء المراد حذفه
    # ننقله تلقائياً إلى المجلد الأب باسم متميز يمنع الحذف
    if clean:
        if output_file.parent == input_path or input_path in output_file.parents:
            original_name = input_path.name.replace("_parts", "")
            if "test_run_temp" in str(input_path.absolute()):
                output_file = input_path.parent / f"{original_name}_summary.md"
                logger.info("نظراً لتفعيل خيار التنظيف، تم نقل مسار الحفظ للمجلد الأب: %s", output_file.name)
            else:
                summaries_dir = Path(__file__).parent / "summaries"
                output_file = summaries_dir / f"{original_name}_summary.md"
                logger.info("نظراً لتفعيل خيار التنظيف، تم نقل مسار الحفظ لمجلد التلخيصات في مجلد المهارة: %s", output_file.name)

    # حفظ الملف
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(merged_text, encoding="utf-8")
    logger.info("تم حفظ الملف المدمج في: %s", output_file.name)

    # تحديث ميتادات الملف إن لم نكن سنحذفه
    if not clean:
        metadata_path = input_path / "metadata.json"
        if metadata_path.exists():
            try:
                content = read_file_with_fallback_encoding(metadata_path)
                metadata = json.loads(content)
                metadata["merged_output"] = output_file.name
                metadata["merged_words"] = len(merged_text.split())
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning("فشل تحديث ملف الميتادات: %s", e)
    else:
        # مسح مجلد الأجزاء
        try:
            shutil.rmtree(input_path)
            logger.info("تم تنظيف وحذف مجلد الأجزاء المؤقت: %s", input_path.name)
        except Exception as e:
            logger.warning("فشل حذف مجلد الأجزاء %s: %s", input_path.name, e)


def main():
    parser = argparse.ArgumentParser(description="دمج الأجزاء الملخصة في ملف واحد نهائي.")
    parser.add_argument("input_dir", type=str, help="مجلد الأجزاء الملخصة أو المجلد الجامع لها")
    parser.add_argument("-o", "--output", type=str, default=None, help="مسار ملف أو مجلد المخرج النهائي")
    parser.add_argument("--keep-prompts", action="store_true", help="الإبقاء على تعليمات الـ Prompt دون حذفها")
    parser.add_argument("-c", "--clean", action="store_true", help="مسح مجلد الأجزاء بعد نجاح الدمج لتوفير المساحة")
    args = parser.parse_args()

    input_path = Path(args.input_dir)
    if not input_path.exists() or not input_path.is_dir():
        logger.error("المسار غير موجود أو ليس مجلداً: %s", args.input_dir)
        sys.exit(1)

    # التحقق مما إذا كان المجلد المعطى يمثل مجلداً مفرداً للأجزاء
    is_single = (input_path / "metadata.json").exists()

    if is_single:
        logger.info("معالجة مجلد أجزاء مفرد: %s", input_path.name)
        process_single_dir(input_path, args.output, not args.keep_prompts, args.clean)
    else:
        # البحث عن ملفات metadata.json في المجلدات الفرعية
        metadata_files = list(input_path.glob("**/metadata.json"))
        if not metadata_files:
            logger.error("لم يتم العثور على أي ملفات ميتادات (metadata.json) صالحة داخل المجلد.")
            sys.exit(1)

        logger.info("تم الكشف عن مجلد دفعي. وجدنا %d ملفات ميتادات صالحة للدمج والتنظيف.", len(metadata_files))
        
        # ترتيب الملفات لضمان دمج الفصول بالتسلسل الصحيح
        metadata_files.sort()

        for idx, meta_file in enumerate(metadata_files):
            parts_dir = meta_file.parent
            rel_parts_dir = parts_dir.relative_to(input_path)
            
            # تحديد اسم ووجهة مخرج التلخيص
            original_stem = parts_dir.name.replace("_parts", "")
            
            if input_path.name == "all_parts":
                parent_dir = input_path.parent
            else:
                parent_dir = input_path
                
            if "test_run_temp" in str(input_path.absolute()):
                dest_folder = parent_dir / "summaries"
            else:
                dest_folder = Path(__file__).parent / "summaries"
            if rel_parts_dir.parent != Path("."):
                dest_file = dest_folder / rel_parts_dir.parent / f"{original_stem}.md"
            else:
                dest_file = dest_folder / f"{original_stem}.md"

            try:
                rel_dest = dest_file.relative_to(parent_dir)
            except ValueError:
                try:
                    rel_dest = dest_file.relative_to(Path(__file__).parent)
                except ValueError:
                    rel_dest = dest_file
            logger.info("[%d/%d] دمج أجزاء: %s -> %s", idx + 1, len(metadata_files), rel_parts_dir, rel_dest)
            process_single_dir(parts_dir, str(dest_file), not args.keep_prompts, args.clean)

        # إذا تم تفعيل خيار الحذف، نمسح مجلد all_parts بالكامل إذا فرغ
        if args.clean:
            try:
                if input_path.exists() and input_path.name == "all_parts":
                    shutil.rmtree(input_path)
                    logger.info("تم مسح وتنظيف المجلد الجامع all_parts بالكامل.")
            except Exception as e:
                logger.warning("فشل حذف المجلد الجامع: %s", e)


if __name__ == "__main__":
    main()