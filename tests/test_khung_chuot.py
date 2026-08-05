"""Kéo / giãn / double-click cửa sổ — nghiệm thu bằng CHUỘT THẬT.

VÌ SAO BÀI NÀY PHẢI TỒN TẠI RIÊNG
---------------------------------
`test_thanh_tieu_de.py` từng có 4 check hỏi `SendMessage(WM_NCHITTEST)` thẳng vào cửa
sổ cha. Cả 4 đều xanh, tổng 25/25 — và app hoàn toàn không kéo, không giãn, không snap
được. Chúng đo SAI CÂU: "nếu được hỏi thì cha trả lời đúng không", chứ không phải
"Windows có hỏi cha không".

Đo ra mới thấy: WebView2 là cửa sổ CON phủ KÍN cửa sổ app
(`Chrome_RenderWidgetHostHWND` đúng bằng kích thước cửa sổ), nên Windows luôn hỏi nó
và nó trả HTCLIENT. Cửa sổ cha không bao giờ được hỏi.

Nên bài này KHÔNG hỏi cửa sổ nào cả. Nó thao tác chuột thật rồi xem KÍCH THƯỚC và VỊ
TRÍ cửa sổ có đổi không — thứ duy nhất không nói dối được.

Aero Snap vẫn không kiểm tự động được: control case (kéo y hệt một cửa sổ title bar
GỐC, 0 bước nhiễu) cũng không snap, nên input giả lập không dựng lại được cơ chế ấy.
Nhưng việc kéo giờ đi qua đúng `WM_NCLBUTTONDOWN`/HTCAPTION của Windows, nên snap là
việc của hệ điều hành, không còn phần nào của app trong đó.

Bài này CHIẾM CHUỘT ~40 giây -> nhóm CHUOT_THAT (chỉ chạy với --full).
"""
import _boot  # noqa: F401
import _web

_web.bo_qua_neu_khoa_man_hinh()

import io, os, sys, time, ctypes
from ctypes import wintypes
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import webview
from api import Api

u = ctypes.windll.user32
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.IsZoomed.argtypes = [wintypes.HWND]
u.mouse_event.argtypes = [wintypes.DWORD] * 4 + [ctypes.c_void_p]
MAN_W, MAN_H = u.GetSystemMetrics(0), u.GetSystemMetrics(1)

api = Api()
win = webview.create_window("Auto Clicker",
                            url=os.path.join(REPO, "webui", "dist", "index.html"),
                            js_api=api, width=1000, height=640,
                            frameless=True, easy_drag=False)
api._window = win
kq = []


def them(t, d, ct=""):
    kq.append((t, d, ct))


def doc():
    p = wintypes.POINT(); u.GetCursorPos(ctypes.byref(p)); return (p.x, p.y)


def dat(x, y):
    u.mouse_event(0x0001 | 0x8000, int(x * 65535 / MAN_W), int(y * 65535 / MAN_H), 0, None)
    time.sleep(0.05)
    return doc()


