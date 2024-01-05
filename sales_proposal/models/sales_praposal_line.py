# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _


class SaleProposalLine(models.Model):
    _name = "sales.proposal.line"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']
    _description = "Sale Proposal Line"

    sales_proposal_id = fields.Many2one(
        comodel_name='sales.proposal',
        string="Order Reference",
        required=True, ondelete='cascade', index=True, copy=False)
    order_partner_id = fields.Many2one(
        related='sales_proposal_id.partner_id',
        string="Customer",
        store=True, index=True, precompute=True)
    proposal_state = fields.Selection(
        related='sales_proposal_id.proposal_state',
        string="Proposal State",
        store=True, index=True, precompute=True)
    state = fields.Selection(
        related='sales_proposal_id.state',
        string="Proposal State",
        store=True, index=True, precompute=True)
    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Product",
        change_default=True, ondelete='restrict', check_company=True, index='btree_not_null',
        domain="[('sale_ok', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    name = fields.Text(
        string="Description",
        compute='_compute_name',
        store=True, readonly=False, required=True,
        precompute=True
    )
    company_id = fields.Many2one(related='sales_proposal_id.company_id', store=True)
    currency_id = fields.Many2one(
        related='sales_proposal_id.currency_id',
        depends=['sales_proposal_id.currency_id'],
        store=True, precompute=True)
    product_template_id = fields.Many2one(
        string="Product Template",
        related='product_id.product_tmpl_id',
        domain=[('sale_ok', '=', True)])
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id', depends=['product_id'])
    product_uom_qty = fields.Float(
        string="Quantity",
        digits='Product Unit of Measure', default=1.0,
        required=True,
    )
    product_uom = fields.Many2one(
        comodel_name='uom.uom',
        string="Unit of Measure",
        compute='_compute_product_uom',
        store=True, readonly=False,
        precompute=True,
        ondelete='restrict',
        domain="[('category_id', '=', product_uom_category_id)]")
    tax_id = fields.Many2many(
        comodel_name='account.tax',
        string="Taxes",
        store=True,
        context={'active_test': False})
    pricelist_item_id = fields.Many2one(
        comodel_name='product.pricelist.item',
    )
    price_unit = fields.Float(
        string="Unit Price",
        compute='_compute_price_unit',
        digits='Product Price',
        store=True, readonly=False, required=True,
        precompute=True
    )
    price_subtotal = fields.Monetary(
        string="Subtotal",
        compute='_compute_amount',
        store=True, precompute=True)
    price_tax = fields.Float(
        string="Total Tax",
        compute='_compute_amount',
        store=True, precompute=True)
    price_total = fields.Monetary(
        string="Total",
        compute='_compute_amount',
        store=True, precompute=True)
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note"),
    ],
        default=False)

    price_unit_approved = fields.Float(
        string="Unit Price Approved",
        digits='Product Price',
        required=True,tracking=True
    )
    product_uom_qty_approved = fields.Float(
        string="Quantity Approved",
        digits='Product Unit of Measure',
        default=1.0,
        required=True,tracking=True
    )
    price_subtotal_approved = fields.Monetary(
        string="Total",
        compute='_compute_amount_approved',
        store=True, precompute=True)
    price_total_approved = fields.Monetary(
        string="Total",
        compute='_compute_amount_approved',
        store=True, precompute=True)


    @api.depends('product_id', 'product_uom', 'product_uom_qty')
    def _compute_price_unit(self):
        for line in self:
            if not line.product_uom or not line.product_id or not line.sales_proposal_id.pricelist_id:
                line.price_unit = 0.0
            else:
                price = line.with_company(line.company_id)._get_display_price()
                line.price_unit = line.product_id._get_tax_included_unit_price(
                    line.company_id,
                    line.sales_proposal_id.currency_id,
                    line.sales_proposal_id.date_order,
                    'sale',
                    fiscal_position=line.sales_proposal_id.fiscal_position_id,
                    product_price_unit=price,
                    product_currency=line.currency_id
                )

    @api.depends('product_id')
    def _compute_name(self):
        for line in self:
            if not line.product_id:
                continue
            name = line.with_context(lang=line.order_partner_id.lang).product_id.display_name
            line.name = name

    def _get_display_price(self):
        self.ensure_one()
        return self._get_pricelist_price()

    @api.onchange('product_id')
    def _compute_price_subtotal_approved(self):
        if self.sales_proposal_id.state == 'draft':
            for line in self:
                line.product_uom_qty_approved, line.price_unit_approved = line.product_uom_qty, line.price_unit

    @api.depends('product_id')
    def _compute_product_uom(self):
        for line in self:
            if not line.product_uom or (line.product_id.uom_id.id != line.product_uom.id):
                line.product_uom = line.product_id.uom_id

    def _get_pricelist_price(self):
        self.ensure_one()
        self.product_id.ensure_one()
        pricelist_rule = self.pricelist_item_id
        order_date = self.sales_proposal_id.date_order or fields.Date.today()
        product = self.product_id
        qty = self.product_uom_qty or 1.0
        uom = self.product_uom or self.product_id.uom_id
        return pricelist_rule._compute_price(
            product, qty, uom, order_date, currency=self.currency_id
        )

    @api.depends('product_uom_qty', 'price_unit', 'tax_id')
    def _compute_amount(self):
        for line in self:
            tax_results = self.env['account.tax']._compute_taxes([line._convert_to_tax_base_line_dict()])
            totals = list(tax_results['totals'].values())[0]
            amount_untaxed = totals['amount_untaxed']
            amount_tax = totals['amount_tax']
            line.update({
                'price_subtotal': amount_untaxed,
                'price_tax': amount_tax,
                'price_total': amount_untaxed + amount_tax,
            })

    def _convert_to_tax_base_line_dict(self):
        self.ensure_one()
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.sales_proposal_id.partner_id,
            currency=self.sales_proposal_id.currency_id,
            product=self.product_id,
            taxes=self.tax_id,
            price_unit=self.price_unit,
            quantity=self.product_uom_qty,
            price_subtotal=self.price_subtotal
        )

    @api.depends('product_uom_qty_approved', 'price_unit_approved', 'tax_id')
    def _compute_amount_approved(self):
        for line in self:
            tax_results_approved = self.env['account.tax']._compute_taxes(
                [line._convert_to_tax_base_line_dict_approved()])
            totals_approved = list(tax_results_approved['totals'].values())[0]
            amount_untaxed_approved = totals_approved['amount_untaxed']
            amount_tax_approved = totals_approved['amount_tax']
            line.update({
                'price_subtotal_approved': amount_untaxed_approved,
                'price_tax': amount_tax_approved,
                'price_total_approved': amount_untaxed_approved + amount_tax_approved,
            })

    def _convert_to_tax_base_line_dict_approved(self):
        self.ensure_one()
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.sales_proposal_id.partner_id,
            currency=self.sales_proposal_id.currency_id,
            product=self.product_id,
            taxes=self.tax_id,
            price_unit=self.price_unit_approved,
            quantity=self.product_uom_qty_approved,
            price_subtotal=self.price_subtotal_approved
        )