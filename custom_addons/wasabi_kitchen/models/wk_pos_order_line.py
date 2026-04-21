from odoo import api, fields, models
from odoo.exceptions import ValidationError


class WKPosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    catatan = fields.Char(string='Catatan')

    @api.constrains('qty', 'product_id')
    def _check_stock_availability(self):
        for line in self:
            # sudo() diperlukan: qty_available query stock.move
            # yang tidak accessible oleh POS user biasa
            product = line.product_id.sudo()
            if not product or product.type not in ('consu', 'product'):
                continue
            if product.qty_available >= 0 and line.qty > product.qty_available:
                raise ValidationError(
                    f'Stok "{product.name}" tidak mencukupi.\n'
                    f'Tersedia: {int(product.qty_available)}, '
                    f'Dipesan: {int(line.qty)}.'
                )
