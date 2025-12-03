# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TwhSalesCommission(models.Model):
    """
    Model untuk tracking komisi sales
    """
    _name = 'twh.sales.commission'
    _description = 'TWH Sales Commission'
    _order = 'date desc, id desc'
    
    # References
    invoice_id = fields.Many2one('twh.invoice', string='Invoice', 
                                  required=True, ondelete='cascade')
    invoice_name = fields.Char(related='invoice_id.name', string='Invoice Number', store=True)
    sales_person_id = fields.Many2one('res.users', string='Sales Person', 
                                       required=True)
    product_id = fields.Many2one('product.product', string='Product', 
                                  required=True)
    
    # Quantity & Prices
    quantity = fields.Float(string='Quantity', required=True, 
                            digits='Product Unit of Measure')
    cost_price = fields.Monetary(string='Cost Price (Bayu)', required=True,
                                  currency_field='currency_id',
                                  help='Harga Bayu (harga dasar)')
    selling_price = fields.Monetary(string='Selling Price', required=True,
                                     currency_field='currency_id',
                                     help='Harga jual ke toko (A/B/Dealer)')
    margin = fields.Monetary(string='Margin per Unit', required=True,
                             currency_field='currency_id',
                             help='Selisih harga jual - harga bayu')
    commission_amount = fields.Monetary(string='Commission Amount', 
                                         required=True,
                                         currency_field='currency_id',
                                         help='Total komisi (margin x quantity)')
    
    # Date & Currency
    date = fields.Date(string='Commission Date', required=True, 
                       default=fields.Date.today, index=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                   default=lambda self: self.env.company.currency_id)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('paid', 'Paid'),
    ], string='Status', default='confirmed', tracking=True)
    
    # Payment
    payment_date = fields.Date(string='Payment Date')
    payment_notes = fields.Text(string='Payment Notes')
    
    # Company
    company_id = fields.Many2one('res.company', string='Company',
                                  default=lambda self: self.env.company)
    
    @api.model
    def get_commission_summary(self, sales_person_id=None, date_from=None, date_to=None):
        """
        Get commission summary for reporting
        """
        domain = [('state', 'in', ['confirmed', 'paid'])]
        
        if sales_person_id:
            domain.append(('sales_person_id', '=', sales_person_id))
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        
        commissions = self.search(domain)
        
        summary = {
            'total_commission': sum(commissions.mapped('commission_amount')),
            'total_quantity': sum(commissions.mapped('quantity')),
            'total_invoices': len(commissions.mapped('invoice_id')),
            'commissions': commissions,
        }
        
        return summary
    
    @api.model
    def get_monthly_commission(self, sales_person_id, year, month):
        """
        Get commission for specific month
        """
        date_from = fields.Date.from_string(f'{year}-{month:02d}-01')
        
        # Get last day of month
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        date_to = fields.Date.from_string(f'{year}-{month:02d}-{last_day}')
        
        return self.get_commission_summary(sales_person_id, date_from, date_to)
    
    def action_mark_paid(self):
        """Mark commission as paid"""
        for commission in self:
            commission.write({
                'state': 'paid',
                'payment_date': fields.Date.today(),
            })
    
    def action_confirm(self):
        """Confirm commission"""
        for commission in self:
            commission.write({'state': 'confirmed'})


class TwhCommissionReport(models.TransientModel):
    """
    Wizard for generating commission reports
    """
    _name = 'twh.commission.report.wizard'
    _description = 'TWH Commission Report Wizard'
    
    sales_person_id = fields.Many2one('res.users', string='Sales Person')
    date_from = fields.Date(string='Date From', required=True,
                            default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='Date To', required=True,
                          default=fields.Date.today)
    period_type = fields.Selection([
        ('custom', 'Custom Period'),
        ('this_month', 'This Month'),
        ('last_month', 'Last Month'),
        ('this_quarter', 'This Quarter'),
        ('this_year', 'This Year'),
    ], string='Period', default='this_month')
    
    @api.onchange('period_type')
    def _onchange_period_type(self):
        """Auto-set date range based on period type"""
        if self.period_type == 'this_month':
            today = fields.Date.today()
            self.date_from = today.replace(day=1)
            import calendar
            last_day = calendar.monthrange(today.year, today.month)[1]
            self.date_to = today.replace(day=last_day)
        
        elif self.period_type == 'last_month':
            today = fields.Date.today()
            first_day = today.replace(day=1)
            import datetime
            last_month = first_day - datetime.timedelta(days=1)
            self.date_from = last_month.replace(day=1)
            import calendar
            last_day = calendar.monthrange(last_month.year, last_month.month)[1]
            self.date_to = last_month.replace(day=last_day)
        
        elif self.period_type == 'this_year':
            today = fields.Date.today()
            self.date_from = today.replace(month=1, day=1)
            self.date_to = today.replace(month=12, day=31)
    
    def action_print_report(self):
        """Print commission report"""
        data = {
            'sales_person_id': self.sales_person_id.id if self.sales_person_id else False,
            'date_from': self.date_from,
            'date_to': self.date_to,
        }
        return self.env.ref('twh_racing_part.action_report_sales_commission').report_action(self, data=data)
    
    def action_export_excel(self):
        """Export commission to Excel"""
        commission_obj = self.env['twh.sales.commission']
        summary = commission_obj.get_commission_summary(
            self.sales_person_id.id if self.sales_person_id else None,
            self.date_from,
            self.date_to
        )
        
        # TODO: Implement Excel export
        raise UserError(_('Excel export will be implemented in next version'))