"""Chạy toàn bộ bài test và tổng kết.

    python tests\\chay_tat_ca.py           chạy các bài AN TOÀN (mặc định)
    python tests\\chay_tat_ca.py --full    chạy thêm bài ĐIỀU KHIỂN CHUỘT THẬT

Mã thoát 0 = tất cả đạt, khác 0 = có bài sai (dùng được cho script build).
"""
import os
import subprocess
import sys
import time

import _boot  # noqa: F401  — đặt sys.path + thư mục làm việc

HERE = os.path.dirname(os.path.abspath(__file__))

# Các bài chỉ dựng cửa sổ và bơm sự kiện vào widget — không đụng chuột thật.
AN_TOAN = [
    ("test_abyss_ocr.py", "Abyss: OCR + dò nút refresh trên ảnh mẫu thật"),
    ("test_abyss_luong_chay.py", "Abyss: luồng reveal/reroll/confirm, thứ tự click"),
    ("test_abyss_loai_tru.py", "Abyss: danh sách loại trừ, cấm hết thì dừng"),
    ("test_luoi_inventory.py", "Lấy currency nhiều ô: dò ô còn/hết trên ảnh kho thật"),
    ("test_di_chuyen.py", "Di chuyển WASD: giữ đúng phím, luôn thả, không tổ hợp sai"),
    ("test_giu_shift.py", "Giữ Shift suốt Loop + gia cố mod_click"),
    ("test_hoi_quy.py", "Hồi quy: các tính năng cũ không vỡ"),
    ("test_do_thi_va_api.py", "Đồ thị (id/toạ độ/đường nối) + tầng api.py cho web"),
    ("test_chay_web.py", "Chạy/Dừng qua api.py: luồng phụ, nhật ký, phím dừng"),
    ("test_re_nhanh.py", "Rẽ nhánh theo mod: confirm_mod, đánh số phân cấp, bộ chạy"),
    ("test_re_nhanh_web.py", "Rẽ nhánh phía giao diện: nút ribbon, nhãn lên huy hiệu (~7s)"),
    ("test_menu_ribbon_web.py", "Menu xổ Lưu/Mở: không bị ribbon cắt cụt (~8s)"),
    ("test_ghi_phim_web.py", "Ghi phím bằng cách bấm phím thật (~9s)"),
    ("test_menu_phai_web.py", "Menu chuột phải: nền / khối / dây (~9s)"),
    ("test_chep_dan_web.py", "Chép/dán khối: bản dán rơi đúng chỗ con trỏ (~6s)"),
    ("test_cong_noi_web.py", "Cổng nối trên canvas: bấm có trúng, nối xong có báo (~8s)"),
    ("test_hoan_tac_hop_thoai.py", "Ctrl+Z trong hộp thoại sửa Loop / Nhóm (~14s)"),
]

# Bài này ĐIỀU KHIỂN CHUỘT THẬT ~30 giây. Đừng chạy khi đang làm việc khác.
CHUOT_THAT = [
    ("test_overlay_tien_trinh_con.py", "Overlay chạy tiến trình con cho giao diện web (~8s)"),
    ("test_chep_dan_chuot.py", "Dán NHIỀU khối: Ctrl+click chọn nhiều, cụm giữ hình (~12s)"),
    ("test_e2e_web.py", "E2E: app web thật còn phản hồi sau mỗi thao tác (~25s)"),
]


def chay(ten):
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, "-u", os.path.join(HERE, ten)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    giay = time.perf_counter() - t0
    dong = [l for l in (p.stdout or "").splitlines() if "KẾT QUẢ" in l]
    return p.returncode, (dong[-1] if dong else "(không có dòng KẾT QUẢ)"), giay, p


def main():
    day_du = "--full" in sys.argv
    ds = list(AN_TOAN) + (list(CHUOT_THAT) if day_du else [])
    if not day_du:
        print("Bỏ qua bài điều khiển chuột thật. Muốn chạy cả: thêm --full\n")

    rong = max(len(t) for t, _ in ds)
    hong, tong_dung, tong_sai = [], 0, 0
    for ten, mo_ta in ds:
        print(f"▶ {ten:<{rong}}  {mo_ta}")
        ma, ket, giay, p = chay(ten)
        so = [int(x) for x in __import__("re").findall(r"(\d+) đúng / (\d+) sai",
                                                       ket)[0]] if "đúng /" in ket else [0, 0]
        tong_dung += so[0]
        tong_sai += so[1]
        dau = "  ✔" if ma == 0 else "  ✘"
        print(f"{dau} {ket}   ({giay:.1f}s)")
        if ma != 0:
            hong.append((ten, p))
        print()

    print("=" * 66)
    print(f"TỔNG: {tong_dung} đúng / {tong_sai} sai   —   "
          f"{len(ds) - len(hong)}/{len(ds)} bài đạt")
    if hong:
        print("\nCÁC BÀI SAI (chi tiết):")
        for ten, p in hong:
            print(f"\n--- {ten} ---")
            for l in (p.stdout or "").splitlines():
                if "FAIL" in l or "sai:" in l or "Traceback" in l:
                    print("   ", l)
            if p.stderr.strip():
                print("    stderr:", p.stderr.strip()[-400:])
    else:
        print("Tất cả đều đạt.")
    return 1 if hong else 0


if __name__ == "__main__":
    sys.exit(main())
