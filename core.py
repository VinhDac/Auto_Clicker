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

import io
import os
import re
import sys
import json
import copy
import time
import random
import threading
import ctypes
import uuid
import functools
import contextlib
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

# OCR — chỉ cần cho hành động Abyss (panel "Well of Souls" KHÔNG copy được bằng
# Ctrl+C nên phải đọc chữ bằng mắt). Dùng Windows.Media.Ocr: có sẵn trong Windows
# 10/11, chạy offline, không cần cài thêm chương trình ngoài nào.
# Thiếu thư viện thì HAS_OCR=False và chỉ riêng hành động Abyss bị tắt, phần còn
# lại của app vẫn chạy bình thường (giống cách HAS_CLIP đang làm).
# Tách 2 cờ: chụp màn hình (Pillow) và ĐỌC CHỮ (winrt). Dò ô inventory còn/hết chỉ
# cần chụp màn hình — thiếu mỗi winrt thì Abyss tắt nhưng tính năng đó vẫn chạy.
try:
    from PIL import Image, ImageGrab, ImageStat
    HAS_SCREEN = True
except Exception:
    HAS_SCREEN = False

try:
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
    HAS_OCR = HAS_SCREEN
except Exception:
    HAS_OCR = False

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

PHIEN_BAN = "2.0"          # bản giao diện web (bản tkinter là 1.x)

SETTINGS_DEFAULT = {
    "game": "poe2",
    "pre_click_ms": 60,
    "hover_ms": 250,
    "copy_keys": "ctrl+c",
    "stop_hotkey": "f6",
    "accent": "#ffa657",     # màu nhấn (đổi trong Cài đặt) — cam dịu, dịu mắt trên nền tối
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
TEMPLATE_KINDS = {"process": "Process", "loop": "Action_Loop", "group": "Nhóm HĐ 1 lần"}
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
            "hold_keys": step.get("hold_keys") or "",
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
            "hold_keys": lp.get("hold_keys") or "",
        }
    return None


def make_group_template(step, game):
    """Đóng gói 1 bước Nhóm HĐ 1 lần thành template loại "group"."""
    return {
        "schema": 3,
        "type": "group",
        "name": step.get("name") or "Nhóm",
        "game": game,
        "group": {
            "kind": "group",
            "name": step.get("name") or "Nhóm",
            "actions": step.get("actions") or [],
        },
    }


