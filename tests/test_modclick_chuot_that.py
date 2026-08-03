"""Chạy THẬT app với flow mod_click y như của người dùng, chuột thật, và đo:
   - giao diện có đơ không (đo độ trễ nhịp after() của chính app)
   - có ngoại lệ nào lọt ra không
   - kết thúc có kẹt phím Shift/Ctrl/Alt trong hệ thống không
   - vòng chạy có kết thúc gọn và mở lại nút Chạy không

Click nhắm vào một cửa sổ bia của chính bài test, không đụng gì của người dùng.
Clipboard bị thay giả để không phá clipboard thật.
"""
import ctypes
import sys
import time
import tkinter as tk

import _boot  # noqa: F401  — đặt sys.path + thư mục làm việc
import core
import auto_clicker_gui as m

VK = {"shift": 0x10, "ctrl": 0x11, "alt": 0x12}
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  OK   {name}")
    else:
        fail += 1
        print(f"  FAIL {name}   {detail}")


def stuck_keys():
    return [k for k, v in VK.items()
            if ctypes.windll.user32.GetAsyncKeyState(v) & 0x8000]


class FakeClip:
    """Item KHÔNG chứa mod mục tiêu -> loop chạy hết số vòng, không dừng sớm."""
    text = ('Item Class: Boots\n--------\n'
            '{ Prefix Modifier "Stalwart" (Tier: 6) — Life }\n+44(40-59) to maximum Life\n')

    def copy(self, s):
        pass

    def paste(self):
        return self.text


def run_case(title, hold_shift, loops):
    print(f"\n=== {title} ===")
    root = tk.Tk()
    m.apply_theme(root)
    app = m.AutoClickerApp(root)
    root.geometry("+40+40")
    root.update()

    bia = tk.Toplevel(root)
    bia.title("bia click")
    bia.geometry("320x220+1000+300")
    bia.update()
    tx = bia.winfo_rootx() + 160
    ty = bia.winfo_rooty() + 110

    app.steps = [{
        "kind": "loop", "name": "Test", "loop_start_index": 1, "max_loops": loops,
        "hold_keys": "shift" if hold_shift else "",
        "actions": [
            {"type": "right_click", "point": [tx, ty]},
            {"type": "mod_click", "point": [tx, ty], "keys": "shift", "button": "left"},
            {"type": "delay", "min_ms": 20, "max_ms": 50},
            {"type": "check_mod", "point": [tx, ty],
             "conditions": [{"mod": "# to maximum Energy Shield", "tier": 1}]},
        ]}]
    app.cur = 0
    app.refresh_steps()
    app.select_step(0)

    saved_clip, saved_hasclip = core.pyperclip, core.HAS_CLIP
    core.pyperclip, core.HAS_CLIP = FakeClip(), True

    ticks = []
    stop_at = [None]
    btn_state = [None]

    # Bám thẳng vào _finish: đây là chỗ DUY NHẤT mở lại nút Chạy và gỡ hotkey.
    real_finish = app._finish

    def spy_finish(status, loops):
        real_finish(status, loops)
        root.after(60, lambda: (btn_state.__setitem__(0, str(app.run_btn["state"])),
                                stop_at.__setitem__(0, time.perf_counter()),
                                root.quit()))
    app._finish = spy_finish

    def tick():
        ticks.append(time.perf_counter())
        if time.perf_counter() > deadline:
            root.quit()
        else:
            root.after(20, tick)

    errors = []
    real_showerror = m.messagebox.showerror
    real_askyes = m.messagebox.askyesno
    m.messagebox.showerror = lambda *a, **k: errors.append(("error",) + a)
    m.messagebox.askyesno = lambda *a, **k: True          # bỏ qua hộp cảnh báo

    t0 = time.perf_counter()
    deadline = t0 + 45
    try:
        app.start_run()
        root.after(20, tick)
        root.mainloop()
    finally:
        m.messagebox.showerror, m.messagebox.askyesno = real_showerror, real_askyes
        app.stop_flag.set()
        core.pyperclip, core.HAS_CLIP = saved_clip, saved_hasclip

    gaps = sorted((ticks[i] - ticks[i - 1]) * 1000 for i in range(1, len(ticks)))
    log = app.log_text.get("1.0", "end")
    status = app.status.get()
    try:
        root.destroy()
    except Exception:
        pass

    print(f"   chạy xong sau {time.perf_counter() - t0:.1f}s")
    print(f"   nhịp giao diện (đặt 20ms): p95 {gaps[int(len(gaps) * .95)]:.0f}ms  "
          f"xấu nhất {gaps[-1]:.0f}ms")
    print(f"   trạng thái: {status[:90]}")
    check("hộp thoại lỗi không bật lên", not errors, errors)
    check("giao diện không đơ (không nhịp nào > 1.5s)", gaps[-1] < 1500, f"{gaps[-1]:.0f}ms")
    check("_finish() có chạy (vòng chạy kết thúc gọn)", stop_at[0] is not None, "hết giờ chờ")
    check("nút Chạy được mở lại", btn_state[0] == "normal", btn_state[0])
    check("không kẹt phím trong hệ thống", stuck_keys() == [], stuck_keys())
    check("nhật ký không có LỖI KHÔNG LƯỜNG TRƯỚC", "KHÔNG LƯỜNG TRƯỚC" not in log,
          [l for l in log.splitlines() if "LƯỜNG" in l])
    if hold_shift:
        check("nhật ký có ghi giữ Shift", "⇧ giữ" in log,
              [l for l in log.splitlines() if "⇧" in l])
        check("nhật ký có ghi ĐÃ THẢ Shift", "đã thả" in log,
              [l for l in log.splitlines() if "⇧" in l])
    return log


print("Trạng thái phím trước khi bắt đầu:", stuck_keys() or "sạch")

run_case("A. mod_click bấm-nhả từng lần (kiểu cũ), 25 vòng", False, 25)
time.sleep(0.5)
run_case("B. Tick Giữ Shift + mod_click, 25 vòng", True, 25)

print("\nTrạng thái phím sau tất cả:", stuck_keys() or "sạch")
check("kết thúc toàn bộ: hệ thống sạch phím", stuck_keys() == [], stuck_keys())

print(f"\nKẾT QUẢ: {ok} đúng / {fail} sai")
sys.exit(1 if fail else 0)
