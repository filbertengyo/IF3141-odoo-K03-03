<div align="center">
  <img width="100%" src="https://capsule-render.vercel.app/api?type=waving&height=260&color=0:F0FFC2,100:28396C&text=Wasabi%20Kitchen&fontColor=1C2850&fontSize=62&desc=IF3141%20Sistem%20Informasi&descAlignY=76&descSize=17&descColor=28396C" />
</div>

<h1 align="center">IF3141 Sistem Informasi</h1>

<div align="center">
  <img src="https://img.shields.io/badge/Odoo%2017-714B67?style=for-the-badge&logo=odoo&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</div>

---

## Introduction

Odoo merupakan *Enterprise Resource Planning System* yang mampu melakukan implementasi modul modul kustom untuk menyelesaikan permasalahan proses bisnis pada suatu perusahaan. Odoo memberikan opsi *on-premise solution* sehingga developer dapat melakukan implementasi kustom modul pada local environment.

Repository ini diperuntukkan untuk Tugas Besar IF3141 Sistem Informasi. Untuk memulai silakan melakukan fork dan membuat repository private untuk workspace setiap kelompok.

---

## About

Modul Odoo 17 kustom untuk restoran Wasabi Kitchen Jatinangor yang mengintegrasikan pemesanan mandiri via QR Code, Kitchen Display System (KDS), konfirmasi pembayaran kasir, manajemen stok real-time, dan ekspor laporan transaksi dalam satu platform terpadu.

---

## Pre-requisites

Odoo diimplementasikan dengan Python environment dan database PostgreSQL. Repository ini sudah membungkus service aplikasi dan database melalui Docker.

Sebelum memulai, pastikan dependency berikut sudah terpasang:

1. **Docker Desktop**
   - Download: https://www.docker.com/products/docker-desktop/
2. **Python 3.11**
   - Digunakan untuk virtual environment (venv) pada proses development modul

---

## Features

- **QR Code Self-Ordering**: Pelanggan scan QR di meja untuk mengakses menu dan membuat pesanan tanpa perlu interaksi dengan kasir. Setiap meja memiliki URL unik dengan access token terenkripsi.

- **Kitchen Display System (KDS)**: Tampilan kanban 3 kolom (Pending, Cooking, Ready) untuk dapur. Koki dapat update status pesanan secara real-time dan melihat antrian masak aktif.

- **Billing & Konfirmasi Pembayaran**: Wizard kasir untuk konfirmasi pembayaran Tunai atau QRIS, kalkulasi kembalian otomatis, dan pembuatan POS payment record yang memicu stock picking.

- **Manajemen Stok Real-time**: Stok otomatis berkurang saat pesanan dibayar. Koki dapat melakukan koreksi stok manual via inventory adjustment. Menu dengan stok 0 tidak dapat dipesan.

- **Katalog Menu dengan Status Stok**: Tampilan card collection dengan filter Tersedia, Menipis, dan Habis. Mendukung pencarian by nama dan pengelompokan by kategori.

- **Laporan Transaksi & Ekspor CSV**: Query transaksi by rentang tanggal dengan ringkasan statistik, ekspor hasil ke file CSV untuk keperluan pelaporan.

---

## Tech Stack

| Layer | Technology |
|:---|:---|
| Backend | Odoo 17 (Python) |
| Database | PostgreSQL 16 |
| Frontend | Odoo Web Client + Custom CSS Design System |
| Infrastructure | Docker Compose |
| POS Modules | point_of_sale, pos_restaurant, pos_self_order, stock |

---

## Struktur Direktori

```
IF3141-odoo-K03-03/
├── custom_addons/
│   └── wasabi_kitchen/
│       ├── models/              # Business logic (Python)
│       ├── views/               # UI definitions (XML)
│       ├── static/src/css/      # Design system CSS
│       ├── data/                # Seed data (POS config, tables)
│       ├── security/            # ACL rules
│       ├── hooks.py             # post_init_hook
│       └── inject_data.py       # Script re-seed demo data
├── config/                      # odoo.conf
├── scripts/                     # export_db / import_db
├── dump/                        # Database dump files
└── docker-compose.yml
```

| Folder | Deskripsi |
|:---|:---|
| `/config` | Untuk menyimpan konfigurasi Odoo |
| `/custom_addons` | Tempat pengerjaan modul kustom |
| `/dump` | Database dump yang dapat diakses scripts untuk proses import/export |
| `/scripts` | Untuk melakukan database migration |
| `docker-compose.yml` | Orchestration service Odoo dan PostgreSQL |

---

## Setup dan Menjalankan

> **Prerequisites:** Docker Desktop terinstal dan berjalan.

### 1. Clone repositori

```bash
git clone <repo-url>
cd IF3141-odoo-K03-03
```

### 2. Jalankan service

```bash
docker compose up -d
```

Buka browser di `http://localhost:8069`, login dengan `admin` / `admin`.

Modul `wasabi_kitchen` otomatis ter-install beserta data demo (10 meja, 8 menu, draft dan paid orders).

### 3. Setup virtual environment (untuk development)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Aktifkan Developer Mode

- Masuk ke **Settings**
- Nyalakan **Developer Mode / Developer Access**

### 5. Update modul setelah perubahan

```bash
# Perubahan model/view/data
docker exec if3141-odoo-k03-03-web-1 odoo -d postgres -u wasabi_kitchen --stop-after-init
docker compose up -d

# Perubahan CSS/template saja
docker compose restart web
```

### 6. Re-inject data demo

```bash
docker cp custom_addons/wasabi_kitchen/inject_data.py if3141-odoo-k03-03-web-1:/tmp/inject_data.py
docker exec if3141-odoo-k03-03-web-1 bash -c "odoo shell -d postgres --no-http < /tmp/inject_data.py"
```

---

## Database Migration (Antar Anggota Tim)

Odoo menggunakan local database pada implementasinya. Maka dari itu dibutuhkan migration system yang dapat dilakukan dengan **dump db** atau **import db**. Sebelum melakukan migration, selalu matikan service terlebih dahulu:

```bash
docker compose down
```

Apabila terdapat perubahan pada database dan ingin diteruskan ke anggota tim lain, lakukan export database menggunakan script pada folder `scripts`.

**Export:**

| OS | Command |
|:---|:---|
| macOS/Linux | `./scripts/export_db.sh` |
| Windows | `scripts\export_db.cmd` |

**Import:**

Untuk melanjutkan pengerjaan dari hasil perubahan database rekan tim, lakukan import database:

| OS | Command |
|:---|:---|
| macOS/Linux | `./scripts/import_db.sh` |
| Windows | `scripts\import_db.cmd` |

---

## Authors

<div align="center">

| NIM | Nama |
|:---:|:---|
| 13523126 | Brian Ricardo Tamin |
| 13523133 | Rafa Abdussalam Danadyaksa |
| 13523151 | Ardell Aghna Mahendra |
| 13523154 | Theo Kurniady |
| 13523163 | Filbert Engyo |

</div>

---

<div align="center">
  <img width="100%" src="https://capsule-render.vercel.app/api?type=waving&height=120&color=0:28396C,100:F0FFC2&section=footer" />
</div>
