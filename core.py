"""
AUTO CLICKER — LÕI (core)
=========================
Toàn bộ logic KHÔNG phụ thuộc giao diện: đọc/ghi cấu hình & template, so khớp mod,
mô hình Process ▸ Action_Loop ▸ Action, kiểm tra cấu hình, thực thi hành động, và
bộ máy chạy `ProcessRunner`.

Module này KHÔNG import tkinter. Nhờ vậy:
  - test được logic mà không cần dựng cửa sổ
  - đổi/​thêm giao diện khác chỉ cần viết lại lớp UI, lõi giữ nguyên

Giao tiếp với giao diện bằng CALLBACK (on_status / on_log), không gọi thẳng widget.
"""

import os
import re
import sys
import json
import copy
import time
import random
import threading
import ctypes
import urllib.request


try:
    import pyautogui
    import keyboard
except ImportError:
    print("Thiếu thư viện. Cài:  pip install pyautogui keyboard pyperclip plyer")
    sys.exit(1)

try:
    import pyperclip
    HAS_CLIP = True
except Exception:
    HAS_CLIP = False

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

# ---------------- Đường dẫn & cấu hình chung ----------------
GAMES = {"poe2": "PoE2", "poe1": "PoE1"}
STATS_API = {
    "poe1": "https://www.pathofexile.com/api/trade/data/stats",
    "poe2": "https://www.pathofexile.com/api/trade2/data/stats",
}
KEEP_LABELS = {"Explicit", "Implicit"}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

SETTINGS_DEFAULT = {
    "game": "poe2",
    "pre_click_ms": 60,
    "hover_ms": 250,
    "copy_keys": "ctrl+c",
    "stop_hotkey": "f6",
    "accent": "#ff7a1a",     # màu nhấn của giao diện (đổi trong Cài đặt)
}


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(name):
    """Tìm 1 file dữ liệu đi kèm, theo thứ tự ưu tiên:
       1. cạnh exe / cạnh mã nguồn   -> bản người dùng tự cập nhật, ưu tiên cao nhất
       2. thư mục data/              -> bản gốc trong repo khi chạy từ mã nguồn
       3. thư mục tạm của PyInstaller-> bản đóng gói sẵn trong exe
    """
    for p in (os.path.join(app_dir(), name),
              os.path.join(app_dir(), "data", name)):
        if os.path.exists(p):
            return p
    base = getattr(sys, "_MEIPASS", app_dir())
    return os.path.join(base, name)


def writable_data_path(name):
    """Nơi GHI file dữ liệu do người dùng cập nhật (vd tải lại danh sách mod).
    Khi chạy từ mã nguồn thì ghi vào data/ cho gọn; bản exe thì ghi cạnh exe."""
    if getattr(sys, "frozen", False):
        return os.path.join(app_dir(), name)
    d = os.path.join(app_dir(), "data")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name)


