"""Test tầng giao diện của hành động Abyss: ActionEditor, lưu/mở template,
overlay căn khung, xem lại điểm."""
import json
import os
import sys
import tempfile
import tkinter as tk

import _boot  # noqa: F401  — đặt sys.path + thư mục làm việc
import core
import auto_clicker_gui as m

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  OK   {name}")
    else:
        fail += 1
        print(f"  FAIL {name}   {detail}")


FRAME = [300, 400, 517, 283]
COND = [{"mod": "#% to Cold Resistance", "min_value": 20},
        {"mod": "# to all Attributes"}]
ACTION = {"type": "abyss", "frame": list(FRAME), "conditions": [dict(c) for c in COND],
          "rerolls": 2, "wait_ms": 350, "name": "Abyss T1"}

sandbox = tempfile.mkdtemp(prefix="abyss_tpl_")

root = tk.Tk()
root.withdraw()
m.apply_theme(root)
app = m.AutoClickerApp(root)
root.update()
# Đổi app_dir SAU khi dựng app: đổi trước thì load_mods() không tìm ra file danh
# sách mod (nó tìm theo app_dir) và danh sách sẽ rỗng.
core.app_dir = lambda: sandbox        # template ghi vào sandbox, không đụng file thật

print("=== 1. ActionEditor mở được với loại Abyss ===")
ed = m.ActionEditor(root, app, ACTION)
root.update()
check("dựng được hộp thoại", ed.winfo_exists())
check("nạp đúng khung", ed.abyss_frame == FRAME, ed.abyss_frame)
check("nạp đúng số reroll", ed.rerolls_var.get() == "2", ed.rerolls_var.get())
check("nạp đúng thời gian chờ", ed.wait_var.get() == "350", ed.wait_var.get())
check("nạp đủ 2 điều kiện", len(ed.conditions) == 2, ed.conditions)
check("nhãn khung hiện toạ độ", "300" in ed.frame_label.cget("text"),
      ed.frame_label.cget("text"))
check("danh sách điều kiện hiện theo kiểu Abyss (ngưỡng, không Tier)",
      "≥ 20" in ed.cond_box.get(0) and "Tier" not in ed.cond_box.get(0), ed.cond_box.get(0))

print("\n=== 2. Lưu ra dữ liệu đúng ===")
ed._save()
root.update()
a = ed.result
check("lưu đúng loại", a["type"] == "abyss", a)
check("giữ nguyên khung", a["frame"] == FRAME, a)
check("giữ nguyên reroll + thời gian chờ", (a["rerolls"], a["wait_ms"]) == (2, 350), a)
check("KHÔNG còn khoá 'pick' (đã bỏ tuỳ chọn, luôn ngẫu nhiên)", "pick" not in a, a)
check("giữ nguyên điều kiện", a["conditions"] == COND, a["conditions"])
check("giữ tên tự đặt", a.get("name") == "Abyss T1", a)

print("\n=== 3. Chặn lưu khi thiếu khung / thiếu điều kiện ===")
real_err = m.messagebox.showerror
errors = []
m.messagebox.showerror = lambda *a, **k: errors.append(a)
ed2 = m.ActionEditor(root, app, dict(ACTION, frame=None))
ed2._save()
check("thiếu khung -> không lưu", ed2.result is None and errors, errors)
ed2.destroy()
errors.clear()
ed3 = m.ActionEditor(root, app, dict(ACTION, conditions=[]))
ed3._save()
check("thiếu điều kiện -> không lưu", ed3.result is None and errors, errors)
ed3.destroy()
m.messagebox.showerror = real_err
root.update()

print("\n=== 4. Thêm điều kiện qua giao diện ===")
ed4 = m.ActionEditor(root, app, dict(ACTION, conditions=[]))
root.update()
ed4.search_var.set("#% to cold resistance")
ed4._refresh_mods()
idx = next(i for i in range(ed4.master_box.size())
           if ed4.master_box.get(i) == "#% to Cold Resistance")
ed4.master_box.selection_set(idx)
ed4.minval_var.set("25")
ed4._add_condition()
check("thêm được điều kiện có ngưỡng",
      ed4.conditions == [{"mod": "#% to Cold Resistance", "min_value": 25}], ed4.conditions)
ed4.minval_var.set("")
ed4.master_box.selection_clear(0, tk.END)
ed4.master_box.selection_set(idx)
ed4._add_condition()
check("để trống ngưỡng -> không ghi khoá min_value",
      ed4.conditions[1] == {"mod": "#% to Cold Resistance"}, ed4.conditions[1])
ed4.minval_var.set("abc")
ed4.master_box.selection_clear(0, tk.END)
ed4.master_box.selection_set(idx)
errors = []
m.messagebox.showerror = lambda *a, **k: errors.append(a)
ed4._add_condition()
m.messagebox.showerror = real_err
check("ngưỡng không phải số -> báo lỗi, không thêm",
      len(ed4.conditions) == 2 and errors, (ed4.conditions, errors))
