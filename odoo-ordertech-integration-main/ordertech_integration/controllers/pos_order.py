import json
import logging
from uuid import uuid4

import requests

from odoo import http
from odoo.http import request
from .general_functions import invalid_response, check_api_key, generate_unique_id, valid_response

_logger = logging.getLogger(__name__)


class PosOrder(http.Controller):

    @http.route('/api/v1/order', type='http', methods=['POST'], auth='public', csrf=False)
    def create_order(self):
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
        required_fields = ['ordertech_orderId', 'company_id', 'customer_id', 'product_id', 'qty']
        missing_fields = [field for field in required_fields if not vals.get(field)]

        if missing_fields:
            return invalid_response(
                error=f"Missing required field(s): {', '.join(missing_fields)}"
            )
        existing = request.env['pos.order'].sudo().search([('ordertech_orderId', '=', vals.get('ordertech_orderId'))],
                                                          limit=1)
        if existing:
            return valid_response(
                message="order already exists",
                data={
                    'orderId': existing.id,
                    'order_number': existing.tracking_number,
                    'order_ref': existing.name,
                    'receipt_number': existing.pos_reference,
                    'status': existing.state,
                },
                status=200
            )
        company_id = request.env['res.company'].sudo().search([('ordertech_tenant_branchId', '=', vals['company_id'])],
                                                              limit=1)
        if not company_id:
            return invalid_response(
                error=f"Company not found with this id : {vals['company_id']}"
            )
        session = request.env['pos.session'].sudo().search([
            ('state', '=', 'opened'),
            ('company_id', '=', company_id.id)
        ], limit=1)

        if not session:
            return invalid_response(
                error="No open POS session"
            )
        partner_id = request.env['res.partner'].sudo().search([('ordertech_customerId', '=', vals['customer_id'])],
                                                              limit=1)
        if not partner_id:
            return invalid_response(
                error=f"Customer not found with this id : {vals['customer_id']}"
            )
        product_tmpl_id = request.env['product.template'].sudo().search(
            [('ordertech_productId', '=', vals['product_id'])])
        if not product_tmpl_id:
            return invalid_response(
                error=f"Product not found with this id : {vals['product_id']}"
            )
        product_id = product_tmpl_id.product_variant_id
        tmpl_values = request.env['product.template.attribute.value'].sudo().search(
            [('product_tmpl_id', '=', product_tmpl_id.id)])
        value_ids = []
        price_extra = 0
        if vals.get('attributes'):
            for val in vals['attributes']:
                value_id = tmpl_values.filtered(
                    lambda v: (
                            v.product_tmpl_id.ordertech_productId == vals['product_id']
                            and v.attribute_id.ordertech_addons_groupId == val.get('group_id')
                            and v.product_attribute_value_id.ordertech_addons_itemId == val.get('item_id')
                    )
                )
                if not value_id:
                    return invalid_response(
                        error=f"Not found addons group_id: {val.get('group_id')} or item_id: {val.get('item_id')}"
                    )
                value_ids.append(value_id.id)
                if value_id.price_extra:
                    price_extra += value_id.price_extra

        if vals.get("size_value"):
            value_id = tmpl_values.filtered(
                lambda v: (
                        v.name.strip().lower() == vals['size_value'].strip().lower()
                        and v.attribute_id.id == request.env.ref(
                    "ordertech_integration.ordertech_product_sizes_attribute").id
                        and v.product_tmpl_id.id == product_tmpl_id.id
                )
            )
            if not value_id:
                return invalid_response(
                    error=f"Size value {vals['size_value']} not found"
                )
            value_ids.append(value_id.id)
            if value_id.price_extra:
                price_extra += value_id.price_extra

        qty = float(vals['qty'])
        if qty <= 0:
            return invalid_response(
                error="Invalid qty value must be greater than 0"
            )
        uniq_id = generate_unique_id(session)
        order_data = {
            'session_id': session.id,
            'company_id': session.company_id.id,
            'config_id': session.config_id.id,
            'picking_type_id': session.config_id.picking_type_id.id,
            'sequence_number': int(uniq_id.split('-')[-1]),
            'uuid': str(uuid4()),
            'name': f"Order {uniq_id}",
            'state': 'draft',
            'partner_id': partner_id.id,
            'amount_paid': 0.0,
            'amount_tax': 0.0,
            'amount_total': 0.0,
            'amount_return': 0.0,
            'general_note': 'OrderTech',
            'ordertech_orderId': vals.get('ordertech_orderId'),
            'lines': [
                (0, 0, {
                    'product_id': product_id.id,
                    'qty': qty,
                    'price_unit': product_id.lst_price + price_extra,
                    'price_extra': price_extra,
                    'price_subtotal': qty * (product_id.lst_price + price_extra),
                    'price_subtotal_incl': qty * (product_id.lst_price + price_extra),
                    'uuid': str(uuid4()),
                    'attribute_value_ids': [(6, 0, value_ids)],
                })
            ]
        }
        pos_order = request.env['pos.order'].sudo()
        try:
            process_order = pos_order._process_order(order_data, False)
        except Exception as e:
            _logger.exception("Error create order from ordertech api request")
            return invalid_response(
                error=str(e),
                status=400
            )
        order = pos_order.browse(process_order)
        order._compute_prices()
        return valid_response(
            message="order created successfully",
            data={
                'orderId': order.id,
                'order_number': order.tracking_number,
                'receipt_number': order.pos_reference,
                'status': order.state,
            },
            status=201
        )

    @http.route('/pos/order/webhook', type='json', auth='user')
    def pos_order_webhook(self, **data):
        order_id = data.get('order_id')
        order = request.env['pos.order'].sudo().search([
            ('id', '=', order_id)
        ], limit=1)
        if order.ordertech_orderId:
            instance = request.env.ref("ordertech_integration.default_ordertech_instance")
            if not instance or not instance.ordertech_token:
                _logger.error("OrderTech instance missing, order status sync skipped.")
                return False
            url = f"{instance.url}/api/integrations/odoo/webhook/order-status"
            headers = {
                'accept': '*/*',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {instance.ordertech_token}'
            }
            payload = json.dumps({
                "order_id": order.ordertech_orderId,
                "status": "preparing",
            })
            try:
                response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
                if response.status_code != 201:
                    _logger.error(
                        "OrderTech update order status failed for order %s: %s ",
                        order.id, response.text,
                    )
                    return False
                _logger.info("Successfully update order status for order %s", order.id)
            except Exception as e:
                _logger.error(
                    "OrderTech API request error for order %s: %s",
                    order.id,
                    str(e),
                )

