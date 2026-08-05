"""Tra tấn tầng đồ thị bằng những cấu hình XẤU NHẤT nghĩ ra được.

Mục tiêu không phải để xanh, mà để KHÔNG CÒN ĐƯỜNG LUI CHO BUG NGẦM. Mỗi trường hợp
dưới đây đều là thứ một file sửa tay, một file chép lại, hoặc một chuỗi thao tác thật
có thể tạo ra — và bốn trong số đó từng lọt qua toàn bộ 500+ check còn lại:

  · khối TRÙNG ID     -> một khối biến mất khỏi sơ đồ, không nhãn, không cảnh báo
  · cạnh TỰ TRỎ       -> đẻ ra thông báo lỗi vô nghĩa ("khối 2 rẽ ra nhánh 2 và 3")
  · cổng CỤT          -> khớp điều kiện xong Process im lặng kết thúc
  · VÒNG LẶP đồ thị   -> chạy tới 10000 bước, mỗi bước một lần Ctrl+C trong game

Chỗ nguy hiểm nhất của app là logic dài về sau sẽ dựa lên tầng này, nên thà đỏ ở đây
còn hơn để người dùng phát hiện lúc đang roll item thật.
"""
import _boot  # noqa: F401

import sys
import time
import random
import threading

import core

dung = sai = 0


def kiem(ten, dk, ct=""):
    global dung, sai
    if dk:
        dung += 1
        print(f"  ✔ {ten} {ct}")
    else:
        sai += 1
        print(f"  ✘ {ten} {ct}")


def cong(mod, x, y):
    s = core.make_action_step({"type": core.CONFIRM_MOD, "point": [1, 1],
                               "conditions": [{"mod": mod, "tier": 1}], "name": mod})
    s["pos"] = [x, y]
    return s


def viec(ten, x, y):
    s = core.make_group_step(ten)
    s["actions"] = [{"type": "key_press", "key": "escape"}]
    s["pos"] = [x, y]
    return s


def day(b, cap):
    return [{"from": b[a]["id"], "to": b[c]["id"]} for a, c in cap]


def loi_cua(steps, edges, muc="error"):
    return [p["message"] for p in core.validate_flow_graph(steps, edges)
            if p["severity"] == muc]


print("§1 — khối trùng id (chép file, sửa tay)")
b = {"A": viec("A", 0, 0), "B": viec("B", 300, 0), "C": viec("C", 600, 0)}
b["B"]["id"] = b["A"]["id"]
ds = list(b.values())
es = [{"from": b["A"]["id"], "to": b["C"]["id"]}]
kq = core.flow_order(ds, es)
kiem("một khối bị nuốt mất khỏi sơ đồ (đây là lý do phải cảnh báo)",
     len(kq["order"]) + len(kq["unreachable"]) < len(ds),
     f"— {len(ds)} khối trong file, {len(kq['order'])} có nhãn")
kiem("CÓ báo lỗi id trùng",
     any("trùng id" in m for m in loi_cua(ds, es)), f"— {loi_cua(ds, es)}")

print("\n§2 — cạnh tự trỏ về chính nó")
b = {"1": viec("1", 0, 0), "2": viec("2", 300, 0), "3": viec("3", 600, 0)}
cap = [("1", "2"), ("2", "2"), ("2", "3")]
e = loi_cua(list(b.values()), day(b, cap))
kiem("CÓ báo lỗi, và nói đúng bản chất là tự trỏ",
     any("CHÍNH NÓ" in m for m in e), f"— {e}")
kq = core.flow_order(list(b.values()), day(b, cap))
kiem("không treo, vẫn đánh số được phần lành", len(kq["order"]) == 3)

print("\n§3 — cổng khớp rồi mà phía sau trống")
b = {"1": viec("đầu", 0, 200), "A": cong("modA", 300, 0), "B": cong("modB", 300, 400),
     "B1": viec("việc B", 600, 400)}
cap = [("1", "A"), ("1", "B"), ("B", "B1")]
w = loi_cua(list(b.values()), day(b, cap), "warning")
kiem("CÓ cảnh báo cổng cụt", any("không có gì phía sau" in m for m in w), f"— {w}")

print("\n§4 — vòng lặp ở tầng Process")
b = {"0": viec("vào", -300, 200), "1": viec("rẽ", 0, 200),
     "A": cong("mA", 300, 0), "B": cong("mB", 300, 400)}
cap = [("0", "1"), ("1", "A"), ("1", "B"), ("A", "1")]
w = loi_cua(list(b.values()), day(b, cap), "warning")
kiem("CÓ cảnh báo vòng lặp", any("VÒNG LẶP" in m for m in w))
kiem("…và nói rõ mỗi vòng là một lần đọc chữ item",
     any("đọc chữ item" in m for m in w), f"— {[m[:70] for m in w]}")

print("\n§5 — cạnh trỏ tới khối không tồn tại")
b = {"A": viec("A", 0, 0)}
try:
    kq = core.flow_order(list(b.values()), [{"from": b["A"]["id"], "to": "khong-co"}])
    kiem("bỏ qua cạnh rác, không nổ", list(kq["order"].values()) == ["1"])
except Exception as ex:
    kiem("bỏ qua cạnh rác, không nổ", False, f"— {type(ex).__name__}")

print("\n§6 — rẽ 30 nhánh (bảng chữ cái chỉ có 26)")
b = {"1": viec("đầu", 0, 0)}
cap = []
for i in range(30):
    b[f"c{i}"] = cong(f"mod{i}", 300, i * 40)
    cap.append(("1", f"c{i}"))
