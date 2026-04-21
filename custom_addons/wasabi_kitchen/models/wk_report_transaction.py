import base64
import csv
import io

from odoo import api, fields, models
from odoo.exceptions import UserError


class WKReportTransaction(models.TransientModel):
    _name = 'wk.report.transaction'
    _description = 'Laporan Transaksi Wasabi Kitchen'

    date_start = fields.Date(string='Dari Tanggal', required=True,
                             default=fields.Date.today)
    date_end = fields.Date(string='Sampai Tanggal', required=True,
                           default=fields.Date.today)
    order_ids = fields.Many2many('pos.order', string='Transaksi', readonly=True)
    total_orders = fields.Integer(string='Jumlah Order', readonly=True)
    total_revenue = fields.Float(string='Total Pendapatan', readonly=True)
    has_result = fields.Boolean(default=False)

    def action_query(self):
        if self.date_end < self.date_start:
            raise UserError('Tanggal selesai tidak boleh sebelum tanggal mulai.')
        orders = self.env['pos.order'].search([
            ('date_order', '>=', str(self.date_start) + ' 00:00:00'),
            ('date_order', '<=', str(self.date_end) + ' 23:59:59'),
            ('state', 'in', ['paid', 'done', 'invoiced']),
        ])
        self.write({
            'order_ids': [(6, 0, orders.ids)],
            'total_orders': len(orders),
            'total_revenue': sum(orders.mapped('amount_total')),
            'has_result': True,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wk.report.transaction',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_export_csv(self):
        if not self.has_result:
            raise UserError('Klik "Tampilkan Data" terlebih dahulu.')
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'No. Transaksi', 'No. Meja', 'Total (Rp)',
            'Metode Bayar', 'Kasir', 'Waktu',
        ])
        for order in self.order_ids:
            metode = (order.payment_ids[0].payment_method_id.name
                      if order.payment_ids else '-')
            writer.writerow([
                order.name,
                order.no_meja or (order.table_id.name if order.table_id else '-'),
                int(order.amount_total),
                metode,
                order.user_id.name if order.user_id else '-',
                order.date_order.strftime('%Y-%m-%d %H:%M') if order.date_order else '-',
            ])
        csv_b64 = base64.b64encode(output.getvalue().encode('utf-8')).decode()
        fname = f'laporan_wasabi_{self.date_start}_{self.date_end}.csv'
        att = self.env['ir.attachment'].create({
            'name': fname, 'type': 'binary',
            'datas': csv_b64, 'mimetype': 'text/csv',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{att.id}?download=true',
            'target': 'new',
        }
