# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class TwhDashboardController(http.Controller):
    """
    Controller untuk endpoint API dashboard TWH Racing Part.
    
    Controller ini menyediakan endpoint JSON untuk:
    1. Ambil data penjualan bulanan
    2. Ambil summary statistics dashboard
    
    Endpoint ini dipanggil oleh frontend JavaScript (OWL component).
    """

    @http.route('/twh/dashboard/sales_data', type='json', auth='user')
    def get_sales_data(self, **kwargs):
        """
        Endpoint untuk ambil data penjualan bulanan.
        
        Endpoint ini return data penjualan (invoice created) untuk
        6 bulan terakhir dalam format yang siap digunakan untuk chart.
        
        Args:
            **kwargs: Parameter tambahan (tidak digunakan saat ini)
        
        Returns:
            list: List of dict dengan format:
                [
                    {'month': 'Jan 2025', 'amount': 50000000},
                    {'month': 'Feb 2025', 'amount': 65000000},
                    ...
                ]
                
                Return list kosong jika terjadi error.
        
        Authentication:
            Memerlukan user login (auth='user')
        
        Example:
            POST /twh/dashboard/sales_data
            Response: [
                {"month": "Jul 2024", "amount": 45000000},
                {"month": "Aug 2024", "amount": 52000000},
                ...
            ]
        """
        try:
            # Ambil model dashboard
            dashboard_model = request.env['twh.dashboard']
            
            # Query data penjualan 6 bulan
            sales_data = dashboard_model.get_sales_data(months=6)
            
            _logger.info(
                f'API /twh/dashboard/sales_data dipanggil - '
                f'return {len(sales_data)} bulan data'
            )
            
            return sales_data
            
        except Exception as error:
            _logger.error(f'Error di endpoint sales_data: {str(error)}')
            _logger.exception('Detail error:')
            return []

    @http.route('/twh/dashboard/summary', type='json', auth='user')
    def get_dashboard_summary(self, **kwargs):
        """
        Endpoint untuk ambil summary statistics dashboard.
        
        Endpoint ini return semua data summary yang ditampilkan di dashboard:
        - Total produk aktif
        - Total customer aktif
        - Invoice belum lunas
        - Total piutang
        - Revenue (dengan filter periode)
        - Data penjualan bulanan
        
        Args:
            **kwargs: Parameter tambahan (tidak digunakan saat ini)
        
        Returns:
            dict: Dictionary berisi semua summary data, dengan struktur:
                {
                    'total_products': int,
                    'total_customers': int,
                    'unpaid_invoices': int,
                    'total_outstanding': str (format rupiah),
                    'overdue_count': int,
                    'partial_count': int,
                    'total_revenue': str (format rupiah),
                    'revenue_period': str,
                    'revenue_period_label': str,
                    'revenue_payment_count': int,
                    'revenue_invoice_count': int,
                    'monthly_sales': list
                }
                
                Return dict kosong jika terjadi error.
        
        Authentication:
            Memerlukan user login (auth='user')
        
        Example:
            POST /twh/dashboard/summary
            Response: {
                "total_products": 150,
                "total_customers": 45,
                "unpaid_invoices": 12,
                ...
            }
        """
        try:
            # Ambil model dashboard
            dashboard_model = request.env['twh.dashboard']
            
            # Query summary data (default revenue period: month)
            summary_data = dashboard_model.get_dashboard_summary()
            
            _logger.info(
                f'API /twh/dashboard/summary dipanggil - '
                f'Data: {summary_data.get("total_products", 0)} produk, '
                f'{summary_data.get("total_customers", 0)} customer'
            )
            
            return summary_data
            
        except Exception as error:
            _logger.error(f'Error di endpoint dashboard summary: {str(error)}')
            _logger.exception('Detail error:')
            return {}