import json
import logging

from odoo import http
from odoo.http import request
from .general_functions import invalid_response, check_api_key

_logger = logging.getLogger(__name__)


class PermanentToken(http.Controller):

    @http.route('/api/ordertech/register', methods=['POST'], type='http', auth="none", csrf=False)
    def register_ordertech(self):
        if not check_api_key():
            return invalid_response(
                error='Unauthorized: you have no permission to access these data!',
                status=401
            )

        try:
            args = request.httprequest.data.decode()
            vals = json.loads(args)
        except Exception as e:
            return invalid_response(
                error=f"invalid Json type : {str(e)}"
            )
        permanent_token = vals.get('platform_jwt_token')
        instance = request.env.ref("ordertech_integration.default_ordertech_instance")
        try:
            instance.sudo().write({
                'ordertech_token' : permanent_token
            })
        except Exception as e:
            _logger.error(e)