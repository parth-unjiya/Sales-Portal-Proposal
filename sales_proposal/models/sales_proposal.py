# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.fields import Command


class SalesProposal(models.Model):
    _name = 'sales.proposal'
    _inherit = ['mail.thread', 'mail.activity.mixin','portal.mixin','utm.mixin']
    _description = 'sales proposal before quotation'

    name = fields.Char(
        string="Order Reference",
        required=True, copy=False, readonly=True,
        states={'draft': [('readonly', False)]},
        default=lambda self: _('New'))
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Customer",
        required=True, readonly=False, change_default=True, index=True,
        domain="[('type', '!=', 'private'), ('company_id', 'in', (False, company_id))]")
    partner_shipping_id = fields.Many2one(comodel_name='res.partner',
                                          string="Delivery Address",
                                          compute='_compute_partner_shipping_id',
                                          store=True, readonly=False, required=True,
                                          precompute=True,
                                          domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    partner_invoice_id = fields.Many2one(
        comodel_name='res.partner',
        string="Invoice Address",
        compute='_compute_partner_invoice_id',
        store=True, readonly=False, required=True,
        precompute=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    state = fields.Selection(
        selection=[
            ('draft', "Draft"),
            ('send', "Send"),
            ('confirm', "Confirm"),
        ],
        string="Status",
        readonly=True, copy=False, index=True,
        tracking=True,
        default='draft')
    proposal_state = fields.Selection(
        selection=[
            ('not_reviewed', " Not Reviewed"),
            ('approved', "Approved"),
            ('rejected', "Rejected"),
        ],
        string="Propsal Status",
        readonly=True, copy=False, index=True,
        tracking=True,
        default='not_reviewed')
    date_order = fields.Datetime(
        string="Order Date",
        required=True, readonly=False, copy=False,
        help="Creation date of draft/sent orders,\nConfirmation date of confirmed orders.",
        default=fields.Datetime.now)
    payment_term_id = fields.Many2one(
        comodel_name='account.payment.term',
        string="Payment Terms",
        compute='_compute_payment_term_id',
        store=True, readonly=False,
        precompute=True,
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    fiscal_position_id = fields.Many2one(
        comodel_name='account.fiscal.position',
        string="Fiscal Position",
        compute='_compute_fiscal_position_id',
        store=True, readonly=False, precompute=True, check_company=True,
        help="Fiscal positions are used to adapt taxes and accounts for particular customers or sales orders/invoices."
             "The default value comes from the customer.",
        domain="[('company_id', '=', company_id)]")
    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        string="Pricelist",
        compute='_compute_pricelist_id',
        store=True, readonly=False,
        precompute=True,
        check_company=True, required=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="If you change the pricelist, only newly added lines will be affected.")
    currency_id = fields.Many2one(
        related='pricelist_id.currency_id',
        depends=["pricelist_id"],
        store=True, precompute=True, ondelete="restrict")
    currency_rate = fields.Float(
        string="Currency Rate",
        compute='_compute_currency_rate',
        digits=(12, 6),
        store=True, precompute=True)
    user_id = fields.Many2one(
        comodel_name='res.users',
        string="Salesperson",
        compute='_compute_user_id',
        store=True, readonly=False, precompute=True, index=True)
    tax_country_id = fields.Many2one(
        comodel_name='res.country',
        compute='_compute_tax_country_id',
        compute_sudo=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        required=True, index=True,
        default=lambda self: self.env.company)
    order_line = fields.One2many(
        comodel_name='sales.proposal.line',
        inverse_name='sales_proposal_id',
        string="Sale Proposal Lines",
        copy=True, auto_join=True)
    note = fields.Html(string="Terms and conditions", store=True)
    tax_totals = fields.Binary(compute='_compute_tax_totals')
    amount_untaxed = fields.Monetary(string="Untaxed Amount", store=True, compute='_compute_amounts')
    amount_tax = fields.Monetary(string="Taxes", store=True, compute='_compute_amounts')
    amount_total = fields.Monetary(string="Total", store=True, compute='_compute_amounts')
    tax_totals_approved = fields.Binary(compute='_compute_tax_totals_approved')
    amount_untaxed_approved = fields.Monetary(string="Approved Untaxed Amount", store=True,
                                              compute='_compute_amounts_approved')
    amount_tax_approved = fields.Monetary(string="Taxes", store=True, compute='_compute_amounts_approved')
    amount_total_approved = fields.Monetary(string="Total", store=True, compute='_compute_amounts_approved')
    order_id = fields.Many2one(comodel_name='sale.order', string='Sale Order')



    @api.depends('currency_id', 'date_order', 'company_id')
    def _compute_currency_rate(self):
        cache = {}
        for rec in self:
            order_date = rec.date_order.date()
            if not rec.company_id:
                rec.currency_rate = rec.currency_id.with_context(date=order_date).rate or 1.0
                continue
            elif not rec.currency_id:
                rec.currency_rate = 1.0
            else:
                key = (rec.company_id.id, order_date, rec.currency_id.id)
                if key not in cache:
                    cache[key] = self.env['res.currency']._get_conversion_rate(
                        from_currency=rec.company_id.currency_id,
                        to_currency=rec.currency_id,
                        company=rec.company_id,
                        date=order_date,
                    )
                rec.currency_rate = cache[key]

    @api.depends('partner_id')
    def _compute_pricelist_id(self):
        for rec in self:
            if not rec.partner_id:
                rec.pricelist_id = False
                continue
            rec = rec.with_company(rec.company_id)
            rec.pricelist_id = rec.partner_id.property_product_pricelist

    @api.depends('partner_id')
    def _compute_payment_term_id(self):
        for rec in self:
            rec = rec.with_company(rec.company_id)
            rec.payment_term_id = rec.partner_id.property_payment_term_id

    @api.depends('partner_id')
    def _compute_partner_invoice_id(self):
        for rec in self:
            rec.partner_invoice_id = rec.partner_id.address_get(['invoice'])['invoice'] if rec.partner_id else False

    @api.depends('partner_id')
    def _compute_partner_shipping_id(self):
        for rec in self:
            rec.partner_shipping_id = rec.partner_id.address_get(['delivery'])['delivery'] if rec.partner_id else False

    @api.depends('partner_shipping_id', 'partner_id', 'company_id')
    def _compute_fiscal_position_id(self):
        cache = {}
        for rec in self:
            if not rec.partner_id:
                rec.fiscal_position_id = False
                continue
            key = (rec.company_id.id, rec.partner_id.id, rec.partner_shipping_id.id)
            if key not in cache:
                cache[key] = self.env['account.fiscal.position'].with_company(
                    rec.company_id
                )._get_fiscal_position(rec.partner_id, rec.partner_shipping_id)
            rec.fiscal_position_id = cache[key]

    @api.depends('partner_id')
    def _compute_user_id(self):
        for rec in self:
            if not rec.user_id:
                rec.user_id = rec.partner_id.user_id or rec.partner_id.commercial_partner_id.user_id or self.env.user

    @api.depends('company_id', 'fiscal_position_id')
    def _compute_tax_country_id(self):
        for rec in self:
            if rec.fiscal_position_id.foreign_vat:
                rec.tax_country_id = rec.fiscal_position_id.country_id
            else:
                rec.tax_country_id = rec.company_id.account_fiscal_country_id

    @api.depends('order_line.price_subtotal', 'order_line.price_tax', 'order_line.price_total')
    def _compute_amounts(self):
        for rec in self:
            order_lines = rec.order_line.filtered(lambda x: not x.display_type)
            rec.amount_untaxed = sum(order_lines.mapped('price_subtotal'))
            rec.amount_total = sum(order_lines.mapped('price_total'))
            rec.amount_tax = sum(order_lines.mapped('price_tax'))

    @api.depends('order_line.tax_id', 'order_line.price_unit', 'amount_total', 'amount_untaxed')
    def _compute_tax_totals(self):
        for rec in self:
            order_lines = rec.order_line.filtered(lambda x: not x.display_type)
            rec.tax_totals = self.env['account.tax']._prepare_tax_totals(
                [x._convert_to_tax_base_line_dict() for x in order_lines],
                rec.currency_id,
            )

    @api.depends('order_line.price_subtotal_approved', 'order_line.price_tax',
                 'order_line.price_total_approved')
    def _compute_amounts_approved(self):
        for rec in self:
            order_lines = rec.order_line.filtered(lambda x: not x.display_type)
            rec.amount_untaxed_approved = sum(order_lines.mapped('price_subtotal_approved'))
            rec.amount_total_approved = sum(order_lines.mapped('price_total_approved'))
            rec.amount_tax_approved = sum(order_lines.mapped('price_tax'))

    @api.depends('order_line.tax_id', 'order_line.price_unit_approved', 'amount_total_approved',
                 'amount_untaxed_approved')
    def _compute_tax_totals_approved(self):
        for rec in self:
            order_lines = rec.order_line.filtered(lambda x: not x.display_type)
            rec.tax_totals_approved = self.env['account.tax']._prepare_tax_totals(
                [x._convert_to_tax_base_line_dict_approved() for x in order_lines],
                rec.currency_id,
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(
                    vals['date_order'])) if 'date_order' in vals else None
                vals['name'] = seq_date.strftime("Proposal/%Y/%b/") + self.env['ir.sequence'].next_by_code(
                    'sales.proposal') if seq_date else 'New'
        return super().create(vals)



    def action_preview_sales_proposal(self):
        self.ensure_one()
        print('self', self.id)
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': f'/sales/proposals/{self.id}/{self.get_portal_url()}',
        }

    def action_confirm_proposal(self):
        self.ensure_one()
        self.order_id = self.env['sale.order'].create(
            [{
                'partner_id': self.partner_id.id,
                'state': 'draft',
                'origin': self.name,
                'order_line': [Command.create({
                    'id': line.id,
                    'product_id': line.product_id.id,
                    'product_uom': line.product_uom.id,
                    'product_uom_qty': line.product_uom_qty_approved,
                    'price_unit': line.price_unit_approved,
                    'tax_id': [(6, 0, line.tax_id.ids)]
                }) for line in self.order_line]
            }]
        )
        self.state = 'confirm'
        return True


    def action_send_proposal_mail(self):
        self.ensure_one()
        lang = self.env.context.get('lang')
        mail_template = self.env.ref('sales_proposal.sales_proposal_email_template', raise_if_not_found=False)
        if mail_template and mail_template.lang:
            lang = mail_template._render_lang(self.ids)[self.id]
        ctx = {
            'default_model': 'sales.proposal',
            'default_res_id': self.id,
            'default_use_template': bool(mail_template),
            'default_template_id': mail_template.id if mail_template else None,
            'default_composition_mode': 'comment',
            'mark_proposal_as_sent': True,
            'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
            'force_email': True,
            'model_description': self.with_context(lang=lang),
        }
        self.write({'state': 'send'})
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    def action_draft(self):
        self.write({
            'state': 'draft',
            'proposal_state': 'not_reviewed'
        })
