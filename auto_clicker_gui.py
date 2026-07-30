"""
AUTO CLICKER - v2 (GUI + dừng theo "dòng chữ")
==============================================
Giao diện tạo/sửa flow, lưu & mở template, chạy loop.

DỪNG LOOP khi 1 trong các điều kiện xảy ra:
  - Đủ số vòng lặp (max_loops), HOẶC
  - Vùng canh trên màn hình XUẤT HIỆN "dòng chữ" đã chụp mẫu (so khớp ảnh bằng OpenCV).
  - Bất cứ lúc nào: nút DỪNG, phím F6, hoặc hất chuột vào góc trên-trái.

CHẠY:   python auto_clicker_gui.py

Cần: pip install pyautogui keyboard plyer opencv-python mss numpy
"""

import os
import sys
import json
import time
import base64
import random
import threading
import ctypes

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import pyautogui
    import keyboard
except ImportError:
    print("Thiếu thư viện. Cài:  pip install pyautogui keyboard plyer")
    sys.exit(1)

# Thư viện cho phần nhận diện ảnh (không bắt buộc — thiếu thì tắt tính năng đó)
try:
    import cv2
    import numpy as np
    import mss
    HAS_CV = True
except Exception:
    HAS_CV = False

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

# ---------------- Hằng số & tiện ích ----------------
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


def do_action(a, stop_flag):
    t = a["type"]
    if t == "left_click":
        pyautogui.click(a["point"][0], a["point"][1], button="left")
    elif t == "right_click":
        pyautogui.click(a["point"][0], a["point"][1], button="right")
    elif t == "double_click":
        pyautogui.doubleClick(a["point"][0], a["point"][1])
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
        notification.notify(title="Auto Clicker",
                            message=f"{status}: {loops} vòng", timeout=5)
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


# ---------------- Chụp / so khớp ảnh ----------------
def grab_bgr(bbox):
    """bbox = (left, top, w, h) tuyệt đối -> ảnh BGR."""
    with mss.mss() as sct:
        raw = sct.grab({"left": bbox[0], "top": bbox[1],
                        "width": bbox[2], "height": bbox[3]})
    return cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)


def grab_primary():
    with mss.mss() as sct:
        mon = sct.monitors[1]  # màn hình chính
        raw = sct.grab(mon)
    return cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)


def png_b64(img_bgr):
    ok, buf = cv2.imencode(".png", img_bgr)
    return base64.b64encode(buf.tobytes()).decode("ascii")


def b64_png(s):
    arr = np.frombuffer(base64.b64decode(s), np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def match_any(region_bgr, templates, threshold):
    """True nếu bất kỳ template nào khớp trong region với điểm >= threshold."""
    rh, rw = region_bgr.shape[:2]
    for tpl in templates:
        if tpl is None:
            continue
        th, tw = tpl.shape[:2]
        if th > rh or tw > rw:
            continue  # mẫu lớn hơn vùng canh -> bỏ qua
        res = cv2.matchTemplate(region_bgr, tpl, cv2.TM_CCOEFF_NORMED)
        if float(res.max()) >= threshold:
            return True
    return False


# ---------------- Overlay kéo chọn vùng ----------------
class RegionSelector:
    """Phủ toàn desktop, kéo chuột để chọn hình chữ nhật -> bbox (x,y,w,h) tuyệt đối."""

    def __init__(self, root, callback, hint="Kéo chuột để chọn vùng. Esc để huỷ."):
        self.callback = callback
        u = ctypes.windll.user32
        self.vx, self.vy = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
        self.vw, self.vh = u.GetSystemMetrics(78), u.GetSystemMetrics(79)
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry(f"{self.vw}x{self.vh}+{self.vx}+{self.vy}")
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.25)
        except Exception:
            pass
        self.canvas = tk.Canvas(self.win, cursor="cross", bg="gray15",
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(self.vw // 2, 30, fill="white", text=hint,
                                font=("Segoe UI", 14))
        self.start = None
        self.rect = None
        self.canvas.bind("<ButtonPress-1>", self._down)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._up)
        self.win.bind("<Escape>", lambda e: self._finish(None))
        self.win.focus_force()

    def _down(self, e):
        self.start = (e.x, e.y)
        self.rect = self.canvas.create_rectangle(e.x, e.y, e.x, e.y,
                                                  outline="red", width=2)

    def _drag(self, e):
        if self.rect:
            self.canvas.coords(self.rect, self.start[0], self.start[1], e.x, e.y)

    def _up(self, e):
        if not self.start:
            return
        x1, y1 = self.start
        x2, y2 = e.x, e.y
        w, h = abs(x2 - x1), abs(y2 - y1)
        if w < 3 or h < 3:
            self._finish(None)
            return
        self._finish((self.vx + min(x1, x2), self.vy + min(y1, y2), w, h))

    def _finish(self, bbox):
        try:
            self.win.destroy()
        except Exception:
            pass
        self.callback(bbox)


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
            ttk.Button(self.body, text="🎯 Chọn điểm (F8)", command=self._pick).grid(
                row=1, column=0, columnspan=4, pady=(8, 0), sticky="ew")
        elif t == "scroll":
            ttk.Label(self.body, text="Lượng cuộn (âm = xuống):").grid(row=0, column=0, sticky="w")
            ttk.Entry(self.body, textvariable=self.amount_var, width=8).grid(row=0, column=1, padx=6)
        elif t == "key_press":
            ttk.Label(self.body, text="Phím (vd: enter, a, space, f5):").grid(row=0, column=0, sticky="w")
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