def normalize_group_template(data):
    """Đọc 1 file template Nhóm -> 1 bước group. Trả None nếu file không phải loại
    group (vd lỡ chọn file Loop hoặc Process) — để bên gọi báo lỗi rõ ràng thay vì
    nhận về một bước méo mó."""
    if not isinstance(data, dict):
        return None
    if data.get("type") == "group" and isinstance(data.get("group"), dict):
        gr = data["group"]
        return {
            "kind": "group",
            "name": gr.get("name") or data.get("name") or "Nhóm",
            "actions": gr.get("actions") or [],
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


def new_step_id():
    """ID bền cho 1 bước. Giao diện đồ thị cần định danh KHÔNG đổi khi bước bị kéo
    sang chỗ khác hay đổi tên — dùng số thứ tự thì kéo-thả một cái là mọi đường nối
    trỏ sai, dùng tên thì đổi tên một cái là gãy."""
    return "s" + uuid.uuid4().hex[:8]


def ensure_step_ids(steps):
    """Cấp ID cho những bước chưa có (file cũ), và dọn ID trùng nếu có.

    Sửa TẠI CHỖ rồi trả về chính danh sách đó, để bên gọi dùng kiểu nào cũng được."""
    da_dung = set()
    for st in steps or []:
        if not isinstance(st, dict):
            continue
        sid = st.get("id")
        if not sid or sid in da_dung:
            sid = new_step_id()
            st["id"] = sid
        da_dung.add(sid)
    return steps


def make_loop_step(name="Loop mới"):
    return {"kind": "loop", "id": new_step_id(), "name": name, "actions": [],
            "loop_start_index": 0, "max_loops": DEFAULT_MAX_LOOPS,
            "hold_keys": ""}


def make_group_step(name="Nhóm mới"):
    """Nhóm HĐ 1 lần: nhiều hành động, chạy đúng 1 lượt, KHÔNG lặp.

    Cố tình không có max_loops / loop_start_index / hold_keys — nhóm không lặp
    nên mấy thứ đó vô nghĩa, có mặt chỉ tổ gây hiểu nhầm."""
    return {"kind": "group", "id": new_step_id(), "name": name, "actions": []}


def make_action_step(action):
    st = dict(action)
    st["kind"] = "action"
    # GIỮ id cũ nếu có: giao diện cũ thay cả bước mỗi lần sửa xong hành động lẻ
    # (`steps[cur] = make_action_step(...)`). Cấp id mới ở đây thì mỗi lần bấm "Sửa"
    # là bước đó thành một nút khác trên đồ thị và mất hết đường nối.
    st["id"] = action.get("id") or new_step_id()
    return st


def is_loop_step(step):
    """Bước LẶP (Action_Loop). Nhóm HĐ 1 lần KHÔNG tính là loop."""
    return step.get("kind") == "loop"


def is_group_step(step):
    return step.get("kind") == "group"


def has_actions(step):
    """Bước có chứa DANH SÁCH hành động không? (Loop và Nhóm thì có, HĐ lẻ thì không)"""
    return is_loop_step(step) or is_group_step(step)


def step_title(step):
    """Tên ngắn của 1 bước (dùng trong thông báo lỗi)."""
    if is_loop_step(step):
        return step.get("name") or "Loop"
    if is_group_step(step):
        return step.get("name") or "Nhóm"
    return (step.get("name") or "").strip() or ACTION_LABELS.get(step.get("type"), "Hành động")


def step_display(step):
    """Chuỗi hiện ở cột danh sách bước."""
    if is_loop_step(step):
        n = len(step.get("actions") or [])
        has_check = any(a.get("type") in GOAL_TYPES for a in (step.get("actions") or []))
        goal = "có mục tiêu" if has_check else "chỉ theo số vòng"
        hold = parse_hold_keys(step.get("hold_keys"))
        hold_txt = f"  ·  ⇧ giữ {'+'.join(hold)}" if hold else ""
        return (f"🔁 {step.get('name') or 'Loop'}   ·  {n} hành động  ·  "
                f"tối đa {step.get('max_loops', DEFAULT_MAX_LOOPS)} vòng  ·  {goal}{hold_txt}")
    if is_group_step(step):
        n = len(step.get("actions") or [])
        return f"▤ {step.get('name') or 'Nhóm'}   ·  {n} hành động  ·  chạy 1 lần"
    return f"⚡ {action_display(step)}   (chạy 1 lần)"


# Trần số bước được chạy trong 1 Process. Đồ thị cho phép nối ngược lên trên (vòng
# lặp ở tầng Process), nên phải có chốt chặn — nếu không, một cái nối sai là app chạy
# mãi không dừng.
MAX_PROCESS_STEPS = 10000


# Hành động RẼ NHÁNH. Khác `check_mod` một trời một vực dù cùng đọc chữ item:
#   check_mod   khớp  -> DỪNG Loop  (đạt mục tiêu)
#   confirm_mod KHÔNG khớp -> DỪNG NHÁNH đang chạy (item không thuộc đường này)
CONFIRM_MOD = "confirm_mod"


def _khoa_nhanh(step):
    """Khoá sắp thứ tự ưu tiên nhánh: TRÊN xuống DƯỚI, rồi TRÁI sang PHẢI.

    Vì sao lấy vị trí trên canvas chứ không phải thứ tự tạo dây: thứ tự tạo dây là
    thứ VÔ HÌNH — kéo khối cách mấy cũng không đổi, nên người dùng không có cách nào
    biết nhánh nào được thử trước. Vị trí thì nhìn thấy, và nhãn A/B trên huy hiệu
    đổi ngay lúc thả chuột, nên ưu tiên không bao giờ là thứ ngầm.
    Cuối cùng chốt bằng `id` để hai khối chồng khít nhau vẫn ra thứ tự cố định."""
    pos = step.get("pos") or []
    try:
        x, y = float(pos[0]), float(pos[1])
    except (TypeError, ValueError, IndexError):
        x = y = 0.0
    return (y, x, str(step.get("id") or ""))


def flow_map(steps, edges):
    """(bảng_tra_id, kế_tiếp) với `kế_tiếp[id] = [id, ...]` THEO ĐÚNG THỨ TỰ ƯU TIÊN.

    ĐÂY LÀ NGUỒN SỰ THẬT DUY NHẤT VỀ THỨ TỰ NHÁNH.

    Trước khi có rẽ nhánh, lời hứa "số ở góc khối không nói dối" được giữ bằng cách
    cho bộ chạy và bộ đánh số đi CHUNG một phép duyệt. Có nhánh rồi thì không còn
    đúng nữa: huy hiệu vẽ CẢ CÂY (tĩnh) còn bộ chạy chỉ đi MỘT đường (động) —
    chúng không thể là cùng một phép duyệt.

    Chỗ duy nhất nó còn có thể nói dối là THỨ TỰ ƯU TIÊN NHÁNH: huy hiệu ghi A
    trước B mà bộ chạy thử B trước thì sai hoàn toàn. Nên đó chính là thứ phải dùng
    chung — và cả hai bên đều chỉ lấy thứ tự từ đúng hàm này."""
    theo_id = {s.get("id"): s for s in (steps or []) if isinstance(s, dict) and s.get("id")}
    ke = {}
    for e in (edges or []):
        if (e.get("port") or "out") != "out":
            continue
        a, b = e.get("from"), e.get("to")
        if a in theo_id and b in theo_id:
            ds = ke.setdefault(a, [])
            if b not in ds:          # nối hai lần cùng một cặp thì vẫn chỉ là một nhánh
                ds.append(b)
    for ds in ke.values():
        ds.sort(key=lambda sid: _khoa_nhanh(theo_id[sid]))
    return theo_id, ke


def is_branch_gate(step):
    """Khối này có phải CỔNG của một nhánh không.

    Cổng = khối "HĐ lẻ" mang đúng một hành động `confirm_mod`.

    Cố ý KHÔNG cho Nhóm hay Loop làm cổng. Ở điểm rẽ các nhánh được thử lần lượt,
    nên nhánh trượt phải LÙI LẠI ĐƯỢC — mà lùi chỉ an toàn khi nhánh đó chưa kịp
    làm gì trong game. Một khối HĐ lẻ `confirm_mod` chỉ đọc chữ item nên lùi bao
    nhiêu lần cũng vô hại; một Nhóm thì không hứa được điều đó (nó có thể click vài
    phát rồi mới kiểm tra, và cú click ấy không rút lại được).

    `confirm_mod` nằm giữa một Nhóm vẫn dùng bình thường — nó chỉ không đóng vai
    cổng, mà đóng vai chốt chặn "không khớp thì bỏ nốt nhóm này"."""
    return (isinstance(step, dict) and not is_loop_step(step)
            and not is_group_step(step) and step.get("type") == CONFIRM_MOD)


def _khoa_dieu_kien(conds):
    """Dấu vân tay của một bộ điều kiện, để phát hiện hai cổng giống hệt nhau.

    Sắp khoá trước khi ghép: hai dict cùng nội dung mà khác thứ tự khoá vẫn phải ra
    cùng một chuỗi, nếu không cảnh báo "hai nhánh trùng điều kiện" sẽ bỏ sót."""
    return json.dumps([sorted((str(k), str(v)) for k, v in (c or {}).items())
                       for c in (conds or [])], ensure_ascii=False)


def flow_entry(steps, edges):
    """Bước BẮT ĐẦU = bước đầu tiên trong danh sách mà không có đường nối đi vào.

    Lấy "đầu tiên trong danh sách" làm tiêu chí phá hoà: cần một quy tắc xác định,
    và thứ tự tạo khối là thứ người dùng nhìn thấy được (số góc khối).
    Không tìm được (mọi bước đều có đường vào -> đồ thị toàn vòng) thì trả None,
    `validate_process` sẽ báo lỗi thay vì đoán bừa.
    """
    ds = [s for s in (steps or []) if isinstance(s, dict) and s.get("id")]
    if not ds:
        return None
    co_vao = {e.get("to") for e in (edges or []) if (e.get("port") or "out") == "out"}
    for s in ds:
        if s["id"] not in co_vao:
            return s["id"]
    return None


def _chu_nhanh(k):
    """0 -> 'A', 1 -> 'B'. Quá 26 nhánh từ một khối là chuyện không xảy ra thật
    (phải có 26 mod khác nhau), nhưng vẫn phải ra chuỗi phân biệt được."""
    return chr(65 + k) if k < 26 else f"({k + 1})"


def diem_gop(cur, ke):
    """Khối đầu tiên mà MỌI nhánh của `cur` đều dẫn tới, hoặc None.

    Nhờ nó mà số quay về mức trên cùng sau khi hết nhánh: 4 rẽ ra 4A/4B, hai nhánh
    chụm lại thì khối sau đó là "5" chứ không phải "4A.4". Không nhánh nào gặp nhau
    -> None, nghĩa là mỗi nhánh tự kết thúc và đơn giản là KHÔNG CÓ số 5 nào cả."""
    nhanh = ke.get(cur) or []
    if len(nhanh) < 2:
        return None

    def toi_duoc(bd):
        tham, hang = set(), [bd]
        while hang:
            n = hang.pop(0)
            if n in tham:
                continue
            tham.add(n)
            hang.extend(ke.get(n) or [])
        return tham

    chung = None
    for uv in nhanh:
        t = toi_duoc(uv)
        chung = t if chung is None else (chung & t)
    chung = (chung or set()) - {cur}      # trừ chính nó, tránh vòng tự trỏ về
    if not chung:
        return None
    # Lấy cái GẦN NHẤT: duyệt rộng từ các đầu nhánh, gặp đầu tiên là điểm gộp.
    tham, hang = set(), list(nhanh)
    while hang:
        n = hang.pop(0)
        if n in tham:
            continue
        tham.add(n)
        if n in chung:
            return n
        hang.extend(ke.get(n) or [])
    return None


def flow_order(steps, edges):
    """Nhãn hiện ở góc khối -> {id: "1" | "4" | "4A" | "4A.2" | "4A.2B.1"}.

    LUẬT: SỐ = đi được bao xa, CHỮ = đi nhánh nào.
    Chữ dính ngay sau số của khối RẼ (khối 4 rẽ ra thì cổng hai nhánh là 4A, 4B),
    dấu chấm ngăn giữa nhãn nhánh và số bước bên trong nhánh (4A.1, 4A.2). Hai thứ
    so le nhau vì một nhánh luôn chứa một chuỗi, và một chuỗi luôn có thể rẽ tiếp.

    Ngữ pháp: các nhóm ngăn bởi dấu chấm, mỗi nhóm = SỐ rồi tới các CHỮ (có thể
    không có). "4A.2B" tách thành "4A" | "2B" — chữ không bao giờ mở đầu một nhóm,
    số luôn đứng ngay sau dấu chấm, nên tách được bằng máy, không nhập nhằng.

    Trả về: {"order": {id: nhãn}, "unreachable": [id...], "entry": id|None,
             "loop": bool}
    """
    theo_id, ke = flow_map(steps, edges)
    bat_dau = flow_entry(steps, edges)
    nhan = {}
    vong = [False]

    def dat(sid, s):
        """Gán nhãn; đã có nhãn nghĩa là quay lại chỗ cũ -> đồ thị có vòng."""
        if sid in nhan:
            vong[0] = True
            return False
        nhan[sid] = s
        return True

    def chuoi(cur, tien_to, i, dung_tai):
        """Đánh số một chuỗi; khối đầu mang nhãn f"{tien_to}{i}", rồi +1 dần.
        Dừng khi tới `dung_tai` (điểm gộp — để dành cho mức trên) hoặc hết đường."""
        for _ in range(MAX_PROCESS_STEPS):
            if cur is None or cur not in theo_id or cur == dung_tai:
                return
            if not dat(cur, f"{tien_to}{i}"):
                return
            if not re_nhanh(cur, f"{tien_to}{i}", dung_tai):
                nhanh = ke.get(cur) or []
                cur, i = (nhanh[0] if nhanh else None), i + 1
                continue
            gop = diem_gop(cur, ke)
            if gop is None or gop == dung_tai:
                return
            cur, i = gop, i + 1

    def re_nhanh(cur, nhan_cur, dung_tai):
        """Nếu `cur` là điểm rẽ thì đánh số hết các nhánh của nó. True = có rẽ."""
        nhanh = ke.get(cur) or []
        if len(nhanh) < 2:
            return False
        gop = diem_gop(cur, ke)
        for k, uv in enumerate(nhanh):
            dau_nhanh(uv, nhan_cur + _chu_nhanh(k), gop if gop is not None else dung_tai)
        return True

    def dau_nhanh(uv, nhan_nhanh, dung_tai):
        """Khối ĐẦU nhánh mang đúng nhãn nhánh ("4A" — chính là cái cổng), các khối
        sau nó mang "4A.1", "4A.2"... Cổng lại rẽ tiếp thì chữ nối thêm chữ ("4AA"),
        vẫn đúng ngữ pháp vì một nhóm cho phép nhiều chữ."""
        if uv is None or uv not in theo_id or uv == dung_tai:
            return
        if not dat(uv, nhan_nhanh):
            return
        if re_nhanh(uv, nhan_nhanh, dung_tai):
            gop = diem_gop(uv, ke)
            if gop is not None and gop != dung_tai:
                chuoi(gop, nhan_nhanh + ".", 1, dung_tai)
            return
        sau = ke.get(uv) or []
        if sau:
            chuoi(sau[0], nhan_nhanh + ".", 1, dung_tai)

    chuoi(bat_dau, "", 1, None)
    return {"order": nhan,
            "unreachable": [sid for sid in theo_id if sid not in nhan],
            "entry": bat_dau,
            "loop": vong[0]}


def validate_flow_graph(steps, edges):
    """Soát riêng phần ĐỒ THỊ. Tách khỏi `validate_actions` vì đây là lỗi ở mức nối
    dây, không phải ở mức một hành động."""
    ra = []
    ds = [s for s in (steps or []) if isinstance(s, dict) and s.get("id")]
    if not ds:
        return ra

    theo_id, ke = flow_map(steps, edges)

    # ---- Khối trùng id ----
    # `flow_map` tra theo id nên hai khối cùng id thì một cái BIẾN MẤT khỏi sơ đồ:
    # không nhãn, không nằm trong "không bao giờ chạy tới", không dấu vết gì. Người
    # dùng nhìn canvas thấy đủ khối, chạy thì thiếu. File chép tay hoặc sửa tay là ra.
    dem_id = {}
    for s_ in ds:
        dem_id[s_["id"]] = dem_id.get(s_["id"], 0) + 1
    for sid, n in dem_id.items():
        if n > 1:
            ra.append({"severity": "error", "step": sid, "index": None,
                       "message": f'Có {n} khối trùng id với nhau ("{step_title(theo_id[sid])}") '
                                  f"— chỉ MỘT cái được chạy, những cái còn lại biến mất khỏi "
                                  f"sơ đồ mà không báo gì. Hãy xoá bớt rồi tạo lại."})

    # ---- Đường nối trỏ về chính nó ----
    # Không chặn thì nó thành "một nhánh của chính mình" và thông báo lỗi rẽ nhánh
    # bên dưới sẽ nói những câu vô nghĩa kiểu 'khối 2 rẽ ra 2 nhánh: "2" và "3"'.
    for e in (edges or []):
        if e.get("from") and e.get("from") == e.get("to") and e["from"] in theo_id:
            ra.append({"severity": "error", "step": e["from"], "index": None,
                       "message": f'"{step_title(theo_id[e["from"]])}" có đường nối trỏ về '
                                  f"CHÍNH NÓ — chạy tới đây là quay lại chính mình mãi mãi."})

    # ---- Cổng khớp rồi mà phía sau trống ----
    for sid, st_ in theo_id.items():
        if is_branch_gate(st_) and not ke.get(sid):
            ra.append({"severity": "warning", "step": sid, "index": None,
                       "message": f'"{step_title(st_)}" khớp điều kiện rồi thì không có gì '
                                  f"phía sau — Process kết thúc ngay tại đó. Nối tiếp một khối "
                                  f"vào nếu bạn muốn nhánh này làm gì đó."})

    # ---- Luật rẽ nhánh ----
    # Nhiều đường ra KHÔNG còn là lỗi, nhưng phải quyết định được đi đường nào. Ở
    # điểm rẽ các nhánh được thử lần lượt trên->dưới, nên mỗi nhánh phải mở đầu bằng
    # một CỔNG (khối HĐ lẻ "Xác nhận mod"), trừ tối đa MỘT nhánh mặc định — và nhánh
    # mặc định luôn khớp nên bắt buộc phải xếp CUỐI, nếu không mấy nhánh sau nó không
    # bao giờ được thử tới.
    for sid, nhanh in ke.items():
        if len(nhanh) < 2 or sid not in theo_id:
            continue
        ten = step_title(theo_id[sid])
        khong_cong = [uv for uv in nhanh if not is_branch_gate(theo_id[uv])]
        if len(khong_cong) > 1:
            ds_ten = ", ".join(f'"{step_title(theo_id[uv])}"' for uv in khong_cong)
            ra.append({"severity": "error", "step": sid, "index": None,
                       "message": f'"{ten}" rẽ {len(nhanh)} nhánh nhưng có {len(khong_cong)} '
                                  f"nhánh không có cổng kiểm tra ({ds_ten}) — chạy tới đây "
                                  f"không biết chọn nhánh nào. Mỗi nhánh phải bắt đầu bằng "
                                  f'khối HĐ lẻ "{ACTION_LABELS[CONFIRM_MOD]}", nhiều nhất '
                                  f"một nhánh được để trống làm nhánh mặc định."})
        elif khong_cong and khong_cong[0] != nhanh[-1]:
            ra.append({"severity": "error", "step": sid, "index": None,
                       "message": f'"{step_title(theo_id[khong_cong[0]])}" là nhánh mặc định '
                                  f'(không có cổng kiểm tra) nhưng không nằm dưới cùng của '
                                  f'"{ten}" — nhánh mặc định luôn khớp nên các nhánh xếp dưới '
                                  f"nó không bao giờ chạy tới. Hãy kéo nó xuống thấp nhất."})
        elif not khong_cong:
            ra.append({"severity": "warning", "step": sid, "index": None,
                       "message": f'"{ten}" rẽ {len(nhanh)} nhánh và nhánh nào cũng có điều '
                                  f"kiện — item không khớp nhánh nào thì Process kết thúc tại "
                                  f"đây. Muốn luôn có lối đi thì thêm một nhánh không cổng "
                                  f"xếp dưới cùng."})
        # Hai cổng cùng điều kiện y hệt: cái dưới không bao giờ tới lượt.
        da_thay = {}
        for uv in nhanh:
            if not is_branch_gate(theo_id[uv]):
                continue
            khoa = _khoa_dieu_kien(theo_id[uv].get("conditions"))
            if khoa in da_thay:
                ra.append({"severity": "warning", "step": uv, "index": None,
                           "message": f'"{step_title(theo_id[uv])}" có điều kiện giống hệt '
                                      f'"{step_title(theo_id[da_thay[khoa]])}" xếp trên — '
                                      f"khớp thì nhánh trên thắng, nhánh này không bao giờ chạy."})
            else:
                da_thay[khoa] = uv

    kq = flow_order(steps, edges)
    if kq["entry"] is None:
        ra.append({"severity": "error", "step": None, "index": None,
                   "message": "Không tìm được bước bắt đầu — mọi bước đều có đường nối "
                              "đi vào. Hãy gỡ bớt một đường để có chỗ khởi đầu."})
    if kq.get("loop"):
        # Nối ngược lên trên là HỢP LỆ (vòng lặp ở tầng Process), nhưng phải nói ra:
        # nó chỉ dừng khi chạm trần MAX_PROCESS_STEPS, và nếu vòng đi qua một điểm rẽ
        # thì MỖI VÒNG là một lần rê chuột + Ctrl+C đọc item. Vòng vô tình = nện
        # clipboard hàng nghìn lần trong game.
        qua_diem_re = any(len(v) > 1 for v in ke.values())
        ra.append({"severity": "warning", "step": None, "index": None,
                   "message": ("Đường nối tạo thành VÒNG LẶP ở tầng Process. Nó chỉ dừng khi "
                               f"chạy đủ {MAX_PROCESS_STEPS} bước"
                               + (" — và vì vòng đi qua điểm rẽ nhánh, mỗi vòng là một lần "
                                  "đọc chữ item, tức là hàng nghìn lần Ctrl+C trong game."
                                  if qua_diem_re else ".")
                               + " Muốn lặp thì nên dùng khối Action_Loop.")})

    for sid in kq["unreachable"]:
        ra.append({"severity": "warning", "step": sid, "index": None,
                   "message": f'"{step_title(theo_id[sid])}" không bao giờ chạy tới — '
                              f"chưa có đường nối dẫn vào từ bước bắt đầu."})
    return ra


def _giu_id_pos(nguon, dich):
    """Chuyển `id` và `pos` từ dict gốc sang dict đã chuẩn hoá.

    `normalize_process` dựng lại từng bước bằng danh sách khoá cố định (cố ý — để file
    rác không lọt vào). Nhưng thế thì hai khoá này bị rơi mất: `id` là định danh nút
    trên đồ thị, `pos` là chỗ người dùng đã kéo nút tới. Mất `pos` là mỗi lần mở file
    sơ đồ lại nhảy về vị trí khác."""
    if nguon.get("id"):
        dich["id"] = nguon["id"]
    pos = nguon.get("pos")
    if isinstance(pos, (list, tuple)) and len(pos) == 2:
        try:
            dich["pos"] = [float(pos[0]), float(pos[1])]
        except (TypeError, ValueError):
            pass
    return dich


def default_edges(steps):
    """Chuỗi thẳng bước 1 → 2 → 3… — đúng cách Process vẫn chạy từ trước tới nay.

    Nhờ hàm này mà "không có đường nối" và "nối thành chuỗi thẳng" là MỘT. File cũ
    (không có khoá `edges`) mở ra vẫn ra đúng sơ đồ nó vẫn chạy, không phải di cư gì."""
    ds = [s for s in (steps or []) if isinstance(s, dict) and s.get("id")]
    return [{"from": a["id"], "to": b["id"], "port": "out"}
            for a, b in zip(ds, ds[1:])]


def clean_edges(edges, steps):
    """Bỏ đường nối trỏ tới bước không còn tồn tại, và bỏ trùng.

    Không tự ý sửa ý người dùng thành thứ khác — chỉ vứt cái đã vô nghĩa. Nối tới một
    bước đã xoá thì giữ lại cũng chẳng để làm gì ngoài việc gây lỗi khó hiểu."""
    co = {s.get("id") for s in (steps or []) if isinstance(s, dict)}
    ra, thay = [], set()
    for e in edges or []:
        if not isinstance(e, dict):
            continue
        a, b = e.get("from"), e.get("to")
        if a not in co or b not in co:
            continue
        khoa = (a, b, e.get("port") or "out")
        if khoa in thay:
            continue
        thay.add(khoa)
        moi = {"from": a, "to": b, "port": e.get("port") or "out"}
        # Cạnh nào của hộp thì đường nối cắm vào — thuần thị giác, nhưng phải lưu,
        # nếu không mở lại file là sơ đồ tự vẽ khác đi so với lúc người dùng sắp.
        for k in ("from_side", "to_side"):
            if e.get(k):
                moi[k] = str(e[k])
        ra.append(moi)
    return ra


def make_process_template(name, game, start_delay, steps, edges=None):
    """Đóng gói cả Process thành template loại "process".

    Ở đây chứ không ở tầng giao diện: `make_loop_template`/`make_group_template` vốn đã
    nằm trong core, riêng bản Process trước đây kẹt lại ở tầng giao diện
    với `schema`/`type` viết cứng. Hai giao diện (tkinter và web) mà
    mỗi bên tự ráp định dạng thì sớm muộn cũng lệch nhau."""
    st = ensure_step_ids(steps or [])
    return {
        "schema": 3,
        "type": "process",
        "name": (name or "").strip() or "Process 1",
        "game": game,
        "start_delay": max(0, int(start_delay or 0)),
        "steps": st,
        # Giao diện tkinter cũ không truyền edges -> ghi ra chuỗi thẳng, đúng thứ tự
        # nó vẫn chạy. Không có nhánh nào bị bịa ra sau lưng người dùng.
        "edges": clean_edges(edges, st) if edges is not None else default_edges(st),
    }


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
                steps.append(_giu_id_pos(st, {
                    "kind": "loop",
                    "name": st.get("name") or "Loop",
                    "actions": st.get("actions") or [],
                    "loop_start_index": int(st.get("loop_start_index") or 0),
                    "max_loops": int(st.get("max_loops") or DEFAULT_MAX_LOOPS),
                    "hold_keys": st.get("hold_keys") or "",
                }))
            elif st.get("kind") == "group":
                steps.append(_giu_id_pos(st, {
                    "kind": "group",
                    "name": st.get("name") or "Nhóm",
                    "actions": st.get("actions") or [],
                }))
            elif st.get("type"):
                steps.append(_giu_id_pos(st, make_action_step(st)))
        steps = ensure_step_ids(steps)
        e = data.get("edges")
        return {
            "name": data.get("name") or "Process 1",
            "start_delay": data.get("start_delay", 3),
            "steps": steps,
            "edges": clean_edges(e, steps) if isinstance(e, list) else default_edges(steps),
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
                "hold_keys": lp.get("hold_keys") or "",
            })
        if len(steps) > 1:
            note = f"Đã nạp {len(steps)} Action_Loop từ file thành {len(steps)} bước."
        steps = ensure_step_ids(steps)
        return {
            "name": data.get("name") if data.get("name") not in (None, "template") else "Process 1",
            "start_delay": data.get("start_delay", 3),
            "steps": steps,
            "edges": default_edges(steps),
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
        "hold_keys": "",          # định dạng cũ chưa có khái niệm này
    }]
    steps = ensure_step_ids(steps)
    return {"name": "Process 1", "start_delay": norm["start_delay"],
            "steps": steps, "edges": default_edges(steps), "note": norm["note"]}


