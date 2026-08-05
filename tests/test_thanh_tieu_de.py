"""Thanh tiêu đề tự vẽ: đúng màu app, và KHÔNG mất tính năng của cửa sổ thường.

VÌ SAO PHẢI TỰ VẼ
-----------------
Windows 10 không cho đổi màu caption hệ thống: `DWMWA_CAPTION_COLOR` là của Win11,
trên máy này trả `E_INVALIDARG` (đã đo). Muốn thanh tiêu đề đúng màu app thì chỉ còn
cách bỏ khung và tự vẽ — như VSCode, Discord, Chrome.

Nhưng bỏ khung là mất sạch tính năng cửa sổ, nên bài này canh đúng chỗ đó. Bốn thứ
dưới đây đều là lỗi CÓ THẬT lúc mới bỏ khung, đo được rồi mới vá:

  · viền kéo giãn biến mất       -> gắn lại WS_THICKFRAME
  · nội dung thụt 7px mỗi cạnh   -> WM_NCCALCSIZE trả 0
  · phóng to CHE TASKBAR 47px    -> WM_GETMINMAXINFO ép về vùng làm việc
  · hết kéo giãn sau khi vá (2)  -> tự trả lời WM_NCHITTEST cho 8 mép

Bài này CHỈ kiểm những thứ hỏi được mà không cần chuột: màu sắc, bố cục, style cửa
sổ, kích thước khi phóng to. Kéo / giãn / double-click phải nghiệm thu bằng thao tác
chuột THẬT — xem `test_khung_chuot.py`; hỏi Win32 "cha có trả lời đúng không" là câu
hỏi sai, đã từng cho 25/25 trong khi app hoàn toàn không dùng được.

Bài này ĐỘNG VÀO CỬA SỔ THẬT (phóng to / thu nhỏ) nhưng không chiếm chuột.
"""
import _boot  # noqa: F401
import _web

import os
import sys
import time
import ctypes
from ctypes import wintypes

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANG = os.path.join(REPO, "webui", "dist", "index.html")

u = ctypes.windll.user32
u.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
u.GetWindowLongPtrW.restype = ctypes.c_longlong
u.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
u.SendMessageW.restype = ctypes.c_longlong
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.IsZoomed.argtypes = [wintypes.HWND]
u.GetSystemMenu.argtypes = [wintypes.HWND, wintypes.BOOL]
u.GetSystemMenu.restype = wintypes.HMENU

GWL_STYLE, WS_THICKFRAME, WS_CAPTION = -16, 0x00040000, 0x00C00000
WM_NCHITTEST, SPI_GETWORKAREA = 0x0084, 0x0030
HT = {1: "HTCLIENT", 2: "HTCAPTION", 10: "HTLEFT", 11: "HTRIGHT", 12: "HTTOP",
      13: "HTTOPLEFT", 14: "HTTOPRIGHT", 15: "HTBOTTOM", 16: "HTBOTTOMLEFT",
      17: "HTBOTTOMRIGHT"}

dung = sai = 0


def kiem(ten, dk, chi_tiet=""):
    global dung, sai
    if dk:
        dung += 1
        print(f"  ✔ {ten} {chi_tiet}")
    else:
        sai += 1
        print(f"  ✘ {ten} {chi_tiet}")


