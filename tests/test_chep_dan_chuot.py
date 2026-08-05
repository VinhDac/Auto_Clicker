"""Dán NHIỀU khối cùng lúc — phần cần chuột thật.

`test_chep_dan_web.py` lo phần dán một khối (bắn sự kiện tổng hợp, chạy nhanh, không
đụng chuột). Riêng CHỌN NHIỀU thì phải có chuột thật: React Flow lấy cờ "đang giữ
Ctrl" từ keydown/keyup THẬT trên window, và KeyboardEvent tổng hợp không dựng lại
được cờ đó (đã thử bắn trên document, trên window, tách thành nhiều nhịp cho React kịp
flush — đều không ăn; với Ctrl thật thì chọn đúng 2 khối ngay).

Điều bài này giữ: dán một CỤM thì cụm phải rơi vào con trỏ mà vẫn giữ nguyên khoảng
cách giữa các khối. Văng mỗi cái một nơi thì coi như phải xếp lại từ đầu.

Bài này ĐIỀU KHIỂN CHUỘT THẬT -> nhóm CHUOT_THAT (chỉ chạy với --full).
"""
import _boot  # noqa: F401
import _web

import os
import sys
import time
import json
import ctypes
from ctypes import wintypes

import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.15

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANG = os.path.join(REPO, "webui", "dist", "index.html")

u = ctypes.windll.user32
u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
u.mouse_event.argtypes = [wintypes.DWORD] * 4 + [ctypes.c_void_p]
XUONG, LEN = 0x0002, 0x0004

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

    def bam(x, y):
        u.SetCursorPos(int(x), int(y))
        time.sleep(0.15)
        u.mouse_event(XUONG, 0, 0, 0, None)
        time.sleep(0.06)
        u.mouse_event(LEN, 0, 0, 0, None)
        time.sleep(0.35)

    def than():
        try:
            _web.cho_san_sang(js)
            _web.mo_mau(js)
            time.sleep(1.6)

            ra = []

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def d(h, _):
                n = u.GetWindowTextLengthW(h)
                if n and u.IsWindowVisible(h):
                    b = ctypes.create_unicode_buffer(n + 1)
                    u.GetWindowTextW(h, b, n + 1)
                    if "Auto Clicker" in b.value:
                        ra.append(h)
                return True

            u.EnumWindows(d, 0)
            h = ra[0]
            u.SetForegroundWindow(h)
            u.SetWindowPos(h, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
            time.sleep(1.2)
            pt = wintypes.POINT(0, 0)
            u.ClientToScreen(h, ctypes.byref(pt))

            def diem_khoi(i):
                r = json.loads(js(
                    "(()=>{const n=document.querySelectorAll('.react-flow__node')[%d];"
                    "const r=n.getBoundingClientRect();"
                    "return JSON.stringify({x:r.x+40,y:r.y+12})})()" % i))
                return pt.x + r["x"], pt.y + r["y"]

            def goc_khoi():
                return json.loads(js(
                    "JSON.stringify([...document.querySelectorAll('.react-flow__node')]"
                    ".map(n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y}}))"))

            def so_chon():
                return js("document.querySelectorAll('.react-flow__node.selected').length")

            khung = json.loads(js(
                "(()=>{const r=document.querySelector('.vung-canvas').getBoundingClientRect();"
                "return JSON.stringify({x:r.x,y:r.y,w:r.width,h:r.height})})()"))

            # --- chọn 2 khối bằng Ctrl+click thật ---
            bam(*diem_khoi(0))
            ghi.append(("bấm 1 khối → chọn đúng 1", so_chon() == 1, f"— {so_chon()}"))
            pyautogui.keyDown("ctrl")
            time.sleep(0.25)
            bam(*diem_khoi(1))
            time.sleep(0.25)
            pyautogui.keyUp("ctrl")
            time.sleep(0.4)
            ghi.append(("Ctrl+click thêm khối → chọn 2", so_chon() == 2, f"— {so_chon()}"))

            truoc_goc = goc_khoi()
            cach_goc = abs(truoc_goc[1]["x"] - truoc_goc[0]["x"])
            cao_goc = abs(truoc_goc[1]["y"] - truoc_goc[0]["y"])
            n0 = len(truoc_goc)

            # --- chép, rê chuột tới chỗ trống, dán ---
            pyautogui.hotkey("ctrl", "c")
            time.sleep(0.5)
            mx = int(pt.x + khung["x"] + khung["w"] * 0.28)
            my = int(pt.y + khung["y"] + khung["h"] * 0.74)
            u.SetCursorPos(mx, my)
            time.sleep(0.4)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(1.3)

            sau_goc = goc_khoi()
            ghi.append(("dán ra đúng 2 khối", len(sau_goc) == n0 + 2,
                        f"— {n0} → {len(sau_goc)} khối"))
            hai = sau_goc[-2:]
            cach_moi = abs(hai[1]["x"] - hai[0]["x"])
            cao_moi = abs(hai[1]["y"] - hai[0]["y"])
            ghi.append(("cụm dán ra giữ nguyên khoảng cách giữa các khối",
                        abs(cach_moi - cach_goc) <= 2 and abs(cao_moi - cao_goc) <= 2,
                        f"— gốc {round(cach_goc)}×{round(cao_goc)}px, "
                        f"bản dán {round(cach_moi)}×{round(cao_moi)}px"))
            trai = min(k["x"] for k in hai) + pt.x
            tren = min(k["y"] for k in hai) + pt.y
            ghi.append(("góc trên-trái của cả cụm rơi vào con trỏ",
                        max(abs(trai - mx), abs(tren - my)) <= 6,
                        f"— con trỏ ({mx}, {my}), cụm ở ({round(trai)}, {round(tren)})"))
            u.SetWindowPos(h, -2, 0, 0, 0, 0, 0x0001 | 0x0002)
        except Exception:
            import traceback
            ghi.append(("chạy được tới cuối", False, "\n" + traceback.format_exc(limit=4)))
        finally:
            # Ctrl kẹt là cả Windows dở chứng — thả cho chắc dù có lỗi gì đi nữa.
            try:
                pyautogui.keyUp("ctrl")
            except Exception:
                pass
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
