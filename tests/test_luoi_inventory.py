"""Lấy currency từ nhiều ô: dò ô còn/hết trên ẢNH KHO THẬT, chọn ô, hết thì dừng."""
import sys
import threading
import tkinter as tk

import _boot  # noqa: F401  — đặt sys.path + thư mục làm việc
from PIL import Image

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


# Lưới trong ảnh mẫu thật: x 11..621, y 12..265
FRAME = [11, 12, 610, 253]
# Ô có đồ trong ảnh (hàng, cột) — đếm bằng mắt từ stash_sample.png
CO_DO = {(0, 0), (0, 1), (1, 0), (1, 1), (1, 5), (2, 0), (2, 1), (2, 7),
         (3, 0), (3, 1), (4, 0), (4, 1)}


def dung_anh(path="tests/anh/stash_sample.png"):
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

# Ô bị coi là đã cạn giữa chừng — để thử khoá ảnh phủ quyết bộ đếm.
RONG = set()


def dung_anh_dong(path="tests/anh/stash_sample.png"):
    """Như `dung_anh` nhưng ô nào nằm trong RONG thì trả về mảng phẳng (= nhìn ra trống)."""
    img = Image.open(path).convert("RGB")

    def fake_grab(rect):
        x, y, w, h = (int(v) for v in rect)
        cx, cy = x + w // 2, y + h // 2
        for (r, c) in RONG:
            bx, by, bw, bh = core.inv_cell_box(FRAME, r, c)
            if bx <= cx < bx + bw and by <= cy < by + bh:
                return Image.new("RGB", (max(1, w), max(1, h)), (20, 20, 20))
        return img.crop((x, y, x + w, y + h))

    core.grab_screen = fake_grab


def moi_hd(cells, moi_o):
    return {"type": "right_click", "point": [0, 0],
            "grid": {"frame": FRAME, "cells": cells, "per_cell": moi_o}}


