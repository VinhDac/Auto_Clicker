"""E2E: mở app web THẬT, thao tác THẬT, và sau MỖI bước hỏi Windows xem cửa sổ
còn bơm thông điệp không.

VÌ SAO PHẢI CÓ BÀI NÀY
----------------------
Đã có lúc toàn bộ 598 check xanh mà app hoàn toàn không dùng được: cửa sổ hiện ra,
JS chạy, DOM đúng, ảnh chụp đẹp — nhưng Windows báo "Not Responding" ngay khi mở.
Nguyên nhân: `api.window = <Window>` làm pywebview đệ quy vào đối tượng cửa sổ và
deadlock luồng giao diện (xem chú thích trong api.py).

Mọi bài test cũ đều mù trước lỗi đó vì chúng hỏi DOM, mà DOM thì vẫn đúng. Chỉ có
`SendMessageTimeout(WM_NULL)` mới trả lời được câu "app còn dùng được không".

BÀI HỌC VỀ PHÉP ĐO: phải khai `argtypes`/`restype` cho ctypes. Lần đầu tôi gọi
`IsHungAppWindow(hwnd)` mà không khai, HWND 64-bit bị cắt còn 32-bit và hàm trả
"không treo" trong khi app đang treo — suýt nữa kết luận sai.

Bài này ĐIỀU KHIỂN CHUỘT THẬT nên nằm ở nhóm CHUOT_THAT (chỉ chạy với --full).
"""
import _boot  # noqa: F401

import os
import sys
import time
import ctypes
import subprocess
from ctypes import wintypes

import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.2

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(REPO, ".venv", "Scripts", "python.exe")
# Khớp CHUỖI CON: tiêu đề đổi theo tên Process ("Process mẫu — Auto Clicker").
TIEU_DE = "Auto Clicker"

u = ctypes.windll.user32
u.IsHungAppWindow.argtypes = [wintypes.HWND]
u.IsHungAppWindow.restype = wintypes.BOOL
u.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                  wintypes.LPARAM, wintypes.UINT, wintypes.UINT,
                                  ctypes.POINTER(ctypes.c_ulong)]
u.SendMessageTimeoutW.restype = wintypes.LPARAM

dung = sai = 0


def kiem(ten, dk, chi_tiet=""):
    global dung, sai
    if dk:
        dung += 1
        print(f"  ✔ {ten} {chi_tiet}")
    else:
        sai += 1
        print(f"  ✘ {ten} {chi_tiet}")


def tim_cua_so():
    """EnumWindows chứ không FindWindowW: tiêu đề có dấu gạch dài và tiếng Việt."""
    ra = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def duyet(h, _):
        n = u.GetWindowTextLengthW(h)
        if n:
            b = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(h, b, n + 1)
            if TIEU_DE in b.value and u.IsWindowVisible(h):
                ra.append(h)
        return True

    u.EnumWindows(duyet, 0)
    return ra[0] if ra else None


def con_song(h, ms=3000):
    """Cách CHUẨN để biết cửa sổ còn xử lý thông điệp không.
    SMTO_ABORTIFHUNG: trả 0 ngay nếu tiến trình đã bị coi là treo."""
    kq = ctypes.c_ulong()
    r = u.SendMessageTimeoutW(h, 0, 0, 0, 0x0002, ms, ctypes.byref(kq))
    return bool(r) and not bool(u.IsHungAppWindow(h))


def main():
    p = subprocess.Popen([PY, "app_web.py"], cwd=REPO,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    h = None
    t0 = time.time()
    try:
        while time.time() - t0 < 40 and not h:
            time.sleep(0.3)
            h = tim_cua_so()
        kiem("cửa sổ mở được", bool(h), f"({time.time() - t0:.1f}s)")
        if not h:
            return

        time.sleep(4)                      # đợi React + bootstrap chạy xong
        kiem("còn phản hồi ngay sau khi mở", con_song(h))

        u.SetForegroundWindow(h)
        time.sleep(1)
        r = wintypes.RECT()
        ctypes.windll.dwmapi.DwmGetWindowAttribute(h, 9, ctypes.byref(r), ctypes.sizeof(r))
        X, Y = r.left, r.top
        kiem("kích thước cửa sổ hợp lý", (r.right - X) > 900 and (r.bottom - Y) > 500,
             f"{r.right - X}x{r.bottom - Y}")

        # Toạ độ tương đối theo bố cục: thanh tiêu đề ~31px, rồi NGAY đến ribbon
        # (không còn dải đầu trang), hàng nút ở y≈75, canvas từ y≈145.
        # Đổi bố cục thì phải sửa mấy số này — chúng bám vào giao diện.
        for ten, viec in [
            ("thêm khối (bấm Loop)",   lambda: pyautogui.click(X + 75, Y + 75)),
            ("thêm khối lần 2",        lambda: pyautogui.click(X + 75, Y + 75)),
            ("kéo khối trên canvas",   lambda: (pyautogui.moveTo(X + 300, Y + 380),
                                                pyautogui.dragTo(X + 560, Y + 470, duration=0.5))),
            ("mở hộp thoại (double-click)", lambda: pyautogui.doubleClick(X + 560, Y + 470)),
            ("đóng hộp thoại (Esc)",   lambda: pyautogui.press("escape")),
            ("mở tab Nhật ký",         lambda: pyautogui.click(X + 140, Y + 655)),
            ("Ctrl+Z",                 lambda: pyautogui.hotkey("ctrl", "z")),
        ]:
            viec()
            time.sleep(1.2)
            kiem(f"còn phản hồi sau: {ten}", con_song(h))

        kiem("tiến trình chưa chết", p.poll() is None)
    finally:
        if h:
            u.PostMessageW(h, 0x0010, 0, 0)       # WM_CLOSE
        time.sleep(2)
        if p.poll() is None:
            p.kill()

    print(f"\n✔ KẾT QUẢ: {dung} đúng / {sai} sai")
    sys.exit(0 if sai == 0 else 1)


if __name__ == "__main__":
    main()
