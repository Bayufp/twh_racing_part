# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class TwhProductAnalytics(models.Model):
    """
    Model untuk analitik produk terlaris
    """
    _name = 'twh.product.analytics'
    _description = 'TWH Product Analytics'
    _auto = False  # This is a SQL view
    _order = 'total_quantity desc, total_value desc'
    
    # Product Info
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_name = fields.Char(string='Product Name', readonly=True)
    product_category = fields.Char(string='Category', readonly=True)
    
    # Sales Data
    total_quantity = fields.Float(string='Total Quantity Sold', readonly=True)
    total_value = fields.Monetary(string='Total Sales Value', readonly=True, 
                                   currency_field='currency_id')
    invoice_count = fields.Integer(string='Number of Invoices', readonly=True)
    avg_price = fields.Monetary(string='Average Price', readonly=True,
                                 currency_field='currency_id')
    
    # Period
    period_start = fields.Date(string='Period Start', readonly=True)
    period_end = fields.Date(string='Period End', readonly=True)
    
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    
    def init(self):
        """
        Create SQL view for analytics
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY SUM(il.quantity) DESC) as id,
                    il.product_id,
                    pt.name as product_name,
                    pt.twh_category as product_category,
                    SUM(il.quantity) as total_quantity,
                    SUM(il.subtotal) as total_value,
                    COUNT(DISTINCT il.invoice_id) as invoice_count,
                    AVG(il.price_unit) as avg_price,
                    MIN(inv.date_invoice) as period_start,
                    MAX(inv.date_invoice) as period_end,
                    inv.currency_id
                FROM
                    twh_invoice_line il
                    INNER JOIN twh_invoice inv ON il.invoice_id = inv.id
                    INNER JOIN product_product pp ON il.product_id = pp.id
                    INNER JOIN product_template pt ON pp.product_tmpl_id = pt.id
                WHERE
                    inv.state IN ('confirmed', 'paid')
                GROUP BY
                    il.product_id,
                    pt.name,
                    pt.twh_category,
                    inv.currency_id
            )
        """ % self._table)


class TwhAnalyticsWizard(models.TransientModel):
    """
    Wizard untuk filter analytics
    """
    _name = 'twh.analytics.wizard'
    _description = 'TWH Analytics Filter Wizard'
    
    period_type = fields.Selection([
        ('this_month', 'This Month'),
        ('last_3_months', 'Last 3 Months'),
        ('last_6_months', 'Last 6 Months'),
        ('this_year', 'This Year'),
        ('custom', 'Custom Period'),
    ], string='Period', default='this_month', required=True)
    
    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To', default=fields.Date.today)
    
    top_n = fields.Integer(string='Top N Products', default=10)
    
    sort_by = fields.Selection([
        ('quantity', 'By Quantity'),
        ('value', 'By Sales Value'),
    ], string='Sort By', default='quantity')
    
    @api.onchange('period_type')
    def _onchange_period_type(self):
        """Auto calculate date range"""
        today = fields.Date.today()
        
        if self.period_type == 'this_month':
            self.date_from = today.replace(day=1)
            self.date_to = today
        
        elif self.period_type == 'last_3_months':
            self.date_from = today - relativedelta(months=3)
            self.date_to = today
        
        elif self.period_type == 'last_6_months':
            self.date_from = today - relativedelta(months=6)
            self.date_to = today
        
        elif self.period_type == 'this_year':
            self.date_from = today.replace(month=1, day=1)
            self.date_to = today
    
    def action_view_analytics(self):
        """View analytics dashboard"""
        self.ensure_one()
        
        # Get data
        data = self._get_analytics_data()
        
        # Return tree view with domain
        return {
            'name': _('Product Analytics'),
            'type': 'ir.actions.act_window',
            'res_model': 'twh.product.analytics.result',
            'view_mode': 'tree,graph,pivot',
            'domain': [],
            'context': {
                'default_period_type': self.period_type,
                'analytics_data': data,
            },
        }
    
    def action_export_excel(self):
        """Export to Excel"""
        # TODO: Implement Excel export
        pass
    
    def _get_analytics_data(self):
        """
        Get analytics data based on filters
        """
        domain = [
            ('invoice_id.state', 'in', ['confirmed', 'paid']),
        ]
        
        if self.date_from:
            domain.append(('invoice_id.date_invoice', '>=', self.date_from))
        if self.date_to:
            domain.append(('invoice_id.date_invoice', '<=', self.date_to))
        
        # Query invoice lines
        invoice_lines = self.env['twh.invoice.line'].search(domain)
        
        # Group by product
        product_data = {}
        for line in invoice_lines:
            product_id = line.product_id.id
            if product_id not in product_data:
                product_data[product_id] = {
                    'product_id': product_id,
                    'product_name': line.product_id.name,
                    'total_quantity': 0,
                    'total_value': 0,
                    'invoice_count': set(),
                }
            
            product_data[product_id]['total_quantity'] += line.quantity
            product_data[product_id]['total_value'] += line.subtotal
            product_data[product_id]['invoice_count'].add(line.invoice_id.id)
        
        # Convert to list and count invoices
        result = []
        for data in product_data.values():
            data['invoice_count'] = len(data['invoice_count'])
            result.append(data)
        
        # Sort
        if self.sort_by == 'quantity':
            result.sort(key=lambda x: x['total_quantity'], reverse=True)
        else:
            result.sort(key=lambda x: x['total_value'], reverse=True)
        
        # Get top N
        if self.top_n > 0:
            result = result[:self.top_n]
        
        return result


