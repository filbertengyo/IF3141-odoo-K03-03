# -*- coding: utf-8 -*-
from odoo import models, fields, api


class WasabiOrderItem(models.Model):
    _name = 'wasabi.order.item'
    _description = 'Wasabi Kitchen — Detail Item Pesanan'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)

    order_id = fields.Many2one(
        'wasabi.order',
        string='Pesanan',
        required=True,
        ondelete='cascade',
    )
    menu_item_id = fields.Many2one(
        'wasabi.menu.item',
        string='Menu',
        required=True,
        ondelete='restrict',
    )

    name = fields.Char(string='Nama', related='menu_item_id.name', readonly=True)
    category_name = fields.Char(
        string='Kategori',
        related='menu_item_id.category_id.name',
        readonly=True,
    )

    quantity = fields.Integer(string='Qty', required=True, default=1)
    unit_price = fields.Monetary(
        string='Harga Satuan',
        required=True,
        currency_field='currency_id',
        help='Snapshot harga saat order dibuat — agar perubahan harga ke depan tidak mengubah riwayat.',
    )
    subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True,
        currency_field='currency_id',
    )
    note = fields.Char(
        string='Catatan',
        help='Catatan dari pelanggan untuk koki. Contoh: "tanpa wasabi", "level pedas 3".',
    )
    currency_id = fields.Many2one(
        related='order_id.currency_id',
        store=True,
    )

    order_status = fields.Selection(
        related='order_id.status',
        store=True,
        string='Status Order',
    )

    _sql_constraints = [
        ('positive_qty', 'CHECK(quantity > 0)', 'Quantity harus lebih dari 0.'),
    ]

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price

    @api.onchange('menu_item_id')
    def _onchange_menu_item_id(self):
        if self.menu_item_id:
            self.unit_price = self.menu_item_id.price
