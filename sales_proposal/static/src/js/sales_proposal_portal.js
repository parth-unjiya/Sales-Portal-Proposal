odoo.define('sales_proposal.portal_proposal', function (require) {
    'use strict';

    console.log("--------")
    var publicWidget = require('web.public.widget');
    var core = require('web.core');
    var _t = core._t;


    publicWidget.registry.PortalProposal = publicWidget.Widget.extend({
        selector: '.o_sales_portal_proposal_sidebar',
        events: {
            'change #approved_qty': '_onChangeApprovedQuantity',
            'change #approved_price': '_onChangeApprovedPrice',
        },
        /**
         * @constructor
         */
        init: function () {
            this._super.apply(this, arguments);
        }
        ,
        start() {
            this._super(...arguments);
            this.orderDetail = this.$el.find('table#sales_proposal_table').data();
        },

        _callUpdateLineRoute(order_id, params) {
            var self = this;
            return this._rpc({
                route: "/sales/proposals/" + order_id + "/update_line_dict",
                params: params,
            }).then(function () {
                window.location.reload();
            });
        },

        _refreshOrderUI(data){
            const $proposalTemplate = $(data['proposal_template']);
            if ($proposalTemplate.length) {
                this.$('#proposal_content').html($proposalTemplate);
            }
        },

        _onChangeApprovedQuantity(ev) {
            ev.preventDefault();
            var quantity_approved = parseFloat(ev.currentTarget.value);
            console.log(">>>>>>",quantity_approved)
            const result =  this._callUpdateLineRoute(this.orderDetail.orderId, {
                'line_id': $(ev.currentTarget).data('lineId'),
                'input_quantity': quantity_approved >= 0 ? quantity_approved : alert('Quantity cannot be a negative value'),
                'access_token': this.orderDetail.token
            });
            this._refreshOrderUI(result);
        },

        _onChangeApprovedPrice(ev) {
            ev.preventDefault();
            var quantity_price = parseFloat(ev.currentTarget.value);
            console.log("<<<<<<<",quantity_price)
            const result =  this._callUpdateLineRoute(this.orderDetail.orderId, {
                'line_id': $(ev.currentTarget).data('lineId'),
                'input_price': quantity_price >= 0 ? quantity_price : alert('Price cannot be a negative value'),
                'access_token': this.orderDetail.token
            });
            this._refreshOrderUI(result);
        },
    })
});