# -*- coding: utf-8 -*-
"""
Post-install hook — seed dataset demo lengkap.

Dipanggil otomatis sekali saat module di-install (lihat __manifest__.py).
Idempotent — kalau order_number sudah ada di DB, skip.

Yang di-seed:
  • 2-3 user kasir baru (selain admin)
  • Stock correction log (manual koreksi koki)
  • Variasi status meja (available / occupied / reserved)
  • ~600+ orders covering 60 hari terakhir
      - Weekend lebih ramai
      - Mix paid / cancelled (historis)
      - Hari ini: mix pending/cooking/ready dengan VARIASI URGENCY
        (baru / hampir telat / late) supaya warna KDS keliatan semua
  • Combos: kecil (1 item) sampai mega (6+ item), repeat-heavy, dll
  • Coverage semua menu item minimal sekali

Re-trigger manual:
    docker compose exec web odoo shell -d postgres --no-http
    >>> from odoo.addons.wasabi_kitchen_vanilla.hooks import seed_demo_dataset
    >>> seed_demo_dataset(env)
"""
import logging
import random
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


def seed_demo_dataset(env):
    try:
        _do_seed(env)
    except Exception as e:
        _logger.warning("Wasabi Kitchen demo seed FAILED: %s", e, exc_info=True)


def _set_home_action(env, user, action_xmlid, menu_xmlid):
    """Set home action via URL so menu_id is included — activates the navbar on login."""
    action = env.ref(action_xmlid, raise_if_not_found=False)
    menu   = env.ref(menu_xmlid,   raise_if_not_found=False)
    if not (action and menu and user):
        return
    url = f'/web#action={action.id}&menu_id={menu.id}'
    existing = env['ir.actions.act_url'].search(
        [('name', '=', f'__wk_home_{user.login}')], limit=1)
    if existing:
        existing.url = url
        user.action_id = existing.id
    else:
        act = env['ir.actions.act_url'].create({
            'name': f'__wk_home_{user.login}',
            'url': url,
            'target': 'self',
        })
        user.action_id = act.id


