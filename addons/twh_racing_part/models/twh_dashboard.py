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
        Ambil data penjualan real dari sale.order
        untuk N bulan terakhir (termasuk bulan ini)
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
                
                # Query sale orders yang sudah confirmed
                domain = [
                    ('date_order', '>=', fields.Datetime.to_string(month_start)),
                    ('date_order', '<=', fields.Datetime.to_string(month_end)),
                    ('state', 'in', ['sale', 'done'])  # Hanya yang sudah confirm
                ]
                
                orders = self.env['sale.order'].search(domain)
                
                # Hitung total amount
                total_amount = sum(orders.mapped('amount_total'))
                
                # Format bulan
                month_label = month_start.strftime('%b %Y')
                
                sales_data.append({
                    'month': month_label,
                    'amount': round(total_amount, 2)
                })
                
                # Log detail untuk debugging
                _logger.info(
                    f"📊 {month_label}: "
                    f"{len(orders)} orders, "
                    f"Total: Rp {total_amount:,.0f} "
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
    def get_dashboard_summary(self):
        """
        Get summary statistics untuk dashboard
        """
        try:
            summary = {
                'total_products': self.env['product.product'].search_count([
                    ('sale_ok', '=', True),
                    ('active', '=', True)
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
            
            _logger.info(
                f"📈 Dashboard Summary: "
                f"{summary['total_products']} products, "
                f"{summary['total_customers']} customers, "
                f"{summary['pending_invoices']} pending invoices"
            )
            
            return summary
            
        except Exception as e:
            _logger.error(f"❌ Error getting dashboard summary: {str(e)}")
            return {
                'total_products': 0,
                'total_customers': 0,
                'pending_invoices': 0,
                'monthly_sales': []
            }