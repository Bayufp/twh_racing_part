# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TwhPriceTier(models.Model):
    """
    Model untuk tier/kategori harga TWH.
    
    TWH punya 5 tier harga:
    - Bayu: Harga dasar/cost (untuk hitung komisi)
    - Dealer: Harga khusus dealer
    - Harga A: Harga untuk toko kategori A
    - Harga B: Harga untuk toko kategori B
    - HET: Harga Eceran Tertinggi (untuk konsumen)
    """
    _name = 'twh.price.tier'
    _description = 'Kategori Harga TWH'
    _order = 'sequence, id'
    
    # ========================
    # FIELDS
    # ========================
    
    name = fields.Char(
        string='Nama Tier',
        required=True,
        help='Nama kategori harga (misal: Harga A, Harga B)'
    )
    
    code = fields.Selection([
        ('bayu', 'Bayu'),
        ('dealer', 'Dealer'),
        ('price_a', 'Harga A'),
        ('price_b', 'Harga B'),
        ('het', 'HET'),
    ], string='Kode Tier', required=True,
       help='Kode unik untuk identifikasi tier')
    
    sequence = fields.Integer(
        string='Urutan',
        default=10,
        help='Urutan tampilan tier'
    )
    
    active = fields.Boolean(
        default=True,
        help='Non-aktifkan jika tier tidak digunakan lagi'
    )
    
    description = fields.Text(
        string='Deskripsi',
        help='Keterangan tentang tier ini'
    )
    
    # ========================
    # CONSTRAINTS
    # ========================
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Kode tier harus unik!')
    ]


class TwhProductPrice(models.Model):
    """
    Model untuk menyimpan harga produk per tier.
    
    Setiap produk bisa punya banyak harga tergantung tier.
    Contoh:
    - Produk A -> Harga Bayu: Rp 100.000
    - Produk A -> Harga A: Rp 120.000
    - Produk A -> Harga B: Rp 115.000
    """
    _name = 'twh.product.price'
    _description = 'Harga Produk per Tier'
    _rec_name = 'product_id'
    _order = 'product_id, tier_id'
    
    # ========================
    # FIELDS
    # ========================
    
    product_id = fields.Many2one(
        'product.product',
        string='Produk',
        required=True,
        ondelete='cascade',
        help='Produk yang diberi harga'
    )
    
    tier_id = fields.Many2one(
        'twh.price.tier',
        string='Kategori Harga',
        required=True,
        ondelete='cascade',
        help='Tier harga yang digunakan'
    )
    
    tier_code = fields.Selection(
        related='tier_id.code',
        string='Kode Tier',
        store=True,
        readonly=True
    )
    
    price = fields.Float(
        string='Harga',
        required=True,
        digits='Product Price',
        help='Harga dalam rupiah'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang',
        default=lambda self: self.env.company.currency_id
    )
    
    active = fields.Boolean(
        default=True,
        help='Non-aktifkan jika harga tidak berlaku lagi'
    )
    
    # ========================
    # CONSTRAINTS
    # ========================
    
    @api.constrains('price')
    def _check_price(self):
        """Validasi harga tidak boleh negatif."""
        for record in self:
            if record.price < 0:
                raise ValidationError(_('Harga tidak boleh negatif!'))
    
    _sql_constraints = [
        ('product_tier_unique', 'unique(product_id, tier_id)',
         'Satu produk hanya bisa punya satu harga per tier!')
    ]


