# -*- coding: utf-8 -*-
import json
import logging
from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class WasabiCustomerController(http.Controller):
    """Public controllers untuk pelanggan (UC-03, UC-04, UC-05).

    Tidak butuh login. Akses dilindungi via QR token unik per meja.
    """

    # ------------------------------------------------------------------
    # UC-04: Scan QR Code — landing page setelah scan
    # ------------------------------------------------------------------
    @http.route(['/wasabi/menu/<string:qr_token>'], type='http', auth='public', csrf=False)
    def customer_menu(self, qr_token, **kw):
        """Halaman browse menu yang dibuka setelah pelanggan scan QR code."""
        table = request.env['wasabi.table'].sudo().search(
            [('qr_token', '=', qr_token), ('is_active', '=', True)],
            limit=1,
        )
        if not table:
            return request.render('wasabi_kitchen_vanilla.customer_invalid_qr', {})

        # Mark meja sebagai occupied jika masih available
        if table.status == 'available':
            table.sudo().write({'status': 'occupied'})

        categories = request.env['wasabi.category'].sudo().search(
            [('is_active', '=', True)],
            order='sequence, name',
        )
        menu_items = request.env['wasabi.menu.item'].sudo().search(
            [('is_available', '=', True)],
            order='category_id, sequence, name',
        )

        return request.render('wasabi_kitchen_vanilla.customer_menu_page', {
            'table':       table,
            'categories':  categories,
            'menu_items':  menu_items,
            'qr_token':    qr_token,
        })

    # ------------------------------------------------------------------
    # API: get menu data (JSON) — untuk live refresh setelah stock update
    # ------------------------------------------------------------------
    @http.route(['/wasabi/api/menu/<string:qr_token>'], type='json', auth='public', csrf=False)
    def api_get_menu(self, qr_token, **kw):
        table = request.env['wasabi.table'].sudo().search(
            [('qr_token', '=', qr_token)], limit=1,
        )
        if not table:
            return {'error': 'Invalid QR token'}

        items = request.env['wasabi.menu.item'].sudo().search(
            [('is_available', '=', True)],
        )
        return {
            'table': {
                'id':           table.id,
                'table_number': table.table_number,
                'floor':        table.floor,
            },
            'items': [{
                'id':              item.id,
                'name':            item.name,
                'description':     item.description or '',
                'price':           float(item.price),
                'category_id':     item.category_id.id,
                'category_name':   item.category_id.name,
                'remaining_stock': item.remaining_stock,
                'is_unlimited':    item.is_unlimited,
                'stock_status':    item.stock_status,
                'photo_color':     item.photo_color,
                'glyph':           item.glyph or '',
            } for item in items],
        }

    # ------------------------------------------------------------------
    # UC-05: Membuat Pesanan
    # ------------------------------------------------------------------
    @http.route(['/wasabi/api/order/create'], type='json', auth='public', csrf=False)
    def api_create_order(self, qr_token=None, items=None, notes=None, **kw):
        """Create order dari customer.

        Body JSON:
            {
                "qr_token": "abc123",
                "items": [
                    {"menu_item_id": 5, "quantity": 2, "note": "tanpa wasabi"},
                    ...
                ],
                "notes": "..."
            }

        Returns:
            { "success": True, "order_number": "ORD-2604-0042" }
            atau { "success": False, "error": "..." }
        """
        if not qr_token or not items:
            return {'success': False, 'error': _('Data pesanan tidak lengkap.')}

        table = request.env['wasabi.table'].sudo().search(
            [('qr_token', '=', qr_token), ('is_active', '=', True)],
            limit=1,
        )
        if not table:
            return {'success': False, 'error': _('Meja tidak ditemukan.')}

        try:
            # Build order items dengan snapshot harga
            order_lines = []
            for it in items:
                menu_item = request.env['wasabi.menu.item'].sudo().browse(int(it['menu_item_id']))
                if not menu_item.exists() or not menu_item.is_available:
                    return {
                        'success': False,
                        'error': _('Menu %s tidak tersedia.') % (menu_item.name or 'unknown'),
                    }
                qty = int(it.get('quantity', 1))
                if qty < 1:
                    continue
                order_lines.append((0, 0, {
                    'menu_item_id': menu_item.id,
                    'quantity':     qty,
                    'unit_price':   menu_item.price,
                    'note':         it.get('note') or False,
                }))

            if not order_lines:
                return {'success': False, 'error': _('Tidak ada item yang dipesan.')}

            order = request.env['wasabi.order'].sudo().create({
                'table_id':       table.id,
                'order_item_ids': order_lines,
                'notes':          notes or False,
                'status':         'pending',
            })

            # Konfirmasi (validasi & decrement stok atomik)
            order.action_confirm()

            return {
                'success':      True,
                'order_id':     order.id,
                'order_number': order.order_number,
                'total':        float(order.total_price),
                'subtotal':     float(order.subtotal),
                'pb1':          float(order.pb1),
                'service':      float(order.service_charge),
            }
        except Exception as e:
            _logger.exception('Create order failed')
            return {'success': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # Tracking status pesanan
    # ------------------------------------------------------------------
    @http.route(['/wasabi/order/status/<int:order_id>'], type='http', auth='public')
    def order_status(self, order_id, **kw):
        order = request.env['wasabi.order'].sudo().browse(order_id)
        if not order.exists():
            return request.not_found()
        return request.render('wasabi_kitchen_vanilla.customer_order_status', {
            'order': order,
        })

    @http.route(['/wasabi/api/order/<int:order_id>/status'], type='json', auth='public', csrf=False)
    def api_order_status(self, order_id, **kw):
        order = request.env['wasabi.order'].sudo().browse(order_id)
        if not order.exists():
            return {'error': 'not_found'}
        return {
            'status':       order.status,
            'order_number': order.order_number,
            'cooking_at':   order.cooking_at and order.cooking_at.isoformat(),
            'ready_at':     order.ready_at and order.ready_at.isoformat(),
            'paid_at':      order.paid_at and order.paid_at.isoformat(),
        }
