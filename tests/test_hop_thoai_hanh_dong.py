"""Hộp thoại tạo/sửa hành động: KHÔNG được có widget nào chiếm grab toàn cục,
và phải luôn bấm được sau khi đóng.

Gốc bệnh cũ: ttk.Combobox ở nhánh mod_click -> MapPopdown -> ttk::globalGrab
-> grab -global, đặt bên trong hộp thoại vốn đã grab_set(). Trả grab hỏng là cả
máy ngừng nhận chuột/phím.
"""
import sys
import time
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
check("mọi loại đều không có TCombobox", not bad, bad)

print("\n=== 1b. Cửa sổ vừa khít nội dung từng loại (không thừa, không cắt chữ) ===")
# BẮT BUỘC deiconify: cửa sổ con của root đang withdraw thì chưa được map,
# winfo_height() luôn trả 1 và bài test sẽ báo sai hết.
root.deiconify()
root.geometry("980x780+40+40")
root.update()
ed = m.ActionEditor(root, app, None)
for _ in range(8):
    root.update()
    time.sleep(0.02)

sizes, lech, tran = {}, [], []
for t in core.ACTION_TYPES:
    ed.type_var.set(t)
    ed._render()
    for _ in range(8):
        root.update()
        time.sleep(0.02)
    w, h, need = ed.winfo_width(), ed.winfo_height(), ed.winfo_reqheight()
    sizes[t] = h
    if abs(h - need) > 2:
        lech.append((t, h, need))
    if w != ed.WIDTH:
        lech.append((t, "rộng", w))
    if ed.winfo_rooty() + h > root.winfo_screenheight():
        tran.append((t, ed.winfo_rooty(), h))
check("mọi loại: cửa sổ cao ĐÚNG bằng nội dung cần", not lech, lech)
check("mọi loại: bề rộng giữ nguyên 520 (không giật ngang)", not lech, lech)
check("không loại nào tràn khỏi đáy màn hình", not tran, tran)
check("loại ít nội dung PHẢI nhỏ hơn hẳn loại nhiều nội dung",
      sizes["delay"] < sizes["check_mod"] < sizes["abyss"], sizes)
check("loại nhỏ nhất không còn bị kéo cao vô lý (< 400px)",
      sizes["delay"] < 400, sizes["delay"])
ed.destroy()
root.withdraw()
root.update()

print("\n=== 1c. Không chớp: dựng xong xuôi rồi mới hiện ===")
# Cửa sổ hiện ra trước khi dựng xong thì người dùng NHÌN THẤY nó tự sửa: loé ở góc
# (0,0) rồi nhảy về giữa, đổi bề rộng, tô lại màu, thanh tiêu đề sáng->tối.
# Bài này bắt mọi thao tác dựng cửa sổ và đòi: KHÔNG cái nào chạy khi đã hiện.
root.deiconify()
root.update()
_goc_geo, _goc_dark, _goc_restyle = tk.Toplevel.geometry, m.dark_titlebar, m.restyle_tree
vi_pham = []


def _ghi(win, ten):
    try:
        if win.winfo_ismapped():
            vi_pham.append((ten, win.geometry()))
    except Exception:
        pass


def _geo(self, *a):
    if a:
        _ghi(self, "geometry()")
    return _goc_geo(self, *a)


def _dark(win, remap=False):
    _ghi(win, "dark_titlebar()")
    return _goc_dark(win, remap)


def _restyle(w):
    if isinstance(w, tk.Toplevel):
        _ghi(w, "restyle_tree()")
    return _goc_restyle(w)


tk.Toplevel.geometry, m.dark_titlebar, m.restyle_tree = _geo, _dark, _restyle
try:
    for ten, tao in (
        ("Hành động (right_click)",
         lambda: m.ActionEditor(root, app, {"type": "right_click", "point": [1, 2]})),
        ("Hành động (abyss)",
         lambda: m.ActionEditor(root, app, {"type": "abyss", "frame": [1, 2, 517, 283],
                                            "conditions": [{"mod": "# to all Attributes"}]})),
        ("Cài đặt", lambda: m.SettingsDialog(root, app)),
    ):
        vi_pham.clear()
        dlg = tao()
        root.update()
        check(f"{ten}: không sửa gì sau khi đã hiện", not vi_pham, vi_pham)
        check(f"{ten}: hiện ra rồi và giữ được grab",
              dlg.winfo_ismapped() and str(dlg.grab_current()) == str(dlg),
              (dlg.winfo_ismapped(), str(dlg.grab_current())))
        dlg.destroy()
        root.update()
finally:
    tk.Toplevel.geometry, m.dark_titlebar, m.restyle_tree = _goc_geo, _goc_dark, _goc_restyle
root.withdraw()
root.update()

print("\n=== 1d. Kích thước 'yêu cầu' trả sai thì cửa sổ vẫn KHÔNG được cắt ===")
# Lỗi thật đã xảy ra: sau khi cho hộp thoại ẩn lúc dựng, winfo_width() trả 1 nên
# code phải hỏi winfo_reqwidth() — mà trong BẢN ĐÓNG GÓI giá trị đó có lúc chưa
# tính xong (đo được 216x239 thay vì 341x395). Ép size sai vào cửa sổ không cho co
# giãn = nội dung bị cắt vĩnh viễn. Chạy từ mã nguồn thì không tái hiện được, nên
# ở đây ÉP winfo_req* trả về số bậy để mô phỏng đúng tình huống đó.
root.deiconify()
root.geometry("980x780+40+40")
root.update()
_rw, _rh = tk.Misc.winfo_reqwidth, tk.Misc.winfo_reqheight
tk.Misc.winfo_reqwidth = lambda self: 120
tk.Misc.winfo_reqheight = lambda self: 100
try:
    dlgs = [("Cài đặt", m.SettingsDialog(root, app)),
            ("Hành động (abyss)",
             m.ActionEditor(root, app, {"type": "abyss", "frame": [1, 2, 517, 283],
                                        "conditions": [{"mod": "# to all Attributes"}]}))]
finally:
    tk.Misc.winfo_reqwidth, tk.Misc.winfo_reqheight = _rw, _rh
for _ in range(10):
    root.update()
    time.sleep(0.02)
for ten, d in dlgs:
    w, h, rw, rh = d.winfo_width(), d.winfo_height(), d.winfo_reqwidth(), d.winfo_reqheight()
    check(f"{ten}: không bị cắt dù kích thước yêu cầu trả sai",
          w >= rw and h >= rh, f"cửa sổ {w}x{h} < nội dung {rw}x{rh}")
    d.destroy()
    root.update()
root.withdraw()
root.update()

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
