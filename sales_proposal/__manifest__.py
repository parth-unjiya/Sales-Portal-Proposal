# -*- coding: utf-8 -*-
{
    'name': "sales_praposal",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Sales Proposal Module
    """,

    'author': "Parth-Unjiya",
    'category': 'Uncategorized',
    'version': '16.0.1',

    'depends': ['base', 'mail', 'sale', 'sale_management'],

    'data': [
        'security/ir.model.access.csv',
        'views/sales_proposal_line_view.xml',
        'views/sales_proposal_view.xml',
        'views/templates.xml',
        'views/menus.xml',
        'data/proposal_sequence.xml'
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'sales_proposal/static/src/js/sales_proposal_portal.js',
            'sales_proposal/static/src/xml/sales_proposal_portal.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}