class ProductProduct(models.Model):
    """
    Extend model product.product untuk tambah harga TWH.
    """
    _inherit = 'product.product'
    
    # ========================
    # FIELDS
    # ========================
    
    # Relasi ke harga per tier
    twh_price_ids = fields.One2many(
        'twh.product.price',
        'product_id',
        string='Harga TWH',
        help='Daftar harga produk ini per tier'
    )
    
    # Field computed untuk quick access
    price_bayu = fields.Float(
        string='Harga Bayu',
        compute='_compute_twh_prices',
        store=True,
        help='Harga dasar/cost'
    )
    
    price_dealer = fields.Float(
        string='Harga Dealer',
        compute='_compute_twh_prices',
        store=True,
        help='Harga untuk dealer'
    )
    
    price_a = fields.Float(
        string='Harga A',
        compute='_compute_twh_prices',
        store=True,
        help='Harga untuk toko kategori A'
    )
    
    price_b = fields.Float(
        string='Harga B',
        compute='_compute_twh_prices',
        store=True,
        help='Harga untuk toko kategori B'
    )
    
    price_het = fields.Float(
        string='HET',
        compute='_compute_twh_prices',
        store=True,
        help='Harga Eceran Tertinggi'
    )
    
    # ========================
    # COMPUTED METHODS
    # ========================
    
    @api.depends('twh_price_ids', 'twh_price_ids.price', 'twh_price_ids.tier_code')
    def _compute_twh_prices(self):
        """
        Hitung harga untuk setiap tier dari twh_price_ids.
        
        Field computed ini memudahkan akses harga tanpa perlu
        search twh_price_ids setiap kali.
        """
        for product in self:
            # Default semua harga 0
            prices = {
                'price_bayu': 0.0,
                'price_dealer': 0.0,
                'price_a': 0.0,
                'price_b': 0.0,
                'price_het': 0.0,
            }
            
            # Loop semua harga yang tersimpan
            for price_line in product.twh_price_ids:
                tier_code = price_line.tier_code
                
                # Map tier_code ke field
                if tier_code == 'bayu':
                    prices['price_bayu'] = price_line.price
                elif tier_code == 'dealer':
                    prices['price_dealer'] = price_line.price
                elif tier_code == 'price_a':
                    prices['price_a'] = price_line.price
                elif tier_code == 'price_b':
                    prices['price_b'] = price_line.price
                elif tier_code == 'het':
                    prices['price_het'] = price_line.price
            
            # Update field produk
            product.update(prices)
    
    # ========================
    # HELPER METHODS
    # ========================
    
    def get_price_by_tier(self, tier_code):
        """
        Ambil harga produk berdasarkan kode tier.
        
        Args:
            tier_code (str): Kode tier ('bayu', 'dealer', 'price_a', dll)
        
        Returns:
            float: Harga produk untuk tier tersebut (0 jika tidak ada)
        
        Contoh:
            >>> product.get_price_by_tier('price_a')
            120000.0
        """
        self.ensure_one()
        
        # Cari harga dengan tier_code yang sesuai
        price_line = self.twh_price_ids.filtered(
            lambda line: line.tier_code == tier_code
        )
        
        return price_line.price if price_line else 0.0
    
    def get_price_by_tier_id(self, tier_id):
        """
        Ambil harga produk berdasarkan ID tier.
        
        Args:
            tier_id (int): ID record tier
        
        Returns:
            float: Harga produk untuk tier tersebut (0 jika tidak ada)
        
        Contoh:
            >>> tier = env['twh.price.tier'].browse(1)
            >>> product.get_price_by_tier_id(tier.id)
            120000.0
        """
        self.ensure_one()
        
        # Cari harga dengan tier_id yang sesuai
        price_line = self.twh_price_ids.filtered(
            lambda line: line.tier_id.id == tier_id
        )
        
        return price_line.price if price_line else 0.0


class ProductTemplate(models.Model):
    """
    Extend model product.template untuk tambah kategori & harga TWH.
    """
    _inherit = 'product.template'
    
    # ========================
    # FIELDS
    # ========================
    
    # Field harga (computed dari variant pertama)
    price_bayu = fields.Float(
        string='Harga Bayu',
        compute='_compute_twh_prices_template',
        store=True,
        help='Harga dasar/cost'
    )
    
    price_dealer = fields.Float(
        string='Harga Dealer',
        compute='_compute_twh_prices_template',
        store=True,
        help='Harga untuk dealer'
    )
    
    price_a = fields.Float(
        string='Harga A',
        compute='_compute_twh_prices_template',
        store=True,
        help='Harga untuk toko kategori A'
    )
    
    price_b = fields.Float(
        string='Harga B',
        compute='_compute_twh_prices_template',
        store=True,
        help='Harga untuk toko kategori B'
    )
    
    price_het = fields.Float(
        string='HET',
        compute='_compute_twh_prices_template',
        store=True,
        help='Harga Eceran Tertinggi'
    )
    
    # Kategori khusus TWH
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
    ], string='Kategori TWH',
       help='Jenis produk racing part')
    
    # Kompatibilitas motor
    bike_model = fields.Char(
        string='Model Motor',
        help='Contoh: MX King, NMAX, Beat'
    )
    
    bike_brand = fields.Selection([
        ('yamaha', 'Yamaha'),
        ('honda', 'Honda'),
        ('suzuki', 'Suzuki'),
        ('kawasaki', 'Kawasaki'),
        ('other', 'Lainnya'),
    ], string='Merk Motor',
       help='Merk motor yang kompatibel')
    
    # ========================
    # COMPUTED METHODS
    # ========================
    
    @api.depends(
        'product_variant_ids',
        'product_variant_ids.price_bayu',
        'product_variant_ids.price_dealer',
        'product_variant_ids.price_a',
        'product_variant_ids.price_b',
        'product_variant_ids.price_het'
    )
    def _compute_twh_prices_template(self):
        """
        Hitung harga template dari variant pertama.
        
        Untuk produk tanpa variant, akan ambil dari variant tunggal yang auto-created.
        Untuk produk dengan variant, ambil harga dari variant pertama.
        """
        for template in self:
            if template.product_variant_ids:
                # Ambil harga dari variant pertama
                first_variant = template.product_variant_ids[0]
                template.price_bayu = first_variant.price_bayu
                template.price_dealer = first_variant.price_dealer
                template.price_a = first_variant.price_a
                template.price_b = first_variant.price_b
                template.price_het = first_variant.price_het
            else:
                # Belum ada variant, set semua 0
                template.price_bayu = 0.0
                template.price_dealer = 0.0
                template.price_a = 0.0
                template.price_b = 0.0
                template.price_het = 0.0