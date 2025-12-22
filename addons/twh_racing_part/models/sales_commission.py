# -*- coding: utf-8 -*-

import calendar
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TwhSalesCommission(models.Model):
    """
    Model untuk tracking komisi sales.
    
    Komisi dihitung berdasarkan margin produk (selisih harga jual dengan harga bayu).
    Setiap invoice yang dikonfirmasi akan otomatis generate komisi untuk sales.
    """
    _name = 'twh.sales.commission'
    _description = 'Komisi Sales TWH'
    _order = 'date desc, id desc'
    
    # ========================
    # FIELDS
    # ========================
    
    # Referensi
    invoice_id = fields.Many2one(
        'twh.invoice',
        string='Invoice',
        required=True,
        ondelete='cascade',
        help='Invoice yang menghasilkan komisi ini'
    )
    
    invoice_name = fields.Char(
        related='invoice_id.name',
        string='Nomor Invoice',
        store=True
    )
    
    sales_person_id = fields.Many2one(
        'res.users',
        string='Sales Person',
        required=True,
        help='Sales yang mendapat komisi'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Produk',
        required=True,
        help='Produk yang menghasilkan komisi'
    )
    
    # Quantity & Harga
    quantity = fields.Float(
        string='Jumlah',
        required=True,
        digits='Product Unit of Measure',
        help='Jumlah produk yang terjual'
    )
    
    cost_price = fields.Monetary(
        string='Harga Bayu',
        required=True,
        currency_field='currency_id',
        help='Harga dasar/cost produk'
    )
    
    selling_price = fields.Monetary(
        string='Harga Jual',
        required=True,
        currency_field='currency_id',
        help='Harga jual ke toko (A/B/Dealer)'
    )
    
    margin = fields.Monetary(
        string='Margin per Unit',
        required=True,
        currency_field='currency_id',
        help='Selisih harga jual - harga bayu'
    )
    
    commission_amount = fields.Monetary(
        string='Total Komisi',
        required=True,
        currency_field='currency_id',
        help='Total komisi = margin x quantity'
    )
    
    # Tanggal & Mata Uang
    date = fields.Date(
        string='Tanggal Komisi',
        required=True,
        default=fields.Date.today,
        index=True,
        help='Tanggal invoice dikonfirmasi'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang',
        default=lambda self: self.env.company.currency_id
    )
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Dikonfirmasi'),
        ('paid', 'Sudah Dibayar'),
    ], string='Status', default='confirmed', tracking=True,
       help='Status pembayaran komisi')
    
    # Pembayaran Komisi
    payment_date = fields.Date(
        string='Tanggal Pembayaran',
        help='Tanggal komisi dibayarkan ke sales'
    )
    
    payment_notes = fields.Text(
        string='Catatan Pembayaran',
        help='Keterangan pembayaran komisi'
    )
    
    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Perusahaan',
        default=lambda self: self.env.company
    )
    
    # ========================
    # BUSINESS METHODS
    # ========================
    
    @api.model
    def get_commission_summary(self, sales_person_id=None, date_from=None, date_to=None):
        """
        Ambil ringkasan komisi untuk reporting.
        
        Args:
            sales_person_id (int, optional): Filter by sales person
            date_from (date, optional): Tanggal mulai
            date_to (date, optional): Tanggal akhir
        
        Returns:
            dict: Ringkasan komisi dengan struktur:
                {
                    'total_commission': float,
                    'total_quantity': float,
                    'total_invoices': int,
                    'commissions': recordset
                }
        """
        # Build domain filter
        domain = [('state', 'in', ['confirmed', 'paid'])]
        
        if sales_person_id:
            domain.append(('sales_person_id', '=', sales_person_id))
        
        if date_from:
            domain.append(('date', '>=', date_from))
        
        if date_to:
            domain.append(('date', '<=', date_to))
        
        # Query komisi
        commissions = self.search(domain)
        
        # Hitung summary
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
        Ambil komisi untuk bulan tertentu.
        
        Args:
            sales_person_id (int): ID sales person
            year (int): Tahun (contoh: 2025)
            month (int): Bulan (1-12)
        
        Returns:
            dict: Ringkasan komisi bulan tersebut
        """
        # Tanggal awal bulan
        date_from = fields.Date.from_string(f'{year}-{month:02d}-01')
        
        # Tanggal akhir bulan (ambil hari terakhir)
        last_day = calendar.monthrange(year, month)[1]
        date_to = fields.Date.from_string(f'{year}-{month:02d}-{last_day}')
        
        return self.get_commission_summary(sales_person_id, date_from, date_to)
    
    # ========================
    # ACTION METHODS
    # ========================
    
    def action_mark_paid(self):
        """
        Tandai komisi sudah dibayar.
        
        Biasanya digunakan setelah komisi ditransfer ke sales.
        """
        for commission in self:
            commission.write({
                'state': 'paid',
                'payment_date': fields.Date.today(),
            })
    
    def action_confirm(self):
        """
        Konfirmasi komisi.
        
        Komisi biasanya sudah auto-confirmed saat invoice dikonfirmasi.
        """
        for commission in self:
            commission.write({'state': 'confirmed'})


class TwhCommissionReportWizard(models.TransientModel):
    """
    Wizard untuk generate laporan komisi sales.
    
    Wizard ini memudahkan user memilih periode dan sales person
    untuk generate laporan komisi.
    """
    _name = 'twh.commission.report.wizard'
    _description = 'Wizard Laporan Komisi'
    
    # ========================
    # FIELDS
    # ========================
    
    sales_person_id = fields.Many2one(
        'res.users',
        string='Sales Person',
        help='Kosongkan untuk semua sales'
    )
    
    date_from = fields.Date(
        string='Dari Tanggal',
        required=True,
        default=lambda self: fields.Date.today().replace(day=1),
        help='Tanggal mulai periode laporan'
    )
    
    date_to = fields.Date(
        string='Sampai Tanggal',
        required=True,
        default=fields.Date.today,
        help='Tanggal akhir periode laporan'
    )
    
    period_type = fields.Selection([
        ('custom', 'Periode Custom'),
        ('this_month', 'Bulan Ini'),
        ('last_month', 'Bulan Lalu'),
        ('this_quarter', 'Kuartal Ini'),
        ('this_year', 'Tahun Ini'),
    ], string='Periode', default='this_month',
       help='Pilih preset periode atau custom')
    
    # ========================
    # ONCHANGE METHODS
    # ========================
    
    @api.onchange('period_type')
    def _onchange_period_type(self):
        """
        Auto-set tanggal berdasarkan tipe periode yang dipilih.
        
        Memudahkan user tidak perlu input tanggal manual untuk
        periode yang umum digunakan.
        """
        today = fields.Date.today()
        
        if self.period_type == 'this_month':
            # Bulan ini: dari tanggal 1 sampai akhir bulan
            self.date_from = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            self.date_to = today.replace(day=last_day)
        
        elif self.period_type == 'last_month':
            # Bulan lalu
            first_day_this_month = today.replace(day=1)
            last_day_last_month = first_day_this_month - timedelta(days=1)
            first_day_last_month = last_day_last_month.replace(day=1)
            
            self.date_from = first_day_last_month
            self.date_to = last_day_last_month
        
        elif self.period_type == 'this_year':
            # Tahun ini: dari 1 Januari sampai 31 Desember
            self.date_from = today.replace(month=1, day=1)
            self.date_to = today.replace(month=12, day=31)
    
    # ========================
    # ACTION METHODS
    # ========================
    
    def action_print_report(self):
        """
        Cetak laporan komisi ke PDF.
        
        Returns:
            dict: Action untuk print report
        """
        data = {
            'sales_person_id': self.sales_person_id.id if self.sales_person_id else False,
            'date_from': self.date_from,
            'date_to': self.date_to,
        }
        
        return self.env.ref('twh_racing_part.action_report_sales_commission').report_action(
            self, data=data
        )
    
    def action_export_excel(self):
        """
        Export laporan komisi ke Excel.
        
        TODO: Implementasi export Excel akan dikembangkan nanti.
        """
        commission_model = self.env['twh.sales.commission']
        
        summary = commission_model.get_commission_summary(
            self.sales_person_id.id if self.sales_person_id else None,
            self.date_from,
            self.date_to
        )
        
        raise UserError(_('Fitur export Excel akan dikembangkan dalam versi selanjutnya'))