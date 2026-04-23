"""
Script injeksi data demo Wasabi Kitchen — semua 10 Use Case terpetakan.

Cara jalankan (Windows PowerShell):
    docker cp custom_addons/wasabi_kitchen/inject_data.py <container>:/tmp/inject_data.py
    docker exec <container> bash -c "odoo shell -d postgres --no-http < /tmp/inject_data.py"

Idempotent: aman dijalankan berulang kali.
"""
import logging
from datetime import datetime, timedelta
_logger = logging.getLogger(__name__)


def log(msg):
    print(f"  [WK] {msg}")


# ─── STEP 1: POS Config ──────────────────────────────────────────────────────
# Pastikan config 'Wasabi Kitchen' ada dan unik.

log("=== STEP 1: POS Config ===")

wk_configs = env['pos.config'].search([('name', '=', 'Wasabi Kitchen')], order='id asc')
if len(wk_configs) > 1:
    keep = wk_configs[0]
    for dup in wk_configs[1:]:
        dup_floors = env['restaurant.floor'].search([('pos_config_ids', 'in', [dup.id])])
        for f in dup_floors:
            f.pos_config_ids = [(3, dup.id)]
        try:
            dup.unlink()
            log(f"  Deleted duplicate config id={dup.id}")
        except Exception as e:
            log(f"  Cannot delete config {dup.id}: {e}")
    wk_config = keep
elif len(wk_configs) == 1:
    wk_config = wk_configs[0]
else:
    wk_config = env['pos.config'].create({
        'name': 'Wasabi Kitchen',
        'iface_orderline_notes': True,
    })
    log(f"  Created POS config id={wk_config.id}")

log(f"  Using config id={wk_config.id}: {wk_config.name}")


# ─── STEP 2: Restaurant Floor ─────────────────────────────────────────────────

log("=== STEP 2: Restaurant Floor ===")

all_lantai = env['restaurant.floor'].search([('name', '=', 'Lantai Utama')])
if len(all_lantai) > 1:
    keep_floor = all_lantai[0]
    for dup in all_lantai[1:]:
        env['restaurant.table'].search([('floor_id', '=', dup.id)]).write({'floor_id': keep_floor.id})
        try:
            dup.unlink()
            log(f"  Merged duplicate floor id={dup.id}")
        except Exception as e:
            log(f"  Cannot delete floor {dup.id}: {e}")
    wk_floor = keep_floor
elif len(all_lantai) == 1:
    wk_floor = all_lantai[0]
else:
    wk_floor = env['restaurant.floor'].create({'name': 'Lantai Utama'})
    log(f"  Created floor id={wk_floor.id}")

if wk_config not in wk_floor.pos_config_ids:
    wk_floor.pos_config_ids = [(4, wk_config.id)]
log(f"  Using floor id={wk_floor.id}: {wk_floor.name}")


# ─── STEP 3: Tables — UC-02 Scan QR Code ──────────────────────────────────────
# Pastikan tepat 10 meja (Table 1–10) pada floor Wasabi Kitchen.
# Hapus meja orphan (nama tidak sesuai pola "Table N") agar UC-02 tampil bersih.

log("=== STEP 3: Tables (UC-02 Scan QR Code) ===")

# 3a. Deduplikasi Table 1–10
for i in range(1, 11):
    tname = f'Table {i}'
    tables = env['restaurant.table'].search([
        ('name', '=', tname), ('floor_id', '=', wk_floor.id)
    ], order='id asc')
    if len(tables) > 1:
        keep_t = tables[0]
        for dup_t in tables[1:]:
            try:
                dup_t.unlink()
            except Exception:
                pass
        log(f"  Deduplicated {tname}, kept id={keep_t.id}")
    elif len(tables) == 0:
        env['restaurant.table'].create({
            'name': tname, 'floor_id': wk_floor.id, 'seats': 4, 'shape': 'square',
        })
        log(f"  Created {tname}")
    else:
        tables[0].floor_id = wk_floor.id  # pastikan di floor yang benar

# 3b. Hapus tabel orphan pada floor WK (nama tidak sesuai "Table 1"–"Table 10")
valid_names = {f'Table {i}' for i in range(1, 11)}
orphan_tables = env['restaurant.table'].search([
    ('floor_id', '=', wk_floor.id),
    ('name', 'not in', list(valid_names)),
])
for t in orphan_tables:
    try:
        t.unlink()
        log(f"  Deleted orphan table '{t.name}' id={t.id}")
    except Exception as e:
        log(f"  Cannot delete orphan table '{t.name}': {e}")

