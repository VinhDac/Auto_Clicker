"""Ghi phím bằng cách BẤM PHÍM THẬT, thay vì bắt người dùng gõ tên phím ra.

Cái bẫy chính: mấy phím hay ghi nhất lại đúng là mấy phím đã có nghĩa sẵn trong app.
Escape đóng hộp thoại, Tab nhảy ô, Enter bấm nút mặc định. Nếu không chặn thì bấm Esc
để ghi sẽ đóng luôn hộp thoại — và "escape" là phím KHÔNG BAO GIỜ ghi được, trong khi
nó chính là phím hay dùng nhất trong PoE (đóng panel).

Escape còn một lớp nữa: listener của `Modal` gắn `capture:true` trên window ngay từ
lúc mở, nên nó luôn chạy TRƯỚC listener của ô ghi phím (đăng ký sau). Không thể chặn
từ phía ô ghi được — phải khoá thẳng ở Modal.

Phép quy đổi tên phím nằm ở `core.key_from_browser`, không ở JS: thứ chạy được hay
không là do pyautogui quyết, mà chỉ Python nhìn thấy nó.

Bắn sự kiện thẳng vào DOM, không đụng chuột thật -> nhóm AN_TOAN.
"""
import _boot  # noqa: F401
import _web

import os
import sys
import time

import core

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANG = os.path.join(REPO, "webui", "dist", "index.html")

