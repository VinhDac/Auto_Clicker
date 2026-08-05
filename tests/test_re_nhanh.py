"""Rẽ nhánh theo mod: hành động `confirm_mod`, cách đánh số phân cấp, và bộ chạy.

MÔ HÌNH
-------
`check_mod`   khớp      -> DỪNG Loop            (đạt mục tiêu, đã có từ trước)
`confirm_mod` KHÔNG khớp -> DỪNG NHÁNH đang chạy (item không thuộc đường này)

Một câu luật đó đúng ở mọi chỗ `confirm_mod` đứng: làm cổng ngay sau điểm rẽ, làm
chốt chặn giữa một Nhóm, hay đứng trên chuỗi thẳng.

ĐÁNH SỐ: SỐ = đi được bao xa, CHỮ = đi nhánh nào.

    1
    2
    3
    4
    ├── 4A            <- cổng nhánh A
    │   ├── 4A.1
    │   ├── 4A.2
    │   │   ├── 4A.2A
    │   │   └── 4A.2B
    │   └── 4A.3
    └── 4B
        ├── 4B.1
        └── 4B.2
    5                 <- điểm gộp: mọi nhánh đều dẫn tới đây nên số về lại mức trên
    6

CHỖ DỄ NÓI DỐI NHẤT: thứ tự ưu tiên nhánh. Huy hiệu ghi A trước B mà bộ chạy thử B
trước là hỏng hoàn toàn. Cả hai bên đều chỉ lấy thứ tự từ `core.flow_map`, và bài
này kiểm đúng chuyện đó — kể cả sau khi kéo khối đổi chỗ.

Không điều khiển chuột, không mở cửa sổ -> nhóm AN_TOAN.
"""
import _boot  # noqa: F401

import sys
import threading

import core

dung = sai = 0


def kiem(ten, dk, chi_tiet=""):
    global dung, sai
    if dk:
        dung += 1
        print(f"  ✔ {ten} {chi_tiet}")
    else:
        sai += 1
        print(f"  ✘ {ten} {chi_tiet}")


# ---------------- tiện ích dựng sơ đồ ----------------
def cong(mod, x, y, ten=None):
    """Khối HĐ lẻ "Xác nhận mod" — đây chính là cái cổng của một nhánh."""
    s = core.make_action_step({"type": core.CONFIRM_MOD, "point": [1, 1],
                               "conditions": [{"mod": mod, "tier": 1}],
                               "name": ten or f"cổng {mod}"})
    s["pos"] = [x, y]
    return s


def viec(ten, x, y):
    s = core.make_group_step(ten)
    s["actions"] = [{"type": "key_press", "key": "escape"}]
    s["pos"] = [x, y]
    return s


def noi_day(b, cap):
    return [{"from": b[x]["id"], "to": b[y]["id"]} for x, y in cap]


def nhan_cua(b, cap):
    """{tên biến: nhãn} — để so với sơ đồ mong đợi bằng mắt thường."""
    kq = core.flow_order(list(b.values()), noi_day(b, cap))
    nguoc = {v["id"]: k for k, v in b.items()}
    return {nguoc[s]: n for s, n in kq["order"].items()}, kq


# ---------------- 1. Đánh số đúng y sơ đồ đã chốt ----------------
print("\n▸ Đánh số phân cấp")
b = {t: viec(t, 0, 0) for t in ("1", "2", "3", "4", "5", "6")}
b["4A"] = cong("modA", 300, 0)
b["4B"] = cong("modB", 300, 400)
b["4A.1"] = viec("a1", 600, 0)
b["4A.2"] = viec("a2", 900, 0)
b["4A.2A"] = cong("modX", 1200, -50)
b["4A.2B"] = cong("modY", 1200, 150)
b["4A.3"] = viec("a3", 1500, 0)
b["4B.1"] = viec("b1", 600, 400)
b["4B.2"] = viec("b2", 900, 400)
CAP = [("1", "2"), ("2", "3"), ("3", "4"),
       ("4", "4A"), ("4", "4B"),
       ("4A", "4A.1"), ("4A.1", "4A.2"),
       ("4A.2", "4A.2A"), ("4A.2", "4A.2B"),
       ("4A.2A", "4A.3"), ("4A.2B", "4A.3"),
       ("4A.3", "5"), ("4B", "4B.1"), ("4B.1", "4B.2"), ("4B.2", "5"),
       ("5", "6")]
nhan, kq = nhan_cua(b, CAP)
lech = [f"{k}→{v}" for k, v in nhan.items() if k != v]
kiem("mọi khối mang đúng nhãn trong sơ đồ", not lech, f"— lệch: {lech or 'không'}")
kiem("điểm gộp kéo số về lại mức trên cùng", nhan.get("5") == "5" and nhan.get("6") == "6")
kiem("không khối nào bị bỏ sót", not kq["unreachable"])
kiem("không báo nhầm là có vòng lặp", kq["loop"] is False)

# nhánh không gộp lại -> đơn giản là không có số ở mức trên nữa
b2 = {"1": viec("1", 0, 200), "A": cong("modA", 300, 0), "B": cong("modB", 300, 400),
      "A1": viec("a", 600, 0), "B1": viec("b", 600, 400)}
