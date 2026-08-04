"""Overlay chạy dạng TIẾN TRÌNH CON (overlays.py) — cầu nối cho giao diện web.

ĐIỀU KHIỂN CHUỘT + BÀN PHÍM THẬT, chiếm màn hình vài giây. Vì thế bài này nằm trong
nhóm CHUOT_THAT của tests/chay_tat_ca.py, chỉ chạy khi thêm --full.

Vì sao phải giữ bài này: giao diện web (WebView2) không tạo nổi cửa sổ trong suốt phủ
lên game, nên 3 overlay tkinter được gọi ra tiến trình con. Nếu cầu nối stdout↔JSON này
hỏng thì "Chọn điểm", "Căn khung Abyss", "Căn lưới inventory" chết cả ba — mà đó lại là
những phần người dùng thích nhất.
"""
import _boot  # noqa: F401  (đặt sys.path + chdir + stdout UTF-8)

import os
import sys
import json
import time
import threading
import subprocess

import pyautogui

pyautogui.FAILSAFE = False
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

dung = sai = 0


def kiem(ten, dk, chi_tiet=""):
    global dung, sai
    if dk:
        dung += 1
        print(f"  ✔ {ten} {chi_tiet}")
    else:
        sai += 1
        print(f"  ✘ {ten} {chi_tiet}")


def chay(mode, args=(), lai_xe=None, cho=2.0):
    """Bật overlay rồi 'lái' chuột/phím thay người dùng."""
    p = subprocess.Popen([sys.executable, "overlays.py", mode, *args], cwd=REPO,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if lai_xe:
        def sau():
            time.sleep(cho)
            lai_xe()
        threading.Thread(target=sau, daemon=True).start()
    out, err = p.communicate(timeout=60)
    return p.returncode, out.decode("utf-8", "replace").strip()


print("§1 — chọn điểm: di chuột tới (700,400) rồi Enter")
rc, out = chay("point", lai_xe=lambda: (pyautogui.moveTo(700, 400),
                                        time.sleep(0.35), pyautogui.press("enter")))
kiem("stdout đúng MỘT dòng JSON", out.startswith("{") and out.endswith("}"))
d = json.loads(out) if out.startswith("{") else {}
kiem("ok = True", d.get("ok") is True)
v = d.get("value") or [0, 0]
kiem("trả về đúng toạ độ tuyệt đối", abs(v[0] - 700) <= 2 and abs(v[1] - 400) <= 2, f"→ {v}")
kiem("mã thoát 0", rc == 0)

print("§2 — Esc là HUỶ, không phải lỗi")
rc, out = chay("point", lai_xe=lambda: pyautogui.press("esc"))
d = json.loads(out) if out.startswith("{") else {}
kiem("ok = False", d.get("ok") is False)
# Phân biệt huỷ với lỗi là quan trọng: giao diện phải im lặng khi người dùng bấm Esc,
# chứ không nhảy hộp thoại đỏ.
kiem("KHÔNG có trường error khi huỷ", "error" not in d)
kiem("mã thoát 0", rc == 0)

print("§3 — tham số hỏng vẫn ra JSON sạch, không phun traceback")
p = subprocess.run([sys.executable, "overlays.py", "abyss_frame", "--frame", "{hong"],
                   cwd=REPO, capture_output=True, timeout=60)
out = p.stdout.decode("utf-8", "replace").strip()
d = json.loads(out) if out.startswith("{") else {}
kiem("vẫn là JSON hợp lệ", bool(d))
kiem("ok = False và có error", d.get("ok") is False and "error" in d)
kiem("mã thoát khác 0", p.returncode != 0)
kiem("stdout không lẫn traceback", "Traceback" not in out)

print(f"\n✔ KẾT QUẢ: {dung} đúng / {sai} sai")
sys.exit(0 if sai == 0 else 1)
