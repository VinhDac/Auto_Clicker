"""Menu chuột phải: nền canvas, khối, và dây.

Trước khi có bài này chuột phải KHÔNG làm gì cả — menu mặc định của WebView2 cũng đã
tắt sẵn (`AreDefaultContextMenusEnabled` đi theo cờ debug, bản phát hành thì debug
tắt). Nên đây là mặt bằng sạch, không tranh chấp với thứ gì.

Ba cái bẫy bài này canh, vì cả ba đều làm menu "trông vẫn đúng" mà hành xử sai:

  1. Bấm phải vào khối phải CHỌN khối đó trước. Không thì "Chép" chép nhầm khối đang
     chọn từ trước — menu vẫn hiện ra đúng chỗ nên rất khó nhận ra.
  2. "Dán" phải dùng vị trí lúc BẤM PHẢI, không phải vị trí con trỏ lúc chọn dòng menu
     (lúc đó chuột đang nằm trên menu, cách chỗ bấm cả trăm pixel).
  3. Mục menu phải được dựng LÚC RENDER. Nhét sẵn closure vào state lúc bấm phải là
     đóng băng trạng thái của khoảnh khắc đó.

Bắn sự kiện thẳng vào DOM, không đụng chuột thật -> nhóm AN_TOAN.
"""
import _boot  # noqa: F401

import os
import sys
import time
import json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANG = os.path.join(REPO, "webui", "dist", "index.html")

