# -*- coding: utf-8 -*-
import secrets
from odoo import models, fields, api, _


class WasabiTable(models.Model):
    _name = 'wasabi.table'
    _description = 'Wasabi Kitchen — Meja Restoran'
    _order = 'table_number'
    _rec_name = 'display_name'

    table_number = fields.Integer(string='Nomor Meja', required=True, copy=False)
    display_name = fields.Char(
        string='Nama',
        compute='_compute_display_name',
        store=True,
    )
    qr_token = fields.Char(
        string='QR Token',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: secrets.token_urlsafe(16),
        help='Token unik untuk QR code. Sertakan di URL: /wasabi/menu/<token>',
    )
    qr_url = fields.Char(
        string='QR URL',
        compute='_compute_qr_url',
        help='URL lengkap yang di-encode pada QR code di meja.',
    )
    capacity = fields.Integer(string='Kapasitas (Pax)', default=4)
    floor = fields.Char(string='Lantai', default='Lantai 1')
    status = fields.Selection(
        [
            ('available', 'Tersedia'),
            ('occupied',  'Terisi'),
            ('reserved',  'Dipesan'),
        ],
        string='Status',
        default='available',
        tracking=True,
    )
    is_active = fields.Boolean(string='Aktif', default=True)
    notes = fields.Text(string='Catatan')

    order_ids = fields.One2many('wasabi.order', 'table_id', string='Riwayat Pesanan')
    active_order_id = fields.Many2one(
        'wasabi.order',
        string='Pesanan Aktif',
        compute='_compute_active_order',
        help='Order yang sedang berjalan (PENDING / COOKING / READY) di meja ini.',
    )

    _sql_constraints = [
        ('unique_table_number', 'unique(table_number)', 'Nomor meja harus unik!'),
        ('unique_qr_token',     'unique(qr_token)',     'QR token harus unik!'),
    ]

    @api.depends('table_number', 'floor')
    def _compute_display_name(self):
        for rec in self:
            num = str(rec.table_number).zfill(2) if rec.table_number else '?'
            rec.display_name = f'Meja {num} · {rec.floor or ""}'.strip(' ·')

    def _compute_qr_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            rec.qr_url = f'{base_url}/wasabi/menu/{rec.qr_token}' if rec.qr_token else ''

    @api.depends('order_ids', 'order_ids.status')
    def _compute_active_order(self):
        for rec in self:
            active = rec.order_ids.filtered(
                lambda o: o.status in ('pending', 'cooking', 'ready')
            )
            rec.active_order_id = active[:1].id if active else False

    def action_regenerate_qr_token(self):
        """Generate ulang QR token. Token lama akan invalid."""
        for rec in self:
            rec.qr_token = secrets.token_urlsafe(16)
        return True

    def action_view_active_order(self):
        self.ensure_one()
        if not self.active_order_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pesanan Aktif'),
            'res_model': 'wasabi.order',
            'res_id': self.active_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_qr_code(self):
        """Tampilkan QR code di popup modal."""
        self.ensure_one()
        wizard = self.env['wasabi.qr.preview'].create({'table_id': self.id})
        return {
            'type': 'ir.actions.act_window',
            'name': _('QR Code Meja %s') % self.table_number,
            'res_model': 'wasabi.qr.preview',
            'res_id': wizard.id,
            'view_mode': 'form',
            'view_id': self.env.ref('wasabi_kitchen_vanilla.view_wasabi_qr_preview_form').id,
            'target': 'new',
        }