CAP2 = [("1", "A"), ("1", "B"), ("A", "A1"), ("B", "B1")]
n2, _ = nhan_cua(b2, CAP2)
kiem("nhánh không gộp → mỗi nhánh tự kết thúc, không có số mức trên",
     n2 == {"1": "1", "A": "1A", "B": "1B", "A1": "1A.1", "B1": "1B.1"}, f"— {n2}")

# không có edges -> chuỗi thẳng như từ trước tới nay
bs = [viec("x", 0, 0), viec("y", 0, 0), viec("z", 0, 0)]
cu = core.flow_order(bs, core.default_edges(bs))
kiem("không rẽ nhánh thì vẫn là 1, 2, 3 như cũ",
     sorted(cu["order"].values()) == ["1", "2", "3"], f"— {sorted(cu['order'].values())}")

# ---------------- 2. Thứ tự ưu tiên nhánh lấy từ VỊ TRÍ, và nhìn thấy được ----------------
print("\n▸ Thứ tự ưu tiên nhánh")
n3, _ = nhan_cua(b2, CAP2)
kiem("cổng nằm TRÊN là nhánh A", n3["A"] == "1A" and n3["B"] == "1B")
b2["B"]["pos"] = [300, -300]                      # kéo cổng B lên trên cổng A
n4, _ = nhan_cua(b2, CAP2)
kiem("kéo cổng lên trên thì nhãn đổi ngay → ưu tiên không bao giờ là thứ ngầm",
     n4["B"] == "1A" and n4["A"] == "1B", f"— B={n4['B']}, A={n4['A']}")
b2["B"]["pos"] = [300, 400]                       # trả lại chỗ cũ

# ---------------- 3. Bộ chạy đi đúng nhánh ----------------
print("\n▸ Bộ chạy")
nhat_ky = []


def chay(b, cap, item_co):
    """Chạy Process với 'item' đang cầm mang mod `item_co` (None = đọc hụt)."""
    nhat_ky.clear()

    def doc_gia_lap(a, stop_flag, hover_ms, copy_keys, log=None):
        if item_co is None:
            return core.CHECK_READ_FAIL, "giả lập: không đọc được"
        for c in a.get("conditions") or []:
            if c.get("mod") == item_co:
                return core.CHECK_MATCH, c
        return core.CHECK_NO_MATCH, None

    that_doc, that_lam = core.check_mod_action, core.do_action
    core.check_mod_action = doc_gia_lap
    core.do_action = lambda a, sf, ms=0, dem_luoi=None: None
    try:
        cfg = {"name": "t", "steps": list(b.values()), "edges": noi_day(b, cap),
               "start_delay": 0}
        r = core.ProcessRunner(cfg, threading.Event(),
                               on_log=lambda m, t=None: nhat_ky.append(m))
        return r.run()[0]
    finally:
        core.check_mod_action, core.do_action = that_doc, that_lam


def da_chay():
    """Nhãn các khối THỰC SỰ chạy, đọc ra từ nhật ký."""
    return [m.split("[")[1].split("]")[0] for m in nhat_ky
            if m.startswith(("▤ [", "⚡ [", "🔁 ["))]


st = chay(b2, CAP2, "modA")
kiem("trúng mod A → đi nhánh A", da_chay() == ["1", "1A.1"], f"— {da_chay()}")
st = chay(b2, CAP2, "modB")
kiem("trúng mod B → đi nhánh B", da_chay() == ["1", "1B.1"], f"— {da_chay()}")
st = chay(b2, CAP2, "modZ")
kiem("không trúng nhánh nào → dừng, KHÔNG chạy bừa nhánh nào", da_chay() == ["1"],
     f"— {da_chay()}")
kiem("  …và nói rõ lý do chứ không báo 'Hoàn thành'",
     "không khớp nhánh nào" in st, f"— \"{st[:52]}…\"")
st = chay(b2, CAP2, None)
kiem("đọc hụt chữ item ở cổng → DỪNG chứ không đoán bừa một nhánh",
     da_chay() == ["1"] and "không đọc được" in st, f"— \"{st[:52]}…\"")

# nhánh mặc định (không có cổng) phải nằm dưới cùng
b3 = dict(b2)
b3["C"] = viec("mặc định", 300, 900)
b3["C1"] = viec("c", 600, 900)
CAP3 = CAP2 + [("1", "C"), ("C", "C1")]
st = chay(b3, CAP3, "modZ")
kiem("có nhánh mặc định → không trúng gì vẫn có lối đi",
     da_chay() == ["1", "1C", "1C.1"], f"— {da_chay()}")
st = chay(b3, CAP3, "modA")
kiem("có nhánh mặc định nhưng trúng A → vẫn ưu tiên A", da_chay() == ["1", "1A.1"],
     f"— {da_chay()}")

# nhãn trong nhật ký PHẢI trùng nhãn trên canvas
n5, _ = nhan_cua(b2, CAP2)
chay(b2, CAP2, "modB")
kiem("nhật ký dùng đúng nhãn đang hiện trên canvas",
     n5["B1"] in da_chay(), f"— canvas {n5['B1']}, nhật ký {da_chay()}")

