# Bài test

Chạy trước mỗi lần build:

```
tools\chay_test.bat
```

Hoặc:

```
python tests\chay_tat_ca.py          # các bài an toàn (~10 giây)
python tests\chay_tat_ca.py --full   # thêm bài điều khiển chuột thật (~30 giây)
```

Mã thoát 0 = tất cả đạt. Từng bài cũng chạy riêng được:
`python tests\test_them_hanh_dong.py`

## Có những bài nào

| File | Kiểm cái gì |
|---|---|
| `test_abyss_ocr.py` | OCR 3 ô mod + dò nút refresh, chạy trên 2 ảnh mẫu thật ở thư mục gốc |
| `test_abyss_luong_chay.py` | Luồng reveal → quét → reroll → confirm, đúng thứ tự click, đọc lỗi thì không chọn bừa |
| `test_abyss_giao_dien.py` | Hộp thoại Abyss, overlay căn khung, lưu/mở template |
| `test_giu_shift.py` | Tick "Giữ Shift suốt Loop" + gia cố `mod_click` |
| `test_hop_thoai_hanh_dong.py` | Hộp thoại hành động không được chứa widget chiếm grab toàn cục |
| `test_them_hanh_dong.py` | Thêm/sửa/xoá/copy hành động qua nhiều Loop, setup dài 40 hành động, lưu & mở lại |
| `test_chon_buoc_chuot.py` | Chọn bước và kéo-thả bằng sự kiện chuột |
| `test_phim_tat.py` | Phím tắt 2 bảng: Ctrl+C/V, Delete, kéo-thả, dán rác không vỡ |
| `test_hoi_quy.py` | Các tính năng cũ không bị vỡ |
| `test_modclick_chuot_that.py` | Chạy thật bằng chuột thật — **chỉ chạy với `--full`** |

## Ba cái bẫy khi viết thêm bài test

Cả ba đều đã từng làm mất thời gian, ghi lại để khỏi vấp lại:

1. **Cửa sổ `withdraw()` không nhận sự kiện chuột/phím.** Bài test dùng
   `event_generate` bắt buộc phải `root.deiconify()`, nếu không sự kiện bị nuốt
   im lặng và bài test "đạt" trong khi lỗi vẫn còn nguyên. Lỗi "thêm hành động
   vào Loop 2 không hiện" chỉ lòi ra khi cửa sổ được hiện thật.

2. **Hộp thoại giả thay `ActionEditor` không được `destroy()` ngay trong
   `__init__`** — `wait_window()` sẽ ném "bad window path name". Dùng
   `self.after(1, self.destroy)`.

3. **Chặn `messagebox` ở đầu bài test.** `delete_step()` bật hộp thoại xác nhận
   thật và treo bài test vô hạn:
   ```python
   m.messagebox.askyesno = lambda *a, **k: True
   ```

Ngoài ra: mọi bài phải `import _boot` đầu tiên — nó đặt `sys.path` và thư mục làm
việc về gốc dự án nên chạy từ đâu cũng được.
