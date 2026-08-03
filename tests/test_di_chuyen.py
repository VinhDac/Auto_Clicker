"""Hành động Di chuyển (WASD): giữ đúng phím, đúng thời gian, luôn thả ra."""
import sys
import threading
import time
import tkinter as tk

import _boot  # noqa: F401  — đặt sys.path + thư mục làm việc
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


class FakeAutoGui:
    FailSafeException = RuntimeError

    def __init__(self):
        self.ev = []
        self.pos = (0, 0)

    def moveTo(self, x, y, duration=0):
        self.pos = (int(x), int(y))

    def click(self, button="left"):
        self.ev.append(("click", button))

    def keyDown(self, k):
        self.ev.append(("down", k))

    def keyUp(self, k):
        self.ev.append(("up", k))

    def press(self, k):
        self.ev.append(("press", k))

    def hotkey(self, *a):
        pass

    def isValidKey(self, k):
        return True

    def con_giu(self):
        held = []
        for e in self.ev:
            if e[0] == "down" and e[1] not in held:
                held.append(e[1])
            elif e[0] == "up" and e[1] in held:
                held.remove(e[1])
        return held


def chay(action, stop=None):
    gui = FakeAutoGui()
    saved = core.pyautogui
    core.pyautogui = gui
    err = None
    t0 = time.perf_counter()
    try:
        core.do_action(action, stop or threading.Event(), 0)
    except Exception as e:
        err = e
    finally:
        core.pyautogui = saved
    return gui, err, (time.perf_counter() - t0) * 1000


print("=== 1. Tên hướng đọc ra người hiểu được ===")
check("1 phím", core.wasd_display("w") == "W (lên)", core.wasd_display("w"))
check("2 phím chéo", core.wasd_display("w+a") == "W+A (chéo lên-trái)",
      core.wasd_display("w+a"))
check("thứ tự ghi luôn dọc trước, bất kể gõ vào thế nào",
      core.wasd_display("a+w") == "W+A (chéo lên-trái)", core.wasd_display("a+w"))
check("chưa chọn gì", "chưa chọn" in core.wasd_display(""), core.wasd_display(""))
for k, ten in (("s", "xuống"), ("a", "trái"), ("d", "phải")):
    check(f"hướng {k.upper()} = {ten}", ten in core.wasd_display(k), core.wasd_display(k))
for combo, ten in (("s+d", "chéo xuống-phải"), ("w+d", "chéo lên-phải"),
                   ("s+a", "chéo xuống-trái")):
    check(f"{combo} = {ten}", ten in core.wasd_display(combo), core.wasd_display(combo))

print("\n=== 2. Bắt bộ phím sai (file sửa tay) ===")
check("rỗng -> báo lỗi", core.wasd_problem("") is not None)
check("W+S ngược chiều -> báo lỗi", "ngược chiều" in (core.wasd_problem("w+s") or ""),
      core.wasd_problem("w+s"))
check("A+D ngược chiều -> báo lỗi", "ngược chiều" in (core.wasd_problem("a+d") or ""),
      core.wasd_problem("a+d"))
check("3 phím -> báo lỗi", "2 hướng" in (core.wasd_problem("w+a+d") or ""),
      core.wasd_problem("w+a+d"))
check("phím lạ -> báo lỗi", "W/A/S/D" in (core.wasd_problem("w+q") or ""),
      core.wasd_problem("w+q"))
for good in ("w", "a", "s", "d", "w+a", "w+d", "s+a", "s+d"):
    check(f"{good} hợp lệ", core.wasd_problem(good) is None, core.wasd_problem(good))

print("\n=== 3. Chạy thật: giữ đúng phím, đúng thời gian, thả sạch ===")
gui, err, ms = chay({"type": "move_wasd", "keys": "w+a", "ms": 150})
check("không lỗi", err is None, err)
check("bấm giữ đúng 2 phím, đúng thứ tự",
      [e for e in gui.ev if e[0] == "down"] == [("down", "w"), ("down", "a")], gui.ev)
check("thả theo thứ tự NGƯỢC lại",
      [e for e in gui.ev if e[0] == "up"] == [("up", "a"), ("up", "w")], gui.ev)
check("kết thúc không còn phím nào bị giữ", gui.con_giu() == [], gui.con_giu())
check("giữ đúng khoảng thời gian đặt (~150ms)", 120 <= ms <= 400, f"{ms:.0f}ms")

gui, err, ms = chay({"type": "move_wasd", "keys": "d", "ms": 50})
check("1 hướng cũng chạy đúng", [e for e in gui.ev if e[0] == "down"] == [("down", "d")],
      gui.ev)
check("thả sạch", gui.con_giu() == [], gui.con_giu())

print("\n=== 4. Bấm Dừng giữa chừng -> nhả NGAY, không chờ hết giờ ===")
ev = threading.Event()
ev.set()
gui, err, ms = chay({"type": "move_wasd", "keys": "w", "ms": 5000}, stop=ev)
check("không chờ hết 5 giây", ms < 500, f"{ms:.0f}ms")
check("vẫn thả phím ra", gui.con_giu() == [], gui.con_giu())

print("\n=== 5. Bộ phím sai lúc chạy -> báo lỗi, KHÔNG giữ phím nào ===")
for xau in ("w+s", "a+d", "w+a+d", "", "w+q"):
    gui, err, ms = chay({"type": "move_wasd", "keys": xau, "ms": 100})
    check(f"'{xau or '(rỗng)'}' -> ném lỗi rõ ràng", isinstance(err, ValueError), err)
    check(f"'{xau or '(rỗng)'}' -> không giữ phím nào", gui.con_giu() == [], gui.con_giu())

