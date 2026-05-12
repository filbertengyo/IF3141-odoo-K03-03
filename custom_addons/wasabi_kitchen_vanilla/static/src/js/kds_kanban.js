/** @odoo-module **/
/* ============================================================
   Wasabi Kitchen — KDS Auto-Refresh
   Otomatis refresh kanban setiap 15 detik untuk pseudo-realtime.
   Tanpa websocket, agar tetap simple & tidak butuh deps tambahan.
   ============================================================ */

import { registry } from "@web/core/registry";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { onWillStart, onWillUnmount } from "@odoo/owl";

const REFRESH_INTERVAL_MS = 15000; // 15 detik

class WasabiKDSKanbanController extends KanbanController {
    setup() {
        super.setup();

        onWillStart(() => {
            this._wasabiTimer = setInterval(() => {
                if (document.visibilityState === 'visible') {
                    this.model.load();
                }
            }, REFRESH_INTERVAL_MS);
        });

        onWillUnmount(() => {
            if (this._wasabiTimer) {
                clearInterval(this._wasabiTimer);
            }
        });
    }
}

export const wasabiKDSKanbanView = {
    ...kanbanView,
    Controller: WasabiKDSKanbanController,
};

registry.category("views").add("wasabi_kds_kanban", wasabiKDSKanbanView);
