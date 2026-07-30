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
import re
import sys
import json
import time
import random
import threading
import ctypes
import urllib.request

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import pyautogui
    import keyboard
except ImportError:
    print("Thiếu thư viện. Cài:  pip install pyautogui keyboard pyperclip plyer")
    sys.exit(1)

try:
    import pyperclip
    HAS_CLIP = True
except Exception:
    HAS_CLIP = False

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

# ---------------- Đường dẫn & cấu hình chung ----------------
GAMES = {"poe2": "PoE2", "poe1": "PoE1"}
STATS_API = {
    "poe1": "https://www.pathofexile.com/api/trade/data/stats",
    "poe2": "https://www.pathofexile.com/api/trade2/data/stats",
}
KEEP_LABELS = {"Explicit", "Implicit"}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

SETTINGS_DEFAULT = {
    "game": "poe2",
    "pre_click_ms": 60,
    "hover_ms": 250,
    "copy_keys": "ctrl+c",
    "stop_hotkey": "f6",
}


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(name):
    """Ưu tiên file cạnh exe (ghi/đọc được), fallback file bundled trong exe."""
    p = os.path.join(app_dir(), name)
    if os.path.exists(p):
        return p
    base = getattr(sys, "_MEIPASS", app_dir())
    return os.path.join(base, name)