print("\n=== 6. Soát cấu hình ===")
p = core.validate_flow([{"type": "move_wasd", "keys": "w+a", "ms": 1000}], 0, 10)
check("cấu hình đúng -> không lỗi", not [x for x in p if x["severity"] == "error"], p)
p = core.validate_flow([{"type": "move_wasd", "keys": "w+s", "ms": 1000}], 0, 10)
check("W+S -> LỖI", any(x["severity"] == "error" and "ngược chiều" in x["message"]
                        for x in p), p)
p = core.validate_flow([{"type": "move_wasd", "keys": "", "ms": 1000}], 0, 10)
check("chưa chọn hướng -> LỖI", any(x["severity"] == "error" for x in p), p)
p = core.validate_flow([{"type": "move_wasd", "keys": "w", "ms": 0}], 0, 10)
check("0 ms -> LỖI", any(x["severity"] == "error" and "lớn hơn 0" in x["message"]
                         for x in p), p)

print("\n=== 7. Giao diện: tick hướng này thì hướng ngược tự bỏ ===")
root = tk.Tk()
root.withdraw()
m.apply_theme(root)
app = m.AutoClickerApp(root)
root.update()

ed = m.ActionEditor(root, app, None)
ed.type_var.set("move_wasd")
ed._render()
root.update()
check("mặc định chưa tick gì", ed._wasd_keys() == [], ed._wasd_keys())

ed.wasd_vars["w"].set(True)
ed._wasd_toggled("w")
check("tick W", ed._wasd_keys() == ["w"], ed._wasd_keys())
ed.wasd_vars["s"].set(True)
ed._wasd_toggled("s")
check("tick S -> W TỰ BỎ (không thể có W+S)", ed._wasd_keys() == ["s"], ed._wasd_keys())
ed.wasd_vars["a"].set(True)
ed._wasd_toggled("a")
check("thêm A -> thành S+A", ed._wasd_keys() == ["s", "a"], ed._wasd_keys())
ed.wasd_vars["d"].set(True)
ed._wasd_toggled("d")
check("tick D -> A TỰ BỎ (không thể có A+D)", ed._wasd_keys() == ["s", "d"],
      ed._wasd_keys())
check("không đường nào tạo ra quá 2 phím", len(ed._wasd_keys()) <= 2, ed._wasd_keys())
check("nhãn tóm tắt hiện đúng hướng + số giây",
      "chéo xuống-phải" in ed.move_lbl["text"] and "giây" in ed.move_lbl["text"],
      ed.move_lbl["text"])

ed.move_ms_var.set("4000")
ed._save()
root.update()
check("lưu ra đúng", ed.result == {"type": "move_wasd", "keys": "s+d", "ms": 4000},
      ed.result)

errs = []
real = m.messagebox.showerror
m.messagebox.showerror = lambda *a, **k: errs.append(a)
ed = m.ActionEditor(root, app, None)
ed.type_var.set("move_wasd")
ed._render()
ed._save()
check("chưa tick hướng -> chặn lưu", ed.result is None and errs, (ed.result, errs))
errs.clear()
ed = m.ActionEditor(root, app, {"type": "move_wasd", "keys": "w", "ms": 100})
root.update()
ed.move_ms_var.set("0")
ed._save()
m.messagebox.showerror = real
check("0 ms -> chặn lưu", ed.result is None and errs, (ed.result, errs))

ed = m.ActionEditor(root, app, {"type": "move_wasd", "keys": "w+d", "ms": 2500})
root.update()
check("mở lại -> nạp đúng hướng", ed._wasd_keys() == ["w", "d"], ed._wasd_keys())
check("mở lại -> nạp đúng ms", ed.move_ms_var.get() == "2500", ed.move_ms_var.get())
ed.destroy()
root.update()

print("\n=== 8. Hoà vào hệ thống như mọi hành động khác ===")
check("là loại hành động thứ 8", len(core.ACTION_TYPES) == 8, core.ACTION_TYPES)
check("có trong danh sách loại", "move_wasd" in core.ACTION_TYPES)
check("có nhãn hiển thị", core.ACTION_LABELS.get("move_wasd"), core.ACTION_LABELS)
A = {"type": "move_wasd", "keys": "w", "ms": 1000}
check("mô tả trong danh sách rõ nghĩa",
      "W (lên)" in core.action_summary(A) and "1000ms" in core.action_summary(A),
      core.action_summary(A))
check("copy/dán bước nhận được hành động này",
      app._sanitize_step({"kind": "group", "name": "N", "actions": [A]})["actions"] == [A],
      app._sanitize_step({"kind": "group", "name": "N", "actions": [A]}))

gui = FakeAutoGui()
saved = core.pyautogui
core.pyautogui = gui
try:
    step = {"kind": "group", "name": "Đi", "actions": [
        {"type": "move_wasd", "keys": "w", "ms": 20},
        {"type": "move_wasd", "keys": "a+s", "ms": 20}]}
    r = core.ProcessRunner({"name": "T", "start_delay": 0, "pre_click_ms": 0, "hover_ms": 0,
                            "copy_keys": "ctrl+c", "steps": [step]}, threading.Event())
    status, loops = r.run()
finally:
    core.pyautogui = saved
check("chạy trong Nhóm: đủ 2 hành động", len([e for e in gui.ev if e[0] == "down"]) == 3,
      gui.ev)
check("chạy xong không kẹt phím nào", gui.con_giu() == [], gui.con_giu())

root.update()
root.destroy()
print(f"\n{'=' * 58}")
print(f"KẾT QUẢ: {ok} đúng / {fail} sai")
for f in fails:
    print("   sai:", f)
sys.exit(1 if fail else 0)
