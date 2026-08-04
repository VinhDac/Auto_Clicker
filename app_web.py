"""Điểm khởi động giao diện WEB (pywebview + WebView2).

Chạy song song với `auto_clicker_gui.py` (bản tkinter). App cũ KHÔNG bị đụng tới —
lúc nào cũng chạy được, cho tới khi bản web đủ tính năng.

    python app_web.py            # mở giao diện web
    python app_web.py --overlay point   # nội bộ: bật overlay chọn điểm
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _giai_quyet_co_overlay():
    """Khi đóng gói .exe sẽ không có python.exe để chạy `overlays.py`, nên api.py gọi
    lại CHÍNH exe này kèm cờ --overlay. Phải bắt TRƯỚC khi import pywebview, nếu không
    mỗi lần chọn điểm lại khởi động thêm một WebView2 vô ích."""
    if len(sys.argv) > 1 and sys.argv[1] == "--overlay":
        import overlays
        sys.exit(overlays.main(sys.argv[2:]))


_giai_quyet_co_overlay()

import webview                                    # noqa: E402
from api import Api                               # noqa: E402


def duong_dan_giao_dien():
    """Ưu tiên bản đã build (P1 trở đi), chưa có thì dùng trang thăm dò của P0."""
    dist = os.path.join(HERE, "webui", "dist", "index.html")
    if os.path.exists(dist):
        return dist
    return os.path.join(HERE, "webui", "p0_probe.html")


def thanh_tieu_de_toi(tieu_de):
    """Bôi đen thanh tiêu đề Windows cho khớp giao diện tối.

    Cùng mẹo DwmSetWindowAttribute mà bản tkinter đang dùng. Phải tìm cửa sổ theo
    EnumWindows chứ không FindWindowW: tiêu đề có dấu gạch dài "—" và tiếng Việt,
    FindWindowW hay trả 0 (đã dính ở bản tkinter)."""
    import ctypes
    from ctypes import wintypes
    try:
        u, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
        tim = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def duyet(hwnd, _):
            n = u.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                u.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value == tieu_de and u.IsWindowVisible(hwnd):
                    tim.append(hwnd)
            return True

        u.EnumWindows(duyet, 0)
        for hwnd in tim:
            dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)),
                                      ctypes.sizeof(ctypes.c_int))
            # Đặt thuộc tính thôi thì khung chưa vẽ lại — phải ép một lần.
            u.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0020)
    except Exception:
        pass          # thanh tiêu đề sáng thì xấu, nhưng không đáng để app chết


def main():
    trang = duong_dan_giao_dien()
    if not os.path.exists(trang):
        print(f"Không tìm thấy giao diện: {trang}", file=sys.stderr)
        return 1

    TIEU_DE = "Auto Clicker — PoE2"
    webview.create_window(
        TIEU_DE,
        url=trang,
        js_api=Api(),
        width=1280, height=820,
        min_size=(980, 640),
        background_color="#202020",       # tránh chớp trắng trước khi CSS kịp chạy
    )

    def sau_khi_mo():
        import time
        time.sleep(0.35)                  # đợi cửa sổ được map xong mới bôi đen được
        thanh_tieu_de_toi(TIEU_DE)

    # debug=True bật DevTools Chromium đầy đủ. Đây là thứ bản tkinter không bao giờ có —
    # trước đây phải LẤY MẪU PIXEL trên ảnh chụp màn hình mới biết màu có đúng không.
    # http_server=True: trang build ra dùng ES module, nạp qua file:// thì Chromium chặn
    # vì CORS (origin "null") -> trang trắng. Phục vụ qua http://127.0.0.1 là hết.
    webview.start(sau_khi_mo, debug=True, http_server=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
