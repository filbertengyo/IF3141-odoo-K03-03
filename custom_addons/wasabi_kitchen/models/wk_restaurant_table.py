from odoo import api, fields, models


class WKRestaurantTable(models.Model):
    _inherit = 'restaurant.table'

    nomor_meja = fields.Integer(
        string='Nomor Meja',
        compute='_compute_nomor_meja',
        store=True,
    )

    @api.depends('name')
    def _compute_nomor_meja(self):
        for rec in self:
            digits = ''.join(filter(str.isdigit, rec.name or ''))
            rec.nomor_meja = int(digits) if digits else 0