print("\n=== 5. do_action: đếm lượt theo số đã khai, hết ô này sang ô sau ===")
gui = FakeAutoGui()
saved = core.pyautogui
core.pyautogui = gui
ev = threading.Event()
try:
    dung_anh_dong()
    RONG.clear()

    # 2 ô đều đầy, khai mỗi ô 2 -> tổng 4 lượt, đúng thứ tự tick
    dem = {}
    a = moi_hd([[0, 0], [0, 1]], 2)
    for _ in range(4):
        core.do_action(a, ev, 0, dem_luoi=dem)
    tam = [core.inv_cell_point(FRAME, 0, 0), core.inv_cell_point(FRAME, 0, 1)]
    check("bấm đủ 4 lượt", len(gui.clicks) == 4, gui.clicks)
    check("2 lượt đầu vào ô 1, 2 lượt sau vào ô 2",
          [c[0] for c in gui.clicks] == [tam[0], tam[0], tam[1], tam[1]], gui.clicks)
    check("click chuột PHẢI", all(c[1] == "right" for c in gui.clicks), gui.clicks)

    try:
        core.do_action(a, ev, 0, dem_luoi=dem)
        check("hết trần -> phải ném FatalActionError", False, "không ném gì")
    except core.FatalActionError as e:
        check("hết trần -> ném FatalActionError", True)
        check("lý do nêu đúng phép tính 2 ô × 2 = 4",
              "2 ô × 2 = 4" in str(e) and "hết" in str(e), str(e))
    check("hết trần -> KHÔNG bấm thêm phát nào", len(gui.clicks) == 4, gui.clicks)

    # Bộ đếm KHÔNG chia sẻ giữa hai lần chạy khác nhau
    gui.clicks.clear()
    core.do_action(a, ev, 0, dem_luoi={})
    check("lần chạy MỚI thì bộ đếm reset, bấm lại được", len(gui.clicks) == 1, gui.clicks)

    print("\n=== 5b. Soát đủ hàng TRƯỚC khi bấm phát nào ===")
    gui.clicks.clear()
    b = moi_hd([[0, 0], [0, 5], [0, 1]], 20)      # ô số 2 trống trong ảnh
    try:
        core.do_action(b, ev, 0, dem_luoi={})
        check("có ô trống -> phải ném FatalActionError", False, "không ném gì")
    except core.FatalActionError as e:
        check("có ô trống -> ném FatalActionError", True)
        check("nêu ĐÚNG SỐ THỨ TỰ ô bị trống (số 2)",
              "ô số 2" in str(e) and "TRỐNG" in str(e), str(e))
        check("nhắc luôn số đã khai", "20" in str(e), str(e))
    check("soát hỏng -> KHÔNG bấm phát nào", gui.clicks == [], gui.clicks)

    print("\n=== 5c. Ảnh có quyền PHỦ QUYẾT bộ đếm (khai thừa) ===")
    gui.clicks.clear()
    RONG.clear()
    dem = {}
    c = moi_hd([[0, 0], [0, 1]], 5)
    core.do_action(c, ev, 0, dem_luoi=dem)         # bấm ô 1 một lượt
    RONG.add((0, 0))                                # ô 1 cạn sớm hơn khai
    core.do_action(c, ev, 0, dem_luoi=dem)
    check("ô cạn sớm hơn khai -> tự nhảy sang ô sau",
          gui.clicks[-1][0] == core.inv_cell_point(FRAME, 0, 1), gui.clicks)
    RONG.add((0, 1))                                # cạn nốt ô 2
    try:
        core.do_action(c, ev, 0, dem_luoi=dem)
        check("còn lượt mà mọi ô đều trống -> phải ném FatalActionError", False, "không ném")
    except core.FatalActionError as e:
        check("còn lượt mà mọi ô đều trống -> ném FatalActionError", True)
        check("lý do nói rõ là KHAI THỪA, không phải hết trần",
              "khai nhiều hơn thực tế" in str(e), str(e))
    RONG.clear()

    print("\n=== 5d. Không bật lưới thì vẫn như cũ ===")
    gui.clicks.clear()
    core.do_action({"type": "right_click", "point": [77, 88]}, ev, 0)
    check("không bật lưới -> click đúng điểm X/Y như cũ",
          gui.clicks[-1][0] == (77, 88), gui.clicks)
    try:
        core.do_action({"type": "right_click", "point": [0, 0],
                        "grid": {"frame": FRAME, "cells": []}}, ev, 0)
        check("bật lưới mà chưa tick ô -> phải ném FatalActionError", False, "không ném")
    except core.FatalActionError:
        check("bật lưới mà chưa tick ô -> ném FatalActionError", True)
finally:
    core.pyautogui = saved
    dung_anh()

print("\n=== 6. Bộ máy chạy: hỏng kiểu nào cũng DỪNG NGAY, nêu rõ lý do ===")


class Clip:
    def copy(self, s):
        pass

    def paste(self):
        return ""


def chay(cells, moi_o, max_loops=50):
    gui = FakeAutoGui()
    saved = (core.pyautogui, core.pyperclip, core.HAS_CLIP)
    core.pyautogui, core.pyperclip, core.HAS_CLIP = gui, Clip(), True
    logs = []
    try:
        step = {"kind": "loop", "name": "Craft", "loop_start_index": 0,
                "max_loops": max_loops,
                "actions": [moi_hd(cells, moi_o), {"type": "left_click", "point": [9, 9]}]}
        r = core.ProcessRunner({"name": "T", "start_delay": 0, "pre_click_ms": 0,
                                "hover_ms": 0, "copy_keys": "ctrl+c", "steps": [step]},
                               threading.Event(), on_log=lambda s, t=None: logs.append(s))
        status, loops = r.run()
    finally:
        core.pyautogui, core.pyperclip, core.HAS_CLIP = saved
    return status, loops, gui.clicks, logs


dung_anh_dong()
RONG.clear()
status, loops, clicks, logs = chay([[0, 0], [0, 5]], 20)
check("có ô trống -> dừng ngay vòng ĐẦU", loops == 1, f"{loops} vòng")
check("thông báo nêu rõ ô nào trống", "ô số 2" in status and "TRỐNG" in status, status)
check("hành động sau KHÔNG chạy", (9, 9) not in [c[0] for c in clicks], clicks)
check("nhật ký có ghi lý do", any("TRỐNG" in l for l in logs),
      [l for l in logs if "⛔" in l][:2])

