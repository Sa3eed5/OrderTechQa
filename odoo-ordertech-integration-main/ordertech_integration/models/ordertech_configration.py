import secrets

from odoo import models, fields, _


class OrderTechConfigration(models.Model):
    _name = 'ordertech.configration'
    _description = 'OrderTech Connector'


    name = fields.Char(string='Instance Name',required=True)
    url = fields.Char(string='OrderTech URL', required=True)
    api_key = fields.Char(string='API Key')
    ordertech_token = fields.Char(string='OrderTech Token')

    def refresh_api_key(self):
        for rec in self:
            saved_key = secrets.token_hex(32)
            rec.api_key = saved_key