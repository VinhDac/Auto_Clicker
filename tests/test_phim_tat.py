"""Phím tắt trên 2 bảng: Ctrl+C / Ctrl+V / Delete / kéo-thả.

Bấm bằng PHÍM THẬT (event_generate) trên cửa sổ đang hiện — bài test withdraw()
sẽ không tái hiện được gì vì widget không nhận sự kiện.
"""
import sys
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


root = tk.Tk()
m.apply_theme(root)
app = m.AutoClickerApp(root)
root.geometry("980x780+30+30")
root.deiconify()
root.update()


def key(widget, seq):
    widget.focus_set()
    root.update()
    widget.event_generate(seq)
    root.update()


# Dựng sẵn: Loop 1 (3 hành động) + Loop 2 (1 hành động)
add(app, 1, 1)
add(app, 2, 2)
add(app, 3, 3)
app.add_loop_step()
root.update()
app.loop_name_var.set("Loop hai")
root.update()
add(app, 9, 9)

print("=== 1. Bảng HÀNH ĐỘNG: phím Delete ===")
app.select_step(0)
root.update()
app.listbox.selection_clear(0, tk.END)
app.listbox.selection_set(1)
key(app.listbox, "<Delete>")
check("Del xoá đúng 1 dòng", len(rows(app)) == 2, rows(app))
check("xoá đúng dòng đang chọn (còn lại 1,1 và 3,3)",
      "(1, 1)" in rows(app)[0] and "(3, 3)" in rows(app)[1], rows(app))
check("dữ liệu khớp", len(app.steps[0]["actions"]) == 2, app.steps[0]["actions"])

app.listbox.selection_clear(0, tk.END)
key(app.listbox, "<Delete>")
check("không chọn gì mà bấm Del -> không xoá bừa", len(rows(app)) == 2, rows(app))

app.listbox.selection_set(0)
app.listbox.selection_set(1)
key(app.listbox, "<Delete>")
check("chọn nhiều dòng -> Del xoá hết", len(rows(app)) == 0, rows(app))

print("\n=== 2. Bảng HÀNH ĐỘNG: Ctrl+C / Ctrl+V (đã có sẵn, kiểm lại) ===")
add(app, 5, 5)
app.listbox.selection_clear(0, tk.END)
app.listbox.selection_set(0)
key(app.listbox, "<Control-c>")
key(app.listbox, "<Control-v>")
check("copy rồi dán thành 2 dòng", len(rows(app)) == 2, rows(app))
check("bản dán là bản SAO độc lập",
      app.steps[0]["actions"][0] is not app.steps[0]["actions"][1], "cùng object")

print("\n=== 3. Bảng BƯỚC: Ctrl+C / Ctrl+V ===")
app.select_step(0)
root.update()
n_steps = len(app.steps)
key(app.step_box, "<Control-c>")
key(app.step_box, "<Control-v>")
check("dán thêm đúng 1 bước", len(app.steps) == n_steps + 1, len(app.steps))
check("bước dán nằm ngay sau bước gốc",
      app.steps[1]["name"] == app.steps[0]["name"], [s["name"] for s in app.steps])
check("bước dán mang đủ hành động của bản gốc",
      len(app.steps[1]["actions"]) == len(app.steps[0]["actions"]) == 2,
      [len(s.get("actions", [])) for s in app.steps])
check("bản SAO độc lập: sửa bản dán không đụng bản gốc",
      app.steps[1]["actions"] is not app.steps[0]["actions"], "chung list")
check("sau khi dán, con trỏ nhảy tới bước vừa dán", app.cur == 1, app.cur)
check("danh sách hành động hiện đúng bước vừa dán",
      len(rows(app)) == len(app.steps[1]["actions"]), (len(rows(app)), app.cur))

app.steps[1]["actions"][0]["point"] = [777, 777]
check("sửa bản dán KHÔNG làm đổi bản gốc",
      app.steps[0]["actions"][0]["point"] != [777, 777], app.steps[0]["actions"][0])

print("\n=== 4. Bảng BƯỚC: copy Loop có tick Giữ Shift ===")
app.select_step(0)
root.update()
app.hold_shift_var.set(True)
app._sync_loop_fields()
root.update()
key(app.step_box, "<Control-c>")
key(app.step_box, "<Control-v>")
check("bước dán giữ nguyên tick Giữ Shift",
      app.steps[1].get("hold_keys") == "shift", app.steps[1].get("hold_keys"))

