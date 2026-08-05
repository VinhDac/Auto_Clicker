"""Cổng nối trên canvas: bấm có trúng không, và nối xong có báo cho người dùng biết.

VÌ SAO PHẢI CÓ BÀI NÀY
----------------------
Người dùng báo "4 điểm nối ở block bé và khó dùng quá, di chuột mãi không nhận
diện được". Có HAI lỗi chồng lên nhau, và cả hai đều vô hình với 325 check còn lại
vì chúng chỉ hỏi dữ liệu, không hỏi *bấm vào có trúng không*:

1. THỨ TỰ NẠP CSS. `@xyflow/react/dist/style.css` được import trong App.tsx, mà
   main.tsx lại import App SAU css của mình -> stylesheet gốc nằm cuối bundle và
   đè mất. Cổng vẫn 6px dù đã khai 24px. Sửa: nạp nó trong main.tsx, TRƯỚC app.css.

2. THỨ TỰ VẼ. `.hop` là position:relative và nằm SAU cổng trong DOM nên với z-index
   mặc định nó vẽ đè lên cổng. Nửa vùng bấm nằm trong lòng khối bị nuốt, chỉ nửa
   thò ra ngoài mép mới bấm được. Sửa: z-index cho cổng.

Cả hai lỗi đều làm DOM "đúng" và ảnh chụp "đẹp". Chỉ `elementFromPoint` mới trả lời
được câu "chuột đặt ở đây thì chạm vào cái gì".

Bài này KHÔNG đụng chuột thật — nó bắn MouseEvent thẳng vào DOM. React Flow v12
nghe onMouseDown (không phải pointerdown) và không đòi event.isTrusted, nên cách
này vừa tất định vừa không giành con trỏ của người đang ngồi máy.
"""
import _boot  # noqa: F401
import _web

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANG = os.path.join(REPO, "webui", "dist", "index.html")

