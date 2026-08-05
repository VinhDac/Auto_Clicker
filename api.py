"""Bề mặt DUY NHẤT mà giao diện web được phép gọi.

    React UI  ──►  api.py  ──►  core.py
                              (KHÔNG ĐỔI)

Luật cứng của tầng này:

1. **JS không bao giờ tự biết định dạng file.** Nó chỉ gửi/nhận JSON và hỏi ở đây.
   Mọi hiểu biết về `schema`, `type`, tên khoá... nằm trong `core.py`. Một nơi biết
   một thứ — nếu không, sửa định dạng sẽ phải sửa hai chỗ và một chỗ sẽ bị quên.
2. **Không import tkinter.** Ba overlay chọn-trên-màn-hình được gọi ra TIẾN TRÌNH CON
   (`overlays.py`), vì tkinter và pywebview mỗi bên đòi một vòng lặp sự kiện.
3. **Mọi hàm ở đây test được bằng Python thuần**, không cần mở cửa sổ. Đây là cách bù
   lại số test giao diện tkinter sẽ mất khi chuyển sang web.
4. **Không bao giờ ném exception sang JS.** Mọi hàm trả `{"ok": bool, ...}` để phía
   giao diện luôn có thứ để hiển thị, thay vì một promise bị reject không ai bắt.
"""
import os
import sys
import json
import queue
import threading
import subprocess
import traceback

import core
import khung_cua_so

# Chạy từ nguồn thì overlay là "python overlays.py <mode>".
# Đóng gói .exe thì không có python.exe -> gọi lại CHÍNH exe đó với cờ --overlay,
# và `app_web.py` bắt cờ này ngay đầu chương trình rồi chuyển cho overlays.main().
# Xử lý luôn từ bây giờ vì phát hiện ở khâu đóng gói thì sửa rất phiền.
FROZEN = getattr(sys, "frozen", False)


def _lenh_overlay(mode, extra=()):
    if FROZEN:
        return [sys.executable, "--overlay", mode, *extra]
    here = os.path.dirname(os.path.abspath(__file__))
    return [sys.executable, os.path.join(here, "overlays.py"), mode, *extra]


