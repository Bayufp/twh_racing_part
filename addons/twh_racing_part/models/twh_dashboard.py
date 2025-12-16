# -*- coding: utf-8 -*-
from odoo import models, api, fields
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class TwhDashboard(models.TransientModel):
    _name = 'twh.dashboard'
    _description = 'TWH Dashboard Data Provider'

    @api.model
    def get_sales_data(self, months=6):
        """
        Ambil data PENJUALAN (invoice created) untuk N bulan terakhir
        
        PENTING: Sales = Invoice yang dibuat (bukan payment yang masuk)
        """
        try:
            today = datetime.now()
            sales_data = []
            
            for i in range(months):
                # Mundur dari bulan sekarang (termasuk bulan ini)
                target_date = today - relativedelta(months=months - i - 1)
                
                # Awal bulan
                month_start = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                
                # Akhir bulan (hari ini jika bulan ini, atau akhir bulan jika bulan lalu)
                if target_date.month == today.month and target_date.year == today.year:
                    # Bulan ini: sampai hari ini
                    month_end = today.replace(hour=23, minute=59, second=59, microsecond=999999)
                else:
                    # Bulan lalu: sampai akhir bulan
                    month_end = (month_start + relativedelta(months=1)) - relativedelta(seconds=1)
                
                # Query TWH INVOICES yang dibuat dalam periode ini
                # HANYA invoice yang confirmed/paid (tidak termasuk draft/cancelled)
                domain = [
                    ('date_invoice', '>=', fields.Date.to_string(month_start.date())),
                    ('date_invoice', '<=', fields.Date.to_string(month_end.date())),
                    ('state', 'in', ['confirmed', 'partial', 'paid', 'overdue'])  # Semua invoice yang valid
                ]
                
                invoices = self.env['twh.invoice'].search(domain)
                
                # Hitung total sales (sum of invoice total)
                total_amount = sum(invoices.mapped('total'))
                
                # Format bulan
                month_label = month_start.strftime('%b %Y')
                
                sales_data.append({
                    'month': month_label,
                    'amount': round(total_amount, 2)
                })
                
                # Log detail untuk debugging
                _logger.info(
                    f"📊 {month_label}: "
                    f"{len(invoices)} invoices created, "
                    f"Total Sales: Rp {total_amount:,.0f} "
                    f"(Range: {month_start.date()} to {month_end.date()})"
                )
            
            _logger.info(f"✅ Sales data loaded: {len(sales_data)} months")
            return sales_data
            
        except Exception as e:
            _logger.error(f"❌ Error loading sales data: {str(e)}")
            import traceback
            _logger.error(traceback.format_exc())
            return []

    @api.model
    def get_total_revenue(self, period='month'):
        """
        Calculate total revenue based on PAYMENTS yang masuk
        
        Revenue = Total payment yang sudah diterima (confirmed)
        (Ini tetap pakai payment, tidak berubah)
        
        Args:
            period (str): 'month', 'year', or 'all'
        
        Returns:
            dict: {
                'amount': float,
                'formatted': str,
                'period_label': str,
                'payment_count': int
            }
        """
        try:
            today = datetime.now()
            domain = [('state', '=', 'confirmed')]
            
            # Tentukan date range berdasarkan period
            if period == 'month':
                # This month
                month_start = today.replace(day=1)
                domain.append(('payment_date', '>=', fields.Date.to_string(month_start)))
                domain.append(('payment_date', '<=', fields.Date.to_string(today)))
                period_label = f"{today.strftime('%B %Y')}"
                
            elif period == 'year':
                # This year
                year_start = today.replace(month=1, day=1)
                domain.append(('payment_date', '>=', fields.Date.to_string(year_start)))
                domain.append(('payment_date', '<=', fields.Date.to_string(today)))
                period_label = f"Year {today.year}"
                
            else:  # 'all'
                # All time - no date filter
                period_label = "All Time"
            
            # Search confirmed payments
            payments = self.env['twh.payment'].search(domain)
            
            # Calculate total revenue (sum of all payments)
            total_amount = sum(payments.mapped('amount'))
            payment_count = len(payments)
            
            # Count unique invoices
            invoice_count = len(payments.mapped('invoice_id'))
            
            # Format currency
            formatted = 'Rp {:,.0f}'.format(total_amount).replace(',', '.')
            
            _logger.info(
                f"💰 Revenue ({period}): {formatted} "
                f"from {payment_count} payments, {invoice_count} invoices ({period_label})"
            )
            
            return {
                'amount': total_amount,
                'formatted': formatted,
                'period_label': period_label,
                'payment_count': payment_count,
                'invoice_count': invoice_count,
                'period': period
            }
            
        except Exception as e:
            _logger.error(f"❌ Error calculating revenue: {str(e)}")
            return {
                'amount': 0,
                'formatted': 'Rp 0',
                'period_label': 'Error',
                'payment_count': 0,
                'invoice_count': 0,
                'period': period
            }

    @api.model
    def get_dashboard_summary(self, revenue_period='month'):
        """
        Get summary statistics untuk dashboard
        
        UNPAID INVOICES = Invoice tempo yang belum lunas
        (confirmed, partial, overdue - excluding paid & cash)
        
        Args:
            revenue_period (str): 'month', 'year', or 'all'
        """
        try:
            # Count TEMPO invoices yang belum lunas
            unpaid_invoices = self.env['twh.invoice'].search_count([
                ('payment_type', '=', 'tempo'),
                ('state', 'in', ['confirmed', 'partial', 'overdue']),
            ])
            
            # Get total outstanding amount
            unpaid_invoice_records = self.env['twh.invoice'].search([
                ('payment_type', '=', 'tempo'),
                ('state', 'in', ['confirmed', 'partial', 'overdue']),
            ])
            total_outstanding = sum(unpaid_invoice_records.mapped('remaining_amount'))
            
            # Count overdue invoices
            overdue_count = self.env['twh.invoice'].search_count([
                ('state', '=', 'overdue'),
            ])
            
            # Count partial payment invoices
            partial_count = self.env['twh.invoice'].search_count([
                ('state', '=', 'partial'),
            ])
            
            # Get revenue data with period
            revenue_data = self.get_total_revenue(revenue_period)
            
            summary = {
                'total_products': self.env['product.product'].search_count([
                    ('sale_ok', '=', True),
                    ('active', '=', True)
                ]),
                'total_customers': self.env['res.partner'].search_count([
                    ('customer_rank', '>', 0),
                    ('active', '=', True)
                ]),
                'unpaid_invoices': unpaid_invoices,
                'total_outstanding': 'Rp {:,.0f}'.format(total_outstanding).replace(',', '.'),
                'overdue_count': overdue_count,
                'partial_count': partial_count,
                'total_revenue': revenue_data['formatted'],
                'revenue_period': revenue_data['period'],
                'revenue_period_label': revenue_data['period_label'],
                'revenue_payment_count': revenue_data['payment_count'],
                'revenue_invoice_count': revenue_data['invoice_count'],
                'monthly_sales': self.get_sales_data()  # ← Ini yang berubah (sales data dari invoice)
            }
            
            _logger.info(
                f"📈 Dashboard Summary: "
                f"{summary['total_products']} products, "
                f"{summary['total_customers']} customers, "
                f"{summary['unpaid_invoices']} unpaid invoices "
                f"(Outstanding: {summary['total_outstanding']}, "
                f"Overdue: {summary['overdue_count']}, "
                f"Partial: {summary['partial_count']}), "
                f"Revenue: {summary['total_revenue']} ({summary['revenue_period_label']})"
            )
            
            return summary
            
        except Exception as e:
            _logger.error(f"❌ Error getting dashboard summary: {str(e)}")
            import traceback
            _logger.error(traceback.format_exc())
            return {
                'total_products': 0,
                'total_customers': 0,
                'unpaid_invoices': 0,
                'total_outstanding': 'Rp 0',
                'overdue_count': 0,
                'partial_count': 0,
                'total_revenue': 'Rp 0',
                'revenue_period': 'month',
                'revenue_period_label': 'This Month',
                'revenue_payment_count': 0,
                'revenue_invoice_count': 0,
                'monthly_sales': []
            }