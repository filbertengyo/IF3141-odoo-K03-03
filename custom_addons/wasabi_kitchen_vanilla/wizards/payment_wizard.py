# -*- coding: utf-8 -*-
import base64
from io import BytesIO

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class WasabiPaymentWizard(models.TransientModel):
    _name = 'wasabi.payment.wizard'
    _description = 'Wasabi Kitchen — Wizard Konfirmasi Pembayaran'

    order_id = fields.Many2one(
        'wasabi.order',
        string='Pesanan',
        required=True,
        default=lambda self: self.env.context.get('default_order_id') or self.env.context.get('active_id'),
    )
    order_number = fields.Char(related='order_id.order_number', readonly=True)
    table_number = fields.Integer(related='order_id.table_number', readonly=True)
    item_count   = fields.Integer(related='order_id.item_count', readonly=True)
    total_amount = fields.Monetary(
        related='order_id.total_price',
        currency_field='currency_id',
        readonly=True,
    )
    currency_id = fields.Many2one(related='order_id.currency_id')

    payment_method = fields.Selection(
        [('cash', '💵 Tunai'), ('qris', '📱 QRIS')],
        string='Metode',
        default='cash',
        required=True,
    )
    amount_received = fields.Monetary(
        string='Jumlah Diterima',
        currency_field='currency_id',
    )
    change_amount = fields.Monetary(
        string='Kembalian',
        compute='_compute_change',
        currency_field='currency_id',
    )
    notes = fields.Text(string='Catatan')

    qris_qr_image = fields.Binary(
        string='QR Code QRIS',
        compute='_compute_qris_qr',
    )

    @api.depends('total_amount', 'order_id')
    def _compute_qris_qr(self):
        try:
            import qrcode  # noqa: PLC0415
        except ImportError:
            for rec in self:
                rec.qris_qr_image = False
            return
        for rec in self:
            amount_int = int(rec.total_amount or 0)
            amount_str = str(amount_int)
            # Mock QRIS EMVCo string — merchant ID placeholder, real format
            qris_payload = (
                "00020101021226600014ID.CO.QRIS.WWW"
                "011893600009150001234500"
                "021500000000000000001"
                "0303UBE"
                "52044812"
                "5303360"
                f"54{len(amount_str):02d}{amount_str}"
                "5802ID"
                "5914Wasabi Kitchen"
                "6015Jatinangor IDN"
                f"62{len(rec.order_id.order_number or '') + 4:02d}"
                f"0508{rec.order_id.order_number or 'DEMO'}"
            )
            try:
                qr = qrcode.QRCode(
                    version=None,
                    error_correction=qrcode.constants.ERROR_CORRECT_M,
                    box_size=8,
                    border=3,
                )
                qr.add_data(qris_payload)
                qr.make(fit=True)
                img = qr.make_image(fill_color='#1f1d24', back_color='white')
                buf = BytesIO()
                img.save(buf, format='PNG')
                rec.qris_qr_image = base64.b64encode(buf.getvalue())
            except Exception:
                rec.qris_qr_image = False

    @api.depends('amount_received', 'total_amount', 'payment_method')
    def _compute_change(self):
        for rec in self:
            if rec.payment_method == 'cash' and rec.amount_received:
                rec.change_amount = max(0, rec.amount_received - rec.total_amount)
            else:
                rec.change_amount = 0

    @api.onchange('payment_method', 'total_amount')
    def _onchange_method(self):
        # Auto-fill QRIS dengan jumlah pas
        if self.payment_method == 'qris':
            self.amount_received = self.total_amount

    # ----- Quick amount buttons -----

    def set_quick_50k(self):
        self.ensure_one()
        self.amount_received = 50000
        return self._return_self()

    def set_quick_100k(self):
        self.ensure_one()
        self.amount_received = 100000
        return self._return_self()

    def set_quick_200k(self):
        self.ensure_one()
        self.amount_received = 200000
        return self._return_self()

    def set_quick_exact(self):
        self.ensure_one()
        self.amount_received = self.total_amount
        return self._return_self()

    def _return_self(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id':    self.id,
            'view_mode': 'form',
            'target':    'new',
        }

    # ----- Confirm payment -----

    def action_confirm_payment(self):
        self.ensure_one()
        order = self.order_id

        if order.status != 'ready':
            raise UserError(_(
                'Hanya pesanan dengan status READY yang bisa dibayarkan. '
                'Status saat ini: %s'
            ) % order.status)

        if self.payment_method == 'cash':
            if not self.amount_received or self.amount_received < self.total_amount:
                raise ValidationError(_(
                    'Jumlah uang yang diterima (Rp %s) kurang dari total tagihan (Rp %s).'
                ) % (self.amount_received or 0, self.total_amount))

        # Buat transaksi (akan trigger update order ke PAID + free meja)
        transaction = self.env['wasabi.transaction'].create({
            'order_id':        order.id,
            'staff_id':        self.env.user.id,
            'payment_method':  self.payment_method,
            'amount_received': self.amount_received if self.payment_method == 'cash' else self.total_amount,
            'paid_at':         fields.Datetime.now(),
            'notes':           self.notes,
        })

        return {
            'type': 'ir.actions.client',
            'tag':  'display_notification',
            'params': {
                'title':   _('✓ Pembayaran berhasil'),
                'message': _('Transaksi %s · Rp %s · Meja %s') % (
                    transaction.transaction_number,
                    self.total_amount,
                    self.table_number,
                ),
                'type':     'success',
                'sticky':   False,
                'next':     {'type': 'ir.actions.act_window_close'},
            },
        }
