from datetime import datetime, time, timedelta

from odoo import models, fields, api


class WasabiDashboard(models.TransientModel):
    _name = 'wasabi.dashboard'
    _description = 'Wasabi Kitchen — KPI Dashboard'

    name = fields.Char(default='Dashboard')
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.ref('base.IDR'),
    )

    today_revenue = fields.Monetary(string='Revenue Hari Ini', compute='_compute_kpi', currency_field='currency_id')
    today_count = fields.Integer(string='Transaksi Hari Ini', compute='_compute_kpi')
    today_avg = fields.Monetary(string='Rata-rata Transaksi', compute='_compute_kpi', currency_field='currency_id')

    week_revenue = fields.Monetary(string='Revenue 7 Hari', compute='_compute_kpi', currency_field='currency_id')
    week_count = fields.Integer(string='Transaksi 7 Hari', compute='_compute_kpi')

    month_revenue = fields.Monetary(string='Revenue Bulan Ini', compute='_compute_kpi', currency_field='currency_id')
    month_count = fields.Integer(string='Transaksi Bulan Ini', compute='_compute_kpi')

    cash_share = fields.Float(string='Tunai (%)', compute='_compute_kpi')
    qris_share = fields.Float(string='QRIS (%)', compute='_compute_kpi')

    active_orders = fields.Integer(string='Pesanan Aktif', compute='_compute_kpi')
    pending_orders = fields.Integer(string='Pending', compute='_compute_kpi')
    cooking_orders = fields.Integer(string='Cooking', compute='_compute_kpi')
    ready_orders = fields.Integer(string='Ready (siap bayar)', compute='_compute_kpi')

    tables_total = fields.Integer(string='Total Meja', compute='_compute_kpi')
    tables_occupied = fields.Integer(string='Meja Terisi', compute='_compute_kpi')

    low_stock_count = fields.Integer(string='Menu Stok Menipis', compute='_compute_kpi')

    def _compute_kpi(self):
        Trx = self.env['wasabi.transaction']
        Order = self.env['wasabi.order']
        Table = self.env['wasabi.table']
        Menu = self.env['wasabi.menu.item']

        today = fields.Date.context_today(self)
        start_today = datetime.combine(today, time.min)
        start_week = datetime.combine(today - timedelta(days=6), time.min)
        start_month = datetime.combine(today.replace(day=1), time.min)

        for rec in self:
            today_trx = Trx.search([('paid_at', '>=', start_today)])
            week_trx = Trx.search([('paid_at', '>=', start_week)])
            month_trx = Trx.search([('paid_at', '>=', start_month)])

            rec.today_revenue = sum(today_trx.mapped('total_amount'))
            rec.today_count = len(today_trx)
            rec.today_avg = (rec.today_revenue / rec.today_count) if rec.today_count else 0.0

            rec.week_revenue = sum(week_trx.mapped('total_amount'))
            rec.week_count = len(week_trx)

            rec.month_revenue = sum(month_trx.mapped('total_amount'))
            rec.month_count = len(month_trx)

            cash_amt = sum(month_trx.filtered(lambda t: t.payment_method == 'cash').mapped('total_amount'))
            qris_amt = sum(month_trx.filtered(lambda t: t.payment_method == 'qris').mapped('total_amount'))
            total = cash_amt + qris_amt
            rec.cash_share = (cash_amt / total * 100) if total else 0.0
            rec.qris_share = (qris_amt / total * 100) if total else 0.0

            rec.pending_orders = Order.search_count([('status', '=', 'pending')])
            rec.cooking_orders = Order.search_count([('status', '=', 'cooking')])
            rec.ready_orders = Order.search_count([('status', '=', 'ready')])
            rec.active_orders = rec.pending_orders + rec.cooking_orders + rec.ready_orders

            rec.tables_total = Table.search_count([('is_active', '=', True)])
            rec.tables_occupied = Table.search_count([('status', '=', 'occupied')])

            rec.low_stock_count = Menu.search_count([
                ('stock_status', 'in', ('low', 'out')),
            ])

    @api.model
    def action_open_dashboard(self):
        rec = self.create({})
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dashboard',
            'res_model': 'wasabi.dashboard',
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'inline',
            'view_id': self.env.ref('wasabi_kitchen_vanilla.view_wasabi_dashboard_form').id,
        }
