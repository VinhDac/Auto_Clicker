"""Chạy/Dừng qua tầng `api.py` của giao diện web.

Process dùng để thử chỉ gồm hành động `delay` — KHÔNG click, KHÔNG đọc clipboard,
KHÔNG đụng chuột thật. Nhờ vậy bài này nằm ở nhóm AN_TOAN dù nó chạy bộ máy thật.

Chỗ dễ hỏng nhất không phải bộ máy (đã có 8 bài khác lo) mà là phần bao quanh nó:
luồng phụ, hàng đợi nhật ký, phím dừng toàn cục, và việc `run()` phải trả về NGAY
thay vì chờ chạy xong.
"""
import _boot  # noqa: F401

import sys
import time
import json

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


class CuaSoGia:
    """Đóng vai cửa sổ pywebview: ghi lại mọi lời gọi evaluate_js."""

    def __init__(self):
        self.goi = []

    def evaluate_js(self, js):
        self.goi.append(js)
        return None


def process_delay(so_vong=3, so_hd=2, ms=10):
    lp = core.make_loop_step("Loop thử")
    lp["max_loops"] = so_vong
    lp["actions"] = [{"type": "delay", "min_ms": ms, "max_ms": ms} for _ in range(so_hd)]
    return [lp]


def cho_xong(a, giay=15):
    t0 = time.time()
    while time.time() - t0 < giay:
        if not (a._thread and a._thread.is_alive()):
            return True
        time.sleep(0.05)
    return False


A_api = api.Api()
cs = CuaSoGia()
A_api._window = cs

print("§1 — chặn trước khi chạy")
r = A_api.run("P", [])
kiem("Process rỗng -> không chạy", r["ok"] is False and "chưa có bước" in r["error"])

xau = [dict(core.make_loop_step("x"), max_loops=0)]
r = A_api.run("P", xau)
kiem("có LỖI -> chặn, kèm danh sách lỗi", r["ok"] is False and r.get("loi"))

# Loop không có check_mod -> validate ra CẢNH BÁO ("chưa có mục tiêu").
# Cảnh báo thì phải HỎI LẠI chứ không tự quyết hộ người dùng.
r = A_api.run("P", process_delay())
kiem("có CẢNH BÁO -> trả can_hoi thay vì tự chạy",
     r["ok"] is False and r.get("can_hoi") is True and r.get("canh_bao"))

print("§2 — chạy thật (chỉ delay, không đụng chuột)")
t0 = time.time()
r = A_api.run("P thử", process_delay(so_vong=3, so_hd=2, ms=10), start_delay=0, bo_qua_canh_bao=True)
tra_ve_sau = time.time() - t0
kiem("run() ok", r["ok"], str(r.get("error", "")))
# Chờ chạy xong rồi mới trả về thì cầu nối bị khoá và cả giao diện đứng hình —
# kể cả nút Dừng. Phải trả về ngay.
kiem("run() trả về NGAY, không chờ chạy xong", tra_ve_sau < 0.5, f"({tra_ve_sau*1000:.0f} ms)")
kiem("báo lại phím dừng cho giao diện", (r.get("value") or {}).get("hotkey", "").upper() == "F6")

kiem("chạy xong trong thời gian hợp lý", cho_xong(A_api))
time.sleep(0.4)                       # cho bơm nhật ký đẩy nốt lô cuối

js = "\n".join(cs.goi)
kiem("có đẩy sự kiện sang JS", "__su_kien" in js)
kiem("nhật ký có dòng bắt đầu Process", "Bắt đầu Process" in js)
kiem("nhật ký có dòng kết thúc", "Kết thúc" in js)
kiem("có gửi trạng thái", '"status"' in js)
# Dòng cuối phải mang cờ "het" — giao diện dựa vào đó để bật lại nút Chạy.
kiem("lô cuối có cờ het", '"het": true' in js or '"het":true' in js)

print("§3 — phím dừng toàn cục phải được GỠ sau khi chạy")
# Không gỡ thì lần chạy sau đăng ký chồng lên, và F6 vẫn dính vào app đã tắt.
kiem("gỡ add_hotkey", A_api._hotkey is None)
kiem("gỡ on_press_key", A_api._hotkey_raw is None)

print("§4 — bấm Dừng giữa chừng")
cs.goi.clear()
r = A_api.run("P dài", process_delay(so_vong=2000, so_hd=2, ms=15), start_delay=0,
          bo_qua_canh_bao=True)
