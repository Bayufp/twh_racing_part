# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """
    Extend model sale.order untuk integrasi dengan TWH Invoice.
    
    Penambahan:
    1. Field price tier untuk tentukan harga jual
    2. Link ke TWH invoice yang di-generate
    3. Method untuk generate TWH invoice dari SO
    """
    _inherit = 'sale.order'
    
    # ========================
    # FIELDS
    # ========================
    
    price_tier_id = fields.Many2one(
        'twh.price.tier',
        string='Kategori Harga',
        help='Pilih kategori harga untuk order ini (Bayu, Dealer, Harga A/B, atau HET)'
    )
    
    twh_invoice_id = fields.Many2one(
        'twh.invoice',
        string='TWH Invoice',
        readonly=True,
        copy=False,
        help='Invoice TWH yang dibuat dari Sales Order ini'
    )
    
    twh_invoice_count = fields.Integer(
        string='Jumlah Invoice',
        compute='_compute_twh_invoice_count',
        help='Jumlah invoice TWH yang sudah dibuat'
    )
    
    # ========================
    # COMPUTED METHODS
    # ========================
    
    @api.depends('twh_invoice_id')
    def _compute_twh_invoice_count(self):
        """Hitung jumlah invoice TWH (maksimal 1 per SO)."""
        for order in self:
            order.twh_invoice_count = 1 if order.twh_invoice_id else 0
    
    # ========================
    # ONCHANGE METHODS
    # ========================
    
    @api.onchange('price_tier_id', 'partner_id')
    def _onchange_price_tier(self):
        """
        Update harga produk saat price tier berubah.
        
        Saat user ganti kategori harga, semua harga produk di order lines
        akan otomatis update sesuai kategori harga yang dipilih.
        """
        if self.price_tier_id and self.order_line:
            for line in self.order_line:
                if line.product_id:
                    # Cari harga sesuai tier yang dipilih
                    product_price = self.env['twh.product.price'].search([
                        ('product_id', '=', line.product_id.id),
                        ('tier_id', '=', self.price_tier_id.id)
                    ], limit=1)
                    
                    if product_price:
                        # Update harga
                        line.price_unit = product_price.price
                        _logger.info(
                            f'Harga diupdate untuk {line.product_id.name}: '
                            f'Rp {product_price.price:,.0f} ({self.price_tier_id.name})'
                        )
                    else:
                        _logger.warning(
                            f'Tidak ditemukan harga untuk {line.product_id.name} '
                            f'dengan tier {self.price_tier_id.name}'
                        )
    
    # ========================
    # ACTION METHODS
    # ========================
    
    def action_generate_twh_invoice(self):
        """
        Generate TWH Invoice dari Sales Order.
        
        Validasi:
        1. Harus pilih price tier dulu
        2. Belum ada invoice yang dibuat
        3. SO harus sudah confirmed
        
        Returns:
            dict: Action untuk buka form invoice yang baru dibuat
        """
        self.ensure_one()
        
        # Validasi 1: Price tier harus dipilih
        if not self.price_tier_id:
            raise UserError(_(
                'Pilih kategori harga terlebih dahulu sebelum generate invoice TWH.'
            ))
        
        # Validasi 2: Belum ada invoice
        if self.twh_invoice_id:
            raise UserError(_(
                'Invoice TWH sudah dibuat untuk order ini. '
                'Gunakan tombol "View Invoice" untuk melihatnya.'
            ))
        
        # Validasi 3: SO harus confirmed
        if self.state not in ['sale', 'done']:
            raise UserError(_(
                'Sales Order harus dikonfirmasi terlebih dahulu.'
            ))
        
        # Siapkan invoice lines
        invoice_lines = self._prepare_twh_invoice_lines()
        
        # Tentukan price tier code
        price_tier_code = self._get_price_tier_code()
        
        # Buat TWH invoice
        twh_invoice = self._create_twh_invoice(invoice_lines, price_tier_code)
        
        # Link invoice ke SO
        self.twh_invoice_id = twh_invoice.id
        
        _logger.info(
            f'Invoice TWH {twh_invoice.name} berhasil dibuat dari SO {self.name}'
        )
        
        # Return action untuk buka form invoice
        return self._get_invoice_view_action(twh_invoice)
    
    def _prepare_twh_invoice_lines(self):
        """
        Siapkan data invoice lines dari order lines.
        
        Returns:
            list: List of tuples untuk create invoice lines
        """
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
        
        return invoice_lines
    
    def _get_price_tier_code(self):
        """
        Ambil kode price tier, default ke 'price_a' jika tidak ada.
        
        Returns:
            str: Kode price tier
        """
        if self.price_tier_id and self.price_tier_id.code:
            return self.price_tier_id.code
        return 'price_a'
    
    def _create_twh_invoice(self, invoice_lines, price_tier_code):
        """
        Buat record TWH invoice.
        
        Args:
            invoice_lines (list): List invoice lines
            price_tier_code (str): Kode price tier
        
        Returns:
            record: Record TWH invoice yang baru dibuat
        """
        # Tentukan payment term (default 60 hari)
        payment_term_days = 60
        if self.payment_term_id and self.payment_term_id.line_ids:
            payment_term_days = self.payment_term_id.line_ids[0].nb_days
        
        # Tentukan sales person
        sales_person = self.user_id if self.user_id else self.env.user
        
        # Buat invoice
        return self.env['twh.invoice'].create({
            'partner_id': self.partner_id.id,
            'sale_order_id': self.id,
            'price_tier': price_tier_code,
            'date_invoice': fields.Date.today(),
            'payment_term_days': payment_term_days,
            'sales_person_id': sales_person.id,
            'invoice_line_ids': invoice_lines,
            'notes': f'Dibuat dari Sales Order: {self.name}',
        })
    
    def _get_invoice_view_action(self, invoice):
        """
        Get action untuk buka form invoice.
        
        Args:
            invoice: Record invoice
        
        Returns:
            dict: Action definition
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'TWH Invoice',
            'res_model': 'twh.invoice',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_twh_invoice(self):
        """
        Lihat TWH Invoice yang sudah dibuat.
        
        Returns:
            dict: Action untuk buka form invoice
        """
        self.ensure_one()
        
        if not self.twh_invoice_id:
            raise UserError(_('Belum ada invoice TWH yang dibuat.'))
        
        return self._get_invoice_view_action(self.twh_invoice_id)


