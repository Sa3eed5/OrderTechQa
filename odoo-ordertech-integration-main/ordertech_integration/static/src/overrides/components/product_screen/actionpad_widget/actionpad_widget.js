import { patch } from "@web/core/utils/patch";
import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { rpc } from "@web/core/network/rpc";

patch(ActionpadWidget.prototype, {
    async submitOrder() {
        // Call original behavior first
        await super.submitOrder();
        const order = this.pos.get_order();
        if (!order) {
            return;
        }
        //  Call backend (safe, no CORS, no secrets in JS)
        try {
            await rpc("/pos/order/webhook", {
                order_id: order.id,
            });
        } catch (error) {
            console.error("POS webhook failed:", error);
        }
    },
});
