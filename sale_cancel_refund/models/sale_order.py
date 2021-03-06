# -*- coding: utf-8 -*-
# Copyright© 2015 ICTSTUDIO <http://www.ictstudio.eu>
# License: AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

import logging
from openerp import api, models, fields, _
from openerp.exceptions import Warning as UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.multi
    def action_create_refund(self):
        refunds = self.env['account.invoice']
        if len(self.invoice_ids) == 1 and self.invoice_ids.type == 'out_invoice':
            refunds = self.env['account.invoice']
            for inv in self.invoice_ids:
                if inv.state in ['open', 'paid']:
                    date = fields.Date.today()
                    period = inv.period_id and inv.period_id.id or False
                    description = inv.internal_number and 'Credit: %s' % inv.internal_number or 'Credit'

                    refund = inv.refund(date, period, description)

                    refund.write(
                        {
                            'date_due': date,
                            'check_total': inv.check_total
                        }
                    )
                    refund.button_compute()
                    refund.signal_workflow('invoice_open')
                    if refund.state == 'open':
                        self.reconcile_invoice_refund(inv, refund)
                    refunds += refund
                else:
                    inv.action_cancel()
        return refunds

    @api.model
    def reconcile_invoice_refund(self, invoice, refund):
        movelines = invoice.move_id.line_id
        to_reconcile_ids = {}

        # Reconcile lines with reconcile true not payable or receivable
        for line in movelines:
            if line.account_id.reconcile and not line.account_id.type in [
                'payable', 'receivable']:
                to_reconcile_ids.setdefault(line.account_id.id, []).append(
                    line.id)
                line.reconcile_id.unlink()

        for rline in refund.move_id.line_id:
            if rline.account_id.reconcile and not rline.account_id.type in [
                'payable', 'receivable']:
                to_reconcile_ids[rline.account_id.id].append(rline.id)

        for account in to_reconcile_ids:
            amls = self.env['account.move.line'].browse(
                to_reconcile_ids[account])
            if amls:
                amls.reconcile(
                    writeoff_period_id=False,
                    writeoff_journal_id=False,
                    writeoff_acc_id=False
                )

    @api.one
    def action_advanced_cancel(self):

        # Cancel Picking
        if len(self.picking_ids) == 1 and self.picking_ids.state not in (
                'done'):
            pick = self.picking_ids[0]
            if 'wave_id' in pick._fields and pick.wave_id:
                raise UserError(
                    _("Order is being picked!"),
                    _(
                        "First pull picking from Picking Wave: %s") % pick.wave_id.name
                )
            try:
                pick.action_cancel()
            except:
                _logger.debug("Error Cancel Picking")
            try:
                for line in self.order_line:
                    line.procurement_ids.cancel()
            except:
                _logger.debug("Error Cancel Sale Order Procurements")

        elif len(self.picking_ids) == 1:
            raise UserError(
                _("Order has been picked!"),
                _("Unable to cancel a picking already done")
            )

        # Create Refund
        refunds = self.action_create_refund()
        _logger.debug("Create Refund: %s", refunds)
        if refunds:
            for refund in refunds:
                self.invoice_ids += refund

        return True

    @api.multi
    def action_cancel(self):
        self.ensure_one()

        if self.order_policy == 'manual' and len(self.invoice_ids) == 1:
            self.action_advanced_cancel()

            self.state = 'cancel'
            return True
        else:
            return super(SaleOrder, self).action_cancel()
