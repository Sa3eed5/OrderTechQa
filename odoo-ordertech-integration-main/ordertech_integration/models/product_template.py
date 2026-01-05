import json
import logging

import requests
from odoo import api, fields, models, SUPERUSER_ID
from odoo.http import request

_logger = logging.getLogger(__name__)

PRODUCT_TRACKED_FIELDS = {
    "name",
    "default_code",
    "image_1920",
    "pos_categ_ids",
    "list_price",
    "attribute_line_ids"
}

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    ordertech_productId = fields.Char()

    def default_get(self, default_fields):
        defaults = super().default_get(default_fields)
        if not defaults.get('company_id'):
            defaults['company_id'] = self.env.company.id
        return defaults

    @api.model_create_multi
    def create(self, vals_list):
        products = super(ProductTemplate, self).create(vals_list)
        ordertech_product = products.filtered(
            lambda p: (
                    p.available_in_pos
                    and any(c.ordertech_categId for c in p.pos_categ_ids)
                    and p.company_id.ordertech_tenantId
            )
        )
        if ordertech_product:
            ordertech_product.create_tenant_product_api()
        return products

    def create_tenant_product_api(self):
        instance = self.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance missing, product sync skipped.")
            return False
        for product in self:
            url = f"{instance.url}/api/menu/products/{product.company_id.ordertech_tenantId}"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            slugify = self.env['ir.http']._slugify
            slug = slugify(product.name)
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            img_url = f"{base_url}/web/image/product.template/{product.id}/image_1920" if product.image_1920 else None
            payload = json.dumps({
                "name_en": product.with_context(lang="en_US").name,
                "name_ar": product.with_context(lang="ar_001").name,
                "slug": slug,
                "sku": product.default_code,
                "category_id": product.pos_categ_ids.filtered(lambda c: c.ordertech_categId)[0].ordertech_categId,
                "image_url": img_url,
                "is_active": True,
                "has_sizes": False,
                "has_addons": False,
                "sort_order": 0,
                # "sizes": [
                #     {
                #         "name_en": "string",
                #         "name_ar": "string",
                #         "size_code": "string",
                #         "price_cents_base": 0,
                #         "sort_order": 0
                #     }
                # ],
                # "addon_groups": [
                #     {
                #         "addon_group_id": "string",
                #         "sort_order": 0
                #     }
                # ],
                "base_price_cents": product.list_price
            })
            try:
                response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
                if response.status_code != 201:
                    _logger.error(
                        "OrderTech tenant product sync failed for product %s: %s ",
                        product.id, response.text,
                    )
                    continue
                data = response.json()
                product.with_user(SUPERUSER_ID).write({
                    'ordertech_productId': data['id'],
                })
                _logger.info("Successfully synced product data for product %s", product.id)
            except Exception as e:
                _logger.error(
                    "OrderTech API request error for product %s: %s",
                    product.id,
                    str(e),
                )

    def write(self, vals):
        trigger_update_pro = bool(PRODUCT_TRACKED_FIELDS & vals.keys())
        res = super(ProductTemplate, self).write(vals)
        if trigger_update_pro:
            products = self.filtered(
                lambda p: (
                        p.available_in_pos
                        and p.ordertech_productId
                        and p.pos_categ_ids[0].ordertech_categId
                        and p.company_id.ordertech_tenantId
                )
            )
            if products:
                products.update_tenant_product_api()
        return res

    def update_tenant_product_api(self):
        instance = self.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance is missing.")
            return False
        for product in self:
            url = f"{instance.url}/api/menu/products/{product.ordertech_productId}"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            slugify = self.env['ir.http']._slugify
            slug = slugify(product.name)
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            img_url = f"{base_url}/web/image/product.template/{product.id}/image_1920" if product.image_128 else None
            payload = {
                "name_en": product.with_context(lang="en_US").name,
                "name_ar": product.with_context(lang="ar_001").name,
                "slug": slug,
                "sku": product.default_code,
                "category_id": product.pos_categ_ids.filtered(lambda c: c.ordertech_categId)[0].ordertech_categId,
                "image_url": img_url,
                "is_active": True,
                "has_sizes": False,
                "has_addons": False,
                "sort_order": 0,
                "base_price_cents": product.list_price
            }
            ot_sizes_attribute = self.env.ref("ordertech_integration.ordertech_product_sizes_attribute")
            if ot_sizes_attribute:
                size_att =  product.attribute_line_ids.filtered(
                    lambda l: l.attribute_id.id == ot_sizes_attribute.id
                )
                if size_att:
                    sizes = []
                    for value in size_att.value_ids:
                        sizes.append({
                            "name_en":value.name,
                            "price_cents_base": value.default_extra_price + product.list_price
                        })
                    payload.update({
                        "has_sizes": True,
                        "sizes": sizes
                    })

            ordertech_attributes = product.attribute_line_ids.filtered(
                lambda l: l.attribute_id.is_addons and l.attribute_id.ordertech_addons_groupId
            )
            if ordertech_attributes:
                addon_groups = []
                for line in ordertech_attributes:
                    addon_groups.append({
                        "addon_group_id": line.attribute_id.ordertech_addons_groupId,
                        "sort_order": 0
                    })
                payload.update({
                    "has_addons": True,
                    "addon_groups": addon_groups
                })

            try:
                response = requests.request("PUT", url, headers=headers, json=payload, timeout=10)
                if response.status_code != 200:
                    _logger.error(
                        "OrderTech tenant product sync failed for product %s: %s ",
                        product.id, response.text,
                    )
                    continue
                _logger.info("Successfully synced product update data for product %s", product.id)
            except Exception as e:
                _logger.error(
                    "OrderTech API request error for product %s: %s",
                    product.id,
                    str(e),
                )
        return True

    def action_sync_products_to_ordertech(self):
        ordertech_product = self.filtered(
            lambda p: (
                    p.available_in_pos
                    and any(c.ordertech_categId for c in p.pos_categ_ids)
                    and p.company_id.ordertech_tenantId
                    and not p.ordertech_productId
            )
        )
        if ordertech_product:
            ordertech_product.create_tenant_product_api()
            ordertech_product.update_tenant_product_api()
        return True