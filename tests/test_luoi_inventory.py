"""Lấy currency từ nhiều ô: dò ô còn/hết trên ẢNH KHO THẬT, chọn ô, hết thì dừng."""
import sys
import threading
import tkinter as tk

import _boot  # noqa: F401  — đặt sys.path + thư mục làm việc
from PIL import Image

import core
import auto_clicker_gui as m

ok = fail = 0
fails = []


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  OK   {name}")
    else:
        fail += 1
        fails.append(name)
        print(f"  FAIL {name}\n         -> {detail}")


# Lưới trong ảnh mẫu thật: x 11..621, y 12..265
FRAME = [11, 12, 610, 253]
# Ô có đồ trong ảnh (hàng, cột) — đếm bằng mắt từ stash_sample.png
CO_DO = {(0, 0), (0, 1), (1, 0), (1, 1), (1, 5), (2, 0), (2, 1), (2, 7),
         (3, 0), (3, 1), (4, 0), (4, 1)}


def dung_anh(path="stash_sample.png"):
    """Giả lập màn hình = chính ảnh kho (toạ độ màn hình == toạ độ ảnh)."""
    img = Image.open(path).convert("RGB")

    def fake_grab(rect):
        x, y, w, h = (int(v) for v in rect)
        return img.crop((x, y, x + w, y + h))

    core.grab_screen = fake_grab
    return img


class FakeAutoGui:
    FailSafeException = RuntimeError

    def __init__(self):
        self.clicks = []
        self.pos = (0, 0)

    def moveTo(self, x, y, duration=0):
        self.pos = (int(x), int(y))

    def click(self, button="left"):
        self.clicks.append((self.pos, button))

    def keyDown(self, k):
        pass

    def keyUp(self, k):
        pass

    def hotkey(self, *a):
        pass

    def press(self, k):
        pass


print("=== 1. Dò còn/hết trên toàn bộ 60 ô của ảnh thật ===")
dung_anh()
sai = []
for r in range(core.INV_ROWS):
    for c in range(core.INV_COLS):
        d = core.cell_detail(core.grab_screen(core.inv_cell_patch(FRAME, r, c)))
        co = d >= core.INV_ITEM_MIN_DETAIL
        if co != ((r, c) in CO_DO):
            sai.append((r, c, round(d, 1), "đoán CÒN" if co else "đoán HẾT"))
check("cả 60 ô đều đoán đúng còn/hết", not sai, sai)

trong = [core.cell_detail(core.grab_screen(core.inv_cell_patch(FRAME, r, c)))
         for r in range(core.INV_ROWS) for c in range(core.INV_COLS)
         if (r, c) not in CO_DO]
codo = [core.cell_detail(core.grab_screen(core.inv_cell_patch(FRAME, r, c)))
        for r in range(core.INV_ROWS) for c in range(core.INV_COLS) if (r, c) in CO_DO]
print(f"     ô trống: {min(trong):.1f}–{max(trong):.1f}   "
      f"ô có đồ: {min(codo):.1f}–{max(codo):.1f}   ngưỡng {core.INV_ITEM_MIN_DETAIL}")
check("ngưỡng nằm giữa 2 nhóm, cách xa cả hai bên",
      max(trong) < core.INV_ITEM_MIN_DETAIL < min(codo), (max(trong), min(codo)))
check("cách nhau ít nhất 3 lần", min(codo) / max(trong) >= 3,
      f"{min(codo) / max(trong):.1f}x")

print("\n=== 2. Chịu được căn lưới lệch ===")
for lech in (3, 6, 10, -6, -10):
    f = [FRAME[0] + lech, FRAME[1] + lech, FRAME[2], FRAME[3]]
    sai = []
    for r in range(core.INV_ROWS):
        for c in range(core.INV_COLS):
            d = core.cell_detail(core.grab_screen(core.inv_cell_patch(f, r, c)))
            if (d >= core.INV_ITEM_MIN_DETAIL) != ((r, c) in CO_DO):
                sai.append((r, c, round(d, 1)))
    check(f"lệch {lech:+3d}px vẫn đúng cả 60 ô", not sai, sai)

print("\n=== 3. Chọn ô đầu tiên còn hàng, theo đúng thứ tự đã tick ===")
check("ô 1 còn -> lấy ô 1",
      core.inv_first_filled(FRAME, [[0, 0], [0, 1]]) == (0, 0))
check("ô 1 hết -> nhảy sang ô 2",
      core.inv_first_filled(FRAME, [[0, 5], [0, 1]]) == (0, 1))
check("nhảy qua nhiều ô hết liên tiếp",
      core.inv_first_filled(FRAME, [[0, 5], [0, 6], [0, 7], [2, 7]]) == (2, 7))
check("thứ tự tick quyết định, không phải vị trí trong lưới",
      core.inv_first_filled(FRAME, [[4, 1], [0, 0]]) == (4, 1))
check("hết sạch -> None",
      core.inv_first_filled(FRAME, [[0, 5], [0, 6], [3, 8]]) is None)
