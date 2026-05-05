# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class WasabiMenuItem(models.Model):
    _name = 'wasabi.menu.item'
    _description = 'Wasabi Kitchen — Item Menu'
    _order = 'category_id, sequence, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nama Menu', required=True, tracking=True)
    sku = fields.Char(string='SKU', required=True, copy=False, tracking=True)
    sequence = fields.Integer(string='Urutan', default=10)
    description = fields.Text(string='Deskripsi', translate=True)

    category_id = fields.Many2one(
        'wasabi.category',
        string='Kategori',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    category_icon = fields.Char(
        string='Icon Kategori',
        related='category_id.icon',
        readonly=True,
    )

    price = fields.Monetary(
        string='Harga',
        required=True,
        tracking=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.ref('base.IDR'),
        required=True,
    )

    remaining_stock = fields.Integer(
        string='Sisa Stok',
        default=0,
        tracking=True,
        help='Jumlah stok tersisa. Set -1 untuk unlimited (cocok untuk minuman seperti ocha).',
    )
    is_unlimited = fields.Boolean(
        string='Stok Unlimited',
        compute='_compute_is_unlimited',
        store=True,
        help='True jika stok tidak dibatasi (remaining_stock = -1)',
    )
    is_available = fields.Boolean(
        string='Tersedia',
        default=True,
        tracking=True,
        help='Toggle ketersediaan menu. Otomatis false jika stok = 0.',
    )
    low_stock_threshold = fields.Integer(
        string='Batas Stok Rendah',
        default=5,
        help='Stok di bawah angka ini akan ditandai sebagai stok rendah.',
    )
    stock_status = fields.Selection(
        [
            ('out',       'Habis'),
            ('low',       'Stok Rendah'),
            ('available', 'Tersedia'),
            ('unlimited', 'Unlimited'),
        ],
        string='Status Stok',
        compute='_compute_stock_status',
        store=True,
    )

    photo = fields.Binary(string='Foto Menu', attachment=True)
    photo_color = fields.Selection(
        [
            ('peach',  'Peach (Salmon)'),
            ('green',  'Green (Sushi)'),
            ('dark',   'Dark (Roll)'),
            ('tea',    'Tea (Minuman)'),
            ('broth',  'Broth (Ramen)'),
            ('cream',  'Cream (Dessert)'),
        ],
        string='Warna Placeholder',
        default='cream',
        help='Warna placeholder jika foto belum diupload.',
    )
    glyph = fields.Char(
        string='Kanji Glyph',
        size=2,
        help='Karakter kanji 1-2 huruf sebagai dekorasi (鮭, 寿, 麺, dll)',
    )

    order_item_ids = fields.One2many(
        'wasabi.order.item',
        'menu_item_id',
        string='Riwayat Pesanan',
    )
    stock_log_ids = fields.One2many(
        'wasabi.stock.log',
        'menu_item_id',
        string='Log Perubahan Stok',
    )

    sold_count = fields.Integer(
        string='Total Terjual',
        compute='_compute_sold_count',
    )

    _sql_constraints = [
        ('unique_sku', 'unique(sku)', 'SKU harus unik!'),
        ('positive_price', 'CHECK(price >= 0)', 'Harga tidak boleh negatif.'),
    ]

    @api.depends('remaining_stock')
    def _compute_is_unlimited(self):
        for rec in self:
            rec.is_unlimited = rec.remaining_stock < 0

    @api.depends('remaining_stock', 'is_available', 'low_stock_threshold')
    def _compute_stock_status(self):
        for rec in self:
            if rec.remaining_stock < 0:
                rec.stock_status = 'unlimited'
            elif rec.remaining_stock == 0:
                rec.stock_status = 'out'
            elif rec.remaining_stock <= rec.low_stock_threshold:
                rec.stock_status = 'low'
            else:
                rec.stock_status = 'available'

    @api.depends('order_item_ids.order_id.status')
    def _compute_sold_count(self):
        for rec in self:
            rec.sold_count = sum(rec.order_item_ids.filtered(
                lambda i: i.order_id.status == 'paid'
            ).mapped('quantity'))

    # ----- Business Logic -----

    def action_toggle_availability(self):
        for rec in self:
            rec.is_available = not rec.is_available

    def action_view_stock_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Log Stok — {self.name}',
            'res_model': 'wasabi.stock.log',
            'view_mode': 'tree,form',
            'domain': [('menu_item_id', '=', self.id)],
        }

    def auto_decrement_stock(self, quantity, order_id=None):
        """Dipanggil saat order dikonfirmasi. Mengurangi stok atomik.

        :param quantity: jumlah yang dipesan
        :param order_id: id order yang memicu (untuk audit)
        :raises UserError: jika stok tidak mencukupi
        :returns: True jika berhasil
        """
        self.ensure_one()
        if self.is_unlimited:
            return True
        if self.remaining_stock < quantity:
            raise UserError(_(
                'Stok %s tidak mencukupi! Tersisa %s, dipesan %s.'
            ) % (self.name, self.remaining_stock, quantity))

        before = self.remaining_stock
        new_stock = before - quantity
        self.write({
            'remaining_stock': new_stock,
            'is_available': new_stock > 0,
        })
        self.env['wasabi.stock.log'].create({
            'menu_item_id':  self.id,
            'before_qty':    before,
            'after_qty':     new_stock,
            'delta':         -quantity,
            'reason':        'auto_decrement',
            'order_id':      order_id,
            'note':          _('Auto-decrement dari order #%s') % (order_id or '-'),
        })
        return True

    def manual_correct_stock(self, new_stock, note=None):
        """Koreksi manual oleh koki. Mencatat StockLog dan auto-toggle availability."""
        self.ensure_one()
        before = self.remaining_stock
        delta = new_stock - before

        self.write({
            'remaining_stock': new_stock,
            'is_available':    new_stock != 0,
        })
        self.env['wasabi.stock.log'].create({
            'menu_item_id':  self.id,
            'staff_id':      self.env.user.id,
            'before_qty':    before,
            'after_qty':     new_stock,
            'delta':         delta,
            'reason':        'manual_correction',
            'note':          note or _('Koreksi manual oleh %s') % self.env.user.name,
        })
        return True