nhan = list(core.flow_order(list(b.values()), day(b, cap))["order"].values())
kiem("mọi nhãn vẫn PHÂN BIỆT được", len(set(nhan)) == len(nhan),
     f"— {len(set(nhan))}/{len(nhan)}")

print("\n§7 — lồng nhánh 6 tầng: đệ quy có tràn không")
b = {"0": viec("gốc", 0, 0)}
cap = []
truoc = "0"
for t in range(6):
    a, c = f"a{t}", f"b{t}"
    b[a] = cong(f"mA{t}", t * 200, -100)
    b[c] = cong(f"mB{t}", t * 200, 100)
    cap += [(truoc, a), (truoc, c)]
    truoc = a
try:
    n = core.flow_order(list(b.values()), day(b, cap))["order"]
    kiem("không tràn ngăn xếp", True, f"— {len(n)} nhãn, dài nhất {max(n.values(), key=len)!r}")
except RecursionError:
    kiem("không tràn ngăn xếp", False, "— RecursionError")

print("\n§8 — sơ đồ to: tốc độ")
bs = [viec(f"k{i}", i * 300, 0) for i in range(400)]
e8 = core.default_edges(bs)
t0 = time.perf_counter()
core.flow_order(bs, e8)
g1 = time.perf_counter() - t0
t0 = time.perf_counter()
core.validate_process(bs, edges=e8)
g2 = time.perf_counter() - t0
kiem("đánh số 400 khối < 300ms", g1 < 0.3, f"— {g1*1000:.0f}ms")
kiem("soát 400 khối < 1s", g2 < 1.0, f"— {g2*1000:.0f}ms")

b = {}
cap = []
for i in range(40):
    b[f"g{i}"] = viec(f"g{i}", i * 400, 200)
    b[f"a{i}"] = cong(f"mA{i}", i * 400 + 150, 0)
    b[f"b{i}"] = cong(f"mB{i}", i * 400 + 150, 400)
    cap += [(f"g{i}", f"a{i}"), (f"g{i}", f"b{i}")]
    if i:
        cap += [(f"a{i-1}", f"g{i}"), (f"b{i-1}", f"g{i}")]
t0 = time.perf_counter()
core.flow_order(list(b.values()), day(b, cap))
g3 = time.perf_counter() - t0
kiem("40 điểm rẽ nối tiếp < 500ms", g3 < 0.5, f"— {g3*1000:.0f}ms")

print("\n§9 — một quyết định rẽ nhánh không được đọc lại cùng một cổng")
# Cổng vòng về chính điểm rẽ: nếu không chốt chặn thì mỗi lần quyết định "đi đâu tiếp"
# sẽ đọc chữ item hàng nghìn lần — tức nện Ctrl+C vào game cả tiếng đồng hồ.
# PHẢI có lối vào, nếu không `flow_entry` trả None và bộ chạy không chạy gì cả —
# phép đo sẽ "đạt" một cách giả với 0 lần đọc.
b = {"0": viec("vào", -300, 200), "1": viec("rẽ", 0, 200),
     "A": cong("mA", 300, 0), "B": cong("mB", 300, 400)}
cap = [("0", "1"), ("1", "A"), ("1", "B"), ("A", "1")]
dem = {"n": 0}


def doc_gia(a, sf, hv, k, log=None):
    dem["n"] += 1
    for c in a.get("conditions") or []:
        if c.get("mod") == "mA":
            return core.CHECK_MATCH, c
    return core.CHECK_NO_MATCH, None


td, tl = core.check_mod_action, core.do_action
core.check_mod_action = doc_gia
core.do_action = lambda a, sf, ms=0, dem_luoi=None: None
try:
    nk = []
    r = core.ProcessRunner({"name": "t", "steps": list(b.values()),
                            "edges": day(b, cap), "start_delay": 0}, threading.Event(),
                           on_log=lambda m, t=None: nk.append(m))
    t0 = time.perf_counter()
    st, _ = r.run()
    giay = time.perf_counter() - t0
    kiem("bộ chạy CÓ đi vào vòng lặp (nếu 0 thì phép đo vô nghĩa)", dem["n"] > 0,
         f"— đọc {dem['n']} lần")
    kiem("vẫn tự dừng, không treo", giay < 10 and "DỪNG" in st, f"— {giay:.2f}s")
    kiem("CẢNH BÁO vòng lặp ngay từ dòng đầu nhật ký",
         any("VÒNG LẶP" in m for m in nk[:3]), f"— {nk[:2]}")
    kiem("nhắc lại định kỳ trong lúc chạy",
         sum(1 for m in nk if "vẫn đang chạy" in m) >= 3,
         f"— nhắc {sum(1 for m in nk if 'vẫn đang chạy' in m)} lần")
finally:
    core.check_mod_action, core.do_action = td, tl

print("\n§10 — 300 đồ thị ngẫu nhiên: có chỗ nào nổ không")
random.seed(7)
no = []
for lan in range(300):
    n = random.randint(1, 9)
    bs = [cong(f"m{i}", random.randint(0, 500), random.randint(0, 500))
          if random.random() < .5 else viec(f"v{i}", random.randint(0, 500),
                                            random.randint(0, 500))
          for i in range(n)]
    ids = [s["id"] for s in bs]
    es = [{"from": random.choice(ids), "to": random.choice(ids)}
          for _ in range(random.randint(0, n * 2))]
    try:
        core.flow_order(bs, es)
        core.validate_process(bs, edges=es)
    except Exception as ex:
        no.append(f"lần {lan}: {type(ex).__name__}: {ex}")
kiem("300 đồ thị ngẫu nhiên không nổ lần nào", not no, f"— {no[:2]}")

print(f"\n✔ KẾT QUẢ: {dung} đúng / {sai} sai")
sys.exit(0 if sai == 0 else 1)
