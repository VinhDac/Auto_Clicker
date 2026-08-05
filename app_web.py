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


# .NET Framework tối thiểu. `Python.Runtime.dll` của pythonnet 3.x build cho
# .NET Standard 2.0 (xem Python.Runtime.deps.json), mà .NET Framework chỉ nạp được
# netstandard2.0 từ bản 4.7.2 trở đi. Thiếu nó là hỏng ngay lúc pywebview khởi động,
# TRƯỚC khi một dòng code nào của app chạy — nên phải kiểm sớm và nói bằng tiếng người
# thay vì để PyInstaller ném ra một hộp traceback không ai đọc nổi.
DOTNET_TOI_THIEU = 461808        # = .NET Framework 4.7.2
KHOA_DOTNET = r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"
KHOA_WEBVIEW2 = (r"SOFTWARE\Microsoft\EdgeUpdate\Clients"
                 r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}")


def thieu_dotnet(release):
    """`release` = số trong registry, None nếu máy không có .NET v4. True = thiếu."""
    if release is None:
        return True
    try:
        return int(release) < DOTNET_TOI_THIEU
    except (TypeError, ValueError):
        return True          # đọc ra thứ không phải số -> coi như không tin được


def _doc_registry(goc, duong, ten):
    """Đọc một giá trị registry, thử cả hai view 32/64-bit rồi mới chịu thua."""
    import winreg
    for view in (0, winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
        try:
            with winreg.OpenKey(goc, duong, 0, winreg.KEY_READ | view) as k:
                return winreg.QueryValueEx(k, ten)[0]
        except OSError:
            continue
    return None


def kiem_moi_truong():
    """Những thứ Windows PHẢI có sẵn. Trả về danh sách vấn đề; rỗng nghĩa là đủ."""
    import winreg
    van_de = []
    rel = _doc_registry(winreg.HKEY_LOCAL_MACHINE, KHOA_DOTNET, "Release")
    if thieu_dotnet(rel):
        van_de.append(
            "THIẾU .NET Framework 4.7.2 trở lên"
            + (f" (máy đang có bản cũ hơn, mã {rel})" if rel
               else " (máy chưa cài .NET Framework 4)")
            + ".\n   Tải tại: https://dotnet.microsoft.com/download/dotnet-framework")

    # WebView2: Windows 10/11 thường có sẵn theo Edge, nhưng Windows Server và mấy
    # bản Windows gọt nhẹ thì không.
    pv = (_doc_registry(winreg.HKEY_LOCAL_MACHINE, KHOA_WEBVIEW2, "pv")
          or _doc_registry(winreg.HKEY_CURRENT_USER, KHOA_WEBVIEW2, "pv"))
    if not pv:
        van_de.append(
            "THIẾU Microsoft Edge WebView2 Runtime.\n"
            "   Tải tại: https://developer.microsoft.com/microsoft-edge/webview2/")
    return van_de


def bao_loi(tieu_de, noi_dung):
    """Hộp thoại lỗi của Windows.

    Bản đóng gói chạy `--windowed` nên KHÔNG có console: in ra stderr thì không ai
    thấy, người dùng chỉ thấy app im lặng không mở lên."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, noi_dung, tieu_de, 0x10 | 0x1000)
    except Exception:
        print(f"{tieu_de}: {noi_dung}", file=sys.stderr)


def duong_dan_giao_dien():
    """Trang giao diện đã build. Chưa build thì báo rõ phải chạy npm chứ không mở
    một cửa sổ trắng rồi để người dùng tự đoán."""
    return os.path.join(HERE, "webui", "dist", "index.html")


def tim_cua_so(chua_chuoi=TIEU_DE_GOC):
    """HWND của cửa sổ app. Khớp theo CHUỖI CON vì tiêu đề đổi theo tên Process.

    Cửa sổ không khung VẪN có tiêu đề Win32 (taskbar, Alt+Tab, và mấy bài test dò
    theo tên đều dựa vào nó) — chỉ là Windows không vẽ nó ra nữa."""
    import ctypes
    from ctypes import wintypes
    ra = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def duyet(h, _):
        n = ctypes.windll.user32.GetWindowTextLengthW(h)
        if n and ctypes.windll.user32.IsWindowVisible(h):
            b = ctypes.create_unicode_buffer(n + 1)
            ctypes.windll.user32.GetWindowTextW(h, b, n + 1)
            if chua_chuoi in b.value:
                ra.append(h)
        return True

    try:
        ctypes.windll.user32.EnumWindows(duyet, 0)
    except Exception:
        return None
    return ra[0] if ra else None


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

    thieu = kiem_moi_truong()
    if thieu:
        bao_loi("Auto Clicker — thiếu thành phần của Windows",
                "Máy này chưa đủ thứ để chạy app:\n\n · "
                + "\n\n · ".join(thieu)
                + "\n\nCài xong rồi mở lại app.")
        return 1

    api = Api()
    win = webview.create_window(
        TIEU_DE_GOC,
        url=trang,
        js_api=api,
        width=1280, height=820,
        min_size=(980, 640),
        background_color="#202020",       # tránh chớp trắng trước khi CSS kịp chạy
        # Bỏ khung hệ thống để tự vẽ thanh tiêu đề đúng màu app. Windows 10 không cho
        # đổi màu caption gốc (`DWMWA_CAPTION_COLOR` trả E_INVALIDARG — đã đo), nên
        # đây là đường duy nhất. Mọi tính năng của cửa sổ được vá lại trong
        # `khung_cua_so.py`; vá hỏng thì app vẫn chạy, chỉ là không có viền.
        frameless=True,
        easy_drag=False,      # cách kéo của pywebview đi qua IPC mỗi mousemove và
                              # giết Aero Snap — ta để Windows tự kéo bằng HTCAPTION
    )
    # Api cần cửa sổ để ĐẨY nhật ký chạy ngược về JS (JS không hỏi liên tục được).
    # Đặt tên có '_': pywebview đệ quy vào thuộc tính công khai của js_api
    # và sẽ treo cứng nếu chạm vào đối tượng Window (xem chú thích trong api.py).
    api._window = win
    api._log_khoi_dong = lambda m: print(f"[khởi động] {m}", file=sys.stderr)
    # Đóng cửa sổ giữa lúc đang chạy: phải dừng worker, thả phím đang giữ và gỡ phím
    # dừng toàn cục — nếu không Shift kẹt trong cả Windows sau khi tắt app.
    win.events.closing += api.dong_app

    def sau_khi_mo():
        import time
        time.sleep(0.35)                  # đợi cửa sổ được map xong mới vá được
        h = tim_cua_so()
        if h and api._khung.va(h):
            api._log_khoi_dong("đã vá khung cửa sổ (thanh tiêu đề tự vẽ)")
        else:
            # Không vá được thì thôi: app vẫn dùng được, chỉ là cửa sổ không viền và
            # không kéo giãn. Thà vậy còn hơn không mở nổi.
            api._log_khoi_dong("KHÔNG vá được khung cửa sổ — chạy với khung trần")

    # debug MẶC ĐỊNH TẮT. Bật lên thì pywebview mở luôn cửa sổ DevTools đè lên app —
    # tiện cho người viết code, nhưng người dùng thì chẳng hiểu cửa sổ đó ở đâu ra.
    # Cần dò lỗi thì:  set AUTOCLICKER_DEBUG=1  rồi chạy lại.
    debug = os.environ.get("AUTOCLICKER_DEBUG", "") not in ("", "0", "false")
    # http_server=True: trang build ra dùng ES module, nạp qua file:// thì Chromium chặn
    # vì CORS (origin "null") -> trang trắng. Phục vụ qua http://127.0.0.1 là hết.
    try:
        webview.start(sau_khi_mo, debug=debug, http_server=True)
    except Exception as e:
        # Lỗi ở tầng khởi động pywebview/pythonnet — xảy ra TRƯỚC khi app kịp làm gì.
        # Không bọc thì người dùng nhận nguyên một hộp traceback dài không đọc nổi và
        # tưởng app hỏng, trong khi thật ra chỉ thiếu một thứ của Windows.
        import traceback
        traceback.print_exc()
        bao_loi("Auto Clicker — không mở được cửa sổ",
                f"{type(e).__name__}: {e}\n\n"
                "Hai nguyên nhân hay gặp nhất trên máy mới:\n\n"
                " · Windows CHẶN file vì tải từ mạng. Chuột phải vào file .zip → "
                "Properties → tick 'Unblock' → OK, RỒI MỚI giải nén lại.\n\n"
                " · Thiếu .NET Framework 4.7.2 trở lên, hoặc thiếu Microsoft Edge "
                "WebView2 Runtime.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
