# -*- coding: utf-8 -*-

from odoo import models, fields, api, _ 
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
    invoice_id = fields.Many2one(
        'twh.invoice',
        string='Invoice',
        required=True,
        ondelete='cascade'
    )
    invoice_name = fields.Char(related='invoice_id.name', string='Invoice Number', store=True)
    partner_id = fields.Many2one(related='invoice_id.partner_id', string='Customer', store=True)

    # Dates
    invoice_date = fields.Date(related='invoice_id.date_invoice', string='Invoice Date', store=True)
    due_date = fields.Date(related='invoice_id.date_due', string='Due Date', store=True)
    reminder_date = fields.Date(string='Reminder Date', required=True, index=True)
    days_before_due = fields.Integer(string='Days Before Due', default=7)

    # Reminder Info
    reminder_type = fields.Selection([
        ('daily', 'Daily Reminder'),
        ('7_days', '7 Days Before'),
        ('3_days', '3 Days Before'),
        ('due_date', 'Due Date'),
        ('overdue', 'Overdue'),
    ], string='Reminder Type', required=True, default='daily')

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

    # Constraint unik: tidak boleh ada reminder ganda untuk invoice + tipe + tanggal
    _sql_constraints = [
        (
            'unique_invoice_reminder',
            'unique(invoice_id, reminder_type, reminder_date)',
            'Reminder sudah ada untuk invoice ini pada tanggal tersebut.'
        ),
    ]

    @api.depends('invoice_id', 'reminder_type', 'due_date', 'days_before_due')
    def _compute_message(self):
        for reminder in self:
            invoice = reminder.invoice_id
            if not invoice:
                reminder.message = ''
                continue

            customer_name = invoice.partner_id.name or ''
            invoice_number = invoice.name or ''
            due_date_str = invoice.date_due.strftime('%d %B %Y') if invoice.date_due else ''
            amount = '{:,.0f}'.format(invoice.total or 0)

            if reminder.reminder_type == 'daily':
                reminder.message = f"""
            PENGINGAT HARIAN: Invoice {invoice_number} akan jatuh tempo dalam {max(reminder.days_before_due, 0)} hari.

            Customer: {customer_name}
            Tanggal Jatuh Tempo: {due_date_str}
            Total: Rp {amount}
            """.strip()
            elif reminder.reminder_type == '7_days':
                reminder.message = f"""
            PENGINGAT: Invoice {invoice_number} akan jatuh tempo dalam 7 hari!

            Customer: {customer_name}
            Tanggal Jatuh Tempo: {due_date_str}
            Total: Rp {amount}
            """.strip()
            elif reminder.reminder_type == '3_days':
                reminder.message = f"""
            PERINGATAN: Invoice {invoice_number} akan jatuh tempo dalam 3 hari!

            Customer: {customer_name}
            Tanggal Jatuh Tempo: {due_date_str}
            Total: Rp {amount}
            """.strip()
            elif reminder.reminder_type == 'due_date':
                reminder.message = f"""
            JATUH TEMPO HARI INI: Invoice {invoice_number}

            Customer: {customer_name}
            Tanggal Jatuh Tempo: {due_date_str}
            Total: Rp {amount}
            """.strip()
            else:  # overdue
                days_overdue = 0
                if invoice.date_due:
                    days_overdue = (fields.Date.today() - invoice.date_due).days
                reminder.message = f"""
            TERLAMBAT {days_overdue} HARI: Invoice {invoice_number}

            Customer: {customer_name}
            Tanggal Jatuh Tempo: {due_date_str}
            Total: Rp {amount}
            SEGERA LAKUKAN PENAGIHAN!
            """.strip()

    def action_send_reminder(self):
        """Send reminder notification"""
        for reminder in self:
            try:
                reminder.invoice_id.activity_schedule(
                    activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                    summary=f'Reminder: Invoice {reminder.invoice_name} - {reminder.reminder_type}',
                    note=reminder.message,
                    user_id=reminder.invoice_id.sales_person_id.id,
                    date_deadline=reminder.reminder_date,
                )
            except Exception as e:
                _logger.warning(f'Failed to schedule activity for invoice {reminder.invoice_name}: {e}')

            try:
                reminder.invoice_id.message_post(
                    body=reminder.message,
                    subject=f'Payment Reminder: {reminder.reminder_type}',
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
            except Exception as e:
                _logger.warning(f'Failed to post message for invoice {reminder.invoice_name}: {e}')

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

        invoices = self.env['twh.invoice'].search([
            ('state', 'in', ['confirmed']),
            ('date_due', '!=', False),
        ])

        for invoice in invoices:
            due_date = invoice.date_due
            if not due_date:
                continue

            days_until_due = (due_date - today).days

            # Overdue reminder
            if days_until_due < 0:
                existing = self.search([
                    ('invoice_id', '=', invoice.id),
                    ('reminder_type', '=', 'overdue'),
                    ('reminder_date', '=', today),
                ])
                if not existing:
                    self.create({
                        'invoice_id': invoice.id,
                        'reminder_date': today,
                        'reminder_type': 'overdue',
                        'days_before_due': days_until_due,
                    })
                    invoice.write({'state': 'overdue'}) 
                continue

            # Daily reminder mulai 14 hari sebelum due
            if days_until_due <= 14:
                existing_daily = self.search([
                    ('invoice_id', '=', invoice.id),
                    ('reminder_type', '=', 'daily'),
                    ('reminder_date', '=', today),
                ])
                if not existing_daily:
                    self.create({
                        'invoice_id': invoice.id,
                        'reminder_date': today,
                        'reminder_type': 'daily',
                        'days_before_due': days_until_due,
                    })
                    _logger.info(f'Created daily reminder for invoice {invoice.name}, {days_until_due} days before due')

            # Milestone reminder (7, 3, 0 hari)
            if days_until_due in (7, 3, 0):
                type_map = {7: '7_days', 3: '3_days', 0: 'due_date'}
                reminder_type = type_map[days_until_due]
                existing_milestone = self.search([
                    ('invoice_id', '=', invoice.id),
                    ('reminder_type', '=', reminder_type),
                    ('reminder_date', '=', today),
                ])
                if not existing_milestone:
                    self.create({
                        'invoice_id': invoice.id,
                        'reminder_date': today,
                        'reminder_type': reminder_type,
                        'days_before_due': days_until_due,
                    })
                    _logger.info(f'Created milestone reminder {reminder_type} for invoice {invoice.name}')

        _logger.info('Cron completed: Create due date reminders')

    @api.model
    def _cron_send_reminders(self):
        """
        Cron job untuk send reminders yang pending
        Jalan setiap hari
        """
        _logger.info('Running cron: Send pending reminders')

        today = fields.Date.today()

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
