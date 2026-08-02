Tự động dùng currency lên item cho tới khi ra đúng mod mong muốn, rồi tự dừng.

## Tải về

### ⬇ [AutoClicker-v1.0.0-windows.zip](https://github.com/VinhDac/Auto_Clicker/releases/download/v1.0.0/AutoClicker-v1.0.0-windows.zip) ← **dùng bản này**

Giải nén ra rồi bấm đúp `AutoClicker.exe`. **Giữ nguyên cả thư mục**, đừng tách riêng file exe ra.

> **Vì sao là ZIP chứ không phải 1 file exe?**
>
> Bản gộp-1-file bị Windows Defender báo nhầm là `Trojan:Win32/Wacatac.H!ml` và xoá ngay khi tải.
> Đuôi `!ml` nghĩa là phát hiện bằng suy đoán/máy học, **không phải khớp chữ ký virus thật** — đây là
> lỗi báo nhầm kinh điển với file đóng gói bằng PyInstaller, do kiểu 1-file phải tự giải nén ra thư mục
> tạm khi chạy, mà Defender coi hành vi đó là đáng ngờ.
>
> Bản ZIP không có hành vi đó nên **Defender không chặn** — đã quét kiểm chứng bằng chính Defender.

## Có gì

- **Chuỗi nhiều bước** — một Process gồm nhiều Action_Loop nối tiếp, xen được hành động chạy 1 lần ở giữa (vd: spam Alteration → Regal 1 lần → spam Exalt)
- **Dừng đúng lúc** — hành động *Kiểm tra mod* khớp là dừng ngay, không táp thêm orb nào
- **Chọn mod từ Trade API chính thức** — ~3.200 mod PoE2 / ~8.600 PoE1, gõ để tìm rồi chọn
- **Lọc mod thuần / hybrid** — mod hybrid có bậc Tier riêng, khác mod thuần cùng tên
- **Tự dừng khi có sự cố** — không đọc được chữ item 3 lần liên tiếp là dừng kèm lý do, tránh đốt currency
- **Soát lỗi trước khi chạy** + **nhật ký chạy** từng bước
- **Lưu template** — cả Process, hoặc riêng một Action_Loop để tái dùng
- Giữ phím + click (Shift/Ctrl-click), delay ngẫu nhiên, cuộn, nhấn phím
- Dừng khẩn: `F6` hoặc hất chuột vào góc trên-trái
- Giao diện tối, đổi được màu nhấn

## Trước khi dùng

Game **phải bật mô tả mod chi tiết** (*Advanced Mod Descriptions*). Rê chuột vào item, bấm `Ctrl+C`, dán ra Notepad — phải thấy dạng:

```
{ Prefix Modifier "Stalwart" (Tier: 6) - Life }
+44(40-59) to maximum Life
```

Không có dòng đó thì app đọc được chữ item nhưng **không bao giờ khớp được Tier**.

## Windows cảnh báo

Lần đầu chạy có thể hiện **"Windows protected your PC"** → bấm **More info** → **Run anyway**. Do file chưa mua chứng chỉ ký số.

App không gửi dữ liệu đi đâu. Mã nguồn công khai, tự build lại được bằng `tools\build.bat`.

Chỉ chạy trên Windows.
