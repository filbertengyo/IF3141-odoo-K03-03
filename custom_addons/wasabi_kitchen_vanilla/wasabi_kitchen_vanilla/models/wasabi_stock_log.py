# -*- coding: utf-8 -*-
from odoo import models, fields, api


class WasabiStockLog(models.Model):
    _name = 'wasabi.stock.log'
    _description = 'Wasabi Kitchen — Log Perubahan Stok (Audit Trail)'
    _order = 'create_date desc'
    _rec_name = 'menu_item_id'

    menu_item_id = fields.Many2one(
        'wasabi.menu.item',
        string='Menu',
        required=True,
        ondelete='cascade',
    )
    staff_id = fields.Many2one(
        'res.users',
        string='Staff',
        help='Pengguna yang melakukan perubahan. Kosong jika auto-decrement sistem.',
    )
    order_id = fields.Many2one(
        'wasabi.order',
        string='Order Pemicu',
        ondelete='set null',
        help='Order yang memicu auto-decrement (jika ada).',
    )

    before_qty = fields.Integer(string='Stok Sebelum', required=True)
    after_qty  = fields.Integer(string='Stok Sesudah', required=True)
    delta      = fields.Integer(
        string='Delta',
        required=True,
        help='Negatif = pengurangan, positif = penambahan.',
    )
    delta_label = fields.Char(
        string='Perubahan',
        compute='_compute_delta_label',
    )

    reason = fields.Selection(
        [
            ('auto_decrement',    'Auto Decrement (Order)'),
            ('manual_correction', 'Koreksi Manual (Koki)'),
            ('initial_setup',     'Setup Awal'),
            ('rollback',          'Rollback (Pembatalan)'),
            ('replenishment',     'Restock / Replenish'),
        ],
        string='Alasan',
        required=True,
    )
    note = fields.Char(string='Catatan')

    create_date = fields.Datetime(string='Waktu', readonly=True)
    category_name = fields.Char(
        related='menu_item_id.category_id.name',
        string='Kategori',
        store=True,
    )

    @api.depends('delta')
    def _compute_delta_label(self):
        for log in self:
            if log.delta > 0:
                log.delta_label = f'+{log.delta}'
            else:
                log.delta_label = str(log.delta)