def load_settings():
    s = dict(SETTINGS_DEFAULT)
    try:
        with open(os.path.join(app_dir(), "settings.json"), encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    if s.get("game") not in GAMES:
        s["game"] = "poe2"
    return s


def save_settings(s):
    try:
        with open(os.path.join(app_dir(), "settings.json"), "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------- Template: 2 loại (Process và Action_Loop) ----------------
# Lưu cạnh exe:  templates/process/*.json   và   templates/loop/*.json
TEMPLATE_KINDS = {"process": "Process", "loop": "Action_Loop"}
_BAD_FILENAME_CHARS = '\\/:*?"<>|'


def templates_dir(kind):
    """Đường dẫn thư mục template theo loại; tự tạo nếu chưa có."""
    d = os.path.join(app_dir(), "templates", kind)
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def safe_filename(name):
    """Bỏ ký tự Windows không cho phép trong tên file."""
    out = "".join(("_" if c in _BAD_FILENAME_CHARS else c) for c in (name or "").strip())
    out = out.rstrip(" .")            # Windows không cho tên kết thúc bằng '.' hoặc ' '
    return out or "khong_ten"


def list_templates(kind):
    """[(tên hiển thị, đường dẫn)] các template đã lưu, sắp theo tên."""
    d = templates_dir(kind)
    out = []
    try:
        for fn in os.listdir(d):
            if fn.lower().endswith(".json"):
                out.append((os.path.splitext(fn)[0], os.path.join(d, fn)))
    except Exception:
        pass
    return sorted(out, key=lambda t: t[0].lower())


def template_path(kind, name):
    return os.path.join(templates_dir(kind), safe_filename(name) + ".json")


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def make_loop_template(step, game):
    """Đóng gói 1 bước Action_Loop thành template loại "loop"."""
    return {
        "schema": 3,
        "type": "loop",
        "name": step.get("name") or "Loop",
        "game": game,
        "loop": {
            "kind": "loop",
            "name": step.get("name") or "Loop",
            "actions": step.get("actions") or [],
            "loop_start_index": int(step.get("loop_start_index") or 0),
            "max_loops": int(step.get("max_loops") or DEFAULT_MAX_LOOPS),
        },
    }


def normalize_loop_template(data):
    """Đọc 1 file template Action_Loop -> 1 bước loop. Trả None nếu file không phải
    loại loop (vd người dùng lỡ chọn file Process)."""
    if not isinstance(data, dict):
        return None
    if data.get("type") == "loop" and isinstance(data.get("loop"), dict):
        lp = data["loop"]
        return {
            "kind": "loop",
            "name": lp.get("name") or data.get("name") or "Loop",
            "actions": lp.get("actions") or [],
            "loop_start_index": int(lp.get("loop_start_index") or 0),
            "max_loops": int(lp.get("max_loops") or DEFAULT_MAX_LOOPS),
        }
    return None


def load_mods(game):
    try:
        with open(resource_path(f"mods_{game}.txt"), encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except Exception:
        return []


def fetch_mod_texts(game):
    req = urllib.request.Request(STATS_API[game],
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    texts = []
    for cat in data.get("result", []):
        if cat.get("label") in KEEP_LABELS:
            for e in cat.get("entries", []):
                t = (e.get("text") or "").strip()
                if t:
                    texts.append(t)
    return sorted(set(texts), key=lambda s: s.lower())


# ---------------- So khớp mod theo khối (đúng Tier) ----------------
def norm(text):
    """Chuẩn hoá 1 dòng mod: bỏ số & ký hiệu, chỉ giữ chữ, để so khớp chính xác."""
    t = text.lower().replace("#", " ")
    t = re.sub(r"[0-9]+", " ", t)
    t = re.sub(r"[()\[\]+%.,:\-–—/]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def parse_blocks(clipboard):
    """Tách clipboard item thành các khối mod: [{'tier': int|None, 'stats': [norm_line,...]}]."""
    blocks = []
    cur = None
    for line in clipboard.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("{"):
            m = re.search(r"\(Tier:\s*(\d+)\)", s)
            cur = {"tier": int(m.group(1)) if m else None, "stats": []}
            blocks.append(cur)
        elif cur is not None and not s.startswith("-"):
            n = norm(s)
            if n:
                cur["stats"].append(n)
    return blocks


# --- Lọc mod thuần / mod hybrid ---
# HYBRID = 1 affix cho NHIỀU dòng stat, vd { Prefix "Hallowed" ... } cho cả Armour
# lẫn Energy Shield. Tier được đánh số RIÊNG theo từng họ affix, nên "ES Tier 1" của
# mod thuần KHÔNG tương đương "Tier 1" của mod hybrid — phải cho người dùng lọc.
# Lưu ý: KHÔNG dùng số TAG sau dấu gạch để nhận biết — mod Fire Res thuần có tới 3
# tag ("Elemental, Fire, Resistance") mà vẫn chỉ 1 dòng stat. Đếm DÒNG STAT mới đúng.
HYBRID_ANY = "any"        # mặc định: thuần hay hybrid đều được (hành vi cũ)
HYBRID_PURE = "pure"      # chỉ mod thuần (khối có đúng 1 dòng stat)
HYBRID_ONLY = "hybrid"    # chỉ mod hybrid (khối có từ 2 dòng stat trở lên)

HYBRID_LABELS = {
    HYBRID_ANY: "Cả hai",
    HYBRID_PURE: "Chỉ mod thuần",
    HYBRID_ONLY: "Chỉ mod hybrid",
}
HYBRID_FROM_LABEL = {v: k for k, v in HYBRID_LABELS.items()}


def block_is_hybrid(block):
    """Khối hybrid = 1 affix sinh ra từ 2 dòng stat trở lên."""
    return len(block.get("stats") or []) >= 2


def cond_allows_block(cond, block):
    mode = cond.get("hybrid", HYBRID_ANY)
    if mode == HYBRID_PURE:
        return not block_is_hybrid(block)
    if mode == HYBRID_ONLY:
        return block_is_hybrid(block)
    return True


def condition_match(blocks, cond):
    """Trả về (khối khớp, khối gần-khớp bị lọc bỏ).

    "gần-khớp" = đúng dòng mod VÀ đúng tier, nhưng bị bộ lọc thuần/hybrid loại ra.
    Dùng để báo cho người dùng biết vì sao thấy mod rồi mà vẫn không dừng."""
    target = norm(cond.get("mod", ""))
    if not target:
        return None, None
    tier = cond.get("tier")
    rejected = None
    for b in blocks:
        if (tier is None or b["tier"] == tier) and target in b["stats"]:
            if cond_allows_block(cond, b):
                return b, None
            if rejected is None:
                rejected = b
    return None, rejected


def condition_hit(blocks, cond):
    """Khớp khi có 1 KHỐI vừa chứa đúng dòng mod, vừa đúng tier (tier None = mọi
    tier), và hợp bộ lọc thuần/hybrid của điều kiện."""
    hit, _ = condition_match(blocks, cond)
    return hit is not None


def block_kind_text(block):
    n = len(block.get("stats") or [])
    return f"mod hybrid, {n} dòng stat" if n >= 2 else "mod thuần, 1 dòng stat"


def cond_display(c):
    tier = c.get("tier")
    tt = f"Tier {tier}" if tier is not None else "mọi tier"
    mode = c.get("hybrid", HYBRID_ANY)
    extra = "" if mode == HYBRID_ANY else f"   ·  {HYBRID_LABELS[mode].lower()}"
    return f"{c.get('mod', '')}   ·  {tt}{extra}"


# ---------------- Action_Loop: data model & tương thích template cũ ----------------
def normalize_loaded_template(data):
    """Chuẩn hoá 1 file template (JSON đã parse) về dạng phẳng mà UI hiện tại dùng.

    Hỗ trợ 2 định dạng:
      - MỚI: có "action_loops" (list) -> lấy Action_Loop ĐẦU TIÊN (UI hiện tại
        chỉ hiểu 1 Action_Loop; nhiều hơn sẽ có ghi chú "note" báo cho người dùng).
      - CŨ: các trường actions/max_loops/... nằm thẳng ở gốc JSON (kể cả bản rất
        cũ dùng "stop.clipboard.texts" thay vì "conditions").
    """
    note = None
    loops = data.get("action_loops")
    if isinstance(loops, list) and loops:
        loop = loops[0] if isinstance(loops[0], dict) else {}
        if len(loops) > 1:
            note = (f"Template có {len(loops)} Action_Loop — bản hiện tại chỉ mở "
                    f"được Action_Loop đầu tiên (\"{loop.get('name', 'Loop 1')}\").")
        actions = loop.get("actions", [])
        max_loops = loop.get("max_loops", 1000)
        hover_point = loop.get("hover_point")
        stop_enabled = loop.get("stop_enabled", True)
        conditions = loop.get("conditions")
        loop_name = loop.get("name", "Loop 1")
        loop_start_index = loop.get("loop_start_index", 0)
        start_delay = data.get("start_delay", 3)
    else:
        actions = data.get("actions", [])
        max_loops = data.get("max_loops", 1000)
        start_delay = data.get("start_delay", 3)
        hover_point = data.get("hover_point")
        stop_enabled = data.get("stop_enabled", True)
        conditions = data.get("conditions")
        loop_name = "Loop 1"
        loop_start_index = 0

    if conditions is None:
        # tương thích bản rất cũ (danh sách chữ gõ tay, chưa có mod picker)
        old = (((data.get("stop") or {}).get("clipboard") or {}).get("texts")) or []
        conditions = [{"mod": t, "tier": None} for t in old]

    return {
        "actions": actions if isinstance(actions, list) else [],
        "max_loops": max_loops,
        "start_delay": start_delay,
        "hover_point": tuple(hover_point) if hover_point else None,
        "stop_enabled": bool(stop_enabled),
        "conditions": [{"mod": c.get("mod", ""), "tier": c.get("tier")} for c in conditions],
        "loop_name": loop_name,
        "loop_start_index": int(loop_start_index or 0),
        "note": note,
    }


def migrate_legacy_conditions_into_actions(actions, hover_point, conditions):
    """Bước 2: điều kiện mod giờ là 1 Action "check_mod" nằm TRONG actions, không
    còn là cấu hình riêng ở cấp Action_Loop. Nếu actions ĐÃ có check_mod (file kiểu
    mới) thì giữ nguyên; nếu chưa (file kiểu cũ, có conditions rời) thì tự thêm 1
    check_mod vào CUỐI danh sách để giữ đúng hành vi cũ."""
    if not conditions:
        return actions
    if any(a.get("type") == "check_mod" for a in actions):
        return actions
    check = {
        "type": "check_mod",
        "point": list(hover_point) if hover_point else None,
        "conditions": conditions,
    }
    return actions + [check]


# ---------------- Process: mô hình 3 tầng (Process ▸ Action_Loop ▸ Action) ----------------
# Process = danh sách BƯỚC tuần tự. Mỗi bước là 1 trong 2 loại:
#   {"kind": "loop",   "name", "actions": [...], "loop_start_index", "max_loops"}
#   {"kind": "action", ...các trường của 1 action...}   -> hành động lẻ, chạy đúng 1 lần
DEFAULT_MAX_LOOPS = 1000


def make_loop_step(name="Loop mới"):
    return {"kind": "loop", "name": name, "actions": [],
            "loop_start_index": 0, "max_loops": DEFAULT_MAX_LOOPS}


def make_action_step(action):
    st = dict(action)
    st["kind"] = "action"
    return st


def is_loop_step(step):
    return step.get("kind") == "loop"


def step_title(step):
    """Tên ngắn của 1 bước (dùng trong thông báo lỗi)."""
    if is_loop_step(step):
        return step.get("name") or "Loop"
    return (step.get("name") or "").strip() or ACTION_LABELS.get(step.get("type"), "Hành động")


def step_display(step):
    """Chuỗi hiện ở cột danh sách bước."""
    if is_loop_step(step):
        n = len(step.get("actions") or [])
        has_check = any(a.get("type") == "check_mod" for a in (step.get("actions") or []))
        goal = "có mục tiêu" if has_check else "chỉ theo số vòng"
        return (f"🔁 {step.get('name') or 'Loop'}   ·  {n} hành động  ·  "
                f"tối đa {step.get('max_loops', DEFAULT_MAX_LOOPS)} vòng  ·  {goal}")
    return f"⚡ {action_display(step)}   (chạy 1 lần)"


def normalize_process(data):
    """Đọc file template ở BẤT KỲ định dạng nào -> {name, start_delay, steps, note}.

    Hỗ trợ:
      - MỚI  : {"type": "process", "name", "start_delay", "steps": [...]}
      - GĐ1/2: {"action_loops": [{name, actions, loop_start_index, max_loops}, ...]}
               (nay nạp TẤT CẢ các loop thành nhiều bước, không chỉ loop đầu)
      - CŨ   : các trường actions/max_loops/hover_point/conditions nằm phẳng ở gốc
    """
    note = None

    steps_raw = data.get("steps")
    if data.get("type") == "process" and isinstance(steps_raw, list):
        steps = []
        for st in steps_raw:
            if not isinstance(st, dict):
                continue
            if st.get("kind") == "loop":
                steps.append({
                    "kind": "loop",
                    "name": st.get("name") or "Loop",
                    "actions": st.get("actions") or [],
                    "loop_start_index": int(st.get("loop_start_index") or 0),
                    "max_loops": int(st.get("max_loops") or DEFAULT_MAX_LOOPS),
                })
            elif st.get("type"):
                steps.append(make_action_step(st))
        return {
            "name": data.get("name") or "Process 1",
            "start_delay": data.get("start_delay", 3),
            "steps": steps,
            "note": note,
        }

    loops_raw = data.get("action_loops")
    if isinstance(loops_raw, list) and loops_raw:
        steps = []
        for i, lp in enumerate(loops_raw, 1):
            if not isinstance(lp, dict):
                continue
            actions = lp.get("actions") or []
            # loop kiểu cũ có thể còn hover_point/conditions rời -> nhúng thành check_mod
            actions = migrate_legacy_conditions_into_actions(
                actions,
                lp.get("hover_point"),
                (lp.get("conditions") or []) if lp.get("stop_enabled", True) else [])
            steps.append({
                "kind": "loop",
                "name": lp.get("name") or f"Loop {i}",
                "actions": actions,
                "loop_start_index": int(lp.get("loop_start_index") or 0),
                "max_loops": int(lp.get("max_loops") or DEFAULT_MAX_LOOPS),
            })
        if len(steps) > 1:
            note = f"Đã nạp {len(steps)} Action_Loop từ file thành {len(steps)} bước."
        return {
            "name": data.get("name") if data.get("name") not in (None, "template") else "Process 1",
            "start_delay": data.get("start_delay", 3),
            "steps": steps,
            "note": note,
        }

    # Định dạng phẳng đời đầu
    norm = normalize_loaded_template(data)
    actions = migrate_legacy_conditions_into_actions(
        norm["actions"], norm["hover_point"],
        norm["conditions"] if norm["stop_enabled"] else [])
    steps = [{
        "kind": "loop",
        "name": norm["loop_name"] or "Loop 1",
        "actions": actions,
        "loop_start_index": norm["loop_start_index"],
        "max_loops": norm["max_loops"],
    }]
    return {"name": "Process 1", "start_delay": norm["start_delay"],
            "steps": steps, "note": norm["note"]}


# ---------------- Kiểm tra cấu hình trước khi chạy (panel "Vấn đề") ----------------
def virtual_screen_rect():
    """(x, y, w, h) của toàn bộ vùng desktop ảo (gộp mọi màn hình)."""
    try:
        u = ctypes.windll.user32
        return (u.GetSystemMetrics(76), u.GetSystemMetrics(77),
                u.GetSystemMetrics(78), u.GetSystemMetrics(79))
    except Exception:
        return None


def validate_flow(actions, loop_start_index, max_loops, has_clip=None, screen=None):
    """Soát cấu hình TRƯỚC KHI CHẠY. Trả về list vấn đề:
        [{"severity": "error"|"warning", "message": str, "index": int|None}]
    "error" = chặn không cho chạy; "warning" = vẫn chạy được nhưng nên xem lại.
    `index` là vị trí hành động có vấn đề (để click nhảy tới), hoặc None nếu là
    vấn đề chung của cả Loop. Hàm thuần logic -> test độc lập được."""
    if has_clip is None:
        has_clip = HAS_CLIP
    if screen is None:
        screen = virtual_screen_rect()

    problems = []

    def err(msg, idx=None):
        problems.append({"severity": "error", "message": msg, "index": idx})

    def warn(msg, idx=None):
        problems.append({"severity": "warning", "message": msg, "index": idx})

    n = len(actions)
    if n == 0:
        err("Chưa có hành động nào — hãy thêm ít nhất 1 hành động.")
        return problems

    if loop_start_index >= n:
        err(f"Điểm bắt đầu Loop (#{loop_start_index + 1}) nằm sau hành động cuối "
            f"→ không có gì để lặp. Dùng nút \"🔁 Loop từ đây\" để đặt lại.")

    checks = [i for i, a in enumerate(actions) if a.get("type") == "check_mod"]
    if not checks:
        warn("Chưa có hành động \"🔍 Kiểm tra mod\" → Loop chỉ dừng theo số vòng, "
             "không tự dừng khi item ra mod mong muốn.")
    elif has_clip is False:
        err("Thiếu thư viện pyperclip → không đọc được chữ item. Cài: pip install pyperclip")

    for i in checks:
        if i < loop_start_index:
            warn(f"\"Kiểm tra mod\" nằm ở phần chỉ chạy 1 lần → chỉ kiểm tra được đúng "
                 f"1 lần lúc đầu, không kiểm tra mỗi vòng.", i)

    for i, a in enumerate(actions):
        t = a.get("type")
        if t == "check_mod":
            if not a.get("point"):
                err("\"Kiểm tra mod\" chưa chọn điểm rê chuột vào item.", i)
            if not (a.get("conditions") or []):
                err("\"Kiểm tra mod\" chưa có điều kiện mod nào.", i)
        point = a.get("point")
        if point and screen:
            sx, sy, sw, sh = screen
            if not (sx <= point[0] < sx + sw and sy <= point[1] < sy + sh):
                warn(f"Điểm ({point[0]}, {point[1]}) nằm NGOÀI màn hình hiện tại "
                     f"— có thể toạ độ lưu từ độ phân giải khác.", i)

    try:
        ml = int(max_loops)
        if ml <= 0:
            err("Số vòng lặp phải lớn hơn 0.")
        elif ml > 100000:
            warn(f"Số vòng lặp rất lớn ({ml}) — chắc chắn muốn chạy lâu vậy?")
    except (TypeError, ValueError):
        err("Số vòng lặp không phải là số.")

    return problems


def validate_process(steps, has_clip=None, screen=None):
    """Soát cả Process. Trả về [{"severity", "message", "step": int|None, "index": int|None}]
    trong đó `step` = vị trí bước, `index` = vị trí hành động trong bước đó (nếu có)."""
    if has_clip is None:
        has_clip = HAS_CLIP
    if screen is None:
        screen = virtual_screen_rect()

    problems = []
    if not steps:
        problems.append({"severity": "error", "step": None, "index": None,
                         "message": "Process chưa có bước nào — hãy thêm 1 Action_Loop hoặc 1 hành động lẻ."})
        return problems

    for si, st in enumerate(steps):
        label = f"Bước {si + 1} \"{step_title(st)}\""
        if is_loop_step(st):
            for p in validate_flow(st.get("actions") or [],
                                   int(st.get("loop_start_index") or 0),
                                   st.get("max_loops", 0), has_clip, screen):
                problems.append({"severity": p["severity"], "step": si, "index": p.get("index"),
                                 "message": f"{label}: {p['message']}"})
        else:
            if st.get("type") == "check_mod":
                if not st.get("point"):
                    problems.append({"severity": "error", "step": si, "index": None,
                                     "message": f"{label}: \"Kiểm tra mod\" chưa chọn điểm rê chuột."})
                if not (st.get("conditions") or []):
                    problems.append({"severity": "error", "step": si, "index": None,
                                     "message": f"{label}: \"Kiểm tra mod\" chưa có điều kiện nào."})
                elif not has_clip:
                    problems.append({"severity": "error", "step": si, "index": None,
                                     "message": f"{label}: thiếu pyperclip → không đọc được chữ item."})
            point = st.get("point")
            if point and screen:
                sx, sy, sw, sh = screen
                if not (sx <= point[0] < sx + sw and sy <= point[1] < sy + sh):
                    problems.append({"severity": "warning", "step": si, "index": None,
                                     "message": f"{label}: điểm ({point[0]}, {point[1]}) nằm NGOÀI "
                                                f"màn hình hiện tại — có thể toạ độ lưu từ độ phân giải khác."})
    return problems


# ---------------- Hành động ----------------
ACTION_TYPES = ["left_click", "right_click", "double_click", "move",
                "mod_click", "scroll", "key_press", "delay", "check_mod"]
ACTION_LABELS = {
    "left_click": "Trái-click", "right_click": "Phải-click",
    "double_click": "Double-click", "move": "Di chuyển tới",
    "mod_click": "Giữ phím + click", "scroll": "Cuộn chuột",
    "key_press": "Nhấn phím", "delay": "Delay",
    "check_mod": "🔍 Kiểm tra mod",
}
POINT_TYPES = ("left_click", "right_click", "double_click", "move")
# Phím giữ hay dùng trong PoE: Shift+click (tách stack), Ctrl+click (chuyển stash)
COMMON_HOLD_KEYS = ["shift", "ctrl", "alt", "ctrl+shift", "alt+shift"]


def parse_hold_keys(s):
    """'ctrl+shift' -> ['ctrl', 'shift'] (bỏ khoảng trắng, bỏ mục rỗng)."""
    return [k.strip().lower() for k in (s or "").split("+") if k.strip()]


def action_display(a):
    """Chuỗi hiện trong danh sách. Tên tự đặt (nếu có) đứng trước, KÈM THEO phần mô
    tả kỹ thuật tự sinh — không thay thế, để vẫn thấy toạ độ/thông số mà kiểm tra."""
    name = (a.get("name") or "").strip()
    summary = action_summary(a)
    return f"{name} — {summary}" if name else summary


def action_summary(a):
    t = a["type"]
    if t == "check_mod":
        n = len(a.get("conditions") or [])
        pt = a.get("point")
        loc = f"@ ({pt[0]}, {pt[1]})" if pt else "(chưa chọn điểm)"
        return f"🔍 Kiểm tra mod {loc}  ·  {n} điều kiện — khớp thì DỪNG Loop"
    if t == "mod_click":
        keys = "+".join(parse_hold_keys(a.get("keys"))) or "(chưa chọn phím)"
        btn = "trái" if a.get("button", "left") == "left" else "phải"
        pt = a.get("point")
        loc = f"@ ({pt[0]}, {pt[1]})" if pt else "(chưa chọn điểm)"
        return f"Giữ [{keys}] + click {btn} {loc}"
    if t in POINT_TYPES:
        return f"{ACTION_LABELS[t]} @ ({a['point'][0]}, {a['point'][1]})"
    if t == "scroll":
        return f"Cuộn {a.get('amount', -300)}"
    if t == "key_press":
        return f"Nhấn phím: {a.get('key', '')}"
    if t == "delay":
        return f"Delay {a['min_ms']}–{a['max_ms']} ms"
    return t


def human_sleep(min_ms, max_ms, stop_flag):
    total = random.uniform(min_ms, max_ms) / 1000.0
    end = time.time() + total
    while time.time() < end:
        if stop_flag.is_set():
            return
        time.sleep(min(0.02, max(0.0, end - time.time())))


def do_action(a, stop_flag, pre_click_ms=0):
    t = a["type"]
    if t in ("left_click", "right_click", "double_click"):
        x, y = a["point"]
        pyautogui.moveTo(x, y)
        if pre_click_ms > 0:
            human_sleep(pre_click_ms, pre_click_ms, stop_flag)
        if stop_flag.is_set():
            return
        if t == "left_click":
            pyautogui.click(button="left")
        elif t == "right_click":
            pyautogui.click(button="right")
        else:
            pyautogui.doubleClick()
    elif t == "mod_click":
        x, y = a["point"]
        keys = parse_hold_keys(a.get("keys"))
        button = a.get("button", "left")
        pyautogui.moveTo(x, y)
        if pre_click_ms > 0:
            human_sleep(pre_click_ms, pre_click_ms, stop_flag)
        held = []
        try:
            for k in keys:
                pyautogui.keyDown(k)
                held.append(k)
            pyautogui.click(button=button)
        finally:
            # LUÔN thả phím, kể cả khi click ném lỗi hoặc bị dừng giữa chừng —
            # nếu không, phím Shift/Ctrl sẽ kẹt ở trạng thái giữ trong cả hệ thống.
            for k in reversed(held):
                try:
                    pyautogui.keyUp(k)
                except Exception:
                    pass
    elif t == "move":
        pyautogui.moveTo(a["point"][0], a["point"][1], duration=0.1)
    elif t == "scroll":
        pyautogui.scroll(a.get("amount", -300))
    elif t == "key_press":
        pyautogui.press(a["key"])
    elif t == "delay":
        human_sleep(a["min_ms"], a["max_ms"], stop_flag)


# Kết quả của 1 lần "Kiểm tra mod". Phân biệt rõ 3 trạng thái — TRƯỚC ĐÂY cả 3 đều
# bị coi là "chưa ra mod" khiến app cứ thế đốt currency dù thực ra không đọc được gì.
CHECK_MATCH = "match"        # đọc được chữ item VÀ khớp điều kiện
CHECK_NO_MATCH = "no_match"  # đọc được chữ item nhưng chưa khớp -> chạy tiếp là đúng
CHECK_READ_FAIL = "read_fail"  # KHÔNG đọc được chữ item -> có gì đó sai, phải báo

# Đọc lỗi liên tiếp bao nhiêu lần thì tự dừng (tránh đốt currency khi game mất focus).
MAX_READ_FAIL_STREAK = 3

# Số mod tối đa hiện trong ô tìm kiếm. Đo thực tế: 500 dòng tốn ~9-11ms mỗi lần gõ
# phím, 150 dòng chỉ ~3ms. Bản thân việc lọc 3223 mod chỉ tốn ~1ms nên không phải
# nút thắt — nút thắt là việc vẽ lại Listbox.
MOD_LIST_DISPLAY_CAP = 150

# Số dòng nhật ký giữ lại tối đa (chạy 1000 vòng vẫn không phình bộ nhớ).
MAX_LOG_LINES = 500

# Cách nhau ít nhất bao nhiêu giây mới ghi lại 1 dòng "bỏ qua vì sai loại mod".
SKIP_LOG_MIN_GAP = 2.0


def looks_like_item_text(text):
    """Có phải chữ item PoE không? Nhận diện qua nhiều dấu hiệu để KHÔNG loại nhầm
    item hợp lệ (báo nhầm "không đọc được" sẽ làm app dừng oan):
      - mở đầu 'Item Class:' (PoE2) hoặc 'Rarity:' (PoE1)
      - có dòng ngăn cách '--------' (mọi item PoE đều có)
      - có khối mod dạng '{ ... Modifier ... }'
    """
    t = (text or "").strip()
    if not t:
        return False
    head = t.lower()
    if head.startswith("item class:") or head.startswith("rarity:"):
        return True
    if "--------" in t:
        return True
    if "modifier" in head and "{" in t:
        return True
    return False


def check_mod_action(a, stop_flag, hover_ms, copy_keys, log=None):
    """Rê chuột tới a['point'] (nếu có), Ctrl+C đọc chữ item, so với a['conditions']
    (ưu tiên trên->dưới).

    `log(msg, tag)` (tuỳ chọn) để ghi nhật ký chi tiết: khớp loại mod nào, hoặc
    thấy đúng mod+tier nhưng bị bộ lọc thuần/hybrid loại ra (tag "skip").

    Trả về (status, payload):
      (CHECK_MATCH, cond)       — khớp điều kiện `cond`
      (CHECK_NO_MATCH, None)    — đọc được item nhưng chưa ra mod
      (CHECK_READ_FAIL, lý_do)  — không đọc được chữ item (lý_do: chuỗi tiếng Việt)
    """
    if not HAS_CLIP:
        return CHECK_READ_FAIL, "thiếu thư viện pyperclip"
    conds = a.get("conditions") or []
    if not conds:
        return CHECK_READ_FAIL, "hành động Kiểm tra mod chưa có điều kiện nào"

    point = a.get("point")
    try:
        if point:
            pyautogui.moveTo(point[0], point[1])
            human_sleep(hover_ms, hover_ms, stop_flag)
        if stop_flag.is_set():
            return CHECK_NO_MATCH, None
        pyperclip.copy("")
        pyautogui.hotkey(*copy_keys)
        time.sleep(0.08)
        text = pyperclip.paste() or ""
    except Exception as e:
        return CHECK_READ_FAIL, f"lỗi khi đọc clipboard ({type(e).__name__})"

    if not text.strip():
        return CHECK_READ_FAIL, "clipboard rỗng — game có thể không nhận phím copy"
    if not looks_like_item_text(text):
        snippet = " ".join(text.split())[:40]
        return CHECK_READ_FAIL, f"clipboard không phải chữ item (\"{snippet}...\")"

    blocks = parse_blocks(text)
    for c in conds:
        hit, rejected = condition_match(blocks, c)
        if hit is not None:
            if log:
                log(f"      ↳ khớp khối: {block_kind_text(hit)}", "ok")
            return CHECK_MATCH, c
        if rejected is not None and log:
            # Thấy đúng mod + đúng tier nhưng sai loại -> phải nói ra, nếu không
            # người dùng sẽ thắc mắc "rõ ràng thấy mod rồi sao không dừng?"
            want = HYBRID_LABELS.get(c.get("hybrid", HYBRID_ANY), "")
            got = "HYBRID" if block_is_hybrid(rejected) else "THUẦN"
            lines = " + ".join(rejected["stats"])
            log(f"   ⏭ item CÓ \"{norm(c.get('mod', ''))}\" đúng tier, nhưng là mod {got} "
                f"({lines}) — bạn đặt \"{want}\" → bỏ qua, roll tiếp", "skip")
    return CHECK_NO_MATCH, None


def notify(loops, status):
    try:
        import winsound
        winsound.MessageBeep()
    except Exception:
        pass
    try:
        from plyer import notification
        notification.notify(title="Auto Clicker", message=f"{status}: {loops} vòng", timeout=5)
    except Exception:
        pass




# ---------------- Bộ máy chạy Process (không phụ thuộc giao diện) ----------------
class ProcessRunner:
    """Chạy 1 Process: danh sách bước tuần tự, mỗi bước là Action_Loop hoặc hành động lẻ.

    KHÔNG biết gì về tkinter. Báo ra ngoài bằng 2 callback:
        on_status(msg)      — 1 dòng trạng thái ngắn (ghi đè liên tục)
        on_log(msg, tag)    — 1 dòng nhật ký (tag: None/"ok"/"warn"/"err"/"dim"/"skip")
    Bên gọi tự quyết hiển thị thế nào và hãm tần suất ra sao.

    Dùng:
        runner = ProcessRunner(cfg, stop_flag, on_status=..., on_log=...)
        status_text, total_loops = runner.run()
    """

    def __init__(self, cfg, stop_flag, on_status=None, on_log=None):
        self.cfg = cfg
        self.stop_flag = stop_flag
        self._on_status = on_status or (lambda msg: None)
        self._on_log = on_log or (lambda msg, tag=None: None)
        self.hotkey_label = str(cfg.get("stop_hotkey", "f6")).upper()

    # -- kênh báo ra ngoài --
    def _status(self, msg):
        self._on_status(msg)

    def _log(self, msg, tag=None):
        self._on_log(msg, tag)

    # -- chạy 1 danh sách hành động --
    def run_sequence(self, actions, pre_click_ms, hover_ms, copy_keys):
        """Trả về (hit, read_fail_reason).
        hit = điều kiện đã khớp -> DỪNG NGAY, không chạy nốt phần còn lại.
        read_fail_reason = KHÔNG đọc được chữ item (khác hẳn "đọc được nhưng chưa ra mod")."""
        for a in actions:
            if self.stop_flag.is_set():
                return None, None
            if a["type"] == "check_mod":
                status, payload = check_mod_action(a, self.stop_flag, hover_ms, copy_keys,
                                                   log=self._log)
                if status == CHECK_MATCH:
                    return payload, None
                if status == CHECK_READ_FAIL:
                    return None, payload
            else:
                try:
                    do_action(a, self.stop_flag, pre_click_ms)
                except pyautogui.FailSafeException:
                    self.stop_flag.set()
                    return None, None
        return None, None

    # -- chạy 1 bước Action_Loop --
    def run_loop_step(self, step, si, total_steps, pre_click_ms, hover_ms, copy_keys):
        """Trả về (outcome, loops, detail). outcome:
            "achieved"  đã khớp điều kiện mục tiêu
            "done"      hết số vòng, loop KHÔNG có mục tiêu -> coi là xong
            "exhausted" có mục tiêu nhưng hết vòng chưa đạt -> DỪNG cả Process
            "read_fail" không đọc được chữ item nhiều lần liên tiếp
            "aborted"   người dùng dừng"""
        actions = step.get("actions") or []
        n = len(actions)
        loop_start = max(0, min(int(step.get("loop_start_index") or 0), n))
        prologue, body = actions[:loop_start], actions[loop_start:]
        max_loops = int(step.get("max_loops") or DEFAULT_MAX_LOOPS)
        has_goal = any(a.get("type") == "check_mod" for a in actions)
        name = step_title(step)

        hit = None
        loops = 0
        fail_streak = 0
        last_fail = None

        if prologue and not self.stop_flag.is_set():
            hit, fail = self.run_sequence(prologue, pre_click_ms, hover_ms, copy_keys)
            if fail:
                fail_streak, last_fail = 1, fail

        while (hit is None and not self.stop_flag.is_set() and body
               and loops < max_loops and fail_streak < MAX_READ_FAIL_STREAK):
            hit, fail = self.run_sequence(body, pre_click_ms, hover_ms, copy_keys)
            loops += 1               # tính cả vòng vừa khớp (đã thực sự chạy 1 lượt)
            if fail:
                fail_streak += 1
                last_fail = fail
                self._status(f"⚠ [{si + 1}/{total_steps}] {name}: không đọc được chữ item "
                             f"({fail_streak}/{MAX_READ_FAIL_STREAK}) — {fail}")
                self._log(f"   ⚠ vòng {loops}: không đọc được chữ item "
                          f"({fail_streak}/{MAX_READ_FAIL_STREAK}) — {fail}", "warn")
            else:
                fail_streak = 0      # đọc được -> reset chuỗi lỗi
                if hit is None and (loops % 5 == 0 or loops == max_loops):
                    self._status(f"[{si + 1}/{total_steps}] {name}: vòng {loops}/{max_loops} "
                                 f"(nhấn {self.hotkey_label} để dừng)")
                if hit is None and loops % 25 == 0:
                    self._log(f"   … {name}: đã {loops}/{max_loops} vòng, chưa ra mod", "dim")

        if hit:
            return "achieved", loops, cond_display(hit)
        if fail_streak >= MAX_READ_FAIL_STREAK:
            return "read_fail", loops, last_fail
        if self.stop_flag.is_set():
            return "aborted", loops, None
        return ("done" if not has_goal else "exhausted"), loops, None

    # -- chạy cả Process --
    def run(self):
        """Chạy trọn Process. Trả về (status_text, total_loops)."""
        cfg = self.cfg
        for i in range(cfg.get("start_delay", 0), 0, -1):
            if self.stop_flag.is_set():
                break
            self._status(f"Bắt đầu sau {i}s... (chuyển sang cửa sổ game)")
            time.sleep(1)

        steps = cfg["steps"]
        total = len(steps)
        pre_click_ms = cfg.get("pre_click_ms", 0)
        hover_ms = cfg.get("hover_ms", 250)
        copy_keys = [k.strip() for k in (cfg.get("copy_keys") or "ctrl+c").split("+") if k.strip()]

        total_loops = 0
        achieved = []          # [(tên bước, mod đã ra)] để tóm tắt cuối cùng
        status = None

        self._log(f"▶ Bắt đầu Process \"{cfg.get('name', '')}\" — {total} bước", "ok")

        for si, step in enumerate(steps):
            if self.stop_flag.is_set():
                status = "Đã dừng"
                break
            name = step_title(step)

            if not is_loop_step(step):
                # Hành động lẻ giữa các Loop -> chạy đúng 1 lần
                self._status(f"[{si + 1}/{total}] {name} (hành động lẻ)")
                self._log(f"⚡ [{si + 1}/{total}] {name} — hành động lẻ, chạy 1 lần")
                hit, fail = self.run_sequence([step], pre_click_ms, hover_ms, copy_keys)
                if fail:
                    status = (f"⛔ DỪNG ở bước {si + 1} \"{name}\" — không đọc được chữ item "
                              f"({fail}). Kiểm tra: game còn focus? Điểm rê chuột còn đúng?")
                    self._log(status, "err")
                    break
                continue

            self._status(f"[{si + 1}/{total}] {name}: bắt đầu...")
            self._log(f"🔁 [{si + 1}/{total}] {name} — bắt đầu "
                      f"(tối đa {step.get('max_loops', DEFAULT_MAX_LOOPS)} vòng)")
            outcome, loops, detail = self.run_loop_step(
                step, si, total, pre_click_ms, hover_ms, copy_keys)
            total_loops += loops

            if outcome == "achieved":
                achieved.append((name, detail))
                self._status(f"✅ [{si + 1}/{total}] {name}: đạt mục tiêu sau {loops} vòng "
                             f"({detail})")
                self._log(f"✅ [{si + 1}/{total}] {name}: ĐẠT MỤC TIÊU sau {loops} vòng — {detail}",
                          "ok")
                continue
            if outcome == "done":
                self._status(f"✔ [{si + 1}/{total}] {name}: xong {loops} vòng")
                self._log(f"✔ [{si + 1}/{total}] {name}: xong {loops} vòng "
                          f"(loop này không đặt mục tiêu)", "ok")
                continue
            if outcome == "exhausted":
                status = (f"⛔ DỪNG cả Process — bước {si + 1} \"{name}\" chạy hết {loops} vòng "
                          f"mà chưa đạt mục tiêu. Không chạy tiếp để khỏi phí currency cho "
                          f"các bước sau.")
                self._log(status, "err")
                break
            if outcome == "read_fail":
                status = (f"⛔ DỪNG ở bước {si + 1} \"{name}\" — không đọc được chữ item "
                          f"{MAX_READ_FAIL_STREAK} lần liên tiếp ({detail}). Kiểm tra: cửa sổ game "
                          f"còn đang focus? Điểm rê chuột còn đúng vị trí item? "
                          f"Đã dừng để không phí currency.")
                self._log(status, "err")
                break
            status = "Đã dừng"
            self._log(f"■ Đã dừng ở bước {si + 1} \"{name}\" (người dùng dừng)", "warn")
            break

        if status is None:
            # Chạy trọn cả Process. Nêu luôn (các) mod đã ra để khỏi mất thông tin.
            if len(achieved) == 1:
                status = f"Hoàn thành cả Process ✅ — 🎯 Ra mod: {achieved[0][1]}"
            elif achieved:
                joined = " | ".join(f"{nm}: {d}" for nm, d in achieved)
                status = f"Hoàn thành cả Process ✅ — 🎯 Ra mod: {joined}"
            else:
                status = "Hoàn thành cả Process ✅"
            self._log(status, "ok")
        self._log(f"── Kết thúc — tổng {total_loops} vòng ──", "dim")
        return status, total_loops
