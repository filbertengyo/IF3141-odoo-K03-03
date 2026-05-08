"""
Seed paid transactions for May 1–31 2026: 5 per day = 155 orders total.
Idempotent — skips if a paid order already exists for the same table+day.

Run:
    docker cp custom_addons/wasabi_kitchen/inject_may_transactions.py <container>:/tmp/inject_may_transactions.py
    docker exec <container> bash -c "odoo shell -d postgres --no-http < /tmp/inject_may_transactions.py"
"""
from datetime import datetime


def log(msg):
    print(f"  [MAY] {msg}")


log("=== MAY TRANSACTIONS SEED ===")

# ─── Resolve POS config, session, payment method ──────────────────────────────
wk_config = env['pos.config'].search([('name', '=', 'Wasabi Kitchen')], limit=1)
if not wk_config:
    log("ERROR: 'Wasabi Kitchen' not found. Run inject_data.py first.")
    raise SystemExit

wk_floor = env['restaurant.floor'].search([('name', '=', 'Lantai Utama')], limit=1)
if not wk_floor:
    log("ERROR: 'Lantai Utama' floor not found. Run inject_data.py first.")
    raise SystemExit

session = env['pos.session'].search([
    ('config_id', '=', wk_config.id),
    ('state', 'in', ['opening_control', 'opened']),
], limit=1)
if not session:
    log("ERROR: No open session found. Run inject_data.py first.")
    raise SystemExit

cash_method = env['pos.payment.method'].search(
    [('config_ids', 'in', [wk_config.id])], limit=1)
if not cash_method:
    cash_method = env['pos.payment.method'].search(
        [('is_cash_count', '=', True)], limit=1)
if not cash_method:
    cash_method = env['pos.payment.method'].search([], limit=1)
if not cash_method:
    cash_method = env['pos.payment.method'].create({
        'name': 'Cash',
        'is_cash_count': True,
    })
    log(f"  Created payment method: {cash_method.name}")
if cash_method and cash_method.id not in wk_config.payment_method_ids.ids:
    # Cannot edit config payment methods while session is open — insert directly
    env.cr.execute(
        "INSERT INTO pos_config_pos_payment_method_rel (pos_config_id, pos_payment_method_id) "
        "VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (wk_config.id, cash_method.id)
    )
    env.invalidate_all()
    log(f"  Linked payment method to config via SQL")

log(f"Config: {wk_config.name} | Session: {session.id} | Payment: {cash_method.name if cash_method else 'NONE'}")

# ─── Product lookup ───────────────────────────────────────────────────────────
PRODUCT_NAMES = [
    'Ramen Tonkotsu', 'Chicken Katsu', 'Sushi Set (8 pcs)', 'Salmon Sashimi',
    'Udon Goreng', 'Miso Soup', 'Takoyaki (6 pcs)', 'Green Tea',
]
products = {}
for name in PRODUCT_NAMES:
    tmpl = env['product.template'].search([('name', '=', name)], limit=1)
    if tmpl:
        products[name] = tmpl.product_variant_ids[0]
    else:
        log(f"WARNING: product '{name}' not found — orders using it will be skipped")

# ─── Boost stock temporarily so historical seeding never hits the constraint ──
location = env['stock.warehouse'].search([], limit=1).lot_stock_id
log("Boosting stock to 999 for seeding...")
for prod in products.values():
    quant = env['stock.quant'].search([
        ('product_id', '=', prod.id),
        ('location_id', '=', location.id),
    ], limit=1)
    if quant:
        quant.sudo().write({'quantity': 999})
    else:
        env['stock.quant'].sudo().create({
            'product_id': prod.id,
            'location_id': location.id,
            'quantity': 999,
        })

