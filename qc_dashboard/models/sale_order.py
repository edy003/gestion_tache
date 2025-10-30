from odoo import models, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def get_sales_count(self):
        return {
            'all_sales': len(self.env['sale.order'].search([])),
            'draft': len(self.env['sale.order'].search([('state', '=', 'draft')])),
            'sent': len(self.env['sale.order'].search([('state', '=', 'sent')])),
            'sale': len(self.env['sale.order'].search([('state', '=', 'sale')])),
            'done': len(self.env['sale.order'].search([('state', '=', 'done')])),
            'cancel': len(self.env['sale.order'].search([('state', '=', 'cancel')])),
        }