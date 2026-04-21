"""
Script injeksi data demo Wasabi Kitchen.
Jalankan via: docker exec <container> odoo shell -d postgres ... < inject_data.py
"""
import logging
_logger = logging.getLogger(__name__)

# ─── 0. Helper ────────────────────────────────────────────────────────────────

def log(msg):
    print(f"  [WK] {msg}")

# ─── 1. Bersihkan duplikat POS Config & floor ─────────────────────────────────

log("=== STEP 1: Clean up duplicate POS configs ===")

wk_configs = env['pos.config'].search([('name', '=', 'Wasabi Kitchen')], order='id asc')
log(f"Found {len(wk_configs)} Wasabi Kitchen configs: {wk_configs.ids}")

if len(wk_configs) > 1:
    keep = wk_configs[0]
    for dup in wk_configs[1:]:
        # Hapus floor/table yg ke-link ke config duplikat
        dup_floors = env['restaurant.floor'].search([('pos_config_ids', 'in', [dup.id])])
        for f in dup_floors:
            f.pos_config_ids = [(3, dup.id)]  # unlink from dup
        try:
            dup.unlink()
            log(f"  Deleted duplicate config id={dup.id}")
        except Exception as e:
            log(f"  Cannot delete config {dup.id}: {e}")
    wk_config = keep
else:
    wk_config = wk_configs[0] if wk_configs else None

if not wk_config:
    log("Creating Wasabi Kitchen POS config...")
    wk_config = env['pos.config'].create({
        'name': 'Wasabi Kitchen',
        'iface_orderline_notes': True,
    })

log(f"Using POS config id={wk_config.id}: {wk_config.name}")

# ─── 2. Pastikan floor "Lantai Utama" unik dan linked ke config yang benar ────

log("=== STEP 2: Fix restaurant floors ===")

all_lantai = env['restaurant.floor'].search([('name', '=', 'Lantai Utama')])
log(f"Found {len(all_lantai)} 'Lantai Utama' floors: {all_lantai.ids}")

if len(all_lantai) > 1:
    keep_floor = all_lantai[0]
    for dup_floor in all_lantai[1:]:
        # Pindahkan semua table ke floor yang dipertahankan
        dup_tables = env['restaurant.table'].search([('floor_id', '=', dup_floor.id)])
        dup_tables.write({'floor_id': keep_floor.id})
        try:
            dup_floor.unlink()
            log(f"  Merged and deleted duplicate floor id={dup_floor.id}")
        except Exception as e:
            log(f"  Cannot delete floor {dup_floor.id}: {e}")
    wk_floor = keep_floor
elif len(all_lantai) == 1:
    wk_floor = all_lantai[0]
else:
    wk_floor = env['restaurant.floor'].create({'name': 'Lantai Utama'})

# Pastikan floor ter-link ke config yang benar
if wk_config not in wk_floor.pos_config_ids:
    wk_floor.pos_config_ids = [(4, wk_config.id)]
log(f"Using floor id={wk_floor.id}: {wk_floor.name}")

# ─── 3. Deduplikasi tables, pastikan Table 1-10 ada ──────────────────────────

log("=== STEP 3: Fix restaurant tables ===")

for i in range(1, 11):
    tname = f'Table {i}'
    tables = env['restaurant.table'].search([('name', '=', tname)], order='id asc')
    if len(tables) > 1:
        keep_t = tables[0]
        keep_t.floor_id = wk_floor.id
        for dup_t in tables[1:]:
            try:
                dup_t.unlink()
            except Exception:
                pass
        log(f"  Deduplicated {tname}, kept id={keep_t.id}")
    elif len(tables) == 1:
        tables[0].floor_id = wk_floor.id
    else:
        env['restaurant.table'].create({
            'name': tname, 'floor_id': wk_floor.id, 'seats': 4, 'shape': 'square',
        })
        log(f"  Created {tname}")

all_tables = env['restaurant.table'].search([('floor_id', '=', wk_floor.id)], order='name')
log(f"Tables in floor: {[t.name for t in all_tables]}")

# ─── 4. Buat/pastikan kategori POS ───────────────────────────────────────────

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

# ─── 5. Buat produk menu ──────────────────────────────────────────────────────

log("=== STEP 5: Menu Products ===")

menu_data = [
    ('Ramen Tonkotsu',   45000, cat_makanan, 10),
    ('Chicken Katsu',    38000, cat_makanan,  8),
    ('Sushi Set (8 pcs)',55000, cat_makanan,  6),
    ('Salmon Sashimi',   65000, cat_makanan,  4),
    ('Udon Goreng',      35000, cat_makanan, 12),
    ('Miso Soup',        18000, cat_snack,   20),
    ('Takoyaki (6 pcs)', 22000, cat_snack,   15),
    ('Green Tea',        15000, cat_minuman, 25),
]

products = {}  # name -> product.product record

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
        log(f"  Created product: {name}")
    else:
        tmpl.write({
            'available_in_pos': True,
            'type': 'product',
            'list_price': price,
            'pos_categ_ids': [(4, cat.id)],
        })
        log(f"  Updated product: {name}")

    # Set stok via stock.quant
    product = tmpl.product_variant_ids[0]
    products[name] = product

    location = env['stock.warehouse'].search([], limit=1).lot_stock_id
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
    log(f"    Stock {name}: {stock_qty}")

env.cr.execute("SELECT count(*) FROM product_template WHERE available_in_pos=true AND name->>'en_US' != 'Discount'")
log(f"Total POS products: {env.cr.fetchone()[0]}")

# ─── 6. Buat/buka POS Session ────────────────────────────────────────────────

log("=== STEP 6: POS Session ===")

session = env['pos.session'].search([
    ('config_id', '=', wk_config.id),
    ('state', 'in', ['opening_control', 'opened']),
], limit=1)

