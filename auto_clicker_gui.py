"""
AUTO CLICKER (PoE) — GUI
========================
Lặp một flow hành động (vd: dùng orb lên item) cho tới khi:
  - Đủ số vòng lặp, HOẶC
  - Item có MOD mong muốn (đúng mod + đúng Tier) — đọc bằng cách rê chuột vào
    item rồi Ctrl+C (game copy chữ item ra clipboard).
  - Bất cứ lúc nào: nút DỪNG, phím dừng (mặc định F6), hoặc hất chuột vào góc trên-trái.

Điều kiện mod: chọn từ danh sách (search), không phải gõ tay -> khỏi sai chính tả.
Nhiều dòng = ưu tiên TỪ TRÊN XUỐNG (dòng nào trúng trước thì dừng, báo theo dòng đó).

CHẠY:   python auto_clicker_gui.py
Cần:    pip install pyautogui keyboard pyperclip plyer
Cập nhật list mod: bấm "Cập nhật" trong Cài đặt, hoặc chạy: python update_mods.py
"""

import os
import copy
import json
import time
import queue
import threading
import ctypes

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser

# Lõi (không phụ thuộc giao diện) — xem core.py
import core
from core import *                                    # noqa: F401,F403  (hằng số & hàm dùng chung)
from core import (app_dir, load_settings, save_settings, load_mods, fetch_mod_texts,
                  templates_dir, safe_filename, list_templates, template_path,
                  write_json, read_json, make_loop_template, normalize_loop_template,
                  normalize_process, make_loop_step, make_action_step, make_group_step,
                  is_loop_step, is_group_step, has_actions, make_group_template,
                  normalize_group_template,
                  step_title, step_display, validate_process, action_display,
                  cond_display, parse_hold_keys, ProcessRunner)

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
class TemplatePicker(tk.Toplevel):
    """Liệt kê template đã lưu theo tên. Kết quả đặt ở self.result:
       - đường dẫn file được chọn, hoặc None nếu huỷ."""

    def __init__(self, master, kind, title):
        super().__init__(master)
        self.kind = kind
        self.result = None
        self.title(title)
        self.transient(master)
        self.withdraw()          # dựng xong mới hiện, khỏi loé (xem ActionEditor)
        self.resizable(False, False)

        pad = ttk.Frame(self, padding=12)
        pad.pack(fill="both", expand=True)
        ttk.Label(pad, text=f"Template {TEMPLATE_KINDS.get(kind, kind)} đã lưu "
                            f"(double-click để mở):").pack(anchor="w")

        fr = ttk.Frame(pad)
        fr.pack(fill="both", expand=True, pady=(6, 0))
        sb = ttk.Scrollbar(fr, orient="vertical")
        self.box = tk.Listbox(fr, height=10, width=48, yscrollcommand=sb.set,
                              exportselection=False, activestyle="dotbox")
        sb.config(command=self.box.yview)
        self.box.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.box.bind("<Double-Button-1>", lambda e: self._ok())

        self.empty_lbl = ttk.Label(pad, text="", style="Muted.TLabel")
        self.empty_lbl.pack(anchor="w", pady=(4, 0))

        btns = ttk.Frame(pad)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="📂 Duyệt file khác...", command=self._browse).pack(side="left")
        ttk.Button(btns, text="🗑 Xoá", command=self._delete).pack(side="left", padx=6)
        ttk.Button(btns, text="Mở", command=self._ok).pack(side="right")
        ttk.Button(btns, text="Huỷ", command=self.destroy).pack(side="right", padx=6)

        self._reload()
        restyle_tree(self)
        set_window_icon(self)
        center_window(self, 460, 380)
        dark_titlebar(self)
        self.deiconify()
        self.grab_set()          # hết cần after(80) hoãn binh: cửa sổ đã hiện hẳn

    def _reload(self):
        self.items = list_templates(self.kind)
        self.box.delete(0, tk.END)
        for name, _ in self.items:
            self.box.insert(tk.END, name)
        self.empty_lbl.config(
            text="" if self.items else
            f"(Chưa có template nào trong templates\\{self.kind}\\ — hãy lưu 1 cái trước, "
            f"hoặc bấm \"Duyệt file khác...\")")

    def _sel_path(self):
        s = self.box.curselection()
        return self.items[s[0]][1] if s else None

    def _ok(self):
        p = self._sel_path()
        if not p:
            messagebox.showinfo("Chọn template", "Hãy chọn 1 template trong danh sách.", parent=self)
            return
        self.result = p
        self.destroy()

    def _delete(self):
        p = self._sel_path()
        if not p:
            return
        if not messagebox.askyesno("Xoá template",
                                   f"Xoá template \"{os.path.splitext(os.path.basename(p))[0]}\"?",
                                   parent=self):
            return
        try:
            os.remove(p)
        except Exception as e:
            messagebox.showerror("Lỗi", str(e), parent=self)
            return
        self._reload()

    def _browse(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")],
                                       initialdir=templates_dir(self.kind), parent=self)
        if p:
            self.result = p
            self.destroy()


