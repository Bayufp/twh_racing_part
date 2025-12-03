# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResPartner(models.Model):
    """
    Extend res.partner untuk tambahkan field TWH-specific
    """
    _inherit = 'res.partner'
    
    # TWH Specific Fields
    is_twh_customer = fields.Boolean(string='TWH Customer', default=False)
    twh_customer_code = fields.Char(string='Customer Code')
    twh_discount_percent = fields.Float(string='Special Discount (%)', 
                                         default=0.0, digits='Discount',
                                         help='Discount khusus untuk customer ini (e.g., 3%)')
    
    # Customer Type
    twh_customer_type = fields.Selection([
        ('retail', 'Retail Store'),
        ('workshop', 'Workshop'),
        ('dealer', 'Dealer'),
        ('distributor', 'Distributor'),
    ], string='Customer Type')
    
    # Invoice Statistics
    twh_invoice_ids = fields.One2many('twh.invoice', 'partner_id', string='TWH Invoices')
    twh_invoice_count = fields.Integer(string='Invoice Count', 
                                         compute='_compute_twh_invoice_stats')
    twh_total_invoiced = fields.Monetary(string='Total Invoiced', 
                                          compute='_compute_twh_invoice_stats',
                                          currency_field='currency_id')
    twh_total_outstanding = fields.Monetary(string='Outstanding Amount',
                                             compute='_compute_twh_invoice_stats',
                                             currency_field='currency_id')
    
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    @api.depends('twh_invoice_ids', 'twh_invoice_ids.state', 'twh_invoice_ids.total')
    def _compute_twh_invoice_stats(self):
        for partner in self:
            invoices = partner.twh_invoice_ids.filtered(
                lambda inv: inv.state in ['confirmed', 'paid', 'overdue']
            )
            partner.twh_invoice_count = len(invoices)
            partner.twh_total_invoiced = sum(invoices.mapped('total'))
            
            outstanding_invoices = invoices.filtered(
                lambda inv: inv.state in ['confirmed', 'overdue']
            )
            partner.twh_total_outstanding = sum(outstanding_invoices.mapped('total'))
    
    def action_view_twh_invoices(self):
        """
        Action untuk view invoices customer ini
        """
        self.ensure_one()
        return {
            'name': _('TWH Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'twh.invoice',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }