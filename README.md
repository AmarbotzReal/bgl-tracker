# BGL Price Tracker (itemku.com)

Melacak harga **Blue Gem Lock (BGL)** — Growtopia — dari 3 listing toko di
itemku.com secara otomatis, menyimpan histori harga (tanggal + jam) sebagai
"database" berupa file JSON di repo ini, dan menampilkannya sebagai grafik
ala trading di sebuah website (GitHub Pages).

```
bgl-tracker/
├── .github/workflows/scrape.yml   # jadwal otomatis (GitHub Actions)
├── scraper/scrape.py              # ambil harga & tulis ke data/*.json
├── data/history.json              # histori harga per toko (auto-generated)
├── data/summary.json              # ringkasan min/max/avg per run (auto-generated)
└── docs/index.html                # website (GitHub Pages)
```

## ⚠️ Baca dulu sebelum pakai

1. **robots.txt itemku memblokir automated fetch.** Saya (Claude) tidak bisa
   memverifikasi langsung struktur HTML halaman produk itemku saat menyusun
   scraper ini. Scraper dibuat dengan strategi generic (parsing data
   `__NEXT_DATA__` + fallback regex `"price":` / `Rp 123.456`) yang biasanya
   cukup andal untuk web app Next.js, tapi **kamu wajib mengetes run pertama
   secara manual** (lihat langkah 4) sebelum mengandalkan jadwal otomatis.
2. **Cek Syarat & Ketentuan itemku** sebelum menjalankan scraping otomatis
   dan terus-menerus. robots.txt yang disallow biasanya menandakan situs
   tidak ingin diakses bot. Pertimbangkan untuk memakai interval yang wajar
   (jangan terlalu sering) supaya tidak membebani server mereka atau
   berisiko IP GitHub Actions diblokir.
3. **Jadwal GitHub Actions tidak presisi.** `cron` di GitHub Actions adalah
   best-effort: minimum realistis aman adalah tiap 15–30 menit, dan sering
   meleset 5–15 menit lagi tergantung antrian runner. Repo publik gratis
   juga bisa kena nonaktif otomatis kalau tidak ada aktivitas commit >60 hari
   (tinggal jalankan manual lagi lewat tab Actions untuk mengaktifkan).

## Setup (5 langkah)

1. **Buat repo GitHub baru** (public, supaya GitHub Pages & raw content gratis),
   lalu upload semua isi folder ini ke repo tersebut.

2. **Edit konfigurasi di `docs/index.html`** — cari bagian ini di dekat akhir file
   dan ganti sesuai repo kamu:
   ```js
   const GH_OWNER  = "USERNAME_KAMU";
   const GH_REPO   = "bgl-tracker";
   const GH_BRANCH = "main";
   ```

3. **Aktifkan GitHub Pages**: Settings → Pages → Source: `Deploy from a branch`
   → Branch: `main` folder `/docs` → Save. Website akan tersedia di
   `https://USERNAME_KAMU.github.io/bgl-tracker/`.

4. **Test scraper manual dulu** sebelum mengandalkan jadwal otomatis:
   - Tab **Actions** → pilih workflow **Scrape BGL Prices** → **Run workflow**.
   - Setelah selesai, cek apakah `data/history.json` terisi dengan harga yang
     masuk akal. Kalau harga salah/kosong, buka file `scraper/scrape.py`,
     jalankan lokal dengan `DEBUG_DUMP=1 python scraper/scrape.py` untuk
     melihat semua kandidat angka yang ditemukan, lalu sesuaikan urutan
     `PRICE_KEY_HINTS` di bagian atas file.

5. Setelah beberapa run berhasil, buka website-nya — ticker, grafik, dan
   tabel perbandingan toko akan otomatis terisi dan ter-refresh sendiri
   tiap 5 menit di sisi browser (data sumbernya sendiri baru berubah
   sesuai jadwal Actions kamu).

## Kalau kamu sempat lihat error "CONFLICT (content): Merge conflict in data/history.json"

Ini terjadi kalau ada 2 run yang overlap (misalnya kamu klik "Run workflow"
manual persis saat jadwal cron juga jalan) — dua-duanya sama-sama mencoba
push ke file JSON yang sama, dan `git merge`/`rebase` biasa tidak tahu cara
menggabungkan isi array JSON secara aman.

**Sudah diperbaiki** di `.github/workflows/scrape.yml` versi ini:
- Sebelum scraping, workflow narik data terbaru dulu (`git pull --ff-only`)
  supaya jendela racenya kecil.
- Kalau tetap ada run lain yang keduluan push, workflow **tidak** memakai
  `git rebase`/`git merge` mentah. Sebaliknya dia memanggil
  `scraper/merge_data.py`, yang menggabungkan (union) isi
  `history.json`/`summary.json` versi lokal & remote berdasarkan
  `timestamp` + dedup, lalu commit ulang di atas versi remote terbaru.
  Ini aman karena tiap run **hanya menambah** entri baru, tidak pernah
  mengubah entri lama — jadi union semacam ini tidak mungkin kehilangan data.
- Kalau masih gagal, dicoba ulang sampai 5x dengan jeda acak singkat.

Kalau repo kamu sudah terlanjur ada konflik manual yang belum selesai
(state rebase nyangkut), paling gampang: jalankan `git rebase --abort` di
lokal, atau langsung ganti `.github/workflows/scrape.yml` dan
`scraper/merge_data.py` dengan versi terbaru ini lalu push ulang.

## Cara kerja singkat

- **Penyimpanan**: bukan database terpisah — cukup file JSON yang di-commit
  balik ke repo oleh GitHub Actions. Ini gratis, versioned (ada histori git-nya
  juga), dan mudah dibaca langsung oleh website lewat `raw.githubusercontent.com`.
- **Perbandingan harga**: tiap run, scraper menghitung harga termurah,
  termahal, dan rata-rata dari 3 toko, disimpan ke `data/summary.json`.
- **Grafik**: pakai [TradingView Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
  — satu garis per toko + satu garis putus-putus rata-rata, dengan toggle
  show/hide per toko dan crosshair ala platform trading.
- **Kalau harga naik/turun**, titik data baru otomatis menyambung ke garis
  yang sudah ada di run berikutnya — tidak perlu campur tangan manual.

## Menambah/mengubah produk yang dipantau

Edit list `PRODUCTS` di `scraper/scrape.py` dan `STORE_LABELS` /
`STORE_COLORS` di `docs/index.html` (keduanya dikunci dengan `product_id`
yang sama).
