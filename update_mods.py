"""
Cập nhật danh sách mod (stat) từ Trade API chính thức của PoE về file mods_<game>.txt.

Chạy:
    python update_mods.py            # cập nhật cả poe1 + poe2
    python update_mods.py poe2       # chỉ poe2

Nguồn (sạch, đúng chữ game dùng để search trên trang trade):
    PoE1: https://www.pathofexile.com/api/trade/data/stats
    PoE2: https://www.pathofexile.com/api/trade2/data/stats
"""

import os
import sys
import json
import urllib.request

API = {
    "poe1": "https://www.pathofexile.com/api/trade/data/stats",
    "poe2": "https://www.pathofexile.com/api/trade2/data/stats",
}
# Nhóm mod liên quan tới craft item bằng currency
KEEP_LABELS = {"Explicit", "Implicit"}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def fetch_texts(game):
    """Trả về list text mod (đã bỏ trùng, sắp xếp) cho game ('poe1'|'poe2')."""
    url = API[game]
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
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


def save(game, out_dir):
    texts = fetch_texts(game)
    path = os.path.join(out_dir, f"mods_{game}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(texts))
    return path, len(texts)


def main():
    out = os.path.dirname(os.path.abspath(__file__))
    games = [g.lower() for g in sys.argv[1:]] or ["poe1", "poe2"]
    for g in games:
        if g not in API:
            print(f"{g}: bỏ qua (chỉ nhận poe1/poe2)")
            continue
        try:
            p, n = save(g, out)
            print(f"{g}: {n} mod -> {p}")
        except Exception as e:
            print(f"{g}: LỖI {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