status, loops, clicks, logs = chay([[0, 0]], 3)
bam = [c for c in clicks if c[0] == core.inv_cell_point(FRAME, 0, 0)]
check("khai 3 thì bấm ĐÚNG 3 lần rồi dừng", len(bam) == 3, clicks)
check("dừng vì hết trần, nói rõ phép tính", "1 ô × 3 = 3" in status, status)
check("không chạy hết 50 vòng", loops <= 4, f"{loops} vòng")
dung_anh()

print("\n=== 7. Soát cấu hình ===")
p = core.validate_flow([{"type": "right_click", "point": [1, 2],
                         "grid": {"frame": FRAME, "cells": [[0, 0]], "per_cell": 20}}], 0, 10)
check("cấu hình đủ -> không lỗi", not [x for x in p if x["severity"] == "error"], p)
p = core.validate_flow([{"type": "right_click", "point": [1, 2],
                         "grid": {"frame": None, "cells": [[0, 0]], "per_cell": 20}}], 0, 10)
check("chưa căn lưới -> LỖI",
      any(x["severity"] == "error" and "căn lưới" in x["message"] for x in p), p)
p = core.validate_flow([{"type": "right_click", "point": [1, 2],
                         "grid": {"frame": FRAME, "cells": []}}], 0, 10)
check("chưa tick ô nào -> LỖI",
      any(x["severity"] == "error" and "tick ô nào" in x["message"] for x in p), p)
p = core.validate_flow([{"type": "right_click", "point": [1, 2],
                         "grid": {"frame": FRAME, "cells": [[0, 0]], "per_cell": 0}}], 0, 10)
check("khai 0 item mỗi ô -> LỖI",
      any(x["severity"] == "error" and "số lượng mỗi ô" in x["message"] for x in p), p)
p = core.validate_flow([{"type": "right_click", "point": [1, 2],
                         "grid": {"frame": FRAME, "cells": [[0, 0]], "per_cell": 2}}], 0, 10)
check("tổng lượt quá ít -> CẢNH BÁO (không phải lỗi)",
      any(x["severity"] == "warning" and "lần bấm" in x["message"] for x in p)
      and not [x for x in p if x["severity"] == "error"], p)

print("\n=== 8. Lưu hành động: số lượng mỗi ô ===")
a, e = core.build_action({"type": "right_click", "point": [1, 2],
                          "grid": {"frame": FRAME, "cells": [[0, 0]], "per_cell": "12"}})
check("khai 12 -> lưu ra số 12", a and a["grid"]["per_cell"] == 12, e or a)
a, e = core.build_action({"type": "right_click", "point": [1, 2],
                          "grid": {"frame": FRAME, "cells": [[0, 0]], "per_cell": ""}})
check("để trống -> rơi về mặc định, KHÔNG báo lỗi",
      a and a["grid"]["per_cell"] == core.INV_DEFAULT_PER_CELL, e or a)
a, e = core.build_action({"type": "right_click", "point": [1, 2],
                          "grid": {"frame": FRAME, "cells": [[0, 0]]}})
check("thiếu hẳn khoá -> rơi về mặc định (file cũ mở lại vẫn chạy)",
      a and a["grid"]["per_cell"] == core.INV_DEFAULT_PER_CELL, e or a)
a, e = core.build_action({"type": "right_click", "point": [1, 2],
                          "grid": {"frame": FRAME, "cells": [[0, 0]], "per_cell": 0}})
check("khai 0 -> báo lỗi khi lưu", a is None and "số lượng mỗi ô" in (e or ""), e)


# ---------------------------------------------------------------------------
# Phần kiểm GIAO DIỆN tkinter đã bỏ: giao diện đó không còn (bản web thay thế).
# Luật hợp lệ của hành động giờ nằm ở `core.build_action`, kiểm trong
# tests/test_do_thi_va_api.py §8 — dùng chung cho mọi giao diện.
# ---------------------------------------------------------------------------

print(f"KẾT QUẢ: {ok} đúng / {fail} sai")
sys.exit(1 if fail else 0)