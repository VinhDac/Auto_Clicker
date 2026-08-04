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


def main():
    trang = duong_dan_giao_dien()
    if not os.path.exists(trang):
        print(f"Không tìm thấy giao diện: {trang}", file=sys.stderr)
        return 1

    webview.create_window(
        "Auto Clicker — PoE2",
        url=trang,
        js_api=Api(),
        width=1280, height=820,
        min_size=(980, 640),
        background_color="#202020",       # tránh chớp trắng trước khi CSS kịp chạy
    )
    # debug=True bật DevTools Chromium đầy đủ. Đây là thứ bản tkinter không bao giờ có —
    # trước đây phải LẤY MẪU PIXEL trên ảnh chụp màn hình mới biết màu có đúng không.
    webview.start(debug=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
