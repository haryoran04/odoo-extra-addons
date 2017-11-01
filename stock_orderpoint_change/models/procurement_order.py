# -*- encoding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2015 ICTSTUDIO (<http://www.ictstudio.eu>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ProcurementOrder(models.Model):
    _inherit = 'procurement.order'

    @api.multi
    def get_chained_procurements(self):
        chained_procurements = self.env['procurement.order']
        for rec in self:
            for move in rec.move_ids:
                chained_procurements += move.procurement_id
                chained_procurements += move.move_dest_id.procurement_id.get_chained_procurements()
            chained_procurements += rec.filtered(lambda p: p.state not in ('cancel', 'done'))
        _logger.debug("Chained Procurements (Stock Change): %s", chained_procurements)
        return chained_procurements

    @api.multi
    def cancel_chain(self):
        error_procurements = self.env['procurement.order']
        cancel_procurements = self.env['procurement.order']
        for rec in self:
            if rec.state not in ('cancel', 'done'):
                _logger.debug("Proc State: %s", rec.state)
                if rec.check_no_cancel():
                    _logger.debug("Prevented Cancel: %s", rec)
                    error_procurements += rec
                else:
                    rec.cancel()
                    cancel_procurements += rec
        return cancel_procurements, error_procurements

    @api.multi
    def check_no_cancel(self):
        self.ensure_one()
        no_cancel = super(ProcurementOrder, self).check_no_cancel()
        if not no_cancel:
            if self.rule_id and self.rule_id.prevent_cancel:
                transit_move = self.env['stock.move'].search(
                    [
                        ('procurement_id', '=', self.id)
                    ],
                    limit=1
                )
                if transit_move and transit_move.move_dest_id and transit_move.move_dest_id.procurement_id and transit_move.move_dest_id.procurement_id.state == 'done':
                    no_cancel = True
        return no_cancel or False
