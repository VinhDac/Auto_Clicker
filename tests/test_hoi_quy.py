"""Soát lại các tính năng CŨ sau khi thêm Abyss — phải không vỡ gì."""
import sys
import threading
import tkinter as tk

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


class FakeAutoGui:
    FailSafeException = RuntimeError

    def __init__(self):
        self.clicks = []
        self.pos = (0, 0)

    def moveTo(self, x, y, duration=0):
        self.pos = (int(x), int(y))

    def click(self, button="left"):
        self.clicks.append((self.pos, button))

    def doubleClick(self):
        self.clicks.append((self.pos, "double"))

    def hotkey(self, *a):
        pass

    def press(self, k):
        self.clicks.append(("key", k))

    def scroll(self, n):
        self.clicks.append(("scroll", n))

    def keyDown(self, k):
        self.clicks.append(("down", k))

    def keyUp(self, k):
        self.clicks.append(("up", k))


class FakeClip:
    def __init__(self, text):
        self.text = text

    def copy(self, s):
        pass

    def paste(self):
        return self.text


ITEM = """Item Class: Boots
Rarity: Rare
--------
{ Prefix Modifier "Stalwart" (Tier: 6) — Life }
+44(40-59) to maximum Life
--------
{ Suffix Modifier "of the Drake" (Tier: 6) — Fire, Resistance }
+31(30-35)% to Fire Resistance
"""

print("=== 1. check_mod vẫn chạy đúng (không bị Abyss làm hỏng) ===")
gui, clip = FakeAutoGui(), FakeClip(ITEM)
real = (core.pyautogui, core.pyperclip, core.HAS_CLIP)
core.pyautogui, core.pyperclip, core.HAS_CLIP = gui, clip, True
try:
    a = {"type": "check_mod", "point": [10, 20],
         "conditions": [{"mod": "# to maximum Life", "tier": 6}]}
    st, pl = core.check_mod_action(a, threading.Event(), 0, ["ctrl", "c"])
    check("khớp mod + đúng tier", st == core.CHECK_MATCH, st)
    check("mô tả theo kiểu Tier (không phải ngưỡng)",
          "Tier 6" in core.goal_display(pl), core.goal_display(pl))

    a2 = {"type": "check_mod", "point": [10, 20],
          "conditions": [{"mod": "# to maximum Life", "tier": 1}]}
    st2, _ = core.check_mod_action(a2, threading.Event(), 0, ["ctrl", "c"])
    check("sai tier -> không khớp", st2 == core.CHECK_NO_MATCH, st2)

    core.pyperclip = FakeClip("")
    st3, why = core.check_mod_action(a, threading.Event(), 0, ["ctrl", "c"])
    check("clipboard rỗng -> READ_FAIL", st3 == core.CHECK_READ_FAIL, st3)
finally:
    core.pyautogui, core.pyperclip, core.HAS_CLIP = real

print("\n=== 2. Các loại hành động khác vẫn thực thi đúng ===")
gui = FakeAutoGui()
real_gui = core.pyautogui
core.pyautogui = gui
try:
    ev = threading.Event()
    core.do_action({"type": "left_click", "point": [5, 6]}, ev)
    core.do_action({"type": "right_click", "point": [7, 8]}, ev)
    core.do_action({"type": "key_press", "key": "enter"}, ev)
    core.do_action({"type": "delay", "min_ms": 0, "max_ms": 0}, ev)
    core.do_action({"type": "mod_click", "point": [1, 2], "keys": "ctrl+shift",
                    "button": "left"}, ev)
    check("trái/phải click đúng",
          gui.clicks[0] == ((5, 6), "left") and gui.clicks[1] == ((7, 8), "right"),
          gui.clicks[:2])
    check("nhấn phím đúng", ("key", "enter") in gui.clicks, gui.clicks)
    check("mod_click giữ rồi THẢ hết phím (đúng thứ tự ngược)",
          gui.clicks[-3:] == [((1, 2), "left"), ("up", "shift"), ("up", "ctrl")],
          gui.clicks[-4:])
finally:
    core.pyautogui = real_gui

print("\n=== 3. Soát cấu hình cũ vẫn nguyên hành vi ===")
p = core.validate_flow([], 0, 10)
check("danh sách rỗng -> lỗi", any(x["severity"] == "error" for x in p), p)
p = core.validate_flow([{"type": "left_click", "point": [1, 1]}], 0, 10)
check("không có mục tiêu -> chỉ CẢNH BÁO, không chặn",
      [x for x in p if x["severity"] == "warning"] and
      not [x for x in p if x["severity"] == "error"], p)
