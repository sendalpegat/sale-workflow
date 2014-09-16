# -*- coding: utf-8 -*-
#
#    Author: Alexandre Fayolle
#    Copyright 2014 Camptocamp SA
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
#
import logging

from openerp import models, fields, api, _
from openerp.exceptions import except_orm

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.multi
    def action_button_confirm(self):
        """before triggering the workflow, if some lines need sourcing, run the
        sourcing wizard, otherwise, propagate the call and do the confirmation
        of the SO.
        """
        self.ensure_one()
        order = self[0]
        lines_to_source = []
        for line in order.order_line:
            if line.needs_sourcing():
                lines_to_source.append(line)
        if lines_to_source:
            wizard = self._create_sourcing_wizard(lines_to_source)
            return {'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_model': 'sale.order.sourcing',
                    'res_id': wizard.id,
                    'target': 'new',
                    }
        else:
            return super(SaleOrder, self).action_button_confirm()

    @api.model
    def _create_sourcing_wizard(self, lines_to_source):
        line_values = []
        for line in lines_to_source:
            line_values.append((0, 0, {'so_line_id': line.id, 'po_id': False}))
        values = {'sale_id': self[0].id,
                  'line_ids': line_values,
                  }
        return self.env['sale.order.sourcing'].create(values)

    @api.model
    def _prepare_order_line_procurement(self, order, line, group_id):
        proc_data = super(SaleOrder, self)._prepare_order_line_procurement(
            order, line, group_id)
        if line.manually_sourced:
            procurement_rule_obj = self.env['procurement.rule']
            domain = [('warehouse_id', '=', proc_data['warehouse_id']),
                      ('action', '=', 'buy'),
                      ]
            rules = procurement_rule_obj.search(domain,
                                                limit=1,
                                                order='route_sequence')
            if not rules:
                msg = _('no buy rule configured for warehouse %d')
                raise except_orm(_('configuration problem'),
                                 msg % proc_data['warehouse_id'])
            proc_data['rule_id'] = rules[0].id
        return proc_data


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    manually_sourced = fields.Boolean('Manually Sourced')
    sourced_by = fields.Many2one('purchase.order.line', copy=False,
                                 domain="[('product_id', '=', product_id)]")

    @api.multi
    def needs_sourcing(self):
        return any(line.manually_sourced and not line.sourced_by
                   for line in self)
