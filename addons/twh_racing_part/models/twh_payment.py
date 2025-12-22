# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TwhPayment(models.Model):
    """
    Model untuk mencatat pembayaran invoice.
    
    Model ini digunakan untuk tracking pembayaran dari customer, baik pembayaran
    penuh maupun cicilan. Setiap pembayaran akan otomatis update status invoice.
    """
    _name = 'twh.payment'
    _description = 'Catatan Pembayaran Invoice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'payment_date desc, id desc'
    
    # ========================
    # FIELDS
    # ========================
    
    # Informasi Dasar
    name = fields.Char(
        string='Nomor Referensi',
        required=True,
        copy=False,
        default='New',
        tracking=True,
        help='Nomor referensi pembayaran (auto-generated)'
    )
    
    invoice_id = fields.Many2one(
        'twh.invoice',
        string='Invoice',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Invoice yang dibayar'
    )
    
    partner_id = fields.Many2one(
        related='invoice_id.partner_id',
        string='Customer',
        store=True,
        readonly=True,
        help='Customer yang melakukan pembayaran'
    )
    
    # Detail Pembayaran
    payment_date = fields.Date(
        string='Tanggal Bayar',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Tanggal pembayaran diterima'
    )
    
    amount = fields.Monetary(
        string='Jumlah Bayar',
        required=True,
        currency_field='currency_id',
        tracking=True,
        help='Jumlah uang yang dibayarkan'
    )
    
    payment_method = fields.Selection([
        ('bank_bca', 'Transfer BCA'),
        ('bank_mandiri', 'Transfer Mandiri'),
        ('bank_bni', 'Transfer BNI'),
        ('bank_bri', 'Transfer BRI'),
        ('cash', 'Tunai'),
        ('giro', 'Giro'),
        ('other', 'Lainnya'),
    ], string='Metode Pembayaran', required=True, default='bank_bca', tracking=True,
       help='Cara pembayaran yang digunakan')
    
    note = fields.Text(
        string='Catatan',
        help='Keterangan pembayaran (misal: Cicilan 1, DP 30%, Pelunasan, dll)'
    )
    
    # Bukti Transfer
    proof_file = fields.Binary(
        string='Bukti Pembayaran',
        attachment=True,
        help='Upload bukti transfer (JPG, PNG, atau PDF)'
    )
    
    proof_filename = fields.Char(
        string='Nama File'
    )
    
    # Informasi Tambahan
    currency_id = fields.Many2one(
        related='invoice_id.currency_id',
        string='Mata Uang'
    )
    
    recorded_by = fields.Many2one(
        'res.users',
        string='Dicatat Oleh',
        default=lambda self: self.env.user,
        readonly=True,
        help='User yang mencatat pembayaran ini'
    )
    
    company_id = fields.Many2one(
        related='invoice_id.company_id',
        string='Perusahaan',
        store=True
    )
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Dikonfirmasi'),
        ('cancelled', 'Dibatalkan'),
    ], string='Status', default='draft', tracking=True,
       help='Status pembayaran')
    
    # ========================
    # CRUD METHODS
    # ========================
    
    @api.model
    def create(self, vals):
        """
        Override create untuk:
        1. Generate nomor referensi otomatis
        2. Auto-confirm pembayaran setelah dibuat
        """
        # Generate nomor referensi
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('twh.payment') or 'New'
        
        # Buat record payment
        payment = super(TwhPayment, self).create(vals)
        
        # Langsung konfirmasi payment
        payment.action_confirm()
        
        return payment
    
    def write(self, vals):
        """
        Override write untuk update status invoice saat payment berubah.
        """
        result = super(TwhPayment, self).write(vals)
        
        # Jika amount atau state berubah, recalculate invoice payment status
        if 'amount' in vals or 'state' in vals:
            for payment in self:
                payment.invoice_id._compute_payment_status()
        
        return result
    
    def unlink(self):
        """
        Override unlink untuk update status invoice setelah payment dihapus.
        """
        # Simpan dulu invoice yang terkait
        invoices = self.mapped('invoice_id')
        
        # Hapus payment
        result = super(TwhPayment, self).unlink()
        
        # Update status invoice
        for invoice in invoices:
            invoice._compute_payment_status()
        
        return result
    
    # ========================
    # ACTION METHODS
    # ========================
    
    def action_confirm(self):
        """
        Konfirmasi pembayaran.
        
        Saat dikonfirmasi:
        1. Status payment jadi 'confirmed'
        2. Status invoice di-update otomatis
        3. Notifikasi dikirim ke invoice
        """
        for payment in self:
            # Skip jika sudah confirmed
            if payment.state != 'draft':
                continue
            
            # Validasi 1: Jumlah harus lebih dari 0
            if payment.amount <= 0:
                raise ValidationError(_('Jumlah pembayaran harus lebih dari 0!'))
            
            # Validasi 2: Tidak boleh melebihi sisa tagihan
            if payment.amount > payment.invoice_id.remaining_amount:
                raise ValidationError(
                    _('Jumlah pembayaran (%(paid)s) tidak boleh melebihi sisa tagihan (%(remaining)s)!') % {
                        'paid': payment.amount,
                        'remaining': payment.invoice_id.remaining_amount
                    }
                )
            
            # Update status payment
            payment.write({'state': 'confirmed'})
            
            # Update status invoice (via computed field)
            payment.invoice_id._compute_payment_status()
            
            # Kirim notifikasi ke invoice
            payment.invoice_id.message_post(
                body=_('Pembayaran diterima: %s via %s') % (
                    payment.amount,
                    dict(payment._fields['payment_method'].selection).get(payment.payment_method)
                )
            )
    
    def action_cancel(self):
        """
        Batalkan pembayaran.
        
        Saat dibatalkan:
        1. Status payment jadi 'cancelled'
        2. Status invoice di-update (kembalikan sisa tagihan)
        3. Notifikasi dikirim ke invoice
        """
        for payment in self:
            # Update status
            payment.write({'state': 'cancelled'})
            
            # Update status invoice
            payment.invoice_id._compute_payment_status()
            
            # Kirim notifikasi
            payment.invoice_id.message_post(
                body=_('Pembayaran dibatalkan: %s') % payment.name
            )
    
    # ========================
    # CONSTRAINTS
    # ========================
    
    @api.constrains('amount')
    def _check_amount(self):
        """Validasi jumlah pembayaran harus lebih dari 0."""
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError(_('Jumlah pembayaran harus lebih dari 0!'))