ed4.destroy()
root.update()

print("\n=== 5. Lưu / mở lại template giữ nguyên hành động Abyss ===")
app.steps = [m.make_loop_step("Loop Abyss")]
app.steps[0]["actions"] = [dict(ACTION)]
app.cur = 0
app.refresh()
data = app.template_data()
path = os.path.join(sandbox, "abyss.json")
m.write_json(path, data)
app.steps = [m.make_loop_step("trống")]
app.cur = 0
app._load_process_from(path)
root.update()
loaded = app.steps[0]["actions"][0]
check("mở lại đúng loại", loaded["type"] == "abyss", loaded)
check("mở lại đúng khung", loaded["frame"] == FRAME, loaded)
check("mở lại đúng điều kiện", loaded["conditions"] == COND, loaded)
check("mở lại đúng reroll", loaded["rerolls"] == 2, loaded)
check("JSON không lẫn khoá _kind nội bộ",
      "_kind" not in json.dumps(data), "có _kind trong file")

print("\n=== 6. Mô tả hiện trong danh sách ===")
txt = m.action_display(loaded)
check("có tên tự đặt", txt.startswith("Abyss T1 —"), txt)
check("nêu số điều kiện + số reroll", "2 điều kiện" in txt and "reroll 2" in txt, txt)
check("khung chưa căn thì nói rõ",
      "chưa căn khung" in m.action_display(dict(ACTION, frame=None, name="")),
      m.action_display(dict(ACTION, frame=None, name="")))

print("\n=== 7. Xem lại điểm: suy ra đủ 5 điểm từ khung ===")
pts = []
real_overlay = m.ReviewOverlay
m.ReviewOverlay = lambda r, p, cb: (pts.extend(p), cb())
app.review_points()
m.ReviewOverlay = real_overlay
root.update()
labels = [p[2] for p in pts]
check("có đủ 3 ô mod + CONFIRM + refresh", len(pts) == 5, labels)
check("nhãn rõ nghĩa", any("mod 1" in s for s in labels) and any("CONFIRM" in s for s in labels),
      labels)
reg = core.abyss_regions(FRAME)
check("toạ độ đúng theo khung",
      (pts[0][0], pts[0][1]) == reg["band_points"][0], (pts[0], reg["band_points"][0]))

print("\n=== 8. Overlay căn khung ===")
res = []
sel = m.AbyssFrameSelector(root, FRAME, res.append)
root.update()
check("nạp đúng khung ban đầu",
      (sel.fx, sel.fy, sel.fw, sel.fh) == tuple(FRAME), (sel.fx, sel.fy, sel.fw, sel.fh))
sel._nudge(3, -4)
check("mũi tên nhích đúng", (sel.fx, sel.fy) == (303, 396), (sel.fx, sel.fy))
before = sel.fw / sel.fh
sel._scale(1.5)
check("phóng to vẫn giữ tỉ lệ", abs(sel.fw / sel.fh - core.ABYSS_ASPECT) < 0.02,
      sel.fw / sel.fh)
sel._scale(0.001)
check("thu nhỏ bị chặn ở kích thước tối thiểu", sel.fw == sel.MIN_W, sel.fw)
# kéo góc dưới-phải: neo là góc trên-trái
sel.fx, sel.fy, sel.fw, sel.fh = 300, 400, 517, 283
sel.drag = ("corner", 300, 400, 1, 1)


class E:
    pass


e = E()
e.x, e.y = 300 - sel.vx + 800, 400 - sel.vy + 100
sel._motion(e)
check("kéo góc: neo trên-trái đứng yên", (sel.fx, sel.fy) == (300, 400), (sel.fx, sel.fy))
check("kéo góc: rộng theo chuột", sel.fw == 800, sel.fw)
check("kéo góc: cao suy ra từ tỉ lệ", abs(sel.fh - 800 / core.ABYSS_ASPECT) <= 1, sel.fh)
# kéo góc trên-trái: neo là góc dưới-phải -> khung nở lên/sang trái
sel.fx, sel.fy, sel.fw, sel.fh = 300, 400, 517, 283
sel.drag = ("corner", 300 + 517, 400 + 283, -1, -1)
e.x, e.y = 300 + 517 - sel.vx - 600, 0
sel._motion(e)
check("kéo góc trên-trái: mép phải đứng yên", sel.fx + sel.fw == 817, sel.fx + sel.fw)
check("kéo góc trên-trái: mép dưới đứng yên", sel.fy + sel.fh == 683, sel.fy + sel.fh)
sel._finish(True)
root.update()
check("Enter trả về khung", res and len(res[0]) == 4, res)

res2 = []
sel2 = m.AbyssFrameSelector(root, FRAME, res2.append)
sel2._finish(False)
root.update()
check("Esc trả về None", res2 == [None], res2)

root.update()
root.destroy()
print(f"\nKẾT QUẢ: {ok} đúng / {fail} sai")
sys.exit(1 if fail else 0)
