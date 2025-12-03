# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta


class TwhInvoice(models.Model):
    """
    Model Invoice TWH Racing Part
    Extended dari account.move untuk custom invoice
    """
    _name = 'twh.invoice'
    _description = 'TWH Invoice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_invoice desc, id desc'
    
    # Basic Info
    name = fields.Char(string='Invoice Number', required=True, copy=False, 
                       default='New', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Customer/Toko', 
                                  required=True, tracking=True,
                                  domain=[('is_company', '=', True)])
    date_invoice = fields.Date(string='Invoice Date', required=True, 
                                default=fields.Date.today, tracking=True)
    
    # Sales Info
    sales_person_id = fields.Many2one('res.users', string='Sales Person', 
                                       default=lambda self: self.env.user,
                                       tracking=True)
    price_tier = fields.Selection([
        ('price_a', 'Harga A'),
        ('price_b', 'Harga B'),
        ('dealer', 'Dealer'),
    ], string='Price Tier', required=True, default='price_a', tracking=True)
    
    # Invoice Lines
    invoice_line_ids = fields.One2many('twh.invoice.line', 'invoice_id', 
                                        string='Invoice Lines')
    
    # Financial
    subtotal = fields.Monetary(string='Subtotal', compute='_compute_amounts', 
                                store=True, currency_field='currency_id')
    discount_percent = fields.Float(string='Discount (%)', default=0.0, 
                                     digits='Discount', tracking=True)
    discount_amount = fields.Monetary(string='Discount Amount', 
                                       compute='_compute_amounts', store=True,
                                       currency_field='currency_id')
    total = fields.Monetary(string='Total', compute='_compute_amounts', 
                            store=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                   default=lambda self: self.env.company.currency_id)
    
    # Payment Terms
    payment_term_days = fields.Integer(string='Payment Terms (Days)', 
                                        default=60, tracking=True)
    date_due = fields.Date(string='Due Date', compute='_compute_due_date', 
                           store=True, tracking=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    
    # Commission
    commission_ids = fields.One2many('twh.sales.commission', 'invoice_id', 
                                      string='Sales Commissions')
    total_commission = fields.Monetary(string='Total Commission', 
                                        compute='_compute_total_commission',
                                        store=True, currency_field='currency_id')
    
    # Notes
    notes = fields.Text(string='Notes')
    
    # Company
    company_id = fields.Many2one('res.company', string='Company', 
                                  default=lambda self: self.env.company)
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('twh.invoice') or 'New'
        return super(TwhInvoice, self).create(vals)
    
    @api.depends('invoice_line_ids', 'invoice_line_ids.subtotal', 'discount_percent')
    def _compute_amounts(self):
        for invoice in self:
            subtotal = sum(line.subtotal for line in invoice.invoice_line_ids)
            discount_amount = subtotal * (invoice.discount_percent / 100.0)
            total = subtotal - discount_amount
            
            invoice.update({
                'subtotal': subtotal,
                'discount_amount': discount_amount,
                'total': total,
            })
    
    @api.depends('date_invoice', 'payment_term_days')
    def _compute_due_date(self):
        for invoice in self:
            if invoice.date_invoice and invoice.payment_term_days:
                invoice.date_due = invoice.date_invoice + timedelta(days=invoice.payment_term_days)
            else:
                invoice.date_due = False
    
    @api.depends('commission_ids', 'commission_ids.commission_amount')
    def _compute_total_commission(self):
        for invoice in self:
            invoice.total_commission = sum(commission.commission_amount 
                                            for commission in invoice.commission_ids)
    
    def action_confirm(self):
        """Confirm invoice and create commission"""
        for invoice in self:
            if not invoice.invoice_line_ids:
                raise UserError(_('Cannot confirm invoice without lines!'))
            
            invoice.write({'state': 'confirmed'})
            invoice._create_commission()
            invoice.message_post(body=_('Invoice confirmed'))
    
    def action_mark_paid(self):
        """Mark invoice as paid"""
        for invoice in self:
            invoice.write({'state': 'paid'})
            invoice.message_post(body=_('Invoice marked as paid'))
    
    def action_cancel(self):
        """Cancel invoice"""
        for invoice in self:
            invoice.write({'state': 'cancelled'})
            # Delete commissions
            invoice.commission_ids.unlink()
            invoice.message_post(body=_('Invoice cancelled'))
    
    def action_set_to_draft(self):
        """Set invoice back to draft"""
        for invoice in self:
            invoice.write({'state': 'draft'})
            invoice.message_post(body=_('Invoice set to draft'))
    
    def _create_commission(self):
        """Create sales commission based on margin"""
        self.ensure_one()
        
        # Delete existing commissions
        self.commission_ids.unlink()
        
        commission_obj = self.env['twh.sales.commission']
        
        for line in self.invoice_line_ids:
            # Get harga bayu (cost)
            cost_price = line.product_id.get_price_by_tier('bayu')
            selling_price = line.price_unit
            margin = selling_price - cost_price
            commission_amount = margin * line.quantity
            
            if commission_amount > 0:
                commission_obj.create({
                    'invoice_id': self.id,
                    'sales_person_id': self.sales_person_id.id,
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'cost_price': cost_price,
                    'selling_price': selling_price,
                    'margin': margin,
                    'commission_amount': commission_amount,
                    'date': self.date_invoice,
                })
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Auto-fill discount if partner has special discount"""
        if self.partner_id and self.partner_id.twh_discount_percent > 0:
            self.discount_percent = self.partner_id.twh_discount_percent
    
    def action_print_invoice(self):
        """Print invoice report"""
        return self.env.ref('twh_racing_part.action_report_twh_invoice').report_action(self)


class TwhInvoiceLine(models.Model):
    """
    Model Invoice Line TWH
    """
    _name = 'twh.invoice.line'
    _description = 'TWH Invoice Line'
    _order = 'invoice_id, sequence, id'
    
    sequence = fields.Integer(string='Sequence', default=10)
    invoice_id = fields.Many2one('twh.invoice', string='Invoice', 
                                  required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', 
                                  required=True, domain=[('sale_ok', '=', True)])
    description = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0, digits='Product Unit of Measure')
    price_unit = fields.Monetary(string='Unit Price', required=True, 
                                  currency_field='currency_id')
    subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal', 
                                store=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='invoice_id.currency_id', string='Currency')
    
    # Price tier reference
    price_tier = fields.Selection(related='invoice_id.price_tier', store=True)
    
    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Auto-fill description and price based on selected tier"""
        if self.product_id:
            self.description = self.product_id.name
            
            # Get price based on invoice price tier
            if self.invoice_id.price_tier:
                tier_code = self.invoice_id.price_tier
                price = self.product_id.get_price_by_tier(tier_code)
                if price > 0:
                    self.price_unit = price
    
    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_('Quantity must be greater than zero!'))