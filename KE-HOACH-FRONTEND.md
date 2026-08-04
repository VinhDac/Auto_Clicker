# Kế hoạch dựng lại Frontend — Auto Clicker

Nhánh: `test_newpipeline` · Viết ngày 2026-08-04

---

## 1. Vì sao làm

Process hiện tại là **danh sách phẳng chạy một chiều**. Muốn có rẽ nhánh
(`trúng mod A → nhánh A`, `trúng mod B → nhánh B`) thì trong danh sách phẳng
phải đắp thêm: khoá `goto`, hành động `↪ Nhảy`, hành động `⏹ Kết thúc`, id bước,
cảnh báo "nhánh A tràn vào nhánh B", trần chống lặp vô tận — **5 luật + 5 cảnh báo
chỉ để mô tả một ngã rẽ**.

Trong **đồ thị**, thứ tự chạy là đường nối, hiện rõ trên màn hình, và toàn bộ đống trên
biến mất:

| Vấn đề trong danh sách phẳng | Trong đồ thị |
|---|---|
| `goto` trên điều kiện | khối rẽ nhánh có nhiều đầu ra |
| `⏹ Kết thúc Process` | đầu ra không nối đi đâu |
| "nhánh A tràn vào nhánh B" | **không thể xảy ra** |
| Nhảy ngược | kéo một đường vòng lên |
| "Loop hết vòng chưa ra mod" | đầu ra thứ hai của khối Loop |

> **Kết luận:** frontend đồ thị không phải để đẹp hơn. Nó **xoá bỏ** cả hệ thống
> goto đáng lẽ phải xây.

---

## 2. Kiểm chứng nền tảng — đã ĐO, không phải đoán

Chạy ngày 2026-08-04 trên máy thật:

| Kiểm tra | Kết quả |
|---|---|
| `core.py` import khi **chặn tkinter** bằng meta-path hook | ✅ chạy được, `tkinter` không vào `sys.modules` |
| Chữ "tkinter" trong `core.py` | 2 lần, **cả 2 đều trong comment** |
| 10 hàm cấp module của `auto_clicker_gui.py` | 100% theme/cửa sổ, **không hàm logic nào lọt ra** |
| Python / Tcl-Tk / Pillow | 3.14.2 / **8.6.15** / 12.1.1 |
| `pip install pywebview` (Python 3.14) | ✅ **pywebview 6.2.1, 8.9 giây, KHÔNG biên dịch** |
| WebView2 Runtime | ✅ **có sẵn, 151.0.4129.59** |
| Node / npm | ✅ **v20.19.0 / 10.8.2, đã cài sẵn** |
| Cửa sổ webview mở + **Python → JS** | ✅ `evaluate_js` trả về đúng |
| **JS → Python** (`js_api`) | ✅ trả về JSON có cấu trúc |
| Tiếng Việt có dấu + `⇧` qua cầu nối | ✅ `"Rẽ nhánh — Kiểm tra mod ⇧"` nguyên vẹn |
| Khởi động Python + mở WebView2 + đóng | ~0.6s (tổng 3.1s trừ 2.5s sleep của phép đo) |

**Bẫy đã né:** `proxy-tools` (dep của pywebview) **chỉ có sdist, không có wheel**.
Kiểm bằng `--only-binary=:all:` trước để pip **không** âm thầm biên dịch — đúng bài học
`winsdk` cp314 đã từng chạy nhiều phút rồi phải giết. Kết quả: proxy-tools là Python
thuần, build tức thì, không phải bẫy.

**Ba giả định lớn nhất đều đã xanh.** Rủi ro còn lại không phải kỹ thuật.

### ⚠ PHẢI dùng venv riêng — không phải chuyện sạch sẽ, mà là chuyện chạy được

pywebview **chết ngay lúc khởi động** trong Python global của máy này:

```
System.IO.FileNotFoundException: Could not load file or assembly 'Microsoft'
  ...\site-packages\Microsoft\__init__.py line 28  ->  AddReference("Microsoft")
```

Thủ phạm: gói **`quantconnect-stubs`** (stubs của nền tảng giao dịch QuantConnect, cài
23/03, **không liên quan gì tới dự án này**) tạo thư mục `site-packages/Microsoft/` che
mất namespace động mà pythonnet dựng lúc chạy — trong khi backend WinForms của pywebview
cần đúng `from Microsoft.Win32 import SystemEvents`.

