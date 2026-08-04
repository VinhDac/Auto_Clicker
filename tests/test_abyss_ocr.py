"""Test abyss_scan / abyss_find_match trên 2 ảnh mẫu thật.

Giả lập màn hình = chính ảnh mẫu: grab_screen(rect) cắt từ file thay vì chụp.
Khung đặt đúng chỗ đã đo: x=0, y=15, w=517, h=283.
"""
import sys

from PIL import Image

import _boot  # noqa: F401  — đặt sys.path + thư mục làm việc
import core

FRAME = (0, 15, 517, 283)
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  OK   {name}")
    else:
        fail += 1
        print(f"  FAIL {name}  {detail}")


def use_image(path):
    """Cho grab_screen đọc từ ảnh này (toạ độ màn hình == toạ độ ảnh)."""
    img = Image.open(path).convert("RGB")

    def fake_grab(rect):
        x, y, w, h = (int(v) for v in rect)
        return img.crop((x, y, x + w, y + h))

    core.grab_screen = fake_grab
    return img


print("=== abyss_sample.png (CÓ nút refresh) ===")
use_image("tests/anh/abyss_sample.png")
texts, has_refresh, reason = core.abyss_scan(FRAME)
for i, t in enumerate(texts, 1):
    print(f"    ô {i}: {t!r}")
print(f"    nút refresh: {has_refresh}   lý do lỗi: {reason}")
check("đọc được cả 3 ô", all(t.strip() for t in texts))
check("không báo lỗi đọc", reason is None, str(reason))
check("thấy nút refresh", has_refresh is True)
check("ô 1 đúng chữ", "REMNANTS CAN BE COLLECTED FROM 29% FURTHER AWAY" in texts[0])
check("ô 2 đúng chữ", "+6 TO ALL ATTRIBUTES" in texts[1])
check("ô 3 đúng chữ", "+13% TO FIRE AND CHAOS RESISTANCES" in texts[2])

conds = [{"mod": "#% to Fire and Chaos Resistances", "min_value": None}]
idx, c, val = core.abyss_find_match(texts, conds)
check("khớp mod ở ô 3", idx == 2, f"idx={idx}")
check("đọc đúng giá trị 13", val == 13.0, f"val={val}")

idx, c, val = core.abyss_find_match(
    texts, [{"mod": "#% to Fire and Chaos Resistances", "min_value": 20}])
check("ngưỡng 20 loại được mod 13%", idx is None, f"idx={idx}")

idx, c, val = core.abyss_find_match(texts, [{"mod": "# to all Attributes"}])
check("mod không có ngưỡng vẫn khớp (ô 2)", idx == 1, f"idx={idx}")

# ưu tiên: điều kiện đứng TRƯỚC thắng, dù nằm ở ô sau
idx, c, val = core.abyss_find_match(texts, [
    {"mod": "#% to Fire and Chaos Resistances"},     # ô 3
    {"mod": "# to all Attributes"},                  # ô 2
])
check("ưu tiên theo thứ tự điều kiện, không theo thứ tự ô", idx == 2, f"idx={idx}")

idx, c, val = core.abyss_find_match(texts, [{"mod": "#% increased Cast Speed"}])
check("mod không có trong panel thì không khớp", idx is None, f"idx={idx}")

print()
print("=== abyss_no_refresh.png (KHÔNG có nút refresh) ===")
use_image("tests/anh/abyss_no_refresh.png")
texts, has_refresh, reason = core.abyss_scan(FRAME)
for i, t in enumerate(texts, 1):
    print(f"    ô {i}: {t!r}")
print(f"    nút refresh: {has_refresh}   lý do lỗi: {reason}")
check("đọc được cả 3 ô", all(t.strip() for t in texts))
check("KHÔNG thấy nút refresh", has_refresh is False)
check("ô 1 đúng chữ", "14% INCREASED CAST SPEED" in texts[0])
check("ô 2 đúng chữ", "+24% TO COLD RESISTANCE" in texts[1])
check("ô 3 đúng chữ", "19% INCREASED RESERVATION EFFICIENCY OF HERALD SKILLS" in texts[2])

idx, c, val = core.abyss_find_match(
    texts, [{"mod": "#% to Cold Resistance", "min_value": 20}])
check("ngưỡng 20 cho qua mod 24%", idx == 1 and val == 24.0, f"idx={idx} val={val}")
idx, c, val = core.abyss_find_match(
    texts, [{"mod": "#% to Cold Resistance", "min_value": 25}])
check("ngưỡng 25 chặn mod 24%", idx is None, f"idx={idx}")

idx, c, val = core.abyss_find_match(
    texts, [{"mod": "#% increased Reservation Efficiency of Herald Skills"}])
check("mod dài nhất vẫn khớp (ô 3)", idx == 2, f"idx={idx}")

print()
print("=== khung căn SAI chỗ (phải báo lỗi, không được im lặng) ===")
use_image("tests/anh/abyss_sample.png")
texts, has_refresh, reason = core.abyss_scan((0, 0, 60, 33))
check("khung sai -> có lý do lỗi", reason is not None, f"reason={reason}")
print(f"    lý do: {reason}")

print()
print(f"KẾT QUẢ: {ok} đúng / {fail} sai")
sys.exit(1 if fail else 0)