JS_TIEN_ICH = r"""
window.__M = {
  bamPhai(el, x, y){
    el.dispatchEvent(new MouseEvent('contextmenu', {bubbles:true, cancelable:true,
      composed:true, view:window, button:2, buttons:2, clientX:x, clientY:y}))
  },
  phaiVaoKhoi(i){
    const n = document.querySelectorAll('.react-flow__node')[i]
    const r = n.getBoundingClientRect()
    this.bamPhai(n, r.x+40, r.y+12)
  },
  phaiVaoNen(x, y){ this.bamPhai(document.querySelector('.react-flow__pane'), x, y) },
  phaiVaoDay(){
    const g = document.querySelector('.react-flow__edge')
    const p = g.querySelector('.react-flow__edge-interaction') || g
    const r = p.getBoundingClientRect()
    this.bamPhai(p, r.x+r.width/2, r.y+r.height/2)
  },
  co(){ return document.querySelectorAll('.menu-phai').length > 0 },
  muc(){ return [...document.querySelectorAll('.menu-phai > .muc-phai')]
           .map(b => ({ten: b.querySelector('.chu-muc').textContent.trim(),
                       tat: b.disabled})) },
  ten(){ return this.muc().map(m => m.ten) },
  bamMuc(t){
    const b = [...document.querySelectorAll('.menu-phai > .muc-phai')]
      .find(x => x.querySelector('.chu-muc').textContent.trim().startsWith(t))
    if (!b) return 'khong thay muc: '+t
    b.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window}))
    return 'ok'
  },
  moCon(t){
    const b = [...document.querySelectorAll('.menu-phai > .muc-phai')]
      .find(x => x.querySelector('.chu-muc').textContent.trim().startsWith(t))
    // React KHÔNG nghe 'mouseenter' gốc — nó tổng hợp enter/leave từ mouseover/mouseout.
    // Bắn 'mouseenter' thì onMouseEnter không bao giờ chạy.
    b.dispatchEvent(new MouseEvent('mouseover',
      {bubbles:true, cancelable:true, view:window, relatedTarget:null}))
    return 'ok'
  },
  tenCon(){ return [...document.querySelectorAll('.menu-con > .muc-phai')]
              .map(b => b.querySelector('.chu-muc').textContent.trim()) },
  bamCon(i){
    const b = document.querySelectorAll('.menu-con > .muc-phai')[i]
    b.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window}))
  },
  dong(){ window.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true})) },
  soKhoi(){ return document.querySelectorAll('.react-flow__node').length },
  soDay(){ return document.querySelectorAll('.react-flow__edge').length },
  soChon(){ return document.querySelectorAll('.react-flow__node.selected').length },
  chonLa(i){ return document.querySelectorAll('.react-flow__node')[i]
               .classList.contains('selected') },
  gocCuoi(){ const ds = document.querySelectorAll('.react-flow__node')
             const r = ds[ds.length-1].getBoundingClientRect(); return {x:r.x, y:r.y} },
  khung(){ const r = document.querySelector('.vung-canvas').getBoundingClientRect()
           return {x:r.x, y:r.y, w:r.width, h:r.height} },
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
            for _ in range(90):
                time.sleep(0.15)
                if js("!!document.querySelector('.hop')"):
                    break
            time.sleep(1.4)
            js(JS_TIEN_ICH)
            khung = json.loads(js("JSON.stringify(window.__M.khung())"))

            # ---------------- menu của NỀN ----------------
            nx = int(khung["x"] + khung["w"] * 0.55)
            ny = int(khung["y"] + khung["h"] * 0.72)
            js(f"window.__M.phaiVaoNen({nx}, {ny})")
            time.sleep(0.5)
            ghi.append(("bấm phải nền → hiện menu", js("window.__M.co()")))
            ten = js("window.__M.ten()")
            ghi.append(("menu nền có đủ 4 mục Thêm khối",
                        [t for t in ten if t.startswith("Thêm")]
                        == ["Thêm Loop", "Thêm Nhóm", "Thêm HĐ lẻ", "Thêm Rẽ nhánh"],
                        f"— {ten}"))
            ghi.append(("menu nền KHÔNG có Chép (chỗ trống thì chép cái gì)",
                        not any(t.startswith("Chép") for t in ten)))
            ghi.append(("chưa chép gì thì Dán bị mờ",
                        any(m["ten"].startswith("Dán") and m["tat"]
                            for m in js("window.__M.muc()"))))

            n0 = js("window.__M.soKhoi()")
            js("window.__M.bamMuc('Thêm Rẽ nhánh')")
            time.sleep(1.0)
            ghi.append(("chọn \"Thêm Rẽ nhánh\" → thêm được khối",
                        js("window.__M.soKhoi()") == n0 + 1,
                        f"— {n0} → {js('window.__M.soKhoi()')}"))
            js("window.__M.dong()")     # đóng hộp thoại hành động vừa mở kèm
            time.sleep(0.6)
            goc = json.loads(js("JSON.stringify(window.__M.gocCuoi())"))
            ghi.append(("khối mới nằm ĐÚNG chỗ đã bấm phải",
                        max(abs(goc["x"] - nx), abs(goc["y"] - ny)) <= 6,
                        f"— bấm ({nx}, {ny}), khối ở ({round(goc['x'])}, {round(goc['y'])})"))

            # ---------------- menu của KHỐI ----------------
            js("window.__M.phaiVaoKhoi(0)")
            time.sleep(0.5)
            ten = js("window.__M.ten()")
            mong = ["Sửa", "Chép", "Dán", "Nhân bản", "Nối tới", "Ngắt hết kết nối", "Xoá"]
            ghi.append(("menu khối có đủ mục đã chốt",
                        [t.split(" (")[0] for t in ten] == mong, f"— {ten}"))
            ghi.append(("bấm phải vào khối là CHỌN luôn khối đó",
                        js("window.__M.soChon()") == 1 and js("window.__M.chonLa(0)")))

            # Nối tới: liệt kê khối nối được, nhãn đứng trước tên
            js("window.__M.moCon('Nối tới')")
            time.sleep(0.4)
            con = js("window.__M.tenCon()")
            ghi.append(("\"Nối tới\" liệt kê các khối nối được", len(con) >= 2,
                        f"— {len(con)} khối: {con[:3]}"))
            ghi.append(("  …không liệt kê khối ĐÃ nối rồi",
                        not any(c.startswith("2 ") for c in con), f"— {con}"))
            truoc_day = js("window.__M.soDay()")
            js("window.__M.bamCon(%d)" % (len(con) - 1))
            time.sleep(0.8)
            ghi.append(("chọn một khối trong \"Nối tới\" → nối thật",
                        js("window.__M.soDay()") == truoc_day + 1,
                        f"— {truoc_day} → {js('window.__M.soDay()')} dây"))

            # Ngắt hết kết nối
            js("window.__M.phaiVaoKhoi(0)")
            time.sleep(0.5)
            js("window.__M.bamMuc('Ngắt hết kết nối')")
            time.sleep(0.8)
            con_lai = js(
                "(()=>{const id=document.querySelectorAll('.react-flow__node')[0]"
                ".getAttribute('data-id');"
                "return [...document.querySelectorAll('.react-flow__edge')]"
                ".filter(e=>e.classList.toString().includes(id)).length})()")
            ghi.append(("\"Ngắt hết kết nối\" gỡ sạch dây của khối đó", con_lai == 0,
                        f"— còn {con_lai} dây dính vào nó"))
            ghi.append(("  …khối mất hết dây thì huy hiệu về \"–\" (sẽ không chạy)",
                        js("[...document.querySelectorAll('.so-thu-tu')]"
                           ".map(e=>e.textContent.trim()).includes('–')")))

            # Chép rồi Dán qua menu — dán phải rơi vào chỗ BẤM PHẢI
            js("window.__M.phaiVaoKhoi(0)")
            time.sleep(0.4)
            js("window.__M.bamMuc('Chép')")
            time.sleep(0.5)
            dx = int(khung["x"] + khung["w"] * 0.22)
            dy = int(khung["y"] + khung["h"] * 0.38)
            js(f"window.__M.phaiVaoNen({dx}, {dy})")
            time.sleep(0.4)
            ghi.append(("chép xong thì Dán hết mờ",
                        any(m["ten"].startswith("Dán") and not m["tat"]
                            for m in js("window.__M.muc()"))))
            truoc = js("window.__M.soKhoi()")
            js("window.__M.bamMuc('Dán')")
            time.sleep(1.0)
            goc2 = json.loads(js("JSON.stringify(window.__M.gocCuoi())"))
            ghi.append(("Dán qua menu rơi vào chỗ BẤM PHẢI, không phải chỗ con trỏ",
                        js("window.__M.soKhoi()") == truoc + 1
                        and max(abs(goc2["x"] - dx), abs(goc2["y"] - dy)) <= 6,
                        f"— bấm phải ({dx}, {dy}), khối ở "
                        f"({round(goc2['x'])}, {round(goc2['y'])})"))

            # ---------------- menu của DÂY ----------------
            js("window.__M.phaiVaoDay()")
            time.sleep(0.5)
            ghi.append(("bấm phải vào dây → menu chỉ có Xoá kết nối",
                        js("window.__M.ten()") == ["Xoá kết nối"],
                        f"— {js('window.__M.ten()')}"))
            truoc_day = js("window.__M.soDay()")
            js("window.__M.bamMuc('Xoá kết nối')")
            time.sleep(0.8)
            ghi.append(("xoá được đúng 1 dây", js("window.__M.soDay()") == truoc_day - 1,
                        f"— {truoc_day} → {js('window.__M.soDay()')}"))

            # ---------------- đóng menu ----------------
            js("window.__M.phaiVaoKhoi(0)")
            time.sleep(0.4)
            js("window.__M.dong()")
            time.sleep(0.4)
            ghi.append(("Esc đóng menu", not js("window.__M.co()")))
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
