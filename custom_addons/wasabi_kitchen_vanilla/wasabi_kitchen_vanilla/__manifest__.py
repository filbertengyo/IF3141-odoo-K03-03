# -*- coding: utf-8 -*-
{
    'name': 'Wasabi Kitchen — QR Ordering & KDS',
    'version': '17.0.1.0.0',
    'category': 'Point of Sale/Restaurant',
    'summary': 'QR Self-Ordering, Kitchen Display System, Real-time Stock & Reporting for Wasabi Kitchen Jatinangor',
    'description': """
Wasabi Kitchen — QR Ordering & Kitchen Display System
======================================================

Sistem informasi terintegrasi untuk operasional restoran Wasabi Kitchen Jatinangor.

Fitur Utama
-----------
* **FR-01** Pemesanan mandiri pelanggan via QR Code (tanpa registrasi akun)
* **FR-02** Auto-decrement stok real-time saat pesanan dikonfirmasi
* **FR-03** Koreksi stok manual oleh koki dengan audit log
* **FR-04** Kitchen Display System (KDS) berbasis Kanban real-time
* **FR-05** Konfirmasi pembayaran kasir (Tunai / QRIS) dengan PB1 10% & service 5%
* **FR-06** Ekstraksi laporan transaksi ke format XLSX/CSV

Aktor: Pelanggan, Koki, Kasir, Manager
    """,
    'author': 'Kelompok 03 - K03 (IF3141 Sistem Informasi)',
    'website': 'https://wasabikitchen.example.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
        'product',
        'portal',
    ],
    'data': [
        # Security
        'security/wasabi_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/wasabi_sequence.xml',
        'data/wasabi_demo_data.xml',

        # Wizards harus load SEBELUM views yang mereferensikan action-nya
        'wizards/payment_wizard_views.xml',
        'wizards/qr_preview_wizard_views.xml',

        # Views — actions must load BEFORE menus that reference them
        'views/category_views.xml',
        'views/menu_item_views.xml',
        'views/table_views.xml',
        'views/order_views.xml',
        'views/transaction_views.xml',
        'views/stock_log_views.xml',
        'views/kds_views.xml',
        'views/billing_views.xml',
        'views/dashboard_views.xml',

        # Wizard lainnya
        'wizards/export_report_wizard_views.xml',

        # Reports
        'report/billing_report.xml',

        # Menus terakhir — semua actions sudah ter-define
        'views/wasabi_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'wasabi_kitchen_vanilla/static/src/css/wasabi_theme.css',
            'wasabi_kitchen_vanilla/static/src/css/kds.css',
            'wasabi_kitchen_vanilla/static/src/css/billing.css',
            'wasabi_kitchen_vanilla/static/src/js/kds_kanban.js',
            'wasabi_kitchen_vanilla/static/src/js/billing_floor.js',
            'wasabi_kitchen_vanilla/static/src/xml/kds_templates.xml',
        ],
        'web.assets_frontend': [
            'wasabi_kitchen_vanilla/static/src/css/customer.css',
            'wasabi_kitchen_vanilla/static/src/js/customer_menu.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'application': True,
    'installable': True,
    'auto_install': False,
}
