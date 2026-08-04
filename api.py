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
import subprocess
import traceback

import core

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
    if loai == "check_mod":
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
                 # "prologue" = chạy 1 lần lúc đầu, nằm TRƯỚC dấu 🔁 Loop từ đây.
                 # Hộp phải cho thấy điều này, nếu không nhìn hộp không biết Loop
                 # thật sự lặp lại những gì.
                 "prologue": i < bat_dau,
                 "goal": a.get("type") in core.GOAL_TYPES}
                for i, a in enumerate(hd)]
    elif kind == "group":
        nhan = ["chạy 1 lần"]
        dong = [{"text": core.action_display(a), "prologue": False,
                 "goal": a.get("type") in core.GOAL_TYPES} for a in hd]
    else:
        nhan = ["chạy 1 lần"]
        dong = [{"text": core.action_display(step), "prologue": False,
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

    # ---------------- khởi động ----------------
    @_bat_loi
    def ping(self):
        return {"ok": True, "value": "pong"}

    @_bat_loi
    def bootstrap(self):
        """Mọi thứ giao diện cần ngay khi mở, gói trong MỘT lần gọi.

        Cố ý gộp: mỗi lần qua cầu nối là một vòng promise, gọi 6 lần lúc khởi động
        thì thấy rõ độ trễ. Dữ liệu ở đây đều nhỏ và ít đổi.
        """
        s = core.load_settings()
        return {"ok": True, "value": {
            "settings": s,
            "action_types": list(core.ACTION_TYPES),
            "action_labels": dict(core.ACTION_LABELS),
            "template_kinds": list(core.TEMPLATE_KINDS),
            "goal_types": list(core.GOAL_TYPES),
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
    def validate(self, steps):
        """Trả về danh sách vấn đề cho bảng ⚠ Vấn đề. Dùng CHÍNH hàm mà app cũ dùng,
        nên hai giao diện không bao giờ bất đồng về việc thế nào là hợp lệ."""
        probs = core.validate_process(steps or [])
        return {"ok": True, "value": probs,
                "so_loi": sum(1 for p in probs if p.get("severity") == "error"),
                "so_canh_bao": sum(1 for p in probs if p.get("severity") != "error")}

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
