"""Rẽ nhánh — phía GIAO DIỆN: nút trên ribbon, và nhãn phân cấp lên tới huy hiệu.

`test_re_nhanh.py` đã chứng minh phần logic (Python tính nhãn "4A.2B" và bộ chạy đi
đúng nhánh). Bài này kiểm nốt đoạn đường còn lại: nhãn ấy có thật sự hiện ra trên
khối, và có hiện TRỌN VẸN không.

Chỗ dễ vỡ nhất: huy hiệu vốn là hình tròn CỨNG 24×24 — vừa đủ cho "1".."9". Nhãn giờ
là chuỗi phân cấp nên nó phải nở ngang được, nếu không chữ bị cắt và người dùng đọc
"4A.2" thành "4A". Kiểu lỗi này không test logic nào bắt được, phải ĐO trên trang.

Bắn sự kiện thẳng vào DOM, không đụng chuột thật -> nhóm AN_TOAN.
"""
import _boot  # noqa: F401
import _web

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANG = os.path.join(REPO, "webui", "dist", "index.html")

JS_TIEN_ICH = r"""
window.__R = {
  tam(el){ const r = el.getBoundingClientRect(); return {x:r.x+r.width/2, y:r.y+r.height/2} },
  ban(el, ten, x, y){
    el.dispatchEvent(new MouseEvent(ten, {bubbles:true, cancelable:true, composed:true,
      view:window, button:0, buttons: ten==='mouseup'?0:1, clientX:x, clientY:y}))
  },
  bam(el){ const t = this.tam(el); this.ban(el,'mousedown',t.x,t.y);
           this.ban(el,'mouseup',t.x,t.y); this.ban(el,'click',t.x,t.y) },
  nutRibbon(ten){ return [...document.querySelectorAll('.ribbon .nut-lon')]
                    .find(b => b.textContent.trim() === ten) },
  nutHt(ten){ return [...document.querySelectorAll('.lop-phu .nut')]
                .find(b => b.textContent.trim().includes(ten)) },
  cong(i, canh){ const n = document.querySelectorAll('.react-flow__node')[i]
                 return n && n.querySelector('.react-flow__handle-'+canh) },
  keo(tu, den){
    const a = this.tam(tu), b = this.tam(den)
    this.ban(tu,'mousedown',a.x,a.y)
    this.ban(document,'mousemove',b.x,b.y)
    this.ban(den,'mouseup',b.x,b.y)
  },
  huyHieu(){ return [...document.querySelectorAll('.so-thu-tu')].map(e => e.textContent.trim()) },
  /** Huy hiệu nào bị cắt chữ: nội dung rộng hơn khung chứa nó. */
  biCat(){ return [...document.querySelectorAll('.so-thu-tu')]
             .filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.textContent.trim()) },
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

    def than():
        try:
            _web.cho_san_sang(js)
            _web.mo_mau(js)
            time.sleep(1.4)
            js(JS_TIEN_ICH)

            # --- 1. Nút trên ribbon ---
            ghi.append(("ribbon có nút \"Rẽ nhánh\"", js("!!window.__R.nutRibbon('Rẽ nhánh')")))
            truoc = js("document.querySelectorAll('.react-flow__node').length")
            js("window.__R.bam(window.__R.nutRibbon('Rẽ nhánh'))")
            time.sleep(1.0)
            ghi.append(("bấm vào là mở thẳng hộp thoại hành động",
                        js("document.querySelectorAll('.lop-phu').length") > 0))
            loai = js("(()=>{const s=document.querySelector('.lop-phu select.day');"
                      "return s?s.value:'—'})()")
            ghi.append(("hộp thoại mở sẵn đúng loại confirm_mod", loai == "confirm_mod",
                        f"— '{loai}'"))
            goi = js("(()=>{const e=document.querySelector('.lop-phu');"
                     "return e?e.textContent:''})()")
            ghi.append(("gợi ý nói rõ luật: khớp thì đi tiếp, không khớp thì dừng nhánh",
                        "ĐI TIẾP" in goi and "DỪNG nhánh" in goi))
            ghi.append(("dùng chung bảng soạn điều kiện với Kiểm tra mod",
                        "Tier" in goi and "Loại mod" in goi))
            js("window.__R.bam(window.__R.nutHt('Huỷ'))")
            time.sleep(0.6)
            sau = js("document.querySelectorAll('.react-flow__node').length")
            ghi.append(("khối cổng đã nằm trên canvas", sau == truoc + 1,
                        f"— {truoc} → {sau} khối"))

            # --- 1b. Nút Delay: thêm THẲNG, KHÔNG mở hộp thoại ---
            # Đây là điểm khác biệt duy nhất so với 4 nút còn lại, và cũng là toàn bộ
            # lý do nút này tồn tại — thêm mà vẫn bắt bấm Lưu thì chẳng nhanh hơn gì.
            truoc_d = js("document.querySelectorAll('.react-flow__node').length")
            js("window.__R.bam(window.__R.nutRibbon('Delay'))")
            time.sleep(1.0)
            sau_d = js("document.querySelectorAll('.react-flow__node').length")
            ghi.append(("nút Delay thêm được khối", sau_d == truoc_d + 1,
                        f"— {truoc_d} → {sau_d}"))
            ghi.append(("nút Delay KHÔNG mở hộp thoại (đó là cả mục đích của nó)",
                        js("document.querySelectorAll('.lop-phu').length") == 0))
            chu_delay = js("(()=>{const n=document.querySelectorAll('.react-flow__node');"
                           "return n[n.length-1].querySelector('.hop').innerText"
                           ".replace(/\\s+/g,' ').trim()})()")
            ghi.append(("khối Delay dùng được ngay, có sẵn thời gian mặc định",
                        "ms" in chu_delay, f"— \"{chu_delay[:60]}\""))
            # dọn lại cho phần sau không bị lệch chỉ số
            js("(()=>{const n=document.querySelectorAll('.react-flow__node');"
               "const e=n[n.length-1];"
               "e.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,view:window,button:0}));"
               "e.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,view:window,button:0}));"
               "e.dispatchEvent(new MouseEvent('click',{bubbles:true,view:window,button:0}))})()")
            time.sleep(0.3)
            js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Delete',bubbles:true}))")
            time.sleep(0.6)

            # --- 2. Nối thành điểm rẽ, xem nhãn có lên huy hiệu ---
            phang = js("window.__R.huyHieu()")
            ghi.append(("chưa rẽ nhánh thì nhãn vẫn là số trơn như cũ",
                        all(x.isdigit() or x == "–" for x in phang), f"— {phang}"))
            # khối 0 vốn đã nối sang khối 1; nối thêm sang khối cổng vừa thêm -> điểm rẽ
            js(f"window.__R.keo(window.__R.cong(0,'right'), window.__R.cong({sau - 1},'left'))")
            time.sleep(1.2)
            nhan = js("window.__R.huyHieu()")
            co_chu = [x for x in nhan if len(x) > 1 and x[-1].isalpha()]
            ghi.append(("nối thành điểm rẽ → huy hiệu mọc chữ nhánh", bool(co_chu),
                        f"— {nhan}"))
            ghi.append(("nhánh trên là A, nhánh dưới là B",
                        any(x.endswith("A") for x in co_chu)
                        and any(x.endswith("B") for x in co_chu), f"— {co_chu}"))

            # --- 3. Huy hiệu phải nở ra, không được cắt chữ ---
            cat = js("window.__R.biCat()")
            ghi.append(("không huy hiệu nào bị cắt chữ", not cat, f"— bị cắt: {cat or 'không'}"))
            hinh = js("(()=>{const e=document.querySelector('.so-thu-tu');"
                      "const s=getComputedStyle(e);"
                      "return s.borderRadius+'|'+s.minWidth+'|'+Math.round("
                      "e.getBoundingClientRect().height)})()")
            bo, rong_toi_thieu, cao = hinh.split("|")
            ghi.append(("huy hiệu là viên thuốc tự nở, không phải hình tròn cứng",
                        bo.startswith("999") and rong_toi_thieu == "24px",
                        f"— bo {bo}, min-width {rong_toi_thieu}, cao {cao}px"))
            dai = js("(()=>{const e=document.querySelector('.so-thu-tu');"
                     "const cu=e.textContent; e.textContent='4A.2B';"
                     "const ok=e.scrollWidth<=e.clientWidth+1; e.textContent=cu; return ok})()")
            ghi.append(("nhãn dài cỡ \"4A.2B\" vẫn hiện trọn", dai))
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
