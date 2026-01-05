import json
import logging

import requests

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

TENANT_TRACKED_FIELDS = {
    "name",
    "phone",
    "email",
    "opening_time",
    "closing_time",
}
BRANCH_TRACKED_FIELDS = {
    "name",
    "phone",
    "email",
    "street",
    "street2",
    "city",
    "state_id",
    "zip",
    "delivery_radius_km",
    "notes"
    "opening_time",
    "closing_time",
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    is_restaurant = fields.Boolean()
    is_branch = fields.Boolean()
    opening_time = fields.Float()
    closing_time = fields.Float()
    ordertech_tenantId = fields.Char()
    ordertech_tenant_branchId = fields.Char()
    delivery_radius_km = fields.Integer(default=1)
    notes = fields.Char()

    @api.onchange('parent_id')
    def check_branch(self):
        for rec in self:
            rec.is_branch = True if rec.parent_id else False

    @api.constrains('opening_time', 'closing_time')
    def _check_time_range(self):
        for record in self:
            for field_name in ['opening_time', 'closing_time']:
                value = getattr(record, field_name)
                if value < 0 or value >= 24:
                    raise ValidationError("Time must be between 00:00 and 23:59.")

    def float_to_time(self, time_float):
        if time_float is None:
            return "00:00"
        hours = int(time_float)
        minutes = int(round((time_float - hours) * 60))
        return f"{hours:02d}:{minutes:02d}"

    def time_to_float(self, time_str):
        if not time_str:
            return 0.0
        hours, minutes = map(int, time_str.split(":"))
        return hours + (minutes / 60.0)

    def sync_ordertech_restaurant(self):
        instance = self.env.ref('ordertech_integration.default_ordertech_instance')
        if not instance or not instance.ordertech_token:
            raise UserError("OrderTech instance is missing.")
        for company in self:
            url = f"{instance.url}/api/tenants/my-restaurants"
            headers = {
                'accept': '*/*',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            try:
                response = requests.request("GET", url, headers=headers)
                if response.status_code != 200:
                    _logger.warning("OrderTech API returned  %s for company %s", response.text, company.id)
                response = response.json()
                if not response:
                    _logger.warning("OrderTech API returned an empty restaurant list")
                    return
                data = response[0]  # get first restaurant
                opening_time = self.time_to_float(data.get('opening_time', '00:00'))
                closing_time = self.time_to_float(data.get('closing_time', '00:00'))
                company.sudo().write({
                    'is_restaurant': True,
                    'ordertech_tenantId': data.get('id'),
                    'name': data.get('name_display'),
                    'phone': data.get('phone'),
                    'email': data.get('email'),
                    'opening_time': opening_time,
                    'closing_time': closing_time,
                })
                _logger.info("Successfully synced restaurant data for company %s", company.id)
            except requests.RequestException as req_e:
                _logger.error("Request error syncing company %s: %s", company.id, req_e, exc_info=True)
            except Exception as e:
                _logger.error("Unexpected error syncing company %s: %s", company.id, e, exc_info=True)

    def write(self, vals):
        trigger_update_rest = bool(TENANT_TRACKED_FIELDS & vals.keys())
        trigger_update_branch = bool(TENANT_TRACKED_FIELDS & vals.keys())
        res = super(ResCompany, self).write(vals)
        if trigger_update_rest:
            companies = self.filtered(
                lambda c: c.is_restaurant and c.ordertech_tenantId
            )
            companies.update_tenant_api()
        if trigger_update_branch:
            branches = self.filtered(
                lambda b: b.is_branch and b.parent_id.ordertech_tenantId and b.ordertech_tenant_branchId
            )
            branches.update_tenant_branch_api()
        return res

    def update_tenant_api(self):
        instance = self.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance is missing.")
            return False
        for company in self:
            url = f"{instance.url}/api/tenants/{company.ordertech_tenantId}"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            payload = json.dumps({
                'name': company.name,
                'email': company.email,
                'phone': company.phone,
                'openingTime': company.float_to_time(company.opening_time),
                'closingTime': company.float_to_time(company.closing_time),
            })
            try:
                response = requests.request("PUT", url, headers=headers, data=payload, timeout=10)
                if response.status_code != 200:
                    _logger.error(
                        "OrderTech tenant sync failed for company %s: %s",
                        company.id,response.text,
                    )
                _logger.info("Successfully synced restaurant update data for company %s", company.id)
            except requests.exceptions.RequestException as e:
                _logger.error(
                    "OrderTech API request error for company %s : %s",
                    company.id,
                    str(e),
                )
        return True

    def update_tenant_branch_api(self):
        instance = self.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance is missing.")
            return False
        for branch in self:
            url = f"{instance.url}/api/branches/{branch.ordertech_tenant_branchId}"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            slugify = self.env['ir.http']._slugify
            slug = slugify(branch.name)
            timezone = self.env.context.get('tz')
            payload = json.dumps({
                "name": branch.name,
                "slug": slug,
                "status": "open",
                "timezone": timezone,
                "addressLine1": branch.street,
                "addressLine2": branch.street2,
                "city": branch.state_id.name,
                "region": branch.city,
                "postalCode": branch.zip,
                "countryCode": branch.country_code,
                "phonePublic": branch.phone,
                "email": branch.email,
                "deliveryRadiusKm": branch.delivery_radius_km,
                "notes": branch.notes,
                "openingTime": branch.float_to_time(branch.opening_time),
                "closingTime": branch.float_to_time(branch.closing_time)
            })
            try:
                response = requests.request("PUT", url, headers=headers, data=payload, timeout=10)
                if response.status_code != 200:
                    _logger.error(
                        "OrderTech tenant sync failed for branch %s : %s",
                        branch.id,response.text,
                    )
                _logger.info("Successfully synced branch update data for company %s", branch.id)
            except Exception as e:
                _logger.error(
                    "OrderTech API request error for branch %s: %s",
                    branch.id,
                    str(e),
                )
        return True

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)

        # Filter only valid branch records
        branches = companies.filtered(
            lambda c: c.is_branch and c.parent_id and c.parent_id.ordertech_tenantId
        )
        if branches:
            branches.create_tenant_branch_api()
        return companies

    def create_tenant_branch_api(self):
        instance = self.env.ref("ordertech_integration.default_ordertech_instance")
        if not instance or not instance.ordertech_token:
            _logger.error("OrderTech instance missing, branch sync skipped.")
            return False
        for branch in self:
            url = f"{instance.url}/api/branches"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            slugify = self.env['ir.http']._slugify
            slug = slugify(branch.name)
            tenantId = branch.parent_id.ordertech_tenantId
            timezone = self.env.context.get('tz')
            payload = json.dumps({
                "name": branch.name,
                "slug": slug,
                "tenantId": tenantId,
                "status": "open",
                "timezone": timezone,
                "addressLine1": branch.street,
                "addressLine2": branch.street2,
                "city": branch.state_id.name,
                "region": branch.city,
                "postalCode": branch.zip,
                "countryCode": branch.country_code,
                "phonePublic": branch.phone,
                "email": branch.email,
                "deliveryRadiusKm": branch.delivery_radius_km,
                "notes": branch.notes,
                "openingTime": branch.float_to_time(branch.opening_time),
                "closingTime": branch.float_to_time(branch.closing_time)
            })
            try:
                response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
                if response.status_code != 201:
                    _logger.error(
                        "OrderTech tenant branch sync failed for branch %s: %s ",
                        branch.id,response.text,
                    )
                    continue
                data = response.json()
                branch.sudo().write({
                    'ordertech_tenant_branchId': data['id'],
                    'ordertech_tenantId': data['tenantId'],
                })
                _logger.info("Successfully synced branch data for branch %s", branch.id)
            except Exception as e:
                _logger.error(
                    "OrderTech API request error for branch %s: %s",
                    branch.id,
                    str(e),
                )

    def action_sync_branch_to_ordertech(self):
        branches = self.filtered(
            lambda c: c.is_branch and c.parent_id and c.parent_id.ordertech_tenantId and not c.ordertech_tenant_branchId
        )
        if branches:
            branches.create_tenant_branch_api()

        return True