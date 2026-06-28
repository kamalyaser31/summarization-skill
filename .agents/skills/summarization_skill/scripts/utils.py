"""
وحدة المرافق المشتركة لمهارة التلخيص.
تجمع الأدوات المستعملة في أكثر من وحدة تفادياً لتكرار الكود.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_workspace_root() -> Path:
    """
    البحث عن جذر بيئة العمل بالصعود في شجرة المجلدات حتى العثور على .git أو .agents.
    """
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists() or (parent / ".agents").exists():
            return parent
    # إذا لم يعثر على علامة مميزة، يصعد 4 مستويات إن أمكن
    if len(current.parents) > 4:
        return current.parents[4]
    return current.parent


def read_file_with_fallback_encoding(file_path: Path) -> str:
    """
    قراءة الملف النصي مع محاولة استخدام عدة ترميزات شائعة.
    يُجرب ترميز UTF-8 أولاً تماشياً مع المعايير الحديثة، ثم يرتد إلى
    ترميز cp1256 العربي لبيئات Windows الشائعة لتفادي أخطاء فك الترميز.
    وملاذاً أخيراً، يقرأ النص بترميز UTF-8 مع استبدال البايتات التالفة تفادياً للانهيار.
    """
    encodings = ["utf-8", "utf-8-sig", "cp1256", "latin-1"]
    for enc in encodings:
        try:
            return file_path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    # OSError يشمل PermissionError وFileNotFoundError وأخطاء القرص
    try:
        logger.warning(
            "فشلت جميع الترميزات؛ سيتم قراءة الملف %s بترميز utf-8 مع استبدال البايتات التالفة.",
            file_path.name,
        )
        return file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise ValueError(
            f"تعذر قراءة الملف {file_path} باستخدام الترميزات المتاحة: {e}"
        )
