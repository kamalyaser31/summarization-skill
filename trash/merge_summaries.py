#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
غلاف (Wrapper) ارتدادي لـ merge_summaries.py.
يقوم بتمرير كافة الوسائط تلقائياً للسكربت الموحد compile_summaries.py.
"""

import sys
import subprocess
from pathlib import Path

def main():
    script_path = Path(__file__).parent / "compile_summaries.py"
    # استدعاء السكربت الموحد مع تمرير وضع merge صراحة والوسائط الحالية
    # نقوم باستخراج كافة الحجج الحالية لتمريرها
    cmd = [sys.executable, str(script_path)] + sys.argv[1:]
    
    # إذا لم يكن هناك خيار mode صراحة، نمرر mode merge كحجة إضافية
    if "--mode" not in sys.argv:
        cmd += ["--mode", "merge"]
    
    print(f"تنبيه: تم دمج merge_summaries.py في السكربت الموحد compile_summaries.py.")
    print(f"جاري تحويل الطلب تلقائياً لـ compile_summaries.py...")
    
    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()