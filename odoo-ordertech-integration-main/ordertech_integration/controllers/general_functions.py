from odoo.http import request
import secrets


def get_api_key():
    instance = request.env.ref('ordertech_integration.default_ordertech_instance').sudo()
    saved_key = instance.api_key
    return saved_key

def check_api_key():
    request_key = request.httprequest.headers.get('X-API-KEY')
    saved_key = get_api_key()
    return request_key == saved_key

def valid_response(message=None, data=None, status=200):
    response_body = {
        key: value for key, value in {
            "message": message,
            "data": data
        }.items() if value is not None
    }
    return request.make_json_response(response_body,status=status)

def invalid_response(error,status=400):
    response_body = {
        'error': error,
    }
    return request.make_json_response(response_body, status=status)

def zero_pad(num, size):
    return str(num).zfill(size)

def generate_unique_id(session):
    # session.id → 5 digits
    part1 = zero_pad(session.id, 5)

    # odoo.login_number → 3 digits
    login_number = session.user_id.id or 0
    part2 = zero_pad(int(login_number), 3)

    # getNextSequenceNumber() → 4 digits
    last_order = session.order_ids.sorted('sequence_number')[-1:]  # last order
    next_seq = (last_order.sequence_number if last_order else 0) + 1
    part3 = zero_pad(next_seq, 4)

    return f"{part1}-{part2}-{part3}"
