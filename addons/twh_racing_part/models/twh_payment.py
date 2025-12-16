# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class TwhPayment(models.Model):
    """
    Model Payment TWH Racing Part
    Untuk tracking pembayaran (cicilan/lunas) dari invoice
    """
    _name = 'twh.payment'
    _description = 'TWH Payment Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'payment_date desc, id desc'
    
    # Basic Info
    name = fields.Char(
        string='Payment Reference',
        required=True,
        copy=False,
        default='New',
        tracking=True
    )
    
    invoice_id = fields.Many2one(
        'twh.invoice',
        string='Invoice',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    
    partner_id = fields.Many2one(
        related='invoice_id.partner_id',
        string='Customer',
        store=True,
        readonly=True
    )
    
    # Payment Details
    payment_date = fields.Date(
        string='Payment Date',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    
    amount = fields.Monetary(
        string='Payment Amount',
        required=True,
        currency_field='currency_id',
        tracking=True
    )
    
    payment_method = fields.Selection([
        ('bank_bca', 'Transfer BCA'),
        ('bank_mandiri', 'Transfer Mandiri'),
        ('bank_bni', 'Transfer BNI'),
        ('bank_bri', 'Transfer BRI'),
        ('cash', 'Cash'),
        ('giro', 'Giro'),
        ('other', 'Other'),
    ], string='Payment Method', required=True, default='bank_bca', tracking=True)
    
    note = fields.Text(
        string='Note',
        help='e.g., Cicilan 1, DP 30%, Pelunasan, etc.'
    )
    
    proof_file = fields.Binary(
        string='Proof of Payment',
        attachment=True,
        help='Upload bukti transfer (JPG, PNG, PDF)'
    )
    
    proof_filename = fields.Char(string='Filename')
    
    # Related Info
    currency_id = fields.Many2one(
        related='invoice_id.currency_id',
        string='Currency'
    )
    
    recorded_by = fields.Many2one(
        'res.users',
        string='Recorded By',
        default=lambda self: self.env.user,
        readonly=True
    )
    
    company_id = fields.Many2one(
        related='invoice_id.company_id',
        string='Company',
        store=True
    )
    
    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('twh.payment') or 'New'
        
        payment = super(TwhPayment, self).create(vals)
        
        # Auto-confirm payment
        payment.action_confirm()
        
        return payment
    
    def write(self, vals):
        res = super(TwhPayment, self).write(vals)
        
        # Recalculate invoice payment status if amount changed
        if 'amount' in vals or 'state' in vals:
            for payment in self:
                payment.invoice_id._compute_payment_status()
        
        return res
    
    def unlink(self):
        # Store invoice IDs before deleting
        invoice_ids = self.mapped('invoice_id')
        
        res = super(TwhPayment, self).unlink()
        
        # Recalculate invoice payment status
        for invoice in invoice_ids:
            invoice._compute_payment_status()
        
        return res
    
    def action_confirm(self):
        """Confirm payment and update invoice"""
        for payment in self:
            if payment.state != 'draft':
                continue
            
            # Validate amount
            if payment.amount <= 0:
                raise ValidationError(_('Payment amount must be greater than zero!'))
            
            # Check if payment exceeds remaining amount
            if payment.amount > payment.invoice_id.remaining_amount:
                raise ValidationError(
                    _('Payment amount (%(amount)s) cannot exceed remaining balance (%(remaining)s)!') % {
                        'amount': payment.amount,
                        'remaining': payment.invoice_id.remaining_amount
                    }
                )
            
            payment.write({'state': 'confirmed'})
            
            # Update invoice payment status
            payment.invoice_id._compute_payment_status()
            
            # Post message to invoice
            payment.invoice_id.message_post(
                body=_('Payment received: %s - %s') % (
                    payment.amount,
                    payment.payment_method
                )
            )
    
    def action_cancel(self):
        """Cancel payment"""
        for payment in self:
            payment.write({'state': 'cancelled'})
            payment.invoice_id._compute_payment_status()
            payment.invoice_id.message_post(
                body=_('Payment cancelled: %s') % payment.name
            )
    
    @api.constrains('amount')
    def _check_amount(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError(_('Payment amount must be greater than zero!'))