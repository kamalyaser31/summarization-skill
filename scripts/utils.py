# -*- coding: utf-8 -*-
"""
وحدة المرافق المشتركة لمهارة التلخيص.
تجمع الأدوات المستعملة في أكثر من وحدة تفادياً لتكرار الكود.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_workspace_root() -> Path:
    """البحث عن جذر بيئة العمل بالصعود في شجرة المجلدات حتى العثور على .git أو .agents."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists() or (parent / ".agents").exists():
            return parent
    if len(current.parents) > 4:
        return current.parents[4]
    return current.parent


def read_file_with_fallback_encoding(file_path: Path) -> str:
    """قراءة الملف النصي مع تجربة الترميزات القياسية والارتداد إلى utf-8 مع الاستبدال."""
    for enc in ("utf-8", "utf-8-sig", "cp1256", "latin-1"):
        try:
            return file_path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    try:
        logger.warning("استخدام الارتداد مع الاستبدال لقراءة الملف: %s", file_path.name)
        return file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        raise ValueError(f"تعذر قراءة الملف {file_path}: {err}") from err