all_tables = env['restaurant.table'].search([('floor_id', '=', wk_floor.id)], order='name')
log(f"  Tables: {[t.name for t in all_tables]}")


# ─── STEP 4: POS Categories ───────────────────────────────────────────────────

log("=== STEP 4: POS Categories ===")

def get_or_create_cat(name):
    cat = env['pos.category'].search([('name', '=', name)], limit=1)
    if not cat:
        cat = env['pos.category'].create({'name': name})
        log(f"  Created category: {name}")
    return cat

cat_makanan = get_or_create_cat('Makanan Utama')
cat_snack   = get_or_create_cat('Snack & Appetizer')
cat_minuman = get_or_create_cat('Minuman')


# ─── STEP 5: Menu Products — UC-03 Browse Menu | UC-06 Koreksi Stok ───────────
# Stock level sengaja bervariasi:
#   qty >= 4  → aman (hijau)       — Ramen, Katsu, Udon, Miso, Takoyaki, GreenTea
#   0 < qty < 4 → menipis (orange) — Salmon Sashimi (stock=2)
#   qty == 0  → habis (merah)      — tidak ada produk 0-stok agar order bisa dibuat

log("=== STEP 5: Menu Products (UC-03 Browse Menu | UC-06 Koreksi Stok) ===")

menu_data = [
    # (nama, harga, kategori, stock)
    ('Ramen Tonkotsu',   45000, cat_makanan, 10),
    ('Chicken Katsu',    38000, cat_makanan,  8),
    ('Sushi Set (8 pcs)',55000, cat_makanan,  6),
    ('Salmon Sashimi',   65000, cat_makanan,  2),   # stock menipis → warning UC-06
    ('Udon Goreng',      35000, cat_makanan, 12),
    ('Miso Soup',        18000, cat_snack,   20),
    ('Takoyaki (6 pcs)', 22000, cat_snack,   15),
    ('Green Tea',        15000, cat_minuman, 25),
]

products = {}
location = env['stock.warehouse'].search([], limit=1).lot_stock_id

for name, price, cat, stock_qty in menu_data:
    tmpl = env['product.template'].search([('name', '=', name)], limit=1)
    if not tmpl:
        tmpl = env['product.template'].create({
            'name': name,
            'list_price': price,
            'available_in_pos': True,
            'type': 'product',
            'pos_categ_ids': [(4, cat.id)],
        })
        log(f"  Created: {name}")
    else:
        tmpl.write({
            'available_in_pos': True,
            'type': 'product',
            'list_price': price,
            'pos_categ_ids': [(4, cat.id)],
        })
        log(f"  Updated: {name}")

    product = tmpl.product_variant_ids[0]
    products[name] = product

    quant = env['stock.quant'].search([
        ('product_id', '=', product.id),
        ('location_id', '=', location.id),
    ], limit=1)
    if quant:
        quant.sudo().write({'quantity': stock_qty})
    else:
        env['stock.quant'].sudo().create({
            'product_id': product.id,
            'location_id': location.id,
            'quantity': stock_qty,
        })
    status = 'WARNING' if 0 < stock_qty < 4 else ('OK' if stock_qty >= 4 else 'EMPTY')
    log(f"    Stock {name}: {stock_qty} [{status}]")


# ─── STEP 6: POS Session ──────────────────────────────────────────────────────

log("=== STEP 6: POS Session ===")

session = env['pos.session'].search([
    ('config_id', '=', wk_config.id),
    ('state', 'in', ['opening_control', 'opened']),
], limit=1)
if not session:
    session = env['pos.session'].create({'config_id': wk_config.id})
    session.action_pos_session_open()
    log(f"  Created and opened session id={session.id}")
else:
    log(f"  Using existing session id={session.id} state={session.state}")


# ─── STEP 7: Draft Orders — UC-05 Update Status | UC-09 Antrian | UC-10 Billing
# 2 order PENDING  → UC-05: tombol "Mulai Masak", UC-09: kolom Pending di kanban
# 2 order COOKING  → UC-05: tombol "Tandai READY", UC-09: kolom Cooking di kanban
# 2 order READY    → UC-10: tombol "Buka Billing", UC-07: bisa konfirmasi bayar

log("=== STEP 7: Draft Orders (UC-05|UC-09|UC-10) ===")

def get_table(name):
    return env['restaurant.table'].search(
        [('name', '=', name), ('floor_id', '=', wk_floor.id)], limit=1)