**Không gỡ gói của người dùng.** Cách xử lý là `.venv` riêng cho dự án (đã tạo, cài
8.7 giây, `Microsoft/` không tồn tại trong đó). Lợi ích kèm theo: build exe từ môi trường
sạch, PyInstaller không vô tình gói lẫn thứ không liên quan.

Chạy mọi thứ bằng `.venv\Scripts\python.exe`. Bộ test cũ: **486/486 xanh trong venv mới.**

---

## 3. Stack

| Tầng | Chọn | Lý do |
|---|---|---|
| Vỏ desktop | **pywebview 6.2.1** | Python là tiến trình chính (engine, hotkey, chụp màn hình, OCR, clipboard đều Python); mượn WebView2 sẵn có nên exe không phình |
| Giao diện | **React + TypeScript + Vite** | Hộp Loop phải là thẻ HTML co giãn theo nội dung |
| Đồ thị | **React Flow (xyflow)** | Node = component HTML; 4 cổng ở 4 cạnh có sẵn; kéo/nối/pan/zoom/chọn nhiều đã được làm mượt sẵn |
| Màu | **CSS thuần + biến `--var`** | Dark trước, light sau = thêm một khối biến. Không Tailwind |
| Trạng thái + Ctrl+Z | **Zustand + chụp ảnh trạng thái** | Đồ thị là JSON nhỏ → lưu nguyên trạng thái mỗi lần đổi. Không cần diff thông minh, cũng không sai bao giờ |
| Engine | **`core.py` GIỮ NGUYÊN** | Đã chạy thật, 271 check engine xanh |
| 3 overlay toàn màn hình | **tkinter, copy nguyên xi, tiến trình con** | Webview không làm nổi cửa sổ trong suốt phủ lên game |

**KHÔNG chọn:** Qt/PySide6 (exe 45–70MB, và node phải là `QGraphicsProxyWidget` mới
có nội dung dạng thẻ — vụng), Electron (>100MB), Tauri (kéo Rust vào dự án Python thuần),
tkinter Canvas (Tk 8.6.15 **không khử răng cưa** — đo được, không phải cảm tính).

---

## 4. Kiến trúc — ranh giới Python ↔ JS

```
   React UI  ──►  api.py  ──►  core.py
   (TypeScript)   (mới)        (KHÔNG ĐỔI)
```

**`api.py` là bề mặt DUY NHẤT** JS được gọi. Nó `import core`, không biết gì về giao diện.

- `load_process` / `save_process` / `list_templates` / `validate` / `get_mods` / `get_settings`
- `run` (bật thread rồi trả về ngay) / `stop`
- `pick_point` / `pick_abyss_frame` / `pick_inv_grid` → bật tiến trình con tkinter
- Nhật ký + trạng thái chảy ngược về JS bằng `evaluate_js`

### Luật cứng

1. **JS không bao giờ tự biết định dạng file.** Chỉ gửi/nhận JSON và hỏi `api.py`.
   Một nơi biết một thứ.
2. **`core.py` không được sửa vì lý do giao diện.** Nếu thấy cần sửa → dừng lại, xem có
   phải đang để logic rò ra ngoài không.
3. **`api.py` phải test được bằng Python.** Đây là cách lấy lại phần lớn số test giao
   diện sẽ mất.

### Vết vá phải làm trước

`core.py` có `make_loop_template()` và `make_group_template()` nhưng **thiếu
`make_process_template()`** — định dạng file Process đang ráp trong GUI tại
`auto_clicker_gui.py:2785` (`template_data`, hardcode `schema:3, type:"process"`),
cùng với `flow_data()`. **~15 dòng, chuyển sang `core.py` ở P1.** Không làm thì frontend
mới sẽ chép lại kiến thức về định dạng file → hai nơi cùng biết một thứ.

---

## 5. Ba overlay toàn màn hình — giữ nguyên xi

`PointSelector` (crosshair), `AbyssFrameSelector` (căn khung Abyss),
`InvGridSelector` (căn lưới inventory) — là cửa sổ trong suốt phủ lên cửa sổ game,
bắt click và đọc pixel. Webview làm chỗ này rất bấp bênh.

