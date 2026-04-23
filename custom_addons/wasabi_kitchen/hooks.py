import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Dijalankan otomatis sekali saat module pertama kali di-install."""
    _logger.info("=== Wasabi Kitchen: post_init_hook START ===")

    # ── 1. POS Config ────────────────────────────────────────────────────────
    wk_config = env.ref('wasabi_kitchen.wk_pos_config', raise_if_not_found=False)
    if not wk_config:
        wk_config = env['pos.config'].create({
            'name': 'Wasabi Kitchen',
            'iface_orderline_notes': True,
        })
        _logger.info("Created POS config id=%s", wk_config.id)

    # ── 2. Floor & Tables ────────────────────────────────────────────────────
    wk_floor = env.ref('wasabi_kitchen.wk_floor_main', raise_if_not_found=False)
    if not wk_floor:
        wk_floor = env['restaurant.floor'].create({
            'name': 'Lantai Utama',
            'pos_config_ids': [(4, wk_config.id)],
        })
    elif wk_config not in wk_floor.pos_config_ids:
        wk_floor.pos_config_ids = [(4, wk_config.id)]

    for i in range(1, 11):
        tname = f'Table {i}'
        if not env['restaurant.table'].search([('name', '=', tname), ('floor_id', '=', wk_floor.id)], limit=1):
            env['restaurant.table'].create({
                'name': tname, 'floor_id': wk_floor.id,
                'seats': 4, 'shape': 'square',
            })

    valid_names = {f'Table {i}' for i in range(1, 11)}
    orphan_tables = env['restaurant.table'].search([
        ('floor_id', '=', wk_floor.id),
        ('name', 'not in', list(valid_names)),
    ])
    for t in orphan_tables:
        try:
            t.unlink()
        except Exception as e:
            _logger.warning("Cannot delete orphan table '%s': %s", t.name, e)
    _logger.info("Tables ready on floor '%s'", wk_floor.name)

    # ── 3. POS Categories ────────────────────────────────────────────────────
    def get_or_create_cat(name):
        cat = env['pos.category'].search([('name', '=', name)], limit=1)
        return cat or env['pos.category'].create({'name': name})

    cat_makanan = get_or_create_cat('Makanan Utama')
    cat_snack   = get_or_create_cat('Snack & Appetizer')
    cat_minuman = get_or_create_cat('Minuman')

    # ── 4. Produk Menu + Stok ────────────────────────────────────────────────
    menu_data = [
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
                'name': name, 'list_price': price,
                'available_in_pos': True, 'type': 'product',
                'pos_categ_ids': [(4, cat.id)],
            })
        else:
            tmpl.write({'available_in_pos': True, 'list_price': price,
                        'pos_categ_ids': [(4, cat.id)]})
        product = tmpl.product_variant_ids[0]
        products[name] = product
        quant = env['stock.quant'].search([
            ('product_id', '=', product.id), ('location_id', '=', location.id)
        ], limit=1)
        if quant:
            quant.sudo().write({'quantity': stock_qty})
        else:
            env['stock.quant'].sudo().create({
                'product_id': product.id, 'location_id': location.id,
                'quantity': stock_qty,
            })
    _logger.info("Created %d menu products", len(products))

    # ── 5. POS Session ───────────────────────────────────────────────────────
    session = env['pos.session'].search([
        ('config_id', '=', wk_config.id),
        ('state', 'in', ['opening_control', 'opened']),
    ], limit=1)
    if not session:
        session = env['pos.session'].create({'config_id': wk_config.id})
        session.action_pos_session_open()
        _logger.info("Opened POS session id=%s", session.id)

    # ── 6. Draft Orders (KDS demo) ───────────────────────────────────────────
    def get_table(name):
        return env['restaurant.table'].search(
            [('name', '=', name), ('floor_id', '=', wk_floor.id)], limit=1)

    def make_order(table_name, kds_status, lines):
        table = get_table(table_name)
        if not table:
            return
        if env['pos.order'].search([('table_id', '=', table.id), ('state', '=', 'draft')], limit=1):
            return
        order_lines = []
        for pname, qty, note in lines:
            prod = products.get(pname)
            if not prod:
                continue
            subtotal = prod.list_price * qty
            order_lines.append((0, 0, {
                'product_id': prod.id, 'qty': qty,
                'price_unit': prod.list_price,
                'price_subtotal': subtotal, 'price_subtotal_incl': subtotal,
                'discount': 0.0, 'catatan': note,
            }))
        order = env['pos.order'].create({
            'session_id': session.id, 'table_id': table.id,
            'lines': order_lines, 'kds_status': kds_status, 'state': 'draft',
            'amount_tax': 0.0, 'amount_total': 0.0,
            'amount_paid': 0.0, 'amount_return': 0.0,
            'pricelist_id': wk_config.pricelist_id.id,
            'currency_id': wk_config.currency_id.id,
        })
        order._compute_batch_amount_all()

    make_order('Table 1', 'pending', [('Ramen Tonkotsu', 2, 'Extra kuah'), ('Green Tea', 2, '')])
    make_order('Table 3', 'pending', [('Sushi Set (8 pcs)', 1, ''), ('Miso Soup', 2, 'Tanpa garam'), ('Green Tea', 1, '')])
    make_order('Table 5', 'cooking', [('Chicken Katsu', 1, 'Saus terpisah'), ('Udon Goreng', 1, 'Level pedas medium'), ('Green Tea', 2, '')])
    make_order('Table 7', 'cooking', [('Takoyaki (6 pcs)', 2, ''), ('Salmon Sashimi', 1, 'Fresh only')])
    make_order('Table 9', 'ready',   [('Ramen Tonkotsu', 1, ''), ('Miso Soup', 1, '')])
    make_order('Table 10', 'ready',  [('Udon Goreng', 2, 'Extra topping'), ('Green Tea', 3, 'Less ice')])
    _logger.info("Draft orders created")

    # ── 7. Paid Orders (riwayat) ─────────────────────────────────────────────
    cash_method = env['pos.payment.method'].search(
        [('config_ids', 'in', [wk_config.id])], limit=1)
    if not cash_method:
        cash_method = env['pos.payment.method'].search(
            [('is_cash_count', '=', True)], limit=1)
        if not cash_method:
            cash_method = env['pos.payment.method'].search([], limit=1)
        if cash_method:
            wk_config.payment_method_ids = [(4, cash_method.id)]

    def make_paid_order(table_name, lines, days_ago):
        table = get_table(table_name)
        if not table or not cash_method:
            return
        order_date = datetime.now() - timedelta(days=days_ago, hours=2)
        date_start = order_date.replace(hour=0, minute=0, second=0)
        date_end   = order_date.replace(hour=23, minute=59, second=59)
        existing = env['pos.order'].search([
            ('table_id', '=', table.id),
            ('state', '=', 'paid'),
            ('date_order', '>=', date_start),
            ('date_order', '<=', date_end),
        ], limit=1)
        if existing:
            _logger.info("Paid order at %s (%dd ago) already exists, skip", table_name, days_ago)
            return existing
        order_lines = []
        total = 0
        for pname, qty, note in lines:
            prod = products.get(pname)
            if not prod:
                continue
            subtotal = prod.list_price * qty
            total += subtotal
            order_lines.append((0, 0, {
                'product_id': prod.id, 'qty': qty,
                'price_unit': prod.list_price,
                'price_subtotal': subtotal, 'price_subtotal_incl': subtotal,
                'discount': 0.0, 'catatan': note,
            }))
        order = env['pos.order'].create({
            'session_id': session.id, 'table_id': table.id,
            'lines': order_lines, 'kds_status': 'ready', 'state': 'draft',
            'date_order': order_date,
            'amount_tax': 0.0, 'amount_total': 0.0,
            'amount_paid': 0.0, 'amount_return': 0.0,
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

    make_paid_order('Table 2', [('Sushi Set (8 pcs)', 2, ''), ('Green Tea', 2, '')], 0)
    make_paid_order('Table 4', [('Ramen Tonkotsu', 1, ''), ('Takoyaki (6 pcs)', 1, '')], 0)
    make_paid_order('Table 6', [('Chicken Katsu', 2, ''), ('Miso Soup', 2, ''), ('Green Tea', 3, '')], 1)
    make_paid_order('Table 8', [('Salmon Sashimi', 1, ''), ('Udon Goreng', 1, '')], 1)
    make_paid_order('Table 2', [('Ramen Tonkotsu', 3, ''), ('Green Tea', 3, '')], 2)
    make_paid_order('Table 4', [('Sushi Set (8 pcs)', 1, ''), ('Miso Soup', 3, '')], 2)
    _logger.info("Paid orders created")

    _logger.info("=== Wasabi Kitchen: post_init_hook DONE ===")
