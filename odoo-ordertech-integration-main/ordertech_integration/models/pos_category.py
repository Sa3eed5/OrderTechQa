import json
import logging

import requests

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class PosCategory(models.Model):
    _inherit = 'pos.category'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id, index=True)
    ordertech_categId = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        categroies = super(PosCategory, self).create(vals_list)
        ordertech_categories = categroies.filtered(
            lambda c: c.company_id and c.company_id.ordertech_tenantId
        )
        if ordertech_categories:
            ordertech_categories.create_tenant_category_api()

        return categroies

    def create_tenant_category_api(self):
        instance = self.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance missing, branch sync skipped.")
            return False
        for categ in self:
            url = f"{instance.url}/api/menu/categories/{categ.company_id.ordertech_tenantId}"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            slugify = self.env['ir.http']._slugify
            slug = slugify(categ.name)
            payload = json.dumps({
                "name_en": categ.with_context(lang="en_US").name,
                "name_ar": categ.with_context(lang="ar_001").name,
                "slug": slug,
                "is_active": True,
                "sort_order": 0
            })
            try:
                response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
                if response.status_code != 201:
                    _logger.error(
                        "OrderTech tenant category sync failed for category %s: %s ",
                        categ.id, response.text,
                    )
                    continue
                data = response.json()
                categ.sudo().write({
                    'ordertech_categId': data['id'],
                })
                _logger.info("Successfully synced category data for category %s", categ.id)
            except Exception as e:
                _logger.error(
                    "OrderTech API request error for categ %s: %s",
                    categ.id,
                    str(e),
                )

    def write(self, vals):
        res = super(PosCategory, self).write(vals)
        if "name" in vals:
            categories = self.filtered(
                lambda c: c.ordertech_categId  and c.company_id.ordertech_tenantId
            )
            if categories:
                categories.update_tenant_categId_api()
        return res

    def update_tenant_categId_api(self):
        instance = self.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance is missing.")
            return False
        for categ in self:
            url = f"{instance.url}/api/menu/categories/{categ.ordertech_categId}"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            slugify = self.env['ir.http']._slugify
            slug = slugify(categ.name)
            payload = json.dumps({
                "name_en": categ.with_context(lang="en_US").name,
                "name_ar": categ.with_context(lang="ar_001").name,
                "slug": slug,
                "is_active": True,
                "sort_order": 0
            })
            try:
                response = requests.request("PUT", url, headers=headers, data=payload, timeout=10)
                if response.status_code != 200:
                    _logger.error(
                        "OrderTech tenant category sync failed for category %s: %s ",
                        categ.id, response.text,
                    )
                    continue
                _logger.info("Successfully synced category update data for category %s", categ.id)
            except Exception as e:
                _logger.error(
                    "OrderTech API request error for category %s: %s",
                    categ.id,
                    str(e),
                )
        return True

    def action_sync_category_to_ordertech(self):
        ordertech_categories = self.filtered(
            lambda c: c.company_id and c.company_id.ordertech_tenantId and not c.ordertech_categId
        )
        if ordertech_categories:
            ordertech_categories.create_tenant_category_api()
        return True