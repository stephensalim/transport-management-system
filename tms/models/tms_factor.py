# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

from openerp import api, fields, models
# import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


# Extra data fields for Waybills & Agreement
# Factors
class TmsFactor(models.Model):
    _name = "tms.factor"
    _description = "Factors to calculate Payment (Driver/Supplier) & Client \
                        charge"

    name = fields.Char('Name', size=64, required=True)
    category = fields.Selection([
        ('driver', 'Driver'),
        ('customer', 'Customer'),
        ('supplier', 'Supplier')], 'Type', required=True)
    factor_type = fields.Selection([
        ('distance', 'Distance Route (Km/Mi)'),
        ('distance_real', 'Distance Real (Km/Mi)'),
        ('weight', 'Weight'),
        ('travel', 'Travel'),
        ('qty', 'Quantity'),
        ('volume', 'Volume'),
        ('percent', 'Income Percent')], 'Factor Type', required=True, help="""
For next options you have to type Ranges or Fixed Amount
 - Distance Route (Km/mi)
 - Distance Real (Km/Mi)
 - Weight
 - Quantity
 - Volume
For next option you only have to type Fixed Amount:
 - Travel
For next option you only have to type Factor like 10.5 for 10.50%:
 - Income Percent
                        """)
    framework = fields.Selection([
                                ('Any', 'Any'),
                                ('Unit', 'Unit'),
                                ('Single', 'Single'),
                                ('Double', 'Double'), ],
        'Framework', required=True, default='Any')
    range_start = fields.Float('Range Start', digits=(16, 4))
    range_end = fields.Float('Range End', digits=(16, 4))
    factor = fields.Float('Factor', digits=(16, 4))
    fixed_amount = fields.Float('Fixed Amount', digits=(16, 4))
    mixed = fields.Boolean('Mixed', default=False)
    sequence = fields.Integer(
        'Sequence', help="Gives the sequence calculation for these factors.",
        default=10)
    notes = fields.Text('Notes')
    driver_helper = fields.Boolean('For Driver Helper')

    _order = "sequence"

    @api.multi
    def on_change_factor_type(self, factor_type):
        if not factor_type:
            return {'value': {'name': False}}
        values = {
            'distance': _('Distance Route (Km/Mi)'),
            'distance_real': _('Distance Real (Km/Mi)'),
            'weight': _('Weight'),
            'travel': _('Travel'),
            'qty': _('Quantity'),
            'volume': _('Volume'),
            'percent': _('Income Percent'),
        }
        return {'value': {'name': values[factor_type]}}

    def calculate(self, record_type, record_ids, calc_type=None,
                  travel_ids=False, driver_helper=False):
        result = 0.0
        if record_type == 'waybill':
            waybill_obj = self.pool.get('tms.waybill')
            for waybill in waybill_obj.browse(record_ids):
                # No soporta segundo operador
                for factor in (
                    waybill.waybill_customer_factor if calc_type == 'client'
                        else waybill.expense_driver_factor
                        if calc_type == 'driver'
                        else waybill.waybill_supplier_factor):
                    if factor.factor_type in ('distance', 'distance_real'):
                        if not waybill.travel_id.id:
                            raise Warning(
                                _('Could calculate Amount for Waybill !'),
                                _('Waybill %s is not assigned to a Travel\
                                    ') % (waybill.name))
                        x = ((float(waybill.travel_id.route_id.distance)
                             if factor.factor_type == 'distance'
                             else float(waybill.travel_id.distance_extraction))
                             if (factor.framework == 'Any' or
                                 factor.framework ==
                                 waybill.travel_id.framework)
                             else 0.0)
                    elif factor.factor_type == 'weight':
                        if not waybill.product_weight:
                            raise Warning(
                                _('Could calculate Freight Amount !'),
                                _('Waybill %s has no Products with UoM \
                                Category = Weight or Product Qty = 0.0\
                                ' % waybill.name))
                        x = float(waybill.product_weight)
                    elif factor.factor_type == 'qty':
                        if not waybill.product_qty:
                            raise Warning(
                                _('Could calculate Freight Amount !'),
                                _('Waybill %s has no Products with Quantity \
                                    > 0.0') % (waybill.name))
                        x = float(waybill.product_qty)
                    elif factor.factor_type == 'volume':
                        if not waybill.product_volume:
                            raise Warning(
                                _('Could calculate Freight Amount !'),
                                _('Waybill %s has no Products with UoM \
                                Category = Volume or Product Qty = 0.0\
                                ') % (waybill.name))
                        x = float(waybill.product_volume)
                    elif factor.factor_type == 'percent':
                        x = float(waybill.amount_freight) / 100.0
                    elif factor.factor_type == 'travel':
                        x = 0.0
                    result += (
                        ((factor.fixed_amount if (
                            factor.mixed or
                            factor.factor_type == 'travel') else 0.0))
                        if (((x >= factor.range_start and
                              x <= factor.range_end) or
                            (factor.range_start ==
                             factor.range_end == 0.0)) and
                            factor.driver_helper == driver_helper) else 0.0)
        elif record_type == 'expense' and travel_ids:
            travel_obj = self.pool.get('tms.travel')
            for travel in travel_obj.browse(travel_ids):
                res1 = res2 = weight = qty = volume = x = 0.0
                if travel.waybill_ids:
                    for waybill in travel.waybill_ids:
                        res1 += self.calculate(
                            'waybill', [waybill.id], 'driver',
                            travel_ids=False, driver_helper=driver_helper)
                        weight += waybill.product_weight
                        qty += waybill.product_qty
                        volume += waybill.product_volume
                if not res1:
                    for factor in travel.expense_driver_factor:
                        if factor.factor_type == 'distance':
                            x = ((float(travel.route_id.distance)
                                 if factor.factor_type == 'distance'
                                 else
                                 float(travel.route_id.distance_extraction))
                                 if (factor.framework == 'Any' or
                                     factor.framework == travel.framework)
                                 else 0.0)
                        elif factor.factor_type == 'weight':
                            if not weight:
                                raise Warning(
                                    _('Could calculate Freight Amount !'),
                                    _('Waybills related to Travel %s has no \
                                    Products with UoM Category = Weight or \
                                    Product Qty = 0.0') % (travel.name))
                            x = float(weight)
                        elif factor.factor_type == 'qty':
                            if not qty:
                                raise Warning(
                                    _('Could calculate Freight Amount !'),
                                    _('Waybills related to Travel %s has no \
                            Products with Quantity > 0.0') % (travel.name))
                            x = float(qty)
                        elif factor.factor_type == 'volume':
                            if not volume:
                                raise Warning(
                                    _('Could calculate Freight Amount !'),
                                    _('Waybills related to Travel %s has no \
                                    Products with UoM Category = Volume or \
                                    Product Qty = 0.0') % (travel.name))
                            x = float(volume)
                        elif factor.factor_type == 'travel':
                            x = 0.0
                        res2 += (((factor.fixed_amount if
                                   (factor.mixed or
                                    factor.factor_type == 'travel') else 0.0))
                                 if (((x >= factor.range_start and
                                       x <= factor.range_end) or
                                     (factor.range_start ==
                                      factor.range_end == 0.0)) and
                                     factor.driver_helper ==
                                     driver_helper) else 0.0)
                result += res1 + res2
        return result