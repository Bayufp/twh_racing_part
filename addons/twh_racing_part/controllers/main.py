# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class TwhDashboardController(http.Controller):

    @http.route('/twh/dashboard/sales_data', type='json', auth='user')
    def get_sales_data(self, **kwargs):
        """
        Endpoint untuk ambil data penjualan
        """
        try:
            dashboard_model = request.env['twh.dashboard']
            sales_data = dashboard_model.get_sales_data(months=6)
            
            _logger.info(f"Dashboard API called - returned {len(sales_data)} months")
            return sales_data
            
        except Exception as e:
            _logger.error(f"Dashboard API error: {str(e)}")
            return []

    @http.route('/twh/dashboard/summary', type='json', auth='user')
    def get_dashboard_summary(self, **kwargs):
        """
        Endpoint untuk ambil summary statistics
        """
        try:
            dashboard_model = request.env['twh.dashboard']
            return dashboard_model.get_dashboard_summary()
            
        except Exception as e:
            _logger.error(f"Dashboard summary error: {str(e)}")
            return {}