kiem("chạy được", r["ok"])
time.sleep(0.5)
kiem("đang chạy", A_api.dang_chay()["value"] is True)
A_api.stop()
kiem("dừng trong vòng 3 giây", cho_xong(A_api, 3))
kiem("gỡ hotkey sau khi dừng", A_api._hotkey is None and A_api._hotkey_raw is None)

print("§5 — không cho chạy chồng")
r = A_api.run("P dài", process_delay(so_vong=400, so_hd=1, ms=15), start_delay=0,
          bo_qua_canh_bao=True)
kiem("chạy lần 1 ok", r["ok"])
r2 = A_api.run("P dài", process_delay(so_vong=400, so_hd=1, ms=15), start_delay=0,
           bo_qua_canh_bao=True)
kiem("lần 2 bị chặn", r2["ok"] is False and "đang chạy" in r2["error"])
A_api.stop()
cho_xong(A_api, 3)

print("§6 — đóng app giữa lúc đang chạy")
A_api.run("P dài", process_delay(so_vong=2000, so_hd=2, ms=15), start_delay=0,
      bo_qua_canh_bao=True)
time.sleep(0.4)
A_api.dong_app()                          # app_web.py gọi ở sự kiện closing
kiem("dong_app() dừng được worker", cho_xong(A_api, 3))
kiem("dong_app() gỡ sạch hotkey", A_api._hotkey is None and A_api._hotkey_raw is None)

print("§7 — cửa sổ đóng rồi vẫn không được làm chết worker")
A_api._window = None                       # y như cửa sổ đã bị huỷ
r = A_api.run("P", process_delay(so_vong=2, so_hd=1, ms=10), start_delay=0, bo_qua_canh_bao=True)
kiem("vẫn chạy được khi không có cửa sổ", r["ok"])
kiem("kết thúc bình thường, không nổ", cho_xong(A_api, 6))

print("§8 — THỨ TỰ CHẠY phải đi theo ĐƯỜNG NỐI, không theo thứ tự danh sách")
# Đây là lỗi từng lọt qua cả P1→P3: canvas vẽ C→A→B mà bộ máy chạy A→B→C.


def buoc(ten):
    s = core.make_loop_step(ten)
    s["max_loops"] = 1
    s["actions"] = [{"type": "delay", "min_ms": 1, "max_ms": 1}]
    return s


def thu_tu_chay(bs, edges):
    """Chạy thật rồi đọc lại nhật ký xem đã đi qua những bước nào, theo thứ tự nào."""
    ra = []
    cfg = {"name": "t", "game": "poe2", "steps": bs, "start_delay": 0, "edges": edges,
           "pre_click_ms": 0, "hover_ms": 0, "copy_keys": "ctrl+c", "stop_hotkey": "f6"}
    core.ProcessRunner(cfg, __import__("threading").Event(),
                       on_log=lambda m, t=None: ra.append(m)).run()
    return [m.split("—")[0].split("]")[-1].strip() for m in ra if m.startswith("🔁")]


A, B, C = buoc("A"), buoc("B"), buoc("C")
bs = [A, B, C]
ids = {s["id"]: s["name"] for s in bs}


def noi(*cap):
    return [{"from": a["id"], "to": b["id"], "port": "out"} for a, b in cap]


kiem("không có edges (file cũ) -> chuỗi thẳng", thu_tu_chay(bs, None) == ["A", "B", "C"])
kiem("nối C→A→B -> chạy C, A, B", thu_tu_chay(bs, noi((C, A), (A, B))) == ["C", "A", "B"])
kiem("nối B→A (2 bước) -> chỉ chạy đúng 2 bước đó",
     thu_tu_chay(bs, noi((B, A))) == ["B", "A"], "(C không có đường vào nên C là… )")
# ^ B và C đều không có đường vào; flow_entry lấy bước ĐẦU TIÊN trong danh sách
#   không có đường vào -> đó là B. C không bao giờ tới -> validate cảnh báo.

print("§9 — số thứ tự trên góc khối = đúng thứ tự chạy thật")
kq = core.flow_order(bs, noi((C, A), (A, B)))
kiem("flow_order khớp thứ tự chạy",
     [ids[k] for k, _ in sorted(kq["order"].items(), key=lambda x: x[1])] == ["C", "A", "B"])
kq2 = core.flow_order(bs, noi((A, B)))
kiem("bước không có đường dẫn tới -> vào danh sách unreachable",
     [ids[i] for i in kq2["unreachable"]] == ["C"])
