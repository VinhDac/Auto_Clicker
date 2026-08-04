"""Danh sách LOẠI TRỪ của Abyss: không bao giờ chốt mod bị cấm, kể cả lúc chọn bừa."""
import sys
import threading
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
        self.clicks = []
        self.pos = (0, 0)

    def moveTo(self, x, y, duration=0):
        self.pos = (int(x), int(y))

    def click(self, button="left"):
        self.clicks.append(self.pos)

    def keyDown(self, k):
        pass

    def keyUp(self, k):
        pass

    def hotkey(self, *a):
        pass

    def press(self, k):
        pass


FRAME = [100, 200, 517, 283]
R = core.abyss_regions(FRAME)
BAND, CONFIRM, REFRESH = R["band_points"], R["confirm"], R["refresh_point"]

CAST = "14% INCREASED CAST SPEED"
COLD = "+24% TO COLD RESISTANCE"
HERALD = "19% INCREASED RESERVATION EFFICIENCY OF HERALD SKILLS"
M_CAST = "#% increased Cast Speed"
M_COLD = "#% to Cold Resistance"
M_HERALD = "#% increased Reservation Efficiency of Herald Skills"
M_LIFE = "# to maximum Life"


def act(**kw):
    a = {"type": "abyss", "frame": list(FRAME), "wait_ms": 0, "rerolls": 1,
         "conditions": [{"mod": M_LIFE}]}          # không bao giờ khớp -> luôn rơi vào chọn bừa
    a.update(kw)
    return a


def run(action, scans):
    gui = FakeAutoGui()
    real_gui, real_scan = core.pyautogui, core.abyss_scan
    seq = list(scans)

    def fake_scan(frame, log=None):
        return seq.pop(0) if seq else ([""] * 3, False, "hết kịch bản")

    core.pyautogui, core.abyss_scan = gui, fake_scan
    try:
        status, payload = core.abyss_action(action, threading.Event(), 0)
    finally:
        core.pyautogui, core.abyss_scan = real_gui, real_scan
    return status, payload, gui.clicks


PANEL = ([CAST, COLD, HERALD], True, None)          # có nút refresh
PANEL_NR = ([CAST, COLD, HERALD], False, None)      # không có nút refresh

print("=== 1. Lọc ô: đúng ô nào được phép chọn ===")
check("không cấm gì -> cả 3 ô",
      core.abyss_pick_allowed([CAST, COLD, HERALD], []) == [0, 1, 2])
check("cấm 1 -> còn 2",
      core.abyss_pick_allowed([CAST, COLD, HERALD], [{"mod": M_COLD}]) == [0, 2])
check("cấm cả 3 -> rỗng",
      core.abyss_pick_allowed([CAST, COLD, HERALD],
                              [{"mod": M_COLD}, {"mod": M_CAST}, {"mod": M_HERALD}]) == [])
check("ô không đọc được thì né, khi còn ô khác đọc được",
      core.abyss_pick_allowed(["", COLD, HERALD], []) == [1, 2])
check("nếu KHÔNG còn ô nào đọc được thì mới đành lấy ô mù",
      core.abyss_pick_allowed(["", "", ""], []) == [0, 1, 2])
check("ô mù vẫn bị loại nếu ô khác đọc được và không cấm",
      core.abyss_pick_allowed(["", COLD], [{"mod": M_COLD}]) == [0],
      core.abyss_pick_allowed(["", COLD], [{"mod": M_COLD}]))

print("\n=== 2. Chọn bừa KHÔNG bao giờ trúng ô bị cấm ===")
seen = set()
for _ in range(60):
    st, pl, clicks = run(act(excludes=[{"mod": M_COLD}], rerolls=0), [PANEL_NR])
    seen.add(tuple(clicks[1]))
check("60 lần chọn bừa, không lần nào chạm ô 2 (bị cấm)",
      tuple(BAND[1]) not in seen, seen)
check("chỉ rơi vào ô 1 hoặc ô 3", seen <= {tuple(BAND[0]), tuple(BAND[2])}, seen)
check("vẫn có ngẫu nhiên thật giữa 2 ô còn lại", len(seen) == 2, seen)

seen = set()
for _ in range(40):
    st, pl, clicks = run(act(excludes=[{"mod": M_COLD}, {"mod": M_HERALD}], rerolls=0),
                         [PANEL_NR])
    seen.add(tuple(clicks[1]))
check("cấm 2 ô -> luôn chọn ô còn lại", seen == {tuple(BAND[0])}, seen)

print("\n=== 3. Cả 3 ô bị cấm: reroll trước, hết reroll thì DỪNG ===")
st, pl, clicks = run(act(excludes=[{"mod": M_COLD}, {"mod": M_CAST}, {"mod": M_HERALD}],
                         rerolls=0), [PANEL_NR])
check("không còn reroll -> trả về CHECK_STOP", st == core.CHECK_STOP, st)
check("lý do nói rõ là do loại trừ", "loại trừ" in (pl or ""), pl)
check("TUYỆT ĐỐI không bấm chốt ô nào — chỉ có cú REVEAL đầu",
      clicks == [CONFIRM], clicks)

st, pl, clicks = run(act(excludes=[{"mod": M_COLD}, {"mod": M_CAST}, {"mod": M_HERALD}],
                         rerolls=2), [PANEL, PANEL, PANEL])
check("còn reroll -> dùng hết reroll đã", clicks.count(REFRESH) == 2, clicks)
check("hết reroll mà vẫn bị cấm hết -> DỪNG", st == core.CHECK_STOP, st)
check("vẫn không chốt ô nào", not any(c in [tuple(b) for b in BAND] for c in
                                      [tuple(x) for x in clicks]), clicks)

