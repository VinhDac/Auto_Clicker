"""ĐỢT KIỂM TRA KỸ: mọi đường tạo/thêm hành động, mô phỏng đúng cách dùng thật.

Trọng tâm: setup DÀI, NHIỀU Loop, NHIỀU hành động — thêm/sửa/xoá/di chuyển/copy
giữa các Loop, rồi lưu ra và mở lại. Không được mất hay lạc hành động nào.
"""
import copy
import os
import sys
import tempfile
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


# ---- Giả lập hộp thoại hành động: trả về kết quả định sẵn, không cần bấm tay ----
QUEUE = []


class FakeEditor(tk.Toplevel):
    def __init__(self, master, app, action=None):
        super().__init__(master)
        self.result = QUEUE.pop(0) if QUEUE else None
        self.withdraw()
        # đóng ở vòng sự kiện kế tiếp, không đóng ngay: wait_window() cần cửa sổ
        # còn sống lúc nó được gọi
        self.after(1, self.destroy)


m.ActionEditor = FakeEditor

# Chặn mọi hộp thoại hệ thống: chúng chặn luồng và treo bài test.
# askyesno luôn "Có" = mô phỏng người dùng bấm xác nhận.
m.messagebox.askyesno = lambda *a, **k: True
m.messagebox.showinfo = lambda *a, **k: None
m.messagebox.showwarning = lambda *a, **k: None
m.messagebox.showerror = lambda *a, **k: None


def click_action(x, y, name=None):
    a = {"type": "left_click", "point": [x, y]}
    if name:
        a["name"] = name
    return a


def add(app, action):
    """Bấm nút '+ Thêm' với kết quả định sẵn."""
    QUEUE.append(action)
    app.add_action()
    app.root.update()


def rows(app):
    """Đúng những gì NGƯỜI DÙNG NHÌN THẤY trong danh sách hành động."""
    return [app.listbox.get(i) for i in range(app.listbox.size())]


def new_app():
    root = tk.Tk()
    root.withdraw()
    m.apply_theme(root)
    app = m.AutoClickerApp(root)
    root.update()
    return root, app


# =====================================================================
print("=== 1. Thêm hành động vào Loop 1 (loop rỗng ban đầu) ===")
root, app = new_app()
add(app, click_action(10, 11))
check("thêm vào loop rỗng -> dữ liệu có 1 hành động", len(app.steps[0]["actions"]) == 1,
      app.steps[0]["actions"])
check("thêm vào loop rỗng -> DANH SÁCH HIỆN 1 dòng", len(rows(app)) == 1, rows(app))
add(app, click_action(20, 21))
add(app, click_action(30, 31))
check("thêm tiếp -> hiện đủ 3 dòng", len(rows(app)) == 3, rows(app))
check("đúng thứ tự", "(10, 11)" in rows(app)[0] and "(30, 31)" in rows(app)[2], rows(app))

# =====================================================================
print("\n=== 2. TẠO LOOP 2 RỒI THÊM HÀNH ĐỘNG (lỗi người dùng báo) ===")
app.add_loop_step()
root.update()
check("đã có 2 bước", len(app.steps) == 2, len(app.steps))
check("đang đứng ở Loop 2", app.cur == 1, app.cur)
check("Loop 2 rỗng -> danh sách trống", rows(app) == [], rows(app))

add(app, click_action(99, 98))
check("Loop 2: dữ liệu có 1 hành động", len(app.steps[1]["actions"]) == 1,
      app.steps[1]["actions"])
check("Loop 2: DANH SÁCH HIỆN 1 dòng  <<< chỗ người dùng báo lỗi",
      len(rows(app)) == 1, rows(app))
check("Loop 2: hiện đúng toạ độ", rows(app) and "(99, 98)" in rows(app)[0], rows(app))
check("Loop 1 KHÔNG bị đụng vào", len(app.steps[0]["actions"]) == 3,
      app.steps[0]["actions"])

add(app, click_action(97, 96))
add(app, click_action(95, 94))
check("Loop 2: thêm tiếp đủ 3 dòng", len(rows(app)) == 3, rows(app))

# =====================================================================
print("\n=== 3. Nhảy qua lại giữa 2 Loop, không lạc hành động ===")
app.select_step(0)
root.update()
check("về Loop 1 thấy đúng 3 dòng của Loop 1", len(rows(app)) == 3 and "(10, 11)" in rows(app)[0],
      rows(app))
app.select_step(1)
root.update()
check("sang Loop 2 thấy đúng 3 dòng của Loop 2", len(rows(app)) == 3 and "(99, 98)" in rows(app)[0],
      rows(app))
for _ in range(5):
    app.select_step(0)
    app.select_step(1)
