"""Mô hình đồ thị (id bước, toạ độ, đường nối) + tầng `api.py`.

Đây là bộ test THAY THẾ cho phần lớn số kiểm tra giao diện tkinter sẽ mất khi chuyển
sang web: `api.py` là bề mặt duy nhất giao diện web gọi tới, và nó chạy được bằng
Python thuần, không cần mở cửa sổ nào.

Không điều khiển chuột, không mở cửa sổ -> nằm ở nhóm AN_TOAN.
"""
import _boot  # noqa: F401

import os
import sys
import json
import copy
import tempfile

import core
import api

dung = sai = 0


def kiem(ten, dk, chi_tiet=""):
    global dung, sai
    if dk:
        dung += 1
        print(f"  ✔ {ten} {chi_tiet}")
    else:
        sai += 1
        print(f"  ✘ {ten} {chi_tiet}")


A = api.Api()

# ============================================================ §1 ID bước
print("§1 — ID bước phải bền")
l1, l2 = core.make_loop_step("A"), core.make_loop_step("B")
kiem("mỗi bước có id riêng", l1["id"] != l2["id"] and l1["id"].startswith("s"))

# Giao diện cũ thay CẢ bước mỗi lần sửa xong hành động lẻ. Nếu id đổi theo thì trên
# đồ thị nó thành nút khác và mất sạch đường nối -> phải giữ id.
a = {"type": "left_click", "point": [1, 2], "id": "sGIU12345"}
kiem("make_action_step GIỮ id cũ", core.make_action_step(a)["id"] == "sGIU12345")
kiem("make_action_step cấp id khi chưa có",
     core.make_action_step({"type": "delay"}).get("id", "").startswith("s"))

trung = [{"kind": "loop", "id": "x", "actions": []}, {"kind": "loop", "id": "x", "actions": []}]
core.ensure_step_ids(trung)
kiem("ensure_step_ids dọn id trùng", trung[0]["id"] != trung[1]["id"])

giu = [{"kind": "loop", "id": "sABC", "actions": []}]
core.ensure_step_ids(giu)
kiem("ensure_step_ids KHÔNG đụng id sẵn có", giu[0]["id"] == "sABC")

# ============================================================ §2 đường nối
print("§2 — đường nối")
b = [core.make_loop_step("1"), core.make_group_step("2"), core.make_loop_step("3")]
e = core.default_edges(b)
kiem("mặc định là chuỗi thẳng 1→2→3",
     len(e) == 2 and e[0]["from"] == b[0]["id"] and e[0]["to"] == b[1]["id"])
kiem("1 bước thì không có đường nối nào", core.default_edges(b[:1]) == [])
kiem("0 bước cũng không nổ", core.default_edges([]) == [])

ids = [s["id"] for s in b]
ban = [{"from": ids[0], "to": ids[2], "port": "out"},
       {"from": ids[0], "to": "khong-ton-tai", "port": "out"},
       {"from": ids[0], "to": ids[2], "port": "out"}]        # trùng
sach = core.clean_edges(ban, b)
kiem("bỏ đường nối trỏ tới bước không tồn tại", all(x["to"] in ids for x in sach))
kiem("bỏ đường nối trùng", len(sach) == 1)
kiem("giữ cạnh hộp (from_side/to_side)",
     core.clean_edges([{"from": ids[0], "to": ids[1], "port": "out",
                        "from_side": "bottom", "to_side": "top"}], b)[0]["to_side"] == "top")

# ============================================================ §3 lưu / đọc lại
print("§3 — lưu rồi đọc lại không mất gì")
b[0]["pos"] = [120, 40]
doc = core.make_process_template("P", "poe2", 5, b, [{"from": ids[0], "to": ids[2], "port": "out"}])
kiem("định dạng đúng chuẩn", doc["schema"] == 3 and doc["type"] == "process")
lai = core.normalize_process(json.loads(json.dumps(doc)))
kiem("giữ pos", lai["steps"][0].get("pos") == [120.0, 40.0])
kiem("giữ đường nối tuỳ biến", len(lai["edges"]) == 1 and lai["edges"][0]["to"] == ids[2])
kiem("giữ id", [s["id"] for s in lai["steps"]] == ids)

# File CŨ (không có khoá edges) phải ra đúng sơ đồ chuỗi thẳng — tức là "chưa có đường
# nối" và "nối thẳng" là một, không phải di cư dữ liệu gì cả.
cu = json.loads(json.dumps(doc))
del cu["edges"]
for s in cu["steps"]:
    s.pop("id", None)
lai_cu = core.normalize_process(cu)
kiem("file cũ -> tự suy ra chuỗi thẳng", len(lai_cu["edges"]) == len(lai_cu["steps"]) - 1)
kiem("file cũ -> được cấp id", all(s.get("id") for s in lai_cu["steps"]))