p = core.validate_flow([{"type": "check_mod", "point": None, "conditions": []}], 0, 10)
check("check_mod thiếu điểm + thiếu điều kiện -> 2 lỗi",
      len([x for x in p if x["severity"] == "error"]) >= 2, p)
p = core.validate_flow([{"type": "left_click", "point": [1, 1]}], 0, 0)
check("max_loops = 0 -> lỗi", any("lớn hơn 0" in x["message"] for x in p), p)

print("\n=== 4. Định dạng template cũ vẫn mở được ===")
old_flat = {"name": "cũ", "actions": [{"type": "left_click", "point": [3, 4]}],
            "max_loops": 50, "hover_point": [7, 8],
            "conditions": [{"mod": "# to maximum Life", "tier": 3}]}
steps = core.normalize_process(old_flat)["steps"]
check("đọc được file phẳng đời cũ", len(steps) == 1 and steps[0]["kind"] == "loop", steps)
acts = steps[0]["actions"]
check("tự chuyển conditions cũ thành hành động check_mod",
      any(x["type"] == "check_mod" for x in acts), acts)

loops_fmt = {"name": "gd1", "action_loops": [
    {"name": "L1", "actions": [{"type": "left_click", "point": [1, 1]}],
     "loop_start_index": 0, "max_loops": 10},
    {"name": "L2", "actions": [{"type": "left_click", "point": [2, 2]}],
     "loop_start_index": 0, "max_loops": 20}]}
steps2 = core.normalize_process(loops_fmt)["steps"]
check("đọc được định dạng action_loops, giữ đủ 2 loop", len(steps2) == 2, steps2)

print("\n=== 5. Mọi loại hành động đều mở được ActionEditor ===")
root = tk.Tk()
root.withdraw()
m.apply_theme(root)
app = m.AutoClickerApp(root)
root.update()
samples = {
    "left_click": {"type": "left_click", "point": [1, 2]},
    "right_click": {"type": "right_click", "point": [1, 2]},
    "mod_click": {"type": "mod_click", "point": [1, 2], "keys": "ctrl", "button": "left"},
    "key_press": {"type": "key_press", "key": "enter"},
    "delay": {"type": "delay", "min_ms": 100, "max_ms": 200},
    "check_mod": {"type": "check_mod", "point": [1, 2],
                  "conditions": [{"mod": "# to maximum Life", "tier": 1}]},
    "abyss": {"type": "abyss", "frame": [1, 2, 517, 283],
              "conditions": [{"mod": "# to all Attributes"}]},
}
bad = []
for t, act in samples.items():
    try:
        ed = m.ActionEditor(root, app, act)
        root.update()
        ed.destroy()
        root.update()
    except Exception as e:
        bad.append((t, repr(e)))
check("cả 8 loại mở được không lỗi", not bad, bad)

print("\n=== 6. Đổi loại giữa Abyss và check_mod ngay trong hộp thoại ===")
try:
    ed = m.ActionEditor(root, app, samples["check_mod"])
    root.update()
    ed.type_var.set("abyss")
    ed._render()
    root.update()
    ed.type_var.set("check_mod")
    ed._render()
    root.update()
    ed.destroy()
    root.update()
    check("đổi qua lại không lỗi", True)
except Exception as e:
    check("đổi qua lại không lỗi", False, repr(e))


print("\n=== 7. Đã gỡ 3 loại không dùng: move / double_click / scroll ===")
go_bo = {"move", "double_click", "scroll"}
check("không còn trong danh sách loại", not go_bo & set(core.ACTION_TYPES),
      core.ACTION_TYPES)
check("còn đúng 8 loại", len(core.ACTION_TYPES) == 8, core.ACTION_TYPES)
check("POINT_TYPES chỉ còn trái/phải click",
      set(core.POINT_TYPES) == {"left_click", "right_click"}, core.POINT_TYPES)
for t in go_bo:
    p = core.validate_flow([{"type": t, "point": [1, 2]}], 0, 10)
    check(f"template cũ còn \"{t}\" -> BÁO LỖI chứ không chạy mù",
          any(x["severity"] == "error" and "không còn được hỗ trợ" in x["message"]
              for x in p), p)

root.update()
root.destroy()
print(f"\nKẾT QUẢ: {ok} đúng / {fail} sai")
sys.exit(1 if fail else 0)
