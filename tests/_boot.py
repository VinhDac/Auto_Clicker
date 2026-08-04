"""Đặt đường dẫn cho các bài test.

Import module này ĐẦU TIÊN trong mỗi bài test. Nó làm 2 việc:
  1. đưa thư mục gốc dự án vào sys.path  -> import được core / api / overlay_ui
  2. chuyển thư mục làm việc về gốc dự án -> mở được data/mods_poe2.txt,
     tests/anh/*.png... dù bạn chạy test từ đâu

Nhờ vậy chạy kiểu nào cũng được:
    python tests\\test_them_hanh_dong.py
    cd tests && python test_do_thi_va_api.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

# Windows console mặc định cp1252, in tiếng Việt là vỡ. Ép UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
