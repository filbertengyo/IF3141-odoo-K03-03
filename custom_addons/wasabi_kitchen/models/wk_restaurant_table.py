from odoo import models, fields, api


class WKRestaurantTable(models.Model):
    _inherit = 'restaurant.table'

    nomor_meja = fields.Integer(
        string='Nomor Meja',
        compute='_compute_nomor_meja',
        store=True,
    )

    active_orders_count = fields.Integer(
        string='Order Aktif',
        compute='_compute_active_orders',
    )

    @api.depends('name')
    def _compute_nomor_meja(self):
        for rec in self:
            digits = ''.join(filter(str.isdigit, rec.name or ''))
            rec.nomor_meja = int(digits) if digits else 0

    @api.depends('pos_order_ids.state')
    def _compute_active_orders(self):
        for rec in self:
            rec.active_orders_count = self.env['pos.order'].search_count([
                ('table_id', '=', rec.id),
                ('state', '=', 'draft'),
            ])

    def action_open_qr_info(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'restaurant.table',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
