"""Hộp thoại tạo/sửa hành động: KHÔNG được có widget nào chiếm grab toàn cục,
và phải luôn bấm được sau khi đóng.

Gốc bệnh cũ: ttk.Combobox ở nhánh mod_click -> MapPopdown -> ttk::globalGrab
-> grab -global, đặt bên trong hộp thoại vốn đã grab_set(). Trả grab hỏng là cả
máy ngừng nhận chuột/phím.
"""
import sys
import tkinter as tk
from tkinter import ttk

import _boot  # noqa: F401  — đặt sys.path + thư mục làm việc
import core
import auto_clicker_gui as m

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  OK   {name}")
    else:
        fail += 1
        print(f"  FAIL {name}   {detail}")


def walk(w, out):
    out.append(w)
    for c in w.winfo_children():
        walk(c, out)
    return out


root = tk.Tk()
root.withdraw()
m.apply_theme(root)
app = m.AutoClickerApp(root)
root.update()

print("=== 1. Không còn Combobox ở BẤT KỲ loại hành động nào ===")
bad = {}
for t in core.ACTION_TYPES:
    ed = m.ActionEditor(root, app, None)
    ed.type_var.set(t)
    ed._render()
    root.update()
    cbs = [w for w in walk(ed, []) if w.winfo_class() == "TCombobox"]
    if cbs:
        bad[t] = len(cbs)
    ed.destroy()
    root.update()
check("cả 10 loại đều không có TCombobox", not bad, bad)

print("\n=== 2. Mở/đóng hộp thoại không để sót grab ===")
before = root.grab_current()
ed = m.ActionEditor(root, app, {"type": "mod_click", "point": [10, 20],
                                "keys": "ctrl+shift", "button": "right"})
root.update()
during = ed.grab_current()
check("hộp thoại có giữ grab CỤC BỘ khi đang mở", during is not None, during)
check("grab thuộc về chính hộp thoại (không phải cửa sổ lạ)",
      str(during) == str(ed), (str(during), str(ed)))
ed.destroy()
root.update()
check("đóng xong không còn grab nào sót", root.grab_current() in (None, ""),
      root.grab_current())

print("\n=== 3. Ô tick nạp/lưu đúng ===")
ed = m.ActionEditor(root, app, {"type": "mod_click", "point": [10, 20],
                                "keys": "ctrl+shift", "button": "right"})
root.update()
check("nạp đúng ctrl+shift",
      (ed.k_ctrl.get(), ed.k_shift.get(), ed.k_alt.get()) == (True, True, False),
      (ed.k_ctrl.get(), ed.k_shift.get(), ed.k_alt.get()))
check("nạp đúng nút phải", ed.button_var.get() == "Phải", ed.button_var.get())
ed._save()
root.update()
check("lưu ra ctrl+shift (thứ tự ổn định)", ed.result["keys"] == "ctrl+shift", ed.result)
check("giữ nguyên nút phải", ed.result["button"] == "right", ed.result)

ed = m.ActionEditor(root, app, {"type": "mod_click", "point": [1, 2], "keys": "shift"})
root.update()
ed.k_shift.set(False)
ed.k_alt.set(True)
ed._save()
root.update()
check("đổi tick -> lưu ra alt", ed.result["keys"] == "alt", ed.result)

errors = []
real = m.messagebox.showerror
m.messagebox.showerror = lambda *a, **k: errors.append(a)
ed = m.ActionEditor(root, app, {"type": "mod_click", "point": [1, 2], "keys": "shift"})
root.update()
ed.k_shift.set(False)
ed._save()
m.messagebox.showerror = real
check("không tick phím nào -> chặn lưu + báo lỗi",
      ed.result is None and errors, (ed.result, errors))
ed.destroy()
root.update()

print("\n=== 4. Gõ sai tên phím giờ là chuyện không thể ===")
ed = m.ActionEditor(root, app, {"type": "mod_click", "point": [1, 2], "keys": "shft"})
root.update()
check("phím rác trong file cũ -> không tick gì (thấy ngay, không âm thầm)",
      not any((ed.k_shift.get(), ed.k_ctrl.get(), ed.k_alt.get())),
      (ed.k_shift.get(), ed.k_ctrl.get(), ed.k_alt.get()))
ed.destroy()
root.update()

print("\n=== 5. Đổi qua lại mọi loại rồi lưu vẫn ổn ===")
ed = m.ActionEditor(root, app, None)
root.update()
crash = []
for t in core.ACTION_TYPES * 2:
    try:
        ed.type_var.set(t)
        ed._render()
        root.update()
    except Exception as e:
        crash.append((t, repr(e)))
check("đổi loại 20 lượt không lỗi", not crash, crash)
ed.type_var.set("mod_click")
ed._render()
ed.x_var.set("77")
ed.y_var.set("88")
ed.k_shift.set(True)
ed._save()
root.update()
check("sau khi đổi qua lại vẫn lưu đúng",
      ed.result == {"type": "mod_click", "point": [77, 88], "keys": "shift", "button": "left"},
      ed.result)

root.update()
root.destroy()
print(f"\nKẾT QUẢ: {ok} đúng / {fail} sai")
sys.exit(1 if fail else 0)