# ---------------- Kiểm tra cấu hình trước khi chạy (panel "Vấn đề") ----------------
def virtual_screen_rect():
    """(x, y, w, h) của toàn bộ vùng desktop ảo (gộp mọi màn hình)."""
    try:
        u = ctypes.windll.user32
        return (u.GetSystemMetrics(76), u.GetSystemMetrics(77),
                u.GetSystemMetrics(78), u.GetSystemMetrics(79))
    except Exception:
        return None


def abyss_problems(a, screen=None):
    """Soát riêng 1 hành động Abyss. Trả về [{"severity", "message"}]."""
    out = []

    def add(sev, msg):
        out.append({"severity": sev, "message": msg})

    frame = a.get("frame")
    if not frame or len(frame) != 4 or frame[2] <= 0 or frame[3] <= 0:
        add("error", "\"Abyss\" chưa căn khung — bấm \"🖼 Căn khung\" trong hành động.")
    else:
        fx, fy, fw, fh = frame
        if screen:
            sx, sy, sw, sh = screen
            if not (sx <= fx and sy <= fy and fx + fw <= sx + sw and fy + fh <= sy + sh):
                add("warning", f"\"Abyss\": khung ({fx}, {fy}) {fw}×{fh} nằm ngoài màn hình "
                               f"hiện tại — có thể căn từ độ phân giải khác.")
        # Dải mod cao ~28% khung; dưới ~30px thì chữ quá nhỏ, OCR bắt đầu sai.
        if fh * ABYSS_BANDS[0][1] < 30:
            add("warning", f"\"Abyss\": khung hơi nhỏ ({fw}×{fh}) — chữ có thể quá nhỏ để "
                           f"đọc chính xác. Căn lại cho trùm đúng panel.")
    conds = a.get("conditions") or []
    if not conds:
        add("error", "\"Abyss\" chưa có điều kiện mod nào.")
    # Cùng 1 mod ở cả 2 bảng là mâu thuẫn -> Điều kiện thắng, nhưng phải nói ra,
    # không thì người dùng tưởng mình đã cấm được nó.
    cam = {norm(e.get("mod", "")) for e in (a.get("excludes") or []) if e.get("mod")}
    trung = [c.get("mod") for c in conds if norm(c.get("mod", "")) in cam]
    if trung:
        add("warning", f"\"Abyss\": mod nằm ở CẢ điều kiện lẫn loại trừ "
                       f"({', '.join(trung)}) — Điều kiện thắng, dòng loại trừ vô tác dụng.")
    reason = ocr_unavailable_reason()
    if reason:
        add("error", f"\"Abyss\" không dùng được: {reason}")
    return out


def validate_actions(actions, screen=None):
    """Soát TỪNG hành động, không quan tâm nó nằm trong Loop hay trong Nhóm.
    Dùng chung cho validate_flow (Loop) và validate_group (Nhóm)."""
    problems = []

    def err(msg, idx=None):
        problems.append({"severity": "error", "message": msg, "index": idx})

    def warn(msg, idx=None):
        problems.append({"severity": "warning", "message": msg, "index": idx})

    for i, a in enumerate(actions):
        t = a.get("type")
        if t not in ACTION_TYPES:
            # Template lưu từ bản cũ có thể còn "move"/"double_click"/"scroll".
            # do_action() sẽ lặng lẽ không làm gì -> phải báo, không để chạy mù.
            err(f"Loại hành động \"{t}\" không còn được hỗ trợ — xoá dòng này "
                f"hoặc thay bằng loại khác.", i)
            continue
        if t == "check_mod":
            if not a.get("point"):
                err("\"Kiểm tra mod\" chưa chọn điểm rê chuột vào item.", i)
            if not (a.get("conditions") or []):
                err("\"Kiểm tra mod\" chưa có điều kiện mod nào.", i)
        elif t == "abyss":
            for p in abyss_problems(a, screen):
                problems.append({"severity": p["severity"], "message": p["message"], "index": i})
        elif t == "mod_click":
            keys = parse_hold_keys(a.get("keys"))
            if not keys:
                err("\"Giữ phím + click\" chưa chọn phím nào.", i)
            else:
                bad = [k for k in keys if not is_valid_key(k)]
                if bad:
                    err(f"\"Giữ phím + click\": phím không hợp lệ: {', '.join(bad)}. "
                        f"Dùng tên như shift, ctrl, alt.", i)
            if not a.get("point"):
                err("\"Giữ phím + click\" chưa chọn điểm click.", i)
        elif t == "key_press" and not is_valid_key(str(a.get("key", "")).strip().lower()):
            err(f"\"Nhấn phím\": phím không hợp lệ: {a.get('key', '')}", i)
        elif t == "move_wasd":
            loi = wasd_problem(a.get("keys"))
            if loi:
                err(f"\"Di chuyển\": {loi}.", i)
            try:
                if int(a.get("ms", MOVE_DEFAULT_MS)) <= 0:
                    err("\"Di chuyển\": thời gian giữ phải lớn hơn 0 ms.", i)
            except (TypeError, ValueError):
                err("\"Di chuyển\": thời gian giữ không phải là số.", i)
        if t in POINT_TYPES and a.get("grid"):
            for p in inv_problems(a["grid"], screen):
                problems.append({"severity": p["severity"], "message": p["message"], "index": i})
            continue          # bật lưới thì điểm X/Y không dùng tới, khỏi soát
        point = a.get("point")
        if point and screen:
            sx, sy, sw, sh = screen
            if not (sx <= point[0] < sx + sw and sy <= point[1] < sy + sh):
                warn(f"Điểm ({point[0]}, {point[1]}) nằm NGOÀI màn hình hiện tại "
                     f"— có thể toạ độ lưu từ độ phân giải khác.", i)
    return problems


def validate_group(actions, has_clip=None, screen=None):
    """Soát 1 Nhóm HĐ 1 lần. KHÔNG kiểm số vòng lặp, KHÔNG kiểm điểm bắt đầu Loop,
    và KHÔNG cảnh báo "chưa có mục tiêu" — nhóm không lặp nên chẳng có gì để dừng."""
    if has_clip is None:
        has_clip = HAS_CLIP
    if screen is None:
        screen = virtual_screen_rect()

    problems = []
    if not actions:
        problems.append({"severity": "warning", "index": None,
                         "message": "Nhóm chưa có hành động nào — bước này sẽ không làm gì."})
        return problems
    if not has_clip and any(a.get("type") in ("check_mod", CONFIRM_MOD) for a in actions):
        problems.append({"severity": "error", "index": None,
                         "message": "Thiếu thư viện pyperclip → không đọc được chữ item. "
                                    "Cài: pip install pyperclip"})
    problems.extend(validate_actions(actions, screen))
    return problems


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

    # `confirm_mod` trong Loop là bẫy: luật của nó là "không khớp -> dừng nhánh",
    # nên ngay vòng đầu item chưa ra mod là cả Process dừng — trong khi thứ người
    # dùng muốn gần như chắc chắn là "roll tới khi ra mod" = `check_mod`.
    for i, a in enumerate(actions):
        if a.get("type") == CONFIRM_MOD:
            warn(f"\"{ACTION_LABELS[CONFIRM_MOD]}\" nằm trong Loop: không khớp là DỪNG "
                 f"ngay từ vòng đầu, Loop sẽ không roll thêm vòng nào. Muốn roll tới khi "
                 f"ra mod thì dùng \"{ACTION_LABELS['check_mod']}\"; còn để rẽ nhánh thì "
                 f"đặt nó thành khối HĐ lẻ riêng ngoài canvas.", i)

    checks = [i for i, a in enumerate(actions) if a.get("type") == "check_mod"]
    goals = [i for i, a in enumerate(actions) if a.get("type") in GOAL_TYPES]
    if not goals:
        warn("Chưa có hành động \"🔍 Kiểm tra mod\" hay \"🌀 Abyss\" → Loop chỉ dừng "
             "theo số vòng, không tự dừng khi item ra mod mong muốn.")
    elif checks and has_clip is False:
        err("Thiếu thư viện pyperclip → không đọc được chữ item. Cài: pip install pyperclip")

    for i in goals:
        if i < loop_start_index:
            warn(f"\"{ACTION_LABELS.get(actions[i].get('type'), '')}\" nằm ở phần chỉ chạy "
                 f"1 lần → chỉ kiểm tra được đúng 1 lần lúc đầu, không kiểm tra mỗi vòng.", i)

    problems.extend(validate_actions(actions, screen))

    try:
        ml = int(max_loops)
        if ml <= 0:
            err("Số vòng lặp phải lớn hơn 0.")
        elif ml > 100000:
            warn(f"Số vòng lặp rất lớn ({ml}) — chắc chắn muốn chạy lâu vậy?")
    except (TypeError, ValueError):
        err("Số vòng lặp không phải là số.")

    return problems


def validate_process(steps, has_clip=None, screen=None, edges=None):
    """Soát cả Process. Trả về [{"severity", "message", "step": int|None, "index": int|None}]
    trong đó `step` = vị trí bước, `index` = vị trí hành động trong bước đó (nếu có).

    `edges` (tuỳ chọn) bật thêm phần soát ĐỒ THỊ: có bước bắt đầu không, có bước nào
    không bao giờ chạy tới không, có bước nào chia 2 đường ra cùng cổng không.
    Bỏ trống thì bỏ qua phần đó — giao diện tkinter cũ không có khái niệm đường nối."""
    if has_clip is None:
        has_clip = HAS_CLIP
    if screen is None:
        screen = virtual_screen_rect()

    problems = []
    if edges is not None:
        problems.extend(validate_flow_graph(steps, edges))
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
        elif is_group_step(st):
            for p in validate_group(st.get("actions") or [], has_clip, screen):
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
            elif st.get("type") == "abyss":
                for p in abyss_problems(st, screen):
                    problems.append({"severity": p["severity"], "step": si, "index": None,
                                     "message": f"{label}: {p['message']}"})
            point = st.get("point")
            if point and screen:
                sx, sy, sw, sh = screen
                if not (sx <= point[0] < sx + sw and sy <= point[1] < sy + sh):
                    problems.append({"severity": "warning", "step": si, "index": None,
                                     "message": f"{label}: điểm ({point[0]}, {point[1]}) nằm NGOÀI "
                                                f"màn hình hiện tại — có thể toạ độ lưu từ độ phân giải khác."})
    return problems


# ---------------- Hành động ----------------
ACTION_TYPES = ["left_click", "right_click", "mod_click", "key_press", "move_wasd",
                "delay", "check_mod", CONFIRM_MOD, "abyss"]
# Nhãn thuần chữ, KHÔNG emoji: chúng hiện ở dropdown "Loại:" của hộp thoại hành
# động, và giao diện tự vẽ icon nét theo `type` cho khớp phần còn lại.
ACTION_LABELS = {
    "left_click": "Trái-click", "right_click": "Phải-click",
    "mod_click": "Giữ phím + click",
    "key_press": "Nhấn phím", "delay": "Delay",
    "move_wasd": "Di chuyển (WASD)",
    "check_mod": "Kiểm tra mod",
    CONFIRM_MOD: "Xác nhận mod (rẽ nhánh)",
    "abyss": "Abyss — chọn mod",
}

# Hành động QUYẾT ĐỊNH ĐƯỜNG ĐI: không khớp thì nhánh đang chạy dừng tại đó.
# Tách khỏi GOAL_TYPES vì ý nghĩa ngược nhau — GOAL_TYPES khớp là XONG SỚM, còn
# cái này khớp mới được ĐI TIẾP.
BRANCH_TYPES = (CONFIRM_MOD,)

# ---- Di chuyển WASD ----
# W/S và A/D là 2 TRỤC ngược nhau: giữ cả hai là triệt tiêu, nhân vật đứng im.
# Giao diện cho tick W thì tự bỏ S (và ngược lại), nên trạng thái sai KHÔNG THỂ
# tạo ra được — khỏi cần luật chặn. Hệ quả: nhiều nhất 2 phím, không bao giờ
# ngược chiều, đúng 8 hướng đi được.
WASD_OPPOSITE = {"w": "s", "s": "w", "a": "d", "d": "a"}
WASD_ORDER = ["w", "s", "a", "d"]          # thứ tự chuẩn khi ghi ra: dọc trước, ngang sau
WASD_NAMES = {"w": "lên", "s": "xuống", "a": "trái", "d": "phải"}
WASD_PAIR_NAMES = {
    ("w", "a"): "chéo lên-trái", ("w", "d"): "chéo lên-phải",
    ("s", "a"): "chéo xuống-trái", ("s", "d"): "chéo xuống-phải",
}
MOVE_DEFAULT_MS = 1000


def wasd_sort(keys):
    """Sắp phím theo thứ tự chuẩn (dọc trước) để chuỗi lưu ra luôn ổn định."""
    return [k for k in WASD_ORDER if k in keys]


def wasd_display(keys):
    """'w+a' -> 'W+A (chéo lên-trái)'. Dùng cho mô tả trong danh sách hành động."""
    ks = wasd_sort(parse_hold_keys(keys) if isinstance(keys, str) else keys)
    if not ks:
        return "(chưa chọn hướng)"
    ten = WASD_PAIR_NAMES.get(tuple(ks)) if len(ks) == 2 else WASD_NAMES.get(ks[0])
    return f"{'+'.join(k.upper() for k in ks)}" + (f" ({ten})" if ten else "")


