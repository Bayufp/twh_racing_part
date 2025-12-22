# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResPartner(models.Model):
    """
    Extend model res.partner untuk tambah field khusus TWH.
    
    Field tambahan:
    - Status TWH customer
    - Kode customer
    - Diskon khusus
    - Tipe customer (retail, workshop, dealer, distributor)
    - Statistik invoice
    """
    _inherit = 'res.partner'
    
    # ========================
    # FIELDS - TWH SPECIFIC
    # ========================
    
    is_twh_customer = fields.Boolean(
        string='Customer TWH',
        default=False,
        help='Centang jika ini adalah customer TWH Racing Part'
    )
    
    twh_customer_code = fields.Char(
        string='Kode Customer',
        help='Kode unik customer (contoh: TKO001, DLR001)'
    )
    
    twh_discount_percent = fields.Float(
        string='Diskon Khusus (%)',
        default=0.0,
        digits='Discount',
        help='Persentase diskon khusus untuk customer ini (misal: 3%)'
    )
    
    # Tipe Customer
    twh_customer_type = fields.Selection([
        ('retail', 'Toko Retail'),
        ('workshop', 'Bengkel'),
        ('dealer', 'Dealer'),
        ('distributor', 'Distributor'),
    ], string='Tipe Customer',
       help='Kategori bisnis customer')
    
    # ========================
    # FIELDS - INVOICE STATISTICS
    # ========================
    
    twh_invoice_ids = fields.One2many(
        'twh.invoice',
        'partner_id',
        string='Invoice TWH',
        help='Daftar semua invoice customer ini'
    )
    
    twh_invoice_count = fields.Integer(
        string='Jumlah Invoice',
        compute='_compute_twh_invoice_stats',
        help='Total invoice yang pernah dibuat'
    )
    
    twh_total_invoiced = fields.Monetary(
        string='Total Penjualan',
        compute='_compute_twh_invoice_stats',
        currency_field='currency_id',
        help='Total nilai semua invoice'
    )
    
    twh_total_outstanding = fields.Monetary(
        string='Total Piutang',
        compute='_compute_twh_invoice_stats',
        currency_field='currency_id',
        help='Total tagihan yang belum dibayar'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # ========================
    # COMPUTED METHODS
    # ========================
    
    @api.depends('twh_invoice_ids', 'twh_invoice_ids.state', 'twh_invoice_ids.total')
    def _compute_twh_invoice_stats(self):
        """
        Hitung statistik invoice customer.
        
        Menghitung:
        1. Jumlah invoice (yang sudah confirmed/paid)
        2. Total penjualan (nilai semua invoice)
        3. Total piutang (invoice yang belum lunas)
        """
        for partner in self:
            # Filter invoice yang valid (bukan draft/cancelled)
            valid_invoices = partner.twh_invoice_ids.filtered(
                lambda inv: inv.state in ['confirmed', 'partial', 'paid', 'overdue']
            )
            
            # Hitung jumlah invoice
            partner.twh_invoice_count = len(valid_invoices)
            
            # Hitung total penjualan
            partner.twh_total_invoiced = sum(valid_invoices.mapped('total'))
            
            # Hitung total piutang (invoice yang belum lunas)
            outstanding_invoices = valid_invoices.filtered(
                lambda inv: inv.state in ['confirmed', 'partial', 'overdue']
            )
            partner.twh_total_outstanding = sum(outstanding_invoices.mapped('remaining_amount'))
    
    # ========================
    # ACTION METHODS
    # ========================
    
    def action_view_twh_invoices(self):
        """
        Buka daftar invoice customer ini.
        
        Action ini akan membuka tree view invoice yang di-filter
        hanya untuk customer yang dipilih.
        
        Returns:
            dict: Action untuk buka window invoice
        """
        self.ensure_one()
        
        return {
            'name': _('Invoice TWH - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'twh.invoice',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
            'help': """
                <p class="o_view_nocontent_smiling_face">
                    Belum ada invoice untuk customer ini
                </p>
                <p>
                    Klik tombol Create untuk membuat invoice baru.
                </p>
            """
        }