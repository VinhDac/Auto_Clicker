"""Điểm khởi động giao diện WEB (pywebview + WebView2).

Giao diện chính của app: React + React Flow trong WebView2, Python lo phần lõi.
Bốn overlay phủ màn hình vẫn là tkinter, chạy ở tiến trình con (xem overlays.py).

    python app_web.py            # mở giao diện web
    python app_web.py --overlay point   # nội bộ: bật overlay chọn điểm
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Tiêu đề lúc mở. Sau đó JS ghi đè thành "<tên Process> — Auto Clicker".
TIEU_DE_GOC = "Auto Clicker"


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
    """Trang giao diện đã build. Chưa build thì báo rõ phải chạy npm chứ không mở
    một cửa sổ trắng rồi để người dùng tự đoán."""
    return os.path.join(HERE, "webui", "dist", "index.html")


def thanh_tieu_de_toi(chua_chuoi=TIEU_DE_GOC):
    """Bôi đen thanh tiêu đề Windows cho khớp giao diện tối.

    Cùng mẹo DwmSetWindowAttribute mà bản tkinter đang dùng. Phải tìm cửa sổ theo
    EnumWindows chứ không FindWindowW: tiêu đề có dấu gạch dài "—" và tiếng Việt,
    FindWindowW hay trả 0 (đã dính ở bản tkinter).

    So khớp CHUỖI CON, không khớp tuyệt đối: tiêu đề đổi theo tên Process
    ("Process mẫu — Auto Clicker"), nên khớp tuyệt đối là thua ngay khi JS đổi tên —
    và trước đây nó chỉ đúng nhờ chạy kịp trước lúc đổi."""
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
                if chua_chuoi in buf.value and u.IsWindowVisible(hwnd):
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
        print("Chưa build giao diện. Chạy:  cd webui && npm install && npm run build",
              file=sys.stderr)
        return 1

    api = Api()
    win = webview.create_window(
        TIEU_DE_GOC,
        url=trang,
        js_api=api,
        width=1280, height=820,
        min_size=(980, 640),
        background_color="#202020",       # tránh chớp trắng trước khi CSS kịp chạy
    )
    # Api cần cửa sổ để ĐẨY nhật ký chạy ngược về JS (JS không hỏi liên tục được).
    # Đặt tên có '_': pywebview đệ quy vào thuộc tính công khai của js_api
    # và sẽ treo cứng nếu chạm vào đối tượng Window (xem chú thích trong api.py).
    api._window = win
    # Đóng cửa sổ giữa lúc đang chạy: phải dừng worker, thả phím đang giữ và gỡ phím
    # dừng toàn cục — nếu không Shift kẹt trong cả Windows sau khi tắt app.
    win.events.closing += api.dong_app

    def sau_khi_mo():
        import time
        time.sleep(0.35)                  # đợi cửa sổ được map xong mới bôi đen được
        thanh_tieu_de_toi()

    # debug MẶC ĐỊNH TẮT. Bật lên thì pywebview mở luôn cửa sổ DevTools đè lên app —
    # tiện cho người viết code, nhưng người dùng thì chẳng hiểu cửa sổ đó ở đâu ra.
    # Cần dò lỗi thì:  set AUTOCLICKER_DEBUG=1  rồi chạy lại.
    debug = os.environ.get("AUTOCLICKER_DEBUG", "") not in ("", "0", "false")
    # http_server=True: trang build ra dùng ES module, nạp qua file:// thì Chromium chặn
    # vì CORS (origin "null") -> trang trắng. Phục vụ qua http://127.0.0.1 là hết.
    webview.start(sau_khi_mo, debug=debug, http_server=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
