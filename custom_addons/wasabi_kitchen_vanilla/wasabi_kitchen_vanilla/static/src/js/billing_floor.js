/** @odoo-module **/
/* ============================================================
   Wasabi Kitchen — Billing Floor Plan
   Auto-refresh setiap 20 detik untuk update status meja.
   ============================================================ */

import { registry } from "@web/core/registry";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { onWillStart, onWillUnmount } from "@odoo/owl";

const REFRESH_INTERVAL_MS = 20000;

class WasabiBillingKanbanController extends KanbanController {
    setup() {
        super.setup();

        onWillStart(() => {
            this._wasabiBillingTimer = setInterval(() => {
                if (document.visibilityState === 'visible') {
                    this.model.load();
                }
            }, REFRESH_INTERVAL_MS);
        });

        onWillUnmount(() => {
            if (this._wasabiBillingTimer) {
                clearInterval(this._wasabiBillingTimer);
            }
        });
    }
}

export const wasabiBillingKanbanView = {
    ...kanbanView,
    Controller: WasabiBillingKanbanController,
};

registry.category("views").add("wasabi_billing_kanban", wasabiBillingKanbanView);
