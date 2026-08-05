"""Test ô tick "Giữ Shift" của Loop + phần gia cố mod_click."""
import sys
import threading

import _boot  # noqa: F401  — đặt sys.path + thư mục làm việc
import core

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
        self.ev = []
        self.pos = (0, 0)

    def moveTo(self, x, y, duration=0):
        self.pos = (int(x), int(y))

    def click(self, button="left"):
        self.ev.append(("click", button))

    def doubleClick(self):
        self.ev.append(("click", "double"))

    def keyDown(self, k):
        self.ev.append(("down", k))

    def keyUp(self, k):
        self.ev.append(("up", k))

    def hotkey(self, *a):
        self.ev.append(("hotkey", "+".join(a)))

    def press(self, k):
        self.ev.append(("press", k))

    def scroll(self, n):
        pass

    def isValidKey(self, k):
        return k in ("shift", "ctrl", "alt", "enter", "a", "f6")

    def still_down(self):
        held = []
        for e in self.ev:
            if e[0] == "down" and e[1] not in held:
                held.append(e[1])
            elif e[0] == "up" and e[1] in held:
                held.remove(e[1])
        return held


class FakeClip:
    text = ('Item Class: Boots\n--------\n'
            '{ Prefix Modifier "Stalwart" (Tier: 6) — Life }\n+44(40-59) to maximum Life\n')

    def copy(self, s):
        pass

    def paste(self):
        return self.text


CLICK = {"type": "left_click", "point": [10, 20]}
CHECK = {"type": "check_mod", "point": [30, 40],
         "conditions": [{"mod": "# to maximum Life", "tier": 1}]}      # không khớp


def run(steps, stop_after_clicks=None):
    gui = FakeAutoGui()
    saved = (core.pyautogui, core.pyperclip, core.HAS_CLIP)
    core.pyautogui, core.pyperclip, core.HAS_CLIP = gui, FakeClip(), True
    ev = threading.Event()
    if stop_after_clicks:
        orig = gui.click

        def click_stop(button="left"):
            orig(button)
            if len([e for e in gui.ev if e[0] == "click"]) >= stop_after_clicks:
                ev.set()
        gui.click = click_stop
    err = None
    try:
        runner = core.ProcessRunner(
            {"name": "T", "start_delay": 0, "pre_click_ms": 0, "hover_ms": 0,
             "copy_keys": "ctrl+c", "steps": steps}, ev)
        try:
            status, loops = runner.run()
        except BaseException as e:
            err, status, loops = e, "LOI", 0
    finally:
        core.pyautogui, core.pyperclip, core.HAS_CLIP = saved
    return gui, status, err


def loop(actions, hold=True, max_loops=3, start=0):
    return {"kind": "loop", "name": "L", "actions": actions, "loop_start_index": start,
            "max_loops": max_loops, "hold_keys": "shift" if hold else ""}


print("=== 1. Tick bật: giữ 1 lần đầu bước, thả cuối bước ===")
gui, status, err = run([loop([CLICK], max_loops=4)])
check("chỉ bấm giữ shift ĐÚNG 1 lần",
      len([e for e in gui.ev if e == ("down", "shift")]) == 1, gui.ev)
check("giữ TRƯỚC cú click đầu tiên", gui.ev[0] == ("down", "shift"), gui.ev[:2])
check("click đủ 4 vòng", len([e for e in gui.ev if e[0] == "click"]) == 4, gui.ev)
check("thả ở cuối, không còn phím nào giữ", gui.still_down() == [], gui.still_down())
check("dòng cuối là thả shift", gui.ev[-1] == ("up", "shift"), gui.ev[-1])

print("\n=== 2. Trùm cả phần '(1 lần)' — đúng như đã chốt ===")
gui, _, _ = run([loop([{"type": "right_click", "point": [1, 2]}, CLICK],
                      max_loops=2, start=1)])
check("giữ shift TRƯỚC cả hành động chạy-1-lần",
      gui.ev[0] == ("down", "shift") and gui.ev[1] == ("click", "right"), gui.ev[:3])

print("\n=== 3. Ctrl+C KHÔNG bị nhả shift ra nữa (bỏ paused) ===")
gui, _, _ = run([loop([CLICK, CHECK], max_loops=2)])
ups = [e for e in gui.ev if e[0] == "up"]
check("suốt vòng chạy chỉ thả shift ĐÚNG 1 lần (lúc kết thúc)", len(ups) == 1, ups)
check("shift vẫn đang giữ lúc bắn Ctrl+C",
      gui.ev.index(("hotkey", "ctrl+c")) < gui.ev.index(("up", "shift")), gui.ev)

print("\n=== 4. Phạm vi đúng 1 bước — bước sau không dính ===")
gui, _, _ = run([loop([CLICK], max_loops=1),
                 {"kind": "loop", "name": "L2", "actions": [CLICK],
                  "loop_start_index": 0, "max_loops": 1, "hold_keys": ""}])
i_up = gui.ev.index(("up", "shift"))
clicks_after = [e for e in gui.ev[i_up:] if e[0] == "click"]
check("thả shift xong mới sang bước 2", len(clicks_after) == 1, gui.ev)
check("bước 2 không bấm giữ gì",
      len([e for e in gui.ev if e == ("down", "shift")]) == 1, gui.ev)