**Cách làm:** web bấm "Chọn điểm" → `api.py` bật một tiến trình con chạy đúng class
tkinter hiện tại → nó in toạ độ ra stdout dạng JSON → tắt. Không xung đột vòng lặp sự
kiện, cách ly luôn được lỗi.

> Nghịch lý dễ chịu: **đúng 3 thứ người dùng khen nhất lại là 3 thứ không bị đụng tới.**

---

## 6. Đánh giá 5 yếu tố

| Yếu tố | tkinter Canvas | Qt / PySide6 | **Web (chọn)** |
|---|---|---|---|
| **Vẽ đồ thị** | tự viết 100%: kéo, nối, zoom, undo, chọn nhiều | `QGraphicsView` giúp nhiều, nhưng node dạng thẻ phải nhúng widget — vụng | **React Flow lo hết**; node là component HTML |
| **Thẩm mỹ** | trần thấp — **Tk 8.6.15 không khử răng cưa (đo)**; không bo góc, không đổ bóng | cao, khử răng cưa sẵn | **cao nhất** — CSS thật, chính là công nghệ của VSCode/GitHub |
| **Mượt** | đủ ở 20–80 khối; **zoom phải vẽ lại tay** | rất mượt | **rất mượt** — Chromium, GPU compositing; mở cửa sổ ~0.6s (đo) |
| **Độ nặng** | 13MB, không đổi — **tốt nhất** | 45–70MB — xấu | ~18–20MB *(ước tính, chưa đo PyInstaller)* |
| **Chuyên nghiệp** | "gọn gàng", không phải "chuyên nghiệp" | cao | **cao nhất** |
| **Phải viết lại** | 1 vùng | 100% giao diện | 100% giao diện + thêm ngôn ngữ |

**Vì sao Web thắng dù phải viết lại nhiều nhất:** yêu cầu *"kích thước box phải design để
hiểu Loop này chạy những gì"* bắt hộp phải là **thẻ HTML co giãn theo nội dung**.
Mọi lựa chọn vẽ-trên-canvas đều bắt tự vẽ chữ bằng tay — tức là **trả giá của Web mà nhận
kết quả của tkinter**.

**Một lợi ích không hiển nhiên:** pywebview bật `debug=True` cho **DevTools Chromium đầy
đủ**. Dự án này từng phải *lấy mẫu pixel trên ảnh chụp màn hình* để kiểm màu có đúng
không. Từ giờ chỉ cần Inspect. **Việc gỡ lỗi giao diện tốt lên chứ không xấu đi.**

---

## 7. Rủi ro và cách chặn

| Rủi ro | Mức | Cách chặn |
|---|---|---|
| **Mất ~215 check giao diện tkinter** | **Cao** | Chúng biến mất hẳn, không phải "viết lại". Bù bằng test `api.py` bằng Python — phần lớn cái chúng kiểm là *hành vi dữ liệu* lái qua giao diện, diễn đạt lại được. Ước lượng lấy lại ~60–70% *giá trị*; mất hẳn lớp tương tác (kéo, click, grab) cho tới khi thêm Playwright (để sau) |
| **Phình phạm vi** — node editor mời gọi đánh bóng vô tận | Cao | Chốt phạm vi v1 ở §9. Ngoài danh sách đó = ghi lại, không làm |
| **Không hợp gu** | Trung bình | P1 dựng vỏ với **dữ liệu thật** và cho xem TRƯỚC khi làm 7 hộp thoại ở P2. Đã trượt 2 lần vì đoán gu (mockup GitHub "xấu quá", CustomTkinter "lỗi rất nhiều") |
| **AV báo nhầm trên exe hình dạng mới** | Trung bình | Chưa đo. Quét bằng `Start-MpScan` ở P3. **Giữ `--onedir`, tuyệt đối không quay lại `--onefile`** |
| **Overlay chạy tiến trình con** | Thấp | Đã quyết cách làm, chứng minh ở P0 |
| **Gỡ lỗi 2 runtime** | Thấp | DevTools bù thừa |
| **Thiếu WebView2 trên máy khác** | Thấp | Đã có sẵn trên máy này; kiểm lúc khởi động và báo rõ nếu thiếu |

---

## 8. Lộ trình

App tkinter cũ **chạy được suốt P0–P3**. Đây là điều lần trước không có.

