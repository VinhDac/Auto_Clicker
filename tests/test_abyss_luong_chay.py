"""Test luồng chạy của abyss_action + hoà vào ProcessRunner.

pyautogui bị thay bằng bản giả ghi lại mọi cú click -> kiểm tra được app bấm
ĐÚNG chỗ, ĐÚNG thứ tự, và không bấm bừa khi đọc lỗi.
abyss_scan cũng bị thay để điều khiển kết quả quét từng lượt.
"""
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
        self.clicks = []
        self.pos = (0, 0)

    def moveTo(self, x, y, duration=0):
        self.pos = (int(x), int(y))

    def click(self, button="left"):
        self.clicks.append(self.pos)

    def hotkey(self, *a):
        pass

    def press(self, k):
        pass

    def scroll(self, n):
        pass

    def keyDown(self, k):
        pass

    def keyUp(self, k):
        pass


FRAME = [100, 200, 517, 283]
R = core.abyss_regions(FRAME)
BAND = R["band_points"]
CONFIRM = R["confirm"]
REFRESH = R["refresh_point"]


def make_action(**kw):
    a = {"type": "abyss", "frame": list(FRAME), "wait_ms": 0, "rerolls": 1,
         "pick": core.ABYSS_PICK_FIRST,
         "conditions": [{"mod": "#% to Cold Resistance", "min_value": 20}]}
    a.update(kw)
    return a


def run(action, scans):
    """Chạy abyss_action với danh sách kết quả quét định sẵn."""
    gui = FakeAutoGui()
    real_gui, real_scan = core.pyautogui, core.abyss_scan
    seq = list(scans)
    calls = []

    def fake_scan(frame, log=None):
        calls.append(frame)
        return seq.pop(0) if seq else ([""] * 3, False, "hết kịch bản")

    core.pyautogui = gui
    core.abyss_scan = fake_scan
    try:
        status, payload = core.abyss_action(action, threading.Event(), 0)
    finally:
        core.pyautogui, core.abyss_scan = real_gui, real_scan
    return status, payload, gui.clicks, len(calls)


HIT = (["14% INCREASED CAST SPEED", "+24% TO COLD RESISTANCE", "X"], True, None)
MISS = (["14% INCREASED CAST SPEED", "+9% TO COLD RESISTANCE", "X"], True, None)
MISS_NOREFRESH = (["14% INCREASED CAST SPEED", "+9% TO COLD RESISTANCE", "X"], False, None)
READFAIL = ([""] * 3, False, "không đọc được chữ nào trong khung")

print("=== 1. Quét phát đầu đã ra mod ===")
st, pl, clicks, n = run(make_action(), [HIT])
check("trả về MATCH", st == core.CHECK_MATCH, st)
check("báo đúng điều kiện", pl and pl.get("mod") == "#% to Cold Resistance", pl)
check("payload có dấu _kind=abyss (để hiện đúng mô tả)", pl.get("_kind") == "abyss")
check("quét đúng 1 lần", n == 1, n)
check("click đúng 3 nhát: REVEAL -> ô 2 -> CONFIRM",
      clicks == [CONFIRM, BAND[1], CONFIRM], clicks)

print("\n=== 2. Trượt lần đầu, có nút refresh -> reroll rồi trúng ===")
st, pl, clicks, n = run(make_action(), [MISS, HIT])
check("trả về MATCH", st == core.CHECK_MATCH, st)
check("quét 2 lần", n == 2, n)
check("click: REVEAL -> refresh -> ô 2 -> CONFIRM",
      clicks == [CONFIRM, REFRESH, BAND[1], CONFIRM], clicks)

print("\n=== 3. Trượt và KHÔNG có nút refresh -> bỏ qua reroll, chọn bừa ===")
st, pl, clicks, n = run(make_action(), [MISS_NOREFRESH])
check("trả về NO_MATCH", st == core.CHECK_NO_MATCH, st)
check("chỉ quét 1 lần (không cố reroll)", n == 1, n)
check("KHÔNG bấm nút refresh", REFRESH not in clicks, clicks)
check("click: REVEAL -> ô 1 -> CONFIRM", clicks == [CONFIRM, BAND[0], CONFIRM], clicks)

print("\n=== 4. Trượt cả sau khi reroll -> chọn bừa rồi CONFIRM ===")
st, pl, clicks, n = run(make_action(), [MISS, MISS])
check("trả về NO_MATCH", st == core.CHECK_NO_MATCH, st)
check("quét 2 lần", n == 2, n)
check("click: REVEAL -> refresh -> ô 1 -> CONFIRM",
      clicks == [CONFIRM, REFRESH, BAND[0], CONFIRM], clicks)

print("\n=== 5. rerolls=0 -> không bao giờ bấm refresh ===")
st, pl, clicks, n = run(make_action(rerolls=0), [MISS])
check("quét đúng 1 lần", n == 1, n)
check("không bấm refresh", REFRESH not in clicks, clicks)

print("\n=== 6. reroll 2 lần ===")
st, pl, clicks, n = run(make_action(rerolls=2), [MISS, MISS, HIT])
check("quét 3 lần", n == 3, n)
check("bấm refresh đúng 2 lần", clicks.count(REFRESH) == 2, clicks)
check("trả về MATCH", st == core.CHECK_MATCH, st)