def wasd_problem(keys):
    """Lý do bộ phím không hợp lệ, hoặc None nếu ổn. Giao diện không tạo ra được
    trạng thái sai, nhưng file sửa tay thì có — phải bắt."""
    ks = parse_hold_keys(keys) if isinstance(keys, str) else list(keys or [])
    if not ks:
        return "chưa chọn hướng nào"
    la = [k for k in ks if k not in WASD_OPPOSITE]
    if la:
        return f"chỉ dùng được W/A/S/D, gặp: {', '.join(la)}"
    if len(set(ks)) > 2:
        return f"nhiều nhất 2 hướng, đang có {len(set(ks))}"
    for k in ks:
        if WASD_OPPOSITE[k] in ks:
            return f"{k.upper()} và {WASD_OPPOSITE[k].upper()} ngược chiều nhau, giữ cả hai thì đứng im"
    return None
# Hành động có thể kết thúc sớm cả Loop khi đạt mục tiêu.
GOAL_TYPES = ("check_mod", "abyss")


class HeldKeys:
    """Sổ theo dõi phím đang được GIỮ suốt một bước Loop (ô tick "Giữ Shift").

    Vì sao phải quản tập trung chứ không để hành động tự lo: phím giữ là trạng
    thái của CẢ HỆ THỐNG. Loop dừng giữa chừng (bấm Dừng, F6, failsafe, hay lỗi)
    mà chưa thả thì Shift kẹt trong toàn Windows — gõ gì cũng ra chữ hoa, click
    đâu cũng thành shift-click.

    KHÔNG có cơ chế "nhả tạm": đã thử và đó là sai lầm. Nhả Shift ra giữa chừng
    (dù chỉ để bắn Ctrl+C) làm game rớt khỏi chế độ dùng-liên-tục ở MỖI vòng lặp
    — đúng cái bệnh đang đi chữa. Đã kiểm chứng trong game: Ctrl+C vẫn đọc được
    chữ item bình thường khi Shift đang giữ.
    """

    def __init__(self):
        self.keys = []

    def hold(self, keys):
        for k in keys:
            try:
                pyautogui.keyDown(k)
            except Exception:
                continue
            if k not in self.keys:
                self.keys.append(k)

    def release_all(self):
        """Thả hết, theo thứ tự ngược. Gọi được nhiều lần, không sao."""
        for k in reversed(list(self.keys)):
            try:
                pyautogui.keyUp(k)
            except Exception:
                pass
        self.keys = []
POINT_TYPES = ("left_click", "right_click")
# Phím giữ hay dùng trong PoE: Shift+click (tách stack), Ctrl+click (chuyển stash)
MOD_KEYS = ["ctrl", "shift", "alt"]      # 3 phím bổ trợ, giao diện cho tick chọn


def parse_hold_keys(s):
    """'ctrl+shift' -> ['ctrl', 'shift'] (bỏ khoảng trắng, bỏ mục rỗng)."""
    return [k.strip().lower() for k in (s or "").split("+") if k.strip()]


# Tên phím của TRÌNH DUYỆT -> tên phím của pyautogui.
# Bảng này nằm ở core chứ không ở JS, cùng lý do với mọi thứ khác: JS không được
# biết định dạng dữ liệu, nó chỉ hỏi. Ở đây còn một lý do nữa — thứ chạy được hay
# không là do pyautogui quyết, mà pyautogui thì chỉ Python nhìn thấy.
PHIM_TRINH_DUYET = {
    " ": "space", "spacebar": "space", "escape": "escape", "esc": "escape",
    "enter": "enter", "return": "enter", "tab": "tab", "backspace": "backspace",
    "delete": "delete", "del": "delete", "insert": "insert",
    "home": "home", "end": "end", "pageup": "pageup", "pagedown": "pagedown",
    "arrowup": "up", "arrowdown": "down", "arrowleft": "left", "arrowright": "right",
    "control": "ctrl", "shift": "shift", "alt": "alt", "meta": "win", "os": "win",
    "capslock": "capslock", "numlock": "numlock", "scrolllock": "scrolllock",
    "printscreen": "printscreen", "pause": "pause", "contextmenu": "apps",
    "dead": "", "unidentified": "",
}


def key_from_browser(key, code=""):
    """(tên_phím_pyautogui, lý_do_lỗi). Đúng một trong hai vế có giá trị.

    Người dùng bấm phím thật, trình duyệt đưa `key` (ký tự/nhãn) và `code` (vị trí
    vật lý). Ưu tiên `key` vì nó đúng theo bố cục bàn phím đang dùng; chỉ dùng `code`
    khi `key` vô nghĩa (numpad, phím chết, IME).

    Bắt buộc chốt lại bằng `is_valid_key`: pyautogui nhận tên phím sai thì IM LẶNG
    không làm gì, nên thà báo ngay lúc ghi còn hơn để người dùng phát hiện lúc chạy
    thật với item thật."""
    key = str(key or "")
    code = str(code or "")

    # NUMPAD XÉT TRƯỚC: phím số trên numpad có `key` trùng hệt phím số hàng trên
    # ("1"), chỉ `code` mới phân biệt được — mà game thì gán được hai phím đó khác
    # nhau. Xét sau `key` là numpad vĩnh viễn ghi thành phím hàng trên.
    m = re.fullmatch(r"Numpad(\d)", code)
    ten = ("num" + m.group(1)) if m else PHIM_TRINH_DUYET.get(key.lower())

    if ten is None:
        if len(key) == 1:
            ten = key.lower()                  # chữ, số, dấu — lấy nguyên
        elif re.fullmatch(r"[fF]\d{1,2}", key):
            ten = key.lower()                  # F1..F24

    if not ten and code:
        # `key` vô nghĩa (phím chết, IME tiếng Việt) -> lần theo vị trí vật lý.
        if code == "NumpadEnter":
            ten = "enter"
        elif re.fullmatch(r"Key([A-Z])", code):
            ten = code[-1].lower()
        elif re.fullmatch(r"Digit(\d)", code):
            ten = code[-1]

    if not ten:
        return None, f'không nhận ra phím "{key or code}" — hãy gõ tên phím vào ô bên cạnh'
    if not is_valid_key(ten):
        return None, f'pyautogui không hiểu phím "{ten}" — hãy gõ tên phím vào ô bên cạnh'
    return ten, None


def is_valid_key(k):
    """pyautogui có hiểu tên phím này không?

    QUAN TRỌNG: pyautogui.keyDown() với tên phím sai KHÔNG ném lỗi — nó lặng lẽ
    không làm gì (đã đo). Nghĩa là gõ nhầm "shft" hay "windows" sẽ ra cú click
    THIẾU phím giữ mà chẳng có dấu hiệu gì. Nên phải tự kiểm và báo trước khi chạy.
    """
    try:
        return bool(pyautogui.isValidKey(k))
    except Exception:
        return True          # không kiểm được thì đừng chặn oan người dùng


def build_action(d):
    """Nhận dữ liệu thô từ MỘT form bất kỳ -> (action hợp lệ, None) hoặc (None, "lý do").

    Luật hợp lệ của 8 loại hành động nằm ở ĐÂY, không nằm trong form. Trước đây chúng
    nằm rải trong `ActionEditor._save` của bản tkinter; giao diện web mà chép lại thì
    hai bên chắc chắn trôi khỏi nhau — sửa luật một bên, bên kia vẫn cho lưu dữ liệu hỏng.

    `d` gần đúng hình dạng action rồi, cộng thêm vài cờ chỉ có ở form:
        point / keys / button / ms / key / min_ms / max_ms / conditions / excludes /
        frame / rerolls / wait_ms / grid / name
    Trả về dict SẠCH: không có khoá thừa, không có khoá rỗng.
    """
    t = d.get("type")
    if t not in ACTION_TYPES:
        return None, f'loại hành động không hợp lệ: "{t}"'

    def so(khoa, mac_dinh=None, bat_buoc=True, ten=None):
        v = d.get(khoa, mac_dinh)
        if v is None or v == "":
            if bat_buoc:
                raise ValueError(f"thiếu {ten or khoa}")
            return None
        return int(v)

    def diem(bat_buoc=True):
        p = d.get("point")
        if not p or len(p) != 2 or p[0] is None or p[1] is None or p[0] == "" or p[1] == "":
            if bat_buoc:
                raise ValueError("chưa có toạ độ X/Y")
            return None
        return [int(p[0]), int(p[1])]

    try:
        if t in ("check_mod", CONFIRM_MOD):
            # Hai loại này cấu hình y hệt nhau (điểm rê chuột + danh sách điều kiện),
            # chỉ khác nhau ở việc khớp rồi thì làm gì. Dùng chung luật để người dùng
            # chỉ phải học MỘT bộ soạn điều kiện.
            conds = [dict(c) for c in (d.get("conditions") or [])]
            if not conds:
                return None, "chưa thêm điều kiện mod nào"
            # point=None là HỢP LỆ ở đây: có thể chuột đã sẵn trên item rồi.
            a = {"type": t, "point": diem(bat_buoc=False), "conditions": conds}

        elif t == "abyss":
            if not d.get("frame"):
                return None, "chưa căn khung Abyss"
            conds = [dict(c) for c in (d.get("conditions") or [])]
            if not conds:
                return None, "chưa thêm điều kiện mod nào"
            # Số lần reroll CỐ ĐỊNH, không còn ô chỉnh trên giao diện: thử lại đúng
            # 1 lần rồi thôi. Nó chưa bao giờ là công tắc bật/tắt reroll — có bấm
            # refresh hay không là do refresh_button_present() dò trên ảnh quyết
            # định, nên để người dùng chỉnh con số này chỉ tổ gây hiểu nhầm.
            # Vẫn GHI vào file để bản ghi tự mô tả được và runner khỏi phải đoán.
            wm = so("wait_ms", ABYSS_DEFAULT_WAIT_MS, bat_buoc=False)
            wm = ABYSS_DEFAULT_WAIT_MS if wm is None else wm
            if wm < 0:
                return None, "thời gian chờ không hợp lệ"
            a = {"type": t, "frame": [int(v) for v in d["frame"]],
                 "conditions": conds, "rerolls": ABYSS_DEFAULT_REROLLS, "wait_ms": wm}
            if d.get("excludes"):        # rỗng thì không ghi, cho file gọn
                a["excludes"] = [dict(e) for e in d["excludes"]]

        elif t == "mod_click":
            keys = [k for k in MOD_KEYS if k in parse_hold_keys(d.get("keys"))]
            if not keys:
                return None, "chưa tick phím nào cần giữ"
            a = {"type": t, "point": diem(), "keys": "+".join(keys),
                 "button": "right" if d.get("button") == "right" else "left"}

        elif t in POINT_TYPES:
            g = d.get("grid") or None
            if t == "right_click" and g:
                if not g.get("frame"):
                    return None, 'bật "lấy từ nhiều ô" thì phải căn lưới trước'
                if not g.get("cells"):
                    return None, "chưa tick ô nào trong lưới"
                spc = g.get("per_cell")
                moi_o = INV_DEFAULT_PER_CELL if spc in (None, "") else int(spc)
                if not 1 <= moi_o <= INV_MAX_PER_CELL:
                    return None, (f"số lượng mỗi ô phải từ 1 đến {INV_MAX_PER_CELL}")
                a = {"type": t, "point": diem(bat_buoc=False) or [0, 0],
                     "grid": {"frame": [int(v) for v in g["frame"]],
                              "cells": [[int(c[0]), int(c[1])] for c in g["cells"]],
                              "per_cell": moi_o}}
            else:
                a = {"type": t, "point": diem()}

        elif t == "move_wasd":
            ks = wasd_sort(parse_hold_keys(d.get("keys")))
            if not ks:
                return None, "chưa tick hướng đi nào"
            ms = so("ms", MOVE_DEFAULT_MS)
            if ms <= 0:
                return None, "thời gian giữ phải lớn hơn 0 ms"
            a = {"type": t, "keys": "+".join(ks), "ms": ms}

        elif t == "key_press":
            k = str(d.get("key") or "").strip()
            if not k:
                return None, "chưa nhập phím"
            if not is_valid_key(k):
                return None, f'pyautogui không biết phím "{k}"'
            a = {"type": t, "key": k}

        elif t == "delay":
            lo, hi = so("min_ms", 0), so("max_ms", 0)
            if lo < 0 or hi < lo:
                return None, "min/max không hợp lệ"
            a = {"type": t, "min_ms": lo, "max_ms": hi}

        else:
            return None, f'chưa hỗ trợ loại "{t}"'

    except (ValueError, TypeError) as e:
        return None, str(e) if str(e).startswith(("thiếu", "chưa")) else f"giá trị không phải số ({e})"

    # Tên là TUỲ CHỌN: để trống thì dùng mô tả tự sinh. Ghi chuỗi rỗng vào file chỉ
    # tổ làm action_display phải đi đoán xem có nên dùng nó không.
    ten = str(d.get("name") or "").strip()
    if ten:
        a["name"] = ten
    if d.get("id"):
        a["id"] = d["id"]
    return a, None


def action_display(a):
    """Chuỗi hiện trong danh sách. Tên tự đặt (nếu có) đứng trước, KÈM THEO phần mô
    tả kỹ thuật tự sinh — không thay thế, để vẫn thấy toạ độ/thông số mà kiểm tra."""
    name = (a.get("name") or "").strip()
    summary = action_summary(a)
    return f"{name} — {summary}" if name else summary


