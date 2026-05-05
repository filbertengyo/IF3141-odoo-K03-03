# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class WasabiTransaction(models.Model):
    _name = 'wasabi.transaction'
    _description = 'Wasabi Kitchen — Transaksi Pembayaran'
    _order = 'paid_at desc'
    _inherit = ['mail.thread']
    _rec_name = 'transaction_number'

    transaction_number = fields.Char(
        string='Nomor Transaksi',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Baru'),
    )
    order_id = fields.Many2one(
        'wasabi.order',
        string='Pesanan',
        required=True,
        ondelete='restrict',
    )
    order_number = fields.Char(
        related='order_id.order_number',
        store=True,
        string='No. Order',
    )
    table_number = fields.Integer(
        related='order_id.table_number',
        store=True,
        string='No. Meja',
    )

    staff_id = fields.Many2one(
        'res.users',
        string='Kasir',
        required=True,
        default=lambda self: self.env.user,
        domain=[('share', '=', False)],
        tracking=True,
    )

    payment_method = fields.Selection(
        [
            ('cash', 'Tunai'),
            ('qris', 'QRIS'),
        ],
        string='Metode Pembayaran',
        required=True,
        tracking=True,
    )

    total_amount = fields.Monetary(
        string='Total Tagihan',
        related='order_id.total_price',
        store=True,
        currency_field='currency_id',
    )
    amount_received = fields.Monetary(
        string='Jumlah Diterima',
        currency_field='currency_id',
        help='Jumlah uang yang diterima dari pelanggan (untuk metode CASH).',
    )
    change_amount = fields.Monetary(
        string='Kembalian',
        compute='_compute_change_amount',
        store=True,
        currency_field='currency_id',
    )

    paid_at = fields.Datetime(
        string='Tanggal Bayar',
        default=fields.Datetime.now,
        required=True,
    )
    notes = fields.Text(string='Catatan')

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.ref('base.IDR'),
        required=True,
    )

    _sql_constraints = [
        ('unique_order', 'unique(order_id)', 'Satu order hanya bisa punya satu transaksi.'),
        ('unique_trx_num', 'unique(transaction_number)', 'Nomor transaksi harus unik.'),
    ]

    @api.depends('amount_received', 'total_amount', 'payment_method')
    def _compute_change_amount(self):
        for trx in self:
            if trx.payment_method == 'cash' and trx.amount_received:
                trx.change_amount = max(0, trx.amount_received - trx.total_amount)
            else:
                trx.change_amount = 0

    @api.constrains('amount_received', 'payment_method', 'total_amount')
    def _check_amount_received(self):
        for trx in self:
            if trx.payment_method == 'cash':
                if not trx.amount_received or trx.amount_received < trx.total_amount:
                    raise ValidationError(_(
                        'Jumlah diterima (Rp %s) kurang dari total tagihan (Rp %s).'
                    ) % (trx.amount_received or 0, trx.total_amount))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('transaction_number', _('Baru')) == _('Baru'):
                vals['transaction_number'] = self.env['ir.sequence'].next_by_code(
                    'wasabi.transaction'
                ) or _('Baru')
        transactions = super().create(vals_list)
        # Update order status & free table
        for trx in transactions:
            order = trx.order_id
            if order.status != 'ready':
                raise UserError(_(
                    'Hanya pesanan dengan status READY yang bisa dibayarkan. '
                    'Status saat ini: %s'
                ) % order.status)
            order.write({
                'status':         'paid',
                'paid_at':        trx.paid_at,
                'transaction_id': trx.id,
            })
            # Bebaskan meja
            if order.table_id:
                order.table_id.status = 'available'
            order.message_post(body=_(
                'Pembayaran %s diterima — Rp %s via %s'
            ) % (trx.transaction_number, trx.total_amount, dict(trx._fields['payment_method'].selection)[trx.payment_method]))
        return transactions

    def action_print_receipt(self):
        return self.env.ref('wasabi_kitchen_vanilla.action_report_billing').report_action(self.order_id)
