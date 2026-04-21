from odoo import api, fields, models


class WKPosOrder(models.Model):
    _inherit = 'pos.order'

    kds_status = fields.Selection([
        ('pending', 'Pending'),
        ('cooking', 'Cooking'),
        ('ready',   'Ready'),
    ], string='Status KDS', default='pending', index=True)

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
        self.write({'kds_status': 'cooking'})
        return True

    def action_kds_mark_ready(self):
        self.write({'kds_status': 'ready'})
        return True

    def action_open_billing(self):
        config_id = self.session_id.config_id.id if self.session_id else False
        if config_id:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/pos/ui?config_id={config_id}',
                'target': 'new',
            }
        return True