def action_summary(a):
    # KHÔNG gắn emoji vào chuỗi này: nó là MÔ TẢ, không phải biểu tượng. Giao diện
    # nhận thêm `type` rồi tự vẽ icon nét cho khớp phần còn lại — emoji tô màu mang
    # màu riêng, không theo currentColor, và hình dáng phụ thuộc font từng máy.
    t = a["type"]
    if t == "check_mod":
        n = len(a.get("conditions") or [])
        pt = a.get("point")
        loc = f"@ ({pt[0]}, {pt[1]})" if pt else "(chưa chọn điểm)"
        return f"Kiểm tra mod {loc}  ·  {n} điều kiện — khớp thì DỪNG Loop"
    if t == CONFIRM_MOD:
        n = len(a.get("conditions") or [])
        pt = a.get("point")
        loc = f"@ ({pt[0]}, {pt[1]})" if pt else "(chưa chọn điểm)"
        return (f"Xác nhận mod {loc}  ·  {n} điều kiện — "
                f"khớp thì ĐI TIẾP, không khớp thì DỪNG nhánh")
    if t == "abyss":
        n = len(a.get("conditions") or [])
        fr = a.get("frame")
        loc = (f"khung @ ({fr[0]}, {fr[1]}) {fr[2]}×{fr[3]}" if fr else "(chưa căn khung)")
        # Không in số lần reroll nữa: nó cố định nên mọi khối đều giống hệt nhau,
        # hiện ra chỉ thêm chữ chứ không cho biết thêm điều gì.
        return (f"Abyss {loc}  ·  {n} điều kiện "
                f"— khớp thì chốt mod & DỪNG Loop")
    if t == "mod_click":
        keys = "+".join(parse_hold_keys(a.get("keys"))) or "(chưa chọn phím)"
        btn = "trái" if a.get("button", "left") == "left" else "phải"
        pt = a.get("point")
        loc = f"@ ({pt[0]}, {pt[1]})" if pt else "(chưa chọn điểm)"
        return f"Giữ [{keys}] + click {btn} {loc}"
    if t in POINT_TYPES:
        grid = a.get("grid")
        if grid:
            n = len(grid.get("cells") or [])
            moi_o = inv_moi_o(grid)
            return (f"{ACTION_LABELS[t]} — {n} ô × {moi_o} lượt = {n * moi_o} lần bấm, "
                    f"hết ô này tự sang ô sau")
        return f"{ACTION_LABELS[t]} @ ({a['point'][0]}, {a['point'][1]})"
    if t == "move_wasd":
        return f"Di chuyển {wasd_display(a.get('keys'))} trong {a.get('ms', MOVE_DEFAULT_MS)}ms"
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


class FatalActionError(Exception):
    """Lỗi mà CHẠY TIẾP LÀ VÔ NGHĨA -> dừng ngay, không đếm đủ 3 lần như read_fail.
    Vd: hết currency ở mọi ô đã tick — vòng sau có chạy cũng chẳng lấy được gì."""


def _point_of(a):
    """Lấy toạ độ của hành động, báo lỗi RÕ RÀNG nếu thiếu.

    Trước đây `x, y = a["point"]` gặp point thiếu/None sẽ ném KeyError/TypeError
    trần trụi từ trong ruột bộ máy chạy — người dùng chỉ thấy app đứng im."""
    pt = a.get("point")
    if not pt or len(pt) != 2:
        raise ValueError(f"hành động \"{ACTION_LABELS.get(a.get('type'), a.get('type'))}\" "
                         f"chưa có toạ độ điểm click")
    return int(pt[0]), int(pt[1])


def do_action(a, stop_flag, pre_click_ms=0, dem_luoi=None):
    t = a["type"]
    if t in POINT_TYPES:
        grid = a.get("grid")
        if grid:
            # Nâng cao: lấy từ nhiều ô. Số lượng mỗi ô do người dùng KHAI, ảnh chỉ
            # làm khoá chặn — xem `inv_chon_o` để biết vì sao chia vai như vậy.
            frame, cells = grid.get("frame"), (grid.get("cells") or [])
            if not frame or not cells:
                raise FatalActionError(
                    'bật "lấy từ nhiều ô" mà chưa căn lưới hoặc chưa tick ô nào.')
            moi_o = max(1, inv_moi_o(grid))
            if dem_luoi is None:
                dem_luoi = {}
            khoa = khoa_luoi(frame, cells)
            if khoa not in dem_luoi:
                # LẦN ĐẦU lưới này chạy trong phiên: soát cho đủ hàng TRƯỚC khi bấm
                # phát nào. Cố tình soát ở đây chứ không soát lúc bấm Chạy: lúc đó
                # game có thể chưa mở túi đồ, soát sẽ báo oan hàng loạt.
                trong = inv_o_trong(frame, cells)
                if trong:
                    raise FatalActionError(
                        f"ô số {', '.join(str(i) for i in trong)} trong lưới đang "
                        f"TRỐNG, mà bạn khai mỗi ô có {moi_o}. Thêm currency vào rồi "
                        f"chạy lại — dừng trước khi bấm phát nào.")
                dem_luoi[khoa] = {}
            dem = dem_luoi[khoa]
            hit = inv_chon_o(frame, cells, moi_o, dem)
            if hit is None:
                con_luot = sum(max(0, moi_o - dem.get((int(c[0]), int(c[1])), 0))
                               for c in cells)
                if con_luot:
                    raise FatalActionError(
                        f"còn {con_luot} lượt đã khai nhưng mọi ô đều nhìn ra TRỐNG "
                        f"— khai nhiều hơn thực tế. Thêm currency rồi chạy lại.")
                raise FatalActionError(
                    f"đã dùng hết {len(cells)} ô × {moi_o} = {len(cells) * moi_o} "
                    f"lượt đã khai. Thêm currency rồi chạy lại.")
            dem[hit] = dem.get(hit, 0) + 1
            x, y = inv_cell_point(frame, hit[0], hit[1])
        else:
            x, y = _point_of(a)
        pyautogui.moveTo(x, y)
        if pre_click_ms > 0:
            human_sleep(pre_click_ms, pre_click_ms, stop_flag)
        if stop_flag.is_set():
            return
        pyautogui.click(button="left" if t == "left_click" else "right")
    elif t == "mod_click":
        x, y = _point_of(a)
        keys = parse_hold_keys(a.get("keys"))
        bad = [k for k in keys if not is_valid_key(k)]
        if bad:
            # Không im lặng bỏ qua: click thiếu phím giữ trong game là hỏng cả
            # vòng chạy mà không ai biết vì sao.
            raise ValueError(f"phím giữ không hợp lệ: {', '.join(bad)} "
                             f"(dùng shift / ctrl / alt)")
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
    elif t == "move_wasd":
        # Kiểm tra trên phím THÔ, TRƯỚC khi sắp xếp: wasd_sort() lọc bỏ phím lạ,
        # kiểm tra sau nó thì "w+q" lặng lẽ thành "w" và chẳng ai biết.
        raw = parse_hold_keys(a.get("keys"))
        loi = wasd_problem(raw)
        if loi:
            raise ValueError(f"hướng di chuyển không hợp lệ: {loi}")
        keys = wasd_sort(raw)
        ms = max(0, int(a.get("ms", MOVE_DEFAULT_MS)))
        held = []
        try:
            for k in keys:
                pyautogui.keyDown(k)
                held.append(k)
            # human_sleep dò stop_flag mỗi 20ms -> giữ W 5 giây mà bấm F6 vẫn nhả
            # ra ngay, không phải chờ hết giờ.
            human_sleep(ms, ms, stop_flag)
        finally:
            # LUÔN thả, kể cả khi bị dừng giữa chừng — không thì nhân vật chạy mãi.
            for k in reversed(held):
                try:
                    pyautogui.keyUp(k)
                except Exception:
                    pass
    elif t == "key_press":
        pyautogui.press(a["key"])
    elif t == "delay":
        human_sleep(a["min_ms"], a["max_ms"], stop_flag)


# Kết quả của 1 lần "Kiểm tra mod". Phân biệt rõ 3 trạng thái — TRƯỚC ĐÂY cả 3 đều
# bị coi là "chưa ra mod" khiến app cứ thế đốt currency dù thực ra không đọc được gì.
CHECK_MATCH = "match"        # đọc được chữ item VÀ khớp điều kiện
CHECK_NO_MATCH = "no_match"  # đọc được chữ item nhưng chưa khớp -> chạy tiếp là đúng
CHECK_READ_FAIL = "read_fail"  # KHÔNG đọc được chữ item -> có gì đó sai, phải báo
# DỪNG NGAY với lý do rõ ràng, không đếm đủ 3 lần như read_fail. Dùng khi chạy tiếp
# là làm bậy — vd cả 3 ô Abyss đều nằm trong danh sách loại trừ: panel đang mở dở,
# vòng sau bấm "REVEAL" sẽ trúng nút CONFIRM và chốt đúng cái mod bị cấm.
CHECK_STOP = "stop"

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
        return CHECK_READ_FAIL, (f"hành động \"{ACTION_LABELS.get(a.get('type'), '?')}\" "
                                 f"chưa có điều kiện nào")

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


# ================= OCR: đọc chữ trực tiếp trên màn hình =================
# Dùng cho panel Abyss, nơi Ctrl+C không lấy được chữ.
_ocr_engine = None
_ocr_tried = False


def ocr_engine():
    """Bộ máy OCR của Windows (tạo 1 lần rồi dùng lại). None = không dùng được."""
    global _ocr_engine, _ocr_tried
    if _ocr_tried:
        return _ocr_engine
    _ocr_tried = True
    if not HAS_OCR:
        return None
    try:
        eng = OcrEngine.try_create_from_user_profile_languages()
        if eng is None:
            # Windows cài ngôn ngữ khác (vd tiếng Việt) thì gói OCR mặc định có thể
            # không phải tiếng Anh — chữ trong game là tiếng Anh nên ép sang en-US.
            from winrt.windows.globalization import Language
            eng = OcrEngine.try_create_from_language(Language("en-US"))
        _ocr_engine = eng
    except Exception:
        _ocr_engine = None
    return _ocr_engine


def ocr_unavailable_reason():
    """Vì sao không OCR được? None nghĩa là dùng được bình thường."""
    if not HAS_OCR:
        return ("thiếu thư viện OCR — cài:  "
                "pip install pillow winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging "
                "winrt-Windows.Storage.Streams")
    if ocr_engine() is None:
        return ("Windows chưa có gói OCR tiếng Anh — vào Settings ▸ Time & Language ▸ "
                "Language, thêm English (United States) kèm phần Optional features")
    return None


def ocr_text(image):
    """OCR 1 ảnh PIL, trả về chữ đọc được gộp thành 1 dòng ("" nếu không đọc được)."""
    eng = ocr_engine()
    if eng is None:
        return ""
    try:
        buf = io.BytesIO()
        image.save(buf, "PNG")
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(buf.getvalue())
        writer.store_async().get()
        writer.flush_async().get()
        writer.detach_stream()
        stream.seek(0)
        decoder = BitmapDecoder.create_async(stream).get()
        bitmap = decoder.get_software_bitmap_async().get()
        result = eng.recognize_async(bitmap).get()
        return " ".join(line.text for line in result.lines).strip()
    except Exception:
        return ""


def grab_screen(rect):
    """Chụp 1 vùng màn hình (x, y, w, h) -> ảnh PIL. None nếu không chụp được."""
    if not HAS_SCREEN:
        return None
    x, y, w, h = (int(v) for v in rect)
    if w <= 0 or h <= 0:
        return None
    try:
        return ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
    except Exception:
        return None


# ================= Lưới inventory (lấy currency từ nhiều ô) =================
# Một stack currency có hạn, cạn là phải sang ô khác. Người dùng tick sẵn những ô
# CHỨA ĐÚNG loại currency cần dùng; app chỉ việc nhìn xem ô nào CÒN HÀNG rồi
# phải-click ô đầu tiên còn hàng.
#
# Cố tình KHÔNG đếm số lần đã dùng: đếm thì phải nhớ trạng thái xuyên vòng lặp và
# xuyên cả lần chạy, mà chỉ cần khai lệch số lượng một cái là app phải-click ô rỗng
# hàng chục lần mà vẫn tưởng còn hàng. Nhìn thì không có gì để lệch — bỏ thêm
# currency giữa chừng hay dừng rồi chạy lại đều đúng.
#
# Inventory PoE2 luôn 12x5. Số đo lấy từ ảnh thật (stash_sample.png): lưới nằm
# trong x 11..621, y 12..265 -> 610x253, ô 50.83 x 50.60 px. Ô ra VUÔNG (tỉ lệ
# 1.004) — đó là phép thử cho thấy đọc đúng đường kẻ.
INV_COLS = 12
INV_ROWS = 5
INV_ASPECT = 610 / 253          # khung luôn giữ tỉ lệ này khi phóng to/thu nhỏ

# Chỉ đo phần LÕI giữa ô, bỏ 25% mỗi mép: vừa loại đường kẻ lưới và viền sáng của
# ô đang chọn, vừa chịu được căn khung lệch. Đo thực tế: lệch tới 10px (1/5 ô) mà
# ô trống vẫn 2.7-2.8 còn ô có đồ thấp nhất 19.4 — cách nhau 6.9 lần.
INV_INSET = 0.25

# Số lượng item mỗi ô do NGƯỜI DÙNG KHAI, không đọc bằng ảnh. Đã thử OCR con số
# stack mà game vẽ ở góc ô: chữ chỉ cao ~10px, nằm đè lên icon lổn nhổn, thử 8 kiểu
# tiền xử lý (phóng to, autocontrast, nhị phân, nhị phân đảo) đều chỉ đọc đúng 1-2
# trên 10 ô — "30" ra "3'oÉ". Không dựng được thì thà để người dùng khai.
INV_DEFAULT_PER_CELL = 20
INV_MAX_PER_CELL = 9999

# "Độ chi tiết" = độ lệch chuẩn của pixel trong lõi ô.
#   ô TRỐNG  : 2.7 - 3.8   (hoa văn nền lặp đều tăm tắp, 48/48 ô đo được đều vậy)
#   ô CÓ ĐỒ  : 19.4 - 80.9 (món tối nhất trong kho vẫn 19.4)
# Dùng độ chi tiết chứ KHÔNG dùng độ sáng: ô currency nền tối đọc sáng gần bằng ô
# trống, nhưng độ chi tiết thì món nào cũng lổn nhổn như nhau.
INV_ITEM_MIN_DETAIL = 10.0


def inv_cell_box(frame, row, col):
    """Ô (hàng, cột) -> (x, y, w, h) của TOÀN Ô."""
    fx, fy, fw, fh = (float(v) for v in frame)
    cw, ch = fw / INV_COLS, fh / INV_ROWS
    return (int(fx + col * cw), int(fy + row * ch), int(cw), int(ch))


