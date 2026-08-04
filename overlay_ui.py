"""Phần tkinter còn sống: bảng màu + 4 overlay chọn-trên-màn-hình.

Đây là những gì còn lại của giao diện tkinter cũ sau khi bản web thay thế nó.
KHÔNG phải code chết — `overlays.py` chạy 4 lớp này trong TIẾN TRÌNH CON, vì
WebView2 không tạo được cửa sổ trong suốt phủ lên cửa sổ game để bắt click và
đọc pixel:

    PointSelector       🎯 chọn 1 điểm bằng crosshair
    AbyssFrameSelector  🖼 căn khung panel Abyss
    InvGridSelector     🖼 căn lưới kho đồ + tick ô
    ReviewOverlay       👁 xem lại mọi điểm sẽ bị click

Giữ NGUYÊN XI từ bản cũ — đây là mấy phần người dùng hài lòng nhất, viết lại chỉ
tổ làm hỏng. Chúng vẫn cần THEME/apply_theme để trông đồng bộ với giao diện web.

Đừng thêm cửa sổ mới vào đây. Giao diện chính là `webui/` + `app_web.py`.
"""

import os
import time
import ctypes

import tkinter as tk
from tkinter import ttk

# Chỉ lấy đúng những gì 4 overlay cần. Trước đây file này `from core import *` vì nó
# là cả một ứng dụng; giờ nó chỉ còn là 4 overlay nên nhập hẹp lại cho rõ ràng.
import core                                           # noqa: F401  (dùng qua core.<tên>)
from core import (pyautogui, resource_path, abyss_regions, abyss_scan,
                  ABYSS_ASPECT, ABYSS_BANDS, ABYSS_CONFIRM, ABYSS_REFRESH, INV_ASPECT,
                  inv_scan, inv_cell_box, INV_ROWS, INV_COLS)

# ================= GIAO DIỆN TỐI =================
# Một chỗ duy nhất giữ màu. Trước đây màu bị hardcode rải rác 8 chỗ, 3 bảng khác nhau.
THEME = {
    "bg":        "#202020",   # nền cửa sổ
    "surface":   "#2b2b2b",   # panel / khung
    "field":     "#2d2d2d",   # ô nhập, danh sách
    "raised":    "#383838",   # nút thường
    "border":    "#3f3f3f",
    "text":      "#e8e8e8",
    "muted":     "#9a9a9a",
    "dim":       "#7a7a7a",
    "accent":    "#ffa657",   # đổi được trong Cài đặt (cam dịu — cam gắt hại mắt trên nền tối)
    "on_accent": "#000000",   # tự tính theo độ sáng của accent
    "ok":        "#3fb950",
    "err":       "#f85149",
    "warn":      "#d29922",
}

# Màu nhấn chọn sẵn (vẫn chọn được màu tuỳ ý qua nút "Tuỳ chọn…")
ACCENT_PRESETS = {
    "Cam": "#ffa657",             # mặc định — cam dịu, dễ nhìn nhất trên nền tối
    "Xanh dương": "#4a9eff",
    "Lục": "#3fb950",
    "Tím": "#a371f7",
    "Đỏ": "#f85149",
    "Vàng": "#d29922",
    "Hồng": "#db61a2",
    "Xanh ngọc": "#39c5cf",
}


def best_fg(hex_color):
    """Chữ đen hay trắng thì dễ đọc hơn trên nền màu này? (tránh nút cam chữ trắng khó đọc)"""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return "#000000"
    return "#000000" if (0.2126 * r + 0.7152 * g + 0.0722 * b) > 140 else "#ffffff"


def set_accent(color):
    THEME["accent"] = color
    THEME["on_accent"] = best_fg(color)


def dark_titlebar(win, remap=False):
    """Làm tối thanh tiêu đề (Windows 10 1903+). Không hỗ trợ thì bỏ qua, không sao.

    Đặt thuộc tính DWM thôi là CHƯA ĐỦ — Windows không vẽ lại khung ngay. Có 2 cách
    ép vẽ lại, và mỗi loại cửa sổ hợp một cách (đã đo bằng cách lấy mẫu pixel):
      - remap=False: SetWindowPos(FRAMECHANGED) — ăn với HỘP THOẠI, không nháy,
        không phá grab. Nhưng KHÔNG ăn với cửa sổ chính.
      - remap=True : ẩn rồi hiện lại — cách duy nhất ăn với CỬA SỔ CHÍNH. Chỉ dùng
        lúc khởi động nên người dùng không thấy nháy.
    """
    try:
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        val = ctypes.c_int(1)
        # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val),
                                                   ctypes.sizeof(val))
        if remap:
            win.withdraw()
            win.update_idletasks()
            win.deiconify()
        else:
            SWP_FRAMECHANGED, SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER = 0x20, 0x2, 0x1, 0x4
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER)
    except Exception:
        pass