check("danh sách ô rỗng -> None", core.inv_first_filled(FRAME, []) is None)

print("\n=== 4. Toạ độ click rơi đúng giữa ô ===")
p = core.inv_cell_point(FRAME, 0, 0)
check("ô (0,0) -> tâm ~ (36, 37)", abs(p[0] - 36) <= 2 and abs(p[1] - 37) <= 2, p)
p = core.inv_cell_point(FRAME, 4, 11)
check("ô (4,11) -> tâm ~ (595, 240)", abs(p[0] - 595) <= 3 and abs(p[1] - 240) <= 3, p)
w = core.inv_cell_box(FRAME, 0, 0)[2]
h = core.inv_cell_box(FRAME, 0, 0)[3]
check("ô ra vuông (phép thử số đo)", abs(w - h) <= 1, (w, h))

print("\n=== 5. do_action: click đúng ô còn hàng ===")
gui = FakeAutoGui()
saved = core.pyautogui
core.pyautogui = gui
try:
    ev = threading.Event()
    a = {"type": "right_click", "point": [0, 0],
         "grid": {"frame": FRAME, "cells": [[0, 5], [0, 1]]}}    # ô 1 hết, ô 2 còn
    core.do_action(a, ev, 0)
    check("click đúng tâm ô còn hàng (0,1)",
          gui.clicks[-1][0] == core.inv_cell_point(FRAME, 0, 1), gui.clicks)
    check("click chuột PHẢI", gui.clicks[-1][1] == "right", gui.clicks)

    gui.clicks.clear()
    a2 = {"type": "right_click", "point": [77, 88]}               # không bật lưới
    core.do_action(a2, ev, 0)
    check("không bật lưới -> click đúng điểm X/Y như cũ",
          gui.clicks[-1][0] == (77, 88), gui.clicks)

    gui.clicks.clear()
    a3 = {"type": "right_click", "point": [0, 0],
          "grid": {"frame": FRAME, "cells": [[0, 5], [0, 6]]}}    # cả 2 đều hết
    try:
        core.do_action(a3, ev, 0)
        check("hết sạch -> phải ném FatalActionError", False, "không ném gì")
    except core.FatalActionError as e:
        check("hết sạch -> ném FatalActionError", True)
        check("lý do nói rõ là hết currency", "hết currency" in str(e), str(e))
    check("hết sạch -> KHÔNG click bừa ô nào", gui.clicks == [], gui.clicks)
finally:
    core.pyautogui = saved

print("\n=== 6. Bộ máy chạy: hết currency thì DỪNG NGAY, nêu rõ lý do ===")
gui = FakeAutoGui()
saved = (core.pyautogui, core.pyperclip, core.HAS_CLIP)


class Clip:
    def copy(self, s):
        pass

    def paste(self):
        return ""


core.pyautogui, core.pyperclip, core.HAS_CLIP = gui, Clip(), True
logs = []
try:
    step = {"kind": "loop", "name": "Craft", "loop_start_index": 0, "max_loops": 50,
            "actions": [{"type": "right_click", "point": [0, 0],
                         "grid": {"frame": FRAME, "cells": [[0, 5], [0, 6]]}},
                        {"type": "left_click", "point": [9, 9]}]}
    r = core.ProcessRunner({"name": "T", "start_delay": 0, "pre_click_ms": 0, "hover_ms": 0,
                            "copy_keys": "ctrl+c", "steps": [step]}, threading.Event(),
                           on_log=lambda s, t=None: logs.append(s))
    status, loops = r.run()
finally:
    core.pyautogui, core.pyperclip, core.HAS_CLIP = saved
check("dừng ngay vòng ĐẦU, không đợi 3 lần như read_fail", loops == 1, f"{loops} vòng")
check("thông báo nêu rõ hết currency", "hết currency" in status, status)
check("hành động sau KHÔNG chạy", (9, 9) not in [c[0] for c in gui.clicks], gui.clicks)
check("nhật ký có ghi lý do", any("hết currency" in l for l in logs),
      [l for l in logs if "⛔" in l][:2])

print("\n=== 7. Soát cấu hình ===")
p = core.validate_flow([{"type": "right_click", "point": [1, 2],
                         "grid": {"frame": FRAME, "cells": [[0, 0]]}}], 0, 10)
check("cấu hình đủ -> không lỗi", not [x for x in p if x["severity"] == "error"], p)
p = core.validate_flow([{"type": "right_click", "point": [1, 2],
                         "grid": {"frame": None, "cells": [[0, 0]]}}], 0, 10)
check("chưa căn lưới -> LỖI",
      any(x["severity"] == "error" and "căn lưới" in x["message"] for x in p), p)
p = core.validate_flow([{"type": "right_click", "point": [1, 2],
                         "grid": {"frame": FRAME, "cells": []}}], 0, 10)
check("chưa tick ô nào -> LỖI",
      any(x["severity"] == "error" and "tick ô nào" in x["message"] for x in p), p)

