from odoo import api, fields, models
from odoo.exceptions import ValidationError


class WKPosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    catatan = fields.Char(string='Catatan')

    @api.constrains('qty', 'product_id')
    def _check_stock_availability(self):
        for line in self:
            product = line.product_id.sudo()
            if not product or product.type not in ('consu', 'product'):
                continue
            pending_qty = sum(
                self.env['pos.order.line'].sudo().search([
                    ('product_id', '=', line.product_id.id),
                    ('order_id.state', '=', 'draft'),
                    ('id', '!=', line.id),
                ]).mapped('qty')
            )
            available = product.qty_available - pending_qty
            if line.qty > available:
                raise ValidationError(
                    f'Stok "{product.name}" tidak mencukupi.\n'
                    f'Tersedia: {int(product.qty_available)}, '
                    f'Sudah dipesan: {int(pending_qty)}, '
                    f'Sisa efektif: {int(available)}, '
                    f'Dipesan sekarang: {int(line.qty)}.'
                )
