# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class TwhDueReminder(models.Model):
    """
    Model untuk tracking reminder jatuh tempo invoice
    """
    _name = 'twh.due.reminder'
    _description = 'TWH Due Date Reminder'
    _order = 'reminder_date desc, id desc'
    
    # References
    invoice_id = fields.Many2one('twh.invoice', string='Invoice', 
                                  required=True, ondelete='cascade')
    invoice_name = fields.Char(related='invoice_id.name', string='Invoice Number', store=True)
    partner_id = fields.Many2one(related='invoice_id.partner_id', string='Customer', store=True)
    
    # Dates
    invoice_date = fields.Date(related='invoice_id.date_invoice', string='Invoice Date', store=True)
    due_date = fields.Date(related='invoice_id.date_due', string='Due Date', store=True)
    reminder_date = fields.Date(string='Reminder Date', required=True, index=True)
    days_before_due = fields.Integer(string='Days Before Due', default=7)
    
    # Reminder Info
    reminder_type = fields.Selection([
        ('7_days', '7 Days Before'),
        ('3_days', '3 Days Before'),
        ('due_date', 'Due Date'),
        ('overdue', 'Overdue'),
    ], string='Reminder Type', required=True, default='7_days')
    
    # Status
    state = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('dismissed', 'Dismissed'),
    ], string='Status', default='pending', tracking=True)
    
    sent_date = fields.Datetime(string='Sent Date')
    sent_by_id = fields.Many2one('res.users', string='Sent By')
    
    # Message
    message = fields.Text(string='Reminder Message', compute='_compute_message')
    notes = fields.Text(string='Notes')
    
    # Invoice Amount
    invoice_total = fields.Monetary(related='invoice_id.total', string='Invoice Total')
    currency_id = fields.Many2one(related='invoice_id.currency_id', string='Currency')
    
    @api.depends('invoice_id', 'reminder_type', 'due_date', 'days_before_due')
    def _compute_message(self):
        for reminder in self:
            if not reminder.invoice_id:
                reminder.message = ''
                continue
            
            invoice = reminder.invoice_id
            customer_name = invoice.partner_id.name
            invoice_number = invoice.name
            due_date_str = invoice.date_due.strftime('%d %B %Y') if invoice.date_due else ''
            amount = '{:,.0f}'.format(invoice.total)
            
            if reminder.reminder_type == '7_days':
                reminder.message = f"""
                PENGINGAT: Invoice {invoice_number} akan jatuh tempo dalam 7 hari!
                
                Customer: {customer_name}
                Tanggal Jatuh Tempo: {due_date_str}
                Total: Rp {amount}
                
                Mohon segera lakukan penagihan.
                """
            elif reminder.reminder_type == '3_days':
                reminder.message = f"""
                PERINGATAN: Invoice {invoice_number} akan jatuh tempo dalam 3 hari!
                
                Customer: {customer_name}
                Tanggal Jatuh Tempo: {due_date_str}
                Total: Rp {amount}
                
                Segera lakukan follow up!
                """
            elif reminder.reminder_type == 'due_date':
                reminder.message = f"""
                JATUH TEMPO HARI INI: Invoice {invoice_number}
                
                Customer: {customer_name}
                Tanggal Jatuh Tempo: {due_date_str}
                Total: Rp {amount}
                
                Harap segera melakukan penagihan!
                """
            else:  # overdue
                days_overdue = (fields.Date.today() - invoice.date_due).days if invoice.date_due else 0
                reminder.message = f"""
                TERLAMBAT {days_overdue} HARI: Invoice {invoice_number}
                
                Customer: {customer_name}
                Tanggal Jatuh Tempo: {due_date_str}
                Total: Rp {amount}
                
                SEGERA LAKUKAN PENAGIHAN!
                """
    
    def action_send_reminder(self):
        """Send reminder notification"""
        for reminder in self:
            # Create activity for sales person
            reminder.invoice_id.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                summary=f'Reminder: Invoice {reminder.invoice_name} - {reminder.reminder_type}',
                note=reminder.message,
                user_id=reminder.invoice_id.sales_person_id.id,
                date_deadline=reminder.reminder_date,
            )
            
            # Post message in chatter
            reminder.invoice_id.message_post(
                body=reminder.message,
                subject=f'Payment Reminder: {reminder.reminder_type}',
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
            
            # Update reminder status
            reminder.write({
                'state': 'sent',
                'sent_date': fields.Datetime.now(),
                'sent_by_id': self.env.user.id,
            })
            
            _logger.info(f'Reminder sent for invoice {reminder.invoice_name}')
    
    def action_dismiss(self):
        """Dismiss reminder"""
        for reminder in self:
            reminder.write({'state': 'dismissed'})
    
    @api.model
    def _cron_create_reminders(self):
        """
        Cron job untuk create reminders otomatis
        Jalan setiap hari
        """
        _logger.info('Running cron: Create due date reminders')
        
        today = fields.Date.today()
        
        # Find invoices yang belum paid
        invoices = self.env['twh.invoice'].search([
            ('state', 'in', ['confirmed']),
            ('date_due', '!=', False),
        ])
        
        for invoice in invoices:
            due_date = invoice.date_due
            
            # Skip if already overdue
            if due_date < today:
                # Create overdue reminder if not exists
                existing = self.search([
                    ('invoice_id', '=', invoice.id),
                    ('reminder_type', '=', 'overdue'),
                    ('state', '=', 'pending'),
                ])
                if not existing:
                    self.create({
                        'invoice_id': invoice.id,
                        'reminder_date': today,
                        'reminder_type': 'overdue',
                        'days_before_due': 0,
                    })
                    # Update invoice state
                    invoice.write({'state': 'overdue'})
                continue
            
            # Calculate days until due
            days_until_due = (due_date - today).days
            
            # Create reminder based on days
            reminder_type = None
            if days_until_due == 7:
                reminder_type = '7_days'
            elif days_until_due == 3:
                reminder_type = '3_days'
            elif days_until_due == 0:
                reminder_type = 'due_date'
            
            if reminder_type:
                # Check if reminder already exists
                existing = self.search([
                    ('invoice_id', '=', invoice.id),
                    ('reminder_type', '=', reminder_type),
                ])
                if not existing:
                    self.create({
                        'invoice_id': invoice.id,
                        'reminder_date': today,
                        'reminder_type': reminder_type,
                        'days_before_due': days_until_due,
                    })
                    _logger.info(f'Created reminder {reminder_type} for invoice {invoice.name}')
        
        _logger.info('Cron completed: Create due date reminders')
    
    @api.model
    def _cron_send_reminders(self):
        """
        Cron job untuk send reminders yang pending
        Jalan setiap hari
        """
        _logger.info('Running cron: Send pending reminders')
        
        today = fields.Date.today()
        
        # Find pending reminders for today
        reminders = self.search([
            ('state', '=', 'pending'),
            ('reminder_date', '<=', today),
        ])
        
        for reminder in reminders:
            try:
                reminder.action_send_reminder()
            except Exception as e:
                _logger.error(f'Failed to send reminder {reminder.id}: {str(e)}')
        
        _logger.info(f'Cron completed: Sent {len(reminders)} reminders')