def make_order(table_name, kds_status, lines):
    """lines = [(product_name, qty, catatan)]"""
    table = get_table(table_name)
    if not table:
        log(f"  Table {table_name} not found, skip")
        return None

    existing = env['pos.order'].search([
        ('table_id', '=', table.id), ('state', '=', 'draft'),
    ], limit=1)
    if existing:
        log(f"  Order at {table_name} already exists (id={existing.id}), skip")
        return existing

    order_lines = []
    for pname, qty, note in lines:
        prod = products.get(pname)
        if not prod:
            log(f"    Product '{pname}' not found")
            continue
        subtotal = prod.list_price * qty
        order_lines.append((0, 0, {
            'product_id': prod.id,
            'qty': qty,
            'price_unit': prod.list_price,
            'price_subtotal': subtotal,
            'price_subtotal_incl': subtotal,
            'discount': 0.0,
            'catatan': note,
        }))

    order = env['pos.order'].create({
        'session_id': session.id,
        'table_id': table.id,
        'lines': order_lines,
        'kds_status': kds_status,
        'state': 'draft',
        'amount_tax': 0.0,
        'amount_total': 0.0,
        'amount_paid': 0.0,
        'amount_return': 0.0,
        'pricelist_id': wk_config.pricelist_id.id,
        'currency_id': wk_config.currency_id.id,
    })
    order._compute_batch_amount_all()
    log(f"  [{kds_status:8}] {table_name} | {len(order_lines)} items | Rp {int(order.amount_total):,}")
    return order

# PENDING — UC-09 Antrian kolom kiri, UC-05 tombol "Mulai Masak"
make_order('Table 1', 'pending', [
    ('Ramen Tonkotsu', 2, 'Extra kuah'),
    ('Green Tea', 2, ''),
])
make_order('Table 3', 'pending', [
    ('Sushi Set (8 pcs)', 1, ''),
    ('Miso Soup', 2, 'Tanpa garam'),
    ('Green Tea', 1, ''),
])

# COOKING — UC-09 Antrian kolom tengah, UC-05 tombol "Tandai READY"
make_order('Table 5', 'cooking', [
    ('Chicken Katsu', 1, 'Saus terpisah'),
    ('Udon Goreng', 1, 'Level pedas medium'),
    ('Green Tea', 2, ''),
])
make_order('Table 7', 'cooking', [
    ('Takoyaki (6 pcs)', 2, ''),
    ('Salmon Sashimi', 1, 'Fresh only'),  # stock=2, qty=1 → OK
])

# READY — UC-10 Buka Billing, UC-07 Konfirmasi Pembayaran
make_order('Table 9', 'ready', [
    ('Ramen Tonkotsu', 1, ''),
    ('Miso Soup', 1, ''),
])
make_order('Table 10', 'ready', [
    ('Udon Goreng', 2, 'Extra topping'),
    ('Green Tea', 3, 'Less ice'),
])


# ─── STEP 8: Paid Orders — UC-01 Query | UC-08 Export CSV ─────────────────────
# Hindari duplicate: skip jika paid order di meja+tanggal sudah ada.

log("=== STEP 8: Paid Orders (UC-01|UC-08) ===")

cash_method = env['pos.payment.method'].search(
    [('config_ids', 'in', [wk_config.id])], limit=1)
if not cash_method:
    cash_method = env['pos.payment.method'].search(
        [('is_cash_count', '=', True)], limit=1)
    if not cash_method:
        cash_method = env['pos.payment.method'].search([], limit=1)
    if cash_method:
        wk_config.payment_method_ids = [(4, cash_method.id)]
log(f"  Payment method: {cash_method.name if cash_method else 'NONE'}")

