# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Field Price Tier untuk TWH
    price_tier_id = fields.Many2one(
        'twh.price.tier',
        string='Price Tier',
        help='Select price tier for this order (Bayu, Dealer, Harga A, B, or HET)'
    )
    
    # Link ke TWH Invoice
    twh_invoice_id = fields.Many2one(
        'twh.invoice',
        string='TWH Invoice',
        readonly=True,
        copy=False,
        help='Generated TWH Invoice from this Sales Order'
    )
    
    twh_invoice_count = fields.Integer(
        string='TWH Invoice Count',
        compute='_compute_twh_invoice_count'
    )

    @api.depends('twh_invoice_id')
    def _compute_twh_invoice_count(self):
        for order in self:
            order.twh_invoice_count = 1 if order.twh_invoice_id else 0

    @api.onchange('price_tier_id', 'partner_id')
    def _onchange_price_tier(self):
        """
        Update harga semua order lines saat Price Tier berubah
        """
        if self.price_tier_id and self.order_line:
            for line in self.order_line:
                if line.product_id:
                    # Cari harga produk sesuai price tier (FIXED: pakai tier_id bukan price_tier_id)
                    product_price = self.env['twh.product.price'].search([
                        ('product_id', '=', line.product_id.id),
                        ('tier_id', '=', self.price_tier_id.id)  # FIXED: tier_id
                    ], limit=1)
                    
                    if product_price:
                        line.price_unit = product_price.price
                        _logger.info(
                            f"✅ Updated price for {line.product_id.name}: "
                            f"Rp {product_price.price:,.0f} ({self.price_tier_id.name})"
                        )
                    else:
                        _logger.warning(
                            f"⚠️ No price found for {line.product_id.name} "
                            f"with tier {self.price_tier_id.name}"
                        )

    def action_generate_twh_invoice(self):
        """
        Generate TWH Invoice dari Sales Order
        """
        self.ensure_one()
        
        # Validasi
        if not self.price_tier_id:
            raise UserError(_('Please select a Price Tier before generating TWH Invoice.'))
        
        if self.twh_invoice_id:
            raise UserError(_('TWH Invoice already generated for this order.'))
        
        if self.state not in ['sale', 'done']:
            raise UserError(_('Please confirm the Sales Order first.'))
        
        # Prepare invoice lines
        invoice_lines = []
        for line in self.order_line:
            if line.product_id:
                invoice_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'description': line.name,
                    'quantity': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'subtotal': line.price_subtotal,
                }))
        
        # Map price_tier_id ke price_tier selection field di TWH Invoice
        # Get tier code dari price tier
        price_tier_code = 'price_a'  # default
        if self.price_tier_id and self.price_tier_id.code:
            price_tier_code = self.price_tier_id.code
        
        # Create TWH Invoice
        twh_invoice = self.env['twh.invoice'].create({
            'partner_id': self.partner_id.id,
            'sale_order_id': self.id,
            'price_tier': price_tier_code,
            'date_invoice': fields.Date.today(),
            'payment_term_days': self.payment_term_id.line_ids[0].nb_days if self.payment_term_id and self.payment_term_id.line_ids else 60,
            'sales_person_id': self.user_id.id if self.user_id else self.env.user.id,
            'invoice_line_ids': invoice_lines,
            'notes': f'Generated from Sales Order: {self.name}',
        })
        
        # Link TWH Invoice ke Sales Order
        self.twh_invoice_id = twh_invoice.id
        
        _logger.info(f"✅ TWH Invoice {twh_invoice.name} generated from SO {self.name}")
        
        # Open TWH Invoice
        return {
            'type': 'ir.actions.act_window',
            'name': 'TWH Invoice',
            'res_model': 'twh.invoice',
            'res_id': twh_invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_twh_invoice(self):
        """
        View TWH Invoice yang sudah di-generate
        """
        self.ensure_one()
        
        if not self.twh_invoice_id:
            raise UserError(_('No TWH Invoice generated yet.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'TWH Invoice',
            'res_model': 'twh.invoice',
            'res_id': self.twh_invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('product_id')
    def _onchange_product_id_twh(self):
        """
        Auto-set harga dari Price Tier saat pilih produk
        """
        if self.product_id and self.order_id.price_tier_id:
            # Cari harga produk sesuai price tier (FIXED: pakai tier_id)
            product_price = self.env['twh.product.price'].search([
                ('product_id', '=', self.product_id.id),
                ('tier_id', '=', self.order_id.price_tier_id.id)  # FIXED: tier_id
            ], limit=1)
            
            if product_price:
                self.price_unit = product_price.price
                _logger.info(
                    f"✅ Auto-set price for {self.product_id.name}: "
                    f"Rp {product_price.price:,.0f}"
                )
            else:
                _logger.warning(
                    f"⚠️ No price found for {self.product_id.name} "
                    f"with tier {self.order_id.price_tier_id.name}"
                )