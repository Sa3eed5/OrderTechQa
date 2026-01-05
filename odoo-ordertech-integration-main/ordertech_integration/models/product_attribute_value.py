import json
import logging
import typing

import requests

from odoo import api, fields, models
from odoo.api import ValuesType

_logger = logging.getLogger(__name__)

class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    ordertech_addons_itemId = fields.Char()


    @api.model_create_multi
    def create(self, vals_list):
        values = super(ProductAttributeValue, self).create(vals_list)
        ordertech_items = values.filtered(
            lambda item: item.attribute_id.ordertech_addons_groupId
        )
        if ordertech_items:
            ordertech_items.create_tenant_addon_item_api()
        return values

    def create_tenant_addon_item_api(self):
        instance = self.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance missing, addons-item sync skipped.")
            return False
        for item in self:
            url = f"{instance.url}/api/menu/addon-items/{item.attribute_id.company_id.ordertech_tenantId}"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            payload = json.dumps({
                "name_en": item.with_context(lang="en_US").name,
                "name_ar": item.with_context(lang="ar_001").name,
                "group_id": item.attribute_id.ordertech_addons_groupId,
                "price_cents_base": item.default_extra_price,
                "is_active": True,
                "sort_order": 0
            })
            try:
                response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
                if response.status_code != 201:
                    _logger.error(
                        "OrderTech tenant addon-item sync failed for addon-item %s: %s ",
                        item.id, response.text,
                    )
                    continue
                data = response.json()
                if data.get('items'):
                    item.sudo().write({
                        'ordertech_addons_itemId': data['items'][0]['id'],
                    })
                _logger.info("Successfully synced addon-item data for addon-item %s", item.id)
            except Exception as e:
                _logger.error(
                    "OrderTech API request error for addon-item %s: %s",
                    item.id,
                    str(e),
                )

    def write(self, vals):
        res = super(ProductAttributeValue, self).write(vals)
        if any(k in vals for k in ('name', 'default_extra_price')):
            values = self.filtered(
                lambda item: item.ordertech_addons_itemId
            )
            if values:
                values.update_tenant_addon_item_api()
        return res

    def update_tenant_addon_item_api(self):
        instance = self.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance is missing.")
            return False
        for item in self:
            url = f"{instance.url}/api/menu/addon-items/{item.ordertech_addons_itemId}"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            payload = json.dumps({
                "name_en": item.with_context(lang="en_US").name,
                "name_ar": item.with_context(lang="ar_001").name,
                "price_cents_base": item.default_extra_price,
                "is_active": True,
                "sort_order": 0
            })
            try:
                response = requests.request("PUT", url, headers=headers, data=payload, timeout=10)
                if response.status_code != 200:
                    _logger.error(
                        "OrderTech tenant addons-item sync failed for addons-item %s: %s ",
                        item.id, response.text,
                    )
                    continue
                _logger.info("Successfully synced addons-item update data for addons-item %s", item.id)
            except Exception as e:
                _logger.error(
                    "OrderTech API request error for addons_item %s: %s",
                    item.id,
                    str(e),
                )
        return True