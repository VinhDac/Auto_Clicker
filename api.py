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

    # ---------------- template ----------------
    @_bat_loi
    def list_templates(self, kind="process"):
        return {"ok": True, "value": core.list_templates(kind)}

    @_bat_loi
    def load_process(self, name):
        """Đọc 1 template Process theo TÊN (không phải đường dẫn — JS không cần biết
        template nằm ở đâu trên đĩa)."""
        path = core.template_path("process", name)
        if not os.path.exists(path):
            return {"ok": False, "error": f'Không có template Process tên "{name}"'}
        data = core.normalize_process(core.read_json(path))
        return {"ok": True, "value": data}

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
