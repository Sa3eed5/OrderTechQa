from  odoo import models, fields, api



class PosOrder(models.Model):
    _inherit = 'pos.order'

    ordertech_orderId = fields.Char()