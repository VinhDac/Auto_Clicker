"""Tiện ích dùng chung cho mọi bài test mở cửa sổ web.

Từ khi app khởi động ra KHUNG TRẮNG (Process mẫu không còn tự hiện), hai việc sau
lặp lại ở mọi bài — gom về một chỗ để 7 bài không trôi mỗi nơi một kiểu:

  · chờ app SẴN SÀNG. Không chờ ".hop" được nữa: canvas trống thì nó không bao giờ
    xuất hiện và bài test treo tới hết giờ rồi mới chạy tiếp với 0 khối. Dấu hiệu
    đúng là ".hop HOẶC .trong-rong" — cái sau chỉ hiện khi đã bootstrap xong mà
    canvas rỗng, nên hai cái phủ kín đủ hai trường hợp.

  · mở Process mẫu làm dữ liệu thử (3 khối, 2 dây, đủ Loop/Nhóm/HĐ lẻ).
"""

JS_CHUNG = r"""
window.__W = {
  sanSang(){ return !!document.querySelector('.hop, .trong-rong') },
  /* Mở menu xổ xuống của ribbon ("Lưu ▾" / "Mở ▾") rồi chọn một mục.
     PHẢI tách làm hai nhịp có nghỉ ở giữa: bấm nút chỉ `setMo(true)`, mà React cập
     nhật state bất đồng bộ — tìm `.muc-menu` ngay trong cùng một lần chạy JS thì nó
     còn chưa tồn tại. */
  moMenu(tenNut){
    const b = [...document.querySelectorAll('.ribbon .nut-lon')]
      .find(x => x.textContent.trim().startsWith(tenNut))
    if (!b) return 'khong thay nut: ' + tenNut
    b.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window}))
    return 'ok'
  },
  chonMuc(tenMuc){
    const m = [...document.querySelectorAll('.ribbon .muc-menu')]
      .find(x => x.textContent.trim().startsWith(tenMuc))
    if (!m) return 'khong thay muc: ' + tenMuc
    m.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window}))
    return 'ok'
  },
  soKhoi(){ return document.querySelectorAll('.react-flow__node').length },
}
'san sang'
"""


def man_hinh_dung_duoc():
    """(dùng_được, lý_do) — phiên Windows này có desktop tương tác không?

    Máy KHOÁ MÀN HÌNH thì `GetSystemMetrics` trả 640x480 và `SetCursorPos` không đi
    đâu cả (`GetCursorPos` luôn ra 0,0). Mọi bài điều khiển chuột sẽ đỏ toàn tập với
    những con số vô nghĩa — đã mất công truy oan sang tính năng cửa sổ vì chuyện này.
    Thà BỎ QUA và nói rõ, còn hơn báo đỏ một thứ không hỏng."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    w, h = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    if w < 800 or h < 600:
        return False, f"màn hình báo {w}x{h} — phiên không có desktop tương tác (máy đang khoá?)"
    u.SetCursorPos(int(w // 2), int(h // 2))
    p = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(p))
    if abs(p.x - w // 2) > 5 or abs(p.y - h // 2) > 5:
        return False, f"đặt con trỏ vào giữa màn hình nhưng nó nằm ở ({p.x},{p.y}) — không điều khiển được chuột"
    return True, ""


def bo_qua_neu_khoa_man_hinh():
    """Gọi ở ĐẦU mọi bài dùng chuột thật. Thoát êm (mã 0) nếu không đo được."""
    import sys
    ok, ly_do = man_hinh_dung_duoc()
    if not ok:
        print(f"  ⊘ BỎ QUA — {ly_do}")
        print("\n✔ KẾT QUẢ: 0 đúng / 0 sai   (không chạy được, không phải lỗi)")
        sys.exit(0)


def cho_san_sang(js, giay=14.0):
    """Chờ app bootstrap xong. Trả True nếu kịp."""
    import time
    for _ in range(int(giay / 0.15)):
        time.sleep(0.15)
        if js("!!document.querySelector('.hop, .trong-rong')"):
            return True
    return False


def mo_mau(js, giay=6.0):
    """Nạp Process mẫu (3 khối, 2 dây) làm dữ liệu thử. Trả số khối nạp được."""
    import time
    js(JS_CHUNG)
    js("window.__W.moMenu('Mở')")
    time.sleep(0.4)
    js("window.__W.chonMuc('Process mẫu')")
    for _ in range(int(giay / 0.15)):
        time.sleep(0.15)
        if js("window.__W.soKhoi()") >= 3:
            break
    time.sleep(0.6)
    return js("window.__W.soKhoi()")
