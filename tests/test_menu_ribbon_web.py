"""Menu xổ xuống của "Lưu ▾" và "Mở ▾" trên ribbon.

LỖI ĐÃ SỬA: menu bị CẮT CỤT, bấm không được mục nào.

`.ribbon` đặt `overflow-x: auto` để khi cửa sổ hẹp thì các nhóm nút cuộn ngang được.
Nhưng theo chuẩn CSS, hễ một trục thôi `visible` thì trục kia cũng thôi luôn — nên
`overflow-y` ngầm thành `auto` và dải ribbon xén mất phần menu thò xuống dưới. Menu
vốn là `position: absolute` nên nằm trong vùng bị xén đó.

Sửa: `position: fixed` + toạ độ tính từ vị trí nút. Fixed thoát khỏi mọi vùng cắt
của khối cha.

Bài này KHÔNG chỉ hỏi "menu có tồn tại trong DOM không" — nó vẫn tồn tại khi đang bị
xén. Phải hỏi `elementFromPoint`: đặt chuột lên mục cuối thì có chạm vào đúng mục đó
không. Đây đúng bài học từ vụ cổng nối bị `.hop` che.

Bắn sự kiện thẳng vào DOM, không đụng chuột thật -> nhóm AN_TOAN.
"""
import _boot  # noqa: F401
import _web

import os
import sys
import time
import json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANG = os.path.join(REPO, "webui", "dist", "index.html")

JS_TIEN_ICH = r"""
window.__N = {
  nut(t){ return [...document.querySelectorAll('.ribbon .nut-lon')]
            .find(b => b.textContent.trim().startsWith(t)) },
  bam(el){ el.dispatchEvent(new MouseEvent('click',
      {bubbles:true, cancelable:true, view:window, button:0})) },
  bang(){ return document.querySelector('.menu-xo') },
  muc(){ return [...document.querySelectorAll('.menu-xo .muc-menu')] },
  ten(){ return this.muc().map(b => b.textContent.trim()) },
  /** Mục nào ĐẶT CHUỘT LÊN LÀ CHẠM ĐÚNG NÓ. Mục bị xén vẫn có trong DOM, vẫn có
      getBoundingClientRect, nhưng elementFromPoint sẽ không trả về nó. */
  bamDuoc(){
    return this.muc().filter(b => {
      const r = b.getBoundingClientRect()
      if (r.width < 1 || r.height < 1) return false
      const e = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2)
      return b === e || b.contains(e)
    }).length
  },
  hinh(){
    const b = this.bang(), r = b.getBoundingClientRect()
    const rb = document.querySelector('.ribbon').getBoundingClientRect()
    return JSON.stringify({
      viTri: getComputedStyle(b).position,
      duoiMenu: Math.round(r.bottom), duoiRibbon: Math.round(rb.bottom),
      caoMan: window.innerHeight, phaiMenu: Math.round(r.right),
      rongMan: window.innerWidth, traiMenu: Math.round(r.x), tren: Math.round(r.y),
    })
  },
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
            time.sleep(1.2)
            js(JS_TIEN_ICH)

            for nut, so_muc in [("Mở", 5), ("Lưu", 5)]:
                js(f"window.__N.bam(window.__N.nut('{nut}'))")
                time.sleep(0.5)
                ghi.append((f"[{nut} ▾] mở ra menu", js("!!window.__N.bang()")))
                ten = js("window.__N.ten()")
                ghi.append((f"[{nut} ▾] đủ {so_muc} mục", len(ten) == so_muc,
                            f"— {len(ten)}: {ten}"))

                h = json.loads(js("window.__N.hinh()"))
                ghi.append((f"[{nut} ▾] định vị theo khung nhìn, không theo ribbon",
                            h["viTri"] == "fixed", f"— {h['viTri']}"))
                # ĐÂY là bằng chứng nó thoát khỏi vùng cắt: menu thò xuống DƯỚI ribbon.
                ghi.append((f"[{nut} ▾] menu thò hẳn xuống dưới dải ribbon",
                            h["duoiMenu"] > h["duoiRibbon"],
                            f"— đáy menu {h['duoiMenu']}px, đáy ribbon {h['duoiRibbon']}px"))
                ghi.append((f"[{nut} ▾] nằm trọn trong cửa sổ",
                            h["duoiMenu"] <= h["caoMan"] and h["phaiMenu"] <= h["rongMan"]
                            and h["traiMenu"] >= 0 and h["tren"] >= 0,
                            f"— đáy {h['duoiMenu']}/{h['caoMan']}, "
                            f"phải {h['phaiMenu']}/{h['rongMan']}"))
                # Câu hỏi thật sự: bấm vào có trúng không.
                bam_duoc = js("window.__N.bamDuoc()")
                ghi.append((f"[{nut} ▾] MỌI mục đều bấm trúng", bam_duoc == len(ten),
                            f"— {bam_duoc}/{len(ten)} mục"))
                # Bấm ra ngoài phải nhắm vào một PHẦN TỬ THẬT. Bắn lên `window` thì
                # `boc.contains(e.target)` nhận vào Window chứ không phải Node và ném
                # TypeError — handler chết giữa chừng, menu không đóng. Chuột thật
                # không bao giờ rơi vào tình huống đó.
                # PHẢI kèm toạ độ thật. MouseEvent không có clientX/Y thì mặc định
                # (0,0) — tức góc trên-trái cửa sổ, đúng vùng kéo giãn, và hook khung
                # cửa sổ chặn sự kiện lại (đúng như nó phải làm). Bắn ở giữa canvas.
                js("(()=>{const c=document.querySelector('.vung-canvas');"
                   "const r=c.getBoundingClientRect();"
                   "c.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,"
                   "cancelable:true,view:window,"
                   "clientX:Math.round(r.left+r.width/2),"
                   "clientY:Math.round(r.top+r.height/2)}))})()")
                time.sleep(0.4)
                ghi.append((f"[{nut} ▾] bấm ra ngoài thì đóng", not js("!!window.__N.bang()")))

            # Mục có thật sự CHẠY không — menu hiện đẹp mà bấm không ăn thì vẫn hỏng.
            js("window.__N.bam(window.__N.nut('Mở'))")
            time.sleep(0.5)
            js("(()=>{const m=window.__N.muc().find("
               "b=>b.textContent.trim().startsWith('Process mẫu'));"
               "window.__N.bam(m)})()")
            time.sleep(1.2)
            ghi.append(("bấm một mục thì nó chạy thật",
                        js("document.querySelectorAll('.react-flow__node').length") == 3,
                        f"— {js('document.querySelectorAll(\".react-flow__node\").length')} khối"))
            ghi.append(("  …và menu tự đóng sau khi chọn", not js("!!window.__N.bang()")))
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
