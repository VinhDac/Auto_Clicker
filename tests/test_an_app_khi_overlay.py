"""Overlay chọn-trên-màn-hình bật lên thì CỬA SỔ APP phải biến mất.

LỖI ĐÃ SỬA — và nó là kiểu lỗi khó thấy nhất sau khi đổi kiến trúc.

Bản tkinter cũ làm đúng việc này ở 4 chỗ: `self.root.withdraw()` trước khi mở overlay,
`deiconify()` sau khi xong. Lúc đó `root` chính là cửa sổ app.

Khi 4 overlay tách ra chạy TIẾN TRÌNH CON cho bản web, `overlays.py` vẫn có dòng
`root.withdraw()` trông y hệt và chú thích cũng nói đúng ý — nhưng `root` giờ là một
cửa sổ Tk rỗng của tiến trình con, chưa bao giờ hiện ra. Nó ẩn một thứ không tồn tại,
còn cửa sổ app thì không ai đụng tới.

Hậu quả có hai mặt, mặt sau nặng hơn:
  · overlay chỉ phủ 30-35% nên cửa sổ app hiện xuyên qua, che mất chỗ cần ngắm trong
    game — người dùng báo "che hết mất, rất khó dùng";
  · "Đọc thử" của khung Abyss và phần dò ô kho đều CHỤP MÀN HÌNH để OCR. Chúng tự ẩn
    overlay trước khi chụp (vốn đã có), nhưng cửa sổ app vẫn nằm nguyên đó. Đo được:
    chụp một vùng nằm trong cửa sổ app ra pixel (26,26,26) — đúng màu nền app. Tức là
    OCR đọc cửa sổ app chứ không đọc game, và KHÔNG có dấu hiệu gì báo sai.

Bài này KHÔNG mở overlay thật (cần desktop tương tác và chiếm cả màn hình). Nó thay
`subprocess.run` bằng bản giả, rồi hỏi Windows ngay tại thời điểm đó: cửa sổ app còn
hiện không. Đó đúng là câu hỏi cần trả lời, và trả lời được mà không cần chuột.
"""
import _boot  # noqa: F401
import _web

import os
import sys
import json
import time
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANG = os.path.join(REPO, "webui", "dist", "index.html")

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
    import api as mod_api

    api = mod_api.Api()
    win = webview.create_window("Auto Clicker", url=TRANG, js_api=api,
                                width=900, height=600, frameless=True, easy_drag=False)
    api._window = win
    ghi = []

    def than():
        try:
            _web.cho_san_sang(lambda s: win.evaluate_js(s))
            time.sleep(0.8)

            import ctypes
            from ctypes import wintypes
            u = ctypes.windll.user32
            tim = []

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def d(h, _):
                n = u.GetWindowTextLengthW(h)
                if n and u.IsWindowVisible(h):
                    b = ctypes.create_unicode_buffer(n + 1)
                    u.GetWindowTextW(h, b, n + 1)
                    if "Auto Clicker" in b.value:
                        tim.append(h)
                return True

            u.EnumWindows(d, 0)
            if not tim:
                ghi.append(("tìm được cửa sổ app", False))
                return
            api._khung.va(tim[0])
            time.sleep(0.5)
            ghi.append(("trước khi mở overlay, cửa sổ app đang hiện",
                        api._khung.dang_hien()))

            # Thay subprocess.run bằng bản giả: nó ghi lại "lúc overlay chạy thì cửa
            # sổ app còn hiện không" — đúng câu hỏi cần trả lời.
            luc_do = {}

            class KetQuaGia:
                returncode = 0
                stderr = b""

                def __init__(self, mode):
                    self.stdout = json.dumps(
                        {"ok": True, "value": [7, 9]}).encode("utf-8")

            def run_gia(lenh, **kw):
                luc_do["hien"] = api._khung.dang_hien()
                luc_do["mode"] = lenh[-1] if lenh else "?"
                return KetQuaGia(luc_do["mode"])

            that = mod_api.subprocess.run
            mod_api.subprocess.run = run_gia
            try:
                for ten_ham, goi in [("Chọn điểm", lambda: api.pick_point()),
                                     ("Căn khung Abyss", lambda: api.pick_abyss_frame()),
                                     ("Căn lưới kho", lambda: api.pick_inv_grid())]:
                    luc_do.clear()
                    r = goi()
                    ghi.append((f"[{ten_ham}] overlay chạy → cửa sổ app ĐÃ BIẾN MẤT",
                                luc_do.get("hien") is False,
                                f"— còn hiện: {luc_do.get('hien')}"))
                    ghi.append((f"[{ten_ham}] xong → cửa sổ app hiện lại",
                                api._khung.dang_hien()))
                    ghi.append((f"[{ten_ham}] vẫn trả về kết quả bình thường",
                                r.get("ok") is True, f"— {r}"))

                # Overlay CHẾT giữa chừng thì vẫn phải hiện app lại, nếu không app
                # coi như biến mất khỏi màn hình.
                def run_no(lenh, **kw):
                    luc_do["hien"] = api._khung.dang_hien()
                    raise subprocess.TimeoutExpired(lenh, 1)

                mod_api.subprocess.run = run_no
                luc_do.clear()
                r = api.pick_point()
                ghi.append(("overlay hết giờ → app VẪN hiện lại", api._khung.dang_hien()))
                ghi.append(("  …và báo lỗi tử tế, không ném exception",
                            r.get("ok") is False and "quá lâu" in (r.get("error") or "")))

                def run_rac(lenh, **kw):
                    class R:
                        returncode = 1
                        stdout = b"khong-phai-json"
                        stderr = b""
                    return R()

                mod_api.subprocess.run = run_rac
                r = api.pick_point()
                ghi.append(("overlay trả rác → app VẪN hiện lại", api._khung.dang_hien()))
                ghi.append(("  …và vẫn báo lỗi tử tế", r.get("ok") is False))
            finally:
                mod_api.subprocess.run = that
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
