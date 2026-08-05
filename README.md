# Auto Clicker cho Path of Exile

Tự động dùng currency lên item **cho tới khi ra đúng mod bạn muốn**, rồi tự dừng.

App đọc mod của item bằng cách rê chuột vào item và bấm `Ctrl+C` — game copy toàn bộ chữ item ra clipboard — rồi so khớp **đúng tên mod + đúng Tier**. Không dùng nhận diện ảnh, không đoán mò.

![Giao diện Auto Clicker](assets/screenshot.png)

---

## Tải về

> ### [⬇ Tải bản mới nhất (.zip)](../../releases/latest)

**Trước khi giải nén:** chuột phải vào file `.zip` → **Properties** → tick **Unblock** → OK. Windows chặn file tải từ mạng, và nếu giải nén trước khi bỏ chặn thì app báo lỗi `Failed to resolve Python.Runtime.Loader.Initialize` lúc mở.

Giải nén ra rồi bấm đúp `AutoClickerWeb.exe`. **Giữ nguyên cả thư mục** — các file bên cạnh là thư viện cần để chạy.

**Không cần cài Python.** Nhưng máy phải có sẵn hai thứ của Windows (Windows 10/11 bản đầy đủ thường có luôn; Windows Server hoặc máy ảo gọt nhẹ thì hay thiếu):