class TwhAnalyticsResult(models.TransientModel):
    """
    Transient model untuk menampilkan hasil analytics
    """
    _name = 'twh.product.analytics.result'
    _description = 'TWH Analytics Result'
    
    product_id = fields.Many2one('product.product', string='Product')
    product_name = fields.Char(string='Product Name')
    total_quantity = fields.Float(string='Total Quantity')
    total_value = fields.Monetary(string='Total Value', currency_field='currency_id')
    invoice_count = fields.Integer(string='Invoice Count')
    avg_price = fields.Monetary(string='Avg Price', compute='_compute_avg_price',
                                 currency_field='currency_id')
    rank = fields.Integer(string='Rank')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    @api.depends('total_value', 'total_quantity')
    def _compute_avg_price(self):
        for record in self:
            if record.total_quantity > 0:
                record.avg_price = record.total_value / record.total_quantity
            else:
                record.avg_price = 0.0


class TwhDashboard(models.Model):
    """
    Model untuk dashboard metrics
    """
    _name = 'twh.dashboard'
    _description = 'TWH Dashboard Metrics'
    
    @api.model
    def get_dashboard_data(self, period='this_month'):
        """
        Get dashboard data untuk widget
        """
        today = fields.Date.today()
        
        # Calculate date range
        if period == 'this_month':
            date_from = today.replace(day=1)
            date_to = today
        elif period == 'last_3_months':
            date_from = today - relativedelta(months=3)
            date_to = today
        elif period == 'last_6_months':
            date_from = today - relativedelta(months=6)
            date_to = today
        elif period == 'this_year':
            date_from = today.replace(month=1, day=1)
            date_to = today
        else:
            date_from = today.replace(month=1, day=1)
            date_to = today
        
        # Query data
        invoices = self.env['twh.invoice'].search([
            ('date_invoice', '>=', date_from),
            ('date_invoice', '<=', date_to),
            ('state', 'in', ['confirmed', 'paid']),
        ])
        
        # Calculate metrics
        total_sales = sum(invoices.mapped('total'))
        total_invoices = len(invoices)
        total_commission = sum(invoices.mapped('total_commission'))
        
        # Get top products
        invoice_lines = invoices.mapped('invoice_line_ids')
        product_sales = {}
        for line in invoice_lines:
            product_id = line.product_id.id
            if product_id not in product_sales:
                product_sales[product_id] = {
                    'product': line.product_id,
                    'quantity': 0,
                    'value': 0,
                }
            product_sales[product_id]['quantity'] += line.quantity
            product_sales[product_id]['value'] += line.subtotal
        
        # Sort by quantity
        top_products = sorted(product_sales.values(), 
                              key=lambda x: x['quantity'], 
                              reverse=True)[:10]
        
        return {
            'total_sales': total_sales,
            'total_invoices': total_invoices,
            'total_commission': total_commission,
            'avg_invoice_value': total_sales / total_invoices if total_invoices > 0 else 0,
            'top_products_by_qty': top_products,
            'period': period,
            'date_from': date_from,
            'date_to': date_to,
        }