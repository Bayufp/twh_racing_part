# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class TwhProductAnalytics(models.Model):
    """
    Model analitik produk terlaris (SQL View).
    
    Model ini adalah SQL view (bukan table biasa) yang menampilkan
    statistik penjualan produk secara real-time dari data invoice.
    
    Data yang ditampilkan:
    - Produk apa saja yang terjual
    - Berapa quantity terjual
    - Total nilai penjualan
    - Berapa kali muncul di invoice
    - Rata-rata harga jual
    """
    _name = 'twh.product.analytics'
    _description = 'Analitik Produk Terlaris'
    _auto = False  # Ini SQL view, bukan table
    _order = 'total_quantity desc, total_value desc'
    
    # ========================
    # FIELDS
    # ========================
    
    # Informasi Produk
    product_id = fields.Many2one(
        'product.product',
        string='Produk',
        readonly=True
    )
    
    product_name = fields.Char(
        string='Nama Produk',
        readonly=True
    )
    
    product_category = fields.Char(
        string='Kategori',
        readonly=True
    )
    
    # Data Penjualan
    total_quantity = fields.Float(
        string='Total Terjual',
        readonly=True,
        help='Total quantity yang terjual'
    )
    
    total_value = fields.Monetary(
        string='Total Nilai Penjualan',
        readonly=True,
        currency_field='currency_id',
        help='Total nilai penjualan dalam rupiah'
    )
    
    invoice_count = fields.Integer(
        string='Jumlah Invoice',
        readonly=True,
        help='Berapa kali produk ini muncul di invoice'
    )
    
    avg_price = fields.Monetary(
        string='Rata-rata Harga',
        readonly=True,
        currency_field='currency_id',
        help='Rata-rata harga jual produk'
    )
    
    # Periode
    period_start = fields.Date(
        string='Periode Mulai',
        readonly=True
    )
    
    period_end = fields.Date(
        string='Periode Akhir',
        readonly=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang',
        readonly=True
    )
    
    # ========================
    # INIT METHOD (Create SQL View)
    # ========================
    
    def init(self):
        """
        Buat SQL view untuk analitik.
        
        View ini mengambil data dari:
        - twh_invoice_line (detail produk di invoice)
        - twh_invoice (status invoice)
        - product_product & product_template (info produk)
        
        Hanya menghitung invoice dengan status confirmed atau paid.
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        
        query = """
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY SUM(il.quantity) DESC) as id,
                    il.product_id,
                    pt.name as product_name,
                    pt.twh_category as product_category,
                    SUM(il.quantity) as total_quantity,
                    SUM(il.subtotal) as total_value,
                    COUNT(DISTINCT il.invoice_id) as invoice_count,
                    AVG(il.price_unit) as avg_price,
                    MIN(inv.date_invoice) as period_start,
                    MAX(inv.date_invoice) as period_end,
                    inv.currency_id
                FROM
                    twh_invoice_line il
                    INNER JOIN twh_invoice inv ON il.invoice_id = inv.id
                    INNER JOIN product_product pp ON il.product_id = pp.id
                    INNER JOIN product_template pt ON pp.product_tmpl_id = pt.id
                WHERE
                    inv.state IN ('confirmed', 'paid', 'partial', 'overdue')
                GROUP BY
                    il.product_id,
                    pt.name,
                    pt.twh_category,
                    inv.currency_id
            )
        """ % self._table
        
        self.env.cr.execute(query)


class TwhAnalyticsWizard(models.TransientModel):
    """
    Wizard untuk filter analitik produk.
    
    Wizard ini memudahkan user untuk:
    1. Pilih periode (bulan ini, 3 bulan, 6 bulan, tahun ini, custom)
    2. Pilih top N produk (10, 20, 50, dst)
    3. Sort berdasarkan quantity atau nilai penjualan
    """
    _name = 'twh.analytics.wizard'
    _description = 'Wizard Filter Analitik'
    
    # ========================
    # FIELDS
    # ========================
    
    period_type = fields.Selection([
        ('this_month', 'Bulan Ini'),
        ('last_3_months', '3 Bulan Terakhir'),
        ('last_6_months', '6 Bulan Terakhir'),
        ('this_year', 'Tahun Ini'),
        ('custom', 'Periode Custom'),
    ], string='Periode', default='this_month', required=True,
       help='Pilih periode waktu untuk analitik')
    
    date_from = fields.Date(
        string='Dari Tanggal',
        help='Tanggal mulai (untuk custom period)'
    )
    
    date_to = fields.Date(
        string='Sampai Tanggal',
        default=fields.Date.today,
        help='Tanggal akhir (untuk custom period)'
    )
    
    top_n = fields.Integer(
        string='Top N Produk',
        default=10,
        help='Tampilkan berapa produk teratas'
    )
    
    sort_by = fields.Selection([
        ('quantity', 'Berdasarkan Quantity'),
        ('value', 'Berdasarkan Nilai Penjualan'),
    ], string='Urutkan Berdasarkan', default='quantity',
       help='Cara mengurutkan produk')
    
    # ========================
    # ONCHANGE METHODS
    # ========================
    
    @api.onchange('period_type')
    def _onchange_period_type(self):
        """
        Auto-calculate range tanggal berdasarkan tipe periode.
        
        Memudahkan user tidak perlu input tanggal manual untuk
        periode yang sering dipakai.
        """
        today = fields.Date.today()
        
        if self.period_type == 'this_month':
            # Bulan ini: dari tanggal 1 sampai sekarang
            self.date_from = today.replace(day=1)
            self.date_to = today
        
        elif self.period_type == 'last_3_months':
            # 3 bulan terakhir
            self.date_from = today - relativedelta(months=3)
            self.date_to = today
        
        elif self.period_type == 'last_6_months':
            # 6 bulan terakhir
            self.date_from = today - relativedelta(months=6)
            self.date_to = today
        
        elif self.period_type == 'this_year':
            # Tahun ini: dari 1 Januari sampai sekarang
            self.date_from = today.replace(month=1, day=1)
            self.date_to = today
    
    # ========================
    # ACTION METHODS
    # ========================
    
    def action_view_analytics(self):
        """
        Tampilkan hasil analitik.
        
        Method ini akan:
        1. Ambil data sesuai filter
        2. Buka tree view dengan hasil analitik
        
        Returns:
            dict: Action untuk buka window analitik
        """
        self.ensure_one()
        
        # Ambil data analitik
        analytics_data = self._get_analytics_data()
        
        # Return action untuk tampilkan data
        return {
            'name': _('Analitik Produk Terlaris'),
            'type': 'ir.actions.act_window',
            'res_model': 'twh.product.analytics.result',
            'view_mode': 'tree,graph,pivot',
            'domain': [],
            'context': {
                'default_period_type': self.period_type,
                'analytics_data': analytics_data,
            },
            'help': """
                <p class="o_view_nocontent_smiling_face">
                    Belum ada data penjualan
                </p>
                <p>
                    Data akan muncul setelah ada invoice yang dikonfirmasi.
                </p>
            """
        }
    
    def action_export_excel(self):
        """
        Export hasil analitik ke Excel.
        
        TODO: Fitur ini akan dikembangkan dalam versi berikutnya.
        """
        # TODO: Implement Excel export
        pass
    
    def _get_analytics_data(self):
        """
        Ambil dan process data analitik sesuai filter.
        
        Returns:
            list: List of dict berisi data analitik per produk
        """
        # Build domain untuk filter invoice lines
        domain = self._build_invoice_domain()
        
        # Query invoice lines
        invoice_lines = self.env['twh.invoice.line'].search(domain)
        
        # Group data per produk
        product_data = self._group_by_product(invoice_lines)
        
        # Sort data
        sorted_data = self._sort_product_data(product_data)
        
        # Ambil top N produk
        if self.top_n > 0:
            sorted_data = sorted_data[:self.top_n]
        
        return sorted_data
    
    def _build_invoice_domain(self):
        """
        Build domain filter untuk query invoice.
        
        Returns:
            list: Domain untuk search invoice lines
        """
        domain = [
            ('invoice_id.state', 'in', ['confirmed', 'paid', 'partial', 'overdue']),
        ]
        
        if self.date_from:
            domain.append(('invoice_id.date_invoice', '>=', self.date_from))
        
        if self.date_to:
            domain.append(('invoice_id.date_invoice', '<=', self.date_to))
        
        return domain
    
    def _group_by_product(self, invoice_lines):
        """
        Group invoice lines per produk dan hitung statistik.
        
        Args:
            invoice_lines: Recordset invoice lines
        
        Returns:
            dict: Dictionary dengan key product_id dan value statistik
        """
        product_data = {}
        
        for line in invoice_lines:
            product_id = line.product_id.id
            
            # Inisialisasi data produk jika belum ada
            if product_id not in product_data:
                product_data[product_id] = {
                    'product_id': product_id,
                    'product_name': line.product_id.name,
                    'total_quantity': 0,
                    'total_value': 0,
                    'invoice_count': set(),  # Pakai set untuk unique invoice
                }
            
            # Akumulasi data
            product_data[product_id]['total_quantity'] += line.quantity
            product_data[product_id]['total_value'] += line.subtotal
            product_data[product_id]['invoice_count'].add(line.invoice_id.id)
        
        return product_data
    
    def _sort_product_data(self, product_data):
        """
        Sort data produk sesuai pilihan user.
        
        Args:
            product_data (dict): Dictionary data produk
        
        Returns:
            list: List of dict yang sudah disort
        """
        # Convert set invoice_count jadi int
        result = []
        for data in product_data.values():
            data['invoice_count'] = len(data['invoice_count'])
            result.append(data)
        
        # Sort sesuai pilihan
        if self.sort_by == 'quantity':
            result.sort(key=lambda x: x['total_quantity'], reverse=True)
        else:
            result.sort(key=lambda x: x['total_value'], reverse=True)
        
        return result


class TwhAnalyticsResult(models.TransientModel):
    """
    Model transient untuk tampilkan hasil analitik.
    
    Model ini temporary, datanya tidak disimpan ke database.
    Hanya untuk display hasil analitik di UI.
    """
    _name = 'twh.product.analytics.result'
    _description = 'Hasil Analitik Produk'
    
    # ========================
    # FIELDS
    # ========================
    
    product_id = fields.Many2one(
        'product.product',
        string='Produk'
    )
    
    product_name = fields.Char(
        string='Nama Produk'
    )
    
    total_quantity = fields.Float(
        string='Total Terjual'
    )
    
    total_value = fields.Monetary(
        string='Total Nilai',
        currency_field='currency_id'
    )
    
    invoice_count = fields.Integer(
        string='Jumlah Invoice'
    )
    
    avg_price = fields.Monetary(
        string='Harga Rata-rata',
        compute='_compute_avg_price',
        currency_field='currency_id'
    )
    
    rank = fields.Integer(
        string='Peringkat'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # ========================
    # COMPUTED METHODS
    # ========================
    
    @api.depends('total_value', 'total_quantity')
    def _compute_avg_price(self):
        """Hitung rata-rata harga dari total nilai / total quantity."""
        for record in self:
            if record.total_quantity > 0:
                record.avg_price = record.total_value / record.total_quantity
            else:
                record.avg_price = 0.0


class TwhDashboard(models.Model):
    """
    Model untuk dashboard metrics.
    
    Model ini menyediakan data summary untuk widget dashboard.
    """
    _name = 'twh.dashboard'
    _description = 'Dashboard Metrics TWH'
    
    # ========================
    # METHODS
    # ========================
    
    @api.model
    def get_dashboard_data(self, period='this_month'):
        """
        Ambil data dashboard untuk widget.
        
        Args:
            period (str): Periode data ('this_month', 'last_3_months', dll)
        
        Returns:
            dict: Dictionary berisi metrics dashboard
        """
        today = fields.Date.today()
        
        # Tentukan range tanggal
        date_from, date_to = self._get_date_range(period, today)
        
        # Query invoice
        invoices = self._get_invoices(date_from, date_to)
        
        # Hitung metrics
        metrics = self._calculate_metrics(invoices)
        
        # Ambil top products
        top_products = self._get_top_products(invoices)
        
        return {
            **metrics,
            'top_products_by_qty': top_products,
            'period': period,
            'date_from': date_from,
            'date_to': date_to,
        }
    
    def _get_date_range(self, period, today):
        """
        Tentukan range tanggal berdasarkan periode.
        
        Args:
            period (str): Tipe periode
            today (date): Tanggal hari ini
        
        Returns:
            tuple: (date_from, date_to)
        """
        if period == 'this_month':
            date_from = today.replace(day=1)
            date_to = today
        elif period == 'last_3_months':
            date_from = today - relativedelta(months=3)
            date_to = today
        elif period == 'last_6_months':
            date_from = today - relativedelta(months=6)
            date_to = today
        elif period == 'this_year':
            date_from = today.replace(month=1, day=1)
            date_to = today
        else:
            date_from = today.replace(month=1, day=1)
            date_to = today
        
        return date_from, date_to
    
    def _get_invoices(self, date_from, date_to):
        """
        Query invoice dalam periode tertentu.
        
        Args:
            date_from (date): Tanggal mulai
            date_to (date): Tanggal akhir
        
        Returns:
            recordset: Invoice yang memenuhi kriteria
        """
        return self.env['twh.invoice'].search([
            ('date_invoice', '>=', date_from),
            ('date_invoice', '<=', date_to),
            ('state', 'in', ['confirmed', 'paid', 'partial', 'overdue']),
        ])
    
    def _calculate_metrics(self, invoices):
        """
        Hitung metrics dari invoice.
        
        Args:
            invoices: Recordset invoice
        
        Returns:
            dict: Dictionary berisi metrics
        """
        total_sales = sum(invoices.mapped('total'))
        total_invoices = len(invoices)
        total_commission = sum(invoices.mapped('total_commission'))
        
        avg_invoice_value = total_sales / total_invoices if total_invoices > 0 else 0
        
        return {
            'total_sales': total_sales,
            'total_invoices': total_invoices,
            'total_commission': total_commission,
            'avg_invoice_value': avg_invoice_value,
        }
    
    def _get_top_products(self, invoices):
        """
        Ambil top 10 produk terlaris.
        
        Args:
            invoices: Recordset invoice
        
        Returns:
            list: List of dict top products
        """
        invoice_lines = invoices.mapped('invoice_line_ids')
        product_sales = {}
        
        # Group per produk
        for line in invoice_lines:
            product_id = line.product_id.id
            
            if product_id not in product_sales:
                product_sales[product_id] = {
                    'product': line.product_id,
                    'quantity': 0,
                    'value': 0,
                }
            
            product_sales[product_id]['quantity'] += line.quantity
            product_sales[product_id]['value'] += line.subtotal
        
        # Sort berdasarkan quantity dan ambil top 10
        top_products = sorted(
            product_sales.values(),
            key=lambda x: x['quantity'],
            reverse=True
        )[:10]
        
        return top_products