print("\n=== 5. Bảng BƯỚC: phím Delete ===")
n_steps = len(app.steps)
app.select_step(1)
root.update()
ten_bi_xoa = app.steps[1]["name"]
key(app.step_box, "<Delete>")
check("Del xoá đúng 1 bước", len(app.steps) == n_steps - 1, len(app.steps))
check("con trỏ bước vẫn hợp lệ sau khi xoá",
      0 <= app.cur < len(app.steps), (app.cur, len(app.steps)))
check("danh sách hành động khớp bước đang chọn",
      len(rows(app)) == len(app.steps[app.cur].get("actions", [])),
      (len(rows(app)), app.cur))

print("\n=== 6. Dán rác từ clipboard thì phải lờ đi, không được vỡ ===")
for rac in ("chữ item PoE ngẫu nhiên", "{}", '{"khac": [1,2,3]}',
            '{"auto_clicker_steps": [{"kind": "loop", "max_loops": "hỏng"}]}',
            '{"auto_clicker_steps": ["không phải dict"]}',
            '{"auto_clicker_steps": [{"type": "scroll", "amount": 1}]}'):
    root.clipboard_clear()
    root.clipboard_append(rac)
    root.update()
    truoc = len(app.steps)
    try:
        key(app.step_box, "<Control-v>")
        lech = len(app.steps) - truoc
        check(f"dán rác {rac[:34]!r} -> không thêm bước hỏng",
              lech == 0 or all(m.is_loop_step(s) or s.get("type") in core.ACTION_TYPES
                               for s in app.steps),
              f"số bước đổi {lech}")
    except Exception as e:
        check(f"dán rác {rac[:34]!r} -> không văng lỗi", False, repr(e))

print("\n=== 7. Kéo-thả bảng BƯỚC vẫn chạy (đã có sẵn) ===")
while len(app.steps) < 3:
    app.add_loop_step()
    root.update()
bb0, bb2 = app.step_box.bbox(0), app.step_box.bbox(2)
names_before = [s["name"] for s in app.steps]
app.step_box.event_generate("<Button-1>", x=bb0[0] + 20, y=bb0[1] + bb0[3] // 2)
root.update()
app.step_box.event_generate("<B1-Motion>", x=bb2[0] + 20, y=bb2[1] + bb2[3] // 2, state=0x100)
root.update()
app.step_box.event_generate("<ButtonRelease-1>", x=bb2[0] + 20, y=bb2[1] + bb2[3] // 2)
root.update()
check("kéo-thả đổi được thứ tự bước",
      [s["name"] for s in app.steps] != names_before, [s["name"] for s in app.steps])
check("kéo xong con trỏ vẫn khớp dòng sáng",
      app.step_box.curselection() == (app.cur,), (app.step_box.curselection(), app.cur))

print("\n=== 8. Kéo-thả bảng HÀNH ĐỘNG vẫn chạy ===")
app.select_step(app.cur)
root.update()
while len(rows(app)) < 3:
    add(app, len(rows(app)) + 60, 60)
r_before = rows(app)
bb0, bb2 = app.listbox.bbox(0), app.listbox.bbox(2)
app.listbox.event_generate("<Button-1>", x=bb0[0] + 20, y=bb0[1] + bb0[3] // 2)
root.update()
app.listbox.event_generate("<B1-Motion>", x=bb2[0] + 20, y=bb2[1] + bb2[3] // 2, state=0x100)
root.update()
app.listbox.event_generate("<ButtonRelease-1>", x=bb2[0] + 20, y=bb2[1] + bb2[3] // 2)
root.update()
check("kéo-thả đổi được thứ tự hành động", rows(app) != r_before,
      (r_before, rows(app)))
check("kéo-thả không làm mất hành động nào", len(rows(app)) == len(r_before),
      (len(r_before), len(rows(app))))

root.update()
root.destroy()
print(f"\n{'=' * 58}")
print(f"KẾT QUẢ: {ok} đúng / {fail} sai")
for f in fails:
    print("   sai:", f)
sys.exit(1 if fail else 0)