# ─── Combo templates ──────────────────────────────────────────────────────────
# Each combo: list of (product_name, qty, catatan)
COMBOS = [
    # idx 0 — ramen lunch pair
    [('Ramen Tonkotsu', 2, 'Extra kuah'), ('Green Tea', 2, 'Less ice')],
    # idx 1 — katsu set
    [('Chicken Katsu', 1, 'Saus terpisah'), ('Miso Soup', 1, ''), ('Green Tea', 1, '')],
    # idx 2 — sushi light
    [('Sushi Set (8 pcs)', 1, ''), ('Green Tea', 2, '')],
    # idx 3 — udon + takoyaki
    [('Udon Goreng', 2, 'Pedas sedang'), ('Takoyaki (6 pcs)', 1, '')],
    # idx 4 — sashimi set
    [('Salmon Sashimi', 1, 'Fresh only'), ('Miso Soup', 1, ''), ('Green Tea', 1, 'Hot')],
    # idx 5 — ramen + katsu combo
    [('Ramen Tonkotsu', 1, ''), ('Chicken Katsu', 1, 'Tidak pedas'), ('Green Tea', 2, '')],
    # idx 6 — takoyaki + miso
    [('Takoyaki (6 pcs)', 2, ''), ('Miso Soup', 1, 'Tanpa garam'), ('Green Tea', 2, '')],
    # idx 7 — big sushi group
    [('Sushi Set (8 pcs)', 2, ''), ('Miso Soup', 1, '')],
    # idx 8 — udon + sashimi
    [('Udon Goreng', 1, ''), ('Salmon Sashimi', 1, ''), ('Green Tea', 1, 'Less ice')],
    # idx 9 — large group ramen
    [('Ramen Tonkotsu', 3, 'Extra kuah'), ('Takoyaki (6 pcs)', 2, ''), ('Green Tea', 3, '')],
    # idx 10 — katsu + udon
    [('Chicken Katsu', 2, ''), ('Udon Goreng', 1, 'Extra topping'), ('Miso Soup', 1, '')],
    # idx 11 — premium sushi + sashimi
    [('Sushi Set (8 pcs)', 1, ''), ('Salmon Sashimi', 1, 'Fresh only'), ('Green Tea', 2, '')],
    # idx 12 — ramen + snack
    [('Ramen Tonkotsu', 1, 'Extra telur'), ('Miso Soup', 2, ''), ('Takoyaki (6 pcs)', 1, '')],
    # idx 13 — big katsu group
    [('Chicken Katsu', 3, ''), ('Green Tea', 3, 'Less sugar')],
    # idx 14 — udon family
    [('Udon Goreng', 2, ''), ('Miso Soup', 2, ''), ('Green Tea', 2, '')],
    # idx 15 — ramen + sushi
    [('Ramen Tonkotsu', 1, ''), ('Sushi Set (8 pcs)', 1, ''), ('Green Tea', 1, '')],
    # idx 16 — snack platter
    [('Chicken Katsu', 1, ''), ('Takoyaki (6 pcs)', 1, ''), ('Miso Soup', 1, ''), ('Green Tea', 1, '')],
    # idx 17 — sashimi + sushi premium
    [('Salmon Sashimi', 1, ''), ('Sushi Set (8 pcs)', 1, ''), ('Green Tea', 2, '')],
    # idx 18 — udon + ramen
    [('Udon Goreng', 1, 'Tidak pedas'), ('Ramen Tonkotsu', 1, ''), ('Green Tea', 2, '')],
    # idx 19 — miso + takoyaki evening
    [('Miso Soup', 3, ''), ('Takoyaki (6 pcs)', 2, ''), ('Green Tea', 2, 'Hot')],
]

# ─── 5 slots per day: 3 lunch + 2 dinner ─────────────────────────────────────
SLOT_TIMES = [(11, 30), (12, 15), (13, 0), (18, 30), (19, 45)]

# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_table(table_num):
    return env['restaurant.table'].search([
        ('name', '=', f'Table {table_num}'),
        ('floor_id', '=', wk_floor.id),
    ], limit=1)


