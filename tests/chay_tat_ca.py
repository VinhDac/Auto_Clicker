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
    ("test_abyss_giao_dien.py", "Abyss: hộp thoại, căn khung, lưu/mở template"),
    ("test_abyss_loai_tru.py", "Abyss: danh sách loại trừ, cấm hết thì dừng"),
    ("test_giu_shift.py", "Giữ Shift suốt Loop + gia cố mod_click"),
    ("test_hop_thoai_hanh_dong.py", "Hộp thoại hành động: không widget nào chiếm grab"),
    ("test_them_hanh_dong.py", "Thêm/sửa/xoá/copy hành động qua nhiều Loop"),
    ("test_chon_buoc_chuot.py", "Chọn bước & kéo-thả bằng chuột (sự kiện giả)"),
    ("test_phim_tat.py", "Phím tắt 2 bảng: Ctrl+C/V, Delete, kéo-thả"),
    ("test_nhom_hd.py", "Nhóm HĐ 1 lần: khung dùng chung, chạy 1 lượt, template"),
    ("test_hoi_quy.py", "Hồi quy: các tính năng cũ không vỡ"),
]

# Bài này ĐIỀU KHIỂN CHUỘT THẬT ~30 giây. Đừng chạy khi đang làm việc khác.
CHUOT_THAT = [
    ("test_modclick_chuot_that.py", "Chạy thật mod_click bằng chuột thật (~30s)"),
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