def load_settings():
    s = dict(SETTINGS_DEFAULT)
    try:
        with open(os.path.join(app_dir(), "settings.json"), encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    if s.get("game") not in GAMES:
        s["game"] = "poe2"
    return s


def save_settings(s):
    try:
        with open(os.path.join(app_dir(), "settings.json"), "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_mods(game):
    try:
        with open(resource_path(f"mods_{game}.txt"), encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except Exception:
        return []


def fetch_mod_texts(game):
    req = urllib.request.Request(STATS_API[game],
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    texts = []
    for cat in data.get("result", []):
        if cat.get("label") in KEEP_LABELS:
            for e in cat.get("entries", []):
                t = (e.get("text") or "").strip()
                if t:
                    texts.append(t)
    return sorted(set(texts), key=lambda s: s.lower())


# ---------------- So khớp mod theo khối (đúng Tier) ----------------
def norm(text):
    """Chuẩn hoá 1 dòng mod: bỏ số & ký hiệu, chỉ giữ chữ, để so khớp chính xác."""
    t = text.lower().replace("#", " ")
    t = re.sub(r"[0-9]+", " ", t)
    t = re.sub(r"[()\[\]+%.,:\-–—/]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def parse_blocks(clipboard):
    """Tách clipboard item thành các khối mod: [{'tier': int|None, 'stats': [norm_line,...]}]."""
    blocks = []
    cur = None
    for line in clipboard.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("{"):
            m = re.search(r"\(Tier:\s*(\d+)\)", s)
            cur = {"tier": int(m.group(1)) if m else None, "stats": []}
            blocks.append(cur)
        elif cur is not None and not s.startswith("-"):
            n = norm(s)
            if n:
                cur["stats"].append(n)
    return blocks


def condition_hit(blocks, cond):
    """Khớp khi có 1 KHỐI vừa chứa đúng dòng mod, vừa đúng tier (tier None = mọi tier)."""
    target = norm(cond.get("mod", ""))
    if not target:
        return False
    tier = cond.get("tier")
    for b in blocks:
        if (tier is None or b["tier"] == tier) and target in b["stats"]:
            return True
    return False


def cond_display(c):
    tier = c.get("tier")
    tt = f"Tier {tier}" if tier is not None else "mọi tier"
    return f"{c.get('mod', '')}   ·  {tt}"


# ---------------- Hành động ----------------
ACTION_TYPES = ["left_click", "right_click", "double_click", "move",
                "scroll", "key_press", "delay"]
ACTION_LABELS = {
    "left_click": "Trái-click", "right_click": "Phải-click",
    "double_click": "Double-click", "move": "Di chuyển tới",
    "scroll": "Cuộn chuột", "key_press": "Nhấn phím", "delay": "Delay",
}
POINT_TYPES = ("left_click", "right_click", "double_click", "move")


def action_summary(a):
    t = a["type"]
    if t in POINT_TYPES:
        return f"{ACTION_LABELS[t]} @ ({a['point'][0]}, {a['point'][1]})"
    if t == "scroll":
        return f"Cuộn {a.get('amount', -300)}"
    if t == "key_press":
        return f"Nhấn phím: {a.get('key', '')}"
    if t == "delay":
        return f"Delay {a['min_ms']}–{a['max_ms']} ms"
    return t


def human_sleep(min_ms, max_ms, stop_flag):
    total = random.uniform(min_ms, max_ms) / 1000.0
    end = time.time() + total
    while time.time() < end:
        if stop_flag.is_set():
            return
        time.sleep(min(0.02, max(0.0, end - time.time())))


def do_action(a, stop_flag, pre_click_ms=0):
    t = a["type"]
    if t in ("left_click", "right_click", "double_click"):
        x, y = a["point"]
        pyautogui.moveTo(x, y)
        if pre_click_ms > 0:
            human_sleep(pre_click_ms, pre_click_ms, stop_flag)
        if stop_flag.is_set():
            return
        if t == "left_click":
            pyautogui.click(button="left")
        elif t == "right_click":
            pyautogui.click(button="right")
        else:
            pyautogui.doubleClick()
    elif t == "move":
        pyautogui.moveTo(a["point"][0], a["point"][1], duration=0.1)
    elif t == "scroll":
        pyautogui.scroll(a.get("amount", -300))
    elif t == "key_press":
        pyautogui.press(a["key"])
    elif t == "delay":
        human_sleep(a["min_ms"], a["max_ms"], stop_flag)


def notify(loops, status):
    try:
        import winsound
        winsound.MessageBeep()
    except Exception:
        pass
    try:
        from plyer import notification
        notification.notify(title="Auto Clicker", message=f"{status}: {loops} vòng", timeout=5)
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
        self.canvas = tk.Canvas(self.win, cursor="none", bg="gray10", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.vline = self.canvas.create_line(0, 0, 0, self.vh, fill="red", width=2)
        self.hline = self.canvas.create_line(0, 0, self.vw, 0, fill="red", width=2)
        self.dot = self.canvas.create_oval(0, 0, 0, 0, outline="yellow", width=2)
        self.coord_bg = self.canvas.create_rectangle(0, 0, 0, 0, fill="black", outline="")
        self.coord = self.canvas.create_text(0, 0, fill="yellow", anchor="nw",
                                             font=("Consolas", 13, "bold"), text="")
        self.canvas.create_text(self.vw // 2, 30, fill="white", font=("Segoe UI", 15),
                                text="Di chuột tới điểm cần chọn  •  Click / F8 / Enter để chốt  •  Esc để huỷ")
        self.canvas.bind("<Motion>", self._move)
        self.canvas.bind("<ButtonPress-1>", lambda e: self._pick(e.x, e.y))
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
        top.columnconfigure(1, weight=1)
        self.body = ttk.Frame(self, padding=10)
        self.body.pack(fill="x")
        self.x_var = tk.StringVar(value="0")
        self.y_var = tk.StringVar(value="0")
        self.amount_var = tk.StringVar(value="-300")
        self.key_var = tk.StringVar(value="enter")
        self.min_var = tk.StringVar(value="200")
        self.max_var = tk.StringVar(value="1000")
        if action:
            if "point" in action:
                self.x_var.set(action["point"][0])
                self.y_var.set(action["point"][1])
            if action["type"] == "scroll":
                self.amount_var.set(action.get("amount", -300))
            if action["type"] == "key_press":
                self.key_var.set(action.get("key", "enter"))
            if action["type"] == "delay":
                self.min_var.set(action.get("min_ms", 200))
                self.max_var.set(action.get("max_ms", 1000))
        btns = ttk.Frame(self, padding=10)
        btns.pack(fill="x")
        ttk.Button(btns, text="Lưu", command=self._save).pack(side="right")
        ttk.Button(btns, text="Huỷ", command=self.destroy).pack(side="right", padx=6)
        self._render()

    def _render(self):
        for w in self.body.winfo_children():
            w.destroy()
        t = self.type_var.get()
        if t in POINT_TYPES:
            ttk.Label(self.body, text="X:").grid(row=0, column=0, sticky="w")
            ttk.Entry(self.body, textvariable=self.x_var, width=8).grid(row=0, column=1)
            ttk.Label(self.body, text="Y:").grid(row=0, column=2, sticky="w", padx=(10, 0))
            ttk.Entry(self.body, textvariable=self.y_var, width=8).grid(row=0, column=3)
            ttk.Button(self.body, text="🎯 Chọn điểm (crosshair)", command=self._pick).grid(
                row=1, column=0, columnspan=4, pady=(8, 0), sticky="ew")
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

    def _pick(self):
        self.app.pick_point(self._on_pick, hide=self)

    def _on_pick(self, pt):
        self.x_var.set(pt[0])
        self.y_var.set(pt[1])

    def _save(self):
        t = self.type_var.get()
        try:
            if t in POINT_TYPES:
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

        upd = ttk.LabelFrame(pad, text="Danh sách mod", padding=8)
        upd.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(upd, text="⟳ Cập nhật từ mạng", command=self._update_mods).grid(row=0, column=0)
        self.upd_status = ttk.Label(upd, text="")
        self.upd_status.grid(row=0, column=1, sticky="w", padx=8)
        self._refresh_count()

        btns = ttk.Frame(pad)
        btns.grid(row=6, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Lưu & đóng", command=self._save).pack(side="right")
        ttk.Button(btns, text="Huỷ", command=self.destroy).pack(side="right", padx=6)

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
                with open(os.path.join(app_dir(), f"mods_{game}.txt"), "w", encoding="utf-8") as f:
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
        })
        save_settings(self.app.settings)
        self.app.apply_settings()
        self.destroy()


# ---------------- App chính ----------------
class AutoClickerApp:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.actions = []
        self.hover_point = None
        self.conditions = []            # [{"mod": "...", "tier": int|None}]  (thứ tự = ưu tiên)
        self.all_mods = load_mods(self.settings["game"])
        self.stop_flag = threading.Event()
        self.hotkey_handle = None
        root.geometry("680x820")
        self._build_ui()
        self.refresh()
        self._refresh_mods()
        self._refresh_conds()
        self._update_hover_label()
        self.apply_settings()

    # ---- UI ----
    def _build_ui(self):
        head = ttk.Frame(self.root, padding=(10, 8, 10, 0))
        head.pack(fill="x")
        self.title_lbl = ttk.Label(head, text="Auto Clicker", font=("Segoe UI", 12, "bold"))
        self.title_lbl.pack(side="left")
        ttk.Button(head, text="⚙ Cài đặt", command=self.open_settings).pack(side="right")

        top = ttk.Frame(self.root, padding=(10, 6))
        top.pack(fill="both", expand=True)
        left = ttk.Frame(top)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Danh sách hành động (double-click để sửa):").pack(anchor="w")
        self.listbox = tk.Listbox(left, height=7, activestyle="dotbox", exportselection=False)
        self.listbox.pack(fill="both", expand=True, pady=(4, 0))
        self.listbox.bind("<Double-Button-1>", lambda e: self.edit_action())
        right = ttk.Frame(top, padding=(10, 4))
        right.pack(side="left", fill="y")
        for text, cmd in [
            ("➕ Thêm", self.add_action), ("✏ Sửa", self.edit_action),
            ("🗑 Xoá", self.delete_action), ("⬆ Lên", lambda: self.move(-1)),
            ("⬇ Xuống", lambda: self.move(1)),
        ]:
            ttk.Button(right, text=text, width=10, command=cmd).pack(pady=2)

        cfg = ttk.LabelFrame(self.root, text="Cấu hình", padding=8)
        cfg.pack(fill="x", padx=10)
        ttk.Label(cfg, text="Số vòng lặp:").grid(row=0, column=0, sticky="w")
        self.loops_var = tk.StringVar(value="1000")
        ttk.Entry(cfg, textvariable=self.loops_var, width=8).grid(row=0, column=1, padx=(4, 16))
        ttk.Label(cfg, text="Đếm ngược (s):").grid(row=0, column=2, sticky="w")
        self.start_var = tk.StringVar(value="3")
        ttk.Entry(cfg, textvariable=self.start_var, width=6).grid(row=0, column=3, padx=(4, 16))
        ttk.Label(cfg, text="(các cài đặt khác nằm ở nút ⚙ Cài đặt)", foreground="gray").grid(
            row=0, column=4, sticky="w")

        stop = ttk.LabelFrame(self.root, text="Dừng khi item có MOD (chọn mod + tier)", padding=8)
        stop.pack(fill="both", expand=True, padx=10, pady=(8, 0))
        stop.columnconfigure(0, weight=1)

        r0 = ttk.Frame(stop)
        r0.grid(row=0, column=0, sticky="ew")
        self.stop_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(r0, text="Bật", variable=self.stop_enabled).pack(side="left")
        ttk.Label(r0, text="   Rê chuột tới item:").pack(side="left")
        self.hover_lbl = ttk.Label(r0, text="(chưa chọn)")
        self.hover_lbl.pack(side="left", padx=4)
        ttk.Button(r0, text="Chọn điểm", command=self.select_hover).pack(side="left", padx=2)
        ttk.Button(r0, text="Xoá", command=self.clear_hover).pack(side="left")

        r1 = ttk.Frame(stop)
        r1.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(r1, text="Tìm mod:").pack(side="left")
        self.search_var = tk.StringVar()
        se = ttk.Entry(r1, textvariable=self.search_var)
        se.pack(side="left", fill="x", expand=True, padx=(4, 0))
        se.bind("<KeyRelease>", self._refresh_mods)

        mfr = ttk.Frame(stop)
        mfr.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        msb = ttk.Scrollbar(mfr, orient="vertical")
        self.master_box = tk.Listbox(mfr, height=5, yscrollcommand=msb.set, exportselection=False)
        msb.config(command=self.master_box.yview)
        self.master_box.pack(side="left", fill="both", expand=True)
        msb.pack(side="right", fill="y")
        self.master_box.bind("<Double-Button-1>", lambda e: self.add_condition())

        r3 = ttk.Frame(stop)
        r3.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(r3, text="Tier (để trống = mọi tier):").pack(side="left")
        self.tier_var = tk.StringVar()
        ttk.Entry(r3, textvariable=self.tier_var, width=6).pack(side="left", padx=(4, 8))
        ttk.Button(r3, text="➕ Thêm điều kiện ↓", command=self.add_condition).pack(side="left")
        self.mods_count_lbl = ttk.Label(r3, text="", foreground="gray")
        self.mods_count_lbl.pack(side="right")

        ttk.Label(stop, text="Điều kiện dừng — dòng TRÊN được ưu tiên trước:").grid(
            row=4, column=0, sticky="w", pady=(8, 0))
        cfr = ttk.Frame(stop)
        cfr.grid(row=5, column=0, sticky="ew")
        csb = ttk.Scrollbar(cfr, orient="vertical")
        self.cond_box = tk.Listbox(cfr, height=4, yscrollcommand=csb.set, exportselection=False)
        csb.config(command=self.cond_box.yview)
        self.cond_box.pack(side="left", fill="both", expand=True)
        csb.pack(side="right", fill="y")
        r6 = ttk.Frame(stop)
        r6.grid(row=6, column=0, sticky="w", pady=(4, 0))
        ttk.Button(r6, text="🗑 Xoá", command=self.del_condition).pack(side="left")
        ttk.Button(r6, text="⬆ Lên", command=lambda: self.move_cond(-1)).pack(side="left", padx=4)
        ttk.Button(r6, text="⬇ Xuống", command=lambda: self.move_cond(1)).pack(side="left")

        bar = ttk.Frame(self.root, padding=10)
        bar.pack(fill="x")
        ttk.Button(bar, text="💾 Lưu template", command=self.save_template).pack(side="left")
        ttk.Button(bar, text="📂 Mở template", command=self.load_template).pack(side="left", padx=6)
        self.run_btn = ttk.Button(bar, text="▶ CHẠY", command=self.start_run)
        self.run_btn.pack(side="right")
        self.stop_btn = ttk.Button(bar, text="■ DỪNG", command=self.stop_run, state="disabled")
        self.stop_btn.pack(side="right", padx=6)

        self.status = tk.StringVar(value="Sẵn sàng.")
        ttk.Label(self.root, textvariable=self.status, relief="sunken", anchor="w", padding=4).pack(
            fill="x", side="bottom")

    # ---- settings ----
    def open_settings(self):
        dlg = SettingsDialog(self.root, self)
        self.root.wait_window(dlg)

    def apply_settings(self):
        g = self.settings["game"]
        self.title_lbl.config(text=f"Auto Clicker — {GAMES.get(g, g)}")
        self.root.title(f"Auto Clicker — {GAMES.get(g, g)}")

    def reload_mods(self):
        self.all_mods = load_mods(self.settings["game"])
        self._refresh_mods()

    # ---- actions ----
    def refresh(self):
        self.listbox.delete(0, tk.END)
        for i, a in enumerate(self.actions, 1):
            self.listbox.insert(tk.END, f"{i}.  {action_summary(a)}")

    def _sel(self):
        s = self.listbox.curselection()
        return s[0] if s else None

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
        i = self._sel()
        if i is None:
            return
        del self.actions[i]
        self.refresh()

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

    def _update_hover_label(self):
        if self.hover_point:
            self.hover_lbl.config(text=f"({self.hover_point[0]}, {self.hover_point[1]})")
        else:
            self.hover_lbl.config(text="(chưa chọn)")

    def select_hover(self):
        self.pick_point(self._set_hover)

    def _set_hover(self, pt):
        self.hover_point = pt
        self._update_hover_label()

    def clear_hover(self):
        self.hover_point = None
        self._update_hover_label()

    # ---- mod picker & điều kiện ----
    def _refresh_mods(self, *_):
        q = self.search_var.get().strip().lower()
        words = q.split()
        self.master_box.delete(0, tk.END)
        shown = 0
        total = 0
        for m in self.all_mods:
            ml = m.lower()
            if all(w in ml for w in words):
                total += 1
                if shown < 500:
                    self.master_box.insert(tk.END, m)
                    shown += 1
        extra = f" (hiện {shown}/{total})" if total > shown else f" ({total})"
        self.mods_count_lbl.config(text=f"{len(self.all_mods)} mod{extra}")

    def add_condition(self):
        sel = self.master_box.curselection()
        if not sel:
            messagebox.showinfo("Chọn mod", "Hãy chọn 1 mod trong danh sách trước.")
            return
        mod = self.master_box.get(sel[0])
        tv = self.tier_var.get().strip()
        tier = None
        if tv:
            try:
                tier = int(tv)
            except ValueError:
                messagebox.showerror("Tier", "Tier phải là số (hoặc để trống).")
                return
        self.conditions.append({"mod": mod, "tier": tier})
        self.stop_enabled.set(True)
        self._refresh_conds()

    def _refresh_conds(self):
        self.cond_box.delete(0, tk.END)
        for i, c in enumerate(self.conditions, 1):
            self.cond_box.insert(tk.END, f"{i}.  {cond_display(c)}")

    def _cond_sel(self):
        s = self.cond_box.curselection()
        return s[0] if s else None

    def del_condition(self):
        i = self._cond_sel()
        if i is None:
            return
        del self.conditions[i]
        self._refresh_conds()

    def move_cond(self, d):
        i = self._cond_sel()
        if i is None:
            return
        j = i + d
        if 0 <= j < len(self.conditions):
            self.conditions[i], self.conditions[j] = self.conditions[j], self.conditions[i]
            self._refresh_conds()
            self.cond_box.selection_set(j)

    # ---- template ----
    def flow_data(self):
        return {
            "name": "template",
            "game": self.settings["game"],
            "actions": self.actions,
            "max_loops": max(1, int(self.loops_var.get() or 1)),
            "start_delay": max(0, int(self.start_var.get() or 0)),
            "hover_point": list(self.hover_point) if self.hover_point else None,
            "stop_enabled": bool(self.stop_enabled.get()),
            "conditions": [dict(c) for c in self.conditions],
        }

    def save_template(self):
        if not self.actions:
            messagebox.showwarning("Trống", "Chưa có hành động nào để lưu.")
            return
        try:
            data = self.flow_data()
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
            self.status.set(f"Đã lưu template: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def load_template(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")], initialdir=".")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.actions = data.get("actions", [])
            self.loops_var.set(str(data.get("max_loops", 1000)))
            self.start_var.set(str(data.get("start_delay", 3)))
            hp = data.get("hover_point")
            self.hover_point = tuple(hp) if hp else None
            self.stop_enabled.set(bool(data.get("stop_enabled", True)))

            conds = data.get("conditions")
            if conds is None:
                # tương thích template cũ (danh sách chữ gõ tay)
                old = (((data.get("stop") or {}).get("clipboard") or {}).get("texts")) or []
                conds = [{"mod": t, "tier": None} for t in old]
            self.conditions = [{"mod": c.get("mod", ""), "tier": c.get("tier")} for c in conds]

            self.refresh()
            self._refresh_conds()
            self._update_hover_label()
            self.status.set(f"Đã mở template: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    # ---- chạy / dừng ----
    def start_run(self):
        if not self.actions:
            messagebox.showwarning("Trống", "Chưa có hành động nào.")
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
        if cfg["stop_enabled"] and cfg["conditions"]:
            if not cfg["hover_point"]:
                if not messagebox.askyesno("Chưa chọn điểm",
                        "Chưa chọn điểm rê chuột vào item nên có thể không đọc được mod.\nVẫn chạy?"):
                    return
            if not HAS_CLIP:
                messagebox.showerror("Thiếu thư viện", "Cần: pip install pyperclip")
                return
        elif cfg["stop_enabled"] and not cfg["conditions"]:
            if not messagebox.askyesno("Chưa có điều kiện",
                    'Bật "dừng theo mod" nhưng chưa thêm điều kiện nào.\nChạy tiếp và chỉ dừng theo số vòng?'):
                return

        self.stop_flag.clear()
        self.run_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        try:
            self.hotkey_handle = keyboard.add_hotkey(cfg["stop_hotkey"], self.stop_flag.set)
        except Exception:
            self.hotkey_handle = None
        threading.Thread(target=self._run_worker, args=(cfg,), daemon=True).start()

    def stop_run(self):
        self.stop_flag.set()

    def _run_worker(self, cfg):
        for i in range(cfg["start_delay"], 0, -1):
            if self.stop_flag.is_set():
                break
            self._set_status(f"Bắt đầu sau {i}s... (chuyển sang cửa sổ game)")
            time.sleep(1)

        hover = cfg.get("hover_point")
        hover_ms = cfg.get("hover_ms", 250)
        copy_keys = [k.strip() for k in (cfg.get("copy_keys") or "ctrl+c").split("+") if k.strip()]
        conds = cfg["conditions"] if cfg["stop_enabled"] else []
        check = HAS_CLIP and conds

        loops = 0
        hit = None
        last_check = 0.0
        while not self.stop_flag.is_set() and loops < cfg["max_loops"]:
            if check and (time.time() - last_check) >= 0.30:
                last_check = time.time()
                try:
                    if hover:
                        pyautogui.moveTo(hover[0], hover[1])
                        human_sleep(hover_ms, hover_ms, self.stop_flag)
                    pyperclip.copy("")
                    pyautogui.hotkey(*copy_keys)
                    time.sleep(0.08)
                    blocks = parse_blocks(pyperclip.paste() or "")
                    for c in conds:                       # ưu tiên từ trên xuống
                        if condition_hit(blocks, c):
                            hit = c
                            break
                    if hit:
                        break
                except Exception:
                    pass

            for a in cfg["actions"]:
                if self.stop_flag.is_set():
                    break
                try:
                    do_action(a, self.stop_flag, cfg.get("pre_click_ms", 0))
                except pyautogui.FailSafeException:
                    self.stop_flag.set()
                    break
            loops += 1
            if loops % 5 == 0 or loops == cfg["max_loops"]:
                self._set_status(f"Đang chạy... {loops}/{cfg['max_loops']} vòng "
                                 f"(nhấn {cfg['stop_hotkey'].upper()} để dừng)")

        if hit:
            status = f"🎯 Ra mod: {cond_display(hit)}"
        elif self.stop_flag.is_set():
            status = "Đã dừng"
        else:
            status = "Hết số vòng (chưa ra mod)"
        self._finish(status, loops)

    def _set_status(self, msg):
        self.root.after(0, lambda: self.status.set(msg))

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
        self.root.after(0, done)


def main():
    root = tk.Tk()
    enable_dpi(root)
    AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
