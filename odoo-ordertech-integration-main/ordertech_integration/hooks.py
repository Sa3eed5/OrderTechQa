import secrets
import logging

_logger = logging.getLogger(__name__)

def post_init_generate_api_key(env):
    try:
        instance = env.ref('ordertech_integration.default_ordertech_instance').sudo()
        if not instance.api_key:
            new_key = secrets.token_hex(32)
            instance.api_key = new_key
            _logger.info("OrderTech API key generated successfully.")
    except ValueError:
        _logger.warning("Default OrderTech instance not found")