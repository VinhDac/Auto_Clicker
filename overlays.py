"""Chạy 3 overlay chọn-trên-màn-hình như một TIẾN TRÌNH CON, trả kết quả qua stdout.

Vì sao phải tách tiến trình: giao diện mới chạy trong WebView (Chromium), không tạo
nổi cửa sổ trong suốt phủ lên cửa sổ game để bắt click và đọc pixel. Ba overlay này
là tkinter và đã chạy tốt nhiều tháng, nên giữ NGUYÊN XI và gọi ra ngoài — thay vì
viết lại bằng web rồi hỏng.

Tách tiến trình (chứ không phải thread) vì tkinter và pywebview mỗi bên đòi vòng lặp
sự kiện riêng; nhét chung một tiến trình là chuốc lấy treo ngẫu nhiên.

Dùng:
    python overlays.py point
    python overlays.py abyss_frame --frame "[100,200,517,283]"
    python overlays.py inv_grid    --frame "[11,12,610,253]" --cells "[[0,0],[0,1]]"

In ra stdout ĐÚNG MỘT dòng JSON:
    {"ok": true,  "value": [x, y]}            # point
    {"ok": true,  "value": [x, y, w, h]}      # abyss_frame
    {"ok": true,  "value": {"frame": [...], "cells": [[r,c], ...]}}   # inv_grid
    {"ok": false}                             # người dùng huỷ (Esc)
    {"ok": false, "error": "..."}             # hỏng

Mọi thứ khác (cảnh báo của thư viện, traceback) đi ra stderr để stdout luôn sạch.
"""
import io
import sys
import json
import argparse

# stdout PHẢI là UTF-8: tên/nhãn trong app là tiếng Việt, mà console Windows mặc định
# là cp1252 -> UnicodeEncodeError giết cả tiến trình. Đúng bẫy tests/_boot.py đã gặp.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _in_ket_qua(ok, value=None, error=None):
    out = {"ok": bool(ok)}
    if value is not None:
        out["value"] = value
    if error:
        out["error"] = str(error)
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stdout.flush()


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("mode", choices=["point", "abyss_frame", "inv_grid", "review"])
    ap.add_argument("--frame", default=None, help="JSON [x,y,w,h]")
    ap.add_argument("--cells", default=None, help="JSON [[hang,cot], ...]")
    ap.add_argument("--points", default=None,
                    help='JSON [[x, y, "nhãn", "ok|accent|warn"], ...] cho mode review')
    args = ap.parse_args(argv)

    try:
        frame = json.loads(args.frame) if args.frame else None
        cells = json.loads(args.cells) if args.cells else None
        points = json.loads(args.points) if args.points else None
    except json.JSONDecodeError as e:
        _in_ket_qua(False, error=f"--frame/--cells không phải JSON hợp lệ: {e}")
        return 2

    # Import muộn: nếu thiếu thư viện thì báo qua JSON chứ không phun traceback.
    try:
        import tkinter as tk
        import overlay_ui as g
        import core
    except Exception as e:
        _in_ket_qua(False, error=f"không import được overlay_ui: {type(e).__name__}: {e}")
        return 3

    ket_qua = {"xong": False, "gia_tri": None}

    root = tk.Tk()
    root.withdraw()                 # chỉ overlay được hiện, cửa sổ gốc phải ẩn
    try:
        s = core.load_settings()
        g.set_accent(s.get("accent") or g.THEME["accent"])
        g.apply_theme(root)
    except Exception:
        pass                        # theme hỏng không được phép chặn việc chọn điểm

    def xong(v):
        ket_qua["xong"] = True
        ket_qua["gia_tri"] = v
        root.quit()

    try:
        if args.mode == "point":
            g.PointSelector(root, xong)
        elif args.mode == "abyss_frame":
            g.AbyssFrameSelector(root, frame, xong)
        elif args.mode == "review":
            # Tên màu do phía gọi gửi sang dạng khoá ("ok"/"accent"/"warn") chứ không
            # phải mã hex — bảng màu là chuyện của giao diện, đổi theme thì đổi ở đây.
            pts = [(p[0], p[1], p[2], g.THEME.get(p[3], g.THEME["accent"]))
                   for p in (points or [])]
            g.ReviewOverlay(root, pts, lambda: xong(True))
        else:
            g.InvGridSelector(root, frame, cells or [], xong)
    except Exception as e:
        _in_ket_qua(False, error=f"không mở được overlay: {type(e).__name__}: {e}")
        return 4

    root.mainloop()
    try:
        root.destroy()
    except Exception:
        pass

    v = ket_qua["gia_tri"]
    if v is None:
        _in_ket_qua(False)          # Esc = huỷ, không phải lỗi
        return 0

    if args.mode == "inv_grid":
        fr, cl = v
        _in_ket_qua(True, {"frame": list(fr), "cells": [list(c) for c in cl]})
    elif args.mode == "review":
        _in_ket_qua(True, True)        # chỉ để xem, không trả dữ liệu gì
    else:
        _in_ket_qua(True, list(v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
