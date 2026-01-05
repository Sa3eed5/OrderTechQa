from odoo import models
import json
import logging
import requests

from odoo.http import request

_logger = logging.getLogger(__name__)


class PreparationDisplayOrder(models.Model):
    _inherit = 'pos_preparation_display.order'


    def change_order_stage(self, stage_id, preparation_display_id):
        res = super(PreparationDisplayOrder, self).change_order_stage(stage_id, preparation_display_id)
        self._send_ordertech_webhook(stage_id)
        return res

    def done_orders_stage(self, preparation_display_id):
        res = super(PreparationDisplayOrder,self).done_orders_stage(preparation_display_id)
        self._send_ordertech_complete_webhook(preparation_display_id)
        return res


    def _send_ordertech_webhook(self, stage_id):
        stage = self.env['pos_preparation_display.stage'].browse(stage_id)
        instance = request.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance missing, order status sync skipped.")
            return False
        for order in self:
            if order.pos_order_id.ordertech_orderId:
                url = f"{instance.url}/api/integrations/odoo/webhook/order-status"
                headers = {
                    'accept': '*/*',
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {instance.ordertech_token}'
                }
                payload = json.dumps({
                    "order_id": order.pos_order_id.ordertech_orderId,
                    "status": stage.name.lower(),
                })
                try:
                    response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
                    if response.status_code != 201:
                        _logger.error(
                            "OrderTech update order status failed for order %s: %s ",
                            order.pos_order_id.id, response.text,
                        )
                        continue
                    _logger.info("Successfully update order status for order %s", order.pos_order_id.id)
                except Exception as e:
                    _logger.error(
                        "OrderTech API request error for order %s: %s",
                        order.pos_order_id.id,
                        str(e),
                    )


    def _send_ordertech_complete_webhook(self, preparation_display_id):
        preparation_display = self.env['pos_preparation_display.display'].browse(preparation_display_id)
        last_stage = preparation_display.stage_ids[-1]
        instance = request.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance missing, order status sync skipped.")
            return False
        for order in self:
            if order.pos_order_id.ordertech_orderId:
                url = f"{instance.url}/api/integrations/odoo/webhook/order-status"
                headers = {
                    'accept': '*/*',
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {instance.ordertech_token}'
                }
                payload = json.dumps({
                    "order_id": order.pos_order_id.ordertech_orderId,
                    "status": last_stage.name.lower(),
                })
                try:
                    response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
                    if response.status_code != 201:
                        _logger.error(
                            "OrderTech update order status failed for order %s: %s ",
                            order.pos_order_id.id, response.text,
                        )
                        continue
                    _logger.info("Successfully update order status for order %s", order.pos_order_id.id)
                except Exception as e:
                    _logger.error(
                        "OrderTech API request error for order %s: %s",
                        order.pos_order_id.id,
                        str(e),
                    )
