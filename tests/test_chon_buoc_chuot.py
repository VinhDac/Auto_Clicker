"""Chọn bước bằng CHUỘT THẬT rồi thêm hành động — đúng cách người dùng làm.

Cửa sổ phải deiconify() thì widget mới nhận được sự kiện chuột/phím (bài test
withdraw() sẽ không tái hiện được lỗi nào cả).
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
root.deiconify()          # BẮT BUỘC: withdraw thì không nhận sự kiện chuột
root.update()


def click_step_row(i, jitter=0):
    """Bấm chuột THẬT vào dòng thứ i của danh sách bước."""
    bb = app.step_box.bbox(i)
    if not bb:
        return False
    x, y = bb[0] + 30, bb[1] + bb[3] // 2
    app.step_box.event_generate("<Button-1>", x=x, y=y)
    root.update()
    if jitter:
        app.step_box.event_generate("<B1-Motion>", x=x + jitter, y=y + jitter, state=0x100)
        root.update()
    app.step_box.event_generate("<ButtonRelease-1>", x=x, y=y)
    root.update()
    return True


print("=== Dựng 3 Loop, mỗi Loop vài hành động (bằng chuột) ===")
add(app, 1, 1)
add(app, 2, 2)
app.add_loop_step()
root.update()
add(app, 10, 10)
app.add_loop_step()
root.update()
add(app, 20, 20)
print(f"   số bước: {len(app.steps)}   số hành động mỗi bước: "
      f"{[len(s['actions']) for s in app.steps]}")

print("\n=== 1. Bấm chuột chọn Loop 2 rồi THÊM hành động ===")
click_step_row(1)
check("bấm chuột -> cur nhảy sang bước 2", app.cur == 1, app.cur)
check("dòng đang sáng trong danh sách bước là dòng 2",
      app.step_box.curselection() == (1,), app.step_box.curselection())
n_before = len(rows(app))
add(app, 111, 222)
check("Loop 2: sau khi thêm, DANH SÁCH HIỆN thêm 1 dòng",
      len(rows(app)) == n_before + 1, (n_before, rows(app)))
check("Loop 2: hành động vào ĐÚNG bước đang chọn",
      len(app.steps[1]["actions"]) == 2, [len(s["actions"]) for s in app.steps])
check("Loop 1 và Loop 3 không bị đụng",
      len(app.steps[0]["actions"]) == 2 and len(app.steps[2]["actions"]) == 1,
      [len(s["actions"]) for s in app.steps])

print("\n=== 2. Bấm qua lại các bước bằng chuột ===")
bad = []
for i in (0, 2, 1, 0, 2):
    click_step_row(i)
    if app.cur != i:
        bad.append((i, app.cur))
    if len(rows(app)) != len(app.steps[i]["actions"]):
        bad.append((i, "danh sách lệch", len(rows(app)), len(app.steps[i]["actions"])))
check("bấm 5 lượt: cur và danh sách luôn khớp bước được bấm", not bad, bad)

print("\n=== 3. Bấm CÓ RUNG TAY (lệch vài pixel) — kéo-thả vô tình ===")
order_before = [s["name"] for s in app.steps]
counts_before = [len(s["actions"]) for s in app.steps]
click_step_row(1, jitter=2)
root.update()
order_after = [s["name"] for s in app.steps]
check("rung tay 2px KHÔNG làm đảo thứ tự các bước",
      order_after == order_before, (order_before, order_after))
check("rung tay không làm mất hành động nào",
      [len(s["actions"]) for s in app.steps] == counts_before,
      (counts_before, [len(s["actions"]) for s in app.steps]))
check("sau khi rung tay, cur vẫn khớp dòng đang sáng",
      app.step_box.curselection() == (app.cur,),
      (app.step_box.curselection(), app.cur))
n_before = len(rows(app))
add(app, 333, 444)
check("rung tay xong vẫn thêm được và HIỆN ra",
      len(rows(app)) == n_before + 1, (n_before, len(rows(app))))
check("hành động vào đúng bước đang sáng",
      len(app.steps[app.cur]["actions"]) == len(rows(app)),
      (app.cur, [len(s["actions"]) for s in app.steps], len(rows(app))))

print("\n=== 4. Kéo-thả đổi thứ tự bước THẬT SỰ rồi thêm hành động ===")
bb0, bb2 = app.step_box.bbox(0), app.step_box.bbox(2)
if bb0 and bb2:
    x0, y0 = bb0[0] + 30, bb0[1] + bb0[3] // 2
    x2, y2 = bb2[0] + 30, bb2[1] + bb2[3] // 2
    names_before = [s["name"] for s in app.steps]
    counts = {s["name"]: len(s["actions"]) for s in app.steps}
    app.step_box.event_generate("<Button-1>", x=x0, y=y0)
    root.update()
    app.step_box.event_generate("<B1-Motion>", x=x2, y=y2, state=0x100)
    root.update()
    app.step_box.event_generate("<ButtonRelease-1>", x=x2, y=y2)
    root.update()
    names_after = [s["name"] for s in app.steps]
    check("kéo bước 1 xuống cuối -> thứ tự đổi thật",
          names_after != names_before and set(names_after) == set(names_before),
          (names_before, names_after))
    check("kéo xong không mất hành động nào",
          {s["name"]: len(s["actions"]) for s in app.steps} == counts,
          ({s["name"]: len(s["actions"]) for s in app.steps}, counts))
    check("kéo xong: dòng đang sáng khớp với cur",
          app.step_box.curselection() == (app.cur,),
          (app.step_box.curselection(), app.cur))
    check("kéo xong: danh sách hành động khớp bước đang chọn",
          len(rows(app)) == len(app.steps[app.cur]["actions"]),
          (len(rows(app)), app.cur, [len(s["actions"]) for s in app.steps]))
    n_before = len(rows(app))
    add(app, 555, 666)
    check("kéo xong vẫn thêm được và hiện ra", len(rows(app)) == n_before + 1,
          (n_before, len(rows(app))))
    check("kéo xong: hành động vào đúng bước đang sáng",
          len(app.steps[app.cur]["actions"]) == len(rows(app)),
          (app.cur, [len(s["actions"]) for s in app.steps]))

print("\n=== 5. Bấm vào vùng TRỐNG dưới danh sách bước ===")
h = app.step_box.winfo_height()
app.step_box.event_generate("<Button-1>", x=30, y=h - 5)
root.update()
app.step_box.event_generate("<ButtonRelease-1>", x=30, y=h - 5)
root.update()
check("bấm vùng trống không làm cur ra ngoài phạm vi",
      0 <= app.cur < len(app.steps), (app.cur, len(app.steps)))
check("bấm vùng trống: danh sách vẫn khớp bước đang chọn",
      len(rows(app)) == len(app.steps[app.cur]["actions"]),
      (len(rows(app)), app.cur))
n_before = len(rows(app))
add(app, 777, 888)
check("bấm vùng trống xong vẫn thêm được và hiện ra",
      len(rows(app)) == n_before + 1, (n_before, len(rows(app))))

print("\n=== 6. Tổng kiểm: mọi bước, danh sách phải khớp dữ liệu ===")
bad = []
for i in range(len(app.steps)):
    click_step_row(i)
    if len(rows(app)) != len(app.steps[i]["actions"]):
        bad.append((i, len(rows(app)), len(app.steps[i]["actions"])))
check("duyệt hết các bước bằng chuột: không bước nào lệch", not bad, bad)

root.update()
root.destroy()
print(f"\n{'=' * 58}")
print(f"KẾT QUẢ: {ok} đúng / {fail} sai")
for f in fails:
    print("   sai:", f)
sys.exit(1 if fail else 0)
