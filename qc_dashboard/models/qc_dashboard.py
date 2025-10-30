# -*- coding: utf-8 -*-
from odoo import models, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def get_dashboard_kpis(self):
        """
        Méthode pour récupérer les données des KPI pour le dashboard.
        """
        # Remplacez ceci par votre propre logique pour récupérer les données réelles
        # Par exemple :
        # product_conformity_rate = self.env['product.template'].search_count([])
        
        kpis = [
            {
                'title': "Produits Conformés",
                'value': 98.5,
                'unit': "%",
                'description': "Taux de conformité des produits du mois en cours.",
            },
            {
                'title': "Inspections Réalisées",
                'value': 245,
                'unit': "Unités",
                'description': "Nombre total d'inspections menées ce mois-ci.",
            },
            {
                'title': "Non-Conformités",
                'value': 12,
                'unit': "Cas",
                'description': "Nombre de cas de non-conformité identifiés.",
            },
            {
                'title': "Délai d'Inspection",
                'value': 2.1,
                'unit': "Jours",
                'description': "Temps moyen pour clore une inspection.",
            },
        ]
        return kpis