def _do_seed(env):
    random.seed(20260511)
    _logger.info("=== WASABI KITCHEN VANILLA — DEMO SEED START ===")

    TODAY = datetime(2026, 5, 11)
    START = TODAY - timedelta(days=60)
    _logger.info("Seed range: %s → %s (60 days)", START.date(), TODAY.date())

    # ── 0. Lookup base data ──────────────────────────────────────────────
    tables = {t.table_number: t for t in env['wasabi.table'].search([])}
    if not tables:
        _logger.warning("No tables — abort.")
        return
    table_nums = sorted(tables.keys())

    items = {i.id: i for i in env['wasabi.menu.item'].search([])
             if (i.remaining_stock or 0) != 0}
    if not items:
        _logger.warning("No menu items — abort.")
        return

    currency = env['res.currency'].with_context(active_test=False).search(
        [('name', '=', 'IDR')], limit=1)
    if not currency:
        currency = env['wasabi.menu.item'].search([], limit=1).currency_id

    admin = env['res.users'].search([('login', '=', 'admin')], limit=1) or env.user

    # ── 1. Bikin role users (koki / kasir) ───────────────────────────────
    koki_group  = env.ref('wasabi_kitchen_vanilla.group_wasabi_koki',  raise_if_not_found=False)
    kasir_group = env.ref('wasabi_kitchen_vanilla.group_wasabi_kasir', raise_if_not_found=False)
    base_user   = env.ref('base.group_user', raise_if_not_found=False)

    admin_group   = env.ref('wasabi_kitchen_vanilla.group_wasabi_admin',   raise_if_not_found=False)
    manager_group = env.ref('wasabi_kitchen_vanilla.group_wasabi_manager', raise_if_not_found=False)

    # (login, display_name, group, action_xmlid, menu_xmlid)
    ROLE_PROFILES = [
        ('koki',    'Koki',    koki_group,    'wasabi_kitchen_vanilla.action_wasabi_kds',                  'wasabi_kitchen_vanilla.menu_wasabi_root_koki'),
        ('kasir',   'Kasir',   kasir_group,   'wasabi_kitchen_vanilla.action_wasabi_billing',              'wasabi_kitchen_vanilla.menu_wasabi_root_kasir'),
        ('manager', 'Manager', manager_group, 'wasabi_kitchen_vanilla.action_wasabi_transaction_analytics','wasabi_kitchen_vanilla.menu_wasabi_root_manager'),
    ]
    kasir_users = [admin]
    for login, name, group, action_xml, menu_xml in ROLE_PROFILES:
        existing = env['res.users'].search([('login', '=', login)], limit=1)
        if existing:
            if login == 'kasir':
                kasir_users.append(existing)
            _set_home_action(env, existing, action_xml, menu_xml)
            continue
        try:
            groups = []
            if base_user:
                groups.append((4, base_user.id))
            if group:
                groups.append((4, group.id))
            user = env['res.users'].create({
                'login':     login,
                'name':      name,
                'password':  login,
                'groups_id': groups,
            })
            if login == 'kasir':
                kasir_users.append(user)
            _set_home_action(env, user, action_xml, menu_xml)
            _logger.info("Created user: %s (group: %s)", login, group.name if group else 'none')
        except Exception as e:
            _logger.warning("Skip create user %s: %s", login, e)

    # Admin: assign group_wasabi_admin + set home → dashboard
    if admin_group and admin_group not in admin.groups_id:
        admin.groups_id = [(4, admin_group.id)]
    _set_home_action(env, admin,
                     'wasabi_kitchen_vanilla.action_wasabi_dashboard_open',
                     'wasabi_kitchen_vanilla.menu_wasabi_root')

    # ── 2. Variasi status meja (untuk floor plan) ────────────────────────
    # Total meja diasumsikan 12. Set 2 jadi 'reserved'.
    reserved_nums = random.sample(table_nums, min(2, len(table_nums)))
    for tn in reserved_nums:
        tables[tn].status = 'reserved'
    _logger.info("Tables set RESERVED: %s", reserved_nums)

    # ── 3. Combo templates: variety pack ─────────────────────────────────
    item_ids_avail = list(items.keys())

    COMBOS_RAW = [
        # Solo orders
        [(6, 1, 'Solo dinner')],
        [(5, 1, '')],
        [(9, 1, 'Take away')],
        [(1, 1, 'Fresh only — penting')],
        # Medium (2-3 item) — paling umum
        [(6, 2, ''), (10, 2, 'Less ice')],
        [(5, 1, 'Saus terpisah'), (10, 1, ''), (11, 1, '')],
        [(3, 1, ''), (10, 2, '')],
        [(4, 2, 'Pedas sedang'), (13, 1, '')],
        [(1, 1, 'Fresh only'), (12, 1, 'Hot'), (10, 1, '')],
        [(6, 1, ''), (5, 1, 'Tidak pedas'), (10, 2, '')],
        [(13, 2, ''), (11, 1, ''), (10, 2, '')],
        [(3, 2, ''), (12, 1, '')],
        [(4, 1, ''), (1, 1, ''), (10, 1, 'Less ice')],
        [(5, 2, ''), (4, 1, 'Extra topping'), (11, 1, '')],
        [(3, 1, ''), (1, 1, 'Fresh only'), (10, 2, '')],
        [(6, 1, 'Extra'), (14, 2, ''), (13, 1, '')],
        [(4, 2, ''), (8, 1, ''), (10, 2, '')],
        [(6, 1, ''), (3, 1, ''), (12, 1, '')],
        [(9, 1, ''), (10, 1, ''), (12, 1, '')],
        [(8, 2, ''), (11, 1, ''), (10, 2, '')],
        [(2, 2, 'Spicy level 2'), (4, 1, ''), (10, 2, '')],
        [(9, 1, ''), (1, 1, 'Fresh only'), (12, 1, '')],
        # Big (4-5 item) — meja besar / family
        [(6, 3, 'Extra kuah'), (13, 2, ''), (10, 3, '')],
        [(5, 1, ''), (13, 1, ''), (11, 1, ''), (10, 1, '')],
        [(1, 1, ''), (3, 1, ''), (10, 2, '')],
        [(4, 1, 'Tidak pedas'), (6, 1, ''), (11, 2, '')],
        [(14, 3, ''), (13, 2, ''), (12, 2, 'Hot')],
        [(6, 1, ''), (8, 1, ''), (13, 1, ''), (10, 2, '')],
        # Mega orders (6+ item) — rombongan
        [(6, 2, ''), (5, 2, ''), (4, 2, ''), (10, 4, 'Less ice'), (13, 3, '')],
        [(8, 3, ''), (9, 2, ''), (12, 3, 'Hot'), (14, 3, ''), (13, 2, '')],
        [(1, 2, 'Fresh'), (2, 2, ''), (3, 2, ''), (4, 2, 'Spicy'), (10, 6, '')],
        # Repeat-heavy (uji kapasitas qty)
        [(10, 8, 'Group order')],
        [(13, 6, 'Birthday')],
        [(6, 5, '')],
    ]
    COMBOS = [c for c in COMBOS_RAW if all(mid in items for mid, _, _ in c)]
    _logger.info("Usable combos: %d", len(COMBOS))

    NOTE_VARIETY = ['', '', '', '', 'Bungkus rapi', 'Pakai sendok plastik',
                    'Tanpa wasabi', 'Extra sumpit', 'Untuk acara ultah',
                    'Bareng kado', '']  # banyak '' biar mayoritas tanpa note

    # ── 4. Stock corrections (log koreksi koki) ──────────────────────────
    correction_reasons = [
        'Stok awal hari',
        'Restock dari supplier',
        'Cek opname akhir shift',
        'Kerusakan bahan baku',
        'Salah hitung kemarin',
    ]
    correction_count = 0
    for _ in range(15):
        item = random.choice(list(items.values()))
        new_stock = random.choice([
            item.remaining_stock + random.randint(5, 20),  # restock
            max(0, item.remaining_stock - random.randint(1, 3)),  # opname turun
        ])
        try:
            item.manual_correct_stock(new_stock, note=random.choice(correction_reasons))
            correction_count += 1
        except Exception:
            pass
    _logger.info("Stock corrections created: %d", correction_count)

    # ── 5. Seed function ─────────────────────────────────────────────────
    def rand_time(day, hour_lo, hour_hi):
        return day.replace(hour=random.randint(hour_lo, hour_hi),
                           minute=random.choice([0, 15, 30, 45]),
                           second=random.randint(0, 59))

    def seed_one(tnum, lines, order_dt, seq, status, method, kasir, order_note=''):
        yyyymm = order_dt.strftime('%Y/%m')
        order_no = f"ORD/{yyyymm}/{seq:04d}"
        trx_no = f"TRX/{yyyymm}/{seq:04d}"

        if env['wasabi.order'].search([('order_number', '=', order_no)], limit=1):
            return False

        table = tables[tnum]
        stage_initial = 'ready' if status in ('paid', 'cancelled') else status

        order = env['wasabi.order'].create({
            'order_number': order_no,
            'table_id': table.id,
            'status': stage_initial,
            'currency_id': currency.id,
            'notes': order_note or False,
        })

        for mid, qty, note in lines:
            if mid not in items:
                continue
            it = items[mid]
            env['wasabi.order.item'].create({
                'order_id': order.id,
                'menu_item_id': it.id,
                'quantity': qty,
                'unit_price': it.price,
                'subtotal': float(it.price * qty),
                'currency_id': currency.id,
                'note': note,
            })

        order.invalidate_recordset()
        total = order.total_price

        if status == 'paid':
            received = (int(total) // 1000 + 1) * 1000 if method == 'cash' else int(total)
            trx = env['wasabi.transaction'].create({
                'transaction_number': trx_no,
                'order_id': order.id,
                'order_number': order_no,
                'staff_id': kasir.id,
                'currency_id': currency.id,
                'payment_method': method,
                'amount_received': received if method == 'cash' else 0,
                'paid_at': order_dt,
            })
            env.cr.execute("UPDATE wasabi_transaction SET paid_at=%s WHERE id=%s",
                           (order_dt, trx.id))
            env.cr.execute("UPDATE wasabi_order SET paid_at=%s, create_date=%s WHERE id=%s",
                           (order_dt, order_dt, order.id))
        elif status == 'cancelled':
            env.cr.execute("UPDATE wasabi_order SET status='cancelled', create_date=%s WHERE id=%s",
                           (order_dt, order.id))
            table.status = 'available'
        else:
            env.cr.execute("UPDATE wasabi_order SET create_date=%s WHERE id=%s",
                           (order_dt, order.id))
            if status in ('pending', 'cooking'):
                table.status = 'occupied'
        return True

    # ── 6. Main loop ─────────────────────────────────────────────────────
    seq = 1
    total_seeded = 0
    day = START
    while day <= TODAY:
        is_today = day.date() == TODAY.date()
        weekend = day.weekday() >= 5

        if is_today:
            n_paid     = random.randint(5, 9)
            # Urgency variety untuk hari ini:
            n_pending_fresh = 1   # baru masuk (2-5 menit)
            n_pending_warn  = 1   # hampir telat (8-12 menit)
            n_cooking_fresh = 1
            n_cooking_warn  = 1
            n_cooking_late  = 1   # late (18+ menit)
            n_ready_fresh   = 2
            n_ready_old     = 1   # ready lama (>30 menit, harus diantar!)
            n_cancelled = 0
            n_lunch = n_paid // 2
        else:
            base = random.randint(14, 22) if weekend else random.randint(7, 14)
            n_paid = base
            n_pending_fresh = n_pending_warn = 0
            n_cooking_fresh = n_cooking_warn = n_cooking_late = 0
            n_ready_fresh = n_ready_old = 0
            n_cancelled = 1 if random.random() < 0.12 else 0
            n_lunch = base // 2

        orders_day = []
        for i in range(n_paid):
            t = rand_time(day, 11, 14) if i < n_lunch else rand_time(day, 18, 21)
            orders_day.append(('paid', t, ''))
        for _ in range(n_cancelled):
            orders_day.append(('cancelled', rand_time(day, 18, 21), 'Customer batalkan'))

        if is_today:
            anchor = TODAY.replace(hour=12, minute=30)
            urgency_buckets = [
                # (status, minutes_ago_range, count, optional_note)
                ('pending', (2, 5),    n_pending_fresh, 'Order baru via QR'),
                ('pending', (8, 12),   n_pending_warn,  'Customer udah nunggu'),
                ('cooking', (3, 8),    n_cooking_fresh, ''),
                ('cooking', (10, 16),  n_cooking_warn,  'Extra portion'),
                ('cooking', (20, 28),  n_cooking_late,  'KOMPLAIN — udah lama!'),
                ('ready',   (5, 14),   n_ready_fresh,   ''),
                ('ready',   (32, 45),  n_ready_old,     'Belum diantar 30+ menit'),
            ]
            for status, (lo, hi), count, note in urgency_buckets:
                for _ in range(count):
                    t = anchor - timedelta(minutes=random.randint(lo, hi))
                    orders_day.append((status, t, note))

        orders_day.sort(key=lambda x: x[1])

        used_tables = set()
        for status, order_dt, note in orders_day:
            # Untuk status aktif hari ini, pastikan beda meja
            if is_today and status in ('pending', 'cooking', 'ready'):
                avail = [t for t in table_nums
                         if t not in used_tables and t not in reserved_nums]
                if not avail:
                    continue
                tnum = random.choice(avail)
                used_tables.add(tnum)
            else:
                tnum = random.choice(table_nums)

            combo = random.choice(COMBOS)
            method = 'cash' if random.random() < 0.58 else 'qris'
            kasir = random.choice(kasir_users)
            final_note = note or random.choice(NOTE_VARIETY)

            if seed_one(tnum, combo, order_dt, seq, status, method, kasir, final_note):
                seq += 1
                total_seeded += 1

        day += timedelta(days=1)

    env.cr.commit()

    # ── 7. Summary ───────────────────────────────────────────────────────
    _logger.info("=== SEED SUMMARY ===")
    _logger.info("  Orders created     : %d", total_seeded)
    _logger.info("  Total orders DB    : %d", env['wasabi.order'].search_count([]))
    _logger.info("  Total transaksi DB : %d", env['wasabi.transaction'].search_count([]))
    for s in ['pending', 'cooking', 'ready', 'paid', 'cancelled']:
        cnt = env['wasabi.order'].search_count([('status', '=', s)])
        _logger.info("  status=%-10s : %d", s, cnt)
    _logger.info("  Stock log entries  : %d",
                 env['wasabi.stock.log'].search_count([]))
    _logger.info("  Kasir users        : %d", len(kasir_users))
    _logger.info("=== DONE ===")
