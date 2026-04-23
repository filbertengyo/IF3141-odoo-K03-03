from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class WKBillingWizard(models.TransientModel):
    """
    Wizard Billing — diakses dari:
    - Kasir -> Buka Billing       (UC-10)
    - Kasir -> Konfirmasi Pembayaran (UC-07)
    """
    _name = 'wk.billing.wizard'
    _description = 'Billing & Konfirmasi Pembayaran Wasabi Kitchen'

    order_id = fields.Many2one(
        'pos.order', string='Pesanan', required=True, readonly=True)
    table_name = fields.Char(string='Meja', readonly=True)
    amount_total = fields.Float(string='Total Tagihan', readonly=True)
    payment_method = fields.Selection([
        ('cash', 'Tunai'),
        ('qris', 'QRIS'),
    ], string='Metode Pembayaran', required=True, default='cash')
    amount_paid = fields.Float(string='Jumlah Dibayar')
    change_amount = fields.Float(
        string='Kembalian', compute='_compute_change', readonly=True)
    order_line_ids = fields.Many2many(
        'pos.order.line', string='Detail Pesanan',
        compute='_compute_lines', readonly=True)
    kds_status = fields.Selection(
        related='order_id.kds_status', string='Status KDS', readonly=True)
    state = fields.Selection([
        ('draft', 'Belum Dibayar'),
        ('confirmed', 'Lunas'),
    ], default='draft', readonly=True)

    @api.depends('order_id')
    def _compute_lines(self):
        for rec in self:
            rec.order_line_ids = rec.order_id.lines if rec.order_id else self.env['pos.order.line']

    @api.depends('amount_paid', 'amount_total')
    def _compute_change(self):
        for rec in self:
            rec.change_amount = (rec.amount_paid or 0.0) - (rec.amount_total or 0.0)

    @api.onchange('order_id')
    def _onchange_order(self):
        if self.order_id:
            self.table_name = self.order_id.table_id.name if self.order_id.table_id else ''
            self.amount_total = self.order_id.amount_total

    def action_confirm_payment(self):
        self.ensure_one()
        if not self.payment_method:
            raise UserError('Pilih metode pembayaran terlebih dahulu.')
        if self.payment_method == 'cash' and self.amount_paid < self.amount_total:
            raise ValidationError(
                f'Jumlah bayar (Rp {int(self.amount_paid):,}) '
                f'kurang dari total tagihan (Rp {int(self.amount_total):,}).'
            )
        self.order_id.write({'kds_status': 'ready'})
        self.write({'state': 'confirmed'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wk.billing.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