| Cần | Nếu thiếu thì tải ở |
|---|---|
| **.NET Framework 4.7.2** trở lên | [dotnet.microsoft.com](https://dotnet.microsoft.com/download/dotnet-framework) |
| **Microsoft Edge WebView2 Runtime** | [developer.microsoft.com](https://developer.microsoft.com/microsoft-edge/webview2/) |

App tự kiểm hai thứ này lúc mở và báo bằng tiếng Việt nếu thiếu, không để bạn phải đoán.

Lần đầu chạy Windows sẽ cảnh báo — [xem cách xử lý bên dưới](#windows-báo-chặn-thì-làm-sao).

---

## Làm được gì

- **Sơ đồ kéo-thả.** Kéo các khối ra canvas rồi nối lại thành luồng chạy — nhìn là hiểu, không phải đọc danh sách. Góc mỗi khối có số thứ tự chạy do chính bộ máy tính ra, nên nó không thể nói khác việc app làm.
- **Chuỗi nhiều bước.** Một *Process* gồm nhiều *Action_Loop* nối tiếp, xen được các hành động chạy 1 lần ở giữa. Ví dụ: spam Alteration → dùng Regal 1 lần → spam Exalt.
- **Rẽ nhánh theo mod.** Nối nhiều cổng *Xác nhận mod* vào cùng một khối: trúng mod A đi đường A, trúng mod B đi đường B. Cổng thử lần lượt từ trên xuống, nhánh không có cổng là nhánh mặc định và phải xếp dưới cùng. Nhãn ở góc khối cho biết luôn nhánh nào chạy trước (`4A`, `4B`, `4A.2`…).
- **Dừng đúng lúc.** Thêm hành động *Kiểm tra mod*; khớp là dừng ngay, **không táp thêm một orb nào nữa**.
- **Chọn mod từ danh sách chính thức.** Lấy từ Trade API của game (~3.200 mod PoE2 / ~8.600 PoE1), gõ để tìm rồi chọn — không phải gõ tay nên không sai chính tả.
- **Lọc mod thuần / mod hybrid.** Một affix cho nhiều dòng stat (vd Armour + Energy Shield) có bậc Tier riêng, khác hẳn mod thuần cùng tên. Chọn được: cả hai / chỉ mod thuần / chỉ mod hybrid.
- **Tự dừng khi có sự cố.** Không đọc được chữ item 3 lần liên tiếp (game mất focus, chuột lệch vị trí…) là dừng ngay kèm lý do — thay vì âm thầm đốt sạch currency.
- **Soát lỗi trước khi chạy.** Panel *Vấn đề* chỉ ra chỗ sai (chưa chọn điểm, chưa có điều kiện, toạ độ nằm ngoài màn hình…) và bấm vào là nhảy tới đúng chỗ.
- **Nhật ký chạy.** Xem diễn biến từng bước, từng vòng, kèm lý do khi bỏ qua.
- **Lưu lại dùng lần sau.** Lưu cả Process, hoặc lưu riêng một Action_Loop để chèn vào Process khác.
- Các hành động: trái/phải-click, di chuyển (WASD), nhấn phím, **giữ phím + click** (Shift/Ctrl-click), delay ngẫu nhiên, kiểm tra mod, xác nhận mod (rẽ nhánh), Abyss.
- **Khỏi nhớ tên phím.** Hành động *Nhấn phím* và ô *Phím dừng khẩn* đều có nút bấm-để-ghi: gõ phím thật, app tự điền.
- **Dừng khẩn cấp bất cứ lúc nào:** phím `F6`, hoặc hất chuột vào **góc trên-trái** màn hình.

---

## Bắt đầu trong 3 bước

### 1. Bật mô tả mod chi tiết trong game — **bắt buộc**

App cần game in ra Tier của mod. Rê chuột vào một item rồi bấm `Ctrl+C`, dán ra Notepad. Phải thấy dạng này:

```
{ Prefix Modifier "Stalwart" (Tier: 6) — Life }
+44(40-59) to maximum Life
```

**Nếu không thấy dòng `{ ... (Tier: N) ... }`**, hãy bật tuỳ chọn hiển thị mô tả mod chi tiết (*Advanced Mod Descriptions*) trong phần Options ▸ UI của game. Thiếu nó thì app đọc được chữ item nhưng **không bao giờ khớp mod**.

### 2. Dựng Process

1. Bấm **➕ Loop** để tạo một Action_Loop.
2. Bấm **➕ Thêm** để thêm hành động (phải-click currency, trái-click item, delay…). Với hành động cần toạ độ, bấm **🎯 Chọn điểm** rồi ngắm crosshair vào đúng vị trí.
3. Thêm một hành động **🔍 Kiểm tra mod**: chọn điểm rê chuột vào item, tìm mod trong danh sách, nhập Tier, bấm **➕ Thêm điều kiện**.
4. Chọn dòng muốn lặp lại rồi bấm **🔁 Loop từ đây** — các dòng phía trên chỉ chạy 1 lần lúc đầu.

### 3. Chạy

Bấm **▶ CHẠY**, chuyển sang cửa sổ game trong lúc đếm ngược. Muốn dừng thì bấm `F6`.

> **Mẹo:** bấm **👁 Xem điểm** để soi lại tất cả toạ độ đã chọn ngay trên màn hình — kiểm tra crosshair có đúng chỗ không trước khi chạy thật.

---

## Windows báo chặn thì làm sao

### "Windows protected your PC"

File chưa mua chứng chỉ ký số nên SmartScreen cảnh báo. Bấm **More info** → **Run anyway**.

### Defender xoá mất file khi vừa tải xong

Đây là lý do bản phát hành là **file `.zip`** chứ không phải một file `.exe` duy nhất.

Bản gộp-1-file bị Windows Defender báo là `Trojan:Win32/Wacatac.H!ml` và **xoá ngay khi tải**. Đuôi `!ml` nghĩa là phát hiện bằng **suy đoán/máy học, không phải khớp chữ ký virus thật** — lỗi báo nhầm rất phổ biến với file đóng gói bằng PyInstaller, do kiểu 1-file phải tự giải nén ra thư mục tạm khi chạy nên bị coi là hành vi đáng ngờ.

**Bản `.zip` không có hành vi đó nên Defender không chặn** (đã quét kiểm chứng bằng chính Defender). Nếu bạn lỡ tải bản `.exe` và bị xoá, hãy tải bản `.zip` thay thế.

App **không** gửi dữ liệu đi đâu. Toàn bộ mã nguồn nằm ngay trong repo này — bạn có thể tự đọc, và [tự build lại](#tự-build-từ-mã-nguồn) nếu không muốn tin file có sẵn.

---

## Tự build từ mã nguồn

Cần **Python 3.10+** và **Node.js 18+** trên Windows.

```bash
git clone https://github.com/VinhDac/Auto_Clicker.git
cd Auto_Clicker
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
cd webui && npm install && npm run build && cd ..
.venv\Scripts\python.exe app_web.py
```

> Dùng **venv riêng**, đừng cài vào Python global: nếu máy có gói `quantconnect-stubs`
> thì nó chiếm namespace `Microsoft` và pywebview chết ngay lúc khởi động.

Đóng gói thành `.exe`:

```bash
tools\build.bat          # kết quả ở dist\AutoClickerWeb\
```

Chạy test:

```bash
.venv\Scripts\python.exe tests\chay_tat_ca.py
```

Cập nhật danh sách mod từ Trade API:

```bash
python update_mods.py            # cả PoE1 + PoE2
python update_mods.py poe2       # chỉ PoE2
```

---

## Cấu trúc dự án

```
core.py             lõi — không phụ thuộc giao diện, chạy headless được
api.py              bề mặt DUY NHẤT giao diện web gọi tới  (JS → api.py → core.py)
app_web.py          khởi động cửa sổ (pywebview + WebView2)
khung_cua_so.py     vá cửa sổ Win32 cho thanh tiêu đề tự vẽ (kéo/giãn/phóng to)
webui/              giao diện: React + TypeScript + React Flow
overlay_ui.py       4 overlay tkinter phủ màn hình (chọn điểm, căn khung, căn lưới)
overlays.py         chạy 4 overlay đó như tiến trình con
update_mods.py      tải danh sách mod từ Trade API chính thức
data/               mods_poe1.txt, mods_poe2.txt
tests/              bộ test  ·  tests/anh/ là ảnh mẫu chụp từ game
tools/              build.bat, setup.bat, chay_test.bat
docs/               tài liệu ý tưởng ban đầu
```

**Ba tầng, mỗi tầng biết đúng việc của mình:**

- `core.py` giữ toàn bộ logic (đọc/so khớp mod, mô hình Process, bộ máy chạy) và
  **không import tkinter** — test được mà không cần mở cửa sổ nào.
- `api.py` là chỗ duy nhất giao diện gọi tới. Giao diện **không bao giờ tự biết định
  dạng file**; nó chỉ gửi/nhận JSON. Nhờ vậy đổi định dạng chỉ phải sửa một nơi.
- `webui/` chỉ lo hiển thị. Ngay cả dòng mô tả hành động cũng do Python sinh
  (`core.action_display`), để hai bên không thể nói khác nhau.

**Vì sao thanh tiêu đề phải tự vẽ:** Windows 10 không cho đổi màu thanh tiêu đề hệ
thống (`DWMWA_CAPTION_COLOR` là của Win11, trên Win10 trả `E_INVALIDARG`). Bỏ khung
rồi tự vẽ là cách duy nhất — và `khung_cua_so.py` vá lại từng tính năng đã mất: viền
kéo giãn, phóng to đúng vùng làm việc (không che taskbar), menu hệ thống. Việc kéo cửa
sổ do **web** khởi động rồi giao cho vòng lặp của chính Windows, vì WebView2 là cửa sổ
con phủ kín cửa sổ app nên cửa sổ cha không bao giờ nhận được chuột.

**Vì sao 4 overlay vẫn là tkinter:** chúng là cửa sổ trong suốt phủ lên cửa sổ game để
bắt click và đọc pixel — WebView2 không làm được. Chúng chạy trong **tiến trình con**
vì tkinter và pywebview mỗi bên đòi một vòng lặp sự kiện riêng.

Dữ liệu của bạn (`settings.json`, thư mục `templates/`) sinh ra cạnh file exe khi chạy, không nằm trong repo.

---

## Lưu ý

- Chỉ chạy trên **Windows** (dùng API riêng của Windows cho phím tắt toàn cục và thanh tiêu đề tối).
- Nếu cửa sổ game chạy **quyền Administrator**, hãy chạy app bằng quyền Administrator, nếu không click sẽ không ăn.
- Toạ độ được lưu theo pixel tuyệt đối. Đổi độ phân giải hoặc đổi màn hình thì phải chọn lại điểm — app sẽ cảnh báo trong panel *Vấn đề* nếu phát hiện toạ độ nằm ngoài màn hình hiện tại.
- Bạn tự chịu trách nhiệm khi dùng công cụ tự động trong game.