# reroll ra bàn mới có ô không bị cấm -> chọn được, không dừng
PANEL2 = ([CAST, "+9% TO FIRE RESISTANCE", HERALD], True, None)
st, pl, clicks = run(act(excludes=[{"mod": M_COLD}, {"mod": M_CAST}, {"mod": M_HERALD}],
                         rerolls=1), [PANEL, PANEL2])
check("reroll ra ô hợp lệ -> chọn ô đó, không dừng", st == core.CHECK_NO_MATCH, st)
check("chọn đúng ô 2 (ô duy nhất không bị cấm)", BAND[1] in clicks, clicks)

print("\n=== 4. Không có nút refresh + cấm hết -> dừng luôn ===")
st, pl, clicks = run(act(excludes=[{"mod": M_COLD}, {"mod": M_CAST}, {"mod": M_HERALD}],
                         rerolls=3), [PANEL_NR])
check("không có nút refresh thì không cố reroll", REFRESH not in clicks, clicks)
check("và dừng ngay", st == core.CHECK_STOP, st)

print("\n=== 5. Loại trừ KHÔNG đụng tới điều kiện muốn ===")
st, pl, clicks = run(act(conditions=[{"mod": M_COLD}], excludes=[{"mod": M_CAST}]), [PANEL])
check("mod muốn vẫn được chọn bình thường", st == core.CHECK_MATCH, st)
check("chốt đúng ô 2", clicks == [CONFIRM, BAND[1], CONFIRM], clicks)

st, pl, clicks = run(act(conditions=[{"mod": M_COLD}], excludes=[{"mod": M_COLD}]), [PANEL])
check("mod nằm ở cả 2 bảng -> Điều kiện THẮNG", st == core.CHECK_MATCH, st)

print("\n=== 6. Không đặt loại trừ thì mọi thứ y như cũ ===")
seen = set()
for _ in range(40):
    st, pl, clicks = run(act(rerolls=0), [PANEL_NR])
    seen.add(tuple(clicks[1]))
check("chọn bừa vẫn rải đều cả 3 ô", len(seen) == 3, seen)
check("vẫn trả về NO_MATCH", st == core.CHECK_NO_MATCH, st)

print("\n=== 7. Bộ máy chạy: CHECK_STOP dừng NGAY, giữ nguyên lý do ===")


class FakeClip:
    def copy(self, s):
        pass

    def paste(self):
        return ""


def run_process(steps, scans):
    gui = FakeAutoGui()
    saved = (core.pyautogui, core.abyss_scan, core.pyperclip, core.HAS_CLIP)
    seq = list(scans)

    def fake_scan(frame, log=None):
        return seq.pop(0) if seq else (([CAST, COLD, HERALD], False, None))

    core.pyautogui, core.abyss_scan = gui, fake_scan
    core.pyperclip, core.HAS_CLIP = FakeClip(), True
    logs = []
    try:
        r = core.ProcessRunner({"name": "T", "start_delay": 0, "pre_click_ms": 0,
                                "hover_ms": 0, "copy_keys": "ctrl+c", "steps": steps},
                               threading.Event(), on_log=lambda s, t=None: logs.append(s))
        status, loops = r.run()
    finally:
        core.pyautogui, core.abyss_scan, core.pyperclip, core.HAS_CLIP = saved
    return status, loops, logs, gui


cam_het = act(excludes=[{"mod": M_COLD}, {"mod": M_CAST}, {"mod": M_HERALD}], rerolls=0)
step = {"kind": "loop", "name": "Abyss", "loop_start_index": 0, "max_loops": 50,
        "actions": [cam_het]}
status, loops, logs, gui = run_process([step], [PANEL_NR] * 50)
check("dừng ngay vòng ĐẦU, không đợi đủ 3 lần như read_fail", loops == 1,
      f"chạy {loops} vòng")
check("thông báo cuối nêu đúng lý do loại trừ", "loại trừ" in status, status)
check("có ghi nhật ký lý do", any("loại trừ" in l for l in logs),
      [l for l in logs if "⛔" in l][:2])
check("không chốt ô nào trong suốt vòng chạy",
      not any(tuple(c) in [tuple(b) for b in BAND] for c in gui.clicks), gui.clicks)

# bước sau không được chạy
step2 = {"kind": "group", "name": "Sau", "actions": [{"type": "left_click", "point": [9, 9]}]}
status, loops, logs, gui = run_process([step, step2], [PANEL_NR] * 50)
check("bước sau KHÔNG chạy", (9, 9) not in [tuple(c) for c in gui.clicks], gui.clicks)

print("\n=== 8. Soát cấu hình ===")
p = core.abyss_problems(act(conditions=[{"mod": M_COLD}], excludes=[{"mod": M_COLD}]))
check("mod ở cả 2 bảng -> CẢNH BÁO", any(x["severity"] == "warning" and "loại trừ" in x["message"]
                                          for x in p), p)
p = core.abyss_problems(act(conditions=[{"mod": M_COLD}], excludes=[{"mod": M_CAST}]))
check("không mâu thuẫn -> không cảnh báo chuyện đó",
      not any("loại trừ" in x["message"] for x in p), p)


# ---------------------------------------------------------------------------
# Phần kiểm GIAO DIỆN tkinter đã bỏ: giao diện đó không còn (bản web thay thế).
# Luật hợp lệ của hành động giờ nằm ở `core.build_action`, kiểm trong
# tests/test_do_thi_va_api.py §8 — dùng chung cho mọi giao diện.
# ---------------------------------------------------------------------------

print(f"KẾT QUẢ: {ok} đúng / {fail} sai")
sys.exit(1 if fail else 0)