def _hanh_dong_mac_dinh(loai):
    """Hành động mới, ĐẦY ĐỦ trường bắt buộc.

    Không trả về `{"type": ...}` trơ trọi: `action_summary` đọc thẳng `a["point"]`
    nên một hành động click thiếu toạ độ làm nổ KeyError ngay lúc vẽ hộp.

    Điểm mặc định đặt giữa màn hình, KHÔNG phải (0, 0): góc trên-trái là chốt
    FAILSAFE của pyautogui — lỡ bấm Chạy trước khi kịp chọn điểm thì (0,0) sẽ ném
    FailSafeException giữa chừng thay vì click một chỗ vô hại.
    """
    x, y, w, h = core.virtual_screen_rect()
    giua = [x + w // 2, y + h // 2]
    if loai in ("left_click", "right_click"):
        return {"type": loai, "point": giua}
    if loai == "mod_click":
        return {"type": loai, "point": giua, "keys": "shift", "button": "left"}
    if loai in ("check_mod", core.CONFIRM_MOD):
        return {"type": loai, "point": giua, "conditions": []}
    if loai == "abyss":
        return {"type": loai, "conditions": [], "excludes": []}
    if loai == "key_press":
        return {"type": loai, "key": "escape"}
    if loai == "move_wasd":
        return {"type": loai, "keys": "w", "ms": 500}
    if loai == "delay":
        return {"type": loai, "min_ms": 50, "max_ms": 120}
    return {"type": loai}


def _the_buoc(step):
    """Một bước -> dữ liệu vẽ hộp trên canvas.

    Trả về DỮ LIỆU, không phải HTML: phía web tự quyết trình bày thế nào, nhưng mọi
    chuỗi mô tả đều do core sinh ra để hai giao diện không bao giờ nói khác nhau.
    """
    kind = step.get("kind")
    tieu_de = core.step_title(step)
    hd = step.get("actions") or []

    if kind == "loop":
        bat_dau = max(0, min(int(step.get("loop_start_index") or 0), len(hd)))
        giu = core.parse_hold_keys(step.get("hold_keys"))
        nhan = [f"tối đa {step.get('max_loops', core.DEFAULT_MAX_LOOPS)} vòng"]
        if giu:
            nhan.append("⇧ giữ " + "+".join(giu))
        dong = [{"text": core.action_display(a),
                 # `type` để giao diện chọn ICON. Python nói ĐÓ LÀ GÌ, web quyết VẼ GÌ.
                 "type": a.get("type"),
                 # "prologue" = chạy 1 lần lúc đầu, nằm TRƯỚC dấu "Loop từ đây".
                 # Hộp phải cho thấy điều này, nếu không nhìn hộp không biết Loop
                 # thật sự lặp lại những gì.
                 "prologue": i < bat_dau,
                 "goal": a.get("type") in core.GOAL_TYPES}
                for i, a in enumerate(hd)]
    elif kind == "group":
        nhan = ["chạy 1 lần"]
        dong = [{"text": core.action_display(a), "type": a.get("type"), "prologue": False,
                 "goal": a.get("type") in core.GOAL_TYPES} for a in hd]
    else:
        nhan = ["chạy 1 lần"]
        dong = [{"text": core.action_display(step), "type": step.get("type"),
                 "prologue": False,
                 "goal": step.get("type") in core.GOAL_TYPES}]

    return {
        "id": step.get("id"),
        "kind": kind,
        "title": tieu_de,
        "badges": nhan,
        "lines": dong,
        "so_hanh_dong": len(hd) if kind in ("loop", "group") else 1,
        "co_muc_tieu": any(d["goal"] for d in dong),
    }


def _bat_loi(fn):
    """Bọc mọi hàm public: lỗi thành dữ liệu, không thành exception xuyên qua cầu nối."""
    def wrap(*a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as e:
            return {"ok": False,
                    "error": f"{type(e).__name__}: {e}",
                    "trace": traceback.format_exc(limit=6)}
    wrap.__name__ = fn.__name__
    wrap.__doc__ = fn.__doc__
    return wrap


class Api:
    """Đối tượng được gắn vào `window.pywebview.api` phía JS."""

    def __init__(self):
        # ⚠ MỌI thuộc tính không-phải-hàm PHẢI bắt đầu bằng "_".
        #
        # pywebview dựng danh sách hàm cho JS bằng `get_functions()` (webview/util.py):
        # nó duyệt `dir(js_api)` và ĐỆ QUY vào mọi thuộc tính không callable. Gán
        # `self._window = <Window>` làm nó bò vào chính đối tượng cửa sổ và đọc các
        # property như `width`/`x`/`title` — mà mấy property đó hỏi ngược luồng giao
        # diện, đúng luồng đang bị chặn để chờ. Kết quả: cửa sổ KHÔNG BAO GIỜ bơm
        # thông điệp nữa, Windows báo "Not Responding". Tên có "_" thì bị bỏ qua.
        self._window = None           # app_web.py gán vào sau khi tạo cửa sổ
        self._stop_flag = threading.Event()
        self._runner = None
        self._thread = None
        self._hang = queue.Queue()    # hàng đợi dòng nhật ký
        self._trang_thai = None
        self._hotkey = None
        self._hotkey_raw = None
        # Trạng thái vá khung cửa sổ (thanh tiêu đề tự vẽ). Tên có '_' như mọi thuộc
        # tính khác ở đây: pywebview đệ quy vào thuộc tính CÔNG KHAI của js_api để
        # dựng danh sách hàm, chạm phải đối tượng không gọi được là treo cứng.
        self._khung = khung_cua_so.KhungTuVe()
        self._log_khoi_dong = lambda m: None      # app_web gắn vào

    # ---------------- đẩy sự kiện sang JS ----------------
    def _ban(self, ten, du_lieu):
        """Gọi `window.__su_kien(ten, dulieu)` bên JS. Nuốt mọi lỗi: cửa sổ có thể
        đã đóng giữa chừng, mà worker thì không được phép chết vì chuyện đó."""
        if not self._window:
            return
        try:
            self._window.evaluate_js(
                f"window.__su_kien && window.__su_kien({json.dumps(ten)},"
                f"{json.dumps(du_lieu, ensure_ascii=False)})")
        except Exception:
            pass

    def _bom_nhat_ky(self):
        """Gom nhật ký rồi đẩy THÀNH LÔ mỗi 150ms.

        Mỗi `evaluate_js` là một vòng qua cầu nối; một vòng lặp nhanh có thể sinh
        hàng chục dòng mỗi giây, đẩy từng dòng một sẽ ngốn hết thời gian của luồng
        giao diện. Bản tkinter cũng phải làm đúng thế này với `root.after`."""
        while True:
            dong = []
            try:
                dong.append(self._hang.get(timeout=0.15))
            except queue.Empty:
                pass
            while True:
                try:
                    dong.append(self._hang.get_nowait())
                except queue.Empty:
                    break
            goi = {}
            if dong:
                goi["log"] = dong
            if self._trang_thai is not None:
                goi["status"] = self._trang_thai
                self._trang_thai = None
            if goi:
                self._ban("run", goi)
            if dong and dong[-1].get("het"):
                return
            if not self._thread or not self._thread.is_alive():
                # worker chết rồi mà hàng đợi cũng cạn -> thoát, đừng quay vòng mãi
                if self._hang.empty():
                    return

    # ---------------- phím dừng toàn cục ----------------
    def _dat_hotkey(self, phim):
        """Đăng ký HAI kiểu, cố ý.

        `add_hotkey` khớp ĐÚNG tổ hợp đang giữ, nên khi Loop đang giữ Shift thì F6 bị
        hiểu là Shift+F6 và không khớp — hỏng đúng lúc cần dừng nhất. `on_press_key`
        bắt theo scan code nên kệ phím bổ trợ."""
        try:
            self._hotkey = core.keyboard.add_hotkey(phim, self._stop_flag.set)
        except Exception:
            self._hotkey = None
        try:
            self._hotkey_raw = core.keyboard.on_press_key(phim, lambda _e: self._stop_flag.set())
        except Exception:
            self._hotkey_raw = None

    def _go_hotkey(self):
        for h, go in ((self._hotkey, core.keyboard.remove_hotkey),
                      (self._hotkey_raw, core.keyboard.unhook_key)):
            if h is not None:
                try:
                    go(h)
                except Exception:
                    pass
        self._hotkey = self._hotkey_raw = None

    # ---------------- chạy / dừng ----------------
    @_bat_loi
    def run(self, name, steps, edges=None, start_delay=3, bo_qua_canh_bao=False):
        """Chạy cả Process trong luồng riêng.

        `edges` BẮT BUỘC phải truyền vào từ giao diện. Trước đây hàm này không nhận
        `edges` và hậu quả rất nặng, im lặng, không test nào bắt được:
          · `validate_process` bị gọi thiếu `edges` -> TOÀN BỘ phần soát đồ thị (luật
            rẽ nhánh, vòng lặp, id trùng, khối không tới được) bị bỏ qua trước khi chạy;
          · `cfg` không có khoá `edges` -> bộ chạy rơi về `default_edges` = CHUỖI THẲNG
            theo thứ tự danh sách, tức bỏ qua sạch mọi đường nối người dùng vẽ.
        Nói cách khác: bấm Chạy thì rẽ nhánh không tồn tại. Sơ đồ vẽ một đằng, app
        chạy một nẻo — đúng thứ mà cả hệ thống đánh số sinh ra để chống.

        Trả về ngay lập tức — KHÔNG chờ chạy xong. Nếu chờ thì cầu nối bị khoá và cả
        giao diện đứng hình suốt lúc chạy (có thể hàng giờ), kể cả nút Dừng.
        Diễn biến đẩy về JS qua sự kiện "run".
        """
        if self._thread and self._thread.is_alive():
            return {"ok": False, "error": "đang chạy rồi"}
        steps = steps or []
        if not steps:
            return {"ok": False, "error": "Process chưa có bước nào"}

        probs = core.validate_process(steps, edges=edges)
        loi = [p for p in probs if p.get("severity") == "error"]
        canh_bao = [p for p in probs if p.get("severity") != "error"]
        if loi:
            return {"ok": False, "error": "Không chạy được — hãy sửa lỗi trước",
                    "loi": loi}
        if canh_bao and not bo_qua_canh_bao:
            # Trả về để JS hỏi lại, thay vì tự quyết hộ người dùng.
            return {"ok": False, "can_hoi": True, "canh_bao": canh_bao}

        s = core.load_settings()
        cfg = {
            "name": name or "Process 1",
            "game": s.get("game", "poe2"),
            "steps": steps,
            "edges": edges,
            "start_delay": max(0, int(start_delay or 0)),
            "pre_click_ms": int(s.get("pre_click_ms", 60)),
            "hover_ms": int(s.get("hover_ms", 250)),
            "copy_keys": s.get("copy_keys", "ctrl+c"),
            "stop_hotkey": s.get("stop_hotkey", "f6"),
        }

        self._stop_flag.clear()
        while not self._hang.empty():        # dọn hàng đợi của lần chạy trước
            self._hang.get_nowait()
        self._dat_hotkey(cfg["stop_hotkey"])

        def ghi_trang_thai(m):
            self._trang_thai = m

        def ghi_log(m, tag=None):
            self._hang.put({"msg": m, "tag": tag})

        def cong_viec():
            trang_thai = "Đã dừng"
            so_vong = 0
            try:
                self._runner = core.ProcessRunner(cfg, self._stop_flag,
                                                  on_status=ghi_trang_thai, on_log=ghi_log)
                trang_thai, so_vong = self._runner.run()
            except BaseException as e:
                # BẮT BUỘC bắt: đây là luồng phụ, lỗi lọt ra là luồng chết ÂM THẦM,
                # nút Chạy kẹt mờ và phím dừng toàn cục không bao giờ được gỡ.
                trang_thai = f"⛔ Lỗi bất ngờ: {type(e).__name__}: {e}"
                ghi_log(traceback.format_exc(limit=6), "err")
            finally:
                try:
                    if self._runner:
                        self._runner.release_held_keys()
                finally:
                    self._go_hotkey()
                self._hang.put({"msg": trang_thai, "tag": "ok", "het": True,
                                "so_vong": so_vong})

        self._thread = threading.Thread(target=cong_viec, daemon=True)
        self._thread.start()
        threading.Thread(target=self._bom_nhat_ky, daemon=True).start()
        return {"ok": True, "value": {"hotkey": cfg["stop_hotkey"].upper()}}

    @_bat_loi
    def stop(self):
        self._stop_flag.set()
        return {"ok": True}

    @_bat_loi
    def dang_chay(self):
        return {"ok": True, "value": bool(self._thread and self._thread.is_alive())}

    def dong_app(self):
        """app_web.py gọi khi đóng cửa sổ: dừng chạy, thả phím, gỡ hotkey.
        Không có bước này thì Shift có thể kẹt trong cả Windows sau khi tắt app."""
        self._stop_flag.set()
        try:
            if self._runner:
                self._runner.release_held_keys()
        except Exception:
            pass
        self._go_hotkey()

    # ---------------- khởi động ----------------
    @_bat_loi
    def ping(self):
        return {"ok": True, "value": "pong"}

    @_bat_loi
    def set_title(self, ten_process):
        """Ghi tên Process lên THANH TIÊU ĐỀ cửa sổ — "Process mẫu — Auto Clicker".

        Đây là chỗ đúng của tên tài liệu (Paint: "Untitled - Paint"). Trước đây thanh
        tiêu đề chỉ lặp lại tên app — thứ người dùng đã biết — còn tên Process thì
        chiếm 263px của một dải ngang riêng."""
        if self._window:
            t = (ten_process or "").strip()
            self._window.set_title(f"{t} — Auto Clicker" if t else "Auto Clicker")
        return {"ok": True}

    @_bat_loi
    def bootstrap(self):
        """Mọi thứ giao diện cần ngay khi mở, gói trong MỘT lần gọi.

        Cố ý gộp: mỗi lần qua cầu nối là một vòng promise, gọi 6 lần lúc khởi động
        thì thấy rõ độ trễ. Dữ liệu ở đây đều nhỏ và ít đổi.
        """
        s = core.load_settings()
        return {"ok": True, "value": {
            "settings": s,
            "phien_ban": core.PHIEN_BAN,
            "action_types": list(core.ACTION_TYPES),
            "action_labels": dict(core.ACTION_LABELS),
            "template_kinds": list(core.TEMPLATE_KINDS),
            "goal_types": list(core.GOAL_TYPES),
            "point_types": list(core.POINT_TYPES),
            "mod_keys": list(core.MOD_KEYS),
            "hybrid_labels": dict(core.HYBRID_LABELS),
            "abyss_max_rerolls": core.ABYSS_MAX_REROLLS,
            "games": dict(core.GAMES),
            "accent_presets": {
                "Cam": "#ffa657", "Xanh dương": "#4a9eff", "Lục": "#3fb950",
                "Tím": "#a371f7", "Đỏ": "#f85149", "Vàng": "#d29922",
                "Hồng": "#db61a2", "Xanh ngọc": "#39c5cf",
            },
            "default_max_loops": core.DEFAULT_MAX_LOOPS,
            "screen": list(core.virtual_screen_rect()),
            "has_clip": bool(core.HAS_CLIP),
            "has_screen": bool(core.HAS_SCREEN),
            "has_ocr": bool(core.HAS_OCR),
            "ocr_reason": core.ocr_unavailable_reason(),
            "app_dir": core.app_dir(),
        }}

    # ---------------- nội dung hiển thị trên hộp ----------------
    @_bat_loi
    def describe(self, steps):
        """Sinh NỘI DUNG hộp cho từng bước, bằng chính hàm mô tả mà bản tkinter dùng.

        Cố ý không để JS tự ghép chuỗi kiểu `"Trái-click @ (x, y)"`: mô tả hành động đã
        có `core.action_display()` lo, gồm cả tên do người dùng đặt và mọi trường hợp
        lắt léo của 8 loại hành động. Chép lại sang JS là cầm chắc hai bên lệch nhau
        ngay lần thêm loại hành động thứ 9.
        """
        return {"ok": True, "value": [_the_buoc(s) for s in (steps or [])]}

    # ---------------- hộp thoại hành động ----------------
    @_bat_loi
    def save_action(self, draft):
        """Kiểm tra 1 hành động do form gửi lên, trả về bản SẠCH + dòng mô tả.

        Dùng chung `core.build_action` với hộp thoại tkinter, nên hai giao diện không
        thể bất đồng về việc thế nào là một hành động hợp lệ.
        """
        a, loi = core.build_action(draft or {})
        if loi:
            return {"ok": False, "error": loi}
        return {"ok": True, "value": {"action": a, "display": core.action_display(a)}}

    @_bat_loi
    def describe_actions(self, actions):
        """Dòng mô tả cho danh sách hành động bên trong 1 Loop/Nhóm."""
        return {"ok": True,
                "value": [{"text": core.action_display(a), "type": a.get("type")}
                          for a in (actions or [])]}

    @_bat_loi
    def describe_conditions(self, conds, kind="check_mod"):
        """Dòng mô tả cho bảng điều kiện. `cond_display` biết cả tier lẫn thuần/hybrid,
        `abyss_cond_display` biết ngưỡng số — JS đừng tự ghép lại mấy thứ đó."""
        f = core.abyss_cond_display if kind == "abyss" else core.cond_display
        return {"ok": True, "value": [f(c) for c in (conds or [])]}

    # ---------------- cửa sổ (thanh tiêu đề tự vẽ) ----------------
    @_bat_loi
    def vung_khong_keo(self, vung, cao):
        """Web báo chỗ nào trên thanh tiêu đề là logo/menu/nút — đừng coi là caption.

        Phải gọi lại mỗi khi cửa sổ đổi kích thước: cụm 3 nút bám mép phải nên toạ độ
        của nó đổi theo. Không cập nhật thì bấm nút Đóng lại hoá ra kéo cửa sổ."""
        self._khung.dat_vung_cam(vung, cao)
        return {"ok": True, "value": None}

    @_bat_loi
    def mo_trang(self, url):
        """Mở một địa chỉ web bằng TRÌNH DUYỆT THẬT của máy.

        Không dùng `window.open` bên JS: WebView2 không có sẵn handler cho cửa sổ mới
        nên lời gọi đó lặng lẽ không làm gì — nút bấm vào không phản ứng, đúng kiểu
        lỗi vặt khó chịu nhất. Chỉ nhận http/https, khỏi mở nhầm thứ khác."""
        u = str(url or "")
        if not (u.startswith("http://") or u.startswith("https://")):
            return {"ok": False, "error": f"địa chỉ không hợp lệ: {u[:40]}"}
        import webbrowser
        webbrowser.open(u)
        return {"ok": True, "value": None}

    @_bat_loi
    def keo_cua_so(self, ht):
        """Web báo "người dùng vừa bấm giữ ở dải tiêu đề / sát mép" -> Windows tự kéo.

        `ht` là mã vùng: 2 = kéo cả cửa sổ, 10..17 = giãn theo từng cạnh/góc."""
        return {"ok": True, "value": self._khung.bat_dau_keo(ht)}

    @_bat_loi
    def cua_so_thu_nho(self):
        self._window.minimize()
        return {"ok": True, "value": None}

    @_bat_loi
    def cua_so_phong_to(self):
        """Phóng to / khôi phục. Trả về trạng thái MỚI để nút đổi icon cho đúng."""
        self._khung.phong_to_hay_khoi_phuc(self._window)
        return {"ok": True, "value": self._khung.dang_phong_to()}

    @_bat_loi
    def cua_so_dang_phong_to(self):
        return {"ok": True, "value": self._khung.dang_phong_to()}

    @_bat_loi
    def cua_so_dong(self):
        self.dong_app()
        self._window.destroy()
        return {"ok": True, "value": None}

    @_bat_loi
    def ghi_phim(self, key, code=""):
        """Người dùng bấm một phím thật -> tên phím pyautogui.

        JS chỉ chuyển nguyên `event.key` / `event.code` sang chứ KHÔNG tự quy đổi:
        thứ chạy được hay không là do pyautogui quyết, mà chỉ Python nhìn thấy nó."""
        ten, loi = core.key_from_browser(key, code)
        if loi:
            return {"ok": False, "error": loi}
        return {"ok": True, "value": ten}

    @_bat_loi
    def action_defaults(self, action_type):
        """Giá trị mặc định khi đổi sang một loại hành động khác trong hộp thoại."""
        return {"ok": True, "value": _hanh_dong_mac_dinh(action_type)}

    # ---------------- template ----------------
    @_bat_loi
    def list_templates(self, kind="process"):
        """CHỈ trả về TÊN. `core.list_templates` trả (tên, đường_dẫn) — đường dẫn đĩa
        không có việc gì phải sang tới JS; nó mở template bằng tên, còn chuyện file
        nằm đâu là chuyện của core."""
        return {"ok": True, "value": [ten for ten, _ in core.list_templates(kind)]}

    @_bat_loi
    def new_process(self):
        """Process rỗng — dùng khi mở app lần đầu (khung trắng)."""
        s = core.load_settings()
        doc = core.make_process_template("Process 1", s.get("game", "poe2"), 3, [])
        return {"ok": True, "value": {"name": doc["name"], "start_delay": doc["start_delay"],
                                      "steps": [], "edges": [], "cards": []}}

    @_bat_loi
    def new_step(self, kind="loop", action_type="left_click"):
        """Tạo 1 bước mới ĐÚNG chuẩn của core (có id, có đủ trường mặc định).

        JS không tự nặn dict bước: mặc định của Loop (max_loops, loop_start_index,
        hold_keys) là kiến thức của core, chép sang JS là hai bên bắt đầu trôi khỏi nhau.
        """
        if kind == "loop":
            st = core.make_loop_step("Loop mới")
        elif kind == "group":
            st = core.make_group_step("Nhóm mới")
        elif kind == "action":
            if action_type not in core.ACTION_TYPES:
                return {"ok": False, "error": f'Không có loại hành động "{action_type}"'}
            st = core.make_action_step(_hanh_dong_mac_dinh(action_type))
        else:
            return {"ok": False, "error": f'Không có loại khối "{kind}"'}
        return {"ok": True, "value": {"step": st, "card": _the_buoc(st)}}

    @_bat_loi
    def clone_steps(self, steps):
        """Nhân bản một nhóm bước: bản sao SÂU, id MỚI, kèm bảng tra id cũ→mới.

        Cấp id ở đây chứ không để JS tự nặn chuỗi: định dạng id là kiến thức của
        `core.new_step_id()`. Trước đây `nhanBan` bên JS tự sinh `'c'+random` — chạy
        được, nhưng là hai nơi cùng quyết một thứ.

        Bảng `map` để bên gọi nối lại các ĐƯỜNG NỐI giữa những bước vừa chép: chép 3
        khối đang nối nhau mà mất đường nối thì coi như chép hụt.
        """
        import copy as _copy
        ra, bang = [], {}
        for st in (steps or []):
            moi = _copy.deepcopy(st)
            cu = moi.get("id")
            moi["id"] = core.new_step_id()
            if cu:
                bang[cu] = moi["id"]
            ra.append(moi)
        return {"ok": True, "value": {"steps": ra, "map": bang,
                                      "cards": [_the_buoc(s) for s in ra]}}

    @_bat_loi
    def demo_process(self):
        """Process mẫu để NHÌN THỬ giao diện khi máy chưa có template nào.

        Không ghi ra đĩa. Chỉ để P1 có thứ thật mà đánh giá — hộp rỗng thì không biết
        được kích thước hộp đã hợp lý chưa.
        """
        roll = core.make_loop_step("Roll Alteration")
        roll["max_loops"] = 1000
        roll["hold_keys"] = "shift"
        roll["loop_start_index"] = 1
        roll["actions"] = [
            {"type": "left_click", "point": [960, 540], "name": "Mở túi đồ"},
            {"type": "right_click", "point": [1520, 300]},
            {"type": "left_click", "point": [740, 446]},
            {"type": "delay", "min_ms": 20, "max_ms": 50},
            {"type": "check_mod", "point": [740, 446],
             "conditions": [{"mod": "# to maximum Life", "tier": 1}]},
        ]
        cat = core.make_group_step("Cất item vào stash")
        cat["actions"] = [
            {"type": "mod_click", "point": [740, 446], "keys": "ctrl", "button": "left"},
            {"type": "key_press", "key": "escape"},
        ]
        di = core.make_action_step({"type": "move_wasd", "keys": "w+a", "ms": 800,
                                    "name": "Đi tới thợ rèn"})
        buoc = [roll, cat, di]
        for i, s in enumerate(buoc):
            # Cách 420px cho hộp rộng 296px -> còn ~124px trống để đường nối có chỗ
            # cong. Đặt sát nhau thì đường nối co thành mẩu ngoằn ngoèo, nhìn như lỗi.
            s["pos"] = [80 + i * 420, 120]
        return {"ok": True, "value": {
            "name": "Process mẫu", "start_delay": 3,
            "steps": buoc, "edges": core.default_edges(buoc),
            "cards": [_the_buoc(s) for s in buoc]}}

    @_bat_loi
    def load_process(self, name):
        """Đọc 1 template Process theo TÊN (không phải đường dẫn — JS không cần biết
        template nằm ở đâu trên đĩa)."""
        path = core.template_path("process", name)
        if not os.path.exists(path):
            return {"ok": False, "error": f'Không có template Process tên "{name}"'}
        data = core.normalize_process(core.read_json(path))
        data["cards"] = [_the_buoc(s) for s in data["steps"]]
        return {"ok": True, "value": data}

    # ---------------- mở / lưu ra FILE bất kỳ ----------------
    # Bản tkinter có "📄 Lưu ra file khác…" / "📄 Mở từ file khác…" / "📂 Duyệt file
    # khác…" để làm việc với file nằm ngoài thư mục templates/ (chép từ bạn bè, để
    # trên Desktop…). Dùng hộp thoại file NATIVE của pywebview, không tự chế.
    _LOC = ("Template Auto Clicker (*.json)", "*.json")

    @_bat_loi
    def open_process_file(self):
        if not self._window:
            return {"ok": False, "error": "chưa sẵn sàng"}
        ds = self._window.create_file_dialog(0, file_types=(self._LOC,))   # OPEN_DIALOG
        if not ds:
            return {"ok": False}                    # người dùng bấm Huỷ — không phải lỗi
        data = core.normalize_process(core.read_json(ds[0]))
        data["cards"] = [_the_buoc(s) for s in data["steps"]]
        return {"ok": True, "value": data}

    @_bat_loi
    def save_process_file(self, name, steps, edges=None, start_delay=3):
        if not self._window:
            return {"ok": False, "error": "chưa sẵn sàng"}
        goi_y = core.safe_filename(name or "Process 1") + ".json"
        d = self._window.create_file_dialog(2, save_filename=goi_y,   # SAVE_DIALOG
                                            file_types=(self._LOC,))
        if not d:
            return {"ok": False}
        path = d if isinstance(d, str) else d[0]
        if not path.lower().endswith(".json"):
            path += ".json"
        s = core.load_settings()
        core.write_json(path, core.make_process_template(
            name, s.get("game", "poe2"), start_delay, steps or [], edges))
        return {"ok": True, "value": {"path": path}}

    @_bat_loi
    def insert_step_file(self, kind):
        """Chèn 1 Loop/Nhóm từ file bất kỳ ngoài thư mục templates/."""
        if not self._window:
            return {"ok": False, "error": "chưa sẵn sàng"}
        ds = self._window.create_file_dialog(0, file_types=(self._LOC,))
        if not ds:
            return {"ok": False}
        data = core.read_json(ds[0])
        st = (core.normalize_loop_template(data) if kind == "loop"
              else core.normalize_group_template(data))
        if st is None:
            khac = "Mở Process" if data.get("type") == "process" else "menu tương ứng"
            return {"ok": False,
                    "error": f"File này không phải template {kind} — hãy dùng {khac}."}
        st["id"] = core.new_step_id()
        return {"ok": True, "value": {"step": st, "card": _the_buoc(st)}}

    @_bat_loi
    def delete_template(self, kind, name):
        path = core.template_path(kind, name)
        if not os.path.exists(path):
            return {"ok": False, "error": f'Không có template "{name}"'}
        os.remove(path)
        return {"ok": True}

    @_bat_loi
    def save_step_template(self, kind, name, step):
        """Lưu RIÊNG một Loop hoặc một Nhóm thành template dùng lại được."""
        ten = (name or "").strip()
        if not ten:
            return {"ok": False, "error": "Tên template không được để trống"}
        s = core.load_settings()
        if kind == "loop":
            if step.get("kind") != "loop":
                return {"ok": False, "error": "Bước đang chọn không phải Action_Loop"}
            doc = core.make_loop_template(step, s.get("game", "poe2"))
        elif kind == "group":
            if step.get("kind") != "group":
                return {"ok": False, "error": "Bước đang chọn không phải Nhóm HĐ 1 lần"}
            doc = core.make_group_template(step, s.get("game", "poe2"))
        else:
            return {"ok": False, "error": f'Loại template không hợp lệ: "{kind}"'}
        core.write_json(core.template_path(kind, ten), doc)
        return {"ok": True, "value": {"name": ten}}

    @_bat_loi
    def insert_step_template(self, kind, name):
        """Đọc 1 template Loop/Nhóm để CHÈN vào Process đang mở.

        Chèn nhầm loại thì báo rõ phải dùng menu nào — `normalize_*_template` trả None
        cho file sai loại, nên nhầm lẫn bị bắt chứ không âm thầm làm méo dữ liệu."""
        path = core.template_path(kind, name)
        if not os.path.exists(path):
            return {"ok": False, "error": f'Không có template "{name}"'}
        data = core.read_json(path)
        st = (core.normalize_loop_template(data) if kind == "loop"
              else core.normalize_group_template(data))
        if st is None:
            khac = "Mở Process" if data.get("type") == "process" else "menu tương ứng"
            return {"ok": False,
                    "error": f'"{name}" không phải template {kind} — hãy dùng {khac}.'}
        st["id"] = core.new_step_id()
        return {"ok": True, "value": {"step": st, "card": _the_buoc(st)}}

    @_bat_loi
    def review_points(self, steps):
        """Phủ màn hình, vẽ MỌI điểm sẽ được click — để soi lại trước khi chạy.

        Gom điểm ở đây (Python) chứ không ở JS: riêng Abyss không có một điểm mà cả
        một khung, phải suy ra 3 ô mod + CONFIRM + nút refresh bằng `abyss_regions`."""
        pts = []

        def them(a, nhan):
            if a.get("type") == "abyss":
                fr = a.get("frame")
                if not fr:
                    return
                r = core.abyss_regions(fr)
                for i, p in enumerate(r["band_points"], 1):
                    pts.append([p[0], p[1], f"{nhan} · mod {i}", "ok"])
                pts.append([r["confirm"][0], r["confirm"][1], f"{nhan} · CONFIRM", "accent"])
                pts.append([r["refresh_point"][0], r["refresh_point"][1], f"{nhan} · ↻", "warn"])
                return
            pt = a.get("point")
            if pt:
                pts.append([pt[0], pt[1], nhan,
                            "ok" if a.get("type") == "check_mod" else "accent"])

        for si, st in enumerate(steps or [], 1):
            if core.has_actions(st):
                for i, a in enumerate(st.get("actions") or [], 1):
                    them(a, f"{si}.{i} {core.step_title(st)}")
            else:
                them(st, f"{si} {core.step_title(st)}")

        if not pts:
            return {"ok": False, "error": "Chưa có điểm nào để xem"}
        return self._chay_overlay("review", ["--points", json.dumps(pts, ensure_ascii=False)])

    @_bat_loi
    def save_process(self, name, steps, edges=None, start_delay=3):
        """Ghi template Process. Định dạng do `core.make_process_template` quyết định."""
        ten = (name or "").strip()
        if not ten:
            return {"ok": False, "error": "Tên Process không được để trống"}
        s = core.load_settings()
        doc = core.make_process_template(ten, s.get("game", "poe2"), start_delay,
                                         steps or [], edges)
        path = core.template_path("process", ten)
        core.write_json(path, doc)
        return {"ok": True, "value": {"path": path, "name": ten}}

    # ---------------- kiểm tra ----------------
    @_bat_loi
    def validate(self, steps, edges=None):
        """Vấn đề + THỨ TỰ CHẠY, gói trong một lần gọi.

        Số thứ tự tính bằng `core.flow_order` — CHÍNH phép duyệt mà `ProcessRunner`
        dùng. Nhờ vậy con số hiện ở góc khối không thể nói khác việc app thực sự làm;
        trước đây canvas vẽ một đằng, bộ máy chạy theo thứ tự tạo khối một nẻo.

        Gộp chung để chỉ tốn một vòng IPC — kéo một cái hộp là bắn ra hàng chục
        thay đổi, tách hai lần gọi thì gấp đôi số vòng.
        """
        steps = steps or []
        probs = core.validate_process(steps, edges=edges)
        luong = core.flow_order(steps, edges if edges is not None else core.default_edges(steps))
        return {"ok": True, "value": probs,
                "so_loi": sum(1 for p in probs if p.get("severity") == "error"),
                "so_canh_bao": sum(1 for p in probs if p.get("severity") != "error"),
                "order": luong["order"], "unreachable": luong["unreachable"],
                "entry": luong["entry"], "loop": luong["loop"]}

    # ---------------- cài đặt ----------------
    @_bat_loi
    def save_settings(self, s):
        """Ghi settings.json. Kiểm kiểu ở đây chứ không tin dữ liệu từ form."""
        cu = core.load_settings()
        game = s.get("game")
        if game not in core.GAMES:
            return {"ok": False, "error": f'Game không hợp lệ: "{game}"'}
        try:
            pre = max(0, int(s.get("pre_click_ms") or 0))
            hov = max(0, int(s.get("hover_ms") or 0))
        except (TypeError, ValueError):
            return {"ok": False, "error": "Delay / Chờ tooltip phải là số"}
        phim = str(s.get("stop_hotkey") or "").strip() or "f6"
        if not core.is_valid_key(phim):
            # pyautogui.keyDown với tên phím sai IM LẶNG không làm gì — đặt nhầm phím
            # dừng thì phát hiện ra đúng lúc đang cần dừng gấp.
            return {"ok": False, "error": f'Không có phím tên "{phim}"'}
        cu.update({
            "game": game, "pre_click_ms": pre, "hover_ms": hov,
            "copy_keys": str(s.get("copy_keys") or "").strip() or "ctrl+c",
            "stop_hotkey": phim,
            "accent": str(s.get("accent") or "").strip() or cu.get("accent", "#ffa657"),
        })
        core.save_settings(cu)
        return {"ok": True, "value": cu}

    @_bat_loi
    def save_ui(self, state):
        """Nhớ trạng thái bố cục (chiều cao bảng dưới, gập hay không) vào settings.json.

        KHÔNG dùng localStorage của trình duyệt: pywebview phục vụ trang qua
        http://127.0.0.1:<cổng NGẪU NHIÊN mỗi lần chạy>, mà localStorage gắn theo
        origin — nên mỗi lần mở app là mất sạch. Phải đi qua Python.
        """
        s = core.load_settings()
        ui = dict(s.get("ui") or {})
        for k, v in (state or {}).items():
            if k in ("panel_cao", "panel_gap"):     # chỉ nhận khoá đã biết
                ui[k] = v
        s["ui"] = ui
        core.save_settings(s)
        return {"ok": True, "value": ui}

    @_bat_loi
    def update_mods(self, game=None):
        """Tải lại danh sách mod từ API trade. Chạy đồng bộ — JS đã `await` sẵn,
        và người dùng đang đứng chờ ở hộp thoại nên không cần luồng riêng."""
        g = game or core.load_settings().get("game", "poe2")
        texts = core.fetch_mod_texts(g)
        with open(core.writable_data_path(f"mods_{g}.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(texts))
        return {"ok": True, "value": {"game": g, "so_luong": len(texts)}}

    # ---------------- danh sách mod ----------------
    @_bat_loi
    def get_mods(self, game=None):
        """Trả về TOÀN BỘ danh sách mod một lần (poe2 ~3200 dòng, ~130KB JSON).

        Cố ý không lọc ở phía Python: lọc theo từng phím gõ mà phải qua cầu nối thì
        mỗi ký tự là một vòng promise. Gửi một lần rồi lọc trong JS nhanh hơn hẳn,
        và bỏ luôn được cái trần hiển thị 150 dòng mà bản tkinter phải đặt.
        """
        g = game or core.load_settings().get("game", "poe2")
        mods = core.load_mods(g)
        return {"ok": True, "value": mods, "game": g, "so_luong": len(mods)}

    # ---------------- 3 overlay chọn trên màn hình ----------------
    def _chay_overlay(self, mode, extra=()):
        try:
            p = subprocess.run(_lenh_overlay(mode, extra), capture_output=True, timeout=300)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "overlay mở quá lâu không thấy phản hồi"}
        out = (p.stdout or b"").decode("utf-8", "replace").strip()
        if not out:
            err = (p.stderr or b"").decode("utf-8", "replace").strip()[:300]
            return {"ok": False, "error": f"overlay không trả kết quả (mã {p.returncode}) {err}"}
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"ok": False, "error": f"overlay trả về thứ không phải JSON: {out[:200]}"}

    @_bat_loi
    def pick_point(self):
        return self._chay_overlay("point")

    @_bat_loi
    def pick_abyss_frame(self, frame=None):
        extra = ["--frame", json.dumps(frame)] if frame else []
        return self._chay_overlay("abyss_frame", extra)

    @_bat_loi
    def pick_inv_grid(self, frame=None, cells=None):
        extra = []
        if frame:
            extra += ["--frame", json.dumps(frame)]
        if cells:
            extra += ["--cells", json.dumps(cells)]
        return self._chay_overlay("inv_grid", extra)
