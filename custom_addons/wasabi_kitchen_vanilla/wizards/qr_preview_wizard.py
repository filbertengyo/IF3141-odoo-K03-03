# -*- coding: utf-8 -*-
import base64

from odoo import models, fields
from odoo.tools.image import image_data_uri  # noqa: F401  (kept for parity if needed)


class WasabiQrPreview(models.TransientModel):
    _name = 'wasabi.qr.preview'
    _description = 'Wasabi Kitchen — QR Code Preview Popup'

    table_id = fields.Many2one('wasabi.table', string='Meja', required=True, readonly=True)
    table_number = fields.Integer(related='table_id.table_number', readonly=True)
    floor = fields.Char(related='table_id.floor', readonly=True)
    capacity = fields.Integer(related='table_id.capacity', readonly=True)
    qr_token = fields.Char(related='table_id.qr_token', readonly=True)
    qr_url = fields.Char(related='table_id.qr_url', readonly=True)
    qr_image = fields.Binary(string='QR Code', compute='_compute_qr_image')

    def _compute_qr_image(self):
        for rec in self:
            if not rec.qr_url:
                rec.qr_image = False
                continue
            png = self.env['ir.actions.report'].barcode(
                barcode_type='QR',
                value=rec.qr_url,
                width=400,
                height=400,
            )
            rec.qr_image = base64.b64encode(png)

    def action_print(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/report/barcode/?barcode_type=QR&value={self.qr_url}&width=400&height=400',
            'target': 'new',
        }
