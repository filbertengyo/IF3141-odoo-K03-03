# -*- coding: utf-8 -*-
import base64
import csv
import io
from odoo import models, fields, api, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class WasabiExportReportWizard(models.TransientModel):
    _name = 'wasabi.export.report.wizard'
    _description = 'Wasabi Kitchen — Wizard Ekspor Laporan Transaksi'

    date_from = fields.Date(
        string='Tanggal Mulai',
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        string='Tanggal Selesai',
        required=True,
        default=fields.Date.context_today,
    )
    payment_method = fields.Selection(
        [
            ('all',  'Semua Metode'),
            ('cash', 'Tunai'),
            ('qris', 'QRIS'),
        ],
        string='Metode Pembayaran',
        default='all',
        required=True,
    )
    staff_id = fields.Many2one(
        'res.users',
        string='Kasir (opsional)',
        domain="[('share', '=', False)]",
    )
    export_format = fields.Selection(
        [('csv', 'CSV'), ('xlsx', 'XLSX (Spreadsheet)')],
        string='Format Ekspor',
        default='xlsx',
        required=True,
    )
    include_items = fields.Boolean(
        string='Sertakan detail item per order',
        default=True,
    )

    # Computed preview
    transaction_count = fields.Integer(
        string='Jumlah Transaksi',
        compute='_compute_preview',
    )
    total_revenue = fields.Monetary(
        string='Total Revenue',
        compute='_compute_preview',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.ref('base.IDR'),
    )

    # Result file
    file_data = fields.Binary(string='File', readonly=True)
    file_name = fields.Char(string='Nama File', readonly=True)

    # ----- Helpers -----

    def _build_domain(self):
        self.ensure_one()
        domain = [
            ('paid_at', '>=', fields.Datetime.to_datetime(self.date_from)),
            ('paid_at', '<=', fields.Datetime.to_datetime(self.date_to).replace(hour=23, minute=59, second=59)),
        ]
        if self.payment_method != 'all':
            domain.append(('payment_method', '=', self.payment_method))
        if self.staff_id:
            domain.append(('staff_id', '=', self.staff_id.id))
        return domain

    @api.depends('date_from', 'date_to', 'payment_method', 'staff_id')
    def _compute_preview(self):
        for rec in self:
            if not (rec.date_from and rec.date_to):
                rec.transaction_count = 0
                rec.total_revenue = 0
                continue
            transactions = self.env['wasabi.transaction'].search(rec._build_domain())
            rec.transaction_count = len(transactions)
            rec.total_revenue = sum(transactions.mapped('total_amount'))

    # ----- Export actions -----

    def action_preview(self):
        """Tampilkan preview data tanpa download (UC-01)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Preview Transaksi'),
            'res_model': 'wasabi.transaction',
            'view_mode': 'tree,form,pivot,graph',
            'domain': self._build_domain(),
            'target': 'current',
        }

    def action_export(self):
        """Generate file CSV/XLSX dan trigger download (UC-02, FR-06)."""
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_('Tanggal mulai harus sebelum tanggal selesai.'))

        transactions = self.env['wasabi.transaction'].search(
            self._build_domain(), order='paid_at asc'
        )
        if not transactions:
            raise UserError(_('Tidak ada transaksi pada rentang tanggal yang dipilih.'))

        if self.export_format == 'csv':
            content, filename = self._generate_csv(transactions)
        else:
            content, filename = self._generate_xlsx(transactions)

        self.write({
            'file_data': base64.b64encode(content),
            'file_name': filename,
        })

        return {
            'type': 'ir.actions.act_url',
            'url':  f'/web/content/?model={self._name}&id={self.id}&field=file_data&filename_field=file_name&download=true',
            'target': 'self',
        }

    def _generate_csv(self, transactions):
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

        headers = [
            'transaksi_id', 'order_id', 'tanggal', 'no_meja',
            'jumlah_item', 'subtotal', 'pb1', 'service_charge',
            'total_harga', 'metode_bayar', 'kasir',
        ]
        if self.include_items:
            headers.append('detail_item')
        writer.writerow(headers)

        for trx in transactions:
            row = [
                trx.transaction_number,
                trx.order_number,
                trx.paid_at and trx.paid_at.strftime('%Y-%m-%d %H:%M:%S') or '',
                trx.table_number,
                trx.order_id.item_count,
                float(trx.order_id.subtotal),
                float(trx.order_id.pb1),
                float(trx.order_id.service_charge),
                float(trx.total_amount),
                dict(trx._fields['payment_method'].selection)[trx.payment_method],
                trx.staff_id.name,
            ]
            if self.include_items:
                items_str = ' | '.join([
                    f'{l.quantity}x {l.name} @ {l.unit_price}'
                    for l in trx.order_id.order_item_ids
                ])
                row.append(items_str)
            writer.writerow(row)

        content = output.getvalue().encode('utf-8-sig')  # BOM untuk Excel
        filename = f'wasabi_transactions_{self.date_from}_{self.date_to}.csv'
        return content, filename

    def _generate_xlsx(self, transactions):
        if xlsxwriter is None:
            raise UserError(_(
                'Library xlsxwriter belum terinstall. Pakai format CSV atau install xlsxwriter.'
            ))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = workbook.add_worksheet('Transaksi')

        # Formats
        fmt_header = workbook.add_format({
            'bold': True, 'bg_color': '#714B67', 'font_color': '#ffffff',
            'border': 1, 'align': 'center', 'valign': 'vcenter',
        })
        fmt_money = workbook.add_format({'num_format': '#,##0', 'border': 1})
        fmt_text = workbook.add_format({'border': 1})
        fmt_date = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss', 'border': 1})
        fmt_title = workbook.add_format({
            'bold': True, 'font_size': 16, 'font_color': '#714B67',
        })
        fmt_meta = workbook.add_format({'italic': True, 'font_color': '#6c7079'})

        # Title block
        ws.merge_range('A1:K1', 'Wasabi Kitchen Jatinangor — Laporan Transaksi', fmt_title)
        ws.merge_range('A2:K2', f'Periode: {self.date_from} s/d {self.date_to} · '
                                 f'Metode: {dict(self._fields["payment_method"].selection)[self.payment_method]} · '
                                 f'Total: {len(transactions)} transaksi · Rp {sum(transactions.mapped("total_amount")):,.0f}',
                       fmt_meta)

        # Headers
        headers = [
            ('A', 'transaksi_id', 18),
            ('B', 'order_id', 18),
            ('C', 'tanggal', 18),
            ('D', 'no_meja', 8),
            ('E', 'jumlah_item', 10),
            ('F', 'subtotal', 12),
            ('G', 'pb1', 12),
            ('H', 'service_charge', 14),
            ('I', 'total_harga', 14),
            ('J', 'metode_bayar', 14),
            ('K', 'kasir', 18),
        ]
        if self.include_items:
            headers.append(('L', 'detail_item', 50))

        for col_idx, (col, name, width) in enumerate(headers):
            ws.set_column(f'{col}:{col}', width)
            ws.write(3, col_idx, name, fmt_header)

        # Data rows
        for row_idx, trx in enumerate(transactions, start=4):
            ws.write_string(row_idx, 0, trx.transaction_number, fmt_text)
            ws.write_string(row_idx, 1, trx.order_number, fmt_text)
            if trx.paid_at:
                ws.write_datetime(row_idx, 2, trx.paid_at, fmt_date)
            else:
                ws.write_string(row_idx, 2, '', fmt_text)
            ws.write_number(row_idx, 3, trx.table_number or 0, fmt_text)
            ws.write_number(row_idx, 4, trx.order_id.item_count or 0, fmt_text)
            ws.write_number(row_idx, 5, float(trx.order_id.subtotal), fmt_money)
            ws.write_number(row_idx, 6, float(trx.order_id.pb1), fmt_money)
            ws.write_number(row_idx, 7, float(trx.order_id.service_charge), fmt_money)
            ws.write_number(row_idx, 8, float(trx.total_amount), fmt_money)
            ws.write_string(row_idx, 9,
                            dict(trx._fields['payment_method'].selection)[trx.payment_method],
                            fmt_text)
            ws.write_string(row_idx, 10, trx.staff_id.name or '', fmt_text)
            if self.include_items:
                items_str = ' | '.join([
                    f'{l.quantity}x {l.name}'
                    for l in trx.order_id.order_item_ids
                ])
                ws.write_string(row_idx, 11, items_str, fmt_text)

        # Summary row
        last_row = len(transactions) + 4
        ws.write(last_row, 4, 'TOTAL', fmt_header)
        ws.write_formula(last_row, 5, f'=SUM(F5:F{last_row})', fmt_money)
        ws.write_formula(last_row, 6, f'=SUM(G5:G{last_row})', fmt_money)
        ws.write_formula(last_row, 7, f'=SUM(H5:H{last_row})', fmt_money)
        ws.write_formula(last_row, 8, f'=SUM(I5:I{last_row})', fmt_money)

        # Freeze header
        ws.freeze_panes(4, 0)

        workbook.close()
        content = output.getvalue()
        filename = f'wasabi_transactions_{self.date_from}_{self.date_to}.xlsx'
        return content, filename
