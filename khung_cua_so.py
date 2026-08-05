"""Title bar tự vẽ: vá cửa sổ Win32 để bỏ khung hệ thống mà KHÔNG mất tính năng.

VÌ SAO PHẢI CÓ FILE NÀY
-----------------------
Windows 10 không cho đổi màu thanh tiêu đề: `DWMWA_CAPTION_COLOR` là của Windows 11,
trên máy Win10 nó trả `E_INVALIDARG` (đã đo). Muốn thanh tiêu đề đúng màu app thì
bắt buộc bỏ khung hệ thống và tự vẽ — đó cũng là cách VSCode, Discord, Chrome làm.

Nhưng bỏ khung là mất sạch tính năng của cửa sổ. Ba lần vá dưới đây lấy lại từng cái,
và mỗi lần vá đều đã đo bằng bản thử riêng trước khi viết vào đây:

  1. `WS_THICKFRAME`  — `frameless` xoá mất viền kéo giãn. Gắn lại là có lại, và cờ
     này SỐNG SÓT qua phóng to/khôi phục (đã đo — đây là rủi ro lo nhất, không xảy ra).

  2. `WM_NCCALCSIZE` trả 0 — nếu không, vùng nội dung bị thụt 7px mỗi cạnh (phần viền
     kéo giãn tính là "vùng ngoài"), web hiện thiếu một khung viền quanh mép.

  3. `WM_GETMINMAXINFO` — không vá thì phóng to phủ TRỌN màn hình và **che mất
     taskbar** 47px. Vá rồi thì đúng bằng vùng làm việc, khớp tuyệt đối.

  4. `WM_KEO_RIENG` — kéo và giãn cửa sổ.

BÀI HỌC ĐẮT NHẤT Ở FILE NÀY — ĐỌC TRƯỚC KHI SỬA
------------------------------------------------
Bản đầu tiên vá `WM_NCHITTEST` để dải tiêu đề trả `HTCAPTION`, tin rằng Windows sẽ tự
lo kéo/snap. Test báo 25/25. Người dùng mở lên: không kéo, không giãn, không snap được
gì cả.

Lý do: **WebView2 là một cửa sổ CON phủ KÍN cửa sổ app.** Đo được cây cửa sổ —
`Chrome_RenderWidgetHostHWND` đúng bằng kích thước cửa sổ. Windows hỏi cửa sổ nằm TRÊN
CÙNG dưới con trỏ, luôn là cửa sổ con ấy, và nó trả `HTCLIENT`. Cửa sổ cha KHÔNG BAO
GIỜ được hỏi.

Test sai vì nó `SendMessage(WM_NCHITTEST)` THẲNG vào cửa sổ cha — tức đo "nếu được hỏi
thì cha trả lời đúng không", chứ không đo "Windows có hỏi cha không". Đúng cái bẫy đã
tránh được hai lần ở phía web (dùng `elementFromPoint` chứ không `querySelector`).
Bằng chứng thậm chí đã có sẵn: phép đo "window proc nhận 0 thông điệp/giây" bị đọc
thành tin vui về hiệu năng, trong khi nó đang nói cửa sổ cha không thấy con chuột nào.

=> Việc kéo/giãn phải do WEB khởi động (nó nhận được chuột), rồi nhờ cửa sổ tự chạy
   thao tác của Windows. Xem `bat_dau_keo` và `webui/src/useKhungCuaSo.ts`.

`WM_NCHITTEST` vẫn giữ ở đây, nhưng chỉ còn là lưới an toàn cho trường hợp có điểm nào
đó không bị cửa sổ con phủ — đừng trông cậy vào nó.

AN TOÀN: mọi thứ ở đây bọc try/except. Vá hỏng thì app vẫn chạy với khung mặc định,
xấu nhưng dùng được — thà thế còn hơn không mở nổi cửa sổ.
"""
import ctypes
from ctypes import wintypes

u = ctypes.windll.user32
dwm = ctypes.windll.dwmapi

u.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
u.GetWindowLongPtrW.restype = ctypes.c_longlong
u.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_longlong]
u.SetWindowLongPtrW.restype = ctypes.c_longlong
u.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                              wintypes.WPARAM, wintypes.LPARAM]
u.CallWindowProcW.restype = ctypes.c_longlong
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
u.MonitorFromWindow.restype = ctypes.c_void_p
u.IsZoomed.argtypes = [wintypes.HWND]
u.IsWindowVisible.argtypes = [wintypes.HWND]
u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
u.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
u.SendMessageW.restype = ctypes.c_longlong

GWL_STYLE, GWL_WNDPROC = -16, -4
WS_THICKFRAME, WS_MAXIMIZEBOX, WS_MINIMIZEBOX, WS_SYSMENU = 0x40000, 0x10000, 0x20000, 0x80000
SWP_FRAMECHANGED, SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE = \
    0x0020, 0x0002, 0x0001, 0x0004, 0x0010
