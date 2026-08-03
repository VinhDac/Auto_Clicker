"""Nhóm HĐ 1 lần: dữ liệu, khung sửa dùng chung với Loop, chạy 1 lượt, template."""
import copy
import os
import sys
import tempfile
import threading
import tkinter as tk

import _boot  # noqa: F401  — đặt sys.path + thư mục làm việc
import core
import auto_clicker_gui as m

ok = fail = 0
fails = []


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  OK   {name}")
    else:
        fail += 1
        fails.append(name)
        print(f"  FAIL {name}\n         -> {detail}")


QUEUE = []


class FakeEditor(tk.Toplevel):
    def __init__(self, master, app, action=None):
        super().__init__(master)
        self.result = QUEUE.pop(0) if QUEUE else None
        self.withdraw()
        self.after(1, self.destroy)


m.ActionEditor = FakeEditor
m.messagebox.askyesno = lambda *a, **k: True
m.messagebox.showinfo = lambda *a, **k: None
m.messagebox.showwarning = lambda *a, **k: None
m.messagebox.showerror = lambda *a, **k: None


def add(app, x, y):
    QUEUE.append({"type": "left_click", "point": [x, y]})
    app.add_action()
    app.root.update()


def rows(app):
    return [app.listbox.get(i) for i in range(app.listbox.size())]


class FakeAutoGui:
    FailSafeException = RuntimeError

    def __init__(self):
        self.ev = []
        self.pos = (0, 0)

    def moveTo(self, x, y, duration=0):
        self.pos = (int(x), int(y))

    def click(self, button="left"):
        self.ev.append(("click", self.pos))

    def keyDown(self, k):
        self.ev.append(("down", k))

    def keyUp(self, k):
        self.ev.append(("up", k))

    def hotkey(self, *a):
        self.ev.append(("hotkey", "+".join(a)))

    def press(self, k):
        self.ev.append(("press", k))

    def isValidKey(self, k):
        return k in ("shift", "ctrl", "alt", "enter")


class FakeClip:
    text = ('Item Class: Boots\n--------\n'
            '{ Prefix Modifier "Stalwart" (Tier: 6) — Life }\n+44(40-59) to maximum Life\n')

    def copy(self, s):
        pass

    def paste(self):
        return self.text


print("=== 1. Mô hình dữ liệu ===")
g = core.make_group_step("Chuẩn bị")
check("kind = group", g["kind"] == "group", g)
check("KHÔNG có max_loops / loop_start_index / hold_keys",
      not ({"max_loops", "loop_start_index", "hold_keys"} & set(g)), list(g))
check("is_group_step nhận đúng", core.is_group_step(g) and not core.is_loop_step(g))
check("has_actions: Loop và Nhóm đều có, HĐ lẻ thì không",
      core.has_actions(g) and core.has_actions(core.make_loop_step())
      and not core.has_actions(core.make_action_step({"type": "left_click", "point": [1, 2]})))
g["actions"] = [{"type": "left_click", "point": [1, 2]}]
check("mô tả bước rõ là chạy 1 lần",
      "▤" in core.step_display(g) and "chạy 1 lần" in core.step_display(g),
      core.step_display(g))

print("\n=== 2. Soát cấu hình: không đòi số vòng, không đòi mục tiêu ===")
p = core.validate_group([{"type": "left_click", "point": [5, 5]}])
check("nhóm bình thường -> không lỗi, không cảnh báo thừa", p == [], p)
p = core.validate_group([])
check("nhóm rỗng -> CẢNH BÁO (không phải lỗi)",
      len(p) == 1 and p[0]["severity"] == "warning", p)
p = core.validate_process([{"kind": "group", "name": "N",
                            "actions": [{"type": "left_click", "point": [5, 5]}]}])
check("nhóm KHÔNG bị cảnh báo 'chưa có Kiểm tra mod'",
      not any("Kiểm tra mod" in x["message"] for x in p), p)
check("nhóm KHÔNG bị kiểm số vòng lặp",
      not any("vòng lặp" in x["message"] for x in p), p)
p = core.validate_process([{"kind": "group", "name": "N",
                            "actions": [{"type": "mod_click", "point": [1, 2], "keys": ""}]}])
check("hành động hỏng trong nhóm vẫn bị bắt",
      any(x["severity"] == "error" for x in p), p)

print("\n=== 3. Chạy: đúng 1 lượt, đúng thứ tự ===")