root.update()
check("nhảy qua lại 5 lượt, dữ liệu vẫn nguyên",
      len(app.steps[0]["actions"]) == 3 and len(app.steps[1]["actions"]) == 3,
      [len(s["actions"]) for s in app.steps])

# =====================================================================
print("\n=== 4. Loop thứ 3, 4, 5 ===")
for k in range(3):
    app.add_loop_step()
    root.update()
    add(app, click_action(500 + k, 600 + k))
    check(f"Loop {k + 3}: thêm xong hiện đúng 1 dòng", len(rows(app)) == 1, rows(app))
check("tổng 5 bước", len(app.steps) == 5, len(app.steps))
check("mỗi bước giữ đúng số hành động của mình",
      [len(s["actions"]) for s in app.steps] == [3, 3, 1, 1, 1],
      [len(s["actions"]) for s in app.steps])

# =====================================================================
print("\n=== 5. Sửa / xoá / di chuyển ở Loop 2 ===")
app.select_step(1)
root.update()
app.listbox.selection_clear(0, tk.END)
app.listbox.selection_set(1)
QUEUE.append(click_action(111, 222, "đã sửa"))
app.edit_action()
root.update()
check("sửa hành động giữa Loop 2", "(111, 222)" in rows(app)[1], rows(app))
check("sửa xong vẫn đủ 3 dòng", len(rows(app)) == 3, rows(app))

app.listbox.selection_clear(0, tk.END)
app.listbox.selection_set(0)
app.move(1)
root.update()
check("đẩy xuống: dòng 1 và 2 đổi chỗ", "(111, 222)" in rows(app)[0], rows(app))

app.listbox.selection_clear(0, tk.END)
app.listbox.selection_set(2)
app.delete_action()
root.update()
check("xoá còn 2 dòng", len(rows(app)) == 2, rows(app))
check("xoá đúng Loop 2, Loop 1 nguyên vẹn", len(app.steps[0]["actions"]) == 3,
      app.steps[0]["actions"])

# =====================================================================
print("\n=== 6. Copy ở Loop 1, dán sang Loop 2 ===")
app.select_step(0)
root.update()
app.listbox.selection_clear(0, tk.END)
app.listbox.selection_set(0)
app.listbox.selection_set(2)
app.copy_actions()
root.update()
app.select_step(1)
root.update()
before = len(rows(app))
app.listbox.selection_clear(0, tk.END)
app.listbox.selection_set(before - 1)
app.paste_actions()
root.update()
check("dán sang Loop 2 tăng đúng 2 dòng", len(rows(app)) == before + 2, rows(app))
check("dán ra bản SAO độc lập (sửa bên này không đổi bên kia)",
      app.steps[1]["actions"][-1] is not app.steps[0]["actions"][2],
      "cùng một object!")

# =====================================================================
print("\n=== 7. Hành động lẻ chen giữa các Loop ===")
app.select_step(0)
root.update()
QUEUE.append(click_action(7, 7, "lẻ"))
app.add_action_step()
root.update()
check("thêm được bước lẻ", any(not m.is_loop_step(s) for s in app.steps), None)
check("bước lẻ nằm ngay sau bước đang chọn", not m.is_loop_step(app.steps[1]),
      [s.get("kind") for s in app.steps])
check("đang chọn bước lẻ -> hiện khung hành động lẻ, không phải khung Loop",
      app.action_pane.winfo_manager() == "pack" and app.loop_pane.winfo_manager() != "pack",
      (app.action_pane.winfo_manager(), app.loop_pane.winfo_manager()))

# thêm hành động khi đang chọn bước LẺ thì không được làm hỏng gì
n_before = [len(s.get("actions", [])) for s in app.steps]
add(app, click_action(1, 1))
check("bấm Thêm khi đang ở bước lẻ -> không nhét bừa vào Loop nào",
      [len(s.get("actions", [])) for s in app.steps] == n_before,
      [len(s.get("actions", [])) for s in app.steps])

app.select_step(2)          # quay lại 1 Loop
root.update()
add(app, click_action(3, 3))
check("sau khi đụng bước lẻ, thêm vào Loop vẫn hiện đúng",
      len(rows(app)) == len(app.steps[2]["actions"]), (len(rows(app)), app.steps[2]))

# =====================================================================
print("\n=== 8. Ô tick Giữ Shift riêng cho từng Loop ===")
app.select_step(0)
root.update()
app.hold_shift_var.set(True)
app._sync_loop_fields()
root.update()
check("bật tick ở Loop 1", app.steps[0].get("hold_keys") == "shift", app.steps[0].get("hold_keys"))
check("dòng của Loop 1 có tiền tố ⇧", all("⇧" in r for r in rows(app)), rows(app))
app.select_step(2)
root.update()
check("Loop khác KHÔNG bị bật lây", not app.steps[2].get("hold_keys"),
      app.steps[2].get("hold_keys"))