def main():
    global sai
    if not os.path.exists(TRANG):
        print("  ✘ chưa có webui/dist — chạy `npm run build` trong webui/ trước")
        sys.exit(1)

    import webview
    from api import Api
    import khung_cua_so

    api = Api()
    win = webview.create_window("Auto Clicker", url=TRANG, js_api=api,
                                width=1180, height=760, frameless=True, easy_drag=False)
    api._window = win
    ghi = []

    def js(s):
        return win.evaluate_js(s)

    def than():
        try:
            _web.cho_san_sang(js)
            time.sleep(1.0)

            ra = []

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def d(h, _):
                n = u.GetWindowTextLengthW(h)
                if n and u.IsWindowVisible(h):
                    b = ctypes.create_unicode_buffer(n + 1)
                    u.GetWindowTextW(h, b, n + 1)
                    if "Auto Clicker" in b.value:
                        ra.append(h)
                return True

            u.EnumWindows(d, 0)
            ghi.append(("cửa sổ không khung VẪN có tiêu đề Win32 (taskbar / Alt+Tab)",
                        bool(ra)))
            if not ra:
                return
            h = ra[0]
            ghi.append(("vá được khung cửa sổ", api._khung.va(h)))
            time.sleep(0.6)

            # ---------------- giao diện ----------------
            ghi.append(("có thanh tiêu đề tự vẽ",
                        js("!!document.querySelector('.thanh-tieu-de')")))
            mau = js("getComputedStyle(document.querySelector('.thanh-tieu-de'))"
                     ".backgroundColor")
            nen = js("getComputedStyle(document.querySelector('.ribbon')).backgroundColor")
            ghi.append(("thanh tiêu đề ĐÚNG MÀU app, không còn đen của Windows",
                        mau == nen, f"— {mau} vs ribbon {nen}"))
            ten_menu = js("[...document.querySelectorAll('.menu-tren')]"
                          ".map(b=>b.textContent.trim())")
            ghi.append(("đủ 4 menu File / Edit / View / Help",
                        ten_menu == ["File", "Edit", "View", "Help"], f"— {ten_menu}"))
            ghi.append(("có logo bên trái", js("!!document.querySelector('.logo-app')")))
            ghi.append(("có 3 nút cửa sổ bên phải",
                        js("document.querySelectorAll('.nut-cua-so .nut-cs').length") == 3))

            # ---------------- style cửa sổ ----------------
            st = u.GetWindowLongPtrW(h, GWL_STYLE)
            ghi.append(("gắn lại được viền kéo giãn (WS_THICKFRAME)",
                        bool(st & WS_THICKFRAME), f"— 0x{st & 0xFFFFFFFF:08X}"))
            ghi.append(("không dính lại caption hệ thống", not (st & WS_CAPTION)))
            hm = u.GetSystemMenu(h, False)
            ghi.append(("còn menu hệ thống (Alt+Space / chuột phải thanh tiêu đề)",
                        bool(hm) and u.GetMenuItemCount(hm) > 0))

            # ---------------- nội dung phủ trọn cửa sổ ----------------
            r = wintypes.RECT(); rc = wintypes.RECT()
            u.GetWindowRect(h, ctypes.byref(r)); u.GetClientRect(h, ctypes.byref(rc))
            ghi.append(("nội dung phủ TRỌN cửa sổ, không thừa viền 7px",
                        abs((r.right - r.left) - rc.right) <= 1
                        and abs((r.bottom - r.top) - rc.bottom) <= 1,
                        f"— cửa sổ {r.right-r.left}x{r.bottom-r.top}, "
                        f"nội dung {rc.right}x{rc.bottom}"))

            # KHÔNG kiểm hit-test ở đây nữa. Bản trước có 4 check hỏi
            # `SendMessage(WM_NCHITTEST)` THẲNG vào cửa sổ cha, tất cả đều xanh, và
            # app vẫn không kéo/giãn/snap được gì. Chúng đo "nếu được hỏi thì cha trả
            # lời đúng không" — trong khi WebView2 là cửa sổ CON phủ kín cửa sổ, nên
            # Windows KHÔNG BAO GIỜ hỏi cha. Check xanh mà tính năng chết là tệ hơn
            # không có check. Việc kéo/giãn giờ do web khởi động và được nghiệm thu
            # bằng thao tác chuột THẬT ở `test_khung_chuot.py`.
            # ---------------- phóng to / thu nhỏ ----------------
            wa = wintypes.RECT()
            u.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(wa), 0)
            win.maximize(); time.sleep(1.0)
            rz = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(rz))
            ghi.append(("phóng to được", bool(u.IsZoomed(h))))
            ghi.append(("phóng to KHÔNG che taskbar",
                        rz.bottom <= wa.bottom + 2,
                        f"— đáy cửa sổ {rz.bottom}, đáy vùng làm việc {wa.bottom}"))
            ghi.append(("phóng to phủ đúng vùng làm việc",
                        abs((rz.right - rz.left) - (wa.right - wa.left)) <= 2
                        and abs((rz.bottom - rz.top) - (wa.bottom - wa.top)) <= 2,
                        f"— {rz.right-rz.left}x{rz.bottom-rz.top}"))
            st2 = u.GetWindowLongPtrW(h, GWL_STYLE)
            ghi.append(("viền kéo giãn sống sót qua phóng to", bool(st2 & WS_THICKFRAME)))
            win.restore(); time.sleep(0.9)
            ghi.append(("khôi phục được", not u.IsZoomed(h)))
            ghi.append(("…và viền vẫn còn",
                        bool(u.GetWindowLongPtrW(h, GWL_STYLE) & WS_THICKFRAME)))
            win.minimize(); time.sleep(0.9)
            ghi.append(("thu nhỏ được", bool(u.IsIconic(h))))
            win.restore(); time.sleep(0.9)
            ghi.append(("bung lại từ thu nhỏ", not u.IsIconic(h)))

            # ---------------- an toàn: vá hỏng thì app vẫn sống ----------------
            k = khung_cua_so.KhungTuVe()
            ghi.append(("vá vào cửa sổ không tồn tại thì chịu thua êm, không ném lỗi",
                        k.va(0) is False or k.va(0) is True))
            ghi.append(("app vẫn còn sống sau tất cả", bool(u.IsWindow(h))))
        except Exception:
            import traceback
            ghi.append(("chạy được tới cuối", False, "\n" + traceback.format_exc(limit=4)))
        finally:
            win.destroy()

    webview.start(than, debug=False, http_server=True)

    for m in ghi:
        kiem(m[0], m[1], m[2] if len(m) > 2 else "")
    if not ghi:
        print("  ✘ không thu được kết quả nào (cửa sổ không mở?)")
        sai += 1

    print(f"\n✔ KẾT QUẢ: {dung} đúng / {sai} sai")
    sys.exit(0 if sai == 0 else 1)


if __name__ == "__main__":
    main()