def kb():
    try:
        js = lambda s: win.evaluate_js(s)
        _web.cho_san_sang(js); time.sleep(1.0)
        tim = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def d(h, _):
            n = u.GetWindowTextLengthW(h)
            if n and u.IsWindowVisible(h):
                b = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, b, n + 1)
                if "Auto Clicker" in b.value: tim.append(h)
            return True
        u.EnumWindows(d, 0)
        h = tim[0]
        api._khung.va(h); time.sleep(0.6)
        u.SetForegroundWindow(h); time.sleep(0.8)

        # cho chuot yen
        t0 = time.perf_counter(); cuoi = doc(); tu = time.perf_counter(); yen = False
        while time.perf_counter() - t0 < 40:
            time.sleep(0.15); p = doc()
            if p != cuoi: cuoi, tu = p, time.perf_counter()
            elif time.perf_counter() - tu >= 2.0: yen = True; break
        them("chuột yên trước khi đo", yen)

        def keo(x1, y1, x2, y2, buoc=18):
            """Kéo thật từ (x1,y1) tới (x2,y2). Trả số bước con trỏ bị lệch."""
            dat(x1, y1); time.sleep(0.35)
            u.mouse_event(0x0002, 0, 0, 0, None); time.sleep(0.3)
            lech = 0
            for k in range(1, buoc + 1):
                nx = x1 + (x2 - x1) * k // buoc
                ny = y1 + (y2 - y1) * k // buoc
                gx, gy = dat(nx, ny)
                if abs(gx - nx) > 5 or abs(gy - ny) > 5: lech += 1
                time.sleep(0.04)
            time.sleep(0.45)
            u.mouse_event(0x0004, 0, 0, 0, None); time.sleep(0.9)
            return lech

        r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
        rong0, cao0 = r.right - r.left, r.bottom - r.top

        # ---- 1. GIÃN: kéo mép phải sang phải 160px ----
        lech = keo(r.right - 3, (r.top + r.bottom) // 2, r.right + 157, (r.top + r.bottom) // 2)
        u.GetWindowRect(h, ctypes.byref(r))
        them("không ai chạm chuột (giãn)", lech == 0, f"— {lech} bước lệch")
        them("KÉO MÉP PHẢI → cửa sổ rộng ra", abs((r.right - r.left) - rong0 - 160) <= 14,
             f"— {rong0}px → {r.right - r.left}px")

        # ---- 2. GIÃN: kéo mép dưới xuống 120px ----
        cao1 = r.bottom - r.top
        keo((r.left + r.right) // 2, r.bottom - 3, (r.left + r.right) // 2, r.bottom + 117)
        u.GetWindowRect(h, ctypes.byref(r))
        them("KÉO MÉP DƯỚI → cửa sổ cao ra", abs((r.bottom - r.top) - cao1 - 120) <= 14,
             f"— {cao1}px → {r.bottom - r.top}px")

        # ---- 3. KÉO CẢ CỬA SỔ bằng dải tiêu đề ----
        trai0 = r.left
        lech = keo((r.left + r.right) // 2, r.top + 16, (r.left + r.right) // 2 + 150, r.top + 16)
        u.GetWindowRect(h, ctypes.byref(r))
        them("không ai chạm chuột (kéo)", lech == 0, f"— {lech} bước lệch")
        them("KÉO DẢI TIÊU ĐỀ → cửa sổ dịch chuyển", abs(r.left - trai0 - 150) <= 14,
             f"— x {trai0} → {r.left}")

        # ---- 4. DOUBLE-CLICK dải tiêu đề → phóng to ----
        dat((r.left + r.right) // 2, r.top + 16); time.sleep(0.4)
        for _ in range(2):
            u.mouse_event(0x0002, 0, 0, 0, None); time.sleep(0.05)
            u.mouse_event(0x0004, 0, 0, 0, None); time.sleep(0.07)
        time.sleep(1.3)
        them("DOUBLE-CLICK dải tiêu đề → phóng to", bool(u.IsZoomed(h)),
             f"— IsZoomed={bool(u.IsZoomed(h))}")

        # ---- 5. double-click lần nữa → khôi phục ----
        u.GetWindowRect(h, ctypes.byref(r))
        dat((r.left + r.right) // 2, r.top + 16); time.sleep(0.4)
        for _ in range(2):
            u.mouse_event(0x0002, 0, 0, 0, None); time.sleep(0.05)
            u.mouse_event(0x0004, 0, 0, 0, None); time.sleep(0.07)
        time.sleep(1.3)
        them("double-click lần nữa → khôi phục", not u.IsZoomed(h), "— chỉ có nghĩa nếu bước trên đạt")

        # ---- 6. bấm vào MENU thì KHÔNG được kéo cửa sổ ----
        u.GetWindowRect(h, ctypes.byref(r))
        xm = js("(()=>{const b=document.querySelector('.menu-tren');"
                "const q=b.getBoundingClientRect();return Math.round(q.left+q.width/2)})()")
        trai1 = r.left
        keo(r.left + xm, r.top + 16, r.left + xm + 120, r.top + 16, buoc=10)
        u.GetWindowRect(h, ctypes.byref(r))
        them("bấm vào MENU thì cửa sổ KHÔNG bị kéo", abs(r.left - trai1) <= 4,
             f"— x {trai1} → {r.left}")
    except Exception:
        import traceback; them("chạy tới cuối", False, "\n" + traceback.format_exc(limit=4))
    finally:
        try: u.mouse_event(0x0004, 0, 0, 0, None)
        except Exception: pass
        win.destroy()


webview.start(kb, debug=False, http_server=True)
print()
for t, d, ct in kq:
    print(f"  {'✔' if d else '✘'} {t} {ct}")
print(f"\n  {sum(1 for _, d, _ in kq if d)}/{len(kq)} đạt")
