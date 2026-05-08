"""
Seed 155 paid transactions (5/hari, 1–31 Mei 2026) ke wasabi.order + wasabi.transaction.
Idempotent — skip jika order_number sudah ada.

Run:
    docker cp custom_addons/wasabi_kitchen_vanilla/inject_may_transactions.py <container>:/tmp/inject_wk_may.py
    docker exec <container> bash -c "odoo shell -d postgres --no-http < /tmp/inject_wk_may.py"
"""
from datetime import datetime

def log(msg):
    print(f"  [WKV] {msg}")

log("=== WASABI KITCHEN VANILLA — MAY SEED ===")

# ─── Lookup data ──────────────────────────────────────────────────────────────
tables = {t.table_number: t for t in env['wasabi.table'].search([])}
log(f"Tables found: {sorted(tables.keys())}")

items = {i.id: i for i in env['wasabi.menu.item'].search([])}
log(f"Menu items: {[(i.id, i.name, int(i.price)) for i in items.values()]}")

# Cari IDR termasuk yang inactive
currency = env['res.currency'].with_context(active_test=False).search([('name', '=', 'IDR')], limit=1)
if not currency:
    # Fallback: pakai currency yang sama dengan menu item pertama
    first_item = env['wasabi.menu.item'].search([], limit=1)
    currency = first_item.currency_id
log(f"Currency: {currency.name} (id={currency.id})")

admin = env['res.users'].search([('login', '=', 'admin')], limit=1)
log(f"Staff: {admin.name} (id={admin.id})")

# ─── Menu combo templates ─────────────────────────────────────────────────────
# (menu_item_id, qty, note)
# Pakai item yang ada: 1=Salmon Sashimi, 2=Spicy Tuna, 3=Wasabi Set,
# 4=California Roll, 5=Chicken Katsu Ramen, 6=Tonkotsu Ramen,
# 8=Chicken Teriyaki Bento, 9=Salmon Bento, 10=Ocha,
# 11=Ramune Soda, 12=Matcha Latte, 13=Mochi Ice Cream, 14=Dorayaki
# (skip id=7 Miso Soup — stok 0)

COMBOS = [
    [(6,2,''), (10,2,'Less ice')],
    [(5,1,'Saus terpisah'), (10,1,''), (11,1,'')],
    [(3,1,''), (10,2,'')],
    [(4,2,'Pedas sedang'), (13,1,'')],
    [(1,1,'Fresh only'), (12,1,'Hot'), (10,1,'')],
    [(6,1,''), (5,1,'Tidak pedas'), (10,2,'')],
    [(13,2,''), (11,1,''), (10,2,'')],
    [(3,2,''), (12,1,'')],
    [(4,1,''), (1,1,''), (10,1,'Less ice')],
    [(6,3,'Extra kuah'), (13,2,''), (10,3,'')],
    [(5,2,''), (4,1,'Extra topping'), (11,1,'')],
    [(3,1,''), (1,1,'Fresh only'), (10,2,'')],
    [(6,1,'Extra'), (14,2,''), (13,1,'')],
    [(5,3,''), (10,3,'Less sugar')],
    [(4,2,''), (8,1,''), (10,2,'')],
    [(6,1,''), (3,1,''), (12,1,'')],
    [(5,1,''), (13,1,''), (11,1,''), (10,1,'')],
    [(1,1,''), (3,1,''), (10,2,'')],
    [(4,1,'Tidak pedas'), (6,1,''), (11,2,'')],
    [(14,3,''), (13,2,''), (12,2,'Hot')],
    [(9,1,''), (10,1,''), (12,1,'')],
    [(8,2,''), (11,1,''), (10,2,'')],
    [(2,2,'Spicy level 2'), (4,1,''), (10,2,'')],
    [(9,1,''), (1,1,'Fresh only'), (12,1,'')],
    [(6,1,''), (8,1,''), (13,1,''), (10,2,'')],
]

SLOT_TIMES = [(11, 30), (12, 15), (13, 0), (18, 30), (19, 45)]

def seed_order(table_num, lines, order_dt, seq):
    if table_num not in tables:
        log(f"  Table {table_num} not found, skip")
        return

    order_no = f"ORD/2026/05/{seq:04d}"
    trx_no   = f"TRX/2026/05/{seq:04d}"

    if env['wasabi.order'].search([('order_number', '=', order_no)], limit=1):
        log(f"  SKIP {order_no} (already exists)")
        return

    table = tables[table_num]

    # 1. Buat order dengan status 'ready' — transaction.create() yang akan set 'paid'
    order = env['wasabi.order'].create({
        'order_number': order_no,
        'table_id': table.id,
        'status': 'ready',
        'currency_id': currency.id,
    })

    # 2. Buat order items — ini yang trigger _compute_totals di order
    for mid, qty, note in lines:
        if mid not in items:
            continue
        item = items[mid]
        env['wasabi.order.item'].create({
            'order_id': order.id,
            'menu_item_id': item.id,
            'quantity': qty,
            'unit_price': item.price,
            'subtotal': float(item.price * qty),
            'currency_id': currency.id,
            'order_status': 'paid',
            'note': note,
        })

    # 3. Baca total_price hasil compute (subtotal * 1.15)
    order.invalidate_recordset()
    actual_total = order.total_price
    # Bulatkan received ke atas ke ribuan terdekat
    received = (int(actual_total) // 1000 + 1) * 1000

    # 4. Buat transaction — create() otomatis set order ke 'paid', set transaction_id, bebaskan meja
    trx = env['wasabi.transaction'].create({
        'transaction_number': trx_no,
        'order_id': order.id,
        'order_number': order_no,
        'staff_id': admin.id,
        'currency_id': currency.id,
        'payment_method': 'cash',
        'amount_received': received,
        'paid_at': order_dt,
    })

    # 5. Paksa paid_at ke tanggal historis (create() mungkin set ke now())
    env.cr.execute(
        "UPDATE wasabi_transaction SET paid_at=%s WHERE id=%s",
        (order_dt, trx.id)
    )
    env.cr.execute(
        "UPDATE wasabi_order SET paid_at=%s WHERE id=%s",
        (order_dt, order.id)
    )

    items_str = ', '.join(f"{q}x{items[m].name}" for m,q,_ in lines if m in items)
    log(f"  CREATE {order_no}  Table {table_num:2}  {order_dt.strftime('%Y-%m-%d %H:%M')}  Rp {int(actual_total):>8,}  [{items_str}]")

# ─── Main seed loop ───────────────────────────────────────────────────────────
seq = 1
for day in range(1, 32):
    tables_today = [((day - 1) * 2 + i * 2) % 12 + 1 for i in range(5)]
    log(f"--- May {day:02d} — tables {tables_today} ---")
    for slot, table_num in enumerate(tables_today):
        hour, minute = SLOT_TIMES[slot]
        order_dt = datetime(2026, 5, day, hour, minute, 0)
        combo_idx = (day * 7 + slot * 3) % len(COMBOS)
        seed_order(table_num, COMBOS[combo_idx], order_dt, seq)
        seq += 1

total = env['wasabi.transaction'].search_count([])
may   = env['wasabi.transaction'].search_count([
    ('paid_at', '>=', datetime(2026,5,1)),
    ('paid_at', '<=', datetime(2026,5,31,23,59,59)),
])
log(f"\nTotal wasabi.transaction: {total}")
log(f"May 2026 transactions   : {may}")
log("=== COMMIT ===")
env.cr.commit()
log("=== DONE ===")