# ============================================================ §4 api.py
print("§4 — api.py: mọi hàm trả dict, không ném exception")
bt = A.bootstrap()
kiem("bootstrap ok", bt["ok"] and len(bt["value"]["action_types"]) == 8)
kiem("ping", A.ping()["value"] == "pong")

for kind in ("loop", "group", "action"):
    r = A.new_step(kind)
    kiem(f"new_step({kind})", r["ok"] and r["value"]["step"]["id"] and r["value"]["card"]["id"])
r = A.new_step("khong-co-loai-nay")
kiem("new_step loại sai -> ok=False chứ KHÔNG ném", r["ok"] is False and "error" in r)
r = A.new_step("action", "khong-phai-hanh-dong")
kiem("new_step hành động sai -> ok=False", r["ok"] is False)

r = A.load_process("template-khong-ton-tai-xyz")
kiem("mở template không có -> ok=False, không traceback", r["ok"] is False and "error" in r)

r = A.save_process("", [])
kiem("lưu với tên rỗng -> ok=False", r["ok"] is False)

# ============================================================ §5 nội dung hộp
print("§5 — nội dung hộp do core sinh, không phải JS tự ghép")
d = A.demo_process()
kiem("demo_process ok", d["ok"] and len(d["value"]["steps"]) == 3)
the = d["value"]["cards"]
loop = the[0]
kiem("hộp Loop có badge số vòng", any("1000" in x for x in loop["badges"]))
kiem("hộp Loop có badge giữ Shift", any("shift" in x.lower() for x in loop["badges"]))
kiem("đánh dấu được mục tiêu", loop["co_muc_tieu"] and any(l["goal"] for l in loop["lines"]))
# Hành động trước dấu "Loop từ đây" chỉ chạy 1 lần — hộp phải phân biệt được, nếu
# không thì nhìn hộp không biết Loop thật sự LẶP những gì.
kiem("phân biệt phần chạy 1 lần", loop["lines"][0]["prologue"] and not loop["lines"][1]["prologue"])
kiem("dùng tên người dùng đặt", "Mở túi đồ" in loop["lines"][0]["text"])
kiem("kèm cả chi tiết kỹ thuật", "(960, 540)" in loop["lines"][0]["text"])
kiem("số dòng khớp số hành động", len(loop["lines"]) == loop["so_hanh_dong"])

# describe() phải cho ra đúng thứ demo_process đã cho -> hai đường vào một kết quả
lai2 = A.describe(d["value"]["steps"])
kiem("describe() khớp với cards của demo",
     [c["title"] for c in lai2["value"]] == [c["title"] for c in the])

# ============================================================ §6 kiểm tra
print("§6 — validate dùng chung với bản tkinter")
v = A.validate([])
kiem("Process rỗng -> báo lỗi", v["so_loi"] == 1)
v = A.validate(d["value"]["steps"])
kiem("Process mẫu -> không lỗi", v["so_loi"] == 0, f"(cảnh báo: {v['so_canh_bao']})")

# ============================================================ §7 lưu thật vào hộp cát
print("§7 — lưu/mở thật (thư mục tạm, không đụng template của người dùng)")
goc = core.app_dir
with tempfile.TemporaryDirectory() as tmp:
    core.app_dir = lambda: tmp
    try:
        r = A.save_process("bai-test-do-thi", d["value"]["steps"],
                           [{"from": d["value"]["steps"][0]["id"],
                             "to": d["value"]["steps"][2]["id"], "port": "out"}], 7)
        kiem("lưu được", r["ok"], r.get("error", ""))
        kiem("có trong danh sách", "bai-test-do-thi" in (A.list_templates()["value"] or []))
        m = A.load_process("bai-test-do-thi")
        kiem("mở lại được", m["ok"])
        kiem("start_delay đúng", m["value"]["start_delay"] == 7)
        kiem("đường nối tuỳ biến còn nguyên sau khi lưu/mở", len(m["value"]["edges"]) == 1)
        kiem("mở lại là có sẵn nội dung hộp", len(m["value"]["cards"]) == 3)
        kiem("toạ độ hộp còn nguyên", m["value"]["steps"][1].get("pos") is not None)
    finally:
        core.app_dir = goc

# ============================================================ §8 build_action
print("§8 — build_action: luật hợp lệ dùng CHUNG cho tkinter và web")


def ok_(ten, draft, kiem_them=None):
    a, loi = core.build_action(draft)
    if loi:
        kiem(ten, False, f"-> {loi}")
        return None
    kiem(ten, kiem_them(a) if kiem_them else True, "" if not kiem_them else f"-> {a}")
    return a


def hong_(ten, draft, chua=""):
    a, loi = core.build_action(draft)
    kiem(ten, a is None and loi and (chua in loi), f"-> {loi!r}")


