import json
import logging

from odoo import http
from odoo.http import request
from .general_functions import valid_response, invalid_response, check_api_key

_logger = logging.getLogger(__name__)


class ResPartner(http.Controller):

    @http.route('/api/v1/customer', type='http', methods=['POST'], auth='public', csrf=False)
    def create_customer(self):
        if not check_api_key():
            return invalid_response(
                error='Unauthorized',
                status=401
            )
        try:
            args = request.httprequest.data.decode()
            vals = json.loads(args)
        except Exception as e:
            return invalid_response(
                error=f"invalid Json type : {str(e)}"
            )
        required_fields = ['ordertech_customerId', 'ordertech_tenant_branchId', 'name', 'phone']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            return invalid_response(
                error=f"Missing required field(s): {', '.join(missing_fields)}"
            )
        exists_customer = request.env['res.partner'].sudo().search([('ordertech_customerId','=',vals['ordertech_customerId'])],limit=1)
        if exists_customer:
            return valid_response(
                message="Customer already exists",
                data={
                    'ordertech_customerId': exists_customer.ordertech_customerId,
                    'name': exists_customer.name,
                },
                status=200
            )
        customer_vals = {
            "ordertech_customerId": vals['ordertech_customerId'],
            "ordertech_tenant_branchId": vals['ordertech_tenant_branchId'],
            "name": vals['name'],
            "phone": vals['phone'],
            "email": vals.get('email')
        }
        company = request.env['res.company'].sudo().search(
            [('ordertech_tenant_branchId', '=', vals['ordertech_tenant_branchId'])], limit=1)
        if not company:
            return invalid_response(
                error=f"tenant branch {vals['ordertech_tenant_branchId']} not found or not synced yet ",
            )
        customer_vals.update({
            "company_id": company.id,
            "customer_rank": 1
        })
        try:
            customer = request.env['res.partner'].sudo().create(customer_vals)
            if customer:
                return valid_response(
                    message="Customer created successfully",
                    status=201
                )
        except Exception as e:
            _logger.exception("Error create customers from ordertech api request")
            return invalid_response(
                error=str(e),
                status=400
            )
