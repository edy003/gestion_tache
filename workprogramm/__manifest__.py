# -*- coding: utf-8 -*-
{
    'name': "work programm final",

    'summary': """
        Comprehensive workflow and work program management system with hierarchical structure""",

    'description': """
        Work Program Management Module
        =============================

        This module provides a complete solution for managing workflows and work programs with:

        * Hierarchical workflow structure (Domain > Process > Subprocess > Activity > Procedure)
        * Work program planning and tracking
        * Department-based access control
        * Task formulation and deliverable management
        * Integration with HR departments

        Key Features:
        * Multi-level workflow hierarchy
        * Role-based permissions (User/Manager/Administrator)
        * Department-specific access rules
        * Work program scheduling and monitoring
    """,

    'author': "Your Company Name",
    'website': "https://www.yourcompany.com",

    'category': 'Project',  # Plus approprié que 'Uncategorized'
    'version': '1.0.0',

    # Dépendances nécessaires
    'depends': [
        'base',
        'web',
        'project',
        'mail',
        'hr',
        'website'
    ],

    # Fichiers de données - ordre important !
    'data': [
        # 1. Sécurité (vient souvent en premier)
        'security/security.xml',
        'data/work_program_sequence.xml',
        # 2. Données des Départements (requis par les pratiques)
        'data/hr_department_data.xml',
        # 3. Données des Pratiques (requis par les sous-catégories)
        'data/practice_data.xml',
        # 4. Données des Sous-catégories
        'data/subcategory_data.xml',
        # 4. Données du cadre de reference
        'data/cd_ref_workflow_data.xml',
        'views/practice_views.xml',
        'views/project_views.xml',
        'views/hr_department_view.xml',
        # Vues et actions
        'views/views.xml',
        'views/work_actions.xml',
        'views/work_menus.xml',
        'views/cd_ref_workflow.xml',
        'views/work_program_view.xml',
        'views/hr_department_view.xml',
        # Templates en dernier
        'views/templates.xml',
        'views/work_program_layout_controller.xml',
        'views/reponses_templates.xml',
        'views/work_program_search_view.xml',
        'views/work_program_kanban_view.xml',  # <-- Kanban ajouté ici

    ],

    # Données de démonstration
    'demo': [
        'demo/demo.xml',
    ],

    # Assets web (si nécessaire)
    'assets': {
        'web.assets_backend': [
            # 'workprogramm/static/src/css/workprogramm.css',
            # 'workprogramm/static/src/js/workprogramm.js',
        ],
    },

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'sequence': 10,
}