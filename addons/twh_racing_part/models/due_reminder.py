# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class TwhDueReminder(models.Model):
    """
    Model untuk tracking reminder jatuh tempo invoice.
    
    Model ini digunakan untuk membuat dan mengirim reminder otomatis
    kepada sales person tentang invoice yang akan jatuh tempo.
    
    PENTING: Hanya untuk invoice TEMPO (bukan cash).
    """
    _name = 'twh.due.reminder'
    _description = 'Reminder Jatuh Tempo Invoice'
    _order = 'reminder_date desc, id desc'
    
    # ========================
    # FIELDS
    # ========================
    
    # Referensi Invoice
    invoice_id = fields.Many2one(
        'twh.invoice',
        string='Invoice',
        required=True,
        ondelete='cascade',
        help='Invoice yang diingatkan'
    )
    
    invoice_name = fields.Char(
        related='invoice_id.name',
        string='Nomor Invoice',
        store=True
    )
    
    partner_id = fields.Many2one(
        related='invoice_id.partner_id',
        string='Customer',
        store=True
    )
    
    # Tanggal-tanggal Penting
    invoice_date = fields.Date(
        related='invoice_id.date_invoice',
        string='Tanggal Invoice',
        store=True
    )
    
    due_date = fields.Date(
        related='invoice_id.date_due',
        string='Tanggal Jatuh Tempo',
        store=True
    )
    
    reminder_date = fields.Date(
        string='Tanggal Reminder',
        required=True,
        index=True,
        help='Tanggal reminder dikirim'
    )
    
    days_before_due = fields.Integer(
        string='Hari Sebelum Jatuh Tempo',
        default=7,
        help='Berapa hari sebelum jatuh tempo (negatif = sudah lewat)'
    )
    
    # Tipe Reminder
    reminder_type = fields.Selection([
        ('daily', 'Reminder Harian'),
        ('7_days', '7 Hari Sebelum'),
        ('3_days', '3 Hari Sebelum'),
        ('due_date', 'Hari Jatuh Tempo'),
        ('overdue', 'Sudah Terlambat'),
    ], string='Tipe Reminder', required=True, default='daily',
       help='Kategori reminder')
    
    # Status
    state = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sudah Dikirim'),
        ('dismissed', 'Diabaikan'),
    ], string='Status', default='pending', tracking=True,
       help='Status pengiriman reminder')
    
    sent_date = fields.Datetime(
        string='Waktu Dikirim',
        help='Kapan reminder dikirim'
    )
    
    sent_by_id = fields.Many2one(
        'res.users',
        string='Dikirim Oleh',
        help='User yang mengirim reminder'
    )
    
    # Pesan & Catatan
    message = fields.Text(
        string='Pesan Reminder',
        compute='_compute_message',
        help='Isi pesan reminder yang dikirim'
    )
    
    notes = fields.Text(
        string='Catatan Internal',
        help='Catatan tambahan (internal only)'
    )
    
    # Info Invoice (untuk tracking progress pembayaran)
    invoice_total = fields.Monetary(
        related='invoice_id.total',
        string='Total Invoice'
    )
    
    paid_amount = fields.Monetary(
        related='invoice_id.paid_amount',
        string='Sudah Dibayar'
    )
    
    remaining_amount = fields.Monetary(
        related='invoice_id.remaining_amount',
        string='Sisa Tagihan'
    )
    
    payment_progress = fields.Float(
        related='invoice_id.payment_progress',
        string='Progress Pembayaran (%)'
    )
    
    currency_id = fields.Many2one(
        related='invoice_id.currency_id',
        string='Mata Uang'
    )
    
    # ========================
    # CONSTRAINTS
    # ========================
    
    _sql_constraints = [
        (
            'unique_invoice_reminder',
            'unique(invoice_id, reminder_type, reminder_date)',
            'Reminder sudah ada untuk invoice ini pada tanggal tersebut.'
        ),
    ]
    
    # ========================
    # COMPUTED METHODS
    # ========================
    
    @api.depends('invoice_id', 'reminder_type', 'due_date', 'days_before_due')
    def _compute_message(self):
        """
        Generate pesan reminder berdasarkan tipe dan status invoice.
        
        Pesan disesuaikan dengan:
        1. Tipe reminder (daily, 7 days, dll)
        2. Status pembayaran (sudah ada cicilan atau belum)
        3. Berapa hari lagi sampai jatuh tempo
        """
        for reminder in self:
            invoice = reminder.invoice_id
            
            if not invoice:
                reminder.message = ''
                continue
            
            # Data invoice
            customer_name = invoice.partner_id.name or ''
            invoice_number = invoice.name or ''
            due_date_str = invoice.date_due.strftime('%d %B %Y') if invoice.date_due else ''
            
            # Format angka
            total_amount = self._format_currency(invoice.total)
            paid_amount = self._format_currency(invoice.paid_amount)
            remaining_amount = self._format_currency(invoice.remaining_amount)
            progress = round(invoice.payment_progress or 0, 1)
            
            # Info pembayaran
            if invoice.paid_amount > 0:
                payment_info = f"\nSudah Dibayar: Rp {paid_amount} ({progress}%)\nSisa: Rp {remaining_amount}"
            else:
                payment_info = f"\nTotal: Rp {total_amount}\nBelum ada pembayaran"
            
            # Generate pesan sesuai tipe
            reminder.message = self._generate_message_by_type(
                reminder.reminder_type,
                invoice_number,
                customer_name,
                due_date_str,
                payment_info,
                reminder.days_before_due
            )
    
    def _format_currency(self, amount):
        """Helper untuk format angka ke format rupiah."""
        return '{:,.0f}'.format(amount or 0)
    
    def _generate_message_by_type(self, reminder_type, invoice_number, customer_name, 
                                   due_date_str, payment_info, days_before_due):
        """
        Generate pesan berdasarkan tipe reminder.
        
        Args:
            reminder_type (str): Tipe reminder
            invoice_number (str): Nomor invoice
            customer_name (str): Nama customer
            due_date_str (str): Tanggal jatuh tempo (formatted)
            payment_info (str): Info pembayaran (formatted)
            days_before_due (int): Hari sebelum jatuh tempo
        
        Returns:
            str: Pesan reminder yang sudah diformat
        """
        messages = {
            'daily': f"""
PENGINGAT HARIAN: Invoice {invoice_number} akan jatuh tempo dalam {max(days_before_due, 0)} hari.

Customer: {customer_name}
Tanggal Jatuh Tempo: {due_date_str}{payment_info}
            """.strip(),
            
            '7_days': f"""
PENGINGAT: Invoice {invoice_number} akan jatuh tempo dalam 7 hari!

Customer: {customer_name}
Tanggal Jatuh Tempo: {due_date_str}{payment_info}
            """.strip(),
            
            '3_days': f"""
PERINGATAN: Invoice {invoice_number} akan jatuh tempo dalam 3 hari!

Customer: {customer_name}
Tanggal Jatuh Tempo: {due_date_str}{payment_info}
            """.strip(),
            
            'due_date': f"""
JATUH TEMPO HARI INI: Invoice {invoice_number}

Customer: {customer_name}
Tanggal Jatuh Tempo: {due_date_str}{payment_info}
            """.strip(),
            
            'overdue': self._generate_overdue_message(
                invoice_number, customer_name, due_date_str, payment_info
            ),
        }
        
        return messages.get(reminder_type, '')
    
    def _generate_overdue_message(self, invoice_number, customer_name, 
                                   due_date_str, payment_info):
        """Generate pesan khusus untuk reminder overdue."""
        days_overdue = 0
        if self.invoice_id.date_due:
            days_overdue = (fields.Date.today() - self.invoice_id.date_due).days
        
        return f"""
TERLAMBAT {days_overdue} HARI: Invoice {invoice_number}

Customer: {customer_name}
Tanggal Jatuh Tempo: {due_date_str}{payment_info}

SEGERA LAKUKAN PENAGIHAN!
        """.strip()
    
    # ========================
    # ACTION METHODS
    # ========================
    
    def action_send_reminder(self):
        """
        Kirim reminder ke sales person.
        
        Reminder dikirim melalui:
        1. Activity (to-do task)
        2. Message/notification di chatter invoice
        """
        for reminder in self:
            # Kirim activity (to-do)
            self._send_activity_reminder(reminder)
            
            # Kirim message ke chatter invoice
            self._send_message_reminder(reminder)
            
            # Update status reminder
            reminder.write({
                'state': 'sent',
                'sent_date': fields.Datetime.now(),
                'sent_by_id': self.env.user.id,
            })
            
            _logger.info(f'Reminder terkirim untuk invoice {reminder.invoice_name}')
    
    def _send_activity_reminder(self, reminder):
        """Kirim activity/to-do ke sales person."""
        try:
            reminder.invoice_id.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                summary=f'Reminder: Invoice {reminder.invoice_name} - {reminder.reminder_type}',
                note=reminder.message,
                user_id=reminder.invoice_id.sales_person_id.id,
                date_deadline=reminder.reminder_date,
            )
        except Exception as error:
            _logger.warning(
                f'Gagal membuat activity untuk invoice {reminder.invoice_name}: {error}'
            )
    
    def _send_message_reminder(self, reminder):
        """Kirim message/notification ke chatter invoice."""
        try:
            reminder.invoice_id.message_post(
                body=reminder.message,
                subject=f'Reminder Pembayaran: {reminder.reminder_type}',
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        except Exception as error:
            _logger.warning(
                f'Gagal posting message untuk invoice {reminder.invoice_name}: {error}'
            )
    
    def action_dismiss(self):
        """
        Abaikan reminder.
        
        Digunakan jika reminder tidak relevan lagi (misal: sudah ditagih manual).
        """
        for reminder in self:
            reminder.write({'state': 'dismissed'})
    
    # ========================
    # CRON METHODS
    # ========================
    
    @api.model
    def _cron_create_reminders(self):
        """
        Cron job untuk create reminder otomatis.
        Dijalankan setiap hari jam 01:00.
        
        Logic:
        1. Ambil semua invoice tempo yang belum lunas
        2. Cek tanggal jatuh tempo
        3. Buat reminder sesuai kondisi (daily, 7 days, 3 days, due, overdue)
        """
        _logger.info('=== Mulai Cron: Create Due Reminders ===')
        
        today = fields.Date.today()
        
        # Ambil invoice tempo yang belum lunas
        invoices = self._get_unpaid_tempo_invoices()
        
        _logger.info(f'Ditemukan {len(invoices)} invoice tempo yang belum lunas')
        
        # Process setiap invoice
        for invoice in invoices:
            self._process_invoice_reminders(invoice, today)
        
        _logger.info('=== Selesai Cron: Create Due Reminders ===')
    
    def _get_unpaid_tempo_invoices(self):
        """Ambil invoice tempo yang belum lunas."""
        return self.env['twh.invoice'].search([
            ('payment_type', '=', 'tempo'),
            ('state', 'in', ['confirmed', 'partial', 'overdue']),
            ('date_due', '!=', False),
        ])
    
    def _process_invoice_reminders(self, invoice, today):
        """
        Process reminder untuk satu invoice.
        
        Args:
            invoice: Record invoice yang akan diprocess
            today: Tanggal hari ini
        """
        due_date = invoice.date_due
        if not due_date:
            return
        
        # Hitung selisih hari
        days_until_due = (due_date - today).days
        
        # Cek kondisi dan buat reminder sesuai kebutuhan
        if days_until_due < 0:
            # Overdue
            self._create_overdue_reminder(invoice, today, days_until_due)
        elif days_until_due <= 14:
            # Daily reminder (14 hari sebelum jatuh tempo)
            self._create_daily_reminder(invoice, today, days_until_due)
            
            # Milestone reminder (7, 3, 0 hari)
            if days_until_due in (7, 3, 0):
                self._create_milestone_reminder(invoice, today, days_until_due)
    
    def _create_overdue_reminder(self, invoice, today, days_until_due):
        """Buat reminder untuk invoice yang sudah overdue."""
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
            
            # Update state invoice jadi overdue
            if invoice.state != 'overdue':
                invoice.write({'state': 'overdue'})
            
            _logger.info(f'Reminder overdue dibuat untuk invoice {invoice.name}')
    
    def _create_daily_reminder(self, invoice, today, days_until_due):
        """Buat daily reminder (14 hari sebelum jatuh tempo)."""
        existing = self.search([
            ('invoice_id', '=', invoice.id),
            ('reminder_type', '=', 'daily'),
            ('reminder_date', '=', today),
        ])
        
        if not existing:
            self.create({
                'invoice_id': invoice.id,
                'reminder_date': today,
                'reminder_type': 'daily',
                'days_before_due': days_until_due,
            })
            
            _logger.info(
                f'Reminder harian dibuat untuk invoice {invoice.name}, '
                f'{days_until_due} hari sebelum jatuh tempo'
            )
    
    def _create_milestone_reminder(self, invoice, today, days_until_due):
        """Buat milestone reminder (7, 3, 0 hari sebelum jatuh tempo)."""
        type_mapping = {
            7: '7_days',
            3: '3_days',
            0: 'due_date'
        }
        
        reminder_type = type_mapping.get(days_until_due)
        
        if not reminder_type:
            return
        
        existing = self.search([
            ('invoice_id', '=', invoice.id),
            ('reminder_type', '=', reminder_type),
            ('reminder_date', '=', today),
        ])
        
        if not existing:
            self.create({
                'invoice_id': invoice.id,
                'reminder_date': today,
                'reminder_type': reminder_type,
                'days_before_due': days_until_due,
            })
            
            _logger.info(
                f'Reminder milestone {reminder_type} dibuat untuk invoice {invoice.name}'
            )
    
    @api.model
    def _cron_send_reminders(self):
        """
        Cron job untuk kirim reminder yang pending.
        Dijalankan setiap hari jam 08:00.
        """
        _logger.info('=== Mulai Cron: Send Pending Reminders ===')
        
        today = fields.Date.today()
        
        # Ambil reminder pending yang tanggalnya sudah tiba
        reminders = self.search([
            ('state', '=', 'pending'),
            ('reminder_date', '<=', today),
        ])
        
        _logger.info(f'Ditemukan {len(reminders)} reminder pending untuk dikirim')
        
        # Kirim setiap reminder
        for reminder in reminders:
            try:
                reminder.action_send_reminder()
            except Exception as error:
                _logger.error(f'Gagal mengirim reminder {reminder.id}: {str(error)}')
        
        _logger.info(f'=== Selesai Cron: {len(reminders)} reminder terkirim ===')
    
    @api.model
    def _cron_cleanup_paid_invoices(self):
        """
        Cron job untuk cleanup reminder dari invoice yang sudah paid.
        Dijalankan setiap hari jam 02:00.
        """
        _logger.info('=== Mulai Cron: Cleanup Paid Invoice Reminders ===')
        
        # Cari reminder dari invoice yang sudah lunas
        paid_reminders = self.search([
            ('invoice_id.state', '=', 'paid'),
            ('state', '=', 'pending'),
        ])
        
        if paid_reminders:
            paid_reminders.write({'state': 'dismissed'})
            _logger.info(
                f'{len(paid_reminders)} reminder dibatalkan karena invoice sudah lunas'
            )
        else:
            _logger.info('Tidak ada reminder yang perlu di-cleanup')
        
        _logger.info('=== Selesai Cron: Cleanup Reminders===')