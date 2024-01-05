# -*- coding: utf-8 -*-

from odoo import fields, http, SUPERUSER_ID, _
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.portal.controllers.mail import _message_post_helper
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.addons.portal.controllers import portal
from odoo.http import request


class ProposalPortal(portal.CustomerPortal):

    def _get_proposal_portal_details(self, proposal):
        return {
            'proposal_template': request.env['ir.ui.view']._render_template(
                'sales_proposal.sales_proposal_portal_content', {
                    'sales_proposal': proposal,
                    'report_type': 'html',
                },
            ),
        }

    def _set_self_portal_data(self, counter):
        values = super()._set_self_portal_data(counter)
        partner = request.env.user.partner_id
        if 'order_count' in counter:
            SaleProposal = request.env['sales.proposal']
            values['order_count'] = SaleProposal.search_count(self._set_proposal_domain(partner)) \
                if SaleProposal.check_access_rights('read', raise_exception=False) else 0
            return values

    def _set_proposal_domain(self, partner):
        return [
            ('message_partner_ids', 'child_of', [partner.commercial_partner_id.id]),
        ]

    def _sales_proposal_sortings(self):
        return {
            'date': {'label': _('Order Date'), 'order': 'date_order desc'},
            'name': {'label': _('Reference'), 'order': 'name'},
            'stage': {'label': _('Stage'), 'order': 'state'},
        }

    def _proposal_portal_rendering_data(
            self, page=1, date_begin=None, date_end=None, sortby=None, **kwargs
    ):
        SaleProposal = request.env['sales.proposal']

        if not sortby:
            sortby = 'date'

        partner = request.env.user.partner_id
        values = self._set_portal_layout_values()

        url = "/my/proposals"
        domain = self._set_proposal_domain(partner)

        searchbar_sortings = self._sales_proposal_sortings()

        sort_order = searchbar_sortings[sortby]['order']

        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        pager_values = portal_pager(
            url=url,
            total=SaleProposal.search_count(domain),
            page=page,
            step=self._items_per_page,
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
        )
        orders = SaleProposal.search(domain, order=sort_order, limit=self._items_per_page,
                                     offset=pager_values['offset'])
        values.update({
            'date': date_begin,
            'quotations': orders.sudo(),
            'orders': orders.sudo(),
            'page_name': 'sales_proposal',
            'pager': pager_values,
            'default_url': url,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return values

    @http.route(['/my/proposals', '/my/propsals/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_proposal(self, **kwargs):
        values = self._proposal_portal_rendering_data(**kwargs)
        request.session['my_proposals_history'] = values['orders'].ids[:100]
        return request.render("sales_proposal.portal_my_sales_proposals", values)

    @http.route(['/sales/proposals/<int:order_id>'], type='http', auth="public", website=True)
    def portal_sales_proposal_page(self, order_id, report_type=None, access_token=None, message=False, download=False,
                                  **kw):
        try:
            order_sudo = self._document_check_access('sales.proposal', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        # backend_url = f'/web#model={order_sudo._name}' \
        #               f'&id={order_sudo.id}' \
        #               f'&action={order_sudo._portal_reback_action().id}' \
        #               f'&view_type=form'
        values = {
            'sales_proposal': order_sudo,
            'message': message,
            'report_type': 'html',
            # 'backend_url': backend_url,
            'res_company': order_sudo.company_id,  # Used to display correct company logo
        }

        if order_sudo.state in ('draft', 'send'):
            history_session_key = 'my_proposals_history'
        else:
            history_session_key = 'my_saleorder_history'

        values = self._get_page_view_values(
            order_sudo, access_token, values, history_session_key, False)

        return request.render('sales_proposal.sales_proposal_portal_template', values)

    @http.route(['/sales/proposals/<int:order_id>/decline'], type='http', auth="public", methods=['POST'], website=True)
    def proposal_reject(self, order_id, access_token=None, decline_message=None, **kwargs):
        try:
            order_sudo = self._document_check_access('sales.proposal', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        if order_sudo and decline_message:
            order_sudo.write({
                'proposal_state': 'rejected'
            })
            _message_post_helper(
                'sales.proposal',
                order_sudo.id,
                decline_message,
                token=access_token,
            )
            redirect_url = order_sudo.get_portal_url()

        return request.redirect(redirect_url)

    @http.route(['/sales/proposals/<int:order_id>/approve'], type='http', auth="public", methods=['POST'], website=True)
    def proposal_approve(self, order_id, access_token=None, **kwargs):
        try:
            order_sudo = self._document_check_access('sales.proposal', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        if order_sudo:
            order_sudo.write({
                'proposal_state': 'approved'
            })
            _message_post_helper(
                'sales.proposal',
                order_sudo.id,
                message='Proposal Approved',
                token=access_token,
            )
            redirect_url = order_sudo.get_portal_url()
        return request.redirect(redirect_url)

    @http.route(['/sales/proposals/<int:order_id>/update_line_dict'], type='json', auth="public", methods=['POST'],
                website=True, csrf=False)
    def update_orderlines_json(self, order_id, access_token=None, line_id=None, input_quantity=None, input_price=None,
                               **kw):
        try:
            proposal = self._document_check_access('sales.proposal', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        if proposal.state not in ('draft', 'send'):
            return False
        order_line = request.env['sales.proposal.line'].sudo().browse(int(line_id)).exists()

        if not order_line or order_line.sales_proposal_id != proposal:
            return False

        if input_quantity != None:
            # quantity = input_quantity
            order_line.product_uom_qty_approved = input_quantity

        if input_price != None:
            order_line.price_unit_approved = input_price
        return self._get_proposal_portal_details(proposal)