def inv_cell_point(frame, row, col):
    """Tâm ô — chỗ để phải-click."""
    x, y, w, h = inv_cell_box(frame, row, col)
    return (x + w // 2, y + h // 2)


def inv_cell_patch(frame, row, col):
    """Vùng LÕI giữa ô để đo còn/hết."""
    x, y, w, h = inv_cell_box(frame, row, col)
    ix, iy = int(w * INV_INSET), int(h * INV_INSET)
    return (x + ix, y + iy, max(1, w - 2 * ix), max(1, h - 2 * iy))


def cell_detail(image):
    """Độ chi tiết của 1 ảnh ô. Càng cao càng chắc là có đồ."""
    if image is None:
        return 0.0
    try:
        return ImageStat.Stat(image.convert("L")).stddev[0]
    except Exception:
        return 0.0


def inv_scan(frame, cells):
    """Quét các ô đã tick. Trả về [(hàng, cột, còn_hàng, độ_chi_tiết), ...]
    theo ĐÚNG thứ tự người dùng đã tick."""
    out = []
    for rc in cells:
        try:
            r, c = int(rc[0]), int(rc[1])
        except (TypeError, ValueError, IndexError):
            continue
        d = cell_detail(grab_screen(inv_cell_patch(frame, r, c)))
        out.append((r, c, d >= INV_ITEM_MIN_DETAIL, d))
    return out


def inv_first_filled(frame, cells):
    """Ô ĐẦU TIÊN còn hàng theo thứ tự đã tick. Trả (hàng, cột) hoặc None."""
    for r, c, co_hang, _ in inv_scan(frame, cells):
        if co_hang:
            return (r, c)
    return None


def inv_o_trong(frame, cells):
    """Ô nào NHÌN RA TRỐNG. Trả [số thứ tự tick, ...] đếm từ 1."""
    return [i for i, (_, _, co_hang, _) in enumerate(inv_scan(frame, cells), 1)
            if not co_hang]


def inv_moi_o(grid):
    """Số item MỖI Ô đã khai.

    Thiếu khoá hoặc để trống -> lấy mặc định (file cũ mở lại vẫn chạy được).
    KHÔNG viết `grid.get("per_cell") or MẶC_ĐỊNH`: số 0 là giá trị sai mà `or` lại
    nuốt mất, hoá ra 0 âm thầm thành 20 và phần soát cấu hình hết đường báo lỗi.
    Giá trị bậy thì trả về 0 để bên soát còn nhìn thấy mà kêu.
    """
    spc = (grid or {}).get("per_cell")
    if spc is None or spc == "":
        return INV_DEFAULT_PER_CELL
    try:
        return int(spc)
    except (TypeError, ValueError):
        return 0


def khoa_luoi(frame, cells):
    """Khoá nhận diện một lưới. Hai hành động tick CÙNG bộ ô thì dùng CHUNG kho —
    đó mới đúng thực tế, vì chúng rút từ cùng những ô currency đó."""
    return (tuple(int(v) for v in frame),
            tuple((int(c[0]), int(c[1])) for c in cells))


def inv_chon_o(frame, cells, moi_o, dem):
    """Ô tiếp theo ĐƯỢC PHÉP bấm — hoặc None nếu không còn ô nào.

    HAI KHOÁ, phải cùng đồng ý mới bấm:
      · bộ đếm — ô này chưa dùng hết `moi_o` lượt đã khai;
      · ảnh    — ô này nhìn vẫn còn hàng.

    Ảnh chỉ có quyền PHỦ QUYẾT, không có quyền cho đi tiếp. Lý do: phép đo là độ
    lệch chuẩn, mà mọi thứ vẽ đè lên ô (tooltip của game, icon dính con trỏ, cửa sổ
    app) đều chỉ làm số đó TĂNG. Đo được: chỉ 4 pixel sáng lạc vào lõi ô là ô trống
    đã vọt từ 2.9 lên 15.1, quá ngưỡng 10. Nên "hết" là đáng tin còn "còn" thì không
    — vì vậy chỉ nghe nó khi nó nói HẾT.

    KHÔNG ghi nhớ ô đã bị ảnh phủ quyết: quét lại mỗi lần tuy tốn một lần chụp
    nhưng đổi lại bỏ thêm currency giữa chừng là dùng được ngay.
    """
    for rc in cells:
        try:
            r, c = int(rc[0]), int(rc[1])
        except (TypeError, ValueError, IndexError):
            continue
        if dem.get((r, c), 0) >= moi_o:
            continue                                  # khoá 1: hết lượt đã khai
        if cell_detail(grab_screen(inv_cell_patch(frame, r, c))) < INV_ITEM_MIN_DETAIL:
            continue                                  # khoá 2: ảnh phủ quyết
        return (r, c)
    return None


def inv_problems(grid, screen=None):
    """Soát cấu hình lưới của 1 hành động. Trả [{"severity", "message"}]."""
    out = []

    def add(sev, msg):
        out.append({"severity": sev, "message": msg})

    frame = (grid or {}).get("frame")
    if not frame or len(frame) != 4 or frame[2] <= 0 or frame[3] <= 0:
        add("error", "\"Lấy từ nhiều ô\" chưa căn lưới — bấm \"🖼 Căn lưới\".")
    else:
        fx, fy, fw, fh = frame
        if screen:
            sx, sy, sw, sh = screen
            if not (sx <= fx and sy <= fy and fx + fw <= sx + sw and fy + fh <= sy + sh):
                add("warning", f"\"Lấy từ nhiều ô\": lưới ({fx}, {fy}) {fw}×{fh} nằm ngoài "
                               f"màn hình hiện tại — có thể căn từ độ phân giải khác.")
        if fw / INV_COLS < 20:
            add("warning", f"\"Lấy từ nhiều ô\": lưới hơi nhỏ ({fw}×{fh}) — ô chỉ "
                           f"{fw / INV_COLS:.0f}px, dò còn/hết dễ sai. Căn lại cho trùm đúng.")
    cells = (grid or {}).get("cells") or []
    if not cells:
        add("error", "\"Lấy từ nhiều ô\" chưa tick ô nào.")
    else:
        moi_o = inv_moi_o(grid)
        if not 1 <= moi_o <= INV_MAX_PER_CELL:
            add("error", f"\"Lấy từ nhiều ô\": số lượng mỗi ô phải từ 1 đến "
                         f"{INV_MAX_PER_CELL}.")
        elif moi_o * len(cells) < 5:
            add("warning", f"\"Lấy từ nhiều ô\": tổng cộng chỉ {moi_o * len(cells)} "
                           f"lần bấm ({len(cells)} ô × {moi_o}) — chạy được một lúc "
                           f"là dừng. Khai đúng số item đang có trong mỗi ô.")
    if not HAS_SCREEN:
        add("error", "\"Lấy từ nhiều ô\" cần thư viện Pillow để chụp màn hình. "
                     "Cài:  pip install pillow")
    return out


# ================= Panel Abyss (Well of Souls) =================
# Panel hiện 3 mod để chọn 1, có thể có nút refresh (đổi 3 mod khác). Ctrl+C KHÔNG
# lấy được chữ ở đây, nên người dùng căn 1 khung duy nhất trùm lên panel rồi mọi
# vùng con suy ra theo TỈ LỆ dưới đây.
#
# Số đo lấy từ ảnh mẫu thật 517x308 (khung tính từ y=15 tới y=298, tức h=283) và đã
# đối chiếu với ảnh mẫu thứ hai: 3 rãnh phân cách chỉ lệch nhau 1px, nên tỉ lệ này
# ổn định giữa các lần mở panel.
ABYSS_ASPECT = 517 / 283            # khung luôn giữ tỉ lệ này khi phóng to/thu nhỏ
ABYSS_BANDS = ((0.0000, 0.2827),    # dải mod 1  (y đầu, y cuối) theo tỉ lệ chiều cao
               (0.2827, 0.5583),    # dải mod 2
               (0.5583, 0.8339))    # dải mod 3
ABYSS_CONFIRM = (0.4990, 0.9152)    # tâm nút REVEAL/CONFIRM (cùng một chỗ)
ABYSS_REFRESH = (0.9072, 0.8622, 0.9923, 0.9965)   # hộp nút refresh (x0,y0,x1,y1)

# Co vùng OCR vào trong một chút để không dính viền dải và chữ của dải bên cạnh khi
# khung căn hơi lệch. Inset dọc tính theo CHIỀU CAO CỦA DẢI, không phải của khung.
ABYSS_INSET_X = 0.015
ABYSS_INSET_Y = 0.15

# Nút refresh là ô vuông VÀNG ĐỒNG, sáng và ấm hơn hẳn nền đá tối xung quanh.
# Đo trên 2 ảnh mẫu thật:   có nút -> sáng 47.0, ấm(R-B) 17.8
#                           không  -> sáng  9.2, ấm(R-B)  1.5
# Ngưỡng đặt ở khoảng giữa nên rất khó nhầm.
ABYSS_REFRESH_MIN_LUM = 25.0
ABYSS_REFRESH_MIN_WARM = 8.0

ABYSS_DEFAULT_REROLLS = 1
ABYSS_DEFAULT_WAIT_MS = 500
ABYSS_MAX_REROLLS = 10


def abyss_regions(frame):
    """Từ khung đã căn (x, y, w, h) suy ra mọi vùng con của panel.

    Trả về dict:
        bands        [(x,y,w,h) x3]  — vùng CHỤP+OCR của từng dải mod
        band_points  [(x,y) x3]      — điểm click chọn từng mod
        confirm      (x,y)           — điểm click nút REVEAL/CONFIRM
        refresh      (x,y,w,h)       — hộp để DÒ xem có nút refresh không
        refresh_point(x,y)           — điểm click nút refresh
    """
    fx, fy, fw, fh = (int(v) for v in frame)
    bands, points = [], []
    ins_x = fw * ABYSS_INSET_X
    for (t0, t1) in ABYSS_BANDS:
        by0, by1 = fy + fh * t0, fy + fh * t1
        ins_y = (by1 - by0) * ABYSS_INSET_Y
        x0, y0 = int(fx + ins_x), int(by0 + ins_y)
        x1, y1 = int(fx + fw - ins_x), int(by1 - ins_y)
        bands.append((x0, y0, max(1, x1 - x0), max(1, y1 - y0)))
        points.append((int(fx + fw / 2), int((by0 + by1) / 2)))
    rx0, ry0, rx1, ry1 = ABYSS_REFRESH
    refresh = (int(fx + fw * rx0), int(fy + fh * ry0),
               max(1, int(fw * (rx1 - rx0))), max(1, int(fh * (ry1 - ry0))))
    return {
        "bands": bands,
        "band_points": points,
        "confirm": (int(fx + fw * ABYSS_CONFIRM[0]), int(fy + fh * ABYSS_CONFIRM[1])),
        "refresh": refresh,
        "refresh_point": (refresh[0] + refresh[2] // 2, refresh[1] + refresh[3] // 2),
    }


def refresh_button_present(image):
    """Ảnh ô góc phải dưới có phải NÚT REFRESH không? (sáng + ấm = có nút)"""
    if image is None:
        return False, 0.0, 0.0
    try:
        stat = ImageStat.Stat(image.convert("RGB"))
        r, g, b = stat.mean
    except Exception:
        return False, 0.0, 0.0
    lum = (r + g + b) / 3.0
    warm = r - b
    return (lum >= ABYSS_REFRESH_MIN_LUM and warm >= ABYSS_REFRESH_MIN_WARM), lum, warm


@functools.lru_cache(maxsize=512)
def template_regex(template):
    """Dựng regex từ dòng mod mẫu để lấy ĐÚNG các số nằm ở vị trí dấu '#'.

    KHÔNG quét mọi số trong câu: nhiều mod có số cố định nằm trong chính câu chữ
    (vd "# to # Added Attack Fire Damage per 25 Strength") — quét bừa sẽ lấy nhầm
    số 25 làm giá trị đã roll.
    """
    num = r"\s*[+\-]?\s*([0-9]+(?:[.,][0-9]+)?)\s*"
    parts = []
    for p in template.split("#"):
        # re.escape thoát cả khoảng trắng -> đổi lại thành \s* để chịu được việc OCR
        # đọc thừa/thiếu khoảng trắng.
        parts.append(re.sub(r"(?:\\\s)+", r"\\s*", re.escape(p)))
    return re.compile(num.join(parts), re.IGNORECASE)


def rolled_values(template, text):
    """Các con số ĐÃ ROLL trong chữ đọc được, theo đúng vị trí '#' của dòng mẫu."""
    if not template or not text:
        return []
    try:
        m = template_regex(template).search(text)
    except re.error:
        return []
    if not m:
        return []
    out = []
    for g in m.groups():
        try:
            out.append(float(str(g).replace(",", ".")))
        except (TypeError, ValueError):
            pass
    return out


def abyss_value(template, text):
    """Giá trị đại diện để so ngưỡng. Mod 2 số (vd "Adds # to # Chaos damage")
    lấy TRUNG BÌNH — đúng nghĩa sát thương trung bình. None = không đọc ra số."""
    vals = rolled_values(template, text)
    if not vals:
        return None
    return sum(vals) / len(vals)


def abyss_cond_match(text, cond):
    """1 dòng chữ OCR có khớp điều kiện Abyss không? Trả về (khớp?, giá_trị|None).

    Khớp mod = so KHỚP TUYỆT ĐỐI sau khi chuẩn hoá (giống check_mod), nên OCR đọc
    nhầm chữ số cũng không sao — norm() bỏ hết số đi rồi."""
    mod = cond.get("mod", "")
    if not mod or not text:
        return False, None
    if norm(text) != norm(mod):
        return False, None
    val = abyss_value(mod, text)
    mn = cond.get("min_value")
    if mn is None:
        return True, val
    if val is None:
        return False, val
    try:
        return val >= float(mn), val
    except (TypeError, ValueError):
        return True, val


def abyss_cond_display(c):
    mn = c.get("min_value")
    tail = f"≥ {mn}" if mn is not None else "mọi giá trị"
    return f"{c.get('mod', '')}   ·  {tail}"


def goal_display(c):
    """Mô tả điều kiện đã khớp, tự nhận ra là của check_mod hay của Abyss.
    Khoá "_kind" chỉ tồn tại lúc chạy (gắn vào bản sao), không bao giờ ghi ra file."""
    if c.get("_kind") == "abyss":
        return abyss_cond_display(c)
    return cond_display(c)


def abyss_scan(frame, log=None):
    """Chụp panel rồi OCR cả 3 dải + dò nút refresh.

    Trả về (texts, has_refresh, reason):
        texts       ['dòng 1', 'dòng 2', 'dòng 3']  ('' nếu dải đó không đọc được)
        has_refresh True/False
        reason      None nếu ổn, ngược lại là lý do KHÔNG đọc được (tiếng Việt)
    """
    regions = abyss_regions(frame)
    texts = []
    for rect in regions["bands"]:
        img = grab_screen(rect)
        if img is None:
            return [], False, "không chụp được màn hình"
        texts.append(ocr_text(img))

    has_refresh, lum, warm = refresh_button_present(grab_screen(regions["refresh"]))
    if log:
        for i, t in enumerate(texts, 1):
            log(f"      · ô {i}: {t or '(không đọc được)'}", "dim")
        log(f"      · nút refresh: {'CÓ' if has_refresh else 'không'} "
            f"(sáng {lum:.0f}, ấm {warm:.0f})", "dim")

    if not any(t.strip() for t in texts):
        return texts, has_refresh, ("không đọc được chữ nào trong khung — khung căn "
                                    "sai chỗ, hoặc panel chưa hiện")
    return texts, has_refresh, None


def abyss_is_excluded(text, excludes):
    """Dòng chữ này có nằm trong danh sách loại trừ không?

    Loại trừ chỉ so THEO MOD, không có ngưỡng số — "cấm mod này" chứ không phải
    "cấm khi dưới 20"."""
    if not text or not excludes:
        return False
    n = norm(text)
    return any(n == norm(e.get("mod", "")) for e in excludes if e.get("mod"))


def abyss_pick_allowed(texts, excludes):
    """Các ô ĐƯỢC PHÉP chọn khi phải chọn bừa, xếp theo thứ tự ưu tiên:

    1. đọc được chữ VÀ không bị cấm      <- an toàn, ưu tiên
    2. không đọc được nhưng không bị cấm <- đánh liều, chỉ dùng khi hết cách
    Ô bị cấm thì không bao giờ vào danh sách. Rỗng = không được chọn ô nào.
    """
    doc_duoc = [i for i, t in enumerate(texts) if t.strip()]
    khong_cam = [i for i, t in enumerate(texts) if not abyss_is_excluded(t, excludes)]
    an_toan = [i for i in doc_duoc if i in khong_cam]
    return an_toan or khong_cam


def abyss_find_match(texts, conds):
    """Tìm ô khớp điều kiện. Điều kiện xét theo thứ tự ưu tiên TRÊN->DƯỚI.
    Trả về (chỉ_số_ô, điều_kiện, giá_trị) hoặc (None, None, None)."""
    for c in conds:
        for i, t in enumerate(texts):
            ok, val = abyss_cond_match(t, c)
            if ok:
                return i, c, val
    return None, None, None


def abyss_action(a, stop_flag, pre_click_ms=0, log=None):
    """Chạy trọn 1 lượt Abyss:

        bấm REVEAL -> quét -> khớp thì chọn ô đó + CONFIRM rồi DỪNG
                   -> không khớp thì bấm refresh (nếu có nút) -> quét lại
                   -> vẫn không khớp thì chọn bừa 1 ô KHÔNG BỊ LOẠI TRỪ + CONFIRM
                   -> nếu cả 3 ô đều bị loại trừ và hết reroll -> DỪNG, báo rõ

    Trả về (status, payload) giống check_mod_action:
        (CHECK_MATCH, cond)      — đã ra mod mong muốn và đã chốt xong
        (CHECK_NO_MATCH, None)   — không ra mod, đã chọn bừa và confirm
        (CHECK_READ_FAIL, lý_do) — không đọc được panel
        (CHECK_STOP, lý_do)      — không có ô nào được phép chọn, phải dừng ngay
    """
    reason = ocr_unavailable_reason()
    if reason:
        return CHECK_READ_FAIL, reason
    frame = a.get("frame")
    if not frame:
        return CHECK_READ_FAIL, "hành động Abyss chưa căn khung"
    conds = a.get("conditions") or []
    if not conds:
        return CHECK_READ_FAIL, "hành động Abyss chưa có điều kiện nào"
    excludes = a.get("excludes") or []

    regions = abyss_regions(frame)
    # KHÔNG dùng `a.get(...) or MẶC_ĐỊNH`: số 0 là giá trị hợp lệ (không chờ) nhưng
    # lại falsy nên sẽ bị đá về 500ms một cách âm thầm.
    wait_ms = a.get("wait_ms")
    wait_ms = ABYSS_DEFAULT_WAIT_MS if wait_ms is None else max(0, int(wait_ms))
    rerolls = max(0, min(int(a.get("rerolls", ABYSS_DEFAULT_REROLLS)), ABYSS_MAX_REROLLS))

    def click(point):
        pyautogui.moveTo(point[0], point[1])
        if pre_click_ms > 0:
            human_sleep(pre_click_ms, pre_click_ms, stop_flag)
        pyautogui.click()

    def settle():
        human_sleep(wait_ms, wait_ms, stop_flag)

    def choose(index):
        """Click ô thứ `index` rồi bấm CONFIRM."""
        click(regions["band_points"][index])
        settle()
        if stop_flag.is_set():
            return
        click(regions["confirm"])
        settle()

    try:
        # 1. Bấm REVEAL (cùng vị trí với CONFIRM)
        click(regions["confirm"])
        settle()
        if stop_flag.is_set():
            return CHECK_NO_MATCH, None

        texts = [""] * len(ABYSS_BANDS)
        for attempt in range(rerolls + 1):
            texts, has_refresh, fail = abyss_scan(frame, log=log)
            if fail:
                return CHECK_READ_FAIL, fail

            idx, cond, val = abyss_find_match(texts, conds)
            if idx is not None:
                if log:
                    shown = f" (giá trị {val:g})" if val is not None else ""
                    log(f"      ↳ ô {idx + 1} khớp: {texts[idx]}{shown}", "ok")
                choose(idx)
                return CHECK_MATCH, dict(cond, _kind="abyss")

            if attempt >= rerolls:
                break
            if not has_refresh:
                if log:
                    log("   ⏭ không có nút refresh → bỏ qua reroll, chọn bừa", "skip")
                break
            if log:
                log(f"   ↻ chưa ra mod → bấm refresh (lần {attempt + 1}/{rerolls})", "skip")
            click(regions["refresh_point"])
            settle()
            if stop_flag.is_set():
                return CHECK_NO_MATCH, None

        # 2. Hết cách -> chọn bừa, nhưng KHÔNG được đụng ô bị loại trừ
        if stop_flag.is_set():
            return CHECK_NO_MATCH, None
        if log and excludes:
            for i, t in enumerate(texts):
                if abyss_is_excluded(t, excludes):
                    log(f"   ⛔ ô {i + 1} ({t}) nằm trong danh sách loại trừ → bỏ qua", "skip")
        allowed = abyss_pick_allowed(texts, excludes)
        if not allowed:
            return CHECK_STOP, ("cả 3 ô đều nằm trong danh sách loại trừ và đã hết lượt "
                                "reroll — dừng để không chốt phải mod bạn đã cấm. "
                                "Panel Abyss đang mở, hãy tự chọn rồi chạy lại.")
        pick = random.choice(allowed)
        if log:
            log(f"   ⏭ không ra mod mong muốn → chọn ô {pick + 1} rồi CONFIRM", "skip")
        choose(pick)
        return CHECK_NO_MATCH, None
    except pyautogui.FailSafeException:
        stop_flag.set()
        return CHECK_NO_MATCH, None
    except Exception as e:
        return CHECK_READ_FAIL, f"lỗi khi chạy Abyss ({type(e).__name__})"


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
        self.held = HeldKeys()
        # Lý do phải DỪNG NGAY (CHECK_STOP). Giữ riêng để thông báo cuối cùng nói
        # đúng chuyện gì xảy ra, thay vì rơi vào nhánh chung "Đã dừng".
        self.fatal = None
        # Hai kết cục BÌNH THƯỜNG của rẽ nhánh — không phải lỗi, nên phải nói khác
        # hẳn "⛔ DỪNG", nếu không người dùng tưởng app hỏng.
        self.dung_nhanh = None      # `confirm_mod` không khớp -> nhánh dừng giữa chừng
        self.het_nhanh = False      # ở điểm rẽ, không nhánh nào khớp
        # Đã bấm bao nhiêu lượt vào từng ô kho, {khoá lưới: {(hàng, cột): số lượt}}.
        # CHỈ sống trong một lần chạy — chạy lại là quên sạch và soát lại từ đầu, nên
        # không có chuyện bộ đếm cũ đá nhau với kho vừa được nạp thêm.
        self.dem_luoi = {}

    def release_held_keys(self):
        """Thả mọi phím đang giữ. Bên gọi nên gọi lại lần nữa cho chắc."""
        self.held.release_all()

    # -- kênh báo ra ngoài --
    def _status(self, msg):
        self._on_status(msg)

    def _log(self, msg, tag=None):
        self._on_log(msg, tag)

    # -- chạy 1 danh sách hành động --
    def run_sequence(self, actions, pre_click_ms, hover_ms, copy_keys, stop_on_hit=True):
        """Trả về (hit, read_fail_reason).
        hit = điều kiện đã khớp.
        read_fail_reason = KHÔNG đọc được chữ item (khác hẳn "đọc được nhưng chưa ra mod").

        stop_on_hit=True  (Loop): khớp là DỪNG NGAY, bỏ phần còn lại của vòng —
                          đúng, vì vòng đó đã đạt mục tiêu rồi.
        stop_on_hit=False (Nhóm HĐ 1 lần): vẫn chạy hết các hành động còn lại.
                          Nhóm không có vòng nào để kết thúc, nên cắt ngang giữa
                          chừng chỉ làm người dùng mất mấy thao tác mà không hiểu vì sao."""
        hit_payload = None
        for a in actions:
            if self.stop_flag.is_set():
                return hit_payload, None
            if a["type"] in BRANCH_TYPES:
                # Luật DUY NHẤT của `confirm_mod`, giống hệt nhau ở mọi chỗ nó đứng:
                # KHÔNG khớp -> nhánh đang chạy dừng tại đây.
                #   · khối HĐ lẻ ngay sau điểm rẽ -> nó là cổng, nhánh này bị loại
                #   · nằm giữa Nhóm            -> chốt chặn, bỏ nốt phần sau của nhóm
                #   · trên chuỗi thẳng          -> Process kết thúc
                status, payload = check_mod_action(a, self.stop_flag, hover_ms,
                                                   copy_keys, log=self._log)
                if status == CHECK_READ_FAIL:
                    return None, payload
                if status == CHECK_NO_MATCH:
                    self.dung_nhanh = "item không khớp điều kiện"
                    self._log("   ⏹ không khớp điều kiện → dừng nhánh này", "warn")
                    return hit_payload, None
                self._log(f"   ✔ khớp {goal_display(payload)} → đi tiếp", "ok")
            elif a["type"] in GOAL_TYPES:
                if a["type"] == "abyss":
                    status, payload = abyss_action(a, self.stop_flag, pre_click_ms,
                                                   log=self._log)
                else:
                    status, payload = check_mod_action(a, self.stop_flag, hover_ms,
                                                       copy_keys, log=self._log)
                if status == CHECK_MATCH:
                    if stop_on_hit:
                        return payload, None
                    hit_payload = hit_payload or payload
                if status == CHECK_STOP:
                    # Chạy tiếp là làm bậy -> chặn ngay, không đếm đủ 3 lần.
                    self.fatal = payload
                    self.stop_flag.set()
                    self._log(f"   ⛔ {payload}", "err")
                    return None, None
                if status == CHECK_READ_FAIL:
                    return None, payload
            else:
                try:
                    do_action(a, self.stop_flag, pre_click_ms, dem_luoi=self.dem_luoi)
                except pyautogui.FailSafeException:
                    self.stop_flag.set()
                    return None, None
                except FatalActionError as e:
                    # Chạy tiếp là vô nghĩa -> chặn ngay, không đếm 3 lần.
                    self.fatal = str(e)
                    self.stop_flag.set()
                    self._log(f"   ⛔ {e}", "err")
                    return None, None
                except Exception as e:
                    # MỘT hành động hỏng KHÔNG được phép giết cả vòng chạy. Trước
                    # đây chỉ bắt FailSafe -> lỗi khác lọt lên, thread chết âm thầm,
                    # giao diện kẹt ở trạng thái "đang chạy" và phím giữ không được
                    # thả. Giờ báo rõ rồi dừng gọn.
                    return None, (f"hành động #{actions.index(a) + 1} "
                                  f"({ACTION_LABELS.get(a.get('type'), a.get('type'))}) "
                                  f"lỗi: {type(e).__name__}: {e}")
        return hit_payload, None

    # -- chạy 1 bước Action_Loop --
    def run_loop_step(self, step, nhan, pre_click_ms, hover_ms, copy_keys):
        """Trả về (outcome, loops, detail). outcome:
            "achieved"  đã khớp điều kiện mục tiêu
            "done"      hết số vòng, loop KHÔNG có mục tiêu -> coi là xong
            "exhausted" có mục tiêu nhưng hết vòng chưa đạt -> DỪNG cả Process
            "read_fail" không đọc được chữ item nhiều lần liên tiếp
            "aborted"   người dùng dừng"""
        # Ô tick "Giữ Shift": bấm giữ ở ĐẦU bước, thả ở CUỐI bước — phạm vi đúng
        # bằng cái khung Loop trên giao diện. Không dính dấu "🔁 Loop từ đây" và
        # không ảnh hưởng bước sau. finally đảm bảo thả kể cả khi dừng/lỗi.
        hold = [k for k in parse_hold_keys(step.get("hold_keys")) if is_valid_key(k)]
        if hold and not self.stop_flag.is_set():
            self.held.hold(hold)
            self._log(f"   ⇧ giữ [{'+'.join(hold)}] suốt Loop này", "dim")
        try:
            return self._run_loop_inner(step, nhan, pre_click_ms,
                                        hover_ms, copy_keys)
        finally:
            if hold:
                self.held.release_all()
                self._log(f"   ⇧ đã thả [{'+'.join(hold)}]", "dim")

    def _run_loop_inner(self, step, nhan, pre_click_ms, hover_ms, copy_keys):
        actions = step.get("actions") or []
        n = len(actions)
        loop_start = max(0, min(int(step.get("loop_start_index") or 0), n))
        prologue, body = actions[:loop_start], actions[loop_start:]
        max_loops = int(step.get("max_loops") or DEFAULT_MAX_LOOPS)
        has_goal = any(a.get("type") in GOAL_TYPES for a in actions)
        name = step_title(step)

        hit = None
        loops = 0
        fail_streak = 0
        last_fail = None

        if prologue and not self.stop_flag.is_set():
            hit, fail = self.run_sequence(prologue, pre_click_ms, hover_ms, copy_keys)
            if fail:
                fail_streak, last_fail = 1, fail

        # `dung_nhanh` trong điều kiện lặp: một `confirm_mod` không khớp nghĩa là
        # nhánh chết, mà nhánh chết thì lặp thêm vòng nữa là vô nghĩa.
        while (hit is None and not self.stop_flag.is_set() and body
               and not self.dung_nhanh
               and loops < max_loops and fail_streak < MAX_READ_FAIL_STREAK):
            hit, fail = self.run_sequence(body, pre_click_ms, hover_ms, copy_keys)
            loops += 1               # tính cả vòng vừa khớp (đã thực sự chạy 1 lượt)
            if fail:
                fail_streak += 1
                last_fail = fail
                self._status(f"⚠ [{nhan}] {name}: không đọc được chữ item "
                             f"({fail_streak}/{MAX_READ_FAIL_STREAK}) — {fail}")
                self._log(f"   ⚠ vòng {loops}: không đọc được chữ item "
                          f"({fail_streak}/{MAX_READ_FAIL_STREAK}) — {fail}", "warn")
            else:
                fail_streak = 0      # đọc được -> reset chuỗi lỗi
                if hit is None and (loops % 5 == 0 or loops == max_loops):
                    self._status(f"[{nhan}] {name}: vòng {loops}/{max_loops} "
                                 f"(nhấn {self.hotkey_label} để dừng)")
                if hit is None and loops % 25 == 0:
                    self._log(f"   … {name}: đã {loops}/{max_loops} vòng, chưa ra mod", "dim")

        if self.dung_nhanh:
            return "branch_stop", loops, self.dung_nhanh
        if hit:
            return "achieved", loops, goal_display(hit)
        if fail_streak >= MAX_READ_FAIL_STREAK:
            return "read_fail", loops, last_fail
        if self.stop_flag.is_set():
            return "aborted", loops, None
        return ("done" if not has_goal else "exhausted"), loops, None

    # -- chạy cả Process --
    def run(self):
        """Chạy trọn Process. Trả về (status_text, total_loops).

        Bọc finally để DÙ DỪNG KIỂU GÌ (xong, bấm Dừng, F6, failsafe, lỗi bất
        ngờ) cũng thả hết phím đang giữ — không để Shift kẹt trong cả Windows."""
        try:
            return self._run_inner()
        finally:
            self.held.release_all()

    def _chon_ke_tiep(self, cur, theo_id, ke_tiep, nhan_buoc, hover_ms, copy_keys):
        """Khối chạy tiếp sau `cur`, hoặc None nếu hết đường.

        HÀM NÀY CÓ TÁC DỤNG PHỤ, cố ý: ở điểm rẽ, cổng nào được thử là CHẠY THẬT
        (rê chuột, Ctrl+C, so điều kiện). Cổng khớp thì coi như đã chạy xong rồi,
        nên trả về khối NẰM SAU nó chứ không trả về chính nó — nếu không nó sẽ bị
        đọc item hai lần cho cùng một quyết định.

        Thứ tự thử nhánh lấy nguyên từ `flow_map`, đúng cái thứ tự mà `flow_order`
        dùng để rải chữ A/B lên huy hiệu. Một nguồn, nên nhãn không thể nói dối.

        Không nhánh nào khớp -> `het_nhanh`, Process kết thúc bình thường. Đọc không
        được chữ item -> DỪNG HẲN: không đọc được thì không biết đi đâu, mà đoán bừa
        một nhánh là làm bậy với currency của người dùng.
        """
        da_qua = set()
        for _ in range(MAX_PROCESS_STEPS):
            # Trong MỘT lần quyết định "đi đâu tiếp", không bao giờ được đánh giá lại
            # một cổng đã đánh giá rồi: đó là vòng lặp, và mỗi lượt là một lần đọc item
            # thật trong game. Trần MAX_PROCESS_STEPS ở vòng ngoài là quá muộn.
            if cur in da_qua:
                self.het_nhanh = True
                return None
            da_qua.add(cur)
            nhanh = ke_tiep.get(cur) or []
            if not nhanh:
                return None
            if len(nhanh) == 1:
                return nhanh[0]

            self._log(f"⑂ [{nhan_buoc.get(cur, '?')}] rẽ {len(nhanh)} nhánh — "
                      f"thử lần lượt từ trên xuống")
            chon = None
            for uv in nhanh:
                b = theo_id[uv]
                nh = nhan_buoc.get(uv, "?")
                if not is_branch_gate(b):
                    self._log(f"   → [{nh}] \"{step_title(b)}\" — nhánh mặc định", "dim")
                    return uv               # chưa chạy; vòng ngoài sẽ chạy nó
                if self.stop_flag.is_set():
                    return None
                status, payload = check_mod_action(b, self.stop_flag, hover_ms,
                                                   copy_keys, log=self._log)
                if status == CHECK_READ_FAIL:
                    self.fatal = (f"không đọc được chữ item ở cổng [{nh}] "
                                  f"\"{step_title(b)}\" ({payload}) — không biết chọn "
                                  f"nhánh nào nên dừng, thay vì đoán bừa")
                    self.stop_flag.set()
                    return None
                if status == CHECK_MATCH:
                    self._log(f"   ✔ [{nh}] khớp {goal_display(payload)} → đi nhánh này", "ok")
                    chon = uv
                    break
                self._log(f"   ✘ [{nh}] \"{step_title(b)}\" không khớp → thử nhánh kế", "dim")
            if chon is None:
                self.het_nhanh = True
                return None
            cur = chon      # cổng đã chạy xong -> tính tiếp từ ngay sau nó
        return None

    def _chay_mot_buoc(self, step, nhan, pre_click_ms, hover_ms, copy_keys, achieved):
        """Chạy ĐÚNG một bước. Trả về (lý_do_dừng|None, số_vòng).

        None = chạy tiếp bước sau. Chuỗi = dừng cả Process với lý do đó.
        Tách khỏi `_run_inner` để vòng duyệt bên ngoài đi theo ĐƯỜNG NỐI được — vòng
        `for ... enumerate(steps)` cũ chỉ chạy tuột từ trên xuống theo thứ tự danh sách,
        nên sơ đồ vẽ một đằng mà app chạy một nẻo."""
        name = step_title(step)

        if not is_loop_step(step):
            # Nhóm HĐ 1 lần và hành động lẻ: chạy đúng 1 lượt, không lặp.
            if is_group_step(step):
                seq = step.get("actions") or []
                self._status(f"[{nhan}] {name} (nhóm 1 lần, {len(seq)} hành động)")
                self._log(f"▤ [{nhan}] {name} — nhóm HĐ 1 lần, "
                          f"{len(seq)} hành động")
            else:
                seq = [step]
                self._status(f"[{nhan}] {name} (hành động lẻ)")
                self._log(f"⚡ [{nhan}] {name} — hành động lẻ, chạy 1 lần")
            hit, fail = self.run_sequence(seq, pre_click_ms, hover_ms, copy_keys,
                                          stop_on_hit=False)
            if self.fatal:
                s = f"⛔ DỪNG ở bước {nhan} \"{name}\" — {self.fatal}"
                self._log(s, "err")
                return s, 0
            if fail:
                s = (f"⛔ DỪNG ở bước {nhan} \"{name}\" — không đọc được chữ item "
                     f"({fail}). Kiểm tra: game còn focus? Điểm rê chuột còn đúng?")
                self._log(s, "err")
                return s, 0
            if hit:
                # Bước 1 lượt không có vòng nào để kết thúc -> chỉ ghi nhận rồi đi tiếp.
                achieved.append((name, goal_display(hit)))
                self._log(f"   ✅ {name}: khớp {goal_display(hit)} "
                          f"(bước 1 lượt nên vẫn chạy tiếp)", "ok")
            return None, 0

        self._status(f"[{nhan}] {name}: bắt đầu...")
        self._log(f"🔁 [{nhan}] {name} — bắt đầu "
                  f"(tối đa {step.get('max_loops', DEFAULT_MAX_LOOPS)} vòng)")
        outcome, loops, detail = self.run_loop_step(
            step, nhan, pre_click_ms, hover_ms, copy_keys)

        if outcome == "achieved":
            achieved.append((name, detail))
            self._status(f"✅ [{nhan}] {name}: đạt mục tiêu sau {loops} vòng "
                         f"({detail})")
            self._log(f"✅ [{nhan}] {name}: ĐẠT MỤC TIÊU sau {loops} vòng — {detail}",
                      "ok")
            return None, loops
        if outcome == "done":
            self._status(f"✔ [{nhan}] {name}: xong {loops} vòng")
            self._log(f"✔ [{nhan}] {name}: xong {loops} vòng "
                      f"(loop này không đặt mục tiêu)", "ok")
            return None, loops
        if outcome == "branch_stop":
            # Không phải lỗi: nhánh này đơn giản là không dành cho item đang cầm.
            # `_run_inner` đọc `self.dung_nhanh` rồi kết thúc Process tử tế.
            return None, loops
        if outcome == "exhausted":
            s = (f"⛔ DỪNG cả Process — bước {nhan} \"{name}\" chạy hết {loops} vòng "
                 f"mà chưa đạt mục tiêu. Không chạy tiếp để khỏi phí currency cho "
                 f"các bước sau.")
            self._log(s, "err")
            return s, loops
        if outcome == "read_fail":
            s = (f"⛔ DỪNG ở bước {nhan} \"{name}\" — không đọc được chữ item "
                 f"{MAX_READ_FAIL_STREAK} lần liên tiếp ({detail}). Kiểm tra: cửa sổ game "
                 f"còn đang focus? Điểm rê chuột còn đúng vị trí item? "
                 f"Đã dừng để không phí currency.")
            self._log(s, "err")
            return s, loops
        if self.fatal:
            s = f"⛔ DỪNG ở bước {nhan} \"{name}\" — {self.fatal}"
            self._log(s, "err")
            return s, loops
        self._log(f"■ Đã dừng ở bước {nhan} \"{name}\" (người dùng dừng)", "warn")
        return "Đã dừng", loops

    def _run_inner(self):
        cfg = self.cfg
        for i in range(cfg.get("start_delay", 0), 0, -1):
            if self.stop_flag.is_set():
                break
            self._status(f"Bắt đầu sau {i}s... (chuyển sang cửa sổ game)")
            time.sleep(1)

        steps = cfg["steps"]
        # Bước thiếu `id` (cấu hình dựng tay, file rất cũ) sẽ bị phép duyệt đồ thị bỏ
        # qua và Process im lặng không chạy gì. Cấp id trước cho chắc.
        ensure_step_ids(steps)
        # ĐƯỜNG NỐI quyết định thứ tự chạy, không phải thứ tự trong danh sách.
        # Không có khoá `edges` (file cũ, hoặc giao diện tkinter) -> chuỗi thẳng
        # 1→2→3, đúng hành vi từ trước tới nay.
        edges = cfg.get("edges")
        if edges is None:
            edges = default_edges(steps)
        theo_id, ke_tiep = flow_map(steps, edges)
        cur = flow_entry(steps, edges)
        # NHÃN chứ không phải "bước i/n": có rẽ nhánh rồi thì tổng số bước sẽ chạy là
        # thứ không biết trước được (mỗi lần chạy đi một đường khác). Dùng đúng cái
        # nhãn đang hiện ở góc khối trên canvas thì nhật ký và sơ đồ nói cùng một thứ
        # tiếng: thấy "[4A.2]" trong log là biết ngay nhìn khối nào.
        luong = flow_order(steps, edges)
        nhan_buoc = luong["order"]
        total = len(nhan_buoc) or len(steps)
        co_vong = bool(luong.get("loop"))
        pre_click_ms = cfg.get("pre_click_ms", 0)
        hover_ms = cfg.get("hover_ms", 250)
        copy_keys = [k.strip() for k in (cfg.get("copy_keys") or "ctrl+c").split("+") if k.strip()]

        total_loops = 0
        achieved = []          # [(tên bước, mod đã ra)] để tóm tắt cuối cùng
        status = None
        si = 0

        self._log(f"▶ Bắt đầu Process \"{cfg.get('name', '')}\" — {total} bước", "ok")
        if co_vong:
            # Nói NGAY từ dòng đầu. Vòng lặp ở tầng Process chỉ dừng khi chạm trần
            # MAX_PROCESS_STEPS, mà nếu vòng đi qua điểm rẽ thì mỗi vòng là một lần rê
            # chuột + Ctrl+C — để người dùng phát hiện sau 50 phút là quá muộn.
            self._log(f"⚠ Đường nối có VÒNG LẶP — Process chỉ tự dừng sau "
                      f"{MAX_PROCESS_STEPS} bước. Nhấn {self.hotkey_label} để dừng sớm.",
                      "warn")

        while cur and cur in theo_id:
            if self.stop_flag.is_set():
                status = "Đã dừng"
                break
            nhan = nhan_buoc.get(cur) or str(si + 1)
            ly_do, loops = self._chay_mot_buoc(theo_id[cur], nhan, pre_click_ms,
                                               hover_ms, copy_keys, achieved)
            total_loops += loops
            if ly_do is not None:
                status = ly_do
                break
            if self.dung_nhanh:
                status = (f"⏹ Nhánh dừng ở bước {nhan} "
                          f"\"{step_title(theo_id[cur])}\" — {self.dung_nhanh}")
                self._log(status, "warn")
                break
            si += 1
            if co_vong and si % 200 == 0:
                self._log(f"⚠ đã chạy {si} bước và vẫn đang chạy — đường nối có vòng "
                          f"lặp, nhấn {self.hotkey_label} để dừng", "warn")
            if si >= MAX_PROCESS_STEPS:
                # Đồ thị cho phép nối ngược lên trên -> có thể tạo vòng lặp vô tận.
                # Chốt chặn này để một cái nối sai không làm app chạy mãi.
                status = (f"⛔ DỪNG — đã chạy {si} bước liên tiếp. Nhiều khả năng "
                          f"đường nối tạo thành vòng lặp không có lối ra.")
                self._log(status, "err")
                break
            cur = self._chon_ke_tiep(cur, theo_id, ke_tiep, nhan_buoc,
                                     hover_ms, copy_keys)

        if status is None and self.fatal:
            # Cổng không đọc được chữ item: `_chon_ke_tiep` chỉ trả None chứ không có
            # đường báo lý do ra ngoài, nên phải vớt ở đây — nếu không nó lặng lẽ rơi
            # vào nhánh "Hoàn thành ✅" trong khi thực ra đã bỏ dở.
            status = f"⛔ DỪNG — {self.fatal}"
            self._log(status, "err")
        elif status is None and self.het_nhanh:
            status = ("⏹ Kết thúc — tới điểm rẽ mà item không khớp nhánh nào. "
                      "Muốn luôn có lối đi thì thêm một nhánh không có cổng kiểm tra, "
                      "xếp dưới cùng.")
            self._log(status, "warn")
        elif status is None:
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
