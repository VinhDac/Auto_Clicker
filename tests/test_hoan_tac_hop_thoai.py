"""Ctrl+Z bên trong hộp thoại sửa Loop / sửa Nhóm.

VÌ SAO PHẢI CÓ BÀI NÀY
----------------------
Canvas đã có Ctrl+Z từ lâu, nhưng vào hộp thoại sửa hành động thì lỡ tay xoá là mất
luôn. Thêm ngăn hoàn tác RIÊNG cho hộp thoại, và chỗ dễ sai nhất là ranh giới giữa
hai ngăn:

  - Ctrl+Z trong hộp thoại KHÔNG được đụng tới khối ngoài canvas. Đã từng có đúng
    lỗi kiểu này với phím Delete: bấm Delete trong hộp thoại vừa xoá hành động vừa
    xoá luôn cả khối phía sau.
  - Ctrl+Z khi con trỏ đang nằm trong ô nhập chữ phải để nguyên cho trình duyệt lo
    (hoàn tác từng đoạn chữ), chứ không được nhảy vào hoàn tác việc xoá hành động.

Bài này bắn sự kiện thẳng vào DOM nên không giành chuột của người đang ngồi máy.
Process mẫu có sẵn 3 khối: Loop 5 hành động, Nhóm 2 hành động, HĐ lẻ.
"""
import _boot  # noqa: F401
import _web

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANG = os.path.join(REPO, "webui", "dist", "index.html")

JS_TIEN_ICH = r"""
window.__D = {
  ban(el, ten){ el.dispatchEvent(new MouseEvent(ten, {bubbles:true, cancelable:true,
      view:window, button:0, detail: ten==='dblclick'?2:1})) },
  phim(el, key, opt){ el.dispatchEvent(new KeyboardEvent('keydown',
      Object.assign({key, bubbles:true, cancelable:true}, opt||{}))) },
  ctrlZ(el){ this.phim(el||window, 'z', {ctrlKey:true}) },
  ctrlY(el){ this.phim(el||window, 'y', {ctrlKey:true}) },
  mucs(){ return [...document.querySelectorAll('.lop-phu .danh-sach .muc')] },
  chu(){ return this.mucs().map(m => m.textContent.trim()) },
  nut(t){ return [...document.querySelectorAll('.lop-phu .nut')]
            .find(b => b.textContent.trim().includes(t)) },
  tieuDe(){ const e = document.querySelector('.lop-phu .ht-dau span'); return e ? e.textContent : '' },
  moKhoi(i){ this.ban(document.querySelectorAll('.react-flow__node')[i], 'dblclick') },
  soKhoi(){ return document.querySelectorAll('.react-flow__node').length },
}
'san sang'
"""

dung = sai = 0


def kiem(ten, dk, chi_tiet=""):
    global dung, sai
    if dk:
        dung += 1
        print(f"  ✔ {ten} {chi_tiet}")
    else:
        sai += 1
        print(f"  ✘ {ten} {chi_tiet}")


