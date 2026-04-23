from odoo import api, fields, models
from odoo.exceptions import UserError


class WkOrderWizard(models.TransientModel):
    _name = 'wk.order.wizard'
    _description = 'Buat Pesanan Baru'

    table_id = fields.Many2one(
        'restaurant.table', string='Meja', required=True)
    line_ids = fields.One2many(
        'wk.order.wizard.line', 'wizard_id', string='Item Pesanan')
    amount_total = fields.Float(
        string='Total (Rp)', compute='_compute_total')

    @api.depends('line_ids.subtotal')
    def _compute_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('subtotal'))

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError('Tambahkan minimal satu item pesanan.')

        config = self.env['pos.config'].search(
            [('name', '=', 'Wasabi Kitchen')], limit=1)
        if not config:
            config = self.env['pos.config'].search([], limit=1)
        if not config:
            raise UserError('POS Config tidak ditemukan.')

        session = self.env['pos.session'].search([
            ('config_id', '=', config.id),
            ('state', 'in', ['opening_control', 'opened']),
        ], limit=1)
        if not session:
            raise UserError(
                'Tidak ada sesi POS aktif. Minta kasir membuka sesi terlebih dahulu.')

        order_lines = []
        for line in self.line_ids:
            product = line.product_id.product_variant_ids[:1]
            if not product:
                continue
            subtotal = line.price_unit * line.qty
            order_lines.append((0, 0, {
                'product_id': product.id,
                'qty': line.qty,
                'price_unit': line.price_unit,
                'price_subtotal': subtotal,
                'price_subtotal_incl': subtotal,
                'discount': 0.0,
                'catatan': line.catatan or '',
            }))

        order = self.env['pos.order'].create({
            'session_id': session.id,
            'table_id': self.table_id.id,
            'lines': order_lines,
            'kds_status': 'pending',
            'state': 'draft',
            'amount_tax': 0.0,
            'amount_total': 0.0,
            'amount_paid': 0.0,
            'amount_return': 0.0,
            'pricelist_id': config.pricelist_id.id,
            'currency_id': config.currency_id.id,
        })
        order._compute_batch_amount_all()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Pesanan Dibuat',
                'message': (
                    f'Pesanan untuk {self.table_id.name} berhasil dibuat '
                    f'(Rp {int(order.amount_total):,}).'
                ),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class WkOrderWizardLine(models.TransientModel):
    _name = 'wk.order.wizard.line'
    _description = 'Item Pesanan Baru'

    wizard_id = fields.Many2one('wk.order.wizard', ondelete='cascade')
    product_id = fields.Many2one(
        'product.template', string='Menu',
        domain=[('available_in_pos', '=', True)],
        required=True)
    qty = fields.Float(string='Jumlah', default=1.0)
    price_unit = fields.Float(
        string='Harga (Rp)', compute='_compute_price', store=True, readonly=False)
    catatan = fields.Char(string='Catatan')
    subtotal = fields.Float(
        string='Subtotal (Rp)', compute='_compute_subtotal', store=True)

    @api.depends('product_id')
    def _compute_price(self):
        for line in self:
            line.price_unit = line.product_id.list_price if line.product_id else 0.0

    @api.depends('qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.qty * line.price_unit