def make_paid_order(table_name, lines, days_ago):
    table = get_table(table_name)
    if not table or not cash_method:
        return

    order_date = datetime.now() - timedelta(days=days_ago, hours=2)

    # Cek duplicate: paid order di meja ini dengan tanggal yang sama (hari)
    date_start = order_date.replace(hour=0, minute=0, second=0)
    date_end   = order_date.replace(hour=23, minute=59, second=59)
    existing = env['pos.order'].search([
        ('table_id', '=', table.id),
        ('state', '=', 'paid'),
        ('date_order', '>=', date_start),
        ('date_order', '<=', date_end),
    ], limit=1)
    if existing:
        log(f"  Paid order at {table_name} ({days_ago}d ago) already exists (id={existing.id}), skip")
        return existing

    order_lines = []
    for pname, qty, note in lines:
        prod = products.get(pname)
        if not prod:
            continue
        subtotal = prod.list_price * qty
        order_lines.append((0, 0, {
            'product_id': prod.id,
            'qty': qty,
            'price_unit': prod.list_price,
            'price_subtotal': subtotal,
            'price_subtotal_incl': subtotal,
            'discount': 0.0,
            'catatan': note,
        }))

    order = env['pos.order'].create({
        'session_id': session.id,
        'table_id': table.id,
        'lines': order_lines,
        'kds_status': 'ready',
        'state': 'draft',
        'date_order': order_date,
        'amount_tax': 0.0,
        'amount_total': 0.0,
        'amount_paid': 0.0,
        'amount_return': 0.0,
        'pricelist_id': wk_config.pricelist_id.id,
        'currency_id': wk_config.currency_id.id,
    })
    order._compute_batch_amount_all()

    env['pos.payment'].create({
        'pos_order_id': order.id,
        'payment_method_id': cash_method.id,
        'amount': order.amount_total,
    })
    order.write({'state': 'paid', 'date_order': order_date})
    log(f"  Paid order id={order.id} {table_name} Rp {int(order.amount_total):,} ({days_ago}d ago)")

# Hari ini (0d ago) — untuk UC-01 query hari ini
make_paid_order('Table 2', [('Sushi Set (8 pcs)', 2, ''), ('Green Tea', 2, '')], 0)
make_paid_order('Table 4', [('Ramen Tonkotsu', 1, ''), ('Takoyaki (6 pcs)', 1, '')], 0)
# Kemarin (1d ago)
make_paid_order('Table 6', [('Chicken Katsu', 2, ''), ('Miso Soup', 2, ''), ('Green Tea', 3, '')], 1)
make_paid_order('Table 8', [('Salmon Sashimi', 1, ''), ('Udon Goreng', 1, '')], 1)  # Salmon: 1<=2 OK
# 2 hari lalu
make_paid_order('Table 2', [('Ramen Tonkotsu', 3, ''), ('Green Tea', 3, '')], 2)
make_paid_order('Table 4', [('Sushi Set (8 pcs)', 1, ''), ('Miso Soup', 3, '')], 2)


# ─── STEP 9: Summary ──────────────────────────────────────────────────────────

log("=== SUMMARY ===")

draft_orders = env['pos.order'].search([('state', '=', 'draft'), ('table_id', '!=', False)])
paid_orders  = env['pos.order'].search([('state', '=', 'paid')])
all_products = env['product.template'].search([
    ('available_in_pos', '=', True), ('name', '!=', 'Discount')
])
tables = env['restaurant.table'].search([('floor_id', '=', wk_floor.id)], order='name')

log(f"Config   : {wk_config.name} (id={wk_config.id})")
log(f"Floor    : {wk_floor.name} (id={wk_floor.id})")
log(f"Tables   : {len(tables)} — {[t.name for t in tables]}")
log(f"Products : {len(all_products)}")
log(f"Draft    : {len(draft_orders)} orders (UC-05/UC-09/UC-10)")
log(f"Paid     : {len(paid_orders)} orders (UC-01/UC-08)")

log("--- Draft orders per status ---")
for o in draft_orders.sorted(lambda o: (o.kds_status, o.no_meja)):
    log(f"  [{o.kds_status:8}] {o.table_id.name:10} | {len(o.lines)} items | Rp {int(o.amount_total):,}")

log("--- UC Coverage ---")
log("  UC-01 Query Transaksi  : Pelaporan → Laporan Transaksi (ada paid orders)")
log("  UC-02 Scan QR Code     : QR Ordering → Scan QR Code (10 meja bersih)")
log("  UC-03 Browse Menu      : QR Ordering → Daftar Menu (8 produk, 1 warning stok)")
log("  UC-04 Buat Pesanan     : QR Ordering → Buat Pesanan Baru → buka POS UI")
log("  UC-05 Update Status    : Kitchen Display → Antrian Masak → [Mulai Masak/Tandai READY]")
log("  UC-06 Koreksi Stok     : Kitchen Display → Koreksi Stok (Salmon=2 warning, edit inline)")
log("  UC-07 Konfirmasi Bayar : Kasir → Konfirmasi Pembayaran → pilih order ready → wizard")
log("  UC-08 Export CSV       : Pelaporan → Laporan Transaksi → [Ekspor CSV]")
log("  UC-09 Antrian Masak    : Kitchen Display → Antrian Masak (kanban 3 kolom)")
log("  UC-10 Buka Billing     : Kasir → Buka Billing → [Buka Billing] pada order ready")
log("=== DONE ===")

env.cr.commit()