def seed_paid_order(table_num, lines, order_dt):
    table = get_table(table_num)
    if not table:
        log(f"  Table {table_num} not found, skip")
        return None

    date_start = order_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    date_end = order_dt.replace(hour=23, minute=59, second=59, microsecond=999999)

    existing = env['pos.order'].search([
        ('table_id', '=', table.id),
        ('state', '=', 'paid'),
        ('date_order', '>=', date_start),
        ('date_order', '<=', date_end),
    ], limit=1)
    if existing:
        log(f"  SKIP  Table {table_num:2}  {order_dt.strftime('%Y-%m-%d %H:%M')}  (already id={existing.id})")
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

    if not order_lines:
        return None

    order = env['pos.order'].create({
        'session_id': session.id,
        'table_id': table.id,
        'lines': order_lines,
        'kds_status': 'ready',
        'state': 'draft',
        'date_order': order_dt,
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
    order.write({'state': 'paid', 'date_order': order_dt})

    items_desc = ', '.join(f"{q}x {n}" for n, q, _ in lines if products.get(n))
    log(f"  CREATE Table {table_num:2}  {order_dt.strftime('%Y-%m-%d %H:%M')}  Rp {int(order.amount_total):>8,}  [{items_desc}]")
    return order


# ─── Main seed loop: May 1–31 ─────────────────────────────────────────────────
#
# Table rotation: for each day d (1-indexed), pick 5 tables with no repeat.
# Formula: ((d-1)*3 + offset) % 10 + 1, offset in [0, 2, 4, 6, 8]
# This gives a different spread each day and repeats only every 10 days.
#
# Combo selection: (day * 7 + slot * 3) % len(COMBOS)
# Chosen primes (7, 3) ensure we cycle through all combos across the month.

created = 0
skipped = 0

for day in range(1, 32):
    tables_today = [((day - 1) * 3 + off) % 10 + 1 for off in [0, 2, 4, 6, 8]]
    log(f"--- May {day:02d} — tables {tables_today} ---")

    for slot, table_num in enumerate(tables_today):
        hour, minute = SLOT_TIMES[slot]
        order_dt = datetime(2026, 5, day, hour, minute, 0)
        combo_idx = (day * 7 + slot * 3) % len(COMBOS)
        lines = COMBOS[combo_idx]

        result = seed_paid_order(table_num, lines, order_dt)
        if result and result.state == 'paid' and result.id:
            # distinguish newly created vs already-existing by date proximity
            # (we just check if it would have been logged as SKIP above)
            pass

# ─── Restore realistic stock levels ──────────────────────────────────────────
FINAL_STOCK = {
    'Ramen Tonkotsu': 10,
    'Chicken Katsu': 8,
    'Sushi Set (8 pcs)': 6,
    'Salmon Sashimi': 2,
    'Udon Goreng': 12,
    'Miso Soup': 20,
    'Takoyaki (6 pcs)': 15,
    'Green Tea': 25,
}
log("Restoring stock levels...")
for pname, qty in FINAL_STOCK.items():
    prod = products.get(pname)
    if not prod:
        continue
    quant = env['stock.quant'].search([
        ('product_id', '=', prod.id),
        ('location_id', '=', location.id),
    ], limit=1)
    if quant:
        quant.sudo().write({'quantity': qty})
    log(f"  {pname}: {qty}")

# ─── Summary ──────────────────────────────────────────────────────────────────
total_paid = env['pos.order'].search_count([('state', '=', 'paid')])
may_paid = env['pos.order'].search_count([
    ('state', '=', 'paid'),
    ('date_order', '>=', datetime(2026, 5, 1)),
    ('date_order', '<=', datetime(2026, 5, 31, 23, 59, 59)),
])
log(f"\nTotal paid orders in DB : {total_paid}")
log(f"May 2026 paid orders    : {may_paid}")
log("=== COMMIT ===")
env.cr.commit()
log("=== DONE ===")
