from odoo import models, fields, api


class WKPosOrder(models.Model):
    _inherit = 'pos.order'

    kds_status = fields.Selection([
        ('pending', 'Pending'),
        ('cooking', 'Cooking'),
        ('ready',   'Ready'),
    ], string='Status KDS', default='pending', index=True, copy=False)

    no_meja = fields.Integer(
        string='No. Meja',
        compute='_compute_no_meja',
        store=True,
    )

    @api.depends('table_id', 'table_id.name')
    def _compute_no_meja(self):
        for rec in self:
            if rec.table_id and rec.table_id.name:
                digits = ''.join(filter(str.isdigit, rec.table_id.name))
                rec.no_meja = int(digits) if digits else 0
            else:
                rec.no_meja = 0

    def action_kds_mark_cooking(self):
        for rec in self:
            rec.kds_status = 'cooking'
        return True

    def action_kds_mark_ready(self):
        for rec in self:
            rec.kds_status = 'ready'
        return True

    def action_open_billing(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Billing — {self.table_id.name or self.name}',
            'res_model': 'wk.billing.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_table_name': self.table_id.name if self.table_id else '',
                'default_amount_total': self.amount_total,
            },
        }