# ---------------- App chính ----------------
class AutoClickerApp:
    def __init__(self, root):
        self.root = root
        self.actions = []
        self.refs = []              # [{"b64":.., "w":.., "h":..}] các mẫu "dòng chữ"
        self.watch_region = None    # (x,y,w,h) hoặc None = toàn màn hình chính
        self.stop_flag = threading.Event()
        self.hotkey_handle = None
        root.title("Auto Clicker — v2")
        root.geometry("620x720")
        self._build_ui()
        self.refresh()
        self._refresh_refs()
        self._update_watch_label()

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="both", expand=True)

        left = ttk.Frame(top)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Danh sách hành động (double-click để sửa):").pack(anchor="w")
        self.listbox = tk.Listbox(left, height=10, activestyle="dotbox")
        self.listbox.pack(fill="both", expand=True, pady=(4, 0))
        self.listbox.bind("<Double-Button-1>", lambda e: self.edit_action())

        right = ttk.Frame(top, padding=(10, 18))
        right.pack(side="left", fill="y")
        for text, cmd in [
            ("➕ Thêm", self.add_action),
            ("✏ Sửa", self.edit_action),
            ("🗑 Xoá", self.delete_action),
            ("⬆ Lên", lambda: self.move(-1)),
            ("⬇ Xuống", lambda: self.move(1)),
        ]:
            ttk.Button(right, text=text, width=10, command=cmd).pack(pady=3)

        cfg = ttk.LabelFrame(self.root, text="Cấu hình", padding=10)
        cfg.pack(fill="x", padx=10)
        ttk.Label(cfg, text="Số vòng lặp:").grid(row=0, column=0, sticky="w")
        self.loops_var = tk.StringVar(value="1000")
        ttk.Entry(cfg, textvariable=self.loops_var, width=8).grid(row=0, column=1, padx=(4, 16))
        ttk.Label(cfg, text="Đếm ngược (s):").grid(row=0, column=2, sticky="w")
        self.start_var = tk.StringVar(value="3")
        ttk.Entry(cfg, textvariable=self.start_var, width=6).grid(row=0, column=3, padx=(4, 16))
        ttk.Label(cfg, text="Phím dừng:").grid(row=0, column=4, sticky="w")
        self.hotkey_var = tk.StringVar(value="f6")
        ttk.Entry(cfg, textvariable=self.hotkey_var, width=6).grid(row=0, column=5, padx=4)

        # --- Điều kiện dừng theo "dòng chữ" ---
        end = ttk.LabelFrame(self.root, text='Dừng khi thấy "dòng chữ" (so khớp ảnh)', padding=10)
        end.pack(fill="x", padx=10, pady=(8, 0))

        self.end_enabled = tk.BooleanVar(value=False)
        chk = ttk.Checkbutton(end, text="Bật", variable=self.end_enabled)
        chk.grid(row=0, column=0, sticky="w")
        ttk.Label(end, text="Ngưỡng khớp (0–1):").grid(row=0, column=1, sticky="e", padx=(10, 2))
        self.threshold_var = tk.StringVar(value="0.85")
        ttk.Entry(end, textvariable=self.threshold_var, width=6).grid(row=0, column=2, sticky="w")

        ttk.Label(end, text="Vùng canh:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.watch_lbl = ttk.Label(end, text="Toàn màn hình chính")
        self.watch_lbl.grid(row=1, column=1, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(end, text="Chọn vùng", command=self.select_watch).grid(row=1, column=3, padx=4, pady=(6, 0))
        ttk.Button(end, text="Xoá vùng", command=self.clear_watch).grid(row=1, column=4, pady=(6, 0))

        ttk.Label(end, text='Mẫu "dòng chữ":').grid(row=2, column=0, sticky="nw", pady=(6, 0))
        self.refs_box = tk.Listbox(end, height=3, width=30)
        self.refs_box.grid(row=2, column=1, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(end, text="➕ Chụp mẫu", command=self.capture_ref).grid(row=2, column=3, padx=4, pady=(6, 0), sticky="ew")
        ttk.Button(end, text="🗑 Xoá mẫu", command=self.delete_ref).grid(row=2, column=4, pady=(6, 0), sticky="ew")
        end.columnconfigure(1, weight=1)

        if not HAS_CV:
            chk.config(state="disabled")
            ttk.Label(end, foreground="red",
                      text="Thiếu thư viện: pip install opencv-python mss numpy").grid(
                row=3, column=0, columnspan=5, sticky="w", pady=(6, 0))

        bar = ttk.Frame(self.root, padding=10)
        bar.pack(fill="x")
        ttk.Button(bar, text="💾 Lưu template", command=self.save_template).pack(side="left")
        ttk.Button(bar, text="📂 Mở template", command=self.load_template).pack(side="left", padx=6)
        self.run_btn = ttk.Button(bar, text="▶ CHẠY", command=self.start_run)
        self.run_btn.pack(side="right")
        self.stop_btn = ttk.Button(bar, text="■ DỪNG", command=self.stop_run, state="disabled")
        self.stop_btn.pack(side="right", padx=6)

        self.status = tk.StringVar(value="Sẵn sàng.")
        ttk.Label(self.root, textvariable=self.status, relief="sunken",
                  anchor="w", padding=4).pack(fill="x", side="bottom")

    # --- thao tác danh sách hành động ---
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

    # --- chọn điểm click (F8) ---
    def pick_point(self, callback, hide=None):
        self.status.set("Di chuột tới vị trí cần chọn rồi nhấn F8...")
        if hide:
            hide.withdraw()
        self.root.iconify()

        def worker():
            keyboard.wait("f8")
            pos = pyautogui.position()

            def done():
                self.root.deiconify()
                if hide:
                    hide.deiconify()
                    hide.grab_set()
                self.status.set(f"Đã chọn điểm ({int(pos.x)}, {int(pos.y)}).")
                callback((int(pos.x), int(pos.y)))
            self.root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    # --- vùng canh & mẫu "dòng chữ" ---
    def _update_watch_label(self):
        if self.watch_region:
            x, y, w, h = self.watch_region
            self.watch_lbl.config(text=f"({x}, {y})  {w}×{h}")
        else:
            self.watch_lbl.config(text="Toàn màn hình chính")

    def _refresh_refs(self):
        self.refs_box.delete(0, tk.END)
        for i, r in enumerate(self.refs, 1):
            self.refs_box.insert(tk.END, f"Mẫu #{i}  ({r['w']}×{r['h']})")

    def select_watch(self):
        if not HAS_CV:
            return
        self.status.set("Kéo chuột chọn VÙNG CANH (nơi dòng chữ sẽ hiện ra)...")
        self.root.withdraw()

        def on_sel(bbox):
            self.root.deiconify()
            if bbox:
                self.watch_region = bbox
                self._update_watch_label()
                self.status.set(f"Vùng canh: ({bbox[0]},{bbox[1]}) {bbox[2]}×{bbox[3]}")
            else:
                self.status.set("Đã huỷ chọn vùng.")

        RegionSelector(self.root, on_sel, hint="Kéo chọn VÙNG CANH. Esc để huỷ.")

    def clear_watch(self):
        self.watch_region = None
        self._update_watch_label()

    def capture_ref(self):
        if not HAS_CV:
            messagebox.showerror("Thiếu thư viện", "Cần: pip install opencv-python mss numpy")
            return
        self.status.set("Kéo chuột quanh DÒNG CHỮ cần nhận diện...")
        self.root.withdraw()

        def on_sel(bbox):
            if not bbox:
                self.root.deiconify()
                self.status.set("Đã huỷ chụp mẫu.")
                return

            def grab():
                img = grab_bgr(bbox)
                self.refs.append({"b64": png_b64(img), "w": bbox[2], "h": bbox[3]})
                self._refresh_refs()
                self.end_enabled.set(True)
                self.root.deiconify()
                self.status.set(f"Đã thêm mẫu ({bbox[2]}×{bbox[3]}).")
            # đợi overlay biến mất khỏi màn hình rồi mới chụp
            self.root.after(200, grab)

        RegionSelector(self.root, on_sel, hint="Kéo chọn quanh DÒNG CHỮ. Esc để huỷ.")

    def delete_ref(self):
        s = self.refs_box.curselection()
        if not s:
            return
        del self.refs[s[0]]
        self._refresh_refs()

    # --- template ---
    def collect(self):
        return {
            "name": "template",
            "actions": self.actions,
            "max_loops": max(1, int(self.loops_var.get() or 1)),
            "start_delay": max(0, int(self.start_var.get() or 0)),
            "stop_hotkey": self.hotkey_var.get().strip() or "f6",
            "end_image": {
                "enabled": bool(self.end_enabled.get()),
                "threshold": float(self.threshold_var.get() or 0.85),
                "watch_region": list(self.watch_region) if self.watch_region else None,
                "refs": [r["b64"] for r in self.refs],
            },
        }

    def save_template(self):
        if not self.actions:
            messagebox.showwarning("Trống", "Chưa có hành động nào để lưu.")
            return
        try:
            data = self.collect()
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
            self.hotkey_var.set(data.get("stop_hotkey", "f6"))

            ei = data.get("end_image") or {}
            self.end_enabled.set(bool(ei.get("enabled", False)))
            self.threshold_var.set(str(ei.get("threshold", 0.85)))
            wr = ei.get("watch_region")
            self.watch_region = tuple(wr) if wr else None
            self.refs = []
            for b in ei.get("refs", []):
                if HAS_CV:
                    img = b64_png(b)
                    self.refs.append({"b64": b, "w": img.shape[1], "h": img.shape[0]})
                else:
                    self.refs.append({"b64": b, "w": "?", "h": "?"})

            self.refresh()
            self._refresh_refs()
            self._update_watch_label()
            self.status.set(f"Đã mở template: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    # --- chạy / dừng ---
    def start_run(self):
        if not self.actions:
            messagebox.showwarning("Trống", "Chưa có hành động nào.")
            return
        try:
            cfg = self.collect()
        except ValueError:
            messagebox.showerror("Lỗi", "Cấu hình số không hợp lệ.")
            return
        ei = cfg["end_image"]
        if ei["enabled"] and not ei["refs"]:
            if not messagebox.askyesno("Chưa có mẫu",
                    'Bạn bật "dừng khi thấy dòng chữ" nhưng chưa chụp mẫu nào.\n'
                    "Chạy tiếp và chỉ dừng theo số vòng?"):
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
            self._set_status(f"Bắt đầu sau {i}s... (chuyển sang cửa sổ đích)")
            time.sleep(1)

        ei = cfg["end_image"]
        templates = []
        if HAS_CV and ei["enabled"] and ei["refs"]:
            templates = [b64_png(b) for b in ei["refs"]]
        watch = ei["watch_region"]
        threshold = ei["threshold"]

        loops = 0
        image_hit = False
        last_check = 0.0
        while not self.stop_flag.is_set() and loops < cfg["max_loops"]:
            # kiểm tra "dòng chữ" (giới hạn ~4 lần/giây để đỡ tốn CPU)
            if templates and (time.time() - last_check) >= 0.25:
                last_check = time.time()
                try:
                    region = grab_bgr(watch) if watch else grab_primary()
                    if match_any(region, templates, threshold):
                        image_hit = True
                        break
                except Exception:
                    pass

            for a in cfg["actions"]:
                if self.stop_flag.is_set():
                    break
                try:
                    do_action(a, self.stop_flag)
                except pyautogui.FailSafeException:
                    self.stop_flag.set()
                    break
            loops += 1
            if loops % 5 == 0 or loops == cfg["max_loops"]:
                self._set_status(f"Đang chạy... {loops}/{cfg['max_loops']} vòng "
                                 f"(nhấn {cfg['stop_hotkey'].upper()} để dừng)")

        if image_hit:
            status = "Hoàn thành (thấy dòng chữ)"
        elif self.stop_flag.is_set():
            status = "Đã dừng"
        else:
            status = "Hoàn thành (đủ số vòng)"
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
