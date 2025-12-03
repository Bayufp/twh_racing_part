# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TwhPriceTier(models.Model):
    """
    Model untuk menyimpan tier harga TWH:
    - Bayu (Harga Dasar/Cost)
    - Dealer
    - Harga A
    - Harga B
    - HET (Harga Eceran Tertinggi)
    """
    _name = 'twh.price.tier'
    _description = 'TWH Price Tier Configuration'
    
    name = fields.Char(string='Tier Name', required=True)
    code = fields.Selection([
        ('bayu', 'Bayu'),
        ('dealer', 'Dealer'),
        ('price_a', 'Harga A'),
        ('price_b', 'Harga B'),
        ('het', 'HET'),
    ], string='Tier Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Price tier code must be unique!')
    ]


class TwhProductPrice(models.Model):
    """
    Model untuk menyimpan harga produk per tier
    """
    _name = 'twh.product.price'
    _description = 'TWH Product Price per Tier'
    _rec_name = 'product_id'
    
    product_id = fields.Many2one('product.product', string='Product', required=True, ondelete='cascade')
    tier_id = fields.Many2one('twh.price.tier', string='Price Tier', required=True, ondelete='cascade')
    tier_code = fields.Selection(related='tier_id.code', string='Tier Code', store=True)
    price = fields.Float(string='Price', required=True, digits='Product Price')
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                   default=lambda self: self.env.company.currency_id)
    active = fields.Boolean(default=True)
    
    @api.constrains('price')
    def _check_price(self):
        for record in self:
            if record.price < 0:
                raise ValidationError('Price cannot be negative!')
    
    _sql_constraints = [
        ('product_tier_unique', 'unique(product_id, tier_id)', 
         'Product can only have one price per tier!')
    ]


class ProductProduct(models.Model):

    _inherit = 'product.product'
    
    twh_price_ids = fields.One2many('twh.product.price', 'product_id', string='TWH Prices')
    
    # Computed fields untuk quick access
    price_bayu = fields.Float(string='Harga Bayu', compute='_compute_twh_prices', store=True)
    price_dealer = fields.Float(string='Harga Dealer', compute='_compute_twh_prices', store=True)
    price_a = fields.Float(string='Harga A', compute='_compute_twh_prices', store=True)
    price_b = fields.Float(string='Harga B', compute='_compute_twh_prices', store=True)
    price_het = fields.Float(string='HET', compute='_compute_twh_prices', store=True)
    
    @api.depends('twh_price_ids', 'twh_price_ids.price', 'twh_price_ids.tier_code')
    def _compute_twh_prices(self):
        for product in self:
            prices = {
                'price_bayu': 0.0,
                'price_dealer': 0.0,
                'price_a': 0.0,
                'price_b': 0.0,
                'price_het': 0.0,
            }
            
            for price_line in product.twh_price_ids:
                if price_line.tier_code == 'bayu':
                    prices['price_bayu'] = price_line.price
                elif price_line.tier_code == 'dealer':
                    prices['price_dealer'] = price_line.price
                elif price_line.tier_code == 'price_a':
                    prices['price_a'] = price_line.price
                elif price_line.tier_code == 'price_b':
                    prices['price_b'] = price_line.price
                elif price_line.tier_code == 'het':
                    prices['price_het'] = price_line.price
            
            product.update(prices)
    
    def get_price_by_tier(self, tier_code):
        """
        Helper method untuk get harga berdasarkan tier code
        """
        self.ensure_one()
        price_line = self.twh_price_ids.filtered(lambda p: p.tier_code == tier_code)
        return price_line.price if price_line else 0.0


class ProductTemplate(models.Model):

    _inherit = 'product.template'
    
    # TWH prices as computed fields
    price_bayu = fields.Float(string='Harga Bayu', compute='_compute_twh_prices', store=True)
    price_dealer = fields.Float(string='Harga Dealer', compute='_compute_twh_prices', store=True)
    price_a = fields.Float(string='Harga A', compute='_compute_twh_prices', store=True)
    price_b = fields.Float(string='Harga B', compute='_compute_twh_prices', store=True)
    price_het = fields.Float(string='HET', compute='_compute_twh_prices', store=True)
    
    # Category khusus TWH
    twh_category = fields.Selection([
        ('gear_ratio', 'Gear Ratio Set'),
        ('crankshaft', 'Forged Crankshaft'),
        ('cylinder', 'Cylinder Block Bore Up'),
        ('cylinder_head', 'Cylinder Head'),
        ('starter', 'Dinamo Starter'),
        ('roller', 'Blue Roller'),
        ('jet', 'Carburetor Jet'),
        ('transmission', 'Transmisi/Gear Ratio Matic'),
        ('clutch', 'Clutch System'),
        ('pulley', 'Pulley System'),
        ('spring', 'Spring/Per'),
        ('valve', 'Valve/Klep'),
        ('piston', 'Piston Kit'),
        ('ring', 'Ring Piston'),
        ('other', 'Lain-lain'),
    ], string='TWH Category')
    
    # Compatibility dengan motor
    bike_model = fields.Char(string='Bike Model')
    bike_brand = fields.Selection([
        ('yamaha', 'Yamaha'),
        ('honda', 'Honda'),
        ('suzuki', 'Suzuki'),
        ('kawasaki', 'Kawasaki'),
        ('other', 'Other'),
    ], string='Bike Brand')