WM_NCCALCSIZE, WM_GETMINMAXINFO, WM_NCHITTEST = 0x0083, 0x0024, 0x0084
WM_NCLBUTTONDOWN = 0x00A1
# Thông điệp riêng của app (dải WM_APP, không đụng WinForms). Web gửi cái này để nhờ
# cửa sổ TỰ bắt đầu một thao tác kéo/giãn của Windows.
WM_KEO_RIENG = 0x8000 + 11
HTCLIENT, HTCAPTION = 1, 2
HT_CANH = {"trai": 10, "phai": 11, "tren": 12, "tren_trai": 13, "tren_phai": 14,
           "duoi": 15, "duoi_trai": 16, "duoi_phai": 17}

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)


class MINMAXINFO(ctypes.Structure):
    _fields_ = [("ptReserved", wintypes.POINT), ("ptMaxSize", wintypes.POINT),
                ("ptMaxPosition", wintypes.POINT), ("ptMinTrackSize", wintypes.POINT),
                ("ptMaxTrackSize", wintypes.POINT)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


class MARGINS(ctypes.Structure):
    _fields_ = [("cxLeftWidth", ctypes.c_int), ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int), ("cyBottomHeight", ctypes.c_int)]


class KhungTuVe:
    """Giữ trạng thái của một cửa sổ đã vá.

    PHẢI giữ tham chiếu tới callback trong đối tượng này. Để nó rơi khỏi tầm nhìn là
    Python thu gom mất trong khi Windows vẫn đang gọi -> app chết ngay lập tức, và
    kiểu chết đó rất khó truy vì nó xảy ra ở lần vẽ lại bất kỳ.
    """

    def __init__(self):
        self.hwnd = None
        self.cao_tieu_de = 32       # chiều cao dải tiêu đề, px
        self.vung_cam = []          # [(x1, x2)] — chỗ KHÔNG được coi là caption
        self._proc_moi = None
        self._proc_cu = None
        self.da_va = False

    # ---------- phần giao diện web gọi tới ----------
    def dat_vung_cam(self, vung, cao):
        """Web báo: chỗ nào trên dải tiêu đề là nút/menu, đừng coi là caption.

        Toạ độ x tính theo VÙNG NỘI DUNG (client), vì web chỉ biết toạ độ của nó.
        Không có bảng này thì bấm vào File/Edit hay nút Đóng sẽ thành kéo cửa sổ."""
        try:
            self.vung_cam = [(int(a), int(b)) for a, b in (vung or [])]
            self.cao_tieu_de = max(1, int(cao))
        except Exception:
            pass

    def bat_dau_keo(self, ht):
        """Nhờ Windows tự chạy thao tác kéo (HTCAPTION) hoặc giãn (HTLEFT/HTTOP/…).

        VÌ SAO PHẢI VÒNG QUA MỘT THÔNG ĐIỆP RIÊNG, không gọi thẳng:
        WebView2 là một cửa sổ CON phủ kín cửa sổ app, nên chuột không bao giờ chạm
        tới cửa sổ cha — mọi việc vá `WM_NCHITTEST` ở cha đều vô ích vì Windows không
        hỏi tới nó. Việc kéo/giãn buộc phải do web khởi động.

        Và `ReleaseCapture()` PHẢI chạy trên LUỒNG GIAO DIỆN — luồng đang giữ chuột.
        Gọi nó từ luồng Python là vô hiệu (đã thử, không ăn). Nên ở đây chỉ gửi thông
        điệp; hook `WndProc` nhận nó trên đúng luồng ấy rồi mới gọi.

        Dùng Post chứ không Send: vòng kéo của Windows là MODAL, nó chỉ trả về khi
        người dùng thả chuột. Send thì luồng Python đứng chờ suốt cú kéo."""
        try:
            if not self.hwnd:
                return False
            u.PostMessageW(self.hwnd, WM_KEO_RIENG, int(ht), 0)
            return True
        except Exception:
            return False

    def phong_to_hay_khoi_phuc(self, win):
        try:
            if u.IsZoomed(self.hwnd):
                win.restore()
            else:
                win.maximize()
        except Exception:
            pass

    def dang_phong_to(self):
        try:
            return bool(u.IsZoomed(self.hwnd))
        except Exception:
            return False

    def dang_hien(self):
        """Windows CÒN ĐANG VẼ cửa sổ này không.

        `Window.hide()` chỉ là ra lệnh, không đợi. Ai cần chắc chắn cửa sổ đã biến
        khỏi màn hình — ví dụ trước khi bật overlay chọn điểm, hoặc trước khi chụp
        màn hình để OCR — thì phải hỏi lại chỗ này chứ đừng tin ngay."""
        try:
            return bool(self.hwnd and u.IsWindowVisible(self.hwnd))
        except Exception:
            return False

    # ---------- vá ----------
    def va(self, hwnd):
        """Vá cửa sổ. Trả True nếu vá trọn, False nếu bỏ dở (app vẫn chạy được)."""
        try:
            self.hwnd = hwnd
            cu = u.GetWindowLongPtrW(hwnd, GWL_STYLE)
            u.SetWindowLongPtrW(hwnd, GWL_STYLE,
                                cu | WS_THICKFRAME | WS_MAXIMIZEBOX
                                | WS_MINIMIZEBOX | WS_SYSMENU)
            # Bóng đổ + bo góc: thiếu nó cửa sổ trông dẹt như một mảng màu dán lên.
            m = MARGINS(0, 0, 1, 0)
            dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(m))

            bien = u.GetSystemMetrics(32) + u.GetSystemMetrics(92)   # SM_CXSIZEFRAME + PADDEDBORDER

            def proc(h, msg, wp, lp):
                try:
                    if msg == WM_NCCALCSIZE and wp:
                        return 0                    # vùng nội dung = trọn cửa sổ
                    if msg == WM_GETMINMAXINFO:
                        mi = MONITORINFO()
                        mi.cbSize = ctypes.sizeof(MONITORINFO)
                        if u.GetMonitorInfoW(u.MonitorFromWindow(h, 2), ctypes.byref(mi)):
                            z = ctypes.cast(lp, ctypes.POINTER(MINMAXINFO)).contents
                            w, mo = mi.rcWork, mi.rcMonitor
                            z.ptMaxPosition.x = w.left - mo.left
                            z.ptMaxPosition.y = w.top - mo.top
                            z.ptMaxSize.x = w.right - w.left
                            z.ptMaxSize.y = w.bottom - w.top
                            z.ptMaxTrackSize.x = z.ptMaxSize.x
                            z.ptMaxTrackSize.y = z.ptMaxSize.y
                            return 0
                    if msg == WM_KEO_RIENG:
                        # Đang ở LUỒNG GIAO DIỆN — chỗ duy nhất ReleaseCapture có tác
                        # dụng. Lấy vị trí chuột NGAY LÚC NÀY làm mốc, để cửa sổ không
                        # giật một cái khi vòng kéo bắt đầu.
                        u.ReleaseCapture()
                        p = wintypes.POINT()
                        u.GetCursorPos(ctypes.byref(p))
                        u.SendMessageW(h, WM_NCLBUTTONDOWN, int(wp),
                                       ((p.y & 0xFFFF) << 16) | (p.x & 0xFFFF))
                        return 0
                    if msg == WM_NCHITTEST:
                        return self._o_dau(h, lp, bien)
                except Exception:
                    pass        # lỗi ở đây là chết cả app -> nuốt, để proc gốc lo
                return u.CallWindowProcW(self._proc_cu, h, msg, wp, lp)

            self._proc_moi = WNDPROC(proc)
            self._proc_cu = ctypes.c_void_p(
                u.SetWindowLongPtrW(hwnd, GWL_WNDPROC,
                                    ctypes.cast(self._proc_moi, ctypes.c_void_p).value))
            u.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FRAMECHANGED | SWP_NOMOVE
                           | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
            self.da_va = True
            return True
        except Exception:
            return False

    def _o_dau(self, h, lp, bien):
        """Điểm này là cạnh nào / caption / nội dung."""
        x = ctypes.c_short(lp & 0xFFFF).value
        y = ctypes.c_short((lp >> 16) & 0xFFFF).value
        r = wintypes.RECT()
        u.GetWindowRect(h, ctypes.byref(r))

        if not u.IsZoomed(h):     # phóng to rồi thì không kéo giãn được, bỏ qua mép
            trai, phai = x < r.left + bien, x >= r.right - bien
            tren, duoi = y < r.top + bien, y >= r.bottom - bien
            if tren and trai:
                return HT_CANH["tren_trai"]
            if tren and phai:
                return HT_CANH["tren_phai"]
            if duoi and trai:
                return HT_CANH["duoi_trai"]
            if duoi and phai:
                return HT_CANH["duoi_phai"]
            if trai:
                return HT_CANH["trai"]
            if phai:
                return HT_CANH["phai"]
            if tren:
                return HT_CANH["tren"]
            if duoi:
                return HT_CANH["duoi"]

        if y - r.top < self.cao_tieu_de:
            cx = x - r.left
            if not any(a <= cx < b for a, b in self.vung_cam):
                return HTCAPTION
        return HTCLIENT
