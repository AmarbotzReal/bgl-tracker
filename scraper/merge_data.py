#!/usr/bin/env python3
"""
merge_data.py
=============
Dipanggil oleh workflow saat `git push` ditolak (non-fast-forward) karena ada
run lain yang lebih dulu push. Alih-alih mengandalkan git merge tekstual pada
file JSON (yang gampang conflict karena urutan/isi array berubah), script ini
melakukan UNION yang paham struktur data:

- data/history.json: dict {product_id: [ {timestamp, price, source}, ... ]}
  -> gabungkan list per product_id, dedup berdasarkan (timestamp, price, source),
     lalu urutkan berdasarkan timestamp.
- data/summary.json: list [ {timestamp, min, max, avg, detail}, ... ]
  -> gabungkan, dedup berdasarkan timestamp, urutkan berdasarkan timestamp.

Karena tiap run hanya MENAMBAH entri baru (tidak pernah mengubah entri lama),
union semacam ini aman dan idempotent tidak peduli urutan proses.

Pemakaian:
    python scraper/merge_data.py <path_ke_versi_local> <path_ke_versi_remote> <path_output>
"""

import json
import sys


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def merge_history(local: dict, remote: dict) -> dict:
    merged = {}
    all_ids = set(local.keys()) | set(remote.keys())
    for pid in all_ids:
        entries = (local.get(pid, []) or []) + (remote.get(pid, []) or [])
        seen = set()
        unique = []
        for e in entries:
            key = (e.get("timestamp"), e.get("price"), e.get("source"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(e)
        unique.sort(key=lambda e: e.get("timestamp", ""))
        merged[pid] = unique
    return merged


def merge_summary(local: list, remote: list) -> list:
    entries = (local or []) + (remote or [])
    seen = set()
    unique = []
    for e in entries:
        key = e.get("timestamp")
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)
    unique.sort(key=lambda e: e.get("timestamp", ""))
    return unique


def main():
    if len(sys.argv) != 5:
        print("Usage: merge_data.py <kind:history|summary> <local_path> <remote_path> <output_path>",
              file=sys.stderr)
        sys.exit(1)

    kind, local_path, remote_path, output_path = sys.argv[1:5]

    local = load(local_path)
    remote = load(remote_path)

    if kind == "history":
        merged = merge_history(local, remote)
    elif kind == "summary":
        merged = merge_summary(local, remote)
    else:
        print(f"Kind tidak dikenal: {kind}", file=sys.stderr)
        sys.exit(1)

    save(output_path, merged)
    print(f"[merge_data] {kind}: berhasil digabung -> {output_path}")


if __name__ == "__main__":
    main()
