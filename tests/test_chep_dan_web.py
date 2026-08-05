"""Chép / dán khối trên canvas: bản dán ra phải rơi vào CHỖ CON TRỎ.

VÌ SAO
------
Trước đây dán ra cách bản gốc 40px. Nghe hợp lý nhưng dùng mới thấy dở: chép một khối
ở đầu sơ đồ rồi cuộn sang cuối để dán, bản sao nằm cạnh BẢN GỐC — tức là ngoài màn
hình — và người dùng tưởng lệnh dán không ăn.

Ba thứ bài này giữ:
  1. Dán ra đúng chỗ con trỏ đang chỉ (đã quy đổi qua thu phóng + cuộn).
  2. Con trỏ không ở trên canvas thì rơi vào GIỮA KHUNG NHÌN — điều phải bảo đảm là
     khối dán ra NHÌN THẤY ĐƯỢC, chứ không phải nó nằm ở toạ độ nào.
  3. (ở `test_chep_dan_chuot.py`) Dán nhiều khối thì giữ nguyên khoảng cách tương đối
     giữa chúng; văng mỗi cái một nơi thì coi như phải xếp lại từ đầu.

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
window.__C = {
  ban(el, ten, x, y){
    el.dispatchEvent(new MouseEvent(ten, {bubbles:true, cancelable:true, composed:true,
      view:window, button:0, buttons: ten==='mouseup'?0:1, clientX:x, clientY:y}))
  },
  chon(i, them){
    const n = document.querySelectorAll('.react-flow__node')[i]
    const r = n.getBoundingClientRect(), x = r.x+40, y = r.y+12
    const o = {bubbles:true, cancelable:true, composed:true, view:window, button:0,
               clientX:x, clientY:y, ctrlKey: !!them}
    // d3-drag (React Flow dùng để chọn/kéo khối) nghe POINTER event, không phải
    // mouse event — thiếu hai dòng pointerdown/pointerup thì khối chỉ được chọn qua
    // đường click phụ và cờ "đang giữ Ctrl" không được đọc tới.
    const p = {...o, pointerId:1, pointerType:'mouse', isPrimary:true}
    n.dispatchEvent(new PointerEvent('pointerdown', {...p, buttons:1}))
    n.dispatchEvent(new MouseEvent('mousedown', {...o, buttons:1}))
    n.dispatchEvent(new PointerEvent('pointerup', {...p, buttons:0}))
    n.dispatchEvent(new MouseEvent('mouseup', {...o, buttons:0}))
    n.dispatchEvent(new MouseEvent('click', {...o, buttons:0}))
  },
  // React Flow biết "đang giữ Ctrl" qua keydown/keyup trên window, KHÔNG đọc ctrlKey
  // của sự kiện chuột. Và nó đưa trạng thái đó vào store bằng React state — CẬP NHẬT
  // BẤT ĐỒNG BỘ. Nên bấm phím và bấm chuột phải là hai nhịp riêng, có nghỉ ở giữa;
  // nhét chung một lần chạy JS thì cú click vẫn thấy "chưa giữ Ctrl".
  phim(k){ window.dispatchEvent(new KeyboardEvent('keydown',
      {key:k, ctrlKey:true, bubbles:true, cancelable:true})) },
  reChuot(x, y){ window.dispatchEvent(new MouseEvent('mousemove',
      {clientX:x, clientY:y, bubbles:true, view:window})) },
  khungCanvas(){ const r = document.querySelector('.vung-canvas').getBoundingClientRect()
                 return {x:r.x, y:r.y, w:r.width, h:r.height} },
  /** Góc trên-trái của mọi khối, theo toạ độ MÀN HÌNH. */
  gocKhoi(){ return [...document.querySelectorAll('.react-flow__node')]
               .map(n => { const r = n.getBoundingClientRect(); return {x:r.x, y:r.y} }) },
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

    def than():
        try:
            _web.cho_san_sang(js)
            _web.mo_mau(js)
            time.sleep(1.4)
            js(JS_TIEN_ICH)
            khung = json.loads(js("JSON.stringify(window.__C.khungCanvas())"))

            # --- 1. Dán một khối: phải rơi vào chỗ con trỏ ---
            n0 = js("window.__C.soKhoi()")
            js("window.__C.chon(0)")
            time.sleep(0.3)
            js("window.__C.phim('c')")
            time.sleep(0.3)
            # chọn một điểm trống hẳn ở nửa dưới canvas
            mx = int(khung["x"] + khung["w"] * 0.62)
            my = int(khung["y"] + khung["h"] * 0.66)
            js(f"window.__C.reChuot({mx}, {my})")
            time.sleep(0.2)
            js("window.__C.phim('v')")
            time.sleep(1.0)
            n1 = js("window.__C.soKhoi()")
            ghi.append(("Ctrl+C rồi Ctrl+V thêm được 1 khối", n1 == n0 + 1,
                        f"— {n0} → {n1} khối"))
            goc = json.loads(js("JSON.stringify(window.__C.gocKhoi())"))[-1]
            lech = max(abs(goc["x"] - mx), abs(goc["y"] - my))
            ghi.append(("khối dán ra nằm ngay chỗ con trỏ", lech <= 6,
                        f"— con trỏ ({mx}, {my}), khối ở ({round(goc['x'])}, "
                        f"{round(goc['y'])}), lệch {round(lech)}px"))

            # --- 2. Dán chỗ khác thì rơi chỗ khác (không dính vào bản gốc) ---
            mx2 = int(khung["x"] + khung["w"] * 0.18)
            my2 = int(khung["y"] + khung["h"] * 0.30)
            js(f"window.__C.reChuot({mx2}, {my2})")
            time.sleep(0.2)
            js("window.__C.phim('v')")
            time.sleep(1.0)
            goc2 = json.loads(js("JSON.stringify(window.__C.gocKhoi())"))[-1]
            lech2 = max(abs(goc2["x"] - mx2), abs(goc2["y"] - my2))
            ghi.append(("dán lần hai ở chỗ khác thì đi theo con trỏ", lech2 <= 6,
                        f"— lệch {round(lech2)}px"))
            ghi.append(("hai lần dán KHÔNG chồng lên nhau",
                        abs(goc2["x"] - goc["x"]) > 50, f"— cách nhau "
                        f"{round(abs(goc2['x'] - goc['x']))}px"))

            # --- 3. Con trỏ ngoài canvas -> giữa khung nhìn, vẫn nhìn thấy được ---
            js(f"window.__C.reChuot({int(khung['x'] + 200)}, {int(khung['y'] - 30)})")
            time.sleep(0.2)
            js("window.__C.phim('v')")
            time.sleep(1.0)
            goc3 = json.loads(js("JSON.stringify(window.__C.gocKhoi())"))[-1]
            giua_x, giua_y = khung["x"] + khung["w"] / 2, khung["y"] + khung["h"] / 2
            ghi.append(("con trỏ ở ngoài canvas → dán vào giữa khung nhìn",
                        max(abs(goc3["x"] - giua_x), abs(goc3["y"] - giua_y)) <= 6,
                        f"— giữa ({round(giua_x)}, {round(giua_y)}), khối ở "
                        f"({round(goc3['x'])}, {round(goc3['y'])})"))
            trong = (khung["x"] <= goc3["x"] <= khung["x"] + khung["w"]
                     and khung["y"] <= goc3["y"] <= khung["y"] + khung["h"])
            ghi.append(("  …và nằm trong vùng nhìn thấy được", trong))

            # Phần dán NHIỀU khối nằm ở `test_chep_dan_chuot.py`: chọn nhiều khối cần
            # React Flow thấy phím Ctrl ĐANG GIỮ, mà cờ đó nó lấy từ keydown/keyup thật
            # trên window — KeyboardEvent tổng hợp không dựng lại được (đã thử cả bắn
            # trên document lẫn tách thành nhiều nhịp). Chuột thật thì chọn đúng 2 khối.
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