def style_tk_widget(w):
    """Tô màu cho widget tk CỔ ĐIỂN (Listbox/Text/Menu/Entry/Frame/Canvas) — mấy loại
    này không theo ttk nên phải đặt màu tay."""
    T = THEME
    try:
        cls = w.winfo_class()
    except Exception:
        return
    try:
        if cls == "Listbox":
            w.configure(bg=T["field"], fg=T["text"], borderwidth=0,
                        highlightthickness=0, activestyle="none",
                        selectbackground=T["accent"], selectforeground=T["on_accent"])
        elif cls == "Text":
            w.configure(bg=T["field"], fg=T["text"], borderwidth=0,
                        highlightthickness=0, insertbackground=T["text"],
                        selectbackground=T["accent"], selectforeground=T["on_accent"])
        elif cls == "Menu":
            w.configure(bg=T["surface"], fg=T["text"], borderwidth=0,
                        activebackground=T["accent"], activeforeground=T["on_accent"],
                        disabledforeground=T["dim"])
        elif cls == "Entry":
            w.configure(bg=T["field"], fg=T["text"], insertbackground=T["text"],
                        highlightthickness=1, highlightbackground=T["border"],
                        highlightcolor=T["accent"], borderwidth=0)
        elif cls in ("Frame", "Toplevel", "Tk"):
            w.configure(bg=T["bg"])
        elif cls == "Label":
            w.configure(bg=T["bg"], fg=T["text"])
    except tk.TclError:
        pass


def restyle_tree(w):
    """Tô lại toàn bộ widget tk cổ điển đang có (dùng khi đổi màu nhấn lúc đang chạy)."""
    style_tk_widget(w)
    try:
        for c in w.winfo_children():
            restyle_tree(c)
    except Exception:
        pass


def apply_theme(root):
    """Áp bảng màu tối lên toàn bộ ttk + widget tk đang tồn tại.
    Gọi lại được bất cứ lúc nào (vd sau khi đổi màu nhấn)."""
    T = THEME
    s = ttk.Style(root)
    # BẮT BUỘC dùng 'clam': theme mặc định 'vista' của Windows vẽ nút/ô nhập bằng
    # ảnh native nên BỎ QUA màu ta đặt (đã đo: nút vẫn xám, ô nhập vẫn trắng).
    try:
        s.theme_use("clam")
    except tk.TclError:
        pass

    BG, SF, FD, RS = T["bg"], T["surface"], T["field"], T["raised"]
    BD, TX, MU, AC = T["border"], T["text"], T["muted"], T["accent"]
    ON = T["on_accent"]

    s.configure(".", background=BG, foreground=TX, fieldbackground=FD,
                bordercolor=BD, lightcolor=BD, darkcolor=BD,
                troughcolor=BG, focuscolor=AC, insertcolor=TX)

    s.configure("TFrame", background=BG)
    s.configure("Card.TFrame", background=SF)
    s.configure("TLabel", background=BG, foreground=TX)
    s.configure("Muted.TLabel", background=BG, foreground=MU)
    s.configure("Title.TLabel", background=BG, foreground=TX,
                font=("Segoe UI", 12, "bold"))
    s.configure("Ok.TLabel", background=BG, foreground=T["ok"])
    s.configure("Err.TLabel", background=BG, foreground=T["err"])
    s.configure("Warn.TLabel", background=BG, foreground=T["warn"])

    s.configure("TLabelframe", background=BG, bordercolor=BD, relief="solid", borderwidth=1)
    s.configure("TLabelframe.Label", background=BG, foreground=MU)

    s.configure("TButton", background=RS, foreground=TX, bordercolor=BD,
                borderwidth=1, focusthickness=0, padding=(8, 4))
    s.map("TButton",
          background=[("pressed", BD), ("active", BD), ("disabled", SF)],
          foreground=[("disabled", T["dim"])])

    s.configure("Accent.TButton", background=AC, foreground=ON,
                bordercolor=AC, borderwidth=0, padding=(10, 5))
    s.map("Accent.TButton",
          background=[("pressed", AC), ("active", AC), ("disabled", SF)],
          foreground=[("disabled", T["dim"])])

    s.configure("Danger.TButton", background=RS, foreground=T["err"], bordercolor=BD)
    s.map("Danger.TButton", background=[("active", BD)],
          foreground=[("disabled", T["dim"])])

    s.configure("TEntry", fieldbackground=FD, foreground=TX, bordercolor=BD,
                insertcolor=TX, padding=3)
    s.map("TEntry", bordercolor=[("focus", AC)])
    s.configure("TCombobox", fieldbackground=FD, background=RS, foreground=TX,
                bordercolor=BD, arrowcolor=TX, padding=3)
    s.map("TCombobox", fieldbackground=[("readonly", FD)], bordercolor=[("focus", AC)])
    s.configure("TMenubutton", background=RS, foreground=TX, bordercolor=BD,
                arrowcolor=TX, padding=(8, 4))
    s.map("TMenubutton", background=[("active", BD)])

    s.configure("TCheckbutton", background=BG, foreground=TX,
                indicatorcolor=FD, focuscolor=BG)
    s.map("TCheckbutton", indicatorcolor=[("selected", AC)],
          background=[("active", BG)])

    s.configure("TNotebook", background=BG, bordercolor=BD, borderwidth=0)
    s.configure("TNotebook.Tab", background=BG, foreground=MU,
                padding=(12, 5), borderwidth=0)
    s.map("TNotebook.Tab", background=[("selected", SF)],
          foreground=[("selected", AC)], expand=[("selected", [0, 0, 0, 0])])

    s.configure("TPanedwindow", background=BG)
    s.configure("Sash", background=BD, gripcount=0)
    s.configure("TSeparator", background=BD)
    s.configure("Vertical.TScrollbar", background=RS, troughcolor=BG,
                bordercolor=BG, arrowcolor=MU, borderwidth=0)
    s.map("Vertical.TScrollbar", background=[("active", BD)])
    s.configure("Horizontal.TScrollbar", background=RS, troughcolor=BG,
                bordercolor=BG, arrowcolor=MU, borderwidth=0)

    # màu nền chung cho các hộp thoại/cửa sổ do Tk vẽ
    try:
        root.configure(bg=BG)
        root.option_add("*background", BG)
        root.option_add("*foreground", TX)
    except Exception:
        pass

    restyle_tree(root)
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel):
            restyle_tree(w)


