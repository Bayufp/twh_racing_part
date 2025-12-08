# -*- coding: utf-8 -*-
{
    'name': 'TWH Racing Part - Distributor Management',
    'version': '17.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Manajemen Invoice, Komisi Sales, dan Analitik untuk Distributor Sparepart Motor',
    'description': """
        TWH Racing Part Distribution System
        =====================================
        
        Fitur Utama:
        ------------
        * Invoice Management dengan Price List Multi-tier (Bayu, Dealer, A, B, HET)
        * Sales Commission Calculation otomatis
        * Due Date Reminder System
        * Product Analytics & Best Seller Tracking
        * Custom Reports & Dashboard
        
        Cocok untuk:
        ------------
        * Distributor Sparepart Motor
        * Wholesaler dengan multi-tier pricing
        * Sales team dengan komisi berbasis margin
    """,
    'author': 'TWH Racing Part',
    'website': 'https://www.twhracingpart.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale_management',
        'account',
        'product',
        'stock',
    ],

    'data': [
        # Security
        'security/twh_security.xml',
        'security/ir.model.access.csv',

        # Views
        'views/action_views.xml',
        'views/menu_views.xml',
        'views/dashboard_views.xml',
        'views/sale_order_views.xml',
        'views/twh_invoice_views.xml',
        'views/sales_commission_views.xml',
        'views/due_reminder_views.xml',
        'views/product_analytics_views.xml',
        'views/twh_pricelist_views.xml',

        # Data
        'data/product_categories.xml',
        'data/price_list_data.xml',
        'data/cron_due_reminder.xml',
        'data/demo_products.xml',

        # Reports
        'report/invoice_report_template.xml',
        'report/commission_report_template.xml',
        'report/report_action.xml',
    ],

    'demo': [
        'demo/demo_data.xml',
    ],

    'assets': {
    'web.assets_backend': [
        # Library ApexCharts
        'twh_racing_part/static/lib/apexcharts/apexcharts.min.js',
        'twh_racing_part/static/lib/apexcharts/apexcharts.css',

        # CSS
        'twh_racing_part/static/src/css/twh_dashboard.css',

        # JS
        'twh_racing_part/static/src/js/twh_dashboard.js',

        # XML Template
        'twh_racing_part/static/src/xml/dashboard_template.xml',
    ],
},

    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 1,
}
