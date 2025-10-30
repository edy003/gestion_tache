# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class WorkProgramController(http.Controller):

    @http.route('/work_program/form', type='http', auth='public', website=True)
    def work_program_form(self):
        """
        Affiche le formulaire pour créer un programme de travail.
        Récupère toutes les données nécessaires du backend pour les menus déroulants.
        """
        # Utilisation de sudo() pour accéder aux modèles avec les droits de super-utilisateur,
        # ce qui est courant pour les pages publiques.
        employees = request.env['hr.employee'].sudo().search([])
        projects = request.env['project.project'].sudo().search([])
        activities = request.env['workflow.activity'].sudo().search([])
        procedures = request.env['workflow.procedure'].sudo().search([])
        task_descriptions = request.env['workflow.task.formulation'].sudo().search([])
        deliverables = request.env['workflow.deliverable'].sudo().search([])
        departments = request.env['hr.department'].sudo().search([])

        # Récupération des listes de sélection directement depuis le modèle
        priorities = request.env['work.program']._fields['priority'].selection
        complexities = request.env['work.program']._fields['complexity'].selection
        satisfaction_levels = request.env['work.program']._fields['satisfaction_level'].selection

        values = {
            'employees': employees,
            'projects': projects,
            'activities': activities,
            'procedures': procedures,
            'task_descriptions': task_descriptions,
            'deliverables': deliverables,
            'departments': departments,
            'priorities': priorities,
            'complexities': complexities,
            'satisfaction_levels': satisfaction_levels,
        }

        # Rendre le template du formulaire
        return request.render('workprogramm.work_program_form_template', values)

    @http.route('/work_program/submit', type='http', auth='public', website=True, methods=['POST'])
    def work_program_submit(self, **post):
        """
        Traite les données du formulaire soumis.
        """
        try:
            # Récupère les IDs des champs many2one
            project_id = int(post.get('project_id')) if post.get('project_id') else False
            activity_id = int(post.get('activity_id')) if post.get('activity_id') else False
            procedure_id = int(post.get('procedure_id')) if post.get('procedure_id') else False
            task_description_id = int(post.get('task_description_id')) if post.get('task_description_id') else False
            responsible_id = int(post.get('responsible_id')) if post.get('responsible_id') else False
            department_id = int(post.get('work_programm_department_id')) if post.get('work_programm_department_id') else False

            # Récupération des IDs des champs many2many
            # CORRECTION CLÉ : Utilisation de request.httprequest.form.getlist() pour les champs multiples
            deliverable_ids_list = [int(d) for d in request.httprequest.form.getlist('deliverable_ids')]
            support_ids_list = [int(s) for s in request.httprequest.form.getlist('support_ids')]

            # Prépare les valeurs pour la création de l'enregistrement
            vals = {
                'project_id': project_id,
                'activity_id': activity_id,
                'procedure_id': procedure_id,
                'task_description_id': task_description_id,
                'inputs_needed': post.get('inputs_needed'),
                'responsible_id': responsible_id,
                'deliverable_ids': [(6, 0, deliverable_ids_list)],
                'support_ids': [(6, 0, support_ids_list)],
                'work_programm_department_id': department_id,
                'my_month': post.get('my_month'),
                'my_week_of': post.get('my_week_of'),
                'priority': post.get('priority'),
                'complexity': post.get('complexity'),
                'assignment_date': post.get('assignment_date'),
                'duration_effort': float(post.get('duration_effort') or 0.0),
                'initial_deadline': post.get('initial_deadline'),
                'nb_postpones': int(post.get('nb_postpones') or 0),
                'actual_deadline': post.get('actual_deadline'),
                'completion_percentage': float(post.get('completion_percentage') or 0.0),
                'satisfaction_level': post.get('satisfaction_level'),
                'comments': post.get('comments'),
                'champ1': post.get('champ1'),
                'champ2': post.get('champ2'),
            }

            # Crée l'enregistrement dans Odoo
            new_record = request.env['work.program'].sudo().create(vals)

            # Redirige l'utilisateur vers la page de succès
            return request.render('workprogramm.work_program_success_template', {'record': new_record})

        except Exception as e:
            # Gérer les erreurs et afficher un message approprié
            return request.render('workprogramm.work_program_error_template', {'error_message': str(e)})