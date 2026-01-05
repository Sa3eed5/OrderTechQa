import json
import logging

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

ATTRIBUTE_TRACKED_FIELDS ={
    "name",
    "limit_min",
    "limit_max",
    "is_required",
}

class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id)
    is_addons = fields.Boolean(string="Is Add-ons Group")
    limit_min = fields.Integer()
    limit_max = fields.Integer()
    is_required = fields.Boolean()
    ordertech_addons_groupId = fields.Char()

    @api.onchange("is_addons")
    def _check_is_addons_group(self):
        for rec in self:
            if rec.is_addons :
                rec.display_type = 'multi'

    @api.model_create_multi
    def create(self, vals_list):
        attributes = super(ProductAttribute, self).create(vals_list)
        ordertech_attrs = attributes.filtered(
            lambda attr: attr.company_id and attr.company_id.ordertech_tenantId and attr.is_addons
        )
        if ordertech_attrs:
            ordertech_attrs.create_tenant_addons_group_api()
        return attributes

    def create_tenant_addons_group_api(self):
        instance = self.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance missing, addons-group sync skipped.")
            return False
        for attr in self:
            url = f"{instance.url}/api/menu/addon-groups/{attr.company_id.ordertech_tenantId}"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            slugify = self.env['ir.http']._slugify
            slug = slugify(attr.name)
            payload = json.dumps({
                "name_en": attr.with_context(lang="en_US").name,
                "name_ar": attr.with_context(lang="ar_001").name,
                "slug": slug,
                "limit_min": attr.limit_min,
                "limit_max": attr.limit_max,
                "is_required": attr.is_required,
                "sort_order": 0
            })
            try:
                response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
                if response.status_code != 201:
                    _logger.error(
                        "OrderTech tenant addon-group sync failed for addon-group %s: %s ",
                        attr.id, response.text,
                    )
                    continue
                data = response.json()
                attr.sudo().write({
                    'ordertech_addons_groupId': data['id'],
                })
                _logger.info("Successfully synced addon-group data for addon-group %s", attr.id)
            except Exception as e:
                _logger.error(
                    "OrderTech API request error for addon-group %s: %s",
                    attr.id,
                    str(e),
                )

    def write(self, vals):
        trigger_update_attr = bool(ATTRIBUTE_TRACKED_FIELDS & vals.keys())
        res = super(ProductAttribute, self).write(vals)
        if trigger_update_attr:
            attributes = self.filtered(
                lambda attr: attr.ordertech_addons_groupId and attr.company_id.ordertech_tenantId and attr.is_addons
            )
            if attributes:
                attributes.update_tenant_addons_group_api()
        return res

    def update_tenant_addons_group_api(self):
        instance = self.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance is missing.")
            return False
        for attr in self:
            url = f"{instance.url}/api/menu/addon-groups/{attr.ordertech_addons_groupId}"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            slugify = self.env['ir.http']._slugify
            slug = slugify(attr.name)
            payload = json.dumps({
                "name_en": attr.with_context(lang="en_US").name,
                "name_ar": attr.with_context(lang="ar_001").name,
                "slug": slug,
                "limit_min": attr.limit_min,
                "limit_max": attr.limit_max,
                "is_required": attr.is_required,
                "sort_order": 0
            })
            try:
                response = requests.request("PUT", url, headers=headers, data=payload, timeout=10)
                if response.status_code != 200:
                    _logger.error(
                        "OrderTech tenant addons-group sync failed for addons-group %s: %s ",
                        attr.id, response.text,
                    )
                    continue
                _logger.info("Successfully synced addons-group update data for addons-group %s", attr.id)
            except Exception as e:
                _logger.error(
                    "OrderTech API request error for addons-group %s: %s",
                    attr.id,
                    str(e),
                )
        return True

    def action_sync_groups_to_ordertech(self):
        ordertech_attrs = self.filtered(
            lambda attr: attr.company_id and attr.company_id.ordertech_tenantId and attr.is_addons and not attr.ordertech_addons_groupId
        )
        if ordertech_attrs:
            ordertech_attrs.create_tenant_addons_group_api()
            if ordertech_attrs.value_ids:
                for value in ordertech_attrs.value_ids:
                    value.create_tenant_addon_item_api()
        return True