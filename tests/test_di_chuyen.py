"""Hành động Di chuyển (WASD): giữ đúng phím, đúng thời gian, luôn thả ra."""
import sys
import threading
import time
import tkinter as tk

import _boot  # noqa: F401  — đặt sys.path + thư mục làm việc
import core

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


# ---------------------------------------------------------------------------
# Phần kiểm GIAO DIỆN tkinter đã bỏ: giao diện đó không còn (bản web thay thế).
# Luật hợp lệ của hành động giờ nằm ở `core.build_action`, kiểm trong
# tests/test_do_thi_va_api.py §8 — dùng chung cho mọi giao diện.
# ---------------------------------------------------------------------------

print(f"KẾT QUẢ: {ok} đúng / {fail} sai")
sys.exit(1 if fail else 0)