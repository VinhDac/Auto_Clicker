# Bài test

Chạy tất cả:

    .venv\Scripts\python.exe tests\chay_tat_ca.py          # nhóm an toàn
    .venv\Scripts\python.exe tests\chay_tat_ca.py --full   # thêm bài điều khiển chuột thật

## Ba cái bẫy đã dính, đừng dính lại

1. **Đo bằng ctypes phải khai `argtypes`/`restype`.** Gọi `IsHungAppWindow(hwnd)` mà
   không khai làm HWND 64-bit bị cắt còn 32-bit; hàm trả "không treo" trong khi app
   đang treo. Suýt kết luận sai hoàn toàn.

2. **Test hỏi DOM không thấy được app treo.** Đã có lúc 598 check xanh mà app hoàn
   toàn không dùng được. Chỉ `SendMessageTimeout(WM_NULL)` mới trả lời được câu
   "cửa sổ còn xử lý thông điệp không" — đó là việc của `test_e2e_web.py`.

3. **Ca đối chứng hỏng thì vứt cả thí nghiệm.** Trước khi kết luận "app treo", phải
   kiểm một cửa sổ pywebview trống xem nó có bị báo treo không.

## Ảnh mẫu

`tests/anh/` — ảnh chụp thật từ game, dùng để kiểm OCR Abyss và bộ dò ô kho đồ.
Đường dẫn trong test tính từ GỐC dự án vì `_boot.py` `chdir` về đó.