def run_steps(steps, scans=None):
    gui = FakeAutoGui()
    saved = (core.pyautogui, core.pyperclip, core.HAS_CLIP)
    core.pyautogui, core.pyperclip, core.HAS_CLIP = gui, FakeClip(), True
    logs = []
    try:
        r = core.ProcessRunner({"name": "T", "start_delay": 0, "pre_click_ms": 0,
                                "hover_ms": 0, "copy_keys": "ctrl+c", "steps": steps},
                               threading.Event(), on_log=lambda s, t=None: logs.append(s))
        status, loops = r.run()
    finally:
        core.pyautogui, core.pyperclip, core.HAS_CLIP = saved
    return gui, status, logs


grp = {"kind": "group", "name": "Chuẩn bị", "actions": [
    {"type": "left_click", "point": [1, 1]},
    {"type": "left_click", "point": [2, 2]},
    {"type": "left_click", "point": [3, 3]}]}
gui, status, logs = run_steps([grp])
check("chạy đủ 3 hành động", len([e for e in gui.ev if e[0] == "click"]) == 3, gui.ev)
check("đúng thứ tự trên xuống",
      [e[1] for e in gui.ev if e[0] == "click"] == [(1, 1), (2, 2), (3, 3)], gui.ev)
check("chỉ chạy 1 lượt (không lặp lại)", len(gui.ev) == 3, gui.ev)
check("nhật ký ghi rõ là nhóm 1 lần",
      any("nhóm HĐ 1 lần" in l for l in logs), logs)

gui, status, logs = run_steps([grp, dict(grp, name="Sau")])
check("2 nhóm nối tiếp chạy đủ 6 hành động",
      len([e for e in gui.ev if e[0] == "click"]) == 6, len(gui.ev))

print("\n=== 4. Kiểm tra mod trong nhóm: KHÔNG cắt ngang phần còn lại ===")
grp_check = {"kind": "group", "name": "N", "actions": [
    {"type": "left_click", "point": [1, 1]},
    {"type": "check_mod", "point": [9, 9],
     "conditions": [{"mod": "# to maximum Life", "tier": 6}]},      # KHỚP
    {"type": "left_click", "point": [2, 2]}]}
gui, status, logs = run_steps([grp_check])
check("hành động SAU khi khớp vẫn được chạy",
      (2, 2) in [e[1] for e in gui.ev if e[0] == "click"], gui.ev)
check("có ghi nhận đã khớp mod", any("khớp" in l for l in logs), logs)
check("nhưng KHÔNG dừng Process", "DỪNG" not in status, status)

print("\n=== 5. Đọc lỗi trong nhóm -> dừng cả Process ===")
gui = FakeAutoGui()
saved = (core.pyautogui, core.pyperclip, core.HAS_CLIP)


class EmptyClip:
    def copy(self, s):
        pass

    def paste(self):
        return ""


core.pyautogui, core.pyperclip, core.HAS_CLIP = gui, EmptyClip(), True
try:
    r = core.ProcessRunner({"name": "T", "start_delay": 0, "pre_click_ms": 0, "hover_ms": 0,
                            "copy_keys": "ctrl+c",
                            "steps": [grp_check, {"kind": "group", "name": "Sau",
                                                  "actions": [{"type": "left_click",
                                                               "point": [7, 7]}]}]},
                           threading.Event())
    status, loops = r.run()
finally:
    core.pyautogui, core.pyperclip, core.HAS_CLIP = saved
check("đọc lỗi -> dừng cả Process", "DỪNG" in status, status)
check("bước sau KHÔNG chạy", (7, 7) not in [e[1] for e in gui.ev if e[0] == "click"], gui.ev)

print("\n=== 6. Giao diện: khung dùng chung, 3 điều khiển bị khoá ===")
root = tk.Tk()
root.withdraw()
m.apply_theme(root)
app = m.AutoClickerApp(root)
root.update()

app.add_group_step()
root.update()
check("thêm được Nhóm", core.is_group_step(app.cur_step), app.cur_step)
check("Số vòng lặp bị khoá", str(app.loops_entry["state"]) == "disabled", app.loops_entry["state"])
check("⇧ Giữ Shift bị khoá", str(app.hold_chk["state"]) == "disabled", app.hold_chk["state"])
check("🔁 Loop từ đây bị khoá", str(app.loop_start_btn["state"]) == "disabled",
      app.loop_start_btn["state"])
check("tiêu đề khung đổi", app.pane_frame["text"] == "Sửa Nhóm HĐ 1 lần", app.pane_frame["text"])
check("nhãn tên đổi", app.name_lbl["text"] == "Tên nhóm:", app.name_lbl["text"])

for x in (11, 22, 33):
    add(app, x, x)