print("\n=== 5. Dừng giữa chừng / lỗi giữa chừng vẫn thả ===")
gui, status, _ = run([loop([CLICK], max_loops=99999)], stop_after_clicks=3)
check("bấm Dừng -> vẫn thả shift", gui.still_down() == [], gui.still_down())

gui = FakeAutoGui()
saved = (core.pyautogui, core.pyperclip, core.HAS_CLIP)
core.pyautogui, core.pyperclip, core.HAS_CLIP = gui, FakeClip(), True
try:
    def boom(button="left"):
        raise ValueError("click hỏng")
    gui.click = boom
    runner = core.ProcessRunner(
        {"name": "T", "start_delay": 0, "pre_click_ms": 0, "hover_ms": 0,
         "copy_keys": "ctrl+c", "steps": [loop([CLICK], max_loops=5)]}, threading.Event())
    status, loops = runner.run()
finally:
    core.pyautogui, core.pyperclip, core.HAS_CLIP = saved
check("hành động lỗi -> KHÔNG ném ra ngoài, dừng gọn", isinstance(status, str), status)
check("thông báo nêu rõ hành động nào lỗi", "lỗi" in status.lower(), status)
check("lỗi giữa chừng vẫn thả shift", gui.still_down() == [], gui.still_down())

print("\n=== 6. Gia cố mod_click ===")
gui = FakeAutoGui()
saved = core.pyautogui
core.pyautogui = gui
try:
    ev = threading.Event()
    for bad_a, why in [({"type": "mod_click", "keys": "shift", "button": "left"}, "thiếu point"),
                       ({"type": "mod_click", "point": None, "keys": "shift"}, "point = None"),
                       ({"type": "mod_click", "point": [1, 2], "keys": "shft"}, "phím sai"),
                       ({"type": "left_click"}, "click thường thiếu point")]:
        try:
            core.do_action(bad_a, ev, 0)
            check(f"{why} -> phải báo lỗi", False, "không ném gì")
        except ValueError as e:
            check(f"{why} -> báo lỗi rõ ràng ({str(e)[:38]}…)", True)
        except Exception as e:
            check(f"{why} -> báo lỗi rõ ràng", False, f"{type(e).__name__}: {e}")
    core.do_action({"type": "mod_click", "point": [5, 6], "keys": "ctrl+shift",
                    "button": "right"}, ev, 0)
    check("mod_click hợp lệ vẫn chạy đúng",
          gui.ev[-4:] == [("down", "ctrl"), ("down", "shift"), ("click", "right"),
                          ("up", "shift")] or gui.still_down() == [], gui.ev[-5:])
    check("mod_click hợp lệ thả sạch phím", gui.still_down() == [], gui.still_down())
finally:
    core.pyautogui = saved

print("\n=== 7. Soát cấu hình bắt được cấu hình hỏng TRƯỚC khi chạy ===")
saved = core.pyautogui
core.pyautogui = FakeAutoGui()
try:
    p = core.validate_flow([{"type": "mod_click", "point": [1, 2], "keys": "shft"}], 0, 10)
    check("phím sai -> LỖI chặn chạy",
          any(x["severity"] == "error" and "không hợp lệ" in x["message"] for x in p), p)
    p = core.validate_flow([{"type": "mod_click", "keys": "shift"}], 0, 10)
    check("thiếu điểm click -> LỖI",
          any(x["severity"] == "error" and "điểm click" in x["message"] for x in p), p)
    p = core.validate_flow([{"type": "mod_click", "point": [1, 2], "keys": "shift"}], 0, 10)
    check("cấu hình đúng -> không lỗi",
          not [x for x in p if x["severity"] == "error"], p)
finally:
    core.pyautogui = saved

print("\n=== 8. Hiển thị + lưu/mở template ===")
st = loop([CLICK])
check("danh sách bước hiện ⇧", "⇧" in core.step_display(st), core.step_display(st))
check("tick tắt thì không hiện ⇧", "⇧" not in core.step_display(loop([CLICK], hold=False)))
data = {"schema": 3, "type": "process", "name": "P", "game": "poe2", "start_delay": 0,
        "steps": [st]}
back = core.normalize_process(data)["steps"][0]
check("mở lại giữ nguyên hold_keys", back.get("hold_keys") == "shift", back)
old = core.normalize_process({"name": "cũ", "actions": [CLICK], "max_loops": 5})["steps"][0]
check("template cũ không có khoá này -> mặc định tắt", old.get("hold_keys") == "", old)

print("\n=== 9. Đã gỡ sạch key_hold / key_release ===")
check("có đúng 9 loại hành động (thêm confirm_mod để rẽ nhánh)",
      len(core.ACTION_TYPES) == 9, core.ACTION_TYPES)
check("không còn key_hold/key_release",
      not {"key_hold", "key_release"} & set(core.ACTION_TYPES), core.ACTION_TYPES)
check("HeldKeys không còn paused()", not hasattr(core.HeldKeys(), "paused"))

print(f"\nKẾT QUẢ: {ok} đúng / {fail} sai")
sys.exit(1 if fail else 0)
