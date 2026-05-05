/** @odoo-module **/
/* ============================================================
   Wasabi Kitchen — Customer ordering JS
   Handles: category filter, cart state, order submission, status polling
   ============================================================ */

(function () {
    'use strict';

    // Wait for DOM ready (vanilla JS, no jQuery dependency)
    function ready(fn) {
        if (document.readyState !== 'loading') fn();
        else document.addEventListener('DOMContentLoaded', fn);
    }

    function formatRupiah(n) {
        return 'Rp ' + Math.round(n).toLocaleString('id-ID');
    }

    /* =========================================
       MENU PAGE
       ========================================= */
    function initMenuPage() {
        const grid = document.getElementById('menu-grid');
        const tabs = document.getElementById('cat-tabs');
        const cartBar = document.getElementById('cart-bar');
        const cartCount = document.getElementById('cart-count');
        const cartSummary = document.getElementById('cart-summary');
        const checkoutBtn = document.getElementById('cart-checkout');
        const qrTokenEl = document.getElementById('qr-token');

        if (!grid || !tabs) return;
        const qrToken = qrTokenEl ? qrTokenEl.value : '';

        // Cart state: { itemId: { qty, name, price, note } }
        const cart = {};

        function persistCart() {
            try {
                sessionStorage.setItem('wasabi_cart_' + qrToken, JSON.stringify(cart));
            } catch (e) { /* ignore */ }
        }

        function restoreCart() {
            try {
                const raw = sessionStorage.getItem('wasabi_cart_' + qrToken);
                if (raw) Object.assign(cart, JSON.parse(raw));
            } catch (e) { /* ignore */ }
        }

        function refreshCartBar() {
            const totalItems = Object.values(cart).reduce((s, x) => s + x.qty, 0);
            const totalPrice = Object.values(cart).reduce((s, x) => s + x.qty * x.price, 0);

            if (totalItems === 0) {
                cartBar.style.display = 'none';
            } else {
                cartBar.style.display = 'flex';
                cartCount.textContent = totalItems;
                cartSummary.textContent = `${totalItems} item · ${formatRupiah(totalPrice)}`;
            }
        }

        // Category filter
        tabs.addEventListener('click', (e) => {
            const tab = e.target.closest('.o_wasabi_cat_tab');
            if (!tab) return;
            tabs.querySelectorAll('.o_wasabi_cat_tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const cat = tab.dataset.cat;
            grid.querySelectorAll('.o_wasabi_menu_item').forEach(item => {
                if (cat === 'all' || item.dataset.cat === cat) {
                    item.classList.remove('hidden');
                } else {
                    item.classList.add('hidden');
                }
            });
        });

        // Add to cart
        grid.addEventListener('click', (e) => {
            const btn = e.target.closest('.o_wasabi_add_btn');
            if (!btn) return;
            const item = btn.closest('.o_wasabi_menu_item');
            const id = item.dataset.id;
            const name = item.dataset.name;
            const price = parseFloat(item.dataset.price);

            if (!cart[id]) {
                cart[id] = { qty: 0, name, price, note: '' };
            }
            cart[id].qty += 1;
            persistCart();
            refreshCartBar();

            // Animation: bump button briefly
            btn.style.transform = 'scale(1.3)';
            setTimeout(() => { btn.style.transform = ''; }, 200);
        });

        // Checkout: open cart review page (simple inline UI)
        checkoutBtn.addEventListener('click', () => {
            renderCartReview(cart, qrToken);
        });

        restoreCart();
        refreshCartBar();
    }

    /* =========================================
       CART REVIEW (simple modal/overlay)
       ========================================= */
    function renderCartReview(cart, qrToken) {
        // Build overlay
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed; inset: 0; background: rgba(31,29,36,.6);
            z-index: 1000; display: grid; place-items: center; padding: 20px;
        `;
        const modal = document.createElement('div');
        modal.style.cssText = `
            background: #fff; border-radius: 20px; max-width: 440px; width: 100%;
            max-height: 90vh; overflow-y: auto; padding: 24px;
            font-family: 'IBM Plex Sans', sans-serif;
        `;

        const items = Object.entries(cart).filter(([_, x]) => x.qty > 0);
        const subtotal = items.reduce((s, [_, x]) => s + x.qty * x.price, 0);
        const pb1 = subtotal * 0.10;
        const service = subtotal * 0.05;
        const total = subtotal + pb1 + service;

        modal.innerHTML = `
            <h2 style="font-family:'Shippori Mincho',serif;font-size:22px;margin:0 0 4px;">Tinjau Pesanan</h2>
            <p style="color:#6c7079;font-size:12px;margin:0 0 18px;">Periksa kembali sebelum dikirim ke dapur</p>
            <div id="cart-items"></div>
            <div style="border-top:1px dashed #e3e1e6;padding-top:14px;margin-top:14px;font-family:'JetBrains Mono',monospace;font-size:13px;">
                <div style="display:flex;justify-content:space-between;color:#6c7079;padding:3px 0;"><span>Subtotal</span><span>${formatRupiah(subtotal)}</span></div>
                <div style="display:flex;justify-content:space-between;color:#6c7079;padding:3px 0;"><span>PB1 (10%)</span><span>${formatRupiah(pb1)}</span></div>
                <div style="display:flex;justify-content:space-between;color:#6c7079;padding:3px 0;"><span>Service (5%)</span><span>${formatRupiah(service)}</span></div>
                <div style="display:flex;justify-content:space-between;border-top:1px solid #e3e1e6;margin-top:8px;padding-top:10px;font-weight:700;font-size:15px;color:#1f1d24;font-family:'IBM Plex Sans',sans-serif;"><span>Total</span><span>${formatRupiah(total)}</span></div>
            </div>
            <textarea id="order-notes" placeholder="Catatan untuk dapur (opsional)..." style="width:100%;margin-top:14px;padding:10px;border:1px solid #e3e1e6;border-radius:8px;font-family:inherit;font-size:13px;resize:vertical;min-height:60px;"></textarea>
            <div style="display:flex;gap:8px;margin-top:18px;">
                <button id="cart-cancel" style="flex:1;padding:12px;border:1px solid #d0cdd4;background:#fff;border-radius:10px;cursor:pointer;font-weight:600;">Kembali</button>
                <button id="cart-submit" style="flex:2;padding:12px;background:#7BAE3F;color:#1f1d24;border:none;border-radius:10px;cursor:pointer;font-weight:700;box-shadow:0 4px 12px rgba(123,174,63,.30);">Kirim ke Dapur →</button>
            </div>
        `;

        const itemsContainer = modal.querySelector('#cart-items');
        items.forEach(([id, x]) => {
            const row = document.createElement('div');
            row.style.cssText = 'display:grid;grid-template-columns:1fr auto auto;gap:10px;align-items:center;padding:10px 0;border-bottom:1px dashed #e3e1e6;';
            row.innerHTML = `
                <div>
                    <div style="font-weight:600;font-size:14px;">${x.name}</div>
                    <div style="font-size:11px;color:#6c7079;font-family:'JetBrains Mono',monospace;">${formatRupiah(x.price)} × ${x.qty}</div>
                </div>
                <div style="display:flex;align-items:center;gap:6px;background:#f5f4f6;border-radius:18px;padding:2px;">
                    <button data-id="${id}" data-act="dec" style="width:26px;height:26px;border-radius:50%;background:#fff;border:1px solid #d0cdd4;font-weight:700;color:#714B67;">−</button>
                    <span style="padding:0 8px;font-weight:700;font-family:'JetBrains Mono',monospace;">${x.qty}</span>
                    <button data-id="${id}" data-act="inc" style="width:26px;height:26px;border-radius:50%;background:#fff;border:1px solid #d0cdd4;font-weight:700;color:#714B67;">+</button>
                </div>
                <div style="font-family:'JetBrains Mono',monospace;font-weight:600;color:#714B67;">${formatRupiah(x.qty * x.price)}</div>
            `;
            itemsContainer.appendChild(row);
        });

        // Stepper handlers
        itemsContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-act]');
            if (!btn) return;
            const id = btn.dataset.id;
            const act = btn.dataset.act;
            if (act === 'inc') cart[id].qty++;
            else if (cart[id].qty > 0) cart[id].qty--;
            try { sessionStorage.setItem('wasabi_cart_' + qrToken, JSON.stringify(cart)); } catch (e) {}
            // re-render
            overlay.remove();
            renderCartReview(cart, qrToken);
        });

        modal.querySelector('#cart-cancel').addEventListener('click', () => overlay.remove());
        modal.querySelector('#cart-submit').addEventListener('click', () => {
            submitOrder(cart, qrToken, modal.querySelector('#order-notes').value, overlay);
        });

        overlay.appendChild(modal);
        document.body.appendChild(overlay);
    }

    /* =========================================
       SUBMIT ORDER → call backend RPC
       ========================================= */
    function submitOrder(cart, qrToken, notes, overlay) {
        const items = Object.entries(cart)
            .filter(([_, x]) => x.qty > 0)
            .map(([id, x]) => ({
                menu_item_id: parseInt(id),
                quantity:     x.qty,
                note:         x.note || '',
            }));

        if (!items.length) return;

        const submitBtn = overlay.querySelector('#cart-submit');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '⏳ Mengirim...';

        fetch('/wasabi/api/order/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method:  'call',
                params: {
                    qr_token: qrToken,
                    items:    items,
                    notes:    notes,
                },
            }),
        })
        .then(r => r.json())
        .then(resp => {
            const result = resp.result || {};
            if (result.success) {
                // Clear cart
                sessionStorage.removeItem('wasabi_cart_' + qrToken);
                // Redirect ke status page
                window.location.href = '/wasabi/order/status/' + result.order_id;
            } else {
                alert('Gagal mengirim pesanan: ' + (result.error || 'Unknown error'));
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Coba lagi →';
            }
        })
        .catch(err => {
            alert('Error koneksi: ' + err.message);
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Coba lagi →';
        });
    }

    /* =========================================
       STATUS PAGE — poll order status every 5s
       ========================================= */
    function initStatusPage() {
        const orderEl = document.getElementById('order-id');
        if (!orderEl) return;
        const orderId = orderEl.value;

        function poll() {
            fetch('/wasabi/api/order/' + orderId + '/status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: {} }),
            })
            .then(r => r.json())
            .then(resp => {
                const data = resp.result || {};
                const card = document.querySelector('.o_wasabi_status_card');
                if (card && data.status && card.dataset.status !== data.status) {
                    // Status berubah → reload halaman
                    window.location.reload();
                }
            })
            .catch(() => {});
        }
        setInterval(poll, 5000);
    }

    ready(() => {
        initMenuPage();
        initStatusPage();
    });
})();