def set_window_icon(win):
    """Đặt icon cho cửa sổ. Không có file thì Tk tự dùng icon mặc định của nó."""
    try:
        p = core.resource_path("logo.ico")
        if os.path.exists(p):
            win.iconbitmap(p)
    except Exception:
        pass


def enable_dpi(root):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            return
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
        ctypes.windll.user32.ReleaseDC(0, hdc)
        root.tk.call("tk", "scaling", dpi / 72.0)
    except Exception:
        pass


def center_window(win, w=None, h=None):
    """Đặt cửa sổ ra giữa màn hình.

    KHÔNG cho w/h -> chỉ đặt VỊ TRÍ, để Tk tự co theo nội dung.
    Từng ép cả kích thước ở đây và nó cắn: cửa sổ đang ẩn thì winfo_width() trả 1
    nên phải hỏi winfo_reqwidth(), mà giá trị đó có lúc CHƯA tính xong (trong bản
    đóng gói đo được 216x239 thay vì 341x395). Ép size sai vào một cửa sổ không cho
    co giãn là nội dung bị cắt vĩnh viễn. Chỉ đặt vị trí thì tệ nhất là lệch tâm
    một chút — không bao giờ mất chữ."""
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    if w and h:
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2 - 30)
        win.geometry(f"{w}x{h}+{x}+{y}")
        return
    x = max(0, (sw - max(win.winfo_width(), win.winfo_reqwidth())) // 2)
    y = max(0, (sh - max(win.winfo_height(), win.winfo_reqheight())) // 2 - 30)
    win.geometry(f"+{x}+{y}")


# ---------------- Overlay crosshair chọn 1 điểm ----------------
class PointSelector:
    def __init__(self, root, callback):
        self.callback = callback
        u = ctypes.windll.user32
        self.vx, self.vy = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
        self.vw, self.vh = u.GetSystemMetrics(78), u.GetSystemMetrics(79)
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry(f"{self.vw}x{self.vh}+{self.vx}+{self.vy}")
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.30)
        except Exception:
            pass
        self.canvas = tk.Canvas(self.win, cursor="none", bg=THEME["bg"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.vline = self.canvas.create_line(0, 0, 0, self.vh, fill="red", width=2)
        self.hline = self.canvas.create_line(0, 0, self.vw, 0, fill="red", width=2)
        self.dot = self.canvas.create_oval(0, 0, 0, 0, outline="yellow", width=2)
        self.coord_bg = self.canvas.create_rectangle(0, 0, 0, 0, fill="black", outline="")
        self.coord = self.canvas.create_text(0, 0, fill="yellow", anchor="nw",
                                             font=("Consolas", 13, "bold"), text="")
        self.canvas.create_text(self.vw // 2, 30, fill=THEME["text"], font=("Segoe UI", 15),
                                text="Di chuột tới điểm cần chọn  •  Click / F8 / Enter để chốt  •  Esc để huỷ")
        self.canvas.bind("<Motion>", self._move)
        # Chốt bằng THẢ chuột: overlay nuốt trọn cú click (cả nhấn lẫn thả),
        # không để lọt thêm 1 left-click xuống game phía dưới.
        self.canvas.bind("<ButtonRelease-1>", lambda e: self._pick(e.x, e.y))
        self.win.bind("<Escape>", lambda e: self._finish(None))
        self.win.bind("<F8>", self._key_pick)
        self.win.bind("<Return>", self._key_pick)
        self.win.bind("<space>", self._key_pick)
        self.win.focus_force()
        try:
            self.win.update_idletasks()
            self.win.grab_set()
        except Exception:
            pass
        p = pyautogui.position()
        ix = min(max(int(p.x) - self.vx, 0), self.vw)
        iy = min(max(int(p.y) - self.vy, 0), self.vh)
        self._last = (ix, iy)
        self._move_to(ix, iy)

    def _move(self, e):
        self._last = (e.x, e.y)
        self._move_to(e.x, e.y)

    def _move_to(self, x, y):
        self.canvas.coords(self.vline, x, 0, x, self.vh)
        self.canvas.coords(self.hline, 0, y, self.vw, y)
        r = 7
        self.canvas.coords(self.dot, x - r, y - r, x + r, y + r)
        ax, ay = self.vx + x, self.vy + y
        self.canvas.itemconfig(self.coord, text=f" X={ax}   Y={ay} ")
        lx = x + 18 if x + 150 < self.vw else x - 150
        ly = y + 18 if y + 34 < self.vh else y - 34
        self.canvas.coords(self.coord, lx, ly)
        b = self.canvas.bbox(self.coord)
        if b:
            self.canvas.coords(self.coord_bg, *b)
        self.canvas.tag_raise(self.coord)

    def _key_pick(self, e):
        self._pick(self._last[0], self._last[1])

    def _pick(self, x, y):
        self._finish((self.vx + x, self.vy + y))

    def _finish(self, pt):
        try:
            self.win.grab_release()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass
        self.callback(pt)


# ---------------- Overlay xem lại các điểm đã chọn ----------------
class ReviewOverlay:
    def __init__(self, root, points, on_close):
        """points: list of (x, y, label, color) theo toạ độ tuyệt đối."""
        self.on_close = on_close
        u = ctypes.windll.user32
        self.vx, self.vy = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
        self.vw, self.vh = u.GetSystemMetrics(78), u.GetSystemMetrics(79)
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry(f"{self.vw}x{self.vh}+{self.vx}+{self.vy}")
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.35)
        except Exception:
            pass
        c = tk.Canvas(self.win, bg=THEME["bg"], highlightthickness=0)
        c.pack(fill="both", expand=True)
        c.create_text(self.vw // 2, 34, fill=THEME["text"], font=("Segoe UI", 16),
                      text="Xem lại các điểm đã chọn  •  Click hoặc Esc để đóng")
        for (x, y, label, color) in points:
            cx, cy = x - self.vx, y - self.vy
            r = 16
            c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=3)
            c.create_line(cx - r - 8, cy, cx + r + 8, cy, fill=color, width=2)
            c.create_line(cx, cy - r - 8, cx, cy + r + 8, fill=color, width=2)
            t = c.create_text(cx + r + 10, cy - 10, anchor="nw", fill=THEME["text"],
                              font=("Segoe UI", 12, "bold"), text=label)
            b = c.bbox(t)
            if b:
                bg = c.create_rectangle(b[0] - 3, b[1] - 2, b[2] + 3, b[3] + 2,
                                        fill=color, outline="")
                c.tag_lower(bg, t)
        self.win.bind("<ButtonRelease-1>", lambda e: self._close())
        self.win.bind("<Escape>", lambda e: self._close())
        self.win.bind("<Key>", lambda e: self._close())
        self.win.focus_force()
        try:
            self.win.grab_set()
        except Exception:
            pass

    def _close(self):
        try:
            self.win.grab_release()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass
        self.on_close()


# ---------------- Overlay căn khung panel Abyss ----------------
class AbyssFrameSelector:
    """Căn 1 khung duy nhất trùm lên panel "Well of Souls".

    Khung LUÔN giữ đúng tỉ lệ của panel thật, nên chỉ cần kéo cho trùm khít là mọi
    vùng con (3 dải mod, nút REVEAL/CONFIRM, nút refresh) tự suy ra theo tỉ lệ —
    người dùng không phải chọn từng điểm.

        kéo giữa   = di chuyển        kéo 4 góc     = phóng to / thu nhỏ
        mũi tên    = nhích 1px        Shift+mũi tên = 10px
        + / -      = phóng to/thu nhỏ D             = đọc thử
        Enter      = lưu              Esc           = huỷ

    "Đọc thử" chụp + OCR ngay tại chỗ để thấy căn chuẩn chưa, khỏi phải chạy thật
    rồi mới biết sai (và đốt currency oan).
    """
    HANDLE = 16          # bán kính vùng bắt 4 góc
    MIN_W = 120

    def __init__(self, root, frame, callback):
        self.callback = callback
        self.result_lines = []
        self.drag = None          # (mode, mốc...) — mode: "move" hoặc góc 0..3
        u = ctypes.windll.user32
        self.vx, self.vy = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
        self.vw, self.vh = u.GetSystemMetrics(78), u.GetSystemMetrics(79)

        if frame and len(frame) == 4 and frame[2] > 0 and frame[3] > 0:
            self.fx, self.fy, self.fw, self.fh = (int(v) for v in frame)
        else:
            self.fw = int(self.vw * 0.27)          # panel thật ~27% bề ngang màn hình
            self.fh = int(self.fw / ABYSS_ASPECT)
            self.fx = self.vx + (self.vw - self.fw) // 2
            self.fy = self.vy + (self.vh - self.fh) // 2

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry(f"{self.vw}x{self.vh}+{self.vx}+{self.vy}")
        self.win.attributes("-topmost", True)
        try:
            # Đậm hơn PointSelector một chút: ở đây phải NHÌN RÕ đường kẻ để căn cho
            # khớp, không chỉ ngắm 1 điểm. Game phía dưới vẫn thấy đủ để căn.
            self.win.attributes("-alpha", 0.35)
        except Exception:
            pass
        self.canvas = tk.Canvas(self.win, bg=THEME["bg"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        for key, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            self.win.bind(f"<{key}>", lambda e, a=dx, b=dy: self._nudge(a, b))
            self.win.bind(f"<Shift-{key}>", lambda e, a=dx, b=dy: self._nudge(a * 10, b * 10))
        self.win.bind("<plus>", lambda e: self._scale(1.02))
        self.win.bind("<equal>", lambda e: self._scale(1.02))
        self.win.bind("<minus>", lambda e: self._scale(1 / 1.02))
        self.win.bind("<Prior>", lambda e: self._scale(1.05))
        self.win.bind("<Next>", lambda e: self._scale(1 / 1.05))
        self.win.bind("<d>", lambda e: self._test_read())
        self.win.bind("<D>", lambda e: self._test_read())
        self.win.bind("<Return>", lambda e: self._finish(True))
        self.win.bind("<Escape>", lambda e: self._finish(False))
        self.win.focus_force()
        try:
            self.win.update_idletasks()
            self.win.grab_set()
        except Exception:
            pass
        self._draw()

    # ---- hình học ----
    def _rect(self):
        """Khung theo toạ độ CANVAS (đã trừ gốc desktop ảo)."""
        return (self.fx - self.vx, self.fy - self.vy, self.fw, self.fh)

    def _corners(self):
        x, y, w, h = self._rect()
        return [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]

    def _clamp(self):
        self.fw = max(self.MIN_W, int(self.fw))
        self.fh = int(self.fw / ABYSS_ASPECT)      # cao luôn suy từ rộng -> giữ tỉ lệ

    def _nudge(self, dx, dy):
        self.fx += dx
        self.fy += dy
        self._draw()

    def _scale(self, k):
        cx, cy = self.fx + self.fw / 2, self.fy + self.fh / 2
        self.fw = int(self.fw * k)
        self._clamp()
        self.fx, self.fy = int(cx - self.fw / 2), int(cy - self.fh / 2)
        self._draw()

    # ---- chuột ----
    def _press(self, e):
        # 4 góc theo thứ tự: trên-trái, trên-phải, dưới-trái, dưới-phải
        for i, (cx, cy) in enumerate(self._corners()):
            if abs(e.x - cx) <= self.HANDLE and abs(e.y - cy) <= self.HANDLE:
                # Neo = góc ĐỐI DIỆN (đứng yên), khung nở ra theo hướng cố định của
                # góc đang kéo. Chốt hướng ngay lúc bấm chứ không tính theo vị trí
                # chuột từng khoảnh khắc — nếu không, kéo qua khỏi neo là khung lật.
                ax = self.fx + self.fw if i in (0, 2) else self.fx
                ay = self.fy + self.fh if i in (0, 1) else self.fy
                sx = -1 if i in (0, 2) else 1
                sy = -1 if i in (0, 1) else 1
                self.drag = ("corner", ax, ay, sx, sy)
                return
        x, y, w, h = self._rect()
        if x <= e.x <= x + w and y <= e.y <= y + h:
            self.drag = ("move", e.x - x, e.y - y)

    def _motion(self, e):
        if not self.drag:
            return
        if self.drag[0] == "move":
            self.fx = self.vx + e.x - self.drag[1]
            self.fy = self.vy + e.y - self.drag[2]
        else:
            _, ax, ay, sx, sy = self.drag
            # Bề rộng quyết định, bề cao suy ra -> tỉ lệ không bao giờ méo
            self.fw = abs(self.vx + e.x - ax)
            self._clamp()
            self.fx = ax if sx > 0 else ax - self.fw
            self.fy = ay if sy > 0 else ay - self.fh
        self._draw()

    def _release(self, e):
        self.drag = None

    # ---- vẽ ----
    def _draw(self):
        self._clamp()
        c = self.canvas
        c.delete("all")
        AC, OK, TX = THEME["accent"], THEME["ok"], THEME["text"]
        x, y, w, h = self._rect()

        c.create_text(self.vw // 2, 26, fill=TX, font=("Segoe UI", 14),
                      text="Kéo giữa = di chuyển  •  kéo 4 góc = phóng to/thu nhỏ  •  "
                           "mũi tên = 1px, Shift = 10px  •  +/− = zoom")
        c.create_text(self.vw // 2, 50, fill=THEME["accent"], font=("Segoe UI", 13, "bold"),
                      text="D = ĐỌC THỬ (xem OCR đọc ra gì)      Enter = lưu      Esc = huỷ")

        c.create_rectangle(x, y, x + w, y + h, outline=AC, width=2)
        # 3 dải mod: vùng sẽ được chụp + OCR, và tâm dải là điểm click chọn mod
        for i, (t0, t1) in enumerate(ABYSS_BANDS, 1):
            by0, by1 = y + h * t0, y + h * t1
            c.create_rectangle(x + 2, by0, x + w - 2, by1, outline=OK, width=1, dash=(4, 3))
            c.create_text(x + 10, (by0 + by1) / 2, anchor="w", fill=OK,
                          font=("Segoe UI", 10, "bold"), text=f"Mod {i}")
            cx, cy = x + w / 2, (by0 + by1) / 2
            c.create_line(cx - 7, cy, cx + 7, cy, fill=OK, width=1)
            c.create_line(cx, cy - 7, cx, cy + 7, fill=OK, width=1)
        # nút REVEAL/CONFIRM
        bx, by = x + w * ABYSS_CONFIRM[0], y + h * ABYSS_CONFIRM[1]
        c.create_oval(bx - 9, by - 9, bx + 9, by + 9, outline=AC, width=2)
        c.create_text(bx, by - 18, fill=AC, font=("Segoe UI", 10, "bold"), text="REVEAL/CONFIRM")
        # hộp dò nút refresh
        rx0, ry0, rx1, ry1 = ABYSS_REFRESH
        c.create_rectangle(x + w * rx0, y + h * ry0, x + w * rx1, y + h * ry1,
                           outline=THEME["warn"], width=2)
        c.create_text(x + w * rx1 + 6, y + h * ry0 - 8, anchor="w", fill=THEME["warn"],
                      font=("Segoe UI", 10, "bold"), text="↻ refresh")
        # tay nắm 4 góc
        for cx, cy in self._corners():
            c.create_rectangle(cx - 5, cy - 5, cx + 5, cy + 5, fill=AC, outline="")

        c.create_text(x, y - 10, anchor="sw", fill=TX, font=("Consolas", 11),
                      text=f"{self.fx}, {self.fy}   {self.fw}×{self.fh}")
        self._draw_results()

    def _draw_results(self):
        if not self.result_lines:
            return
        c = self.canvas
        y = 90
        c.create_text(20, y, anchor="nw", fill=THEME["accent"],
                      font=("Segoe UI", 12, "bold"), text="Đọc thử:")
        for i, (txt, color) in enumerate(self.result_lines):
            t = c.create_text(20, y + 24 + i * 22, anchor="nw", fill=color,
                              font=("Consolas", 11), text=txt)
            b = c.bbox(t)
            if b:
                bg = c.create_rectangle(b[0] - 4, b[1] - 2, b[2] + 4, b[3] + 2,
                                        fill="#000000", outline="")
                c.tag_lower(bg, t)

    # ---- đọc thử ----
    def _test_read(self):
        reason = core.ocr_unavailable_reason()
        if reason:
            self.result_lines = [(f"✖ {reason}", THEME["err"])]
            self._draw()
            return
        # Overlay đang phủ lên game -> phải ẩn đi mới chụp được ảnh thật bên dưới
        self.win.withdraw()
        self.win.update()
        time.sleep(0.15)
        try:
            texts, has_refresh, fail = core.abyss_scan((self.fx, self.fy, self.fw, self.fh))
        finally:
            self.win.deiconify()
            self.win.update()
            self.win.focus_force()
            try:
                self.win.grab_set()
            except Exception:
                pass

        lines = []
        for i, t in enumerate(texts or [], 1):
            if t.strip():
                lines.append((f"  Mod {i}: {t}", THEME["ok"]))
            else:
                lines.append((f"  Mod {i}: (không đọc được)", THEME["err"]))
        if fail:
            lines.append((f"  ✖ {fail}", THEME["err"]))
        else:
            lines.append((f"  ↻ nút refresh: {'CÓ' if has_refresh else 'không thấy'}",
                          THEME["warn"]))
        self.result_lines = lines
        self._draw()

    def _finish(self, save):
        try:
            self.win.grab_release()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass
        self.callback([self.fx, self.fy, self.fw, self.fh] if save else None)


# ---------------- Overlay căn lưới inventory + tick ô ----------------
class InvGridSelector:
    """Căn khung trùm lưới inventory (12×5), rồi BẤM THẲNG VÀO Ô để tick.

    Khung khoá đúng tỉ lệ lưới thật nên chỉ cần kéo cho 4 mép trùng là 60 ô tự
    rơi đúng chỗ — không phải căn từng ô, không phải khai số hàng/cột.

        kéo giữa = di chuyển     kéo 4 góc = phóng to/thu nhỏ
        BẤM vào ô = tick/bỏ tick (ô đã tick hiện số thứ tự dùng)
        mũi tên = nhích 1px      Shift+mũi tên = 10px
        D = đọc thử (ô nào CÒN, ô nào HẾT)     Enter = lưu     Esc = huỷ
    """
    HANDLE = 16
    MIN_W = 200
    DRAG_SLOP = 4          # di chuột dưới ngần này pixel thì coi là BẤM, không phải KÉO

    def __init__(self, root, frame, cells, callback):
        self.callback = callback
        self.cells = [tuple(c) for c in (cells or [])]
        self.scan = None            # {(r,c): còn_hàng} sau khi Đọc thử
        self.drag = None
        u = ctypes.windll.user32
        self.vx, self.vy = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
        self.vw, self.vh = u.GetSystemMetrics(78), u.GetSystemMetrics(79)

        if frame and len(frame) == 4 and frame[2] > 0 and frame[3] > 0:
            self.fx, self.fy, self.fw, self.fh = (int(v) for v in frame)
        else:
            self.fw = int(self.vw * 0.32)
            self.fh = int(self.fw / INV_ASPECT)
            self.fx = self.vx + (self.vw - self.fw) // 2
            self.fy = self.vy + (self.vh - self.fh) // 2

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry(f"{self.vw}x{self.vh}+{self.vx}+{self.vy}")
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.35)
        except Exception:
            pass
        self.canvas = tk.Canvas(self.win, bg=THEME["bg"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        for key, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            self.win.bind(f"<{key}>", lambda e, a=dx, b=dy: self._nudge(a, b))
            self.win.bind(f"<Shift-{key}>", lambda e, a=dx, b=dy: self._nudge(a * 10, b * 10))
        self.win.bind("<plus>", lambda e: self._scale(1.02))
        self.win.bind("<equal>", lambda e: self._scale(1.02))
        self.win.bind("<minus>", lambda e: self._scale(1 / 1.02))
        self.win.bind("<d>", lambda e: self._test_read())
        self.win.bind("<D>", lambda e: self._test_read())
        self.win.bind("<c>", lambda e: self._clear())
        self.win.bind("<C>", lambda e: self._clear())
        self.win.bind("<Return>", lambda e: self._finish(True))
        self.win.bind("<Escape>", lambda e: self._finish(False))
        self.win.focus_force()
        try:
            self.win.update_idletasks()
            self.win.grab_set()
        except Exception:
            pass
        self._draw()

    # ---- hình học ----
    def _rect(self):
        return (self.fx - self.vx, self.fy - self.vy, self.fw, self.fh)

    def _corners(self):
        x, y, w, h = self._rect()
        return [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]

    def _clamp(self):
        self.fw = max(self.MIN_W, int(self.fw))
        self.fh = int(self.fw / INV_ASPECT)

    def _cell_at(self, cx, cy):
        """Toạ độ canvas -> (hàng, cột), None nếu ngoài lưới."""
        x, y, w, h = self._rect()
        if not (x <= cx < x + w and y <= cy < y + h):
            return None
        c = int((cx - x) / (w / INV_COLS))
        r = int((cy - y) / (h / INV_ROWS))
        if 0 <= r < INV_ROWS and 0 <= c < INV_COLS:
            return (r, c)
        return None

    def _nudge(self, dx, dy):
        self.fx += dx
        self.fy += dy
        self._draw()

    def _scale(self, k):
        cx, cy = self.fx + self.fw / 2, self.fy + self.fh / 2
        self.fw = int(self.fw * k)
        self._clamp()
        self.fx, self.fy = int(cx - self.fw / 2), int(cy - self.fh / 2)
        self._draw()

    def _clear(self):
        self.cells = []
        self.scan = None
        self._draw()

    # ---- chuột: BẤM = tick ô, KÉO = di chuyển khung ----
    def _press(self, e):
        for i, (cx, cy) in enumerate(self._corners()):
            if abs(e.x - cx) <= self.HANDLE and abs(e.y - cy) <= self.HANDLE:
                ax = self.fx + self.fw if i in (0, 2) else self.fx
                ay = self.fy + self.fh if i in (0, 1) else self.fy
                sx = -1 if i in (0, 2) else 1
                sy = -1 if i in (0, 1) else 1
                self.drag = ("corner", ax, ay, sx, sy)
                return
        x, y, w, h = self._rect()
        if x <= e.x <= x + w and y <= e.y <= y + h:
            # Chưa biết là bấm hay kéo — chờ xem chuột có đi đủ xa không.
            self.drag = ("maybe", e.x - x, e.y - y, e.x, e.y)

    def _motion(self, e):
        if not self.drag:
            return
        mode = self.drag[0]
        if mode == "maybe":
            _, ox, oy, sx0, sy0 = self.drag
            if abs(e.x - sx0) <= self.DRAG_SLOP and abs(e.y - sy0) <= self.DRAG_SLOP:
                return                      # rung tay vài pixel: vẫn coi là bấm
            self.drag = ("move", ox, oy)
            mode = "move"
        if mode == "move":
            self.fx = self.vx + e.x - self.drag[1]
            self.fy = self.vy + e.y - self.drag[2]
        else:
            _, ax, ay, sx, sy = self.drag
            self.fw = abs(self.vx + e.x - ax)
            self._clamp()
            self.fx = ax if sx > 0 else ax - self.fw
            self.fy = ay if sy > 0 else ay - self.fh
        self._draw()

    def _release(self, e):
        if self.drag and self.drag[0] == "maybe":
            rc = self._cell_at(e.x, e.y)
            if rc is not None:
                if rc in self.cells:
                    self.cells.remove(rc)
                else:
                    self.cells.append(rc)      # thứ tự tick = thứ tự dùng
                self.scan = None
                self._draw()
        self.drag = None

    # ---- vẽ ----
    def _draw(self):
        self._clamp()
        c = self.canvas
        c.delete("all")
        AC, OK, TX = THEME["accent"], THEME["ok"], THEME["text"]
        x, y, w, h = self._rect()
        cw, ch = w / INV_COLS, h / INV_ROWS

        c.create_text(self.vw // 2, 26, fill=TX, font=("Segoe UI", 14),
                      text="Kéo giữa = di chuyển  •  kéo 4 góc = phóng to/thu nhỏ  •  "
                           "mũi tên = 1px, Shift = 10px")
        c.create_text(self.vw // 2, 50, fill=AC, font=("Segoe UI", 13, "bold"),
                      text="BẤM VÀO Ô để chọn ô lấy currency   •   D = đọc thử   •   "
                           "C = xoá hết   •   Enter = lưu   •   Esc = huỷ")

        for i in range(INV_COLS + 1):          # lưới
            c.create_line(x + i * cw, y, x + i * cw, y + h, fill=AC, width=1)
        for j in range(INV_ROWS + 1):
            c.create_line(x, y + j * ch, x + w, y + j * ch, fill=AC, width=1)
        c.create_rectangle(x, y, x + w, y + h, outline=AC, width=2)

        for n, (r, col) in enumerate(self.cells, 1):
            cx0, cy0 = x + col * cw, y + r * ch
            co_hang = None if self.scan is None else self.scan.get((r, col))
            mau = OK if co_hang is None else (OK if co_hang else THEME["err"])
            c.create_rectangle(cx0 + 2, cy0 + 2, cx0 + cw - 2, cy0 + ch - 2,
                               outline=mau, width=3)
            # Số thứ tự phải có NỀN ĐEN ĐẶC lót dưới: overlay chỉ 35% mờ, chữ trần
            # nằm trên icon item lổn nhổn nhiều màu thì gần như không đọc ra.
            # Đặt ở góc dưới-phải để không che mặt item (và không đè số lượng stack
            # mà game vẽ ở góc trên-trái).
            rad = max(11, min(cw, ch) * 0.27)
            bx, by = cx0 + cw - rad - 4, cy0 + ch - rad - 4
            c.create_oval(bx - rad, by - rad, bx + rad, by + rad,
                          fill="#000000", outline=mau, width=2)
            c.create_text(bx, by, fill="#ffffff", text=str(n),
                          font=("Segoe UI", int(rad * 1.1), "bold"))
            if co_hang is not None:
                t = c.create_text(cx0 + cw / 2, cy0 + 12, fill=mau,
                                  font=("Segoe UI", 10, "bold"),
                                  text="CÒN" if co_hang else "HẾT")
                b = c.bbox(t)
                if b:
                    bg = c.create_rectangle(b[0] - 4, b[1] - 2, b[2] + 4, b[3] + 2,
                                            fill="#000000", outline="")
                    c.tag_lower(bg, t)

        for cx, cy in self._corners():
            c.create_rectangle(cx - 5, cy - 5, cx + 5, cy + 5, fill=AC, outline="")
        c.create_text(x, y - 10, anchor="sw", fill=TX, font=("Consolas", 11),
                      text=f"{self.fx}, {self.fy}   {self.fw}×{self.fh}   "
                           f"ô {cw:.0f}×{ch:.0f}px   đã chọn {len(self.cells)} ô")

    # ---- đọc thử ----
    def _test_read(self):
        if not self.cells:
            return
        self.win.withdraw()          # overlay đang che game -> phải ẩn mới chụp được
        self.win.update()
        time.sleep(0.15)
        try:
            ket = core.inv_scan((self.fx, self.fy, self.fw, self.fh), self.cells)
        finally:
            self.win.deiconify()
            self.win.update()
            self.win.focus_force()
            try:
                self.win.grab_set()
            except Exception:
                pass
        self.scan = {(r, c): co for r, c, co, _ in ket}
        self._draw()

    def _finish(self, save):
        try:
            self.win.grab_release()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass
        self.callback(([self.fx, self.fy, self.fw, self.fh],
                       [list(c) for c in self.cells]) if save else None)


# ---------------- Hộp thoại chọn template đã lưu ----------------
