import json
import os
import re
import sys
import time
import statistics
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

PRODUCTS = [
    {
        "id": "3425149",
        "label": "Store A",
        "url": "https://www.itemku.com/g/growtopia/lock?from=searchhomepage&item_info_group_id=104&item_info_id=21719&server_id=62&product_id=3425149",
    },
    {
        "id": "2453334",
        "label": "Store B",
        "url": "https://www.itemku.com/g/growtopia/lock?from=searchhomepage&item_info_group_id=104&item_info_id=21719&server_id=62&product_id=2453334",
    },
    {
        "id": "2133494",
        "label": "Store C",
        "url": "https://www.itemku.com/g/growtopia/lock?from=searchhomepage&item_info_group_id=104&item_info_id=21719&server_id=62&product_id=2133494",
    },
]

PRICE_KEY_HINTS = [
    "sell_price", "sellprice", "price_sell", "final_price",
    "price", "harga", "product_price", "item_price", "display_price",
]

# Memastikan file disimpan di dalam folder "data" sesuai permintaan index.html baru
DATA_DIR = "data"
HISTORY_PATH = os.path.join(DATA_DIR, "history.json")
SUMMARY_PATH = os.path.join(DATA_DIR, "summary.json")

WIB = timezone(timedelta(hours=7))  # Asia/Jakarta

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

DEBUG = os.environ.get("DEBUG_DUMP") == "1"

def fetch_html(url: str, retries: int = 3, timeout: int = 20) -> str:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (URLError, HTTPError) as e:
            last_err = e
            print(f"  [!] percobaan {attempt}/{retries} gagal: {e}", file=sys.stderr)
            time.sleep(2 * attempt)
    raise RuntimeError(f"Gagal mengambil {url}: {last_err}")


def find_next_data(html: str):
    m = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html, re.DOTALL,
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def recursive_find_prices(obj, key_hints, path="", found=None):
    if found is None:
        found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = k.lower()
            if isinstance(v, (int, float)) and any(h in lk for h in key_hints):
                found.append((f"{path}.{k}", v))
            recursive_find_prices(v, key_hints, f"{path}.{k}", found)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            recursive_find_prices(v, key_hints, f"{path}[{i}]", found)
    return found

def extract_price_from_html(html: str, label: str):
    candidates = []

    # Strategi 1: __NEXT_DATA__
    data = find_next_data(html)
    if data is not None:
        hits = recursive_find_prices(data, PRICE_KEY_HINTS)
        candidates.extend(hits)
        if DEBUG:
            print(f"  [debug:{label}] kandidat dari __NEXT_DATA__:")
            for path, val in hits:
                print(f"      {path} = {val}")

    if candidates:
        for hint in PRICE_KEY_HINTS:
            for path, val in candidates:
                if hint in path.lower() and val and val > 0:
                    return int(val), f"next_data:{path}"

    # Strategi 2: pola JSON mentah "price":12345
    m = re.findall(r'"(?:sell_price|price|harga)"\s*:\s*"?(\d{3,12})"?', html)
    if m:
        nums = [int(x) for x in m if int(x) > 0]
        if nums:
            mode_val = statistics.mode(nums)
            return mode_val, "regex_json"

    # Strategi 3: pola teks "Rp 123.456"
    m = re.findall(r'Rp\s*([\d.,]{4,15})', html)
    if m:
        cleaned = [int(re.sub(r"[.,]", "", x)) for x in m]
        cleaned = [c for c in cleaned if c > 100]  
        if cleaned:
            mode_val = statistics.mode(cleaned)
            return mode_val, "regex_text_rp"

    return None, None

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def main():
    history = load_json(HISTORY_PATH, {})
    now = datetime.now(WIB)
    ts_iso = now.isoformat()

    run_results = []

    for prod in PRODUCTS:
        pid = prod["id"]
        print(f"[*] Mengambil harga {prod['label']} ({pid}) ...")
        try:
            html = fetch_html(prod["url"])
        except RuntimeError as e:
            print(f"  [x] {e}", file=sys.stderr)
            continue

        price, source = extract_price_from_html(html, prod["label"])
        if price is None:
            print(f"  [x] Harga tidak ditemukan untuk {prod['label']}.", file=sys.stderr)
            continue

        print(f"  [ok] {prod['label']}: Rp {price:,} (via {source})".replace(",", "."))

        entry = {
            "timestamp": ts_iso,
            "price": price,
            "source": source,
        }
        history.setdefault(pid, []).append(entry)
        run_results.append({"id": pid, "label": prod["label"], "price": price})

    save_json(HISTORY_PATH, history)

    if run_results:
        prices = [r["price"] for r in run_results]
        summary_entry = {
            "timestamp": ts_iso,
            "min": min(prices),
            "max": max(prices),
            "avg": round(sum(prices) / len(prices)),
            "detail": run_results,
        }
        summary_history = load_json(SUMMARY_PATH, [])
        summary_history.append(summary_entry)
        save_json(SUMMARY_PATH, summary_history)

        print("\n=== RINGKASAN RUN INI ===")
        print(f"Termurah : Rp {summary_entry['min']:,}".replace(",", "."))
        print(f"Termahal : Rp {summary_entry['max']:,}".replace(",", "."))
        print(f"Rata-rata: Rp {summary_entry['avg']:,}".replace(",", "."))
    else:
        print("[!] Tidak ada harga yang berhasil diambil pada run ini.")


if __name__ == "__main__":
    main()