# ---------------- Hộp thoại thêm/sửa hành động ----------------
class ActionEditor(tk.Toplevel):
    def __init__(self, master, app, action=None):
        super().__init__(master)
        self.app = app
        self.result = None
        self.title("Hành động")
        self.transient(master)
        # ẨN ngay, dựng xong xuôi mới hiện. Không có dòng này thì grab_set() làm Tk
        # hiện cửa sổ ra sớm, và người dùng nhìn thấy nó loé ở góc (0,0) rồi mới
        # nhảy về giữa, đổi bề rộng, tô lại màu, đổi thanh tiêu đề sáng->tối.
        self.withdraw()
        self.resizable(False, False)
        self.type_var = tk.StringVar(value=(action["type"] if action else "left_click"))
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Loại:").grid(row=0, column=0, sticky="w")
        ttk.OptionMenu(top, self.type_var, self.type_var.get(), *ACTION_TYPES,
                       command=lambda _=None: self._render()).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(top, text="Tên:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.name_var = tk.StringVar(value=((action or {}).get("name") or ""))
        ttk.Entry(top, textvariable=self.name_var).grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))
        ttk.Label(top, text="(tuỳ chọn — để trống thì dùng mô tả tự sinh)",
                  style="Muted.TLabel").grid(row=2, column=1, sticky="w", padx=6)
        top.columnconfigure(1, weight=1)
        self.body = ttk.Frame(self, padding=10)
        self.body.pack(fill="x")
        self.x_var = tk.StringVar(value="0")
        self.y_var = tk.StringVar(value="0")
        self.key_var = tk.StringVar(value="enter")
        self.min_var = tk.StringVar(value="200")
        self.max_var = tk.StringVar(value="1000")
        self.search_var = tk.StringVar()
        self.tier_var = tk.StringVar()
        self.hybrid_var = tk.StringVar(value=HYBRID_LABELS[HYBRID_ANY])
        self.k_shift = tk.BooleanVar(value=True)
        self.k_ctrl = tk.BooleanVar(value=False)
        self.k_alt = tk.BooleanVar(value=False)
        self.button_var = tk.StringVar(value="Trái")
        self.minval_var = tk.StringVar()
        self.rerolls_var = tk.StringVar(value=str(ABYSS_DEFAULT_REROLLS))
        self.wait_var = tk.StringVar(value=str(ABYSS_DEFAULT_WAIT_MS))
        self.abyss_frame = None
        self.excl_box = None
        self.wasd_vars = {k: tk.BooleanVar(value=False) for k in ("w", "a", "s", "d")}
        self.move_ms_var = tk.StringVar(value=str(MOVE_DEFAULT_MS))
        self.move_lbl = None
        self.grid_on_var = tk.BooleanVar(value=False)
        self.grid_frame = None
        self.grid_cells = []
        self.grid_lbl = None
        self.conditions = copy.deepcopy(action.get("conditions", [])) if action else []
        self.excludes = copy.deepcopy(action.get("excludes", [])) if action else []
        if action and action.get("type") == "abyss":
            fr = action.get("frame")
            self.abyss_frame = list(fr) if fr else None
            self.rerolls_var.set(str(action.get("rerolls", ABYSS_DEFAULT_REROLLS)))
            self.wait_var.set(str(action.get("wait_ms", ABYSS_DEFAULT_WAIT_MS)))
        if action and action.get("type") == "move_wasd":
            for k in parse_hold_keys(action.get("keys")):
                if k in self.wasd_vars:
                    self.wasd_vars[k].set(True)
            self.move_ms_var.set(str(action.get("ms", MOVE_DEFAULT_MS)))
        if action and (action.get("grid") or {}).get("frame"):
            g = action["grid"]
            self.grid_on_var.set(True)
            self.grid_frame = list(g["frame"])
            self.grid_cells = [list(c) for c in (g.get("cells") or [])]
        if action and action.get("type") == "mod_click":
            keys = parse_hold_keys(action.get("keys"))
            self.k_shift.set("shift" in keys)
            self.k_ctrl.set("ctrl" in keys)
            self.k_alt.set("alt" in keys)
            self.button_var.set("Trái" if action.get("button", "left") == "left" else "Phải")
        if action:
            if "point" in action:
                pt = action.get("point")
                if pt:
                    self.x_var.set(pt[0])
                    self.y_var.set(pt[1])
            if action["type"] == "key_press":
                self.key_var.set(action.get("key", "enter"))
            if action["type"] == "delay":
                self.min_var.set(action.get("min_ms", 200))
                self.max_var.set(action.get("max_ms", 1000))
        btns = ttk.Frame(self, padding=10)
        btns.pack(fill="x", side="bottom")
        ttk.Button(btns, text="Lưu", command=self._save).pack(side="right")
        ttk.Button(btns, text="Huỷ", command=self.destroy).pack(side="right", padx=6)
        self._render()
        # Kích thước cố định, đủ rộng cho MỌI loại hành động (kể cả "Kiểm tra mod"
        # — loại nhiều nội dung nhất) — tránh bị cắt chữ khi đổi loại, vì đổi Loại
        # chỉ vẽ lại nội dung chứ cửa sổ không tự phóng lại.
        restyle_tree(self)
        set_window_icon(self)
        self._fit_window(center=True)
        dark_titlebar(self)
        self.deiconify()        # giờ mới hiện — đã hoàn chỉnh, không còn gì để sửa
        self.grab_set()         # grab đòi cửa sổ đang hiện, nên phải sau deiconify

    # Bề rộng CỐ ĐỊNH cho mọi loại: loại rộng nhất cần 470px nên vẫn dư, mà giữ
    # nguyên bề rộng thì đổi Loại cửa sổ chỉ co giãn theo chiều dọc, nhìn êm —
    # co cả hai chiều sẽ giật qua giật lại.
    WIDTH = 520

    def _fit_window(self, center=False):
        """Cho cửa sổ vừa khít nội dung của loại hành động đang chọn.

        KHÔNG ép chiều cao bằng geometry: minsize giữ bề rộng 520, còn CHIỀU CAO
        để Tk tự co theo nội dung. Ép chiều cao từng làm hộp thoại Cài đặt bị cắt
        cụt trong bản đóng gói — winfo_reqheight() có lúc chưa tính xong mà cửa sổ
        lại không cho co giãn nên hỏng vĩnh viễn. Tự co thì luôn đúng."""
        self.minsize(self.WIDTH, 1)
        self.update_idletasks()
        h = max(self.winfo_height(), self.winfo_reqheight())
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        if center:
            x = max(0, (sw - self.WIDTH) // 2)
            y = max(0, (sh - h) // 2 - 30)
        else:
            # Đổi Loại thì GIỮ NGUYÊN chỗ cửa sổ đang đứng — nhảy về giữa màn hình
            # mỗi lần đổi Loại rất khó chịu. Chỉ đẩy lên nếu sắp tràn đáy.
            x = max(0, min(self.winfo_x(), sw - self.WIDTH))
            y = max(0, min(self.winfo_y(), sh - h - 40))
        self.geometry(f"+{x}+{y}")

    def _render(self):
        for w in self.body.winfo_children():
            w.destroy()
        t = self.type_var.get()
        if t == "check_mod":
            self._render_check_mod()
        elif t == "abyss":
            self._render_abyss()
        elif t in POINT_TYPES:
            ttk.Label(self.body, text="X:").grid(row=0, column=0, sticky="w")
            self.x_entry = ttk.Entry(self.body, textvariable=self.x_var, width=8)
            self.x_entry.grid(row=0, column=1)
            ttk.Label(self.body, text="Y:").grid(row=0, column=2, sticky="w", padx=(10, 0))
            self.y_entry = ttk.Entry(self.body, textvariable=self.y_var, width=8)
            self.y_entry.grid(row=0, column=3)
            self.pick_btn = ttk.Button(self.body, text="🎯 Chọn điểm (crosshair)",
                                       command=self._pick)
            self.pick_btn.grid(row=1, column=0, columnspan=4, pady=(8, 0), sticky="ew")
            if t == "right_click":
                self._render_grid_advanced(row=2)
        elif t == "mod_click":
            # 3 ô tick, KHÔNG dùng ttk.Combobox. Dropdown của Combobox chiếm grab
            # TOÀN CỤC (ttk::combobox::MapPopdown -> ttk::globalGrab -> grab -global)
            # ngay bên trong hộp thoại vốn đã grab_set() -> có lúc không trả grab
            # lại được và cả máy ngừng nhận chuột/phím. Ô tick không grab gì cả,
            # lại chặn luôn được lỗi gõ sai tên phím.
            ttk.Label(self.body, text="Giữ phím:").grid(row=0, column=0, sticky="w")
            kf = ttk.Frame(self.body)
            kf.grid(row=0, column=1, columnspan=2, sticky="w", padx=4)
            for label, var in (("Shift", self.k_shift), ("Ctrl", self.k_ctrl),
                               ("Alt", self.k_alt)):
                ttk.Checkbutton(kf, text=label, variable=var).pack(side="left", padx=(0, 12))
            ttk.Label(self.body, text="Nút chuột:").grid(row=0, column=3, sticky="w", padx=(10, 0))
            ttk.OptionMenu(self.body, self.button_var, self.button_var.get(),
                           "Trái", "Phải").grid(row=0, column=4, sticky="w")
            ttk.Label(self.body, text="(tick được nhiều phím cùng lúc, vd Ctrl + Shift)",
                      style="Muted.TLabel").grid(row=1, column=0, columnspan=5, sticky="w",
                                                 pady=(2, 6))
            ttk.Label(self.body, text="X:").grid(row=2, column=0, sticky="w")
            ttk.Entry(self.body, textvariable=self.x_var, width=8).grid(row=2, column=1, sticky="w")
            ttk.Label(self.body, text="Y:").grid(row=2, column=2, sticky="w", padx=(10, 0))
            ttk.Entry(self.body, textvariable=self.y_var, width=8).grid(row=2, column=3, sticky="w")
            ttk.Button(self.body, text="🎯 Chọn điểm (crosshair)", command=self._pick).grid(
                row=3, column=0, columnspan=4, pady=(8, 0), sticky="ew")
        elif t == "move_wasd":
            self._render_move_wasd()
        elif t == "key_press":
            ttk.Label(self.body, text="Phím (vd: enter, a, space, escape):").grid(row=0, column=0, sticky="w")
            ttk.Entry(self.body, textvariable=self.key_var, width=14).grid(row=0, column=1, padx=6)
        elif t == "delay":
            ttk.Label(self.body, text="Min ms:").grid(row=0, column=0, sticky="w")
            ttk.Entry(self.body, textvariable=self.min_var, width=8).grid(row=0, column=1)
            ttk.Label(self.body, text="Max ms:").grid(row=0, column=2, sticky="w", padx=(10, 0))
            ttk.Entry(self.body, textvariable=self.max_var, width=8).grid(row=0, column=3)
        # Tô màu NGAY, không hoãn sang vòng nhàn rỗi: widget tk cổ điển (Listbox…)
        # sinh ra với nền trắng, hoãn lại là loé trắng một khung hình khi đổi Loại.
        restyle_tree(self.body)
        # Vẽ lại ruột xong thì co giãn cửa sổ theo. Bỏ dòng này là quay lại đúng
        # cái bệnh cũ: đổi Loại mà cửa sổ đứng im -> loại nhỏ trống, loại to bị cắt.
        self._fit_window()

    def _render_move_wasd(self):
        """4 ô tick xếp đúng hình phím WASD. Tick W thì S tự bỏ (và A/D cũng vậy),
        nên KHÔNG THỂ tạo ra tổ hợp ngược chiều hay quá 2 phím — luật tự thoả mãn,
        không cần hộp báo lỗi nào."""
        ttk.Label(self.body, text="Hướng đi:").grid(row=0, column=0, sticky="nw", pady=(2, 0))
        pad = ttk.Frame(self.body)
        pad.grid(row=0, column=1, sticky="w", padx=(4, 0))
        ttk.Checkbutton(pad, text="W", variable=self.wasd_vars["w"],
                        command=lambda: self._wasd_toggled("w")).grid(row=0, column=1, padx=2)
        ttk.Checkbutton(pad, text="A", variable=self.wasd_vars["a"],
                        command=lambda: self._wasd_toggled("a")).grid(row=1, column=0, padx=2)
        ttk.Checkbutton(pad, text="S", variable=self.wasd_vars["s"],
                        command=lambda: self._wasd_toggled("s")).grid(row=1, column=1, padx=2)
        ttk.Checkbutton(pad, text="D", variable=self.wasd_vars["d"],
                        command=lambda: self._wasd_toggled("d")).grid(row=1, column=2, padx=2)

        r = ttk.Frame(self.body)
        r.grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Label(r, text="Giữ trong:").pack(side="left")
        ttk.Entry(r, textvariable=self.move_ms_var, width=8).pack(side="left", padx=4)
        ttk.Label(r, text="ms").pack(side="left")
        self.move_ms_var.trace_add("write", lambda *_: self._refresh_move_label())

        self.move_lbl = ttk.Label(self.body, style="Muted.TLabel", text="")
        self.move_lbl.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(self.body, style="Muted.TLabel",
                  text="W/S và A/D ngược chiều nhau nên không tick cùng lúc được —\n"
                       "tick cái này thì cái kia tự bỏ. Đang giữ mà bấm Dừng/F6 thì nhả ngay."
                  ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self._refresh_move_label()

    def _wasd_toggled(self, key):
        """Tick 1 hướng -> tự bỏ hướng ngược lại."""
        if self.wasd_vars[key].get():
            self.wasd_vars[WASD_OPPOSITE[key]].set(False)
        self._refresh_move_label()

    def _wasd_keys(self):
        return wasd_sort([k for k, v in self.wasd_vars.items() if v.get()])

    def _refresh_move_label(self):
        if not getattr(self, "move_lbl", None):
            return
        ks = self._wasd_keys()
        if not ks:
            self.move_lbl.config(text="→ chưa chọn hướng nào")
            return
        try:
            ms = int(self.move_ms_var.get() or 0)
        except ValueError:
            ms = 0
        self.move_lbl.config(text=f"→ giữ {wasd_display(ks)} trong {ms} ms "
                                  f"({ms / 1000:.1f} giây)")

    def _render_grid_advanced(self, row):
        """Tuỳ chọn NÂNG CAO của right_click: lấy từ nhiều ô, hết ô này sang ô sau.
        Không tick thì mọi thứ y như cũ, file lưu ra cũng không có khoá thừa."""
        ttk.Separator(self.body, orient="horizontal").grid(
            row=row, column=0, columnspan=4, sticky="ew", pady=(12, 8))
        ttk.Checkbutton(self.body, variable=self.grid_on_var, command=self._toggle_grid,
                        text="Nâng cao: lấy từ nhiều ô, hết ô này tự sang ô khác"
                        ).grid(row=row + 1, column=0, columnspan=4, sticky="w")
        gf = ttk.Frame(self.body)
        gf.grid(row=row + 2, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.grid_btn = ttk.Button(gf, text="🖼 Căn lưới", command=self._calibrate_grid)
        self.grid_btn.pack(side="left")
        self.grid_lbl = ttk.Label(gf, text="", style="Muted.TLabel")
        self.grid_lbl.pack(side="left", padx=(8, 0))
        ttk.Label(self.body, style="Muted.TLabel",
                  text="Tick sẵn những ô CHỨA ĐÚNG loại currency cần dùng.\n"
                       "App tự nhìn ô nào còn hàng — không đếm, không nhớ, nên bỏ thêm\n"
                       "currency giữa chừng hay chạy lại đều đúng. Hết sạch thì DỪNG."
                  ).grid(row=row + 3, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self._toggle_grid()

    def _toggle_grid(self):
        """Bật lưới thì X/Y vô nghĩa -> làm mờ, cho khỏi hiểu nhầm."""
        on = self.grid_on_var.get()
        for w in (self.x_entry, self.y_entry, self.pick_btn):
            try:
                w.config(state="disabled" if on else "normal")
            except tk.TclError:
                pass
        try:
            self.grid_btn.config(state="normal" if on else "disabled")
        except tk.TclError:
            pass
        self._refresh_grid_label()

    def _refresh_grid_label(self):
        if not getattr(self, "grid_lbl", None):
            return
        if not self.grid_on_var.get():
            self.grid_lbl.config(text="(đang tắt — dùng đúng 1 điểm X/Y ở trên)")
        elif not self.grid_frame:
            self.grid_lbl.config(text="chưa căn lưới")
        else:
            f = self.grid_frame
            self.grid_lbl.config(text=f"({f[0]}, {f[1]}) {f[2]}×{f[3]}  ·  "
                                      f"đã tick {len(self.grid_cells)} ô")

    def _calibrate_grid(self):
        def done(res):
            if res:
                self.grid_frame, self.grid_cells = res
            self._refresh_grid_label()

        self.app.pick_inv_grid(self.grid_frame, self.grid_cells, done, hide=self)

    def _render_check_mod(self):
        ttk.Label(self.body, text='Item sẽ "biến mất" nếu khớp — dừng cả Loop, coi như đã đạt.',
                  style="Muted.TLabel").pack(anchor="w")

        row = ttk.Frame(self.body)
        row.pack(fill="x", pady=(6, 0))
        ttk.Label(row, text="Rê chuột tới item — X:").pack(side="left")
        ttk.Entry(row, textvariable=self.x_var, width=8).pack(side="left", padx=(4, 10))
        ttk.Label(row, text="Y:").pack(side="left")
        ttk.Entry(row, textvariable=self.y_var, width=8).pack(side="left", padx=4)
        ttk.Button(self.body, text="🎯 Chọn điểm (crosshair)", command=self._pick).pack(
            fill="x", pady=(4, 10))

        ttk.Label(self.body, text="Tìm mod:").pack(anchor="w")
        se = ttk.Entry(self.body, textvariable=self.search_var)
        se.pack(fill="x")
        se.bind("<KeyRelease>", self._refresh_mods)

        mfr = ttk.Frame(self.body)
        mfr.pack(fill="x", pady=(4, 0))
        msb = ttk.Scrollbar(mfr, orient="vertical")
        self.master_box = tk.Listbox(mfr, height=5, yscrollcommand=msb.set, exportselection=False)
        msb.config(command=self.master_box.yview)
        self.master_box.pack(side="left", fill="both", expand=True)
        msb.pack(side="right", fill="y")
        self.master_box.bind("<Double-Button-1>", lambda e: self._add_condition())

        r3 = ttk.Frame(self.body)
        r3.pack(fill="x", pady=(4, 0))
        ttk.Label(r3, text="Tier (trống = mọi):").pack(side="left")
        ttk.Entry(r3, textvariable=self.tier_var, width=6).pack(side="left", padx=(4, 10))
        ttk.Label(r3, text="Loại mod:").pack(side="left")
        ttk.OptionMenu(r3, self.hybrid_var, self.hybrid_var.get(),
                       *HYBRID_LABELS.values()).pack(side="left", padx=(4, 0))
        r3b = ttk.Frame(self.body)
        r3b.pack(fill="x", pady=(2, 0))
        ttk.Label(r3b, style="Muted.TLabel",
                  text="mod hybrid = 1 affix cho nhiều dòng stat (vd Armour + Energy Shield);\n"
                       "tier của họ hybrid KHÁC tier của mod thuần cùng tên").pack(anchor="w")
        ttk.Button(r3b, text="➕ Thêm điều kiện ↓", command=self._add_condition).pack(
            anchor="w", pady=(4, 0))

        ttk.Label(self.body, text="Điều kiện — dòng TRÊN ưu tiên trước (kéo-thả để đổi thứ tự):").pack(
            anchor="w", pady=(10, 2))
        cfr = ttk.Frame(self.body)
        cfr.pack(fill="both", expand=True)
        csb = ttk.Scrollbar(cfr, orient="vertical")
        self.cond_box = tk.Listbox(cfr, height=4, yscrollcommand=csb.set, exportselection=False)
        csb.config(command=self.cond_box.yview)
        self.cond_box.pack(side="left", fill="both", expand=True)
        csb.pack(side="right", fill="y")
        self.app._enable_drag_reorder(self.cond_box, lambda: self.conditions, self._refresh_conds)

        r6 = ttk.Frame(self.body)
        r6.pack(fill="x", pady=(4, 0))
        ttk.Button(r6, text="🗑 Xoá", command=self._del_condition).pack(side="left")
        ttk.Button(r6, text="⬆ Lên", command=lambda: self._move_condition(-1)).pack(side="left", padx=4)
        ttk.Button(r6, text="⬇ Xuống", command=lambda: self._move_condition(1)).pack(side="left")

        self._refresh_mods()
        self._refresh_conds()

    def _render_abyss(self):
        ttk.Label(self.body, style="Muted.TLabel",
                  text="Panel Abyss không Ctrl+C được → app ĐỌC CHỮ bằng ảnh.\n"
                       "Bấm REVEAL → quét 3 ô → khớp thì chọn ô đó + CONFIRM rồi DỪNG Loop;\n"
                       "không khớp thì bấm refresh (nếu có) → quét lại → vẫn không thì chọn\n"
                       "bừa 1 ô KHÔNG bị loại trừ + CONFIRM rồi chạy tiếp vòng sau."
                  ).pack(anchor="w")

        reason = core.ocr_unavailable_reason()
        if reason:
            ttk.Label(self.body, text=f"⚠ {reason}", foreground=THEME["err"],
                      wraplength=470, justify="left").pack(anchor="w", pady=(6, 0))

        fr = ttk.Frame(self.body)
        fr.pack(fill="x", pady=(8, 0))
        ttk.Button(fr, text="🖼 Căn khung Abyss", command=self._calibrate).pack(side="left")
        self.frame_label = ttk.Label(fr, text="", style="Muted.TLabel")
        self.frame_label.pack(side="left", padx=(8, 0))
        self._refresh_frame_label()

        r2 = ttk.Frame(self.body)
        r2.pack(fill="x", pady=(8, 0))
        ttk.Label(r2, text="Số lần reroll:").pack(side="left")
        ttk.Entry(r2, textvariable=self.rerolls_var, width=5).pack(side="left", padx=(4, 12))
        ttk.Label(r2, text="Chờ sau mỗi lần bấm (ms):").pack(side="left")
        ttk.Entry(r2, textvariable=self.wait_var, width=6).pack(side="left", padx=4)

        ttk.Label(self.body, text="Tìm mod:").pack(anchor="w", pady=(10, 0))
        se = ttk.Entry(self.body, textvariable=self.search_var)
        se.pack(fill="x")
        se.bind("<KeyRelease>", self._refresh_mods)

        mfr = ttk.Frame(self.body)
        mfr.pack(fill="x", pady=(4, 0))
        msb = ttk.Scrollbar(mfr, orient="vertical")
        self.master_box = tk.Listbox(mfr, height=5, yscrollcommand=msb.set, exportselection=False)
        msb.config(command=self.master_box.yview)
        self.master_box.pack(side="left", fill="both", expand=True)
        msb.pack(side="right", fill="y")
        self.master_box.bind("<Double-Button-1>", lambda e: self._add_condition())

        r4 = ttk.Frame(self.body)
        r4.pack(fill="x", pady=(4, 0))
        ttk.Label(r4, text="Ngưỡng số tối thiểu (trống = mọi giá trị):").pack(side="left")
        ttk.Entry(r4, textvariable=self.minval_var, width=7).pack(side="left", padx=4)
        ttk.Label(self.body, style="Muted.TLabel",
                  text="Panel Abyss KHÔNG hiện tier — dùng ngưỡng số thay cho tier.\n"
                       "Mod 2 số (vd \"Adds # to # Chaos damage\") so theo giá trị trung bình."
                  ).pack(anchor="w", pady=(2, 0))

        r5 = ttk.Frame(self.body)
        r5.pack(fill="x", pady=(4, 0))
        ttk.Button(r5, text="➕ Thêm điều kiện ↓", command=self._add_condition).pack(side="left")
        ttk.Button(r5, text="⛔ Thêm vào loại trừ ↓", command=self._add_exclude).pack(
            side="left", padx=(8, 0))

        ttk.Label(self.body, text="Điều kiện — dòng TRÊN ưu tiên trước (kéo-thả để đổi thứ tự):"
                  ).pack(anchor="w", pady=(10, 2))
        cfr = ttk.Frame(self.body)
        cfr.pack(fill="both", expand=True)
        csb = ttk.Scrollbar(cfr, orient="vertical")
        self.cond_box = tk.Listbox(cfr, height=4, yscrollcommand=csb.set, exportselection=False)
        csb.config(command=self.cond_box.yview)
        self.cond_box.pack(side="left", fill="both", expand=True)
        csb.pack(side="right", fill="y")
        self.cond_box.bind("<Delete>", lambda e: (self._del_condition(), "break")[1])
        self.app._enable_drag_reorder(self.cond_box, lambda: self.conditions, self._refresh_conds)

        r6 = ttk.Frame(self.body)
        r6.pack(fill="x", pady=(4, 0))
        ttk.Button(r6, text="🗑 Xoá", command=self._del_condition).pack(side="left")
        ttk.Button(r6, text="⬆ Lên", command=lambda: self._move_condition(-1)).pack(side="left", padx=4)
        ttk.Button(r6, text="⬇ Xuống", command=lambda: self._move_condition(1)).pack(side="left")

        # Bảng loại trừ: KHÔNG có Lên/Xuống vì thứ tự vô nghĩa — nó là một tập hợp
        # "cấm chốt", không phải danh sách ưu tiên.
        ttk.Label(self.body, text="⛔ Loại trừ — không bao giờ chốt mấy mod này, "
                                  "kể cả lúc phải chọn bừa:").pack(anchor="w", pady=(10, 2))
        efr = ttk.Frame(self.body)
        efr.pack(fill="both", expand=True)
        esb = ttk.Scrollbar(efr, orient="vertical")
        self.excl_box = tk.Listbox(efr, height=4, yscrollcommand=esb.set, exportselection=False)
        esb.config(command=self.excl_box.yview)
        self.excl_box.pack(side="left", fill="both", expand=True)
        esb.pack(side="right", fill="y")
        self.excl_box.bind("<Delete>", lambda e: (self._del_exclude(), "break")[1])

        r7 = ttk.Frame(self.body)
        r7.pack(fill="x", pady=(4, 0))
        ttk.Button(r7, text="🗑 Xoá", command=self._del_exclude).pack(side="left")
        ttk.Label(r7, style="Muted.TLabel",
                  text="  cả 3 ô đều bị loại trừ → reroll; hết reroll thì DỪNG, không chốt bừa"
                  ).pack(side="left", padx=(8, 0))

        self._refresh_mods()
        self._refresh_conds()
        self._refresh_excludes()

    def _refresh_frame_label(self):
        if not getattr(self, "frame_label", None):
            return
        fr = self.abyss_frame
        self.frame_label.config(
            text=(f"({fr[0]}, {fr[1]})  {fr[2]}×{fr[3]}" if fr else "chưa căn khung"))

    def _calibrate(self):
        def done(fr):
            self.abyss_frame = list(fr)
            self._refresh_frame_label()

        self.app.pick_abyss_frame(self.abyss_frame, done, hide=self)

    def _refresh_mods(self, *_):
        q = self.search_var.get().strip().lower()
        words = q.split()
        self.master_box.delete(0, tk.END)
        shown = 0
        for m in self.app.all_mods:
            ml = m.lower()
            if all(w in ml for w in words):
                self.master_box.insert(tk.END, m)
                shown += 1
                if shown >= MOD_LIST_DISPLAY_CAP:
                    break

    def _add_condition(self):
        sel = self.master_box.curselection()
        if not sel:
            messagebox.showinfo("Chọn mod", "Hãy chọn 1 mod trong danh sách trước.", parent=self)
            return
        mod = self.master_box.get(sel[0])
        if self.type_var.get() == "abyss":
            mv = self.minval_var.get().strip()
            cond = {"mod": mod}
            if mv:
                try:
                    val = float(mv.replace(",", "."))
                except ValueError:
                    messagebox.showerror("Ngưỡng", "Ngưỡng phải là số (hoặc để trống).",
                                         parent=self)
                    return
                cond["min_value"] = int(val) if val == int(val) else val
            self.conditions.append(cond)
            self._refresh_conds()
            return
        tv = self.tier_var.get().strip()
        tier = None
        if tv:
            try:
                tier = int(tv)
            except ValueError:
                messagebox.showerror("Tier", "Tier phải là số (hoặc để trống).", parent=self)
                return
        cond = {"mod": mod, "tier": tier}
        mode = HYBRID_FROM_LABEL.get(self.hybrid_var.get(), HYBRID_ANY)
        if mode != HYBRID_ANY:          # "Cả hai" là mặc định -> không cần ghi
            cond["hybrid"] = mode
        self.conditions.append(cond)
        self._refresh_conds()

    def _refresh_conds(self):
        disp = core.abyss_cond_display if self.type_var.get() == "abyss" else cond_display
        self.cond_box.delete(0, tk.END)
        for i, c in enumerate(self.conditions, 1):
            self.cond_box.insert(tk.END, f"{i}.  {disp(c)}")

    # ---- bảng loại trừ (chỉ có ở Abyss) ----
    def _add_exclude(self):
        sel = self.master_box.curselection()
        if not sel:
            messagebox.showinfo("Chọn mod", "Hãy chọn 1 mod trong danh sách trước.", parent=self)
            return
        mod = self.master_box.get(sel[0])
        if any(e.get("mod") == mod for e in self.excludes):
            return                          # đã có rồi, thêm nữa cũng vô nghĩa
        self.excludes.append({"mod": mod})
        self._refresh_excludes()

    def _del_exclude(self):
        s = self.excl_box.curselection()
        if not s:
            return
        del self.excludes[s[0]]
        self._refresh_excludes()

    def _refresh_excludes(self):
        if not getattr(self, "excl_box", None):
            return
        self.excl_box.delete(0, tk.END)
        for i, e in enumerate(self.excludes, 1):
            self.excl_box.insert(tk.END, f"{i}.  {e.get('mod', '')}")

    def _cond_sel(self):
        s = self.cond_box.curselection()
        return s[0] if s else None

    def _del_condition(self):
        i = self._cond_sel()
        if i is None:
            return
        del self.conditions[i]
        self._refresh_conds()

    def _move_condition(self, d):
        i = self._cond_sel()
        if i is None:
            return
        j = i + d
        if 0 <= j < len(self.conditions):
            self.conditions[i], self.conditions[j] = self.conditions[j], self.conditions[i]
            self._refresh_conds()
            self.cond_box.selection_set(j)

    def _pick(self):
        self.app.pick_point(self._on_pick, hide=self)

    def _on_pick(self, pt):
        self.x_var.set(pt[0])
        self.y_var.set(pt[1])

    def _save(self):
        t = self.type_var.get()
        try:
            if t == "check_mod":
                if not self.conditions:
                    raise ValueError("chưa thêm điều kiện mod nào")
                try:
                    x, y = int(self.x_var.get()), int(self.y_var.get())
                    point = [x, y]
                except ValueError:
                    point = None
                a = {"type": t, "point": point, "conditions": [dict(c) for c in self.conditions]}
            elif t == "abyss":
                if not self.abyss_frame:
                    raise ValueError("chưa căn khung Abyss")
                if not self.conditions:
                    raise ValueError("chưa thêm điều kiện mod nào")
                rr = int(self.rerolls_var.get())
                if not 0 <= rr <= ABYSS_MAX_REROLLS:
                    raise ValueError(f"số lần reroll phải từ 0 đến {ABYSS_MAX_REROLLS}")
                wm = int(self.wait_var.get())
                if wm < 0:
                    raise ValueError("thời gian chờ không hợp lệ")
                a = {"type": t,
                     "frame": [int(v) for v in self.abyss_frame],
                     "conditions": [dict(c) for c in self.conditions],
                     "rerolls": rr, "wait_ms": wm,
                     }
                if self.excludes:          # rỗng thì không ghi, cho file gọn
                    a["excludes"] = [dict(e) for e in self.excludes]
            elif t == "mod_click":
                keys = [k for k, v in (("ctrl", self.k_ctrl), ("shift", self.k_shift),
                                       ("alt", self.k_alt)) if v.get()]
                if not keys:
                    raise ValueError("chưa tick phím nào cần giữ")
                a = {"type": t,
                     "point": [int(self.x_var.get()), int(self.y_var.get())],
                     "keys": "+".join(keys),
                     "button": "left" if self.button_var.get() == "Trái" else "right"}
            elif t in POINT_TYPES:
                if t == "right_click" and self.grid_on_var.get():
                    if not self.grid_frame:
                        raise ValueError("bật \"lấy từ nhiều ô\" thì phải căn lưới trước")
                    if not self.grid_cells:
                        raise ValueError("chưa tick ô nào trong lưới")
                    a = {"type": t,
                         "point": [int(self.x_var.get() or 0), int(self.y_var.get() or 0)],
                         "grid": {"frame": [int(v) for v in self.grid_frame],
                                  "cells": [[int(c[0]), int(c[1])] for c in self.grid_cells]}}
                else:
                    a = {"type": t, "point": [int(self.x_var.get()), int(self.y_var.get())]}
            elif t == "move_wasd":
                ks = self._wasd_keys()
                if not ks:
                    raise ValueError("chưa tick hướng đi nào")
                ms = int(self.move_ms_var.get())
                if ms <= 0:
                    raise ValueError("thời gian giữ phải lớn hơn 0 ms")
                a = {"type": t, "keys": "+".join(ks), "ms": ms}
            elif t == "key_press":
                k = self.key_var.get().strip()
                if not k:
                    raise ValueError("chưa nhập phím")
                a = {"type": t, "key": k}
            elif t == "delay":
                lo, hi = int(self.min_var.get()), int(self.max_var.get())
                if lo < 0 or hi < lo:
                    raise ValueError("min/max không hợp lệ")
                a = {"type": t, "min_ms": lo, "max_ms": hi}
            else:
                raise ValueError("loại không hợp lệ")
        except ValueError as e:
            messagebox.showerror("Lỗi", f"Giá trị không hợp lệ: {e}", parent=self)
            return
        nm = self.name_var.get().strip()
        if nm:                      # để trống -> không lưu trường name, dùng mô tả tự sinh
            a["name"] = nm
        self.result = a
        self.destroy()


# ---------------- Hộp thoại Cài đặt ----------------
class SettingsDialog(tk.Toplevel):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        s = app.settings
        self.title("⚙ Cài đặt")
        self.transient(master)
        self.withdraw()          # dựng xong mới hiện, khỏi loé (xem ActionEditor)
        self.resizable(False, False)
        pad = ttk.Frame(self, padding=12)
        pad.pack(fill="both", expand=True)

        ttk.Label(pad, text="Game:").grid(row=0, column=0, sticky="w", pady=3)
        self.game_var = tk.StringVar(value=GAMES.get(s["game"], "PoE2"))
        ttk.OptionMenu(pad, self.game_var, self.game_var.get(), *GAMES.values()).grid(
            row=0, column=1, sticky="w", pady=3)

        self.pre_var = tk.StringVar(value=str(s["pre_click_ms"]))
        self.hover_var = tk.StringVar(value=str(s["hover_ms"]))
        self.copy_var = tk.StringVar(value=s["copy_keys"])
        self.hotkey_var = tk.StringVar(value=s["stop_hotkey"])
        rows = [
            ("Delay trước click (ms):", self.pre_var),
            ("Chờ tooltip hiện (ms):", self.hover_var),
            ("Phím copy item:", self.copy_var),
            ("Phím dừng khẩn:", self.hotkey_var),
        ]
        for i, (lbl, var) in enumerate(rows, start=1):
            ttk.Label(pad, text=lbl).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Entry(pad, textvariable=var, width=12).grid(row=i, column=1, sticky="w", pady=3)

        # ---- Màu nhấn (đổi được, áp ngay không cần khởi động lại) ----
        col = ttk.LabelFrame(pad, text="Giao diện", padding=8)
        col.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Label(col, text="Màu nhấn:").grid(row=0, column=0, sticky="w")
        cur = THEME["accent"]
        name = next((n for n, c in ACCENT_PRESETS.items() if c.lower() == cur.lower()),
                    "Tuỳ chỉnh")
        self.accent_var = tk.StringVar(value=name)
        self._accent_color = cur
        ttk.OptionMenu(col, self.accent_var, name, *ACCENT_PRESETS.keys(),
                       command=self._pick_preset_accent).grid(row=0, column=1, sticky="w", padx=6)
        self.swatch = tk.Label(col, text="   ", bg=cur, relief="solid", borderwidth=1)
        self.swatch.grid(row=0, column=2, sticky="w", padx=(2, 6))
        ttk.Button(col, text="Tuỳ chọn…", command=self._pick_custom_accent).grid(
            row=0, column=3, sticky="w")
        ttk.Label(col, text="(đổi là thấy ngay)", style="Muted.TLabel").grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(4, 0))

        upd = ttk.LabelFrame(pad, text="Danh sách mod", padding=8)
        upd.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(upd, text="⟳ Cập nhật từ mạng", command=self._update_mods).grid(row=0, column=0)
        self.upd_status = ttk.Label(upd, text="")
        self.upd_status.grid(row=0, column=1, sticky="w", padx=8)
        self._refresh_count()

        btns = ttk.Frame(pad)
        btns.grid(row=7, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Lưu & đóng", command=self._save).pack(side="right")
        ttk.Button(btns, text="Huỷ", command=self.destroy).pack(side="right", padx=6)
        restyle_tree(self)
        set_window_icon(self)
        center_window(self)
        dark_titlebar(self)
        self.deiconify()
        self.grab_set()

    # ---- màu nhấn ----
    def _apply_accent(self, color):
        self._accent_color = color
        set_accent(color)
        self.swatch.config(bg=color)
        apply_theme(self.app.root)      # cả cửa sổ chính
        restyle_tree(self)              # và chính hộp thoại này
        self.app.refresh_steps()        # vẽ lại danh sách để ăn màu chọn mới
        self.app.refresh()

    def _pick_preset_accent(self, name=None):
        color = ACCENT_PRESETS.get(self.accent_var.get())
        if color:
            self._apply_accent(color)

    def _pick_custom_accent(self):
        rgb, hexv = colorchooser.askcolor(color=self._accent_color,
                                          title="Chọn màu nhấn", parent=self)
        if hexv:
            self.accent_var.set("Tuỳ chỉnh")
            self._apply_accent(hexv)

    def _game_key(self):
        for k, v in GAMES.items():
            if v == self.game_var.get():
                return k
        return "poe2"

    def _refresh_count(self):
        n = len(load_mods(self._game_key()))
        self.upd_status.config(text=f"{n} mod (game hiện chọn)")

    def _update_mods(self):
        game = self._game_key()
        self.upd_status.config(text="Đang tải...")

        def worker():
            try:
                texts = fetch_mod_texts(game)
                with open(core.writable_data_path(f"mods_{game}.txt"), "w", encoding="utf-8") as f:
                    f.write("\n".join(texts))
                msg = f"Đã cập nhật: {len(texts)} mod"
            except Exception as e:
                msg = f"Lỗi: {type(e).__name__}"
            self.after(0, lambda: (self.upd_status.config(text=msg), self.app.reload_mods()))

        threading.Thread(target=worker, daemon=True).start()

    def _save(self):
        try:
            pre = max(0, int(self.pre_var.get() or 0))
            hov = max(0, int(self.hover_var.get() or 0))
        except ValueError:
            messagebox.showerror("Lỗi", "Delay/Chờ phải là số.", parent=self)
            return
        self.app.settings.update({
            "game": self._game_key(),
            "pre_click_ms": pre,
            "hover_ms": hov,
            "copy_keys": self.copy_var.get().strip() or "ctrl+c",
            "stop_hotkey": self.hotkey_var.get().strip() or "f6",
            "accent": self._accent_color,
        })
        save_settings(self.app.settings)
        self.app.apply_settings()
        self.destroy()


# ---------------- App chính ----------------
class AutoClickerApp:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        # ---- Mô hình 3 tầng: Process ▸ các BƯỚC (Action_Loop hoặc hành động lẻ) ▸ Action ----
        self.process_name = "Process 1"
        self.steps = [make_loop_step("Loop 1")]
        self.cur = 0                     # chỉ số bước đang chọn
        self.all_mods = load_mods(self.settings["game"])
        self.stop_flag = threading.Event()
        self.hotkey_handle = None
        self.hotkey_raw = None
        self._rename_entry = None
        self._hotkey_label = "F6"
        self._log_q = queue.Queue()      # worker thread -> UI, gom lại rồi vẽ 1 lượt
        self._pump_after_id = None
        center_window(root, 980, 780)
        self._build_ui()
        apply_theme(root)              # tô màu sau khi widget đã dựng xong
        self.refresh_steps()
        self.select_step(0)
        self.apply_settings()
        self._pump_log()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _remove_hotkeys(self):
        """Gỡ CẢ HAI kiểu đăng ký phím dừng (tổ hợp + bắt thô). Gọi mấy lần cũng được."""
        if self.hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(self.hotkey_handle)
            except Exception:
                pass
            self.hotkey_handle = None
        if self.hotkey_raw is not None:
            try:
                keyboard.unhook_key(self.hotkey_raw)
            except Exception:
                pass
            self.hotkey_raw = None

    def on_close(self):
        """Đóng cửa sổ: dừng vòng chạy, huỷ hẹn giờ bơm log, gỡ hotkey toàn cục."""
        self.stop_flag.set()
        self._cancel_pump()
        self._remove_hotkeys()
        try:
            self.root.destroy()
        except Exception:
            pass

    def _cancel_pump(self):
        if self._pump_after_id is not None:
            try:
                self.root.after_cancel(self._pump_after_id)
            except Exception:
                pass
            self._pump_after_id = None

    # ---- truy cập bước / hành động đang chọn ----
    @property
    def cur_step(self):
        if 0 <= self.cur < len(self.steps):
            return self.steps[self.cur]
        return None

    @property
    def actions(self):
        """Danh sách hành động của bước đang chọn (Loop hoặc Nhóm).
        Rỗng nếu bước là hành động lẻ — loại đó chỉ có đúng 1 hành động, không có list."""
        st = self.cur_step
        if st is not None and has_actions(st):
            return st.setdefault("actions", [])
        return []

    @actions.setter
    def actions(self, value):
        """Gán thẳng danh sách hành động cho bước đang chọn (Loop hoặc Nhóm)."""
        st = self.cur_step
        if st is not None and has_actions(st):
            st["actions"] = list(value)

    # ---- UI ----
    def _build_ui(self):
        # ===== Thanh tiêu đề: tên Process =====
        head = ttk.Frame(self.root, padding=(10, 8, 10, 0))
        head.pack(fill="x")
        self.title_lbl = ttk.Label(head, text="Auto Clicker", font=("Segoe UI", 12, "bold"))
        self.title_lbl.pack(side="left")
        ttk.Label(head, text="   Process:").pack(side="left", padx=(10, 2))
        self.process_name_var = tk.StringVar(value=self.process_name)
        ttk.Entry(head, textvariable=self.process_name_var, width=26).pack(side="left")
        ttk.Button(head, text="⚙ Cài đặt", command=self.open_settings).pack(side="right")
        ttk.Button(head, text="👁 Xem điểm", command=self.review_points).pack(side="right", padx=(0, 6))

        # ===== Thân: 2 cột (trái = các bước, phải = sửa bước đang chọn) =====
        pane = ttk.PanedWindow(self.root, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=10, pady=6)

        # --- Cột trái: danh sách BƯỚC của Process ---
        lwrap = ttk.LabelFrame(pane, text="Các bước của Process (F2 đổi tên • Ctrl+C/Ctrl+V • "
                                          "Del xoá • kéo-thả)",
                               padding=8)
        pane.add(lwrap, weight=1)
        sfr = ttk.Frame(lwrap)
        sfr.pack(fill="both", expand=True)
        ssb = ttk.Scrollbar(sfr, orient="vertical")
        self.step_box = tk.Listbox(sfr, height=12, yscrollcommand=ssb.set,
                                   exportselection=False, activestyle="dotbox")
        ssb.config(command=self.step_box.yview)
        self.step_box.pack(side="left", fill="both", expand=True)
        ssb.pack(side="right", fill="y")
        self.step_box.bind("<<ListboxSelect>>", self._on_step_select)
        self.step_box.bind("<F2>", self.rename_step)
        for seq, fn in (("<Control-c>", self.copy_steps), ("<Control-C>", self.copy_steps),
                        ("<Control-v>", self.paste_steps), ("<Control-V>", self.paste_steps),
                        ("<Delete>", self.delete_step_key)):
            self.step_box.bind(seq, fn)
        self._enable_drag_reorder(self.step_box, lambda: self.steps, self._steps_reordered,
                                  on_moved=self._step_moved)

        sb1 = ttk.Frame(lwrap)
        sb1.pack(fill="x", pady=(6, 0))
        ttk.Button(sb1, text="➕ Loop", width=9, command=self.add_loop_step).pack(side="left")
        ttk.Button(sb1, text="➕ Nhóm", width=9, command=self.add_group_step).pack(side="left", padx=4)
        ttk.Button(sb1, text="➕ HĐ lẻ", width=9, command=self.add_action_step).pack(side="left")
        sb2 = ttk.Frame(lwrap)
        sb2.pack(fill="x", pady=(4, 0))
        ttk.Button(sb2, text="🏷 Đổi tên", width=11, command=self.rename_step).pack(side="left")
        ttk.Button(sb2, text="🗑 Xoá", width=8, command=self.delete_step).pack(side="left", padx=4)
        ttk.Button(sb2, text="⬆", width=4, command=lambda: self.move_step(-1)).pack(side="left")
        ttk.Button(sb2, text="⬇", width=4, command=lambda: self.move_step(1)).pack(side="left", padx=2)
        ttk.Label(lwrap, style="Muted.TLabel",
                  text="🔁 = Action_Loop (lặp)   •   ⚡ = hành động lẻ (chạy 1 lần)").pack(
            anchor="w", pady=(6, 0))

        # --- Cột phải: khung sửa bước đang chọn ---
        self.detail = ttk.Frame(pane)
        pane.add(self.detail, weight=2)
        self._build_loop_pane()
        self._build_action_pane()

        # ===== Panel dưới: 2 tab (Vấn đề / Nhật ký chạy) =====
        self.bottom_nb = ttk.Notebook(self.root)
        self.bottom_nb.pack(fill="x", padx=10, pady=(8, 0))

        prob = ttk.Frame(self.bottom_nb, padding=8)
        self.bottom_nb.add(prob, text="⚠ Vấn đề")
        self.prob_lbl = ttk.Label(prob, text="", style="Muted.TLabel")
        self.prob_lbl.pack(anchor="w")
        pfr = ttk.Frame(prob)
        pfr.pack(fill="x", pady=(4, 0))
        psb = ttk.Scrollbar(pfr, orient="vertical")
        self.prob_box = tk.Listbox(pfr, height=5, yscrollcommand=psb.set, exportselection=False,
                                   activestyle="none")
        psb.config(command=self.prob_box.yview)
        self.prob_box.pack(side="left", fill="both", expand=True)
        psb.pack(side="right", fill="y")
        # Click 1 vấn đề -> nhảy tới hành động gây ra nó
        self.prob_box.bind("<<ListboxSelect>>", self._jump_to_problem)
        self._problems = []

        logf = ttk.Frame(self.bottom_nb, padding=8)
        self.bottom_nb.add(logf, text="📋 Nhật ký chạy")
        lrow = ttk.Frame(logf)
        lrow.pack(fill="x")
        ttk.Label(lrow, text="Diễn biến từng bước khi chạy:", style="Muted.TLabel").pack(side="left")
        ttk.Button(lrow, text="🗑 Xoá nhật ký", command=self.clear_log).pack(side="right")
        tfr = ttk.Frame(logf)
        tfr.pack(fill="both", expand=True, pady=(4, 0))
        tsb = ttk.Scrollbar(tfr, orient="vertical")
        self.log_text = tk.Text(tfr, height=6, wrap="word", yscrollcommand=tsb.set,
                                state="disabled", font=("Consolas", 9))
        tsb.config(command=self.log_text.yview)
        self.log_text.pack(side="left", fill="both", expand=True)
        tsb.pack(side="right", fill="y")
        self.log_text.tag_config("ok", foreground=THEME["ok"])
        self.log_text.tag_config("warn", foreground=THEME["warn"])
        self.log_text.tag_config("err", foreground=THEME["err"])
        self.log_text.tag_config("dim", foreground=THEME["dim"])

        bar = ttk.Frame(self.root, padding=10)
        bar.pack(fill="x")
        self.save_btn = ttk.Button(bar, text="💾 Lưu ▾", width=12, command=self._show_save_menu)
        self.save_btn.pack(side="left")
        self.open_btn = ttk.Button(bar, text="📂 Mở ▾", width=12, command=self._show_open_menu)
        self.open_btn.pack(side="left", padx=6)
        ttk.Label(bar, text="   Đếm ngược (s):").pack(side="left")
        self.start_var = tk.StringVar(value="3")
        ttk.Entry(bar, textvariable=self.start_var, width=5).pack(side="left", padx=4)
        self.run_btn = ttk.Button(bar, text="▶ CHẠY", style="Accent.TButton",
                                  command=self.start_run)
        self.run_btn.pack(side="right")
        self.stop_btn = ttk.Button(bar, text="■ DỪNG", style="Danger.TButton",
                                   command=self.stop_run, state="disabled")
        self.stop_btn.pack(side="right", padx=6)

        self.status = tk.StringVar(value="Sẵn sàng.")
        ttk.Label(self.root, textvariable=self.status, relief="sunken", anchor="w", padding=4).pack(
            fill="x", side="bottom")

    # ---- khung sửa: Action_Loop ----
    def _build_loop_pane(self):
        f = ttk.LabelFrame(self.detail, text="Sửa Action_Loop", padding=8)
        self.pane_frame = f
        self.loop_pane = f

        top = ttk.Frame(f)
        top.pack(fill="x")
        self.name_lbl = ttk.Label(top, text="Tên Loop:")
        self.name_lbl.pack(side="left")
        self.loop_name_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.loop_name_var, width=24).pack(side="left", padx=(4, 14))
        ttk.Label(top, text="Số vòng lặp:").pack(side="left")
        self.loops_var = tk.StringVar(value=str(DEFAULT_MAX_LOOPS))
        self.loops_lbl = top.winfo_children()[-1]      # nhãn "Số vòng lặp:" vừa tạo
        self.loops_entry = ttk.Entry(top, textvariable=self.loops_var, width=8)
        self.loops_entry.pack(side="left", padx=4)
        # Giữ Shift là THUỘC TÍNH CỦA LOOP, không phải một hành động: phạm vi của
        # nó đúng bằng cái khung này, không phụ thuộc thứ tự hay dấu "🔁 Loop từ đây".
        self.hold_shift_var = tk.BooleanVar(value=False)
        self.hold_chk = ttk.Checkbutton(top, text="⇧ Giữ Shift suốt Loop",
                                        variable=self.hold_shift_var,
                                        command=self._sync_loop_fields)
        self.hold_chk.pack(side="left", padx=(14, 0))
        self.loop_name_var.trace_add("write", lambda *_: self._sync_loop_fields())
        self.loops_var.trace_add("write", lambda *_: self._sync_loop_fields())

        ttk.Label(f, text="Hành động (double-click sửa • F2 đổi tên • Ctrl+C/Ctrl+V • "
                          "Del xoá • kéo-thả):").pack(
            anchor="w", pady=(8, 2))
        body = ttk.Frame(f)
        body.pack(fill="both", expand=True)
        lfr = ttk.Frame(body)
        lfr.pack(side="left", fill="both", expand=True)
        lsb = ttk.Scrollbar(lfr, orient="vertical")
        self.listbox = tk.Listbox(lfr, height=12, activestyle="dotbox", exportselection=False,
                                  selectmode=tk.EXTENDED, yscrollcommand=lsb.set)
        lsb.config(command=self.listbox.yview)
        self.listbox.pack(side="left", fill="both", expand=True)
        lsb.pack(side="right", fill="y")
        self.listbox.bind("<Double-Button-1>", lambda e: self.edit_action())
        self.listbox.bind("<Control-c>", self.copy_actions)
        self.listbox.bind("<Control-C>", self.copy_actions)
        self.listbox.bind("<Control-v>", self.paste_actions)
        self.listbox.bind("<Control-V>", self.paste_actions)
        self.listbox.bind("<Delete>", self.delete_action_key)
        self.listbox.bind("<F2>", self.rename_action)
        self._enable_drag_reorder(self.listbox, lambda: self.actions, self.refresh)

        col = ttk.Frame(body, padding=(8, 0))
        col.pack(side="left", fill="y")
        for text, cmd in [
            ("➕ Thêm", self.add_action), ("✏ Sửa", self.edit_action),
            ("🏷 Đổi tên", self.rename_action), ("🗑 Xoá", self.delete_action),
            ("⬆ Lên", lambda: self.move(-1)), ("⬇ Xuống", lambda: self.move(1)),
        ]:
            ttk.Button(col, text=text, width=12, command=cmd).pack(pady=2)
        ttk.Separator(col, orient="horizontal").pack(fill="x", pady=6)
        self.loop_start_btn = ttk.Button(col, text="🔁 Loop từ đây", width=12,
                                         command=self.set_loop_start)
        self.loop_start_btn.pack(pady=2)

        self.pane_hint = ttk.Label(f, style="Muted.TLabel", text="")
        self.pane_hint.pack(anchor="w", pady=(6, 0))
        self._apply_pane_mode(True)

    # ---- khung sửa: hành động lẻ ----
    def _build_action_pane(self):
        f = ttk.LabelFrame(self.detail, text="Sửa hành động lẻ", padding=8)
        self.action_pane = f
        ttk.Label(f, text="Bước này là 1 hành động lẻ — chạy đúng 1 lần rồi sang bước kế tiếp.",
                  style="Muted.TLabel").pack(anchor="w")
        self.single_lbl = ttk.Label(f, text="", font=("Segoe UI", 10, "bold"), wraplength=460,
                                    justify="left")
        self.single_lbl.pack(anchor="w", pady=(10, 12))
        row = ttk.Frame(f)
        row.pack(anchor="w")
        ttk.Button(row, text="✏ Sửa hành động", command=self.edit_single_action).pack(side="left")
        ttk.Button(row, text="🏷 Đổi tên", command=self.rename_step).pack(side="left", padx=6)

    # ---- quản lý các BƯỚC ----
    def refresh_steps(self):
        self.step_box.delete(0, tk.END)
        for i, st in enumerate(self.steps, 1):
            self.step_box.insert(tk.END, f"{i}.  {step_display(st)}")
        if 0 <= self.cur < len(self.steps):
            self.step_box.selection_clear(0, tk.END)
            self.step_box.selection_set(self.cur)
        self.refresh_problems()

    def _step_moved(self, new_index):
        """Kéo-thả bước -> con trỏ bước đi THEO dòng vừa kéo.

        Không có cái này thì dòng sáng một đằng, self.cur một nẻo: bấm "➕ Thêm"
        sẽ nhét hành động vào Loop KHÁC với Loop đang sáng, người dùng tưởng hành
        động biến mất."""
        self.cur = max(0, min(new_index, len(self.steps) - 1))

    def _steps_reordered(self):
        """Sau khi kéo-thả bước: vẽ lại CẢ khung bên phải theo bước vừa kéo,
        không chỉ vẽ lại danh sách bước."""
        self.select_step(self.cur)

    def _on_step_select(self, event=None):
        sel = self.step_box.curselection()
        if sel and sel[0] != self.cur:
            self.select_step(sel[0])

    def select_step(self, i):
        if not self.steps:
            self.cur = 0
            self.loop_pane.pack_forget()
            self.action_pane.pack_forget()
            return
        self.cur = max(0, min(i, len(self.steps) - 1))
        st = self.steps[self.cur]
        self.step_box.selection_clear(0, tk.END)
        self.step_box.selection_set(self.cur)

        self._syncing = True
        try:
            if has_actions(st):
                # Nhóm dùng CHUNG khung với Loop, chỉ khoá 3 thứ không liên quan.
                self.action_pane.pack_forget()
                self.loop_pane.pack(fill="both", expand=True)
                self.loop_name_var.set(st.get("name") or "")
                self.loops_var.set(str(st.get("max_loops", DEFAULT_MAX_LOOPS))
                                   if is_loop_step(st) else "1")
                self.hold_shift_var.set(bool(parse_hold_keys(st.get("hold_keys")))
                                        if is_loop_step(st) else False)
                self._apply_pane_mode(is_loop_step(st))
                self.refresh()
            else:
                self.loop_pane.pack_forget()
                self.action_pane.pack(fill="both", expand=True)
                self.single_lbl.config(text=action_display(st))
                self.refresh_problems()
        finally:
            self._syncing = False

    def _apply_pane_mode(self, is_loop):
        """Khung bên phải dùng chung cho Loop và Nhóm HĐ 1 lần.
        Nhóm không lặp nên khoá hẳn 3 thứ vô nghĩa với nó: Số vòng lặp,
        ⇧ Giữ Shift, và 🔁 Loop từ đây."""
        state = "normal" if is_loop else "disabled"
        for w in (self.loops_entry, self.hold_chk, self.loop_start_btn):
            try:
                w.config(state=state)
            except tk.TclError:
                pass
        self.loops_lbl.config(foreground=THEME["text"] if is_loop else THEME["dim"])
        self.pane_frame.config(text="Sửa Action_Loop" if is_loop else "Sửa Nhóm HĐ 1 lần")
        self.name_lbl.config(text="Tên Loop:" if is_loop else "Tên nhóm:")
        self.pane_hint.config(
            text=('Xám + "(1 lần)" = chạy 1 lần lúc đầu   •   🔁 = lặp mỗi vòng   •   '
                  'thêm "🔍 Kiểm tra mod" để Loop tự dừng khi đạt') if is_loop else
            ('Cả nhóm chạy ĐÚNG 1 LƯỢT theo thứ tự trên xuống   •   không lặp nên '
             'không có số vòng, không có "Loop từ đây"'))

    def _sync_loop_fields(self):
        """Ô Tên / Số vòng / tick Shift đổi -> ghi ngược vào bước đang chọn."""
        if getattr(self, "_syncing", False):
            return
        st = self.cur_step
        if st is None or not has_actions(st):
            return
        if is_group_step(st):
            st["name"] = self.loop_name_var.get().strip() or "Nhóm"
            self.refresh_steps()
            self.refresh()
            return
        st["name"] = self.loop_name_var.get().strip() or "Loop"
        st["hold_keys"] = "shift" if self.hold_shift_var.get() else ""
        try:
            st["max_loops"] = max(1, int(self.loops_var.get() or 1))
        except ValueError:
            pass
        self.refresh_steps()
        self.refresh()          # tiền tố ⇧ trên từng dòng hành động đổi theo

    def add_group_step(self):
        self.steps.insert(self.cur + 1 if self.steps else 0,
                          make_group_step(f"Nhóm {len(self.steps) + 1}"))
        self.refresh_steps()
        self.select_step(self.cur + 1 if len(self.steps) > 1 else 0)
        self.status.set("Đã thêm 1 Nhóm HĐ 1 lần.")

    def add_loop_step(self):
        self.steps.insert(self.cur + 1 if self.steps else 0,
                          make_loop_step(f"Loop {len(self.steps) + 1}"))
        self.refresh_steps()
        self.select_step(self.cur + 1 if len(self.steps) > 1 else 0)
        self.status.set("Đã thêm 1 Action_Loop.")

    def add_action_step(self):
        dlg = ActionEditor(self.root, self)
        self.root.wait_window(dlg)
        if not dlg.result:
            return
        self.steps.insert(self.cur + 1 if self.steps else 0, make_action_step(dlg.result))
        self.refresh_steps()
        self.select_step(self.cur + 1 if len(self.steps) > 1 else 0)
        self.status.set("Đã thêm 1 hành động lẻ giữa các Loop.")

    def edit_single_action(self):
        st = self.cur_step
        if st is None or has_actions(st):
            return
        dlg = ActionEditor(self.root, self, st)
        self.root.wait_window(dlg)
        if dlg.result:
            self.steps[self.cur] = make_action_step(dlg.result)
            self.refresh_steps()
            self.select_step(self.cur)

    def rename_step(self, event=None):
        st = self.cur_step
        if st is None:
            return "break"
        cur_name = st.get("name") or ""
        new = simpledialog.askstring(
            "Đổi tên bước",
            "Tên Action_Loop:" if is_loop_step(st) else
            ("Tên nhóm:" if is_group_step(st)
             else "Tên bước (để trống = dùng mô tả tự sinh):"),
            initialvalue=cur_name, parent=self.root)
        if new is None:
            return "break"
        new = new.strip()
        if has_actions(st):
            st["name"] = new or ("Loop" if is_loop_step(st) else "Nhóm")
            self._syncing = True
            self.loop_name_var.set(st["name"])
            self._syncing = False
        else:
            if new:
                st["name"] = new
            else:
                st.pop("name", None)
            self.single_lbl.config(text=action_display(st))
        self.refresh_steps()
        return "break"

    def delete_step(self):
        if not self.steps:
            return
        st = self.cur_step
        if not messagebox.askyesno("Xoá bước", f"Xoá bước \"{step_title(st)}\"?"):
            return
        del self.steps[self.cur]
        if not self.steps:
            self.steps.append(make_loop_step("Loop 1"))
            self.cur = 0
        self.refresh_steps()
        self.select_step(min(self.cur, len(self.steps) - 1))

    def delete_step_key(self, event=None):
        """Phím Delete trên danh sách bước (vẫn hỏi xác nhận như nút 🗑)."""
        self.delete_step()
        return "break"

    # ---- copy / paste BƯỚC (Ctrl+C / Ctrl+V trên danh sách bước) ----
    CLIP_TAG_STEPS = "auto_clicker_steps"

    def copy_steps(self, event=None):
        st = self.cur_step
        if st is None:
            return "break"
        payload = json.dumps({self.CLIP_TAG_STEPS: [st]}, ensure_ascii=False)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(payload)
            self.root.update()
        except Exception:
            pass
        self.status.set(f"Đã copy bước \"{step_title(st)}\".")
        return "break"

    def _sanitize_step(self, st):
        """Dựng lại 1 bước từ dữ liệu clipboard. Trả None nếu không hợp lệ.

        Không tin dữ liệu clipboard: người dùng có thể đang giữ chữ item PoE hay
        JSON của chương trình khác."""
        if not isinstance(st, dict):
            return None
        if st.get("kind") == "loop":
            acts = [a for a in (st.get("actions") or [])
                    if isinstance(a, dict) and a.get("type") in ACTION_TYPES]
            try:
                max_loops = max(1, int(st.get("max_loops") or DEFAULT_MAX_LOOPS))
                start = max(0, int(st.get("loop_start_index") or 0))
            except (TypeError, ValueError):
                max_loops, start = DEFAULT_MAX_LOOPS, 0
            return {"kind": "loop",
                    "name": str(st.get("name") or "Loop"),
                    "actions": copy.deepcopy(acts),
                    "loop_start_index": min(start, len(acts)),
                    "max_loops": max_loops,
                    "hold_keys": st.get("hold_keys") or ""}
        if st.get("kind") == "group":
            return {"kind": "group",
                    "name": str(st.get("name") or "Nhóm"),
                    "actions": copy.deepcopy(
                        [a for a in (st.get("actions") or [])
                         if isinstance(a, dict) and a.get("type") in ACTION_TYPES])}
        if st.get("type") in ACTION_TYPES:
            return make_action_step(copy.deepcopy(st))
        return None

    def paste_steps(self, event=None):
        try:
            data = json.loads(self.root.clipboard_get())
            items = data.get(self.CLIP_TAG_STEPS) if isinstance(data, dict) else None
        except Exception:
            items = None
        if not items:
            return "break"
        new_steps = [s for s in (self._sanitize_step(x) for x in items) if s]
        if not new_steps:
            return "break"
        pos = self.cur + 1 if self.steps else 0
        self.steps[pos:pos] = new_steps
        self.refresh_steps()
        self.select_step(pos + len(new_steps) - 1)   # nhảy tới bước vừa dán
        self.status.set(f"Đã dán {len(new_steps)} bước.")
        return "break"

    def move_step(self, d):
        j = self.cur + d
        if 0 <= j < len(self.steps):
            self.steps[self.cur], self.steps[j] = self.steps[j], self.steps[self.cur]
            self.cur = j
            self.refresh_steps()
            self.select_step(j)

    # ---- settings ----
    def open_settings(self):
        dlg = SettingsDialog(self.root, self)
        self.root.wait_window(dlg)

    def apply_settings(self):
        g = self.settings["game"]
        self.title_lbl.config(text=f"Auto Clicker — {GAMES.get(g, g)}")
        self.root.title(f"Auto Clicker — {GAMES.get(g, g)}")

    def reload_mods(self):
        """Nạp lại danh sách mod (sau khi đổi game hoặc cập nhật từ mạng).
        Danh sách mod giờ nằm trong hộp thoại "Kiểm tra mod", nên ở đây chỉ cần
        cập nhật dữ liệu — hộp thoại mở lần sau sẽ tự dùng danh sách mới."""
        self.all_mods = load_mods(self.settings["game"])

    # ---- actions (của Action_Loop đang chọn) ----
    @property
    def loop_start_index(self):
        st = self.cur_step
        return int(st.get("loop_start_index", 0)) if (st and is_loop_step(st)) else 0

    @loop_start_index.setter
    def loop_start_index(self, v):
        st = self.cur_step
        if st is not None and is_loop_step(st):
            st["loop_start_index"] = int(v)

    def refresh(self):
        st = self.cur_step
        if st is None or not has_actions(st):
            self.refresh_problems()
            return
        self.listbox.delete(0, tk.END)
        acts = self.actions
        n = len(acts)
        if is_group_step(st):
            # Nhóm: mọi dòng bình đẳng, đều chạy đúng 1 lượt. Không dấu 🔁, không
            # đuôi "(1 lần)", không dòng nào bị xám — vì không có phần lặp.
            for idx, a in enumerate(acts):
                self.listbox.insert(tk.END, f"    {idx + 1}.  {action_display(a)}")
            self.refresh_steps()
            return
        start = max(0, min(self.loop_start_index, n))
        self.loop_start_index = start
        # Tick "Giữ Shift" bật -> gắn ⇧ vào TỪNG dòng, để nhìn 1 dòng vẫn biết cú
        # click đó là shift-click, khỏi phải ngó ngược lên ô tick.
        hold_mark = "⇧" if parse_hold_keys(st.get("hold_keys")) else ""
        for idx, a in enumerate(acts):
            i = idx + 1
            looping = idx >= start
            prefix = "🔁 " if looping else "    "
            suffix = "" if looping else "   (1 lần)"
            self.listbox.insert(tk.END,
                                f"{prefix}{hold_mark}{i}.  {action_display(a)}{suffix}")
            if not looping:
                self.listbox.itemconfig(idx, fg=THEME["dim"])
        self.refresh_steps()

    # ---- đổi tên hành động (F2 / nút Đổi tên) ----
    def rename_action(self, event=None):
        """Hiện ô nhập ngay trên dòng đang chọn. Enter=lưu, Esc=huỷ, click ra ngoài=lưu.
        Để trống = xoá tên tự đặt, quay về mô tả tự sinh."""
        i = self._sel()
        if i is None:
            self.status.set("Chọn 1 hành động rồi nhấn F2 để đổi tên.")
            return "break"
        if getattr(self, "_rename_entry", None) is not None:
            return "break"                      # đang đổi tên dòng khác

        self.listbox.see(i)
        box = self.listbox.bbox(i)
        if not box:
            return "break"
        _, y, _, h = box

        var = tk.StringVar(value=(self.actions[i].get("name") or ""))
        ent = tk.Entry(self.listbox, textvariable=var, borderwidth=1, relief="solid")
        ent.place(x=0, y=y, width=self.listbox.winfo_width(), height=h)
        ent.focus_set()
        ent.select_range(0, tk.END)
        self._rename_entry = ent
        done = {"v": False}

        def cleanup():
            done["v"] = True
            self._rename_entry = None
            try:
                ent.destroy()
            except Exception:
                pass

        def commit(_=None):
            if done["v"]:
                return
            new = var.get().strip()
            old = self.actions[i].get("name") or ""
            if new:
                self.actions[i]["name"] = new
            else:
                self.actions[i].pop("name", None)
            cleanup()
            self.refresh()
            self.listbox.selection_set(i)
            if new:
                self.status.set(f"Đã đặt tên hành động #{i + 1}: \"{new}\"")
            elif old:
                self.status.set(f"Đã xoá tên hành động #{i + 1} — dùng lại mô tả tự sinh.")

        def cancel(_=None):
            if done["v"]:
                return
            cleanup()
            self.listbox.selection_set(i)

        ent.bind("<Return>", commit)
        ent.bind("<KP_Enter>", commit)
        ent.bind("<Escape>", cancel)
        ent.bind("<FocusOut>", commit)
        return "break"

    # ---- panel Vấn đề (soát cả Process) ----
    def refresh_problems(self):
        """Soát lại toàn bộ Process và cập nhật panel Vấn đề."""
        self._problems = validate_process(self.steps)
        self.prob_box.delete(0, tk.END)
        n_err = sum(1 for p in self._problems if p["severity"] == "error")
        n_warn = len(self._problems) - n_err
        for p in self._problems:
            icon = "✖" if p["severity"] == "error" else "⚠"
            self.prob_box.insert(tk.END, f"{icon} {p['message']}")
            if p["severity"] == "error":
                self.prob_box.itemconfig(self.prob_box.size() - 1, fg=THEME["err"])
        if not self._problems:
            self.prob_lbl.config(text="✔ Không có vấn đề — sẵn sàng chạy.", foreground=THEME["ok"])
        else:
            parts = []
            if n_err:
                parts.append(f"{n_err} lỗi")
            if n_warn:
                parts.append(f"{n_warn} cảnh báo")
            self.prob_lbl.config(text=" · ".join(parts) + "   (bấm 1 dòng để nhảy tới chỗ sai)",
                                 foreground=THEME["err"] if n_err else THEME["warn"])
        # Hiện số lượng ngay trên nhãn tab, khỏi phải mở tab mới biết
        try:
            n = len(self._problems)
            self.bottom_nb.tab(0, text="⚠ Vấn đề" + (f" ({n})" if n else ""))
        except Exception:
            pass

    def _jump_to_problem(self, event=None):
        """Bấm 1 vấn đề -> nhảy tới đúng BƯỚC, rồi tới đúng hành động trong bước đó."""
        sel = self.prob_box.curselection()
        if not sel:
            return
        p = self._problems[sel[0]] if sel[0] < len(self._problems) else None
        if not p:
            return
        si = p.get("step")
        if si is not None and 0 <= si < len(self.steps):
            if si != self.cur:
                self.select_step(si)
            self.step_box.see(si)
        i = p.get("index")
        st = self.cur_step
        if i is not None and st is not None and has_actions(st) and 0 <= i < len(self.actions):
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(i)
            self.listbox.see(i)

    def set_loop_start(self):
        i = self._sel()
        if i is None:
            messagebox.showinfo("Chọn dòng",
                                "Chọn 1 hành động rồi bấm lại để đặt làm điểm bắt đầu Loop.\n"
                                "Các hành động phía TRÊN dòng này sẽ chỉ chạy 1 lần lúc đầu.")
            return
        self.loop_start_index = i
        self.refresh()
        self.listbox.selection_set(i)
        if i == 0:
            self.status.set("Toàn bộ danh sách sẽ lặp lại (không có bước mở đầu).")
        else:
            self.status.set(f"Sẽ lặp lại từ hành động #{i + 1} trở đi; {i} hành động đầu chỉ chạy 1 lần.")

    def _sel(self):
        s = self.listbox.curselection()
        return s[0] if s else None

    def _sel_indices(self):
        return list(self.listbox.curselection())

    def _enable_drag_reorder(self, listbox, get_list, on_refresh, on_moved=None):
        """Cho phép kéo-thả 1 dòng để đổi vị trí trong danh sách (Hành động / Điều kiện).
        Kéo sẽ CHÈN dòng vào đúng vị trí thả (các dòng ở giữa tự dồn), không phải hoán đổi.

        `on_moved(vị_trí_mới)` gọi NGAY SAU khi đổi chỗ và TRƯỚC khi vẽ lại, để bên
        gọi kịp cập nhật "dòng đang chọn" của mình. Bắt buộc với danh sách BƯỚC:
        listbox tự đặt dòng sáng, mà đặt bằng code thì KHÔNG kích hoạt
        <<ListboxSelect>> -> self.cur không bao giờ được sửa lại."""
        state = {"idx": None}

        def on_start(event):
            i = listbox.nearest(event.y)
            lst = get_list()
            state["idx"] = i if 0 <= i < len(lst) else None
            # không return "break": vẫn để hành vi chọn dòng mặc định chạy bình thường

        def on_motion(event):
            if state["idx"] is None:
                return "break"
            lst = get_list()
            if not lst:
                return "break"
            i = max(0, min(listbox.nearest(event.y), len(lst) - 1))
            if i != state["idx"]:
                item = lst.pop(state["idx"])
                lst.insert(i, item)
                if on_moved:
                    on_moved(i)
                on_refresh()
                listbox.selection_clear(0, tk.END)
                listbox.selection_set(i)
                state["idx"] = i
            return "break"  # chặn hành vi kéo-để-chọn-nhiều-dòng mặc định của Listbox

        def on_release(event):
            state["idx"] = None

        listbox.bind("<Button-1>", on_start, add="+")
        listbox.bind("<B1-Motion>", on_motion)
        listbox.bind("<ButtonRelease-1>", on_release, add="+")

    def add_action(self):
        dlg = ActionEditor(self.root, self)
        self.root.wait_window(dlg)
        if dlg.result:
            self.actions.append(dlg.result)
            self.refresh()

    def edit_action(self):
        i = self._sel()
        if i is None:
            return
        dlg = ActionEditor(self.root, self, self.actions[i])
        self.root.wait_window(dlg)
        if dlg.result:
            self.actions[i] = dlg.result
            self.refresh()
            self.listbox.selection_set(i)

    def delete_action_key(self, event=None):
        """Phím Delete trên danh sách hành động."""
        self.delete_action()
        return "break"

    def delete_action(self):
        idxs = self._sel_indices()
        if not idxs:
            return
        for i in sorted(idxs, reverse=True):
            del self.actions[i]
        self.refresh()

    # ---- copy / paste hành động (Ctrl+C / Ctrl+V) ----
    CLIP_TAG = "auto_clicker_actions"

    def copy_actions(self, event=None):
        idxs = self._sel_indices()
        if not idxs:
            return "break"
        items = [self.actions[i] for i in idxs]
        payload = json.dumps({self.CLIP_TAG: items}, ensure_ascii=False)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(payload)
            self.root.update()
        except Exception:
            pass
        self.status.set(f"Đã copy {len(items)} hành động.")
        return "break"

    def paste_actions(self, event=None):
        try:
            text = self.root.clipboard_get()
            data = json.loads(text)
            items = data.get(self.CLIP_TAG) if isinstance(data, dict) else None
        except Exception:
            items = None
        if not items:
            return "break"
        valid = [a for a in items if isinstance(a, dict) and a.get("type") in ACTION_TYPES]
        if not valid:
            return "break"
        idxs = self._sel_indices()
        pos = (max(idxs) + 1) if idxs else len(self.actions)
        new_items = [copy.deepcopy(a) for a in valid]
        self.actions[pos:pos] = new_items
        self.refresh()
        self.listbox.selection_clear(0, tk.END)
        for k in range(pos, pos + len(new_items)):
            self.listbox.selection_set(k)
        self.status.set(f"Đã dán {len(new_items)} hành động.")
        return "break"

    def move(self, d):
        i = self._sel()
        if i is None:
            return
        j = i + d
        if 0 <= j < len(self.actions):
            self.actions[i], self.actions[j] = self.actions[j], self.actions[i]
            self.refresh()
            self.listbox.selection_set(j)

    # ---- chọn điểm ----
    def pick_point(self, callback, hide=None):
        self.status.set("Chọn điểm: di chuột, Click/F8/Enter để chốt, Esc để huỷ.")
        if hide:
            try:
                hide.grab_release()
            except Exception:
                pass
            hide.withdraw()
        self.root.withdraw()

        def on_pick(pt):
            self.root.deiconify()
            if hide:
                hide.deiconify()
                try:
                    hide.grab_set()
                except Exception:
                    pass
            if pt:
                self.status.set(f"Đã chọn điểm ({pt[0]}, {pt[1]}).")
                callback(pt)
            else:
                self.status.set("Đã huỷ chọn điểm.")

        PointSelector(self.root, on_pick)

    def pick_abyss_frame(self, frame, callback, hide=None):
        """Mở overlay căn khung Abyss (giống pick_point nhưng chọn cả 1 vùng)."""
        self.status.set("Căn khung Abyss: kéo cho trùm panel, D để đọc thử, Enter để lưu.")
        if hide:
            try:
                hide.grab_release()
            except Exception:
                pass
            hide.withdraw()
        self.root.withdraw()

        def on_done(fr):
            self.root.deiconify()
            if hide:
                hide.deiconify()
                try:
                    hide.grab_set()
                except Exception:
                    pass
            if fr:
                self.status.set(f"Đã căn khung Abyss: ({fr[0]}, {fr[1]}) {fr[2]}×{fr[3]}.")
                callback(fr)
            else:
                self.status.set("Đã huỷ căn khung.")

        AbyssFrameSelector(self.root, frame, on_done)

    def pick_inv_grid(self, frame, cells, callback, hide=None):
        """Mở overlay căn lưới inventory + tick ô."""
        self.status.set("Căn lưới: kéo cho trùm lưới, BẤM vào ô để chọn, Enter để lưu.")
        if hide:
            try:
                hide.grab_release()
            except Exception:
                pass
            hide.withdraw()
        self.root.withdraw()

        def on_done(res):
            self.root.deiconify()
            if hide:
                hide.deiconify()
                try:
                    hide.grab_set()
                except Exception:
                    pass
            if res:
                self.status.set(f"Đã căn lưới, chọn {len(res[1])} ô.")
                callback(res)
            else:
                self.status.set("Đã huỷ căn lưới.")

        InvGridSelector(self.root, frame, cells, on_done)

    # ---- xem lại điểm đã chọn (toàn bộ Process) ----
    def review_points(self):
        pts = []

        def add(a, label):
            if a.get("type") == "abyss":
                # Abyss không có 1 điểm mà cả 1 khung -> hiện mọi điểm suy ra từ khung
                fr = a.get("frame")
                if not fr:
                    return
                r = core.abyss_regions(fr)
                for i, p in enumerate(r["band_points"], 1):
                    pts.append((p[0], p[1], f"{label} · mod {i}", THEME["ok"]))
                cf = r["confirm"]
                pts.append((cf[0], cf[1], f"{label} · CONFIRM", THEME["accent"]))
                rp = r["refresh_point"]
                pts.append((rp[0], rp[1], f"{label} · ↻", THEME["warn"]))
                return
            pt = a.get("point")
            if not pt:
                return
            color = THEME["ok"] if a.get("type") == "check_mod" else THEME["accent"]
            pts.append((pt[0], pt[1], label, color))

        for si, st in enumerate(self.steps, 1):
            if has_actions(st):
                for i, a in enumerate(st.get("actions") or [], 1):
                    add(a, f"{si}.{i} {step_title(st)}")
            else:
                add(st, f"{si}. {step_title(st)} (lẻ)")
        if not pts:
            messagebox.showinfo("Chưa có điểm",
                                "Chưa có điểm nào để xem (thêm hành động click hoặc kiểm tra mod).")
            return
        self.status.set("Đang xem điểm... (click hoặc Esc để đóng)")
        self.root.withdraw()
        ReviewOverlay(self.root, pts,
                      lambda: (self.root.deiconify(), self.status.set("Sẵn sàng.")))

    # ---- template ----
    def flow_data(self):
        """Cấu hình dùng để CHẠY: cả Process (danh sách bước)."""
        return {
            "name": self.process_name_var.get().strip() or "Process 1",
            "game": self.settings["game"],
            "steps": self.steps,
            "start_delay": max(0, int(self.start_var.get() or 0)),
        }

    def template_data(self):
        """Dữ liệu LƯU FILE — định dạng Process (nhiều bước nối tiếp).

        Định dạng do core quyết định, không phải ở đây: giao diện web dùng chung
        `make_process_template`, nên hai bên không thể lệch nhau."""
        return core.make_process_template(
            self.process_name_var.get(),
            self.settings["game"],
            self.start_var.get() or 0,
            self.steps)

    # ---- menu Lưu ▾ / Mở ▾ ----
    def _popup_under(self, widget, menu):
        try:
            menu.tk_popup(widget.winfo_rootx(),
                          widget.winfo_rooty() + widget.winfo_height())
        finally:
            menu.grab_release()

    def _show_save_menu(self):
        mnu = tk.Menu(self.root, tearoff=0)
        mnu.add_command(label="💾 Lưu cả Process thành template",
                        command=self.save_process_template)
        st = self.cur_step
        can_loop = st is not None and is_loop_step(st)
        can_group = st is not None and is_group_step(st)
        mnu.add_command(label=f"🔁 Lưu riêng Loop đang chọn"
                              f"{'' if can_loop else '  (bước hiện tại không phải Loop)'}",
                        command=self.save_loop_template,
                        state=("normal" if can_loop else "disabled"))
        mnu.add_command(label=f"▤ Lưu riêng Nhóm đang chọn"
                              f"{'' if can_group else '  (bước hiện tại không phải Nhóm)'}",
                        command=self.save_group_template,
                        state=("normal" if can_group else "disabled"))
        mnu.add_separator()
        mnu.add_command(label="📄 Lưu ra file khác...", command=self.save_template)
        self._popup_under(self.save_btn, mnu)

    def _show_open_menu(self):
        mnu = tk.Menu(self.root, tearoff=0)
        mnu.add_command(label="📂 Mở Process (thay toàn bộ)", command=self.open_process_template)
        mnu.add_command(label="➕ Chèn Loop có sẵn vào Process này",
                        command=self.insert_loop_template)
        mnu.add_command(label="➕ Chèn Nhóm có sẵn vào Process này",
                        command=self.insert_group_template)
        mnu.add_separator()
        mnu.add_command(label="📄 Mở từ file khác...", command=self.load_template)
        self._popup_under(self.open_btn, mnu)

    def _ask_template_name(self, kind, default):
        """Hỏi tên, cảnh báo nếu trùng. Trả về đường dẫn đích, hoặc None nếu huỷ."""
        while True:
            name = simpledialog.askstring(
                f"Lưu template {TEMPLATE_KINDS[kind]}",
                "Đặt tên template:", initialvalue=default, parent=self.root)
            if name is None:
                return None
            name = name.strip()
            if not name:
                messagebox.showwarning("Thiếu tên", "Hãy nhập tên cho template.")
                continue
            path = template_path(kind, name)
            if os.path.exists(path):
                if not messagebox.askyesno(
                        "Trùng tên",
                        f"Đã có template tên \"{os.path.splitext(os.path.basename(path))[0]}\".\n"
                        f"Ghi đè?"):
                    continue
            return path

    def save_process_template(self):
        if not self.steps:
            messagebox.showwarning("Trống", "Process chưa có bước nào để lưu.")
            return
        default = self.process_name_var.get().strip() or "Process 1"
        path = self._ask_template_name("process", default)
        if not path:
            return
        try:
            write_json(path, self.template_data())
            self.status.set(f"Đã lưu template Process: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def save_loop_template(self):
        st = self.cur_step
        if st is None or not is_loop_step(st):
            messagebox.showinfo("Không phải Loop",
                                "Bước đang chọn không phải Action_Loop.\n"
                                "Nếu là Nhóm HĐ 1 lần thì dùng \"▤ Lưu riêng Nhóm đang chọn\".")
            return
        if not (st.get("actions") or []):
            if not messagebox.askyesno("Loop rỗng",
                                       "Loop này chưa có hành động nào. Vẫn lưu?"):
                return
        path = self._ask_template_name("loop", st.get("name") or "Loop")
        if not path:
            return
        try:
            write_json(path, make_loop_template(st, self.settings["game"]))
            self.status.set(f"Đã lưu template Action_Loop: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def open_process_template(self):
        dlg = TemplatePicker(self.root, "process", "Mở Process")
        self.root.wait_window(dlg)
        if dlg.result:
            self._load_process_from(dlg.result)

    def insert_loop_template(self):
        dlg = TemplatePicker(self.root, "loop", "Chèn Action_Loop có sẵn")
        self.root.wait_window(dlg)
        if not dlg.result:
            return
        try:
            data = read_json(dlg.result)
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))
            return
        step = normalize_loop_template(data)
        if step is None:
            messagebox.showerror(
                "Sai loại template",
                "File này không phải template Action_Loop.\n"
                "Nếu là template Nhóm, hãy dùng \"Chèn Nhóm có sẵn\".\n"
                "Nếu là template Process, hãy dùng \"Mở Process\".")
            return
        pos = self.cur + 1 if self.steps else 0
        self.steps.insert(pos, step)
        self.refresh_steps()
        self.select_step(pos)
        self.status.set(f"Đã chèn Loop \"{step['name']}\" vào Process.")

    def save_group_template(self):
        st = self.cur_step
        if st is None or not is_group_step(st):
            messagebox.showinfo("Không phải Nhóm",
                                "Bước đang chọn không phải Nhóm HĐ 1 lần.\n"
                                "Nếu là Action_Loop thì dùng \"🔁 Lưu riêng Loop đang chọn\".")
            return
        if not (st.get("actions") or []):
            if not messagebox.askyesno("Nhóm rỗng",
                                       "Nhóm này chưa có hành động nào. Vẫn lưu?"):
                return
        path = self._ask_template_name("group", st.get("name") or "Nhóm")
        if not path:
            return
        try:
            write_json(path, make_group_template(st, self.settings["game"]))
            self.status.set(f"Đã lưu template Nhóm: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def insert_group_template(self):
        dlg = TemplatePicker(self.root, "group", "Chèn Nhóm HĐ 1 lần có sẵn")
        self.root.wait_window(dlg)
        if not dlg.result:
            return
        try:
            data = read_json(dlg.result)
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))
            return
        step = normalize_group_template(data)
        if step is None:
            messagebox.showerror(
                "Sai loại template",
                "File này không phải template Nhóm HĐ 1 lần.\n"
                "Nếu là template Action_Loop, hãy dùng \"Chèn Loop có sẵn\".\n"
                "Nếu là template Process, hãy dùng \"Mở Process\".")
            return
        pos = self.cur + 1 if self.steps else 0
        self.steps.insert(pos, step)
        self.refresh_steps()
        self.select_step(pos)
        self.status.set(f"Đã chèn Nhóm \"{step['name']}\" vào Process.")

    def save_template(self):
        if not self.steps:
            messagebox.showwarning("Trống", "Process chưa có bước nào để lưu.")
            return
        try:
            data = self.template_data()
        except ValueError:
            messagebox.showerror("Lỗi", "Cấu hình số không hợp lệ.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON", "*.json")], initialdir=".")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.status.set(f"Đã lưu Process: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def _load_process_from(self, path):
        """Nạp 1 file thành Process hiện tại (thay toàn bộ). Dùng chung cho
        "Mở Process" (template) và "Mở từ file khác..."."""
        try:
            data = read_json(path)
            if data.get("type") == "loop":
                messagebox.showerror(
                    "Sai loại template",
                    "File này là template Action_Loop, không phải Process.\n"
                    "Hãy dùng \"➕ Chèn Loop có sẵn vào Process này\".")
                return
            norm = normalize_process(data)      # hiểu mọi định dạng cũ lẫn mới

            self.steps = norm["steps"] or [make_loop_step("Loop 1")]
            self.process_name = norm["name"]
            self.process_name_var.set(self.process_name)
            self.start_var.set(str(norm["start_delay"]))
            self.cur = 0

            self.refresh_steps()
            self.select_step(0)
            msg = f"Đã mở Process: {os.path.basename(path)} ({len(self.steps)} bước)"
            if norm.get("note"):
                msg += f"  ⚠ {norm['note']}"
            self.status.set(msg)
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def load_template(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")], initialdir=".")
        if path:
            self._load_process_from(path)

    # ---- chạy / dừng ----
    def start_run(self):
        if not self.steps:
            messagebox.showwarning("Trống", "Process chưa có bước nào.")
            return
        try:
            cfg = self.flow_data()
        except ValueError:
            messagebox.showerror("Lỗi", "Cấu hình số không hợp lệ.")
            return
        cfg.update({
            "pre_click_ms": int(self.settings.get("pre_click_ms", 60)),
            "hover_ms": int(self.settings.get("hover_ms", 250)),
            "copy_keys": self.settings.get("copy_keys", "ctrl+c"),
            "stop_hotkey": self.settings.get("stop_hotkey", "f6"),
        })
        # Soát cấu hình trước khi chạy: LỖI thì chặn, CẢNH BÁO thì hỏi lại.
        self.refresh_problems()
        errors = [p for p in self._problems if p["severity"] == "error"]
        warns = [p for p in self._problems if p["severity"] == "warning"]
        if errors:
            messagebox.showerror(
                "Không chạy được — hãy sửa các lỗi sau",
                "\n\n".join(f"✖ {p['message']}" for p in errors) +
                "\n\n(Các lỗi này cũng hiện ở panel \"Vấn đề\"; bấm vào 1 dòng để nhảy tới hành động.)")
            return
        if warns:
            if not messagebox.askyesno(
                    "Có cảnh báo — vẫn chạy?",
                    "\n\n".join(f"⚠ {p['message']}" for p in warns) + "\n\nVẫn chạy?"):
                return

        self.stop_flag.clear()
        self.run_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.bottom_nb.select(1)         # nhảy sang tab Nhật ký để theo dõi diễn biến
        try:
            self.hotkey_handle = keyboard.add_hotkey(cfg["stop_hotkey"], self.stop_flag.set)
        except Exception:
            self.hotkey_handle = None
        # Lớp dự phòng: add_hotkey khớp ĐÚNG tổ hợp, nên khi app đang GIỮ Shift
        # thì F6 bị hiểu thành Shift+F6 và không khớp -> không dừng được, đúng lúc
        # cần dừng nhất. on_press_key bắt phím thô, kệ phím bổ trợ.
        try:
            self.hotkey_raw = keyboard.on_press_key(cfg["stop_hotkey"],
                                                    lambda e: self.stop_flag.set())
        except Exception:
            self.hotkey_raw = None
        threading.Thread(target=self._run_worker, args=(cfg,), daemon=True).start()

    def stop_run(self):
        self.stop_flag.set()

    def _run_worker(self, cfg):
        """Chỉ còn nhiệm vụ NỐI bộ máy chạy (core.ProcessRunner) với giao diện.
        Toàn bộ logic chạy nằm trong core.py, không phụ thuộc tkinter."""
        runner = ProcessRunner(cfg, self.stop_flag,
                               on_status=self._set_status,
                               on_log=self._log_check)
        try:
            status, total_loops = runner.run()
        except BaseException as e:
            # BẮT BUỘC phải bắt: đây là thread phụ, lỗi lọt ra là thread chết ÂM
            # THẦM -> _finish() không chạy -> nút Chạy kẹt mờ, nút Dừng kẹt sáng,
            # hotkey toàn cục không được gỡ. Nhìn y như "app bị đơ".
            # Bản .exe chạy --windowed còn không có console để thấy traceback.
            import traceback
            detail = traceback.format_exc(limit=6)
            self._log(f"⛔ LỖI KHÔNG LƯỜNG TRƯỚC: {type(e).__name__}: {e}", "err")
            for line in detail.strip().splitlines()[-6:]:
                self._log(f"    {line}", "dim")
            status, total_loops = (f"⛔ Dừng vì lỗi: {type(e).__name__}: {e}", 0)
        finally:
            # Dù hỏng kiểu gì cũng phải thả hết phím đang giữ, không để kẹt Shift
            # trong cả hệ thống.
            try:
                runner.release_held_keys()
            except Exception:
                pass
        self._finish(status, total_loops)

    def _set_status(self, msg):
        # Worker chạy ở thread riêng: nếu người dùng ĐÓNG cửa sổ giữa chừng thì root
        # đã bị huỷ -> after() ném TclError. Nuốt đúng lỗi này, không nuốt lỗi khác.
        try:
            self.root.after(0, lambda: self.status.set(msg))
        except tk.TclError:
            pass

    # ---- nhật ký chạy ----
    def _log_check(self, msg, tag=None):
        """Nhật ký từ bước Kiểm tra mod. Riêng dòng "bỏ qua vì sai loại mod" (tag
        "skip") bị hãm tần suất — nếu item cứ roll ra hybrid mãi thì không spam."""
        if tag == "skip":
            now = time.time()
            if now - getattr(self, "_last_skip_log", 0.0) < SKIP_LOG_MIN_GAP:
                return
            self._last_skip_log = now
            tag = "warn"
        self._log(msg, tag)

    def _log(self, msg, tag=None):
        """Ghi 1 dòng nhật ký. GỌI ĐƯỢC TỪ WORKER THREAD — chỉ bỏ vào hàng đợi,
        việc vẽ do _pump_log() làm trên UI thread."""
        self._log_q.put((time.strftime("%H:%M:%S"), msg, tag))

    def _pump_log(self):
        """Chạy trên UI thread mỗi 200ms: rút hết hàng đợi rồi vẽ 1 lượt (thay vì
        gọi after() cho từng dòng — tránh dồn hàng nghìn callback khi chạy lâu)."""
        lines = []
        try:
            while True:
                lines.append(self._log_q.get_nowait())
        except queue.Empty:
            pass
        if lines:
            try:
                self.log_text.config(state="normal")
                for ts, msg, tag in lines:
                    self.log_text.insert("end", f"[{ts}] ", "dim")
                    self.log_text.insert("end", msg + "\n", tag or ())
                # Giữ tối đa MAX_LOG_LINES dòng để không phình bộ nhớ khi chạy lâu
                total = int(self.log_text.index("end-1c").split(".")[0])
                if total > MAX_LOG_LINES:
                    self.log_text.delete("1.0", f"{total - MAX_LOG_LINES}.0")
                self.log_text.see("end")
                self.log_text.config(state="disabled")
            except tk.TclError:
                self._pump_after_id = None
                return                      # cửa sổ đã đóng
        try:
            self._pump_after_id = self.root.after(200, self._pump_log)
        except tk.TclError:
            self._pump_after_id = None

    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _finish(self, status, loops):
        def done():
            self.status.set(f"{status} — tổng {loops} vòng.")
            self.run_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self._remove_hotkeys()
            notify(loops, status)
        try:
            self.root.after(0, done)
        except tk.TclError:
            # cửa sổ đã đóng khi đang chạy — vẫn gỡ hotkey toàn cục cho sạch
            self._remove_hotkeys()


def main():
    root = tk.Tk()
    enable_dpi(root)
    s = load_settings()
    set_accent(s.get("accent") or THEME["accent"])
    apply_theme(root)
    AutoClickerApp(root)
    set_window_icon(root)
    root.update()          # cửa sổ phải vẽ xong thì đặt thuộc tính DWM mới ăn
    dark_titlebar(root, remap=True)
    root.mainloop()


if __name__ == "__main__":
    main()