# ---------------- 4. confirm_mod dùng như hành động thường ----------------
print("\n▸ Dùng như hành động thường")
g = core.make_group_step("cất nếu đúng mod")
g["pos"] = [300, 0]
g["actions"] = [{"type": core.CONFIRM_MOD, "point": [1, 1],
                 "conditions": [{"mod": "modA", "tier": 1}]},
                {"type": "key_press", "key": "escape"}]
b4 = {"1": viec("đầu", 0, 0), "G": g, "2": viec("cuối", 600, 0)}
CAP4 = [("1", "G"), ("G", "2")]
st = chay(b4, CAP4, "modA")
kiem("chốt chặn giữa Nhóm: khớp thì chạy nốt và đi tiếp", da_chay() == ["1", "2", "3"],
     f"— {da_chay()}")
st = chay(b4, CAP4, "modZ")
kiem("chốt chặn giữa Nhóm: không khớp thì bỏ nốt nhóm và dừng nhánh",
     da_chay() == ["1", "2"] and "Nhánh dừng" in st, f"— {da_chay()}, \"{st[:40]}…\"")

# ---------------- 5. Cảnh báo ----------------
print("\n▸ Cảnh báo & chặn cấu hình sai")


def loi(steps, cap_edges, muc="error"):
    return [p["message"] for p in core.validate_flow_graph(steps, cap_edges)
            if p["severity"] == muc]


b5 = {"1": viec("đầu", 0, 200), "X": viec("nhánh không cổng", 300, 0),
      "A": cong("modA", 300, 400)}
CAP5 = [("1", "X"), ("1", "A")]
e = loi(list(b5.values()), noi_day(b5, CAP5))
kiem("nhánh mặc định xếp TRÊN cổng → chặn (mấy nhánh dưới không bao giờ chạy)",
     any("không nằm dưới cùng" in m for m in e), f"— {len(e)} lỗi")

b6 = {"1": viec("đầu", 0, 200), "X": viec("không cổng 1", 300, 0),
      "Y": viec("không cổng 2", 300, 400)}
e = loi(list(b6.values()), noi_day(b6, [("1", "X"), ("1", "Y")]))
kiem("hai nhánh đều không có cổng → chặn",
     any("không biết chọn nhánh nào" in m for m in e), f"— {len(e)} lỗi")

w = loi(list(b2.values()), noi_day(b2, CAP2), "warning")
kiem("mọi nhánh đều có điều kiện → nhắc rằng có thể không đi được đâu cả",
     any("kết thúc tại" in m for m in w), f"— {w}")

b7 = {"1": viec("đầu", 0, 200), "A": cong("modA", 300, 0), "A2": cong("modA", 300, 400)}
w = loi(list(b7.values()), noi_day(b7, [("1", "A"), ("1", "A2")]), "warning")
kiem("hai cổng trùng điều kiện → báo cái dưới không bao giờ chạy",
     any("không bao giờ chạy" in m for m in w), f"— {w}")

lp = core.make_loop_step("roll")
lp["actions"] = [{"type": core.CONFIRM_MOD, "point": [1, 1],
                  "conditions": [{"mod": "modA", "tier": 1}]}]
w = [p["message"] for p in core.validate_flow(lp["actions"], 0, 100, has_clip=True)
     if p["severity"] == "warning"]
kiem("confirm_mod đặt trong Loop → cảnh báo (đó là việc của check_mod)",
     any("DỪNG ngay từ vòng đầu" in m for m in w), f"— {len(w)} cảnh báo")

# ---------------- 6. Hành động: dựng & mô tả ----------------
print("\n▸ Hành động confirm_mod")
kiem("có trong danh sách loại hành động", core.CONFIRM_MOD in core.ACTION_TYPES)
a, err = core.build_action({"type": core.CONFIRM_MOD, "point": [10, 20],
                            "conditions": [{"mod": "modA", "tier": 1}]})
kiem("dựng được từ form", err is None and a["conditions"][0]["mod"] == "modA")
a2, err2 = core.build_action({"type": core.CONFIRM_MOD, "point": [10, 20], "conditions": []})
kiem("thiếu điều kiện thì báo lỗi", a2 is None and "điều kiện" in err2)
kiem("mô tả nói rõ khớp thì làm gì",
     "ĐI TIẾP" in core.action_summary(a) and "DỪNG nhánh" in core.action_summary(a))
kiem("KHÔNG bị coi là mục tiêu kết thúc Loop", core.CONFIRM_MOD not in core.GOAL_TYPES)
kiem("là cổng khi đứng riêng thành khối HĐ lẻ",
     core.is_branch_gate(cong("modA", 0, 0)) is True)
kiem("Nhóm KHÔNG được làm cổng (nhánh trượt phải lùi lại được)",
     core.is_branch_gate(g) is False)

print(f"\n✔ KẾT QUẢ: {dung} đúng / {sai} sai")
sys.exit(0 if sai == 0 else 1)
