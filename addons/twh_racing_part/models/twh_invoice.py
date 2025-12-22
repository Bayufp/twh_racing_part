# -*- coding: utf-8 -*-

from datetime import timedelta 

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TwhInvoice(models.Model):
    """
    Model untuk mengelola invoice TWH Racing Part.
    
    Model ini mencatat transaksi penjualan produk racing part kepada toko/dealer,
    termasuk pembayaran tempo dan cicilan.
    """
    _name = 'twh.invoice'
    _description = 'Invoice TWH Racing Part'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_invoice desc, id desc'
    
    # ========================
    # FIELDS
    # ========================
    
    # Informasi Dasar
    name = fields.Char(
        string='Nomor Invoice', 
        required=True, 
        copy=False, 
        default='New', 
        tracking=True,
        help='Nomor invoice akan di-generate otomatis'
    )
    
    partner_id = fields.Many2one(
        'res.partner', 
        string='Customer', 
        required=True, 
        tracking=True,
        domain=[('is_company', '=', True)],
        help='Pilih toko atau dealer yang membeli'
    )
    
    date_invoice = fields.Date(
        string='Tanggal Invoice', 
        required=True, 
        default=fields.Date.today, 
        tracking=True,
        help='Tanggal pembuatan invoice'
    )
    
    # Informasi Sales
    sales_person_id = fields.Many2one(
        'res.users', 
        string='Sales Person', 
        default=lambda self: self.env.user,
        tracking=True,
        help='Sales yang bertanggung jawab atas transaksi ini'
    )
    
    price_tier = fields.Selection([
        ('price_a', 'Harga A'),
        ('price_b', 'Harga B'),
        ('dealer', 'Dealer'),
    ], string='Kategori Harga', required=True, default='price_a', tracking=True,
       help='Kategori harga yang digunakan untuk invoice ini')
    
    # Relasi ke Sales Order
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        readonly=True,
        copy=False,
        tracking=True,
        help='Sales Order sumber jika invoice dibuat dari SO'
    )
    
    # Detail Produk
    invoice_line_ids = fields.One2many(
        'twh.invoice.line', 
        'invoice_id', 
        string='Detail Produk',
        help='Daftar produk yang dibeli'
    )
    
    # Perhitungan Harga
    subtotal = fields.Monetary(
        string='Subtotal', 
        compute='_compute_amounts', 
        store=True, 
        currency_field='currency_id',
        help='Total harga sebelum diskon'
    )
    
    discount_percent = fields.Float(
        string='Diskon (%)', 
        default=0.0, 
        digits='Discount', 
        tracking=True,
        help='Persentase diskon khusus customer'
    )
    
    discount_amount = fields.Monetary(
        string='Nilai Diskon', 
        compute='_compute_amounts', 
        store=True,
        currency_field='currency_id',
        help='Nilai rupiah dari diskon'
    )
    
    total = fields.Monetary(
        string='Total Bayar', 
        compute='_compute_amounts', 
        store=True, 
        currency_field='currency_id',
        help='Total yang harus dibayar setelah diskon'
    )
    
    currency_id = fields.Many2one(
        'res.currency', 
        string='Mata Uang', 
        default=lambda self: self.env.company.currency_id
    )
    
    # Pembayaran
    payment_type = fields.Selection([
        ('cash', 'Cash'),
        ('tempo', 'Tempo'),
    ], string='Tipe Pembayaran', required=True, default='tempo', tracking=True,
       help='Cash = bayar langsung, Tempo = bayar kemudian dengan jatuh tempo')
    
    payment_ids = fields.One2many(
        'twh.payment',
        'invoice_id',
        string='Riwayat Pembayaran',
        help='Daftar pembayaran yang sudah diterima'
    )
    
    paid_amount = fields.Monetary(
        string='Sudah Dibayar',
        compute='_compute_payment_status',
        store=True,
        currency_field='currency_id',
        help='Total yang sudah dibayar customer'
    )
    
    remaining_amount = fields.Monetary(
        string='Sisa Tagihan',
        compute='_compute_payment_status',
        store=True,
        currency_field='currency_id',
        help='Sisa yang masih harus dibayar'
    )
    
    payment_progress = fields.Float(
        string='Progress Pembayaran (%)',
        compute='_compute_payment_status',
        store=True,
        help='Persentase pembayaran yang sudah diterima'
    )
    
    payment_count = fields.Integer(
        string='Jumlah Pembayaran',
        compute='_compute_payment_count',
        help='Total berapa kali customer sudah bayar'
    )
    
    # Jatuh Tempo
    payment_term_days = fields.Integer(
        string='Termin Pembayaran (Hari)', 
        default=60, 
        tracking=True,
        help='Berapa hari setelah invoice dibuat sampai jatuh tempo'
    )
    
    date_due = fields.Date(
        string='Tanggal Jatuh Tempo', 
        compute='_compute_due_date', 
        store=True, 
        tracking=True,
        help='Tanggal batas pembayaran harus lunas'
    )
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Dikonfirmasi'),
        ('partial', 'Dibayar Sebagian'),
        ('paid', 'Lunas'),
        ('overdue', 'Terlambat'),
        ('cancelled', 'Dibatalkan'),
    ], string='Status', default='draft', tracking=True,
       help='Status invoice saat ini')
    
    # Komisi
    commission_ids = fields.One2many(
        'twh.sales.commission', 
        'invoice_id', 
        string='Komisi Sales',
        help='Komisi yang didapat sales dari invoice ini'
    )
    
    total_commission = fields.Monetary(
        string='Total Komisi', 
        compute='_compute_total_commission',
        store=True, 
        currency_field='currency_id',
        help='Total komisi untuk sales'
    )
    
    # Catatan
    notes = fields.Text(
        string='Catatan',
        help='Catatan tambahan untuk invoice ini'
    )
    
    # Company
    company_id = fields.Many2one(
        'res.company', 
        string='Perusahaan', 
        default=lambda self: self.env.company
    )
    
    # ========================
    # COMPUTED METHODS
    # ========================
    
    @api.depends('invoice_line_ids', 'invoice_line_ids.subtotal', 'discount_percent')
    def _compute_amounts(self):
        """
        Menghitung subtotal, diskon, dan total invoice.
        Dijalankan otomatis saat ada perubahan di line items atau diskon.
        """
        for invoice in self:
            # Hitung subtotal dari semua line
            subtotal = sum(line.subtotal for line in invoice.invoice_line_ids)
            
            # Hitung nilai diskon
            discount_amount = subtotal * (invoice.discount_percent / 100.0)
            
            # Hitung total setelah diskon
            total = subtotal - discount_amount
            
            invoice.update({
                'subtotal': subtotal,
                'discount_amount': discount_amount,
                'total': total,
            })
    
    @api.depends('payment_ids', 'payment_ids.amount', 'payment_ids.state', 'total')
    def _compute_payment_status(self):
        """
        Menghitung status pembayaran invoice.
        
        Menghitung berapa yang sudah dibayar, sisa tagihan, dan progress pembayaran.
        Juga otomatis update status invoice jika sudah lunas atau dibayar sebagian.
        """
        for invoice in self:
            # Filter hanya pembayaran yang sudah dikonfirmasi
            confirmed_payments = invoice.payment_ids.filtered(
                lambda payment: payment.state == 'confirmed'
            )
            
            # Hitung total yang sudah dibayar
            paid_amount = sum(confirmed_payments.mapped('amount'))
            
            # Hitung sisa tagihan
            remaining_amount = invoice.total - paid_amount
            
            # Hitung persentase progress
            if invoice.total > 0:
                progress = (paid_amount / invoice.total) * 100
            else:
                progress = 0.0
            
            # Update field
            invoice.update({
                'paid_amount': paid_amount,
                'remaining_amount': remaining_amount,
                'payment_progress': progress,
            })
            
            # Auto-update status berdasarkan pembayaran
            # Hanya update jika invoice dalam status tertentu
            if invoice.state in ['confirmed', 'partial', 'overdue']:
                if remaining_amount <= 0:
                    # Sudah lunas
                    invoice.state = 'paid'
                elif paid_amount > 0:
                    # Sudah ada pembayaran tapi belum lunas
                    invoice.state = 'partial'
    
    @api.depends('payment_ids')
    def _compute_payment_count(self):
        """Menghitung jumlah pembayaran yang sudah dikonfirmasi."""
        for invoice in self:
            invoice.payment_count = len(
                invoice.payment_ids.filtered(lambda p: p.state == 'confirmed')
            )
    
    @api.depends('date_invoice', 'payment_term_days', 'payment_type')
    def _compute_due_date(self):
        """
        Menghitung tanggal jatuh tempo.
        
        Untuk pembayaran cash tidak ada jatuh tempo.
        Untuk tempo, jatuh tempo = tanggal invoice + termin pembayaran.
        """
        for invoice in self:
            if invoice.payment_type == 'cash':
                # Cash tidak ada jatuh tempo
                invoice.date_due = False
            elif invoice.date_invoice and invoice.payment_term_days:
                # Hitung jatuh tempo
                invoice.date_due = invoice.date_invoice + timedelta(
                    days=invoice.payment_term_days
                )
            else:
                invoice.date_due = False
    
    @api.depends('commission_ids', 'commission_ids.commission_amount')
    def _compute_total_commission(self):
        """Menghitung total komisi dari semua line commission."""
        for invoice in self:
            invoice.total_commission = sum(
                commission.commission_amount 
                for commission in invoice.commission_ids
            )
    
    # ========================
    # ONCHANGE METHODS
    # ========================
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """
        Mengisi diskon otomatis jika customer punya diskon khusus.
        Dijalankan saat user memilih customer.
        """
        if self.partner_id and self.partner_id.twh_discount_percent > 0:
            self.discount_percent = self.partner_id.twh_discount_percent
    
    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        """
        Reset termin pembayaran jika tipe pembayaran cash.
        Cash tidak butuh jatuh tempo.
        """
        if self.payment_type == 'cash':
            self.payment_term_days = 0
    
    # ========================
    # CRUD METHODS
    # ========================
    
    @api.model
    def create(self, vals):
        """
        Override create untuk generate nomor invoice otomatis.
        Format: TWH/INV/YYYY/00001
        """
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('twh.invoice') or 'New'
        
        return super(TwhInvoice, self).create(vals)
    
    # ========================
    # ACTION METHODS
    # ========================
    
    def action_confirm(self):
        """
        Konfirmasi invoice.
        
        Setelah dikonfirmasi:
        - Status berubah jadi 'confirmed'
        - Komisi sales dibuat otomatis
        - Jika cash, pembayaran full langsung dibuat
        """
        for invoice in self:
            # Validasi harus ada produk
            if not invoice.invoice_line_ids:
                raise UserError(_('Tidak bisa konfirmasi invoice tanpa produk!'))
            
            # Update status
            invoice.write({'state': 'confirmed'})
            
            # Buat komisi untuk sales
            invoice._create_commission()
            
            # Jika cash, langsung buat pembayaran full
            if invoice.payment_type == 'cash':
                self.env['twh.payment'].create({
                    'invoice_id': invoice.id,
                    'payment_date': invoice.date_invoice,
                    'amount': invoice.total,
                    'payment_method': 'cash',
                    'note': 'Pembayaran cash saat invoice dibuat',
                })
            
            # Kirim notifikasi
            invoice.message_post(body=_('Invoice telah dikonfirmasi'))
    
    def action_mark_paid(self):
        """
        Tandai invoice sebagai lunas manual.
        Biasanya digunakan jika pembayaran di luar sistem.
        """
        for invoice in self:
            invoice.write({'state': 'paid'})
            invoice.message_post(body=_('Invoice ditandai lunas'))
    
    def action_cancel(self):
        """
        Batalkan invoice.
        
        Saat dibatalkan:
        - Status jadi 'cancelled'
        - Komisi sales dihapus
        - Pembayaran dihapus
        """
        for invoice in self:
            invoice.write({'state': 'cancelled'})
            
            # Hapus komisi
            invoice.commission_ids.unlink()
            
            # Hapus pembayaran
            invoice.payment_ids.unlink()
            
            invoice.message_post(body=_('Invoice dibatalkan'))
    
    def action_set_to_draft(self):
        """
        Kembalikan invoice ke draft.
        Bisa digunakan untuk edit invoice yang sudah dikonfirmasi.
        """
        for invoice in self:
            invoice.write({'state': 'draft'})
            invoice.message_post(body=_('Invoice dikembalikan ke draft'))
    
    def action_add_payment(self):
        """
        Buka form untuk tambah pembayaran (cicilan).
        """
        self.ensure_one()
        
        # Validasi invoice harus sudah dikonfirmasi
        if self.state not in ['confirmed', 'partial', 'overdue']:
            raise UserError(_('Hanya invoice yang sudah dikonfirmasi yang bisa dibayar!'))
        
        # Validasi masih ada sisa tagihan
        if self.remaining_amount <= 0:
            raise UserError(_('Invoice sudah lunas!'))
        
        # Buka form payment baru
        return {
            'type': 'ir.actions.act_window',
            'name': 'Catat Pembayaran',
            'res_model': 'twh.payment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_invoice_id': self.id,
                'default_amount': self.remaining_amount,
            }
        }
    
    def action_view_payments(self):
        """
        Lihat semua pembayaran untuk invoice ini.
        """
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Riwayat Pembayaran',
            'res_model': 'twh.payment',
            'view_mode': 'tree,form',
            'domain': [('invoice_id', '=', self.id)],
            'context': {'default_invoice_id': self.id}
        }
    
    def action_view_sale_order(self):
        """
        Lihat Sales Order yang generate invoice ini.
        """
        self.ensure_one()
        
        if not self.sale_order_id:
            raise UserError(_('Invoice ini tidak dibuat dari Sales Order.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Order',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_print_invoice(self):
        """Cetak invoice ke PDF."""
        return self.env.ref('twh_racing_part.action_report_twh_invoice').report_action(self)
    
    # ========================
    # BUSINESS METHODS
    # ========================
    
    def _create_commission(self):
        """
        Buat komisi sales berdasarkan margin produk.
        
        Komisi dihitung dari selisih harga jual dengan harga bayu (cost).
        Contoh:
        - Harga Bayu (cost): Rp 100.000
        - Harga Jual (A/B/Dealer): Rp 120.000
        - Margin: Rp 20.000
        - Qty: 5
        - Komisi: Rp 20.000 x 5 = Rp 100.000
        """
        self.ensure_one()
        
        # Hapus komisi yang sudah ada (kalau di re-confirm)
        self.commission_ids.unlink()
        
        commission_model = self.env['twh.sales.commission']
        
        # Loop setiap produk di invoice
        for line in self.invoice_line_ids:
            # Ambil harga bayu (cost) produk
            cost_price = line.product_id.get_price_by_tier('bayu')
            
            # Harga jual ke customer
            selling_price = line.price_unit
            
            # Hitung margin per unit
            margin = selling_price - cost_price
            
            # Hitung total komisi
            commission_amount = margin * line.quantity
            
            # Buat record komisi jika ada untung
            if commission_amount > 0:
                commission_model.create({
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


class TwhInvoiceLine(models.Model):
    """
    Model untuk detail produk di invoice.
    Satu invoice bisa punya banyak line (banyak produk).
    """
    _name = 'twh.invoice.line'
    _description = 'Detail Produk Invoice'
    _order = 'invoice_id, sequence, id'
    
    # ========================
    # FIELDS
    # ========================
    
    sequence = fields.Integer(
        string='Urutan', 
        default=10,
        help='Urutan tampilan produk di invoice'
    )
    
    invoice_id = fields.Many2one(
        'twh.invoice', 
        string='Invoice', 
        required=True, 
        ondelete='cascade',
        help='Invoice induk'
    )
    
    product_id = fields.Many2one(
        'product.product', 
        string='Produk', 
        required=True, 
        domain=[('sale_ok', '=', True)],
        help='Produk yang dijual'
    )
    
    description = fields.Text(
        string='Deskripsi',
        help='Deskripsi produk (opsional, default dari nama produk)'
    )
    
    quantity = fields.Float(
        string='Jumlah', 
        default=1.0, 
        digits='Product Unit of Measure',
        help='Jumlah produk yang dibeli'
    )
    
    price_unit = fields.Monetary(
        string='Harga Satuan', 
        required=True, 
        currency_field='currency_id',
        help='Harga per unit produk'
    )
    
    subtotal = fields.Monetary(
        string='Subtotal', 
        compute='_compute_subtotal', 
        store=True, 
        currency_field='currency_id',
        help='Total harga = jumlah x harga satuan'
    )
    
    currency_id = fields.Many2one(
        related='invoice_id.currency_id', 
        string='Mata Uang'
    )
    
    price_tier = fields.Selection(
        related='invoice_id.price_tier', 
        store=True,
        string='Kategori Harga'
    )
    
    # ========================
    # COMPUTED METHODS
    # ========================
    
    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        """Menghitung subtotal = jumlah x harga satuan."""
        for line in self:
            line.subtotal = line.quantity * line.price_unit
    
    # ========================
    # ONCHANGE METHODS
    # ========================
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """
        Isi otomatis deskripsi dan harga saat produk dipilih.
        
        Harga diambil sesuai kategori harga invoice (A/B/Dealer).
        """
        if self.product_id:
            # Isi deskripsi dari nama produk
            self.description = self.product_id.name
            
            # Isi harga sesuai kategori harga invoice
            if self.invoice_id.price_tier:
                tier_code = self.invoice_id.price_tier
                price = self.product_id.get_price_by_tier(tier_code)
                
                if price > 0:
                    self.price_unit = price
    
    # ========================
    # CONSTRAINTS
    # ========================
    
    @api.constrains('quantity')
    def _check_quantity(self):
        """Validasi jumlah harus lebih dari 0."""
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_('Jumlah produk harus lebih dari 0!'))