class SaleOrderLine(models.Model):
    """
    Extend model sale.order.line untuk auto-update harga dari price tier.
    """
    _inherit = 'sale.order.line'
    
    # ========================
    # ONCHANGE METHODS
    # ========================
    
    @api.onchange('product_id')
    def _onchange_product_id_twh(self):
        """
        Auto-set harga saat produk dipilih berdasarkan price tier SO.
        
        Jika SO sudah pilih price tier, harga akan otomatis
        diambil dari tier tersebut.
        """
        if self.product_id and self.order_id.price_tier_id:
            # Cari harga sesuai tier
            product_price = self.env['twh.product.price'].search([
                ('product_id', '=', self.product_id.id),
                ('tier_id', '=', self.order_id.price_tier_id.id)
            ], limit=1)
            
            if product_price:
                self.price_unit = product_price.price
                _logger.info(
                    f'Harga auto-set untuk {self.product_id.name}: '
                    f'Rp {product_price.price:,.0f}'
                )
            else:
                _logger.warning(
                    f'Harga tidak ditemukan untuk {self.product_id.name} '
                    f'dengan tier {self.order_id.price_tier_id.name}'
                )
    
    @api.onchange('product_uom_qty')
    def _onchange_qty_preserve_price(self):
        """
        Preserve harga saat quantity berubah.
        
        Secara default Odoo akan reset harga saat qty berubah.
        Method ini memastikan harga tetap sesuai price tier yang dipilih.
        """
        if self.order_id.price_tier_id and self.product_id:
            # Ambil ulang harga dari tier
            product_price = self.env['twh.product.price'].search([
                ('product_id', '=', self.product_id.id),
                ('tier_id', '=', self.order_id.price_tier_id.id)
            ], limit=1)
            
            if product_price:
                self.price_unit = product_price.price
                _logger.debug(
                    f'Harga dipertahankan untuk {self.product_id.name}: '
                    f'Rp {product_price.price:,.0f}'
                )