- **P0 — Thăm dò** ✅ **XONG**
  - ✅ pywebview trên Python 3.14, WebView2, node/npm, cầu nối 2 chiều
  - ✅ `.venv` riêng (né xung đột `quantconnect-stubs`); test cũ 486/486 xanh
  - ✅ `overlays.py` — 3 overlay tkinter chạy dạng tiến trình con, **10/10 kiểm tra**:
    trả đúng toạ độ, Esc = huỷ (khác lỗi), tham số hỏng vẫn ra JSON sạch
  - ✅ `api.py` → `core.py`: 8 loại hành động, 3223 mod, `validate_process` dùng chung
  - ✅ `app_web.py` + `webui/p0_probe.html`: cửa sổ mở, giao diện tối render đúng
  - **Số đo:** mở cửa sổ + bootstrap xong **0,62s** · 1 lần gọi API **6ms** ·
    **3223 mod (~130KB) qua cầu nối 7ms** → xác nhận quyết định gửi cả danh sách một
    lần rồi lọc trong JS, thay vì lọc ở Python theo từng phím gõ như bản tkinter
    (bản cũ phải đặt trần hiển thị 150 dòng, bản web bỏ được trần đó)
- **P1 — Vỏ giao diện thật** ✅ **XONG — xem và chê ở đây**
  - ✅ core: `new_step_id`/`ensure_step_ids` (id bền), `pos` (toạ độ hộp),
    `default_edges`/`clean_edges` (đường nối), `make_process_template` **đã chuyển từ
    GUI về core** — giao diện tkinter cũ giờ gọi chung hàm đó
  - ✅ **File cũ không cần di cư**: thiếu khoá `edges` = chuỗi thẳng 1→2→3, đúng thứ
    tự nó vẫn chạy. Thiếu `id` thì được cấp lúc mở
  - ✅ `api.py`: `new_step` / `describe` / `save_process` / `load_process` /
    `demo_process` / `validate`. **Nội dung hộp do Python sinh** bằng chính
    `core.action_display` mà bản tkinter dùng → hai giao diện không thể mô tả khác nhau
  - ✅ React + TS + Vite + React Flow: ribbon 5 nhóm kiểu Paint, canvas, hộp co theo
    nội dung, 4 cổng mỗi cạnh, Ctrl+Z/Y/D/S, F2, Delete, tab Vấn đề + Nhật ký,
    thanh trạng thái, thanh tiêu đề tối (DwmSetWindowAttribute + EnumWindows)
  - ✅ Bộ test mới `test_do_thi_va_api.py` (44) — chạy bằng Python thuần, không mở cửa
    sổ. **Tổng: 530 check / 14 bài, tất cả xanh.** Test cũ không vỡ cái nào
  - **Số đo:** build 1,1s · gói ra 342KB JS (110KB gzip) + 23KB CSS
  - **Lỗi test bắt được (đáng ghi lại):** `core.list_templates()` trả tuple
    `(tên, đường_dẫn)` chứ không phải tên — trả thẳng sang JS là vừa sai kiểu vừa lộ
    đường dẫn đĩa; và `new_step("action")` tạo hành động thiếu `point` làm
    `action_summary` nổ `KeyError`. Cả hai lọt qua mắt, chỉ test mới thấy
- **P2 — Hộp thoại** ✅ **XONG**
  - ✅ **`core.build_action(draft)` — luật hợp lệ của 8 loại hành động đã rút khỏi
    `ActionEditor._save` về core.** Hộp thoại tkinter giờ chỉ còn đọc form rồi gọi hàm
    đó; hộp thoại web gọi đúng hàm đó qua `api.save_action`. Sửa luật một chỗ, hai
    giao diện đổi theo
  - ✅ `ActionDialog` (8 loại) + `StepDialog` (Loop/Nhóm) dựng lại đúng thứ tự trường,
    chữ nhãn và chữ gợi ý của bản tkinter. Double-click hộp trên canvas để mở
  - ✅ Ba overlay nối vào: 🎯 Chọn điểm · 🖼 Căn khung Abyss · 🖼 Căn lưới
  - ✅ Mô tả hành động và mô tả điều kiện đều do Python sinh
    (`action_display` / `cond_display` / `abyss_cond_display`)
  - ✅ Bộ test §8 cho `build_action`: 8 loại hợp lệ + 12 đường lỗi.
    **Tổng: 558 check / 14 bài, tất cả xanh**
  - **Hai lớp lỗi của bản tkinter biến mất theo kiến trúc**, không phải nhờ sửa:
    hộp thoại "loé" lúc mở (web dựng xong mới vẽ) và `ttk.Combobox` chiếm grab toàn
    cục làm treo cả máy (web không có khái niệm grab)