if not session:
    session = env['pos.session'].create({'config_id': wk_config.id})
    session.action_pos_session_open()
    log(f"  Created and opened new session id={session.id}")
else:
    log(f"  Using existing session id={session.id} state={session.state}")

# ─── 7. Inject POS Orders (draft / active) ───────────────────────────────────

log("=== STEP 7: Draft Orders (KDS) ===")

def get_table(name):
    return env['restaurant.table'].search([('name', '=', name), ('floor_id', '=', wk_floor.id)], limit=1)

def make_order(table_name, kds_status, lines):
    """lines = [(product_name, qty, note)]"""
    table = get_table(table_name)
    if not table:
        log(f"  Table {table_name} not found, skip")
        return None

    # Cek kalau sudah ada order draft di meja ini
    existing = env['pos.order'].search([
        ('table_id', '=', table.id),
        ('state', '=', 'draft'),
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
    log(f"  Created order id={order.id} at {table_name}, kds={kds_status}, total={order.amount_total}")
    return order

make_order('Table 1', 'pending', [
    ('Ramen Tonkotsu', 2, 'Extra kuah'),
    ('Green Tea', 2, ''),
])
make_order('Table 3', 'pending', [
    ('Sushi Set (8 pcs)', 1, ''),
    ('Miso Soup', 2, 'Tanpa garam'),
    ('Green Tea', 1, ''),
])
make_order('Table 5', 'cooking', [
    ('Chicken Katsu', 1, 'Saus terpisah'),
    ('Udon Goreng', 1, 'Level pedas medium'),
    ('Green Tea', 2, ''),
])
make_order('Table 7', 'cooking', [
    ('Takoyaki (6 pcs)', 2, ''),
    ('Salmon Sashimi', 1, 'Fresh only'),
])
make_order('Table 9', 'ready', [
    ('Ramen Tonkotsu', 1, ''),
    ('Miso Soup', 1, ''),
])
make_order('Table 10', 'ready', [
    ('Udon Goreng', 2, 'Extra topping'),
    ('Green Tea', 3, 'Less ice'),
])

# ─── 8. Inject Paid Orders (riwayat transaksi) ───────────────────────────────

log("=== STEP 8: Paid Orders (Riwayat) ===")

from datetime import datetime, timedelta

cash_method = env['pos.payment.method'].search([
    ('config_ids', 'in', [wk_config.id]),
], limit=1)
if not cash_method:
    # Cari payment method apapun lalu link ke config
    cash_method = env['pos.payment.method'].search([('is_cash_count', '=', True)], limit=1)
    if not cash_method:
        cash_method = env['pos.payment.method'].search([], limit=1)
    if cash_method:
        wk_config.payment_method_ids = [(4, cash_method.id)]
log(f"Payment method: {cash_method.name if cash_method else 'NONE'}")

def make_paid_order(table_name, lines, days_ago, payment_method=None):
    table = get_table(table_name)
    if not table:
        return
    pm = payment_method or cash_method

    order_lines = []
    total = 0
    for pname, qty, note in lines:
        prod = products.get(pname)
        if not prod:
            continue
        subtotal = prod.list_price * qty
        total += subtotal
        order_lines.append((0, 0, {
            'product_id': prod.id,
            'qty': qty,
            'price_unit': prod.list_price,
            'price_subtotal': subtotal,
            'price_subtotal_incl': subtotal,
            'discount': 0.0,
            'catatan': note,
        }))

    order_date = datetime.now() - timedelta(days=days_ago, hours=2)
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

    # Tambah payment
    env['pos.payment'].create({
        'pos_order_id': order.id,
        'payment_method_id': pm.id,
        'amount': order.amount_total,
    })

    # Mark as paid
    order.write({'state': 'paid', 'date_order': order_date})
    log(f"  Paid order id={order.id} table={table_name} total={order.amount_total} ({days_ago}d ago)")

make_paid_order('Table 2', [('Sushi Set (8 pcs)', 2, ''), ('Green Tea', 2, '')], 0)
make_paid_order('Table 4', [('Ramen Tonkotsu', 1, ''), ('Takoyaki (6 pcs)', 1, '')], 0)
make_paid_order('Table 6', [('Chicken Katsu', 2, ''), ('Miso Soup', 2, ''), ('Green Tea', 3, '')], 1)
make_paid_order('Table 8', [('Salmon Sashimi', 1, ''), ('Udon Goreng', 1, '')], 1)
make_paid_order('Table 2', [('Ramen Tonkotsu', 3, ''), ('Green Tea', 3, '')], 2)
make_paid_order('Table 4', [('Sushi Set (8 pcs)', 1, ''), ('Miso Soup', 3, '')], 2)

# ─── 9. Summary ───────────────────────────────────────────────────────────────

log("=== SUMMARY ===")
draft_orders  = env['pos.order'].search([('state', '=', 'draft'), ('table_id', '!=', False)])
paid_orders   = env['pos.order'].search([('state', '=', 'paid')])
all_products  = env['product.template'].search([('available_in_pos', '=', True)])

log(f"POS config     : {wk_config.name} (id={wk_config.id})")
log(f"Restaurant floor: {wk_floor.name} (id={wk_floor.id})")
log(f"Tables         : {len(all_tables)}")
log(f"POS products   : {len(all_products)}")
log(f"Draft orders   : {len(draft_orders)} (KDS antrian)")
log(f"Paid orders    : {len(paid_orders)} (riwayat transaksi)")

for o in draft_orders:
    log(f"  [{o.kds_status:8}] {o.table_id.name:10} | {len(o.lines)} items | Rp {int(o.amount_total):,}")

log("=== DONE ===")
env.cr.commit()