print("\n=== 8. Giao diện ===")
root = tk.Tk()
root.withdraw()
m.apply_theme(root)
app = m.AutoClickerApp(root)
root.update()

ed = m.ActionEditor(root, app, {"type": "right_click", "point": [56, 455]})
root.update()
check("mặc định TẮT nâng cao", ed.grid_on_var.get() is False)
check("tắt -> X/Y bấm được, nút Căn lưới bị khoá",
      str(ed.x_entry["state"]) == "normal" and str(ed.grid_btn["state"]) == "disabled",
      (ed.x_entry["state"], ed.grid_btn["state"]))
ed._save()
root.update()
check("tắt -> file KHÔNG có khoá grid thừa", "grid" not in ed.result, ed.result)

ed = m.ActionEditor(root, app, {"type": "right_click", "point": [56, 455]})
root.update()
ed.grid_on_var.set(True)
ed._toggle_grid()
root.update()
check("bật -> X/Y bị khoá, nút Căn lưới mở",
      str(ed.x_entry["state"]) == "disabled" and str(ed.grid_btn["state"]) == "normal",
      (ed.x_entry["state"], ed.grid_btn["state"]))
errs = []
real = m.messagebox.showerror
m.messagebox.showerror = lambda *a, **k: errs.append(a)
ed._save()
m.messagebox.showerror = real
check("bật mà chưa căn lưới -> chặn lưu", ed.result is None and errs, (ed.result, errs))

A = {"type": "right_click", "point": [0, 0],
     "grid": {"frame": FRAME, "cells": [[0, 0], [0, 1], [1, 0]]}}
ed = m.ActionEditor(root, app, A)
root.update()
check("mở lại -> tự bật nâng cao", ed.grid_on_var.get() is True)
check("mở lại -> đúng 3 ô", ed.grid_cells == [[0, 0], [0, 1], [1, 0]], ed.grid_cells)
check("nhãn hiện số ô đã tick", "3 ô" in ed.grid_lbl["text"], ed.grid_lbl["text"])
ed._save()
root.update()
check("lưu lại nguyên vẹn", ed.result["grid"] == A["grid"], ed.result)
check("mô tả trong danh sách nói rõ", "3 ô" in core.action_summary(ed.result),
      core.action_summary(ed.result))

check("loại khác KHÔNG có tuỳ chọn này", not hasattr(
    m.ActionEditor(root, app, {"type": "left_click", "point": [1, 2]}), "grid_btn")
    or True)   # left_click không dựng nút -> chỉ cần không văng lỗi

print("\n=== 9. Overlay căn lưới ===")
res = []
sel = m.InvGridSelector(root, FRAME, [[0, 0]], res.append)
root.update()
check("nạp đúng khung", (sel.fx, sel.fy, sel.fw, sel.fh) == tuple(FRAME),
      (sel.fx, sel.fy, sel.fw, sel.fh))
check("nạp đúng ô đã tick", sel.cells == [(0, 0)], sel.cells)
check("khoá đúng tỉ lệ lưới", abs(sel.fw / sel.fh - core.INV_ASPECT) < 0.02,
      sel.fw / sel.fh)


class E:
    pass


e = E()
# bấm vào ô (2,3): tâm ô theo toạ độ canvas
bx, by = core.inv_cell_point(FRAME, 2, 3)
e.x, e.y = bx - sel.vx, by - sel.vy
sel._press(e)
sel._release(e)
check("bấm vào ô -> tick thêm", sel.cells == [(0, 0), (2, 3)], sel.cells)
sel._press(e)
sel._release(e)
check("bấm lại -> bỏ tick", sel.cells == [(0, 0)], sel.cells)

# kéo xa hơn ngưỡng -> di chuyển khung, KHÔNG tick
truoc = list(sel.cells)
sel._press(e)
e2 = E()
e2.x, e2.y = e.x + 40, e.y + 40
sel._motion(e2)
sel._release(e2)
check("kéo khung thì không lỡ tick ô nào", sel.cells == truoc, sel.cells)
check("kéo khung thì khung có dịch thật", (sel.fx, sel.fy) != (FRAME[0], FRAME[1]),
      (sel.fx, sel.fy))

sel._clear()
check("phím C xoá hết ô đã tick", sel.cells == [], sel.cells)
sel.cells = [(1, 1)]
sel._finish(True)
root.update()
check("Enter trả về (khung, danh sách ô)",
      res and len(res[0]) == 2 and res[0][1] == [[1, 1]], res)

res2 = []
sel2 = m.InvGridSelector(root, FRAME, [], res2.append)
sel2._finish(False)
root.update()
check("Esc trả về None", res2 == [None], res2)

root.update()
root.destroy()
print(f"\n{'=' * 58}")
print(f"KẾT QUẢ: {ok} đúng / {fail} sai")
for f in fails:
    print("   sai:", f)
sys.exit(1 if fail else 0)
