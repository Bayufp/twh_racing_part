# -*- coding: utf-8 -*-
from odoo import models, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class TwhDashboard(models.TransientModel):
    _name = 'twh.dashboard'
    _description = 'TWH Dashboard Data Provider'

    @api.model
    def get_sales_data(self, months=6):
        """
        Ambil data penjualan real dari sale.order
        untuk N bulan terakhir
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30 * months)
            
            sales_data = []
            
            for i in range(months):
                # Hitung range tanggal per bulan
                month_start = end_date - timedelta(days=30 * (months - i))
                month_end = month_start + timedelta(days=30)
                
                # Query sale orders yang sudah confirmed
                domain = [
                    ('date_order', '>=', month_start.strftime('%Y-%m-%d')),
                    ('date_order', '<', month_end.strftime('%Y-%m-%d')),
                    ('state', 'in', ['sale', 'done'])  # Hanya yang sudah confirm
                ]
                
                orders = self.env['sale.order'].search(domain)
                
                # Hitung total amount
                total_amount = sum(orders.mapped('amount_total'))
                
                sales_data.append({
                    'month': month_start.strftime('%b %Y'),
                    'amount': round(total_amount, 2)
                })
            
            _logger.info(f"Sales data loaded: {len(sales_data)} months")
            return sales_data
            
        except Exception as e:
            _logger.error(f"Error loading sales data: {str(e)}")
            return []

    @api.model
    def get_dashboard_summary(self):
        """
        Get summary statistics untuk dashboard
        """
        return {
            'total_products': self.env['product.product'].search_count([
                ('sale_ok', '=', True)
            ]),
            'total_customers': self.env['res.partner'].search_count([
                ('customer_rank', '>', 0),
                ('active', '=', True)
            ]),
            'pending_invoices': self.env['account.move'].search_count([
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial'])
            ]),
            'monthly_sales': self.get_sales_data()
        }