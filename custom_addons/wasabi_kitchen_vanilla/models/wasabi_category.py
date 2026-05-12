# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class WasabiCategory(models.Model):
    _name = 'wasabi.category'
    _description = 'Wasabi Kitchen — Kategori Menu'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Nama Kategori', required=True, translate=True)
    sequence = fields.Integer(string='Urutan', default=10)
    description = fields.Text(string='Deskripsi')
    icon = fields.Char(
        string='Icon (Emoji)',
        help='Emoji atau karakter pendek sebagai ikon kategori. Contoh: 🍣, 🍜, 🍱',
        default='🍽️',
    )
    color = fields.Integer(string='Warna Kanban', default=0)
    is_active = fields.Boolean(string='Aktif', default=True)

    menu_item_ids = fields.One2many(
        'wasabi.menu.item',
        'category_id',
        string='Daftar Menu',
    )
    menu_item_count = fields.Integer(
        string='Jumlah Menu',
        compute='_compute_menu_item_count',
        store=True,
    )

    _sql_constraints = [
        ('unique_name', 'unique(name)', 'Nama kategori harus unik!'),
    ]

    @api.depends('menu_item_ids')
    def _compute_menu_item_count(self):
        for rec in self:
            rec.menu_item_count = len(rec.menu_item_ids)

    def unlink(self):
        for rec in self:
            if rec.menu_item_ids:
                raise UserError(
                    f'Kategori "{rec.name}" masih memiliki {len(rec.menu_item_ids)} item menu. '
                    f'Hapus atau pindahkan item menu terlebih dahulu sebelum menghapus kategori.'
                )
        return super().unlink()

    def action_view_menu_items(self):
        self.ensure_one()
        all_cat = self.env.ref(
            'wasabi_kitchen_vanilla.category_all', raise_if_not_found=False
        )
        is_all = all_cat and self.id == all_cat.id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Menu & Stok' if is_all else f'Menu — {self.name}',
            'res_model': 'wasabi.menu.item',
            'view_mode': 'kanban,tree,form',
            'domain': [] if is_all else [('category_id', '=', self.id)],
            'context': {} if is_all else {'default_category_id': self.id},
        }