def main():
    global sai
    if not os.path.exists(TRANG):
        print("  ✘ chưa có webui/dist — chạy `npm run build` trong webui/ trước")
        sys.exit(1)

    import webview
    from api import Api

    api = Api()
    win = webview.create_window("Auto Clicker", url=TRANG, js_api=api,
                                width=1280, height=860)
    api._window = win
    ghi = []

    def js(s):
        return win.evaluate_js(s)

    def cho_ds():
        """Danh sách vẽ lại sau khi Python mô tả xong hành động -> phải chờ vòng gọi."""
        time.sleep(0.6)

    def than():
        try:
            _web.cho_san_sang(js)
            _web.mo_mau(js)
            time.sleep(1.2)
            js(JS_TIEN_ICH)
            khoi_dau = js("window.__D.soKhoi()")
            ghi.append(("process mẫu dựng đủ khối", khoi_dau == 3, f"— {khoi_dau} khối"))

            for chi_so, ten_hop, nhan in [(0, "Sửa Action_Loop", "Loop"),
                                          (1, "Sửa Nhóm HĐ 1 lần", "Nhóm")]:
                js(f"window.__D.moKhoi({chi_so})")
                cho_ds()
                ghi.append((f"[{nhan}] mở đúng hộp thoại",
                            js("window.__D.tieuDe()") == ten_hop,
                            f"— '{js('window.__D.tieuDe()')}'"))
                dau = js("window.__D.chu()")
                n0 = len(dau)
                ghi.append((f"[{nhan}] có sẵn hành động để thử", n0 >= 2, f"— {n0} hành động"))

                # --- xoá 1 hành động rồi hoàn tác ---
                js("window.__D.ban(window.__D.mucs()[0], 'click')")
                time.sleep(0.2)
                js("window.__D.phim(window, 'Delete')")
                cho_ds()
                ghi.append((f"[{nhan}] Del xoá được 1 hành động",
                            len(js("window.__D.chu()")) == n0 - 1,
                            f"— {n0} → {len(js('window.__D.chu()'))}"))
                js("window.__D.ctrlZ()")
                cho_ds()
                ghi.append((f"[{nhan}] Ctrl+Z lấy lại hành động vừa xoá",
                            js("window.__D.chu()") == dau))
                js("window.__D.ctrlY()")
                cho_ds()
                ghi.append((f"[{nhan}] Ctrl+Y xoá lại",
                            len(js("window.__D.chu()")) == n0 - 1))
                js("window.__D.ctrlZ()")
                cho_ds()
                ghi.append((f"[{nhan}] Ctrl+Z lần nữa vẫn đúng",
                            js("window.__D.chu()") == dau))

                # --- xếp lại thứ tự rồi hoàn tác ---
                js("window.__D.ban(window.__D.mucs()[0], 'click')")
                time.sleep(0.2)
                js("window.__D.ban(window.__D.nut('Xuống'), 'click')")
                cho_ds()
                doi = js("window.__D.chu()")
                ghi.append((f"[{nhan}] nút Xuống đổi được thứ tự", doi != dau))
                js("window.__D.ctrlZ()")
                cho_ds()
                ghi.append((f"[{nhan}] Ctrl+Z trả lại thứ tự cũ",
                            js("window.__D.chu()") == dau))

                # --- ranh giới 1: đang gõ trong ô nhập thì nhường cho trình duyệt ---
                js("window.__D.ban(window.__D.mucs()[0], 'click')")
                time.sleep(0.2)
                js("window.__D.phim(window, 'Delete')")
                cho_ds()
                bot = js("window.__D.chu()")
                js("(()=>{const o=document.querySelector('.lop-phu input.o');"
                   "o.focus(); window.__D.ctrlZ(o)})()")
                cho_ds()
                ghi.append((f"[{nhan}] Ctrl+Z trong ô nhập KHÔNG đụng danh sách",
                            js("window.__D.chu()") == bot))
                js("window.__D.ctrlZ()")     # ra ngoài ô nhập thì mới hoàn tác
                cho_ds()
                ghi.append((f"[{nhan}] ra khỏi ô nhập thì Ctrl+Z chạy lại bình thường",
                            js("window.__D.chu()") == dau))

                # --- ranh giới 2: không được đụng tới khối ngoài canvas ---
                ghi.append((f"[{nhan}] Ctrl+Z trong hộp thoại KHÔNG xoá khối ngoài canvas",
                            js("window.__D.soKhoi()") == khoi_dau,
                            f"— vẫn {js('window.__D.soKhoi()')} khối"))

                # Huỷ để không mang thay đổi ra canvas, rồi sang khối sau.
                js("window.__D.ban(window.__D.nut('Huỷ'), 'click')")
                time.sleep(0.5)
                ghi.append((f"[{nhan}] bấm Huỷ thì đóng hộp thoại",
                            js("document.querySelectorAll('.lop-phu').length") == 0))
        except Exception:
            import traceback
            ghi.append(("chạy được tới cuối", False, "\n" + traceback.format_exc(limit=4)))
        finally:
            win.destroy()

    webview.start(than, debug=False, http_server=True)

    for m in ghi:
        kiem(m[0], m[1], m[2] if len(m) > 2 else "")
    if not ghi:
        print("  ✘ không thu được kết quả nào (cửa sổ không mở?)")
        sai += 1

    print(f"\n✔ KẾT QUẢ: {dung} đúng / {sai} sai")
    sys.exit(0 if sai == 0 else 1)


if __name__ == "__main__":
    main()