P = [100, 200]
ok_("left_click", {"type": "left_click", "point": P}, lambda a: a["point"] == P)
ok_("right_click", {"type": "right_click", "point": P})
ok_("mod_click", {"type": "mod_click", "point": P, "keys": "shift+ctrl", "button": "right"},
    # thứ tự phím LUÔN theo MOD_KEYS, không theo thứ tự người dùng tick -> file ổn định
    lambda a: a["keys"] == "ctrl+shift" and a["button"] == "right")
ok_("key_press", {"type": "key_press", "key": " escape "}, lambda a: a["key"] == "escape")
ok_("delay", {"type": "delay", "min_ms": "20", "max_ms": "50"},
    lambda a: a["min_ms"] == 20 and a["max_ms"] == 50)
ok_("move_wasd", {"type": "move_wasd", "keys": "a+w", "ms": "800"},
    lambda a: a["keys"] == "w+a" and a["ms"] == 800)     # WASD_ORDER: dọc trước
ok_("check_mod", {"type": "check_mod", "point": P, "conditions": [{"mod": "x", "tier": 1}]})
# point=None hợp lệ ở check_mod: có thể chuột đã sẵn trên item
ok_("check_mod không cần điểm", {"type": "check_mod", "point": None,
                                 "conditions": [{"mod": "x"}]}, lambda a: a["point"] is None)
ok_("abyss", {"type": "abyss", "frame": [1, 2, 3, 4], "conditions": [{"mod": "x"}],
              "rerolls": 1, "wait_ms": 300})

hong_("loại không có thật", {"type": "bay-bien"}, "không hợp lệ")
hong_("click thiếu toạ độ", {"type": "left_click", "point": None}, "toạ độ")
hong_("mod_click chưa tick phím", {"type": "mod_click", "point": P, "keys": ""}, "chưa tick phím")
hong_("move_wasd chưa chọn hướng", {"type": "move_wasd", "keys": "", "ms": 500}, "chưa tick hướng")
hong_("move_wasd 0ms", {"type": "move_wasd", "keys": "w", "ms": 0}, "lớn hơn 0")
hong_("key_press bỏ trống", {"type": "key_press", "key": "  "}, "chưa nhập phím")
hong_("key_press phím bịa", {"type": "key_press", "key": "khong-co-phim-nay"}, "không biết phím")
hong_("delay max < min", {"type": "delay", "min_ms": 500, "max_ms": 100}, "không hợp lệ")
hong_("check_mod chưa có điều kiện", {"type": "check_mod", "point": P, "conditions": []},
      "chưa thêm điều kiện")
hong_("abyss chưa căn khung", {"type": "abyss", "conditions": [{"mod": "x"}]}, "căn khung")
hong_("abyss reroll quá lớn", {"type": "abyss", "frame": [1, 2, 3, 4],
                               "conditions": [{"mod": "x"}], "rerolls": 999}, "reroll")

# Tên là TUỲ CHỌN — chuỗi rỗng KHÔNG được ghi vào file, nếu không `action_display`
# phải đi đoán xem có nên dùng nó không.
a, _ = core.build_action({"type": "delay", "min_ms": 1, "max_ms": 2, "name": "   "})
kiem("tên toàn khoảng trắng -> không ghi khoá name", "name" not in a)
a, _ = core.build_action({"type": "delay", "min_ms": 1, "max_ms": 2, "name": " Nghỉ tay "})
kiem("tên có nội dung -> cắt khoảng trắng rồi ghi", a.get("name") == "Nghỉ tay")

# right_click nâng cao (lấy currency nhiều ô)
a, loi = core.build_action({"type": "right_click", "point": P,
                            "grid": {"frame": [1, 2, 3, 4], "cells": [[0, 0], [0, 1]]}})
kiem("right_click + lưới", loi is None and len(a["grid"]["cells"]) == 2)
hong_("bật lưới mà chưa căn", {"type": "right_click", "point": P,
                               "grid": {"frame": None, "cells": []}}, "căn lưới")
hong_("căn lưới mà chưa tick ô", {"type": "right_click", "point": P,
                                  "grid": {"frame": [1, 2, 3, 4], "cells": []}}, "chưa tick ô")
# Không bật lưới thì file lưu ra KHÔNG được có khoá thừa — template cũ phải giữ nguyên
a, _ = core.build_action({"type": "right_click", "point": P})
kiem("không bật lưới -> không có khoá grid", "grid" not in a)

# api.save_action đi qua đúng con đường đó
r = A.save_action({"type": "delay", "min_ms": 10, "max_ms": 20})
kiem("api.save_action ok", r["ok"] and "Delay" in r["value"]["display"])
r = A.save_action({"type": "key_press", "key": ""})
kiem("api.save_action báo lỗi thay vì ném", r["ok"] is False and "chưa nhập phím" in r["error"])

print(f"\n✔ KẾT QUẢ: {dung} đúng / {sai} sai")
sys.exit(0 if sai == 0 else 1)