- **P3 — Chạy/Dừng + nhật ký + đóng gói** ✅ **XONG — app dùng được thật**
  - ✅ `api.run()` chạy `ProcessRunner` trong luồng riêng và **trả về NGAY**. Chờ chạy
    xong mới trả về thì cầu nối bị khoá, cả giao diện đứng hình suốt lúc chạy (có thể
    hàng giờ) — kể cả nút Dừng
  - ✅ Nhật ký đẩy sang JS **theo lô 150ms**. Mỗi `evaluate_js` là một vòng IPC; một
    vòng lặp nhanh sinh hàng chục dòng/giây, đẩy từng dòng sẽ ngốn hết luồng giao diện
    (bản tkinter cũng phải gom lô y hệt bằng `root.after`)
  - ✅ Phím dừng toàn cục đăng ký **hai kiểu** như bản cũ: `add_hotkey` khớp đúng tổ
    hợp, cộng `on_press_key` bắt theo scan code — vì khi Loop đang giữ Shift thì F6 bị
    hiểu là Shift+F6 và không khớp, hỏng đúng lúc cần dừng nhất
  - ✅ Lỗi thì chặn, cảnh báo thì **hỏi lại** (không tự quyết hộ người dùng)
  - ✅ Đóng cửa sổ giữa lúc chạy (`events.closing`) → dừng worker, thả phím đang giữ,
    gỡ hotkey. Không có bước này thì Shift kẹt trong cả Windows sau khi tắt app
  - ✅ `tools/build_web.bat` + đã build thật: **44MB thư mục**, 27s
  - ✅ **Kiểm chứng trên chính file .exe**, không suy từ bản chạy nguồn: cửa sổ mở
    trong 0,8s · 98% điểm ảnh tối (không trắng bóc) · đường `--overlay` trả đúng toạ độ
  - ✅ **Quét Windows Defender: 0 phát hiện mới, exe còn nguyên.** Giữ `--onedir`
  - ✅ Bộ test mới `test_chay_web.py` (24) — Process chỉ gồm `delay` nên không đụng
    chuột thật, vẫn chạy bộ máy thật. **Tổng: 582 check / 15 bài, tất cả xanh**
  - **Đo được:** overlay sẵn sàng ~1s ở CẢ bản nguồn lẫn bản đóng gói — không có độ
    trễ nào do tách tiến trình
- **P3.5 — Đuổi kịp bản tkinter** ✅ **XONG** (sinh ra sau một cuộc audit thất bại)
  - ✅ **Bộ máy chạy theo ĐƯỜNG NỐI.** Trước đó `_run_inner` duyệt
    `enumerate(steps)` và chưa từng đọc `edges` → canvas vẽ C→A→B mà app chạy A→B→C.
    Đã tách `_chay_mot_buoc()` ra khỏi vòng duyệt, thêm `flow_map` / `flow_entry` /
    `flow_order` / `validate_flow_graph` + `MAX_PROCESS_STEPS` chặn vòng vô tận
  - ✅ **Số thứ tự chạy ở góc khối**, tính bằng CHÍNH `flow_order` mà bộ máy dùng —
    con số không thể nói khác việc app làm. Khối không có đường dẫn tới hiện viền
    đứt + dấu `–`
  - ✅ Soát đồ thị: 2 đường ra cùng cổng (lỗi) · không có bước bắt đầu (lỗi) ·
    bước không bao giờ chạy tới (cảnh báo)
  - ✅ ⚙ Cài đặt (game, delay, phím copy, phím dừng, màu nhấn đổi-là-thấy-ngay,
    ⟳ cập nhật mod từ mạng)
  - ✅ 💾 Lưu ▾ / 📂 Mở ▾ đầy đủ + `TemplatePicker` — thay hết `window.prompt`
  - ✅ 👁 Xem điểm (thêm mode `review` cho `overlays.py`, dùng lại `ReviewOverlay`)
  - ✅ Chọn nhiều + Ctrl+C/Ctrl+V + kéo-thả trong bảng hành động; bấm dòng ⚠ Vấn đề
    để nhảy tới khối
  - **Tổng: 596 check / 15 bài, tất cả xanh**
  - **Lỗi test bắt được:** bước thiếu `id` bị phép duyệt đồ thị bỏ qua → Process
    **im lặng không chạy gì**. Đã vá bằng `ensure_step_ids` ngay trước khi duyệt
  - **Ghi chú Ctrl+C/V**: dùng bộ nhớ trong app, KHÔNG dùng clipboard hệ điều hành —
    clipboard thật đang phục vụ luồng đọc chữ item, trộn vào là có ngày dán nhầm cả
    một item PoE vào danh sách hành động

