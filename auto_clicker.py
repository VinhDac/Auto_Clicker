"""
AUTO CLICKER - MVP
==================
Chạy 1 flow: click / delay ngẫu nhiên / loop theo số. Nhấn F6 để DỪNG bất cứ lúc nào.

CÁCH DÙNG:
  1) Lấy toạ độ:   python auto_clicker.py record
     -> di chuột tới điểm cần bấm, nhấn F8 để in toạ độ, Esc để thoát.
  2) Sửa danh sách FLOW bên dưới cho đúng toạ độ của bạn.
  3) Chạy:         python auto_clicker.py
     -> có 3 giây để chuyển sang cửa sổ đích, rồi nó tự chạy.

DỪNG KHẨN CẤP:
  - Nhấn F6, HOẶC
  - Hất chuột vào góc TRÊN-TRÁI màn hình (cơ chế fail-safe của pyautogui).
"""

import sys
import time
import random
import threading

try:
    import pyautogui
    import keyboard
except ImportError:
    print("Thiếu thư viện. Cài bằng lệnh:")
    print("    pip install pyautogui keyboard")
    sys.exit(1)

pyautogui.FAILSAFE = True   # đưa chuột vào góc trên-trái (0,0) -> dừng khẩn cấp
pyautogui.PAUSE = 0         # tự quản delay, không để pyautogui tự chèn

# =====================  CẤU HÌNH  =====================
# Mỗi phần tử là 1 "hành động". Sửa toạ độ (point) theo màn hình của bạn.
FLOW = [
    {"type": "right_click", "point": (820, 430)},
    {"type": "delay",       "min_ms": 200, "max_ms": 1000},   # nghỉ ngẫu nhiên 0.2-1s
    {"type": "left_click",  "point": (900, 550)},
    {"type": "delay",       "min_ms": 200, "max_ms": 1000},
]
MAX_LOOPS   = 1000          # dừng sau đủ số vòng này
START_DELAY = 3            # giây đếm ngược trước khi chạy
STOP_HOTKEY = "f6"          # phím dừng toàn cục
# =====================================================

stop_flag = threading.Event()


def human_sleep(min_ms, max_ms):
    """Nghỉ 1 khoảng ngẫu nhiên, vẫn kiểm tra cờ dừng liên tục để thoát ngay."""
    total = random.uniform(min_ms, max_ms) / 1000.0
    end = time.time() + total
    while time.time() < end:
        if stop_flag.is_set():
            return
        time.sleep(min(0.02, max(0.0, end - time.time())))


def do_action(act):
    t = act["type"]
    if t == "left_click":
        x, y = act["point"]; pyautogui.click(x, y, button="left")
    elif t == "right_click":
        x, y = act["point"]; pyautogui.click(x, y, button="right")
    elif t == "double_click":
        x, y = act["point"]; pyautogui.doubleClick(x, y)
    elif t == "move":
        x, y = act["point"]; pyautogui.moveTo(x, y, duration=0.1)
    elif t == "scroll":
        pyautogui.scroll(act.get("amount", -300))   # âm = cuộn xuống
    elif t == "key_press":
        pyautogui.press(act["key"])                 # vd: {"type":"key_press","key":"enter"}
    elif t == "delay":
        human_sleep(act["min_ms"], act["max_ms"])
    else:
        print("  [!] Bỏ qua hành động lạ:", t)


def run_flow():
    loops = 0
    while not stop_flag.is_set() and loops < MAX_LOOPS:
        for act in FLOW:
            if stop_flag.is_set():
                break
            try:
                do_action(act)
            except pyautogui.FailSafeException:
                print("\n[FAIL-SAFE] Chuột ở góc màn hình -> dừng.")
                stop_flag.set()
                break
        loops += 1
        if loops % 10 == 0:
            print(f"  ...đã chạy {loops}/{MAX_LOOPS} vòng")

    status = "BỊ DỪNG" if stop_flag.is_set() else "HOÀN THÀNH"
    print(f"\n=== {status} — tổng {loops} vòng ===")
    notify(loops, status)


def notify(loops, status):
    try:
        import winsound
        winsound.MessageBeep()
    except Exception:
        pass
    try:
        from plyer import notification
        notification.notify(title="Auto Clicker",
                            message=f"{status}: {loops} vòng",
                            timeout=5)
    except Exception:
        pass


def record_mode():
    print("=== CHẾ ĐỘ LẤY TOẠ ĐỘ ===")
    print("Di chuột tới vị trí cần bấm -> nhấn F8 để in toạ độ. Nhấn Esc để thoát.\n")
    keyboard.add_hotkey("f8", lambda: print("  point:", tuple(pyautogui.position())))
    keyboard.wait("esc")
    print("Đã thoát chế độ lấy toạ độ.")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "record":
        record_mode()
        return

    print("=========== AUTO CLICKER (MVP) ===========")
    print(f"  Dừng: nhấn [{STOP_HOTKEY.upper()}]  hoặc  hất chuột vào góc TRÊN-TRÁI.")
    print(f"  Số vòng tối đa: {MAX_LOOPS}")
    print(f"  Bắt đầu sau {START_DELAY}s — hãy chuyển sang cửa sổ đích ngay...\n")

    keyboard.add_hotkey(STOP_HOTKEY, stop_flag.set)

    for i in range(START_DELAY, 0, -1):
        print(f"  {i}...")
        time.sleep(1)
    print("  -> CHẠY!\n")

    run_flow()


if __name__ == "__main__":
    main()
