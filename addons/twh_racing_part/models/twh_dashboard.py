# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class TwhDashboard(models.TransientModel):
    """
    Model untuk menyediakan data dashboard TWH Racing Part.
    
    Model ini adalah transient (tidak menyimpan data ke database),
    hanya untuk provide data ke frontend dashboard.
    
    Data yang disediakan:
    1. Sales data (invoice yang dibuat per bulan)
    2. Revenue data (pembayaran yang diterima)
    3. Summary statistics (produk, customer, piutang, dll)
    """
    _name = 'twh.dashboard'
    _description = 'Provider Data Dashboard TWH'

    # ========================
    # SALES DATA METHODS
    # ========================

    @api.model
    def get_sales_data(self, months=6):
        """
        Ambil data PENJUALAN (invoice created) untuk N bulan terakhir.
        
        PENTING: Sales = Invoice yang dibuat (bukan payment yang masuk).
        Data ini menunjukkan tren penjualan bisnis.
        
        Args:
            months (int): Jumlah bulan data yang diambil (default: 6)
        
        Returns:
            list: List of dict dengan format:
                [
                    {'month': 'Jan 2025', 'amount': 50000000},
                    {'month': 'Feb 2025', 'amount': 65000000},
                    ...
                ]
        """
        try:
            today = datetime.now()
            sales_data = []
            
            # Loop dari bulan terlama ke terbaru
            for i in range(months):
                # Hitung target bulan
                target_date = today - relativedelta(months=months - i - 1)
                
                # Tentukan range tanggal untuk bulan ini
                date_range = self._get_month_date_range(target_date, today)
                
                # Query invoice untuk bulan ini
                invoices = self._query_invoices_by_date_range(
                    date_range['start'],
                    date_range['end']
                )
                
                # Hitung total sales
                total_amount = sum(invoices.mapped('total'))
                
                # Format label bulan
                month_label = target_date.strftime('%b %Y')
                
                sales_data.append({
                    'month': month_label,
                    'amount': round(total_amount, 2)
                })
                
                # Log untuk debugging
                _logger.info(
                    f'Sales {month_label}: {len(invoices)} invoice, '
                    f'Total: Rp {total_amount:,.0f}'
                )
            
            _logger.info(f'Sales data berhasil dimuat: {len(sales_data)} bulan')
            return sales_data
            
        except Exception as error:
            _logger.error(f'Error saat load sales data: {str(error)}')
            return []

    def _get_month_date_range(self, target_date, today):
        """
        Tentukan range tanggal untuk satu bulan.
        
        Args:
            target_date (datetime): Target bulan
            today (datetime): Tanggal hari ini
        
        Returns:
            dict: {'start': date, 'end': date}
        """
        # Awal bulan
        month_start = target_date.replace(
            day=1, 
            hour=0, 
            minute=0, 
            second=0, 
            microsecond=0
        )
        
        # Akhir bulan (hari ini jika bulan ini, atau akhir bulan jika bulan lalu)
        if target_date.month == today.month and target_date.year == today.year:
            # Bulan ini: sampai hari ini
            month_end = today.replace(
                hour=23, 
                minute=59, 
                second=59, 
                microsecond=999999
            )
        else:
            # Bulan lalu: sampai akhir bulan
            next_month = month_start + relativedelta(months=1)
            month_end = next_month - relativedelta(seconds=1)
        
        return {
            'start': fields.Date.to_string(month_start.date()),
            'end': fields.Date.to_string(month_end.date())
        }

    def _query_invoices_by_date_range(self, date_from, date_to):
        """
        Query invoice berdasarkan range tanggal.
        
        Args:
            date_from (str): Tanggal mulai (format: YYYY-MM-DD)
            date_to (str): Tanggal akhir (format: YYYY-MM-DD)
        
        Returns:
            recordset: Invoice yang memenuhi kriteria
        """
        return self.env['twh.invoice'].search([
            ('date_invoice', '>=', date_from),
            ('date_invoice', '<=', date_to),
            ('state', 'in', ['confirmed', 'partial', 'paid', 'overdue'])
        ])

    # ========================
    # REVENUE DATA METHODS
    # ========================

    @api.model
    def get_total_revenue(self, period='month'):
        """
        Hitung total revenue berdasarkan PEMBAYARAN yang masuk.
        
        Revenue = Total payment yang sudah diterima (confirmed).
        Berbeda dengan sales yang dihitung dari invoice.
        
        Args:
            period (str): Periode revenue ('month', 'year', 'all')
        
        Returns:
            dict: Dictionary berisi:
                {
                    'amount': float (nilai revenue),
                    'formatted': str (format rupiah),
                    'period_label': str (label periode),
                    'payment_count': int (jumlah pembayaran),
                    'invoice_count': int (jumlah invoice),
                    'period': str (periode yang diminta)
                }
        """
        try:
            today = datetime.now()
            
            # Tentukan domain filter berdasarkan periode
            domain = [('state', '=', 'confirmed')]
            period_label = self._add_period_filter(domain, period, today)
            
            # Query payments yang sudah confirmed
            payments = self.env['twh.payment'].search(domain)
            
            # Hitung metrics
            total_amount = sum(payments.mapped('amount'))
            payment_count = len(payments)
            invoice_count = len(payments.mapped('invoice_id'))
            
            # Format currency
            formatted_amount = self._format_currency(total_amount)
            
            _logger.info(
                f'Revenue ({period}): {formatted_amount} '
                f'dari {payment_count} pembayaran, {invoice_count} invoice'
            )
            
            return {
                'amount': total_amount,
                'formatted': formatted_amount,
                'period_label': period_label,
                'payment_count': payment_count,
                'invoice_count': invoice_count,
                'period': period
            }
            
        except Exception as error:
            _logger.error(f'Error saat hitung revenue: {str(error)}')
            return {
                'amount': 0,
                'formatted': 'Rp 0',
                'period_label': 'Error',
                'payment_count': 0,
                'invoice_count': 0,
                'period': period
            }

    def _add_period_filter(self, domain, period, today):
        """
        Tambahkan filter periode ke domain dan return label periode.
        
        Args:
            domain (list): Domain list yang akan dimodifikasi
            period (str): Tipe periode
            today (datetime): Tanggal hari ini
        
        Returns:
            str: Label periode untuk display
        """
        if period == 'month':
            # Bulan ini
            month_start = today.replace(day=1)
            domain.append(('payment_date', '>=', fields.Date.to_string(month_start)))
            domain.append(('payment_date', '<=', fields.Date.to_string(today)))
            return f"{today.strftime('%B %Y')}"
            
        elif period == 'year':
            # Tahun ini
            year_start = today.replace(month=1, day=1)
            domain.append(('payment_date', '>=', fields.Date.to_string(year_start)))
            domain.append(('payment_date', '<=', fields.Date.to_string(today)))
            return f"Tahun {today.year}"
            
        else:  # 'all'
            # All time - tidak tambah filter tanggal
            return "Semua Waktu"

    def _format_currency(self, amount):
        """
        Format angka ke format rupiah Indonesia.
        
        Args:
            amount (float): Jumlah uang
        
        Returns:
            str: Format rupiah (contoh: "Rp 1.500.000")
        """
        return 'Rp {:,.0f}'.format(amount).replace(',', '.')

    # ========================
    # DASHBOARD SUMMARY METHODS
    # ========================

    @api.model
    def get_dashboard_summary(self, revenue_period='month'):
        """
        Ambil summary statistics untuk dashboard.
        
        Data yang disediakan:
        1. Total produk aktif
        2. Total customer aktif
        3. Unpaid invoices (tempo yang belum lunas)
        4. Total outstanding (piutang)
        5. Overdue count (invoice terlambat)
        6. Partial count (invoice cicilan)
        7. Revenue data (sesuai periode)
        8. Monthly sales data (6 bulan)
        
        Args:
            revenue_period (str): Periode untuk revenue ('month', 'year', 'all')
        
        Returns:
            dict: Dictionary berisi semua summary statistics
        """
        try:
            # Hitung unpaid invoices dan outstanding
            unpaid_stats = self._calculate_unpaid_stats()
            
            # Ambil revenue data dengan periode
            revenue_data = self.get_total_revenue(revenue_period)
            
            # Build summary lengkap
            summary = {
                'total_products': self._count_active_products(),
                'total_customers': self._count_active_customers(),
                'unpaid_invoices': unpaid_stats['count'],
                'total_outstanding': unpaid_stats['outstanding_formatted'],
                'overdue_count': unpaid_stats['overdue_count'],
                'partial_count': unpaid_stats['partial_count'],
                'total_revenue': revenue_data['formatted'],
                'revenue_period': revenue_data['period'],
                'revenue_period_label': revenue_data['period_label'],
                'revenue_payment_count': revenue_data['payment_count'],
                'revenue_invoice_count': revenue_data['invoice_count'],
                'monthly_sales': self.get_sales_data()
            }
            
            _logger.info(
                f'Dashboard summary: {summary["total_products"]} produk, '
                f'{summary["total_customers"]} customer, '
                f'{summary["unpaid_invoices"]} unpaid invoice'
            )
            
            return summary
            
        except Exception as error:
            _logger.error(f'Error saat ambil dashboard summary: {str(error)}')
            return self._get_empty_summary()

    def _count_active_products(self):
        """
        Hitung jumlah produk aktif yang bisa dijual.
        
        Returns:
            int: Jumlah produk
        """
        return self.env['product.product'].search_count([
            ('sale_ok', '=', True),
            ('active', '=', True)
        ])

    def _count_active_customers(self):
        """
        Hitung jumlah customer aktif.
        
        Returns:
            int: Jumlah customer
        """
        return self.env['res.partner'].search_count([
            ('customer_rank', '>', 0),
            ('active', '=', True)
        ])

    def _calculate_unpaid_stats(self):
        """
        Hitung statistik invoice yang belum lunas.
        
        UNPAID INVOICES = Invoice tempo yang belum lunas
        (status: confirmed, partial, overdue - exclude paid & cash)
        
        Returns:
            dict: Dictionary berisi:
                {
                    'count': int (jumlah invoice belum lunas),
                    'outstanding': float (total piutang),
                    'outstanding_formatted': str (format rupiah),
                    'overdue_count': int (jumlah terlambat),
                    'partial_count': int (jumlah cicilan)
                }
        """
        # Query unpaid invoices
        unpaid_invoices = self.env['twh.invoice'].search([
            ('payment_type', '=', 'tempo'),
            ('state', 'in', ['confirmed', 'partial', 'overdue']),
        ])
        
        # Hitung total outstanding
        total_outstanding = sum(unpaid_invoices.mapped('remaining_amount'))
        
        # Hitung overdue & partial
        overdue_count = self.env['twh.invoice'].search_count([
            ('state', '=', 'overdue'),
        ])
        
        partial_count = self.env['twh.invoice'].search_count([
            ('state', '=', 'partial'),
        ])
        
        return {
            'count': len(unpaid_invoices),
            'outstanding': total_outstanding,
            'outstanding_formatted': self._format_currency(total_outstanding),
            'overdue_count': overdue_count,
            'partial_count': partial_count,
        }

    def _get_empty_summary(self):
        """
        Return empty summary saat terjadi error.
        
        Returns:
            dict: Summary dengan nilai default/kosong
        """
        return {
            'total_products': 0,
            'total_customers': 0,
            'unpaid_invoices': 0,
            'total_outstanding': 'Rp 0',
            'overdue_count': 0,
            'partial_count': 0,
            'total_revenue': 'Rp 0',
            'revenue_period': 'month',
            'revenue_period_label': 'Bulan Ini',
            'revenue_payment_count': 0,
            'revenue_invoice_count': 0,
            'monthly_sales': []
        }