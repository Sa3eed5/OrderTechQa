import json
import logging

import requests

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)

CUSTOMER_TRACKED_FIELDS = {
    "name",
    "phone",
    "email"
}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    ordertech_customerId = fields.Char()
    ordertech_tenantId = fields.Char(related='company_id.ordertech_tenantId')
    ordertech_tenant_branchId = fields.Char(related='company_id.ordertech_tenant_branchId')

    def default_get(self, default_fields):
        defaults = super().default_get(default_fields)
        if not defaults.get('parent_id'):
            defaults['company_id'] = self.env.company.id
        return defaults

    # @api.constrains('email')
    # def _check_email(self):
    #     for rec in self:
    #         if rec.email and not email_normalize(rec.email):
    #             raise ValidationError(_("Invalid email format"))

    @api.model_create_multi
    def create(self, vals_list):
        partners = super(ResPartner, self).create(vals_list)

        customers = partners.filtered(
            lambda p: (
                    p.customer_rank
                    and p.company_id.parent_id.is_restaurant
                    and p.company_id.ordertech_tenantId
                    and p.company_id.ordertech_tenant_branchId
                    and not p.ordertech_customerId
            )
        )
        if customers:
            customers.create_tenant_customer_api()
        return partners

    def create_tenant_customer_api(self):
        instance = self.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance missing, customer sync skipped.")
            return False
        for customer in self:
            url = f"{instance.url}/api/customers/tenant/{customer.company_id.ordertech_tenantId}"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            payload = json.dumps({
                "full_name": customer.name,
                "phone_e164": customer.phone,
                # "email": customer.email,
            })
            try:
                response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
                if response.status_code != 201:
                    _logger.error(
                        "OrderTech tenant customer sync failed for customer %s: %s ",
                        customer.id, response.text,
                    )
                    continue
                data = response.json()
                customer.sudo().write({
                    'ordertech_customerId': data['id'],
                })
                _logger.info("Successfully synced customer data for customer %s", customer.id)
            except Exception as e:
                _logger.error(
                    "OrderTech API request error for customer %s: %s",
                    customer.id,
                    str(e),
                )

    def write(self, vals):
        trigger_update_cust = bool(CUSTOMER_TRACKED_FIELDS & vals.keys())
        res = super(ResPartner, self).write(vals)
        if trigger_update_cust:
            customers = self.filtered(
                lambda p: (
                        p.customer_rank
                        and p.ordertech_customerId
                        and p.company_id.parent_id.is_restaurant
                        and p.company_id.ordertech_tenantId
                        and p.company_id.ordertech_tenant_branchId
                )
            )
            if customers:
                customers.update_tenant_customer_api()
        return res

    def update_tenant_customer_api(self):
        instance = self.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance is missing.")
            return False
        for customer in self:
            url = f"{instance.url}/api/customers/{customer.ordertech_customerId}/tenant/{customer.company_id.ordertech_tenantId}"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            payload = json.dumps({
                "full_name": customer.name,
                "phone_e164": customer.phone,
                # "email": customer.email,
            })
            try:
                response = requests.request("PUT", url, headers=headers, data=payload, timeout=10)
                if response.status_code != 200:
                    _logger.error(
                        "OrderTech tenant customer sync failed for customer %s: %s ",
                        customer.id, response.text,
                    )
                    continue
                _logger.info("Successfully synced customer data update for customer %s", customer.id)
            except Exception as e:
                _logger.error(
                    "OrderTech API request error for customer %s: %s",
                    customer.id,
                    str(e),
                )
        return True

    def action_sync_customer_to_ordertech(self):
        customers = self.filtered(
            lambda p: (
                    p.customer_rank
                    and p.company_id.parent_id.is_restaurant
                    and p.company_id.ordertech_tenantId
                    and p.company_id.ordertech_tenant_branchId
                    and not p.ordertech_customerId
            )
        )
        if customers:
            customers.create_tenant_customer_api()

        return True

