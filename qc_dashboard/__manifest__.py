# -*- coding: utf-8 -*-
{
    'name': 'QC Dashboard ',
    'version': '1.1',
    'summary': ' work programm and evaluation Dashboard  ',
    # 'sequence': -1,
    'description': """
    Tableau de bord avancé avec :
    - KPI des utilisateurs
    - Graphiques interactifs 
    - Analytics en temps réel
    """,
    'category': 'Dashboard',
    'depends': ['base', 'web'],
    'data': [
        # 'views/kpi_card_views.xml',
        # 'qc_dashboard/static/src/xml/templates.xml',
        # 'qc_dashboard/static/src/xml/kpi_card.xml',
        'views/kpi_card_views.xml',
        # 'views/user_kpi_dashboard.xml',

    ],
    'assets': {
        'web.assets_backend': [
            'qc_dashboard/static/src/css/dist/output.css',
            'qc_dashboard/static/src/css/kpi.css',
            # 'qc_dashboard/static/src/css/evaluation_template.css',
        'qc_dashboard/static/src/css/evaluation_template1.css',
            # 'qc_dashboard/static/src/js/card.js',
            'qc_dashboard/static/src/js/template.js',
            # 'qc_dashboard/static/src/js/sidebar_toggle.js',
            # 'qc_dashboard/static/src/js/kpi_card.js',
            'qc_dashboard/static/src/js/evaluation_template.js',
            # 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css',
            # 'https://cdn.jsdelivr.net/npm/ag-grid-community/dist/ag-grid-community.min.js',
            # 'https://unpkg.com/ag-grid-community@30.2.1/dist/ag-grid-community.min.js',
            # 'https://unpkg.com/ag-grid-community@27.3.0/dist/ag-grid-community.min.js',
'https://cdn.jsdelivr.net/npm/ag-grid-community/dist/ag-grid-community.min.js',
"https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css",
            # "https://cdn.jsdelivr.net/npm/flatpickr",

            # 'https://cdn.jsdelivr.net/npm/ag-grid-community@27.3.0/dist/ag-grid-community.min.js',
'https://cdn.plot.ly/plotly-3.1.0.min.js',
        ],
        'web.assets_qweb': [
            'qc_dashboard/static/src/xml/evaluation_template1.xml',
             'qc_dashboard/static/src/xml/template1.xml',
            # 'qc_dashboard/static/src/xml/evaluation_template.xml',
            # 'qc_dashboard/static/src/xml/kpi_card.xml',

            # Templates QWeb legacy si nécessaire
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
}

# npx tailwindcss -i ./static/src/css/input.css -o ./static/src/css/dist/output.css --watch