check("ô tick hiện đúng trạng thái của Loop đang chọn", app.hold_shift_var.get() is False,
      app.hold_shift_var.get())
check("dòng của Loop này không có ⇧", all("⇧" not in r for r in rows(app)), rows(app))

# =====================================================================
print("\n=== 9. Đổi tên Loop / số vòng không làm mất hành động ===")
app.select_step(0)
root.update()
app.loop_name_var.set("Loop đổi tên")
app.loops_var.set("777")
root.update()
check("đổi tên + số vòng xong, hành động còn nguyên", len(rows(app)) == 3, rows(app))
check("ghi đúng vào bước", app.steps[0]["name"] == "Loop đổi tên"
      and app.steps[0]["max_loops"] == 777, app.steps[0])

# =====================================================================
print("\n=== 10. Setup DÀI: 40 hành động chia 4 Loop ===")
root.destroy()
root, app = new_app()
plan = []
for li in range(4):
    if li:
        app.add_loop_step()
        root.update()
    for ai in range(10):
        a = click_action(li * 100 + ai, li * 100 + ai, f"L{li}A{ai}")
        add(app, a)
    plan.append(len(rows(app)))
check("mỗi Loop hiện đủ 10 dòng ngay sau khi thêm", plan == [10, 10, 10, 10], plan)
check("dữ liệu: 4 Loop x 10 hành động",
      [len(s["actions"]) for s in app.steps] == [10] * 4,
      [len(s["actions"]) for s in app.steps])
bad = []
for i in range(4):
    app.select_step(i)
    root.update()
    r = rows(app)
    if len(r) != 10 or f"L{i}A0" not in r[0] or f"L{i}A9" not in r[9]:
        bad.append((i, r[:2]))
check("duyệt lại từng Loop: đúng 10 dòng, đúng nội dung của chính nó", not bad, bad)

# =====================================================================
print("\n=== 11. Lưu ra file rồi mở lại: không mất gì ===")
sandbox = tempfile.mkdtemp(prefix="them_hd_")
path = os.path.join(sandbox, "p.json")
app.select_step(1)
app.hold_shift_var.set(True)
app._sync_loop_fields()
root.update()
data = app.template_data()
m.write_json(path, data)
saved = copy.deepcopy([s["actions"] for s in app.steps])
app._load_process_from(path)
root.update()
check("mở lại đủ 4 bước", len(app.steps) == 4, len(app.steps))
check("mở lại đủ 40 hành động, đúng từng bước",
      [s["actions"] for s in app.steps] == saved,
      [len(s["actions"]) for s in app.steps])
check("mở lại giữ đúng tick Giữ Shift của Loop 2",
      app.steps[1].get("hold_keys") == "shift" and not app.steps[0].get("hold_keys"),
      [s.get("hold_keys") for s in app.steps])
app.select_step(3)
root.update()
check("mở lại xong, chọn Loop cuối vẫn hiện đủ 10 dòng", len(rows(app)) == 10, len(rows(app)))
add(app, click_action(1, 2))
check("mở lại xong vẫn thêm được hành động mới", len(rows(app)) == 11, len(rows(app)))

# =====================================================================
print("\n=== 12. Xoá bước / xoá hết bước ===")
app.select_step(1)
root.update()
app.delete_step()
root.update()
check("xoá 1 bước còn 3", len(app.steps) == 3, len(app.steps))
check("sau khi xoá bước, danh sách hành động khớp bước đang chọn",
      len(rows(app)) == len(app.cur_step.get("actions", [])),
      (len(rows(app)), len(app.cur_step.get("actions", []))))
for _ in range(12):        # có chặn số vòng: app tự tạo lại Loop nên xoá mãi không hết
    app.delete_step()
    root.update()
check("xoá hết -> tự tạo lại 1 Loop rỗng, không bao giờ về 0 bước",
      len(app.steps) == 1 and m.is_loop_step(app.steps[0]), app.steps)
check("sau khi xoá sạch, con trỏ bước vẫn hợp lệ", app.cur == 0, app.cur)
add(app, click_action(4, 5))
check("Loop tự tạo lại vẫn thêm được và HIỆN ra", len(rows(app)) == 1, rows(app))

root.update()
root.destroy()
print(f"\n{'=' * 60}")
print(f"KẾT QUẢ: {ok} đúng / {fail} sai")
if fails:
    print("Các mục sai:")
    for f in fails:
        print("   -", f)
sys.exit(1 if fail else 0)