JS_TIEN_ICH = r"""
window.__P = {
  bam(el){ el.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true,
      view:window, button:0})) },
  nutRibbon(t){ return [...document.querySelectorAll('.ribbon .nut-lon')]
                  .find(b => b.textContent.trim() === t) },
  // Nút Cài đặt nằm ở góc trái DƯỚI, không phải trên ribbon.
  nutCaiDat(){ return [...document.querySelectorAll('.nut-tt')]
                 .find(b => (b.getAttribute('title')||'') === 'Cài đặt') },
  nutHt(t){ return [...document.querySelectorAll('.lop-phu .nut')]
              .find(b => b.textContent.trim().includes(t)) },
  chonLoai(v){
    const s = document.querySelector('.lop-phu select.day')
    const dat = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set
    dat.call(s, v)
    s.dispatchEvent(new Event('change', {bubbles:true}))
  },
  // PHẢI nhắm theo nhãn: ô đầu tiên trong hộp thoại là "Tên:", không phải "Phím:".
  // Lấy `querySelector('input.o')` là đọc nhầm ô Tên — và phép thử sẽ xanh một cách
  // giả tạo vì ghi vào ô nào rồi đọc lại ô đó thì luôn khớp.
  oTheoNhan(nhan){
    const l = [...document.querySelectorAll('.lop-phu .nhan-o')]
      .find(e => e.textContent.trim().startsWith(nhan))
    return l ? l.parentElement.querySelector('input.o') : null
  },
  oPhim(){ return this.oTheoNhan('Phím:') },
  oDung(){ return this.oTheoNhan('Phím dừng') },
  triDung(){ const o = this.oDung(); return o ? o.value : '(khong co o)' },
  giaTri(){ const o = this.oPhim(); return o ? o.value : '(khong co o)' },
  phim(k, code){
    window.dispatchEvent(new KeyboardEvent('keydown',
      {key:k, code:code||'', bubbles:true, cancelable:true}))
  },
  moHt(){ return document.querySelectorAll('.lop-phu').length > 0 },
  goiY(){ return [...document.querySelectorAll('.lop-phu .goi-y')]
            .map(e => e.textContent.trim()).join(' | ') },
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


# ---------------- phần thuần logic: bảng quy đổi ----------------
print("▸ Quy đổi tên phím (core)")
for kb, code, mong in [("Escape", "", "escape"), ("a", "KeyA", "a"), ("A", "KeyA", "a"),
                       (" ", "Space", "space"), ("ArrowUp", "", "up"),
                       ("F5", "F5", "f5"), ("Enter", "NumpadEnter", "enter"),
                       ("Control", "", "ctrl"), ("Delete", "", "delete"),
                       ("PageDown", "", "pagedown")]:
    ten, loi = core.key_from_browser(kb, code)
    kiem(f'"{kb}" → {mong}', ten == mong and loi is None, f"— ra {ten!r}")

# Numpad phải phân biệt được với phím số hàng trên: `key` của hai bên trùng hệt nhau.
t1, _ = core.key_from_browser("1", "Digit1")
t2, _ = core.key_from_browser("1", "Numpad1")
kiem("phím số hàng trên và numpad KHÔNG lẫn nhau", t1 == "1" and t2 == "num1",
     f"— hàng trên {t1!r}, numpad {t2!r}")

# Gõ tiếng Việt bật sẵn: `key` ra chữ có dấu, phải lần theo vị trí vật lý.
t3, loi3 = core.key_from_browser("ầ", "KeyA")
t4, loi4 = core.key_from_browser("Dead", "KeyE")
kiem("gõ tiếng Việt: chữ có dấu thì báo lỗi rõ ràng", t3 is None and "không hiểu" in loi3)
kiem("gõ tiếng Việt: phím chết thì lần theo vị trí vật lý", t4 == "e", f"— {t4!r}")

# Không đoán bừa: pyautogui nhận tên sai thì im lặng không làm gì, nên thà báo ngay.
t5, loi5 = core.key_from_browser("Unidentified", "")
kiem("phím không nhận ra thì BÁO, không đoán bừa", t5 is None and bool(loi5))


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

    def than():
        try:
            _web.cho_san_sang(js)
            _web.mo_mau(js)
            time.sleep(1.4)
            js(JS_TIEN_ICH)

            # mở hộp thoại hành động, chuyển sang loại "Nhấn phím"
            js("window.__P.bam(window.__P.nutRibbon('HĐ lẻ'))")
            time.sleep(1.0)
            js("window.__P.chonLoai('key_press')")
            time.sleep(0.8)
            ghi.append(("mở được hộp thoại loại Nhấn phím",
                        js("!!window.__P.nutHt('Bấm phím để ghi')")))
            ghi.append(("gợi ý chỉ ra cả hai cách dùng",
                        "gõ phím thật" in js("window.__P.goiY()")))

            # --- ghi một phím thường ---
            js("window.__P.bam(window.__P.nutHt('Bấm phím để ghi'))")
            time.sleep(0.4)
            ghi.append(("bấm nút → chuyển sang trạng thái đang chờ",
                        js("!!window.__P.nutHt('Đang chờ')")))
            js("window.__P.phim('i', 'KeyI')")
            time.sleep(0.8)
            ghi.append(("bấm phím I → ô nhận 'i'", js("window.__P.giaTri()") == "i",
                        f"— {js('window.__P.giaTri()')!r}"))
            ghi.append(("ghi xong thì thôi chờ",
                        js("!!window.__P.nutHt('Bấm phím để ghi')")))

            # --- ESCAPE: cái bẫy chính ---
            js("window.__P.bam(window.__P.nutHt('Bấm phím để ghi'))")
            time.sleep(0.4)
            js("window.__P.phim('Escape', 'Escape')")
            time.sleep(0.8)
            ghi.append(("bấm Esc để ghi thì KHÔNG đóng hộp thoại", js("window.__P.moHt()")))
            ghi.append(("  …và ghi được đúng 'escape'",
                        js("window.__P.giaTri()") == "escape",
                        f"— {js('window.__P.giaTri()')!r}"))

            # --- Esc vẫn phải đóng hộp thoại khi KHÔNG đang ghi ---
            js("window.__P.phim('Escape', 'Escape')")
            time.sleep(0.7)
            ghi.append(("không ghi nữa thì Esc lại đóng hộp thoại như thường",
                        not js("window.__P.moHt()")))

            # --- phím bổ trợ bấm một mình thì bỏ qua ---
            js("window.__P.bam(window.__P.nutRibbon('HĐ lẻ'))")
            time.sleep(1.0)
            js("window.__P.chonLoai('key_press')")
            time.sleep(0.8)
            js("window.__P.bam(window.__P.nutHt('Bấm phím để ghi'))")
            time.sleep(0.4)
            js("window.__P.phim('Shift', 'ShiftLeft')")
            time.sleep(0.6)
            ghi.append(("giữ Shift một mình KHÔNG cướp mất cú ghi",
                        js("!!window.__P.nutHt('Đang chờ')")))
            js("window.__P.phim('F5', 'F5')")
            time.sleep(0.8)
            ghi.append(("bấm tiếp F5 thì ghi được F5", js("window.__P.giaTri()") == "f5",
                        f"— {js('window.__P.giaTri()')!r}"))

            # --- vẫn gõ tay được như cũ ---
            js("(()=>{const o=window.__P.oPhim();"
               "const dat=Object.getOwnPropertyDescriptor("
               "window.HTMLInputElement.prototype,'value').set;"
               "dat.call(o,'space'); o.dispatchEvent(new Event('input',{bubbles:true}))})()")
            time.sleep(0.5)
            ghi.append(("gõ tay vào ô vẫn dùng được bình thường",
                        js("window.__P.giaTri()") == "space"))
            js("window.__P.bam(window.__P.nutHt('Lưu'))")
            time.sleep(0.8)
            ghi.append(("lưu được hành động vừa ghi", not js("window.__P.moHt()")))

            # ---------------- phím DỪNG KHẨN trong Cài đặt ----------------
            # Chỗ này còn đáng làm hơn: gõ sai tên phím thì phím dừng IM LẶNG không
            # chạy, và phát hiện ra đúng lúc đang cần dừng gấp.
            js('window.__P.bam(window.__P.nutCaiDat())')
            time.sleep(1.0)
            ghi.append(("Cài đặt cũng có nút ghi phím",
                        js("!!window.__P.oDung()") and js("!!window.__P.nutHt('Bấm phím để ghi')")))
            cu = js("window.__P.triDung()")
            js("window.__P.bam(window.__P.nutHt('Bấm phím để ghi'))")
            time.sleep(0.4)
            js("window.__P.phim('F8', 'F8')")
            time.sleep(0.8)
            ghi.append(("ghi được phím dừng mới", js("window.__P.triDung()") == "f8",
                        f"— {cu!r} → {js('window.__P.triDung()')!r}"))
            js("window.__P.bam(window.__P.nutHt('Bấm phím để ghi'))")
            time.sleep(0.4)
            js("window.__P.phim('Escape', 'Escape')")
            time.sleep(0.8)
            ghi.append(("bấm Esc để ghi KHÔNG đóng mất hộp Cài đặt", js("window.__P.moHt()")))
            ghi.append(("  …và ghi được 'escape' làm phím dừng",
                        js("window.__P.triDung()") == "escape",
                        f"— {js('window.__P.triDung()')!r}"))
            js("window.__P.bam(window.__P.nutHt('Huỷ'))")
            time.sleep(0.7)
            ghi.append(("bấm Huỷ thì không đổi gì cả", not js("window.__P.moHt()")))
        except Exception:
            import traceback
            ghi.append(("chạy được tới cuối", False, "\n" + traceback.format_exc(limit=4)))
        finally:
            win.destroy()

    print("\n▸ Giao diện")
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
