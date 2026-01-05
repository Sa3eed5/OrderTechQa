# -*- coding: utf-8 -*-

{
    'name': "OrderTech Integration",

    'summary': """ """,

    'description': """ """,

    'author': "Tarek Ashry",

    'version': '18.0.1.0',

    'depends': [
        'base',
        'base_geolocalize',
        'account',
        'point_of_sale',
        'pos_preparation_display'
    ],
    'external_dependencies': {
        'python': ['phonenumbers'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/ordertech_configration.xml',
        'data/ordertech_product_attributes.xml',
        'views/ordertech_configration_view.xml',
        'views/res_company_view.xml',
        'views/ordertech_restaurant_view.xml',
        'views/ordertech_branch_view.xml',
        'views/res_partner_view.xml',
        'views/ordertech_customer_view.xml',
        'views/pos_category_view.xml',
        'views/ordertech_category_view.xml',
        'views/product_template_view.xml',
        'views/ordertech_product_view.xml',
        'views/product_attribute_view.xml',
        'views/ordertech_addons_view.xml',
        'views/pos_order_view.xml',
        'views/ordertech_order_view.xml',

    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'ordertech_integration/static/src/**/*',
        ],
    },
    'post_init_hook': 'post_init_generate_api_key',
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'AGPL-3',
}