- **P4 — Audit + Dọn dẹp** ✅ **XONG**
  - ✅ **Sửa lỗi "Not Responding"** — app mở ra là treo, không traceback, 0% CPU.
    Nguyên nhân: `api.window = <Window>`. pywebview dựng danh sách hàm cho JS bằng
    `get_functions()` (`webview/util.py:190`) — nó duyệt `dir(js_api)` và **đệ quy vào
    mọi thuộc tính không callable**; chạm vào `Window` là đọc các property
    `width`/`x`/`title`, những thứ hỏi ngược luồng giao diện đang bị chặn để chờ →
    deadlock. Luật mới: **mọi thuộc tính không-phải-hàm của `Api` phải có tiền tố `_`**
  - ✅ **Checklist UI/UX 36 mục đối chiếu bản tkinter → đủ 36/36.** 7 mục thiếu đã bổ
    sung: nút Sửa · Đặt làm bước bắt đầu · Lưu ra file khác · Mở từ file khác ·
    Duyệt file khác · phím Delete ở bảng điều kiện · kéo-thả điều kiện
  - ✅ **`tests/test_e2e_web.py`** — mở app THẬT, thao tác THẬT, sau mỗi bước hỏi
    Windows `SendMessageTimeout(WM_NULL)` xem cửa sổ còn bơm thông điệp không.
    **Đã mutation-test**: tái hiện lỗi cũ thì bài này đỏ 8 chỗ
  - ✅ **Dọn**: `auto_clicker_gui.py` (3142 dòng) → tách 846 dòng còn dùng thành
    `overlay_ui.py` (4 overlay + theme), xoá phần còn lại. Xoá 7 bộ test chỉ phục vụ
    giao diện đã mất; 4 bộ khác cắt riêng phần giao diện, giữ nguyên phần lõi.
    Xoá `p0_probe.html`, 3 file `.spec`, zip cũ, `tools/build.bat` của bản tkinter.
    Ảnh mẫu về `tests/anh/`
  - **Test: 325 check / 9 bài (nhóm an toàn) + 22 check / 2 bài chuột thật.** Tất cả xanh
  - **Đóng gói: 41MB, Defender quét sạch**

- **Tiếp theo — Theme sáng**, rồi **rẽ nhánh check_mod**

---

## 9. Phạm vi v1

**Có:** thêm/xoá/di chuyển khối · nối/gỡ đường · 4 cổng mỗi khối · double-click mở hộp
thoại · chuột phải ra menu · pan/zoom · Ctrl+Z/Ctrl+Y · chọn nhiều · Ctrl+C/V ·
bảng ⚠ Vấn đề · 📋 Nhật ký · lưu/mở template · Chạy/Dừng · theme tối

**Không (ghi lại, làm sau):** minimap · tự sắp xếp bố cục · hộp thoại tìm kiếm ·
chạy từng bước / debug · nhiều tab Process · lịch sử hoàn tác có tên · theme sáng (P4) ·
kiểm thử giao diện bằng Playwright

---

## 10. Nguyên tắc bất di bất dịch

1. **Không sửa `core.py` vì lý do giao diện.**
2. **App cũ vẫn chạy được cho tới hết P3.**
3. **Giữ `--onedir`** khi đóng gói. Không bao giờ quay lại `--onefile`.
4. **Đo, đừng đoán** — kích thước exe, thời gian khởi động, kết quả quét AV đều phải
   có số thật trước khi kết luận.
5. **Bản nháp chính là sản phẩm.** Với web thì file HTML vẽ ra để xem chính là giao diện
   sẽ chạy — không có công nào bị phí.