check("thêm hành động vào nhóm -> hiện đủ 3 dòng", len(rows(app)) == 3, rows(app))
check("dòng trong nhóm KHÔNG có dấu 🔁 và KHÔNG có '(1 lần)'",
      all("🔁" not in r and "(1 lần)" not in r for r in rows(app)), rows(app))

app.listbox.selection_clear(0, tk.END)
app.listbox.selection_set(1)
app.delete_action()
root.update()
check("xoá hành động trong nhóm được", len(rows(app)) == 2, rows(app))
app.listbox.selection_set(0)
app.copy_actions()
app.paste_actions()
root.update()
check("copy/dán hành động trong nhóm được", len(rows(app)) == 3, rows(app))
app.loop_name_var.set("Nhóm chuẩn bị")
root.update()
check("đổi tên nhóm ghi đúng vào bước", app.cur_step["name"] == "Nhóm chuẩn bị",
      app.cur_step)
check("đổi tên KHÔNG lỡ tạo max_loops/hold_keys cho nhóm",
      not ({"max_loops", "hold_keys"} & set(app.cur_step)), list(app.cur_step))

print("\n=== 7. Chuyển qua lại Loop <-> Nhóm ===")
app.select_step(0)
root.update()
check("về Loop: 3 điều khiển mở lại",
      all(str(w["state"]) == "normal"
          for w in (app.loops_entry, app.hold_chk, app.loop_start_btn)),
      [str(w["state"]) for w in (app.loops_entry, app.hold_chk, app.loop_start_btn)])
check("về Loop: tiêu đề khung đổi lại", app.pane_frame["text"] == "Sửa Action_Loop",
      app.pane_frame["text"])
app.select_step(1)
root.update()
check("sang Nhóm: lại bị khoá", str(app.loops_entry["state"]) == "disabled")

print("\n=== 8. Copy/dán BƯỚC nhóm bằng Ctrl+C/Ctrl+V ===")
root.deiconify()
root.update()
n = len(app.steps)
app.step_box.focus_set()
app.step_box.event_generate("<Control-c>")
root.update()
app.step_box.event_generate("<Control-v>")
root.update()
check("dán được bước Nhóm", len(app.steps) == n + 1, len(app.steps))
check("bước dán vẫn là Nhóm", core.is_group_step(app.steps[2]), app.steps[2])
check("bước dán mang đủ hành động",
      len(app.steps[2]["actions"]) == len(app.steps[1]["actions"]),
      [len(s.get("actions", [])) for s in app.steps])

print("\n=== 9. Template riêng cho Nhóm ===")
sandbox = tempfile.mkdtemp(prefix="nhom_")
core.app_dir = lambda: sandbox
grp_step = app.steps[1]
data = core.make_group_template(grp_step, "poe2")
check("template ghi đúng type", data["type"] == "group", data["type"])
back = core.normalize_group_template(data)
check("đọc lại đúng nhóm", back and back["kind"] == "group"
      and len(back["actions"]) == len(grp_step["actions"]), back)
check("đọc file Loop bằng hàm của Nhóm -> None (chặn chọn nhầm)",
      core.normalize_group_template(core.make_loop_template(core.make_loop_step(), "poe2"))
      is None)
check("đọc file Nhóm bằng hàm của Loop -> None (chặn chiều ngược lại)",
      core.normalize_loop_template(data) is None)
check("có thư mục template riêng cho Nhóm", "group" in core.TEMPLATE_KINDS,
      core.TEMPLATE_KINDS)
d = core.templates_dir("group")
check("tạo được thư mục templates/group", os.path.isdir(d), d)
core.write_json(os.path.join(d, "test.json"), data)
check("liệt kê thấy template Nhóm vừa lưu",
      any(n == "test" for n, _ in core.list_templates("group")),
      core.list_templates("group"))

print("\n=== 10. Lưu / mở cả Process có Nhóm ===")
path = os.path.join(sandbox, "p.json")
truoc = copy.deepcopy(app.steps)
m.write_json(path, app.template_data())
app._load_process_from(path)
root.update()
check("mở lại đủ số bước", len(app.steps) == len(truoc), (len(app.steps), len(truoc)))
check("Nhóm vẫn là Nhóm sau khi mở lại",
      [s.get("kind") for s in app.steps] == [s.get("kind") for s in truoc],
      [s.get("kind") for s in app.steps])
check("hành động trong Nhóm còn nguyên",
      [s.get("actions") for s in app.steps] == [s.get("actions") for s in truoc],
      [len(s.get("actions", [])) for s in app.steps])

root.update()
root.destroy()
print(f"\n{'=' * 58}")
print(f"KẾT QUẢ: {ok} đúng / {fail} sai")
for f in fails:
    print("   sai:", f)
sys.exit(1 if fail else 0)