# Vòng lặp chỉ NHÌN THẤY được khi có lối vào rồi mới quay ngược (A→B→C→B).
# Đồ thị toàn vòng (A→B→C→A) thì không có bước bắt đầu nên phép duyệt không chạy —
# trường hợp đó bị bắt bằng lỗi "không tìm được bước bắt đầu" ở §10.
kq3 = core.flow_order(bs, noi((A, B), (B, C), (C, B)))
kiem("phát hiện vòng lặp ở tầng Process", kq3["loop"] is True)
kiem("vẫn đánh số được phần trước vòng lặp", len(kq3["order"]) == 3)

print("§10 — soát đồ thị")
# Nhiều đường ra KHÔNG còn là lỗi — đó là rẽ nhánh. Nhưng phải quyết định được đi
# đường nào: B và C đều không phải cổng "Xác nhận mod" nên vẫn bị chặn.
p = core.validate_flow_graph(bs, noi((A, B), (A, C)))
kiem("rẽ 2 nhánh mà nhánh nào cũng không có cổng -> LỖI",
     any(x["severity"] == "error" and "không biết chọn nhánh nào" in x["message"] for x in p))
p = core.validate_flow_graph(bs, noi((A, B)))
kiem("bước không bao giờ tới -> CẢNH BÁO",
     any(x["severity"] == "warning" and "không bao giờ chạy tới" in x["message"] for x in p))
p = core.validate_flow_graph(bs, noi((A, B), (B, C), (C, A)))
kiem("đồ thị toàn vòng, không có chỗ bắt đầu -> LỖI",
     any(x["severity"] == "error" and "bước bắt đầu" in x["message"] for x in p))
kiem("chuỗi thẳng bình thường -> không có vấn đề gì",
     core.validate_flow_graph(bs, core.default_edges(bs)) == [])

# api.validate trả kèm số thứ tự cho giao diện vẽ lên góc khối
r = A_api.validate(bs, noi((C, A), (A, B)))
kiem("api.validate trả kèm order", r["ok"] and len(r["order"]) == 3)
# Nhãn là CHUỖI, không phải số: có rẽ nhánh rồi thì "4A.2" mới nói đủ chuyện.
kiem("order của api khớp core",
     r["order"][C["id"]] == "1" and r["order"][B["id"]] == "3")

print("§11 — chốt chặn vòng lặp vô tận")
kiem("MAX_PROCESS_STEPS có thật và đủ lớn",
     isinstance(core.MAX_PROCESS_STEPS, int) and core.MAX_PROCESS_STEPS >= 1000)

print("§12 — CHỐT CHẶN: js_api không được mang thuộc tính là ĐỐI TƯỢNG")
# Lỗi thật đã gặp: `api.window = <Window>` làm app "Not Responding" ngay khi mở.
#
# pywebview dựng danh sách hàm cho JS bằng `get_functions()` (webview/util.py:190):
# nó duyệt `dir(js_api)` và ĐỆ QUY vào mọi thuộc tính không callable. Chạm vào đối
# tượng Window là nó đọc các property `width`/`x`/`title` — những thứ hỏi ngược luồng
# giao diện, đúng luồng đang bị chặn để chờ -> deadlock, cửa sổ không bơm thông điệp
# nữa. Không có traceback, không tốn CPU, chỉ đơ.
#
# Luật: mọi thứ không phải hàm PHẢI có tên bắt đầu bằng "_".
import inspect

_a = api.Api()
_xau = []
for _ten in dir(_a):
    if _ten.startswith("_"):
        continue                       # pywebview bỏ qua tên có gạch dưới
    _v = getattr(_a, _ten)
    if not (inspect.ismethod(_v) or inspect.isfunction(_v)):
        _xau.append(f"{_ten} ({type(_v).__name__})")
kiem("mọi thuộc tính công khai của Api đều là HÀM", not _xau,
     f"— vi phạm: {', '.join(_xau)}" if _xau else "")

# Và bề mặt công khai phải đúng những gì giao diện cần, không thừa
_ham = {t for t in dir(_a) if not t.startswith("_")}
kiem("có đủ các hàm giao diện dùng",
     {"run", "stop", "validate", "bootstrap", "save_action", "pick_point",
      "save_process", "load_process", "save_settings"} <= _ham)

print(f"\n✔ KẾT QUẢ: {dung} đúng / {sai} sai")
sys.exit(0 if sai == 0 else 1)
