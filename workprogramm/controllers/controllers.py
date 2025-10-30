# -*- coding: utf-8 -*-
from odoo import http

class HelloWorldController(http.Controller):
    @http.route('/helloj/world', auth='public', website=True)
    def hello_world_page(self):
        """Affiche une page simple avec le texte 'Hello, World!'."""
        return "<h1>Hello, World!</h1>"