print("\n=== 7. Đọc lỗi -> KHÔNG được chọn bừa, phải báo lỗi ===")
st, pl, clicks, n = run(make_action(), [READFAIL])
check("trả về READ_FAIL", st == core.CHECK_READ_FAIL, st)
check("chỉ bấm REVEAL rồi dừng, không chốt mod nào", clicks == [CONFIRM], clicks)

print("\n=== 7b. wait_ms = 0 phải là KHÔNG CHỜ, không bị đá về mặc định ===")
import time as _t
_t0 = _t.perf_counter()
run(make_action(wait_ms=0), [HIT])
_d0 = _t.perf_counter() - _t0
check("wait_ms=0 chạy gần như tức thì (0 là giá trị hợp lệ, không phải 'chưa đặt')",
      _d0 < 0.5, f"mất {_d0:.2f}s — số 0 đang bị coi là chưa đặt")
_t0 = _t.perf_counter()
run(make_action(wait_ms=120), [HIT])
_d1 = _t.perf_counter() - _t0
check("wait_ms=120 thì có chờ thật", _d1 > _d0, f"{_d1:.2f}s vs {_d0:.2f}s")

print("\n=== 8. Chọn bừa ngẫu nhiên thì phải nằm trong 3 ô ===")
seen = set()
for _ in range(40):
    st, pl, clicks, n = run(make_action(pick=core.ABYSS_PICK_RANDOM), [MISS_NOREFRESH])
    seen.add(tuple(clicks[1]))
check("mọi lần chọn đều là 1 trong 3 ô", seen <= {tuple(p) for p in BAND}, seen)
check("có ngẫu nhiên thật (không phải luôn 1 ô)", len(seen) > 1, seen)

print("\n=== 9. Thiếu khung / thiếu điều kiện -> báo lỗi, không click gì ===")
st, pl, clicks, n = run(make_action(frame=None), [HIT])
check("thiếu khung -> READ_FAIL", st == core.CHECK_READ_FAIL, st)
check("thiếu khung -> không click gì", clicks == [], clicks)
st, pl, clicks, n = run(make_action(conditions=[]), [HIT])
check("thiếu điều kiện -> READ_FAIL", st == core.CHECK_READ_FAIL, st)
check("thiếu điều kiện -> không click gì", clicks == [], clicks)

print("\n=== 10. Hoà vào ProcessRunner: khớp thì DỪNG cả Loop ===")


def run_process(steps, scans):
    gui = FakeAutoGui()
    real_gui, real_scan = core.pyautogui, core.abyss_scan
    seq = list(scans)

    def fake_scan(frame, log=None):
        return seq.pop(0) if seq else (["", "", ""], False, "hết kịch bản")

    core.pyautogui = gui
    core.abyss_scan = fake_scan
    logs = []
    try:
        runner = core.ProcessRunner({"name": "T", "steps": steps, "start_delay": 0,
                                     "pre_click_ms": 0, "hover_ms": 0, "copy_keys": "ctrl+c"},
                                    threading.Event(),
                                    on_log=lambda m, t=None: logs.append(m))
        status, loops = runner.run()
    finally:
        core.pyautogui, core.abyss_scan = real_gui, real_scan
    return status, loops, logs


step = {"kind": "loop", "name": "Abyss", "loop_start_index": 0, "max_loops": 5,
        "actions": [make_action()]}
status, loops, logs = run_process([step], [MISS, MISS, MISS, MISS, HIT])
check("dừng ngay khi trúng, không chạy hết 5 vòng", loops == 3, f"loops={loops}")
check("báo hoàn thành + nêu mod", "Ra mod" in status, status)
check("mô tả mod theo kiểu Abyss (ngưỡng, không phải Tier)",
      "≥ 20" in status and "Tier" not in status, status)

status, loops, logs = run_process([step], [MISS_NOREFRESH] * 20)
check("hết vòng mà chưa ra mod -> DỪNG cả Process",
      "DỪNG cả Process" in status, status)
check("chạy đủ 5 vòng", loops == 5, f"loops={loops}")

print("\n=== 11. Soát cấu hình (panel Vấn đề) ===")
probs = core.validate_process([{"kind": "loop", "name": "L", "loop_start_index": 0,
                                "max_loops": 10, "actions": [make_action(frame=None)]}])
check("thiếu khung -> có lỗi", any(p["severity"] == "error" and "căn khung" in p["message"]
                                   for p in probs), probs)
probs = core.validate_process([{"kind": "loop", "name": "L", "loop_start_index": 0,
                                "max_loops": 10, "actions": [make_action(conditions=[])]}])
check("thiếu điều kiện -> có lỗi", any(p["severity"] == "error" and "điều kiện" in p["message"]
                                       for p in probs), probs)
probs = core.validate_process([{"kind": "loop", "name": "L", "loop_start_index": 0,
                                "max_loops": 10, "actions": [make_action()]}])
check("cấu hình đủ -> không còn lỗi", not [p for p in probs if p["severity"] == "error"], probs)
check("có Abyss thì KHÔNG còn cảnh báo 'chưa có mục tiêu'",
      not any("chỉ dừng" in p["message"] for p in probs), probs)

probs = core.validate_process([{"kind": "loop", "name": "L", "loop_start_index": 1,
                                "max_loops": 10,
                                "actions": [make_action(), {"type": "left_click", "point": [5, 5]}]}])
check("Abyss nằm ở phần chạy 1 lần -> cảnh báo",
      any(p["severity"] == "warning" and "1 lần" in p["message"] for p in probs), probs)

print(f"\nKẾT QUẢ: {ok} đúng / {fail} sai")
sys.exit(1 if fail else 0)
