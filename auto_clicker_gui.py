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
                  normalize_process, make_loop_step, make_action_step, is_loop_step,
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
    "accent":    "#ff7a1a",   # đổi được trong Cài đặt
    "on_accent": "#000000",   # tự tính theo độ sáng của accent
    "ok":        "#3fb950",
    "err":       "#f85149",
    "warn":      "#d29922",
}

# Màu nhấn chọn sẵn (vẫn chọn được màu tuỳ ý qua nút "Tuỳ chọn…")
ACCENT_PRESETS = {
    "Cam": "#ff7a1a",
    "Xanh dương": "#0078d4",
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


def dark_titlebar(win):
    """Làm tối thanh tiêu đề (Windows 10 1903+). Không có thì bỏ qua, không sao."""
    try:
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        val = ctypes.c_int(1)
        # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val),
                                                   ctypes.sizeof(val))
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
    """Đặt cửa sổ ra giữa màn hình. Nếu w/h không cho, tự lấy theo nội dung."""
    win.update_idletasks()
    if not w:
        w = win.winfo_width()
        if w <= 1:
            w = win.winfo_reqwidth()
    if not h:
        h = win.winfo_height()
        if h <= 1:
            h = win.winfo_reqheight()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 2 - 30)
    win.geometry(f"{w}x{h}+{x}+{y}")


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
        center_window(self, 460, 380)
        self.after(80, self.grab_set)

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
        self.grab_set()
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
        self.amount_var = tk.StringVar(value="-300")
        self.key_var = tk.StringVar(value="enter")
        self.min_var = tk.StringVar(value="200")
        self.max_var = tk.StringVar(value="1000")
        self.search_var = tk.StringVar()
        self.tier_var = tk.StringVar()
        self.hybrid_var = tk.StringVar(value=HYBRID_LABELS[HYBRID_ANY])
        self.hold_var = tk.StringVar(value="shift")
        self.button_var = tk.StringVar(value="Trái")
        self.conditions = copy.deepcopy(action.get("conditions", [])) if action else []
        if action and action.get("type") == "mod_click":
            self.hold_var.set("+".join(parse_hold_keys(action.get("keys"))) or "shift")
            self.button_var.set("Trái" if action.get("button", "left") == "left" else "Phải")
        if action:
            if "point" in action:
                pt = action.get("point")
                if pt:
                    self.x_var.set(pt[0])
                    self.y_var.set(pt[1])
            if action["type"] == "scroll":
                self.amount_var.set(action.get("amount", -300))
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
        center_window(self, 520, 720)

    def _render(self):
        for w in self.body.winfo_children():
            w.destroy()
        self.after_idle(lambda: restyle_tree(self.body))   # widget vừa dựng -> tô lại
        t = self.type_var.get()
        if t == "check_mod":
            self._render_check_mod()
        elif t in POINT_TYPES:
            ttk.Label(self.body, text="X:").grid(row=0, column=0, sticky="w")
            ttk.Entry(self.body, textvariable=self.x_var, width=8).grid(row=0, column=1)
            ttk.Label(self.body, text="Y:").grid(row=0, column=2, sticky="w", padx=(10, 0))
            ttk.Entry(self.body, textvariable=self.y_var, width=8).grid(row=0, column=3)
            ttk.Button(self.body, text="🎯 Chọn điểm (crosshair)", command=self._pick).grid(
                row=1, column=0, columnspan=4, pady=(8, 0), sticky="ew")
        elif t == "mod_click":
            ttk.Label(self.body, text="Giữ phím:").grid(row=0, column=0, sticky="w")
            cb = ttk.Combobox(self.body, textvariable=self.hold_var, width=14,
                              values=COMMON_HOLD_KEYS)
            cb.grid(row=0, column=1, sticky="w", padx=4)
            ttk.Label(self.body, text="Nút chuột:").grid(row=0, column=2, sticky="w", padx=(10, 0))
            ttk.OptionMenu(self.body, self.button_var, self.button_var.get(),
                           "Trái", "Phải").grid(row=0, column=3, sticky="w")
            ttk.Label(self.body, text="(nhiều phím thì nối bằng dấu +, vd: ctrl+shift)",
                      style="Muted.TLabel").grid(row=1, column=0, columnspan=4, sticky="w", pady=(2, 6))
            ttk.Label(self.body, text="X:").grid(row=2, column=0, sticky="w")
            ttk.Entry(self.body, textvariable=self.x_var, width=8).grid(row=2, column=1, sticky="w")
            ttk.Label(self.body, text="Y:").grid(row=2, column=2, sticky="w", padx=(10, 0))
            ttk.Entry(self.body, textvariable=self.y_var, width=8).grid(row=2, column=3, sticky="w")
            ttk.Button(self.body, text="🎯 Chọn điểm (crosshair)", command=self._pick).grid(
                row=3, column=0, columnspan=4, pady=(8, 0), sticky="ew")
        elif t == "scroll":
            ttk.Label(self.body, text="Lượng cuộn (âm = xuống):").grid(row=0, column=0, sticky="w")
            ttk.Entry(self.body, textvariable=self.amount_var, width=8).grid(row=0, column=1, padx=6)
        elif t == "key_press":
            ttk.Label(self.body, text="Phím (vd: enter, a, space, escape):").grid(row=0, column=0, sticky="w")
            ttk.Entry(self.body, textvariable=self.key_var, width=14).grid(row=0, column=1, padx=6)
        elif t == "delay":
            ttk.Label(self.body, text="Min ms:").grid(row=0, column=0, sticky="w")
            ttk.Entry(self.body, textvariable=self.min_var, width=8).grid(row=0, column=1)
            ttk.Label(self.body, text="Max ms:").grid(row=0, column=2, sticky="w", padx=(10, 0))
            ttk.Entry(self.body, textvariable=self.max_var, width=8).grid(row=0, column=3)

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
        self.cond_box.delete(0, tk.END)
        for i, c in enumerate(self.conditions, 1):
            self.cond_box.insert(tk.END, f"{i}.  {cond_display(c)}")

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
            elif t == "mod_click":
                keys = parse_hold_keys(self.hold_var.get())
                if not keys:
                    raise ValueError("chưa chọn phím cần giữ")
                a = {"type": t,
                     "point": [int(self.x_var.get()), int(self.y_var.get())],
                     "keys": "+".join(keys),
                     "button": "left" if self.button_var.get() == "Trái" else "right"}
            elif t in POINT_TYPES:
                a = {"type": t, "point": [int(self.x_var.get()), int(self.y_var.get())]}
            elif t == "scroll":
                a = {"type": t, "amount": int(self.amount_var.get())}
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
        self.grab_set()
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
        center_window(self)

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

    def on_close(self):
        """Đóng cửa sổ: dừng vòng chạy, huỷ hẹn giờ bơm log, gỡ hotkey toàn cục."""
        self.stop_flag.set()
        self._cancel_pump()
        if self.hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(self.hotkey_handle)
            except Exception:
                pass
            self.hotkey_handle = None
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
        """Danh sách hành động của Action_Loop đang chọn (rỗng nếu bước là hành động lẻ)."""
        st = self.cur_step
        if st is not None and is_loop_step(st):
            return st.setdefault("actions", [])
        return []

    @actions.setter
    def actions(self, value):
        """Gán thẳng danh sách hành động cho Action_Loop đang chọn."""
        st = self.cur_step
        if st is not None and is_loop_step(st):
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
        lwrap = ttk.LabelFrame(pane, text="Các bước của Process (chạy lần lượt từ trên xuống)",
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
        self._enable_drag_reorder(self.step_box, lambda: self.steps, self._steps_reordered)

        sb1 = ttk.Frame(lwrap)
        sb1.pack(fill="x", pady=(6, 0))
        ttk.Button(sb1, text="➕ Loop", width=11, command=self.add_loop_step).pack(side="left")
        ttk.Button(sb1, text="➕ HĐ lẻ", width=11, command=self.add_action_step).pack(side="left", padx=4)
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
        self.loop_pane = f

        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="Tên Loop:").pack(side="left")
        self.loop_name_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.loop_name_var, width=24).pack(side="left", padx=(4, 14))
        ttk.Label(top, text="Số vòng lặp:").pack(side="left")
        self.loops_var = tk.StringVar(value=str(DEFAULT_MAX_LOOPS))
        ttk.Entry(top, textvariable=self.loops_var, width=8).pack(side="left", padx=4)
        self.loop_name_var.trace_add("write", lambda *_: self._sync_loop_fields())
        self.loops_var.trace_add("write", lambda *_: self._sync_loop_fields())

        ttk.Label(f, text="Hành động (double-click sửa • F2 đổi tên • Ctrl+C/Ctrl+V • kéo-thả):").pack(
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
        ttk.Button(col, text="🔁 Loop từ đây", width=12, command=self.set_loop_start).pack(pady=2)

        ttk.Label(f, style="Muted.TLabel",
                  text='Xám + "(1 lần)" = chạy 1 lần lúc đầu   •   🔁 = lặp mỗi vòng   •   '
                       'thêm "🔍 Kiểm tra mod" để Loop tự dừng khi đạt').pack(anchor="w", pady=(6, 0))

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

    def _steps_reordered(self):
        """Sau khi kéo-thả bước: giữ đúng bước đang chọn theo vị trí mới."""
        self.refresh_steps()

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
            if is_loop_step(st):
                self.action_pane.pack_forget()
                self.loop_pane.pack(fill="both", expand=True)
                self.loop_name_var.set(st.get("name") or "")
                self.loops_var.set(str(st.get("max_loops", DEFAULT_MAX_LOOPS)))
                self.refresh()
            else:
                self.loop_pane.pack_forget()
                self.action_pane.pack(fill="both", expand=True)
                self.single_lbl.config(text=action_display(st))
                self.refresh_problems()
        finally:
            self._syncing = False

    def _sync_loop_fields(self):
        """Ô Tên Loop / Số vòng đổi -> ghi ngược vào bước đang chọn."""
        if getattr(self, "_syncing", False):
            return
        st = self.cur_step
        if st is None or not is_loop_step(st):
            return
        st["name"] = self.loop_name_var.get().strip() or "Loop"
        try:
            st["max_loops"] = max(1, int(self.loops_var.get() or 1))
        except ValueError:
            pass
        self.refresh_steps()

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
        if st is None or is_loop_step(st):
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
            "Tên bước (để trống = dùng mô tả tự sinh):" if not is_loop_step(st)
            else "Tên Action_Loop:",
            initialvalue=cur_name, parent=self.root)
        if new is None:
            return "break"
        new = new.strip()
        if is_loop_step(st):
            st["name"] = new or "Loop"
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
        if st is None or not is_loop_step(st):
            self.refresh_problems()
            return
        self.listbox.delete(0, tk.END)
        acts = self.actions
        n = len(acts)
        start = max(0, min(self.loop_start_index, n))
        self.loop_start_index = start
        for idx, a in enumerate(acts):
            i = idx + 1
            looping = idx >= start
            prefix = "🔁 " if looping else "    "
            suffix = "" if looping else "   (1 lần)"
            self.listbox.insert(tk.END, f"{prefix}{i}.  {action_display(a)}{suffix}")
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
        if i is not None and st is not None and is_loop_step(st) and 0 <= i < len(self.actions):
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

    def _enable_drag_reorder(self, listbox, get_list, on_refresh):
        """Cho phép kéo-thả 1 dòng để đổi vị trí trong danh sách (Hành động / Điều kiện).
        Kéo sẽ CHÈN dòng vào đúng vị trí thả (các dòng ở giữa tự dồn), không phải hoán đổi."""
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

    # ---- xem lại điểm đã chọn (toàn bộ Process) ----
    def review_points(self):
        pts = []

        def add(a, label):
            pt = a.get("point")
            if not pt:
                return
            color = THEME["ok"] if a.get("type") == "check_mod" else THEME["accent"]
            pts.append((pt[0], pt[1], label, color))

        for si, st in enumerate(self.steps, 1):
            if is_loop_step(st):
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
        """Dữ liệu LƯU FILE — định dạng Process (nhiều bước nối tiếp)."""
        return {
            "schema": 3,
            "type": "process",
            "name": self.process_name_var.get().strip() or "Process 1",
            "game": self.settings["game"],
            "start_delay": max(0, int(self.start_var.get() or 0)),
            "steps": self.steps,
        }

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
        mnu.add_command(label=f"🔁 Lưu riêng Loop đang chọn"
                              f"{'' if can_loop else '  (bước hiện tại không phải Loop)'}",
                        command=self.save_loop_template,
                        state=("normal" if can_loop else "disabled"))
        mnu.add_separator()
        mnu.add_command(label="📄 Lưu ra file khác...", command=self.save_template)
        self._popup_under(self.save_btn, mnu)

    def _show_open_menu(self):
        mnu = tk.Menu(self.root, tearoff=0)
        mnu.add_command(label="📂 Mở Process (thay toàn bộ)", command=self.open_process_template)
        mnu.add_command(label="➕ Chèn Loop có sẵn vào Process này",
                        command=self.insert_loop_template)
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
                                "Bước đang chọn là hành động lẻ. Hãy chọn 1 Action_Loop rồi lưu lại.")
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
                "Nếu đây là template Process, hãy dùng \"Mở Process\" thay vì \"Chèn Loop\".")
            return
        pos = self.cur + 1 if self.steps else 0
        self.steps.insert(pos, step)
        self.refresh_steps()
        self.select_step(pos)
        self.status.set(f"Đã chèn Loop \"{step['name']}\" vào Process.")

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
        threading.Thread(target=self._run_worker, args=(cfg,), daemon=True).start()

    def stop_run(self):
        self.stop_flag.set()

    def _run_worker(self, cfg):
        """Chỉ còn nhiệm vụ NỐI bộ máy chạy (core.ProcessRunner) với giao diện.
        Toàn bộ logic chạy nằm trong core.py, không phụ thuộc tkinter."""
        runner = ProcessRunner(cfg, self.stop_flag,
                               on_status=self._set_status,
                               on_log=self._log_check)
        status, total_loops = runner.run()
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
            if self.hotkey_handle is not None:
                try:
                    keyboard.remove_hotkey(self.hotkey_handle)
                except Exception:
                    pass
                self.hotkey_handle = None
            notify(loops, status)
        try:
            self.root.after(0, done)
        except tk.TclError:
            # cửa sổ đã đóng khi đang chạy — vẫn gỡ hotkey toàn cục cho sạch
            if self.hotkey_handle is not None:
                try:
                    keyboard.remove_hotkey(self.hotkey_handle)
                except Exception:
                    pass
                self.hotkey_handle = None


def main():
    root = tk.Tk()
    enable_dpi(root)
    s = load_settings()
    set_accent(s.get("accent") or THEME["accent"])
    apply_theme(root)
    AutoClickerApp(root)
    dark_titlebar(root)
    # ép vẽ lại 1 lần để thanh tiêu đề đổi màu ngay (không thì phải đợi tương tác)
    root.withdraw()
    root.update_idletasks()
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
