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


A = api.Api()
cs = CuaSoGia()
A.window = cs

print("§1 — chặn trước khi chạy")
r = A.run("P", [])
kiem("Process rỗng -> không chạy", r["ok"] is False and "chưa có bước" in r["error"])

xau = [dict(core.make_loop_step("x"), max_loops=0)]
r = A.run("P", xau)
kiem("có LỖI -> chặn, kèm danh sách lỗi", r["ok"] is False and r.get("loi"))

# Loop không có check_mod -> validate ra CẢNH BÁO ("chưa có mục tiêu").
# Cảnh báo thì phải HỎI LẠI chứ không tự quyết hộ người dùng.
r = A.run("P", process_delay())
kiem("có CẢNH BÁO -> trả can_hoi thay vì tự chạy",
     r["ok"] is False and r.get("can_hoi") is True and r.get("canh_bao"))

print("§2 — chạy thật (chỉ delay, không đụng chuột)")
t0 = time.time()
r = A.run("P thử", process_delay(so_vong=3, so_hd=2, ms=10), start_delay=0, bo_qua_canh_bao=True)
tra_ve_sau = time.time() - t0
kiem("run() ok", r["ok"], str(r.get("error", "")))
# Chờ chạy xong rồi mới trả về thì cầu nối bị khoá và cả giao diện đứng hình —
# kể cả nút Dừng. Phải trả về ngay.
kiem("run() trả về NGAY, không chờ chạy xong", tra_ve_sau < 0.5, f"({tra_ve_sau*1000:.0f} ms)")
kiem("báo lại phím dừng cho giao diện", (r.get("value") or {}).get("hotkey", "").upper() == "F6")

kiem("chạy xong trong thời gian hợp lý", cho_xong(A))
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
kiem("gỡ add_hotkey", A._hotkey is None)
kiem("gỡ on_press_key", A._hotkey_raw is None)

print("§4 — bấm Dừng giữa chừng")
cs.goi.clear()
r = A.run("P dài", process_delay(so_vong=2000, so_hd=2, ms=15), start_delay=0,
          bo_qua_canh_bao=True)
kiem("chạy được", r["ok"])
time.sleep(0.5)
kiem("đang chạy", A.dang_chay()["value"] is True)
A.stop()
kiem("dừng trong vòng 3 giây", cho_xong(A, 3))
kiem("gỡ hotkey sau khi dừng", A._hotkey is None and A._hotkey_raw is None)

print("§5 — không cho chạy chồng")
r = A.run("P dài", process_delay(so_vong=400, so_hd=1, ms=15), start_delay=0,
          bo_qua_canh_bao=True)
kiem("chạy lần 1 ok", r["ok"])
r2 = A.run("P dài", process_delay(so_vong=400, so_hd=1, ms=15), start_delay=0,
           bo_qua_canh_bao=True)
kiem("lần 2 bị chặn", r2["ok"] is False and "đang chạy" in r2["error"])
A.stop()
cho_xong(A, 3)

print("§6 — đóng app giữa lúc đang chạy")
A.run("P dài", process_delay(so_vong=2000, so_hd=2, ms=15), start_delay=0,
      bo_qua_canh_bao=True)
time.sleep(0.4)
A.dong_app()                          # app_web.py gọi ở sự kiện closing
kiem("dong_app() dừng được worker", cho_xong(A, 3))
kiem("dong_app() gỡ sạch hotkey", A._hotkey is None and A._hotkey_raw is None)

print("§7 — cửa sổ đóng rồi vẫn không được làm chết worker")
A.window = None                       # y như cửa sổ đã bị huỷ
r = A.run("P", process_delay(so_vong=2, so_hd=1, ms=10), start_delay=0, bo_qua_canh_bao=True)
kiem("vẫn chạy được khi không có cửa sổ", r["ok"])
kiem("kết thúc bình thường, không nổ", cho_xong(A, 6))

print(f"\n✔ KẾT QUẢ: {dung} đúng / {sai} sai")
sys.exit(0 if sai == 0 else 1)
