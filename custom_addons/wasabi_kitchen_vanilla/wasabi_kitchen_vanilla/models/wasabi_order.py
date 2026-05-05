# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WasabiOrder(models.Model):
    _name = 'wasabi.order'
    _description = 'Wasabi Kitchen — Pesanan'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'order_number'

    order_number = fields.Char(
        string='Nomor Order',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Baru'),
    )
    table_id = fields.Many2one(
        'wasabi.table',
        string='Meja',
        required=True,
        tracking=True,
    )
    table_number = fields.Integer(
        string='No. Meja',
        related='table_id.table_number',
        store=True,
    )

    status = fields.Selection(
        [
            ('pending',   'Pending'),
            ('cooking',   'Cooking'),
            ('ready',     'Ready'),
            ('paid',      'Paid'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='pending',
        tracking=True,
        required=True,
    )

    # Timestamps untuk SLA & analitik
    create_date = fields.Datetime(string='Diterima', readonly=True)
    cooking_at  = fields.Datetime(string='Mulai Dimasak')
    ready_at    = fields.Datetime(string='Siap Diantar')
    paid_at     = fields.Datetime(string='Dibayar')

    # Items
    order_item_ids = fields.One2many(
        'wasabi.order.item',
        'order_id',
        string='Item Pesanan',
    )
    item_count = fields.Integer(
        string='Jumlah Item',
        compute='_compute_totals',
        store=True,
    )
    total_qty = fields.Integer(
        string='Total Qty',
        compute='_compute_totals',
        store=True,
    )

    # Pricing — tax-inclusive flow
    subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    pb1 = fields.Monetary(
        string='PB1 (10%)',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Pajak Pembangunan 1 — 10% dari subtotal (regulasi pajak daerah).',
    )
    service_charge = fields.Monetary(
        string='Service (5%)',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    total_price = fields.Monetary(
        string='Total Bayar',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.ref('base.IDR'),
        required=True,
    )

    notes = fields.Text(string='Catatan Pesanan')

    transaction_id = fields.Many2one(
        'wasabi.transaction',
        string='Transaksi',
        readonly=True,
    )

    # Display computeds for KDS
    elapsed_minutes = fields.Float(
        string='Elapsed (menit)',
        compute='_compute_elapsed_minutes',
        help='Waktu sejak pesanan masuk — untuk warning SLA di KDS.',
    )
    urgency = fields.Selection(
        [('normal','Normal'),('warn','Hampir Telat'),('late','Terlambat')],
        string='Urgensi',
        compute='_compute_elapsed_minutes',
    )

    PB1_RATE     = 0.10
    SERVICE_RATE = 0.05

    @api.depends('order_item_ids', 'order_item_ids.subtotal')
    def _compute_totals(self):
        for order in self:
            subtotal = sum(order.order_item_ids.mapped('subtotal'))
            order.subtotal       = subtotal
            order.pb1            = subtotal * order.PB1_RATE
            order.service_charge = subtotal * order.SERVICE_RATE
            order.total_price    = subtotal + order.pb1 + order.service_charge
            order.item_count     = len(order.order_item_ids)
            order.total_qty      = sum(order.order_item_ids.mapped('quantity'))

    @api.depends('create_date', 'status')
    def _compute_elapsed_minutes(self):
        from datetime import datetime
        now = fields.Datetime.now()
        for order in self:
            if order.create_date and order.status in ('pending', 'cooking'):
                delta = (now - order.create_date).total_seconds() / 60.0
                order.elapsed_minutes = round(delta, 1)
                if delta > 8:
                    order.urgency = 'late'
                elif delta > 5:
                    order.urgency = 'warn'
                else:
                    order.urgency = 'normal'
            else:
                order.elapsed_minutes = 0
                order.urgency = 'normal'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('order_number', _('Baru')) == _('Baru'):
                vals['order_number'] = self.env['ir.sequence'].next_by_code(
                    'wasabi.order'
                ) or _('Baru')
        orders = super().create(vals_list)
        # Set meja menjadi occupied
        for order in orders:
            if order.table_id.status == 'available':
                order.table_id.status = 'occupied'
        return orders

    # ----- State workflow -----

    def action_confirm(self):
        """Konfirmasi order: validasi & decrement stok atomik (FR-02).

        Race condition handling: gunakan SELECT FOR UPDATE pada menu items.
        """
        for order in self:
            if order.status != 'pending':
                raise UserError(_('Hanya pesanan PENDING yang bisa dikonfirmasi.'))
            if not order.order_item_ids:
                raise UserError(_('Pesanan kosong, tidak bisa dikonfirmasi.'))

            # Lock rows — Odoo akan menggunakan transaction RR isolation
            menu_ids = order.order_item_ids.mapped('menu_item_id').ids
            self.env.cr.execute(
                "SELECT id FROM wasabi_menu_item WHERE id IN %s FOR UPDATE",
                (tuple(menu_ids),),
            )

            # Validasi & decrement
            for line in order.order_item_ids:
                line.menu_item_id.auto_decrement_stock(
                    line.quantity, order_id=order.id
                )

            order.message_post(body=_('Pesanan dikonfirmasi & stok di-decrement.'))
        return True

    def action_start_cooking(self):
        """Koki klik 'Mulai Masak' (UC-07 part 1)."""
        for order in self:
            if order.status != 'pending':
                raise UserError(_('Hanya order PENDING yang bisa dimulai memasak.'))
            order.write({
                'status':     'cooking',
                'cooking_at': fields.Datetime.now(),
            })
            order.message_post(body=_('Mulai dimasak oleh %s') % self.env.user.name)
        return True

    def action_mark_ready(self):
        """Koki tandai READY (UC-07 part 2)."""
        for order in self:
            if order.status != 'cooking':
                raise UserError(_('Hanya order COOKING yang bisa ditandai READY.'))
            order.write({
                'status':   'ready',
                'ready_at': fields.Datetime.now(),
            })
            order.message_post(body=_('Pesanan siap diantarkan.'))
        return True

    def action_open_billing(self):
        """Buka halaman billing untuk kasir (UC-09)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Billing — %s') % self.order_number,
            'res_model': 'wasabi.order',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id':   self.env.ref('wasabi_kitchen_vanilla.view_wasabi_order_billing_form').id,
            'target': 'new',
        }

    def action_cancel(self):
        for order in self:
            if order.status == 'paid':
                raise UserError(_('Pesanan yang sudah dibayar tidak bisa dibatalkan.'))
            # Kembalikan stok (rollback)
            for line in order.order_item_ids:
                if not line.menu_item_id.is_unlimited:
                    line.menu_item_id.manual_correct_stock(
                        line.menu_item_id.remaining_stock + line.quantity,
                        note=_('Rollback stok dari pembatalan order %s') % order.order_number,
                    )
            order.status = 'cancelled'
            if order.table_id.active_order_id == order:
                order.table_id.status = 'available'
        return True

    def action_print_bill(self):
        return self.env.ref('wasabi_kitchen_vanilla.action_report_billing').report_action(self)