# Tiện ích phía trang. Gom vào một chỗ để các câu hỏi bên dưới ngắn và đọc được.
JS_TIEN_ICH = r"""
window.__T = {
  tam(el){ const r = el.getBoundingClientRect(); return {x:r.x+r.width/2, y:r.y+r.height/2} },
  ban(el, ten, x, y){
    el.dispatchEvent(new MouseEvent(ten, {bubbles:true, cancelable:true, composed:true,
      view:window, button:0, buttons: ten==='mouseup'?0:1, clientX:x, clientY:y}))
  },
  cong(i, canh){
    const n = document.querySelectorAll('.react-flow__node')[i]
    return n && n.querySelector('.react-flow__handle-'+canh)
  },
  /** Bán kính lớn nhất mà mọi hướng quanh tâm cổng đều còn chạm vào chính cổng đó. */
  banKinhBam(h){
    const t = this.tam(h)
    for (let k = 1; k <= 24; k++)
      for (let j = 0; j < 8; j++) {
        const a = j*Math.PI/4
        if (document.elementFromPoint(t.x+k*Math.cos(a), t.y+k*Math.sin(a)) !== h) return k-1
      }
    return 24
  },
  cham(h){ return getComputedStyle(h, '::after').width },
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

            # --- 1. Kích thước: stylesheet của mình phải thắng stylesheet gốc ---
            # ĐO BẰNG CSS, không bằng getBoundingClientRect: rect co giãn theo mức thu
            # phóng của canvas, mà mức đó lại phụ thuộc chiều cao canvas — thêm thanh
            # tiêu đề vào là fitView chọn mức khác và phép đo "22px" tụt xuống 18px dù
            # chẳng có gì hỏng. CSS width thì bất biến.
            rong = js("getComputedStyle(document.querySelector('.react-flow__handle')).width")
            ghi.append(("cổng khai 24px (gốc React Flow là 6px)", rong == "24px",
                        f"— {rong}"))
            phong = js("(()=>{const v=document.querySelector('.react-flow__viewport');"
                       "const m=new DOMMatrixReadOnly(getComputedStyle(v).transform);"
                       "return Math.round(m.a*100)/100})()")
            ghi.append(("đọc được mức thu phóng để quy đổi các phép đo sau", phong > 0,
                        f"— {phong}×"))
            ghi.append(("chấm nhìn thấy vẫn nhỏ gọn 9px",
                        js("window.__T.cham(document.querySelector('.react-flow__handle'))") == "9px"))

            # --- 2. Bấm có trúng không: thân khối không được đè lên cổng ---
            trung = js("(()=>{const h=window.__T.cong(0,'right'), t=window.__T.tam(h);"
                       "return document.elementFromPoint(t.x,t.y)===h})()")
            ghi.append(("tâm cổng bấm là trúng cổng, không bị .hop che", trung))
            bk = js("window.__T.banKinhBam(window.__T.cong(0,'right'))")
            # Ngưỡng tính theo mức phóng: bán kính thật là 11px ở 100%, co lại theo
            # canvas. Ngưỡng cứng sẽ đỏ oan mỗi lần bố cục đổi một chút.
            nguong = max(4, round(9 * phong))
            ghi.append(("lệch gần hết bán kính vẫn trúng", bk >= nguong,
                        f"— bán kính bấm {bk}px ở mức phóng {phong}× "
                        f"(cần ≥{nguong}, trước khi sửa là 3px ở 100%)"))

            so_khoi = js("document.querySelectorAll('.react-flow__node').length")
            truoc = js("document.querySelectorAll('.react-flow__edge').length")
            ghi.append(("canvas có sẵn nhiều khối để nối thử", so_khoi >= 3,
                        f"— {so_khoi} khối, {truoc} dây"))
            dich = so_khoi - 1
            js(f"window.__DICH={dich}")

            # --- 3. Kéo dây: đang kéo thì MỌI cổng phải hiện rõ ---
            js("(()=>{const h=window.__T.cong(0,'bottom'), t=window.__T.tam(h);"
               "window.__T.ban(h,'mousedown',t.x,t.y)})()")
            time.sleep(0.25)
            js("(()=>{const b=window.__T.tam(window.__T.cong(window.__DICH,'left'));"
               "window.__T.ban(document,'mousemove',b.x-70,b.y-25)})()")
            time.sleep(0.3)
            ghi.append(("đang kéo → canvas bật cờ báo hiệu",
                        js("document.querySelectorAll('.vung-canvas.dang-noi').length>0")))
            to = js("window.__T.cham(document.querySelector('.react-flow__handle'))")
            ghi.append(("đang kéo → mọi cổng phóng to lên", to == "13px", f"— {to}"))
            ghi.append(("có đường nối tạm bám theo chuột",
                        js("document.querySelectorAll('.react-flow__connection,"
                           ".react-flow__connectionline').length>0")))

            # --- 4. Rê trúng cổng đích: cổng sáng + VIỀN CẢ KHỐI sáng ---
            js("(()=>{const b=window.__T.tam(window.__T.cong(window.__DICH,'left'));"
               "window.__T.ban(document,'mousemove',b.x,b.y)})()")
            time.sleep(0.35)
            ghi.append(("cổng đích nhận trạng thái nối được",
                        js("document.querySelectorAll('.react-flow__handle.connectingto')"
                           ".length>0")))
            sang = js("(()=>{const h=document.querySelector('.react-flow__handle.connectingto');"
                      "return h?window.__T.cham(h):'—'})()")
            # 16px, KHÔNG phải 13px: luật '.dang-noi' 3 lớp từng đè luật 'trúng đích' 2 lớp.
            ghi.append(("cổng đích sáng hẳn lên, hơn cổng thường", sang == "16px", f"— {sang}"))
            ghi.append(("VIỀN KHỐI ĐÍCH sáng lên",
                        js("document.querySelectorAll('.react-flow__node:has("
                           ".react-flow__handle.connectingto) .hop').length>0")))
            khac = js("(()=>{const a=document.querySelector('.react-flow__node:has("
                      ".react-flow__handle.connectingto) .hop');"
                      "const b=[...document.querySelectorAll('.hop')].find(x=>x!==a);"
                      "return a&&b&&getComputedStyle(a).borderColor!==getComputedStyle(b).borderColor})()")
            ghi.append(("viền khối đích KHÁC hẳn khối thường", khac))

            # --- 5. Thả ra: dây phải nối thật, và trạng thái phải sạch ---
            js("(()=>{const h=window.__T.cong(window.__DICH,'left'), b=window.__T.tam(h);"
               "window.__T.ban(h,'mouseup',b.x,b.y)})()")
            time.sleep(0.5)
            sau = js("document.querySelectorAll('.react-flow__edge').length")
            ghi.append(("thả ra là nối thành công", sau == truoc + 1,
                        f"— {truoc} dây → {sau} dây"))
            ghi.append(("thả xong thì tắt hết trạng thái kéo",
                        js("document.querySelectorAll('.vung-canvas.dang-noi').length===0")))

            # --- 6. Mũi tên phải nhỏ hơn trước, đừng nặng hơn cả cổng nó cắm vào ---
            mw = js("(()=>{const m=document.querySelector('marker');"
                    "return m?Number(m.getAttribute('markerWidth')):-1})()")
            ghi.append(("đầu mũi tên nhỏ (trước là 16)", 0 < mw <= 12, f"— {mw}px"))

            # --- 7. Double-click lên dây = huỷ kết nối, và Ctrl+Z lấy lại được ---
            js("(()=>{const g=document.querySelector('.react-flow__edge');"
               "const p=g.querySelector('.react-flow__edge-interaction')||g;"
               "const r=p.getBoundingClientRect();"
               "window.__T.ban(p,'dblclick',r.x+r.width/2,r.y+r.height/2)})()")
            time.sleep(0.4)
            con = js("document.querySelectorAll('.react-flow__edge').length")
            ghi.append(("double-click lên dây là huỷ nối", con == sau - 1,
                        f"— {sau} dây → {con} dây"))
            # Xoá nhầm phải lấy lại được: đây là lý do huyNoi() gọi chup() trước khi xoá.
            js("window.dispatchEvent(new KeyboardEvent('keydown',"
               "{key:'z',ctrlKey:true,bubbles:true}))")
            time.sleep(0.4)
            lai = js("document.querySelectorAll('.react-flow__edge').length")
            ghi.append(("Ctrl+Z lấy lại dây vừa huỷ", lai == sau, f"— {con} dây → {lai} dây"))
            ghi.append(("dây có con trỏ bàn tay để biết bấm được",
                        js("getComputedStyle(document.querySelector("
                           "'.react-flow__edge')).cursor") == "pointer"))
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
