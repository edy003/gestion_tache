# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)



class WorkProgramDashboardController(http.Controller):

    @http.route('/dashboard/current_employee_info', type='json', auth='user', methods=['GET', 'POST'], csrf=False)
    def get_current_employee_info(self, **kw):
        """
        Retourne les infos de l'employé lié à l'utilisateur connecté :
        - id, name
        - department: {id, name} (None si pas de département)
        - image_url: URL de l'image de l'employé (ou placeholder)
        - role: Rôle prioritaire ('Administrateur', 'Manager', 'Employé')
        """
        try:
            user = request.env.user
            _logger.info(f"Récupération info employé pour user: {user.login} ({user.name})")

            # Récupération de l'employé lié à l'utilisateur connecté
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)

            if not employee:
                _logger.warning(f"Aucun employé associé pour l'utilisateur {user.name} (id={user.id})")
                return {
                    'error': True,
                    'message': "Aucun employé associé à cet utilisateur.",
                    'employee': None
                }

            # Récupération des informations de base
            emp_id = employee.id
            emp_name = employee.name or ''
            dept = employee.department_id.sudo() if employee.department_id else None
            dept_info = {'id': dept.id, 'name': dept.name} if dept else None

            # URL de l'image
            image_url = f"/web/image/hr.employee/{emp_id}/avatar_128" if emp_id else "/web/static/src/img/placeholder.png"

            # Détermination du rôle prioritaire
            if user.has_group('workprogramm.workprogramm_group_admin'):
                role = "Administrateur"
            elif user.has_group('workprogramm.workprogramm_group_manager'):
                role = "Manager"
            elif user.has_group('workprogramm.workprogramm_group_user_limited'):
                role = "Employé"
            else:
                role = "Employé"  # Valeur par défaut si aucun rôle spécifique

            _logger.info(f"✅ Employé trouvé : {emp_name}, Département : {dept_info['name'] if dept_info else 'Aucun'}, Rôle : {role}")

            return {
                'error': False,
                'employee': {
                    'id': emp_id,
                    'name': emp_name,
                    'department': dept_info,
                    'image_url': image_url,
                    'role': role
                }
            }

        except Exception as e:
            _logger.exception("Erreur lors de la récupération des infos employé")
            return {
                'error': True,
                'message': str(e),
                'employee': None
            }

   
    def _apply_security_filter(self, df):
        """
        Filtre le DataFrame selon les droits d'accès de l'utilisateur :
        - Admin ou Manager : accès à toutes les données.
        - User (standard ou limité) : accès aux enregistrements où il est responsible_id ou dans support_ids.
        """
        user = request.env.user
        _logger.info(f"Application du filtre de sécurité pour l'utilisateur : {user.name}")
    
        # Vérifier si l'utilisateur est Admin ou Manager
        if user.has_group('workprogramm.workprogramm_group_admin') or user.has_group('workprogramm.workprogramm_group_manager'):
            _logger.info(f"👑 Utilisateur {user.name} (Admin/Manager) - accès à toutes les données")
            return df
    
        # Trouver l'employé associé
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not employee:
            _logger.warning(f"⚠️ Utilisateur {user.name} n'a pas d'employé associé")
            return pd.DataFrame()

        # Utilisateur standard ou limité : accès aux tâches où il est responsible_id ou dans support_ids
        _logger.info(f"👤 Utilisateur {user.name} - accès aux données où il est responsable ou support")
        if 'responsible_id' in df.columns and 'support_ids' in df.columns:
            return df[
                (df['responsible_id'] == employee.id) |
                (df['support_ids'].apply(lambda x: employee.id in x if isinstance(x, list) else False))
            ]
        elif 'responsible_id' in df.columns:
            return df[df['responsible_id'] == employee.id]
        return pd.DataFrame()
    
    @http.route('/dashboard/work_program_projects_count', type='json', auth='user', methods=['POST'], csrf=False)
    def get_work_program_projects_count(self, date_from=None, date_to=None, department_id=None, responsible_id=None, project_id=None):
        """
        Récupère le nombre distinct de projets avec filtres date, département et responsable
        """
        try:
            _logger.info(
                f"Début de get_work_program_projects_count avec filtres: "
                f"date_from={date_from}, date_to={date_to}, dept={department_id}, resp={responsible_id}"
            )

            # Récupération de toutes les tâches
            tasks = request.env['work.program'].sudo().search([])
            _logger.info(f"Trouvé {len(tasks)} tâches au total")

            if not tasks:
                return {'total_projects': 0, 'error': False}

            # Préparation des données
            task_data_list = []
            for task in tasks:
                task_data_list.append({
                    'id': task.id,
                    'assignment_date': task.assignment_date if task.assignment_date else None,
                    'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                    'support_ids': [emp.id for emp in task.support_ids] if task.support_ids else [],
                    'responsible_id': task.responsible_id.id if task.responsible_id else None,
                    'project_id': task.project_id.id if task.project_id else None,
                })

            df = pd.DataFrame(task_data_list)

            if df.empty:
                return {'total_projects': 0, 'error': False}
            
            df = self._apply_security_filter(df)

            # Application des filtres
            filtered_df = self._apply_date_filters(df, date_from, date_to, department_id, responsible_id,project_id)

            if filtered_df.empty:
                _logger.info("Aucune tâche après filtres - retour de 0 projets")
                return {'total_projects': 0, 'error': False}

            # Calcul du nombre distinct de projets
            nb_projets = filtered_df['project_id'].nunique()
            _logger.info(f"Nombre de projets distincts après filtres: {nb_projets}")

            return {
                'total_projects': nb_projets,
                'error': False
            }

        except Exception as e:
            _logger.error(f"Erreur dans get_work_program_projects_count: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'total_projects': 0
            }
            
    @http.route('/dashboard/work_program_count', type='json', auth='user', methods=['POST'], csrf=False)
    def get_work_program_count(self, date_from=None, date_to=None, department_id=None, responsible_id=None,project_id=None):
        """
        Récupère le nombre total de tâches avec filtres date, département et responsable
        """
        try:
            _logger.info(
                f"Début de get_work_program_count avec filtres: "
                f"date_from={date_from}, date_to={date_to}, dept={department_id}, resp={responsible_id}"
            )

            # Récupération de toutes les tâches
            tasks = request.env['work.program'].sudo().search([])
            _logger.info(f"Trouvé {len(tasks)} tâches au total")

            if not tasks:
                return {'total_tasks': 0, 'error': False}

            # Préparation des données
            task_data_list = []
            for task in tasks:
                task_data_list.append({
                    'id': task.id,
                    'assignment_date': task.assignment_date if task.assignment_date else None,
                    'project_id': task.project_id.id if task.project_id else None,
                    'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                    'responsible_id': task.responsible_id.id if task.responsible_id else None,
                    'support_ids': [emp.id for emp in task.support_ids] if task.support_ids else [],
                })

            df = pd.DataFrame(task_data_list)

            if df.empty:
                return {'total_tasks': 0, 'error': False}
            
            df = self._apply_security_filter(df)

            # Application des filtres
            filtered_df = self._apply_date_filters(df, date_from, date_to, department_id, responsible_id,project_id)

            if filtered_df.empty:
                _logger.info("Aucune tâche après filtres - retour de 0 tâches")
                return {'total_tasks': 0, 'error': False}

            # Calcul du nombre total de tâches
            total_tasks = len(filtered_df)
            _logger.info(f"Nombre de tâches après filtres: {total_tasks}")

            return {
                'total_tasks': total_tasks,
                'error': False
            }

        except Exception as e:
            _logger.error(f"Erreur dans get_work_program_count: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'total_tasks': 0
            }
            
    @http.route('/dashboard/work_program_valid', type='json', auth='user', methods=['POST'], csrf=False)
    def get_work_program_valid_count(self, date_from=None, date_to=None, department_id=None, responsible_id=None,project_id=None):
        """
        Récupère le nombre total de tâches validées avec filtres date, département et responsable
        """
        try:
            _logger.info(
                f"Début de get_work_program_count avec filtres: "
                f"date_from={date_from}, date_to={date_to}, dept={department_id}, resp={responsible_id}"
            )

            # Récupération de toutes les tâches
            tasks = request.env['work.program'].sudo().search([])
            _logger.info(f"Trouvé {len(tasks)} tâches au total")

            if not tasks:
                return {'tasks_valid': 0, 'error': False}

            # Préparation des données
            task_data_list = []
            for task in tasks:
                task_data_list.append({
                    'id': task.id,
                    'assignment_date': task.assignment_date if task.assignment_date else None,
                    'project_id': task.project_id.id if task.project_id else None,
                    'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                    'responsible_id': task.responsible_id.id if task.responsible_id else None,
                    'support_ids': [emp.id for emp in task.support_ids] if task.support_ids else [],
                    'state': task.state  # Pour filtrer les tâches validées
                })

            df = pd.DataFrame(task_data_list)

            if df.empty:
                return {'tasks_valid': 0, 'error': False}
            
            df = self._apply_security_filter(df)

            # Filtrage des tâches validées
            df_valid = df[df['state'] == 'validated']

            if df_valid.empty:
                _logger.info("Aucune tâche validée après filtrage")
                return {'tasks_valid': 0, 'error': False}

            # Application des filtres existants
            filtered_df = self._apply_date_filters(df_valid, date_from, date_to, department_id, responsible_id,project_id)

            if filtered_df.empty:
                _logger.info("Aucune tâche validée après filtres supplémentaires")
                return {'tasks_valid': 0, 'error': False}

            # Calcul du nombre total de tâches validées
            tasks_valid = len(filtered_df)
            _logger.info(f"Nombre de tâches validées après filtres: {tasks_valid}")

            return {
                'tasks_valid': tasks_valid,
                'error': False
            }

        except Exception as e:
            _logger.error(f"Erreur dans get_work_program_count: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'tasks_valid': 0
            }
            
    @http.route('/dashboard/work_program_to_validate', type='json', auth='user', methods=['POST'], csrf=False)
    def get_work_program_to_validate_count(self, date_from=None, date_to=None, department_id=None, responsible_id=None,project_id=None):
        """
        Récupère le nombre total de tâches à valider avec filtres date, département et responsable
        """
        try:
            _logger.info(
                f"Début de get_work_program_to_validate_count avec filtres: "
                f"date_from={date_from}, date_to={date_to}, dept={department_id}, resp={responsible_id}"
            )

            # Récupération de toutes les tâches
            tasks = request.env['work.program'].sudo().search([])
            _logger.info(f"Trouvé {len(tasks)} tâches au total")

            if not tasks:
                return {'tasks_to_validate': 0, 'error': False}

            # Préparation des données dans une liste
            task_data_list = []
            for task in tasks:
                task_data_list.append({
                    'id': task.id,
                    'assignment_date': task.assignment_date if task.assignment_date else None,
                    'project_id': task.project_id.id if task.project_id else None,
                    'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                    'support_ids': [emp.id for emp in task.support_ids] if task.support_ids else [],
                    'responsible_id': task.responsible_id.id if task.responsible_id else None,
                    'state': task.state
                })

            df = pd.DataFrame(task_data_list)

            if df.empty:
                return {'tasks_to_validate': 0, 'error': False}
            
            df = self._apply_security_filter(df)

            # 🔹 Filtrage des tâches à valider
            df_to_validate = df[df['state'] == 'to_validate']

            if df_to_validate.empty:
                _logger.info("Aucune tâche à valider après filtrage")
                return {'tasks_to_validate': 0, 'error': False}

            # 🔹 Application des filtres supplémentaires
            filtered_df = self._apply_date_filters(df_to_validate, date_from, date_to, department_id, responsible_id,project_id)

            if filtered_df.empty:
                _logger.info("Aucune tâche à valider après filtres supplémentaires")
                return {'tasks_to_validate': 0, 'error': False}

            # 🔹 Calcul final
            tasks_to_validate = len(filtered_df)
            _logger.info(f"Nombre de tâches à valider après filtres: {tasks_to_validate}")

            return {
                'tasks_to_validate': tasks_to_validate,
                'error': False
            }

        except Exception as e:
            _logger.error(f"Erreur dans get_work_program_to_validate_count: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'tasks_to_validate': 0
            }
            
    @http.route('/dashboard/work_program_complexity_distribution', type='json', auth='user', methods=['POST'], csrf=False)
    def get_work_program_complexity_distribution(self, date_from=None, date_to=None, department_id=None, responsible_id=None,project_id=None):
        """
        Récupère la répartition des tâches par complexité ('low', 'medium', 'high')
        avec les filtres date, département et responsable.
        """
        try:
            _logger.info(
                f"Début de get_work_program_complexity_distribution avec filtres: "
                f"date_from={date_from}, date_to={date_to}, dept={department_id}, resp={responsible_id}"
            )

            # 🔹 Récupération des tâches
            tasks = request.env['work.program'].sudo().search([])
            _logger.info(f"Trouvé {len(tasks)} tâches au total")

            if not tasks:
                return {'complexity_data': {'labels': [], 'values': []}, 'error': False}

            # 🔹 Préparation du DataFrame
            task_data_list = []
            for task in tasks:
                task_data_list.append({
                    'id': task.id,
                    'assignment_date': task.assignment_date if task.assignment_date else None,
                    'project_id': task.project_id.id if task.project_id else None,
                    'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                    'responsible_id': task.responsible_id.id if task.responsible_id else None,
                    'support_ids': [emp.id for emp in task.support_ids] if task.support_ids else [],
                    'complexity': task.complexity,
                })

            df = pd.DataFrame(task_data_list)
            if df.empty:
                return {'complexity_data': {'labels': [], 'values': []}, 'error': False}
            
            df = self._apply_security_filter(df)

            # 🔹 Application des filtres via ta fonction existante
            filtered_df = self._apply_date_filters(df, date_from, date_to, department_id, responsible_id,project_id)
            if filtered_df.empty:
                _logger.info("Aucune tâche après filtres")
                return {'complexity_data': {'labels': [], 'values': []}, 'error': False}

            # 🔹 Ne garder que les valeurs valides
            valid_values = ['low', 'medium', 'high']
            df_valid = filtered_df[filtered_df['complexity'].isin(valid_values)]

            # 🔹 Comptage par complexité
            complexity_counts = df_valid['complexity'].value_counts().reindex(valid_values, fill_value=0)

            complexity_data = {
                'labels': complexity_counts.index.tolist(),
                'values': complexity_counts.values.tolist()
            }

            _logger.info(f"Répartition des complexités: {complexity_data}")

            return {
                'complexity_data': complexity_data,
                'error': False
            }

        except Exception as e:
            _logger.error(f"Erreur dans get_work_program_complexity_distribution: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'complexity_data': {'labels': [], 'values': []}
            }
            
    @http.route('/dashboard/work_program_priority_distribution', type='json', auth='user', methods=['POST'], csrf=False)
    def get_work_program_priority_distribution(self, date_from=None, date_to=None, department_id=None, responsible_id=None,project_id=None):
        """
        Récupère la répartition des tâches par priorité ('low', 'medium', 'high')
        avec filtres date, département et responsable.
        """
        try:
            _logger.info(
                f"Début de get_work_program_priority_distribution avec filtres: "
                f"date_from={date_from}, date_to={date_to}, dept={department_id}, resp={responsible_id}"
            )

            # 🔹 Récupération des tâches
            tasks = request.env['work.program'].sudo().search([])
            _logger.info(f"Trouvé {len(tasks)} tâches au total")

            if not tasks:
                return {'priority_data': {'labels': [], 'values': []}, 'error': False}

            # 🔹 Préparation du DataFrame
            task_data_list = []
            for task in tasks:
                task_data_list.append({
                    'id': task.id,
                    'assignment_date': task.assignment_date if task.assignment_date else None,
                    'project_id': task.project_id.id if task.project_id else None,
                    'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                    'responsible_id': task.responsible_id.id if task.responsible_id else None,
                    'support_ids': [emp.id for emp in task.support_ids] if task.support_ids else [],
                    'priority': task.priority,
                })

            df = pd.DataFrame(task_data_list)
            if df.empty:
                return {'priority_data': {'labels': [], 'values': []}, 'error': False}
            
            df = self._apply_security_filter(df)

            # 🔹 Application des filtres via ta fonction existante
            filtered_df = self._apply_date_filters(df, date_from, date_to, department_id, responsible_id,project_id)
            if filtered_df.empty:
                _logger.info("Aucune tâche après filtres")
                return {'priority_data': {'labels': [], 'values': []}, 'error': False}

            # 🔹 Sélection des valeurs valides
            valid_values = ['low', 'medium', 'high']
            df_valid = filtered_df[filtered_df['priority'].isin(valid_values)]

            # 🔹 Comptage par priorité
            priority_counts = df_valid['priority'].value_counts().reindex(valid_values, fill_value=0)

            priority_data = {
                'labels': priority_counts.index.tolist(),
                'values': priority_counts.values.tolist()
            }

            _logger.info(f"Répartition des priorités: {priority_data}")

            return {
                'priority_data': priority_data,
                'error': False
            }

        except Exception as e:
            _logger.error(f"Erreur dans get_work_program_priority_distribution: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'priority_data': {'labels': [], 'values': []}
            }
            
    @http.route('/dashboard/work_program_state_distribution', type='json', auth='user', methods=['POST'], csrf=False)
    def get_work_program_state_distribution(self, date_from=None, date_to=None, department_id=None, responsible_id=None,project_id=None):
        """
        Récupère la répartition des tâches par état (sauf 'draft') avec filtres date, département et responsable.
        Trié du plus petit au plus grand.
        """
        try:
            _logger.info(
                f"Début de get_work_program_state_distribution avec filtres: "
                f"date_from={date_from}, date_to={date_to}, dept={department_id}, resp={responsible_id}"
            )

            # 🔹 Récupération des tâches
            tasks = request.env['work.program'].sudo().search([])
            _logger.info(f"Trouvé {len(tasks)} tâches au total")

            if not tasks:
                return {'state_data': {'labels': [], 'values': []}, 'error': False}

            # 🔹 Préparation du DataFrame
            task_data_list = []
            for task in tasks:
                task_data_list.append({
                    'id': task.id,
                    'assignment_date': task.assignment_date if task.assignment_date else None,
                    'project_id': task.project_id.id if task.project_id else None,
                    'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                    'responsible_id': task.responsible_id.id if task.responsible_id else None,
                    'support_ids': [emp.id for emp in task.support_ids] if task.support_ids else [],
                    'state': task.state,
                })

            df = pd.DataFrame(task_data_list)
            if df.empty:
                return {'state_data': {'labels': [], 'values': []}, 'error': False}
            
            df = self._apply_security_filter(df)

            # 🔹 Application des filtres
            filtered_df = self._apply_date_filters(df, date_from, date_to, department_id, responsible_id,project_id)
            if filtered_df.empty:
                _logger.info("Aucune tâche après filtres")
                return {'state_data': {'labels': [], 'values': []}, 'error': False}

            # 🔹 États valides et traduction en français
            state_map = {
                'draft':'Brouillon',
                'ongoing': 'En cours',
                'to_validate': 'À valider',
                'validated': 'Validé',
                'refused': 'Refusé',
                'to_redo': 'À refaire',
                'incomplete': 'Inachevé',
                'done': 'Terminé',
                'cancelled': 'Annulé'
            }
            df_valid = filtered_df[filtered_df['state'].isin(state_map.keys())]

            # 🔹 Comptage par état et tri du plus petit au plus grand
            state_counts = df_valid['state'].value_counts().reindex(state_map.keys(), fill_value=0).sort_values()

            state_data = {
                'labels': [state_map[s] for s in state_counts.index.tolist()],
                'values': state_counts.values.tolist()
            }

            _logger.info(f"Répartition des états (triée): {state_data}")

            return {
                'state_data': state_data,
                'error': False
            }

        except Exception as e:
            _logger.error(f"Erreur dans get_work_program_state_distribution: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'state_data': {'labels': [], 'values': []}
            }


    @http.route('/dashboard/work_program_grid', type='json', auth='user', methods=['POST'], csrf=False)
    def get_work_program_grid(self, date_from=None, date_to=None, department_id=None, responsible_id=None,project_id=None):
        """
        Renvoie les données filtrées pour AG Grid :
        - Champs : projet, description, responsable, image, département, dates, état, priorité, complexité
        - Applique les filtres date, département et responsable
        """
        try:
            _logger.info(
                f"Début de get_work_program_grid avec filtres: "
                f"date_from={date_from}, date_to={date_to}, dept={department_id}, resp={responsible_id}"
            )

            # 🔹 Récupération des tâches
            tasks = request.env['work.program'].sudo().search([])
            _logger.info(f"Trouvé {len(tasks)} tâches au total")
            _logger.info(f"Valeurs de state trouvées : {set(task.state for task in tasks)}")
            _logger.info(f"Dates brutes : {[{'id': t.id, 'assignment_date': t.assignment_date, 'initial_deadline': t.initial_deadline, 'actual_deadline': t.actual_deadline} for t in tasks]}")

            if not tasks:
                return {'data': [], 'error': False}

            # 🔹 Préparation du DataFrame
            task_data_list = []
            for task in tasks:
                task_data_list.append({
                    'project': task.project_id.name if task.project_id else 'Non défini',
                    'description': task.inputs_needed or '',
                    'responsible_display': task.responsible_id.name if task.responsible_id else 'Non défini',
                    'responsible_image': f'/web/image/hr.employee/{task.responsible_id.id}/avatar_128' if task.responsible_id else '/web/static/src/img/placeholder.png',
                    'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                    'responsible_id': task.responsible_id.id if task.responsible_id else None,
                    'project_id': task.project_id.id if task.project_id else None,
                    'department_display': task.responsible_id.department_id.name if task.responsible_id and task.responsible_id.department_id else 'Non défini',
                    'assignment_date': task.assignment_date if task.assignment_date else None,
                    'due_date': task.initial_deadline if task.initial_deadline else None,
                    'completion_date': task.actual_deadline if task.actual_deadline else None,
                    'priority': task.priority or 'unknown',
                    'complexity': task.complexity or 'unknown',
                    'support_ids': [emp.id for emp in task.support_ids] if task.support_ids else [],
                    'support_name': ', '.join(task.support_ids.mapped('name')) if task.support_ids else '',
                    'state': task.state or 'unknown'
                })

            df = pd.DataFrame(task_data_list)
            if df.empty:
                _logger.info("DataFrame vide après création")
                return {'data': [], 'error': False}
            
            df = self._apply_security_filter(df)

            # 🔹 Application des filtres
            filtered_df = self._apply_date_filters(df, date_from, date_to, department_id, responsible_id,project_id)
            _logger.info(f"Tâches après filtres : {len(filtered_df)}")
            
             # 🔹 Conversion et tri par date d'assignation (plus récente en premier)
            if 'assignment_date' in filtered_df.columns:
                filtered_df['assignment_date'] = pd.to_datetime(filtered_df['assignment_date'], errors='coerce')
                filtered_df = filtered_df.sort_values(
                    by='assignment_date',
                    ascending=False,
                    na_position='last'
                ).reset_index(drop=True)

            if filtered_df.empty:
                _logger.info("Aucune tâche après filtres")
                return {'data': [], 'error': False}

            # 🔹 Formatage des données pour AG Grid
            grid_data = []
            for _, row in filtered_df.iterrows():
                grid_data.append({
                    'project': row['project'],
                    'description': row['description'],
                    'responsible_display': row['responsible_display'],
                    'responsible_image': row['responsible_image'],
                    'department_display': row['department_display'],
                    'support': row['support_name'],
                    'start_date': self.safe_date_format(row['assignment_date']),
                    'due_date': self.safe_date_format(row['due_date']),
                    'completion_date': self.safe_date_format(row['completion_date']),
                    'priority': row['priority'],
                    'complexity': row['complexity'],
                    'state': row['state']
                })

            _logger.info(f"Données renvoyées à AG Grid après filtres: {len(grid_data)} lignes")

            return {
                'data': grid_data,
                'error': False
            }

        except Exception as e:
            _logger.error(f"Erreur dans get_work_program_grid: {str(e)}", exc_info=True)
            return {
                'data': [],
                'error': True,
                'message': str(e)
            }
            
    def _apply_date_filters(self, df, date_from, date_to, department_id, responsible_id,project_id=None):
        """Applique les filtres de date, département et responsable sur le DataFrame"""
        filtered_df = df.copy()

        # Filtrage par dates basé sur assignment_date
        if date_from or date_to:
            filtered_df['assignment_date'] = pd.to_datetime(filtered_df['assignment_date'], errors='coerce')
            
            if date_from:
                date_from_dt = pd.to_datetime(date_from)
                filtered_df = filtered_df[filtered_df['assignment_date'] >= date_from_dt]
            
            if date_to:
                date_to_dt = pd.to_datetime(date_to)
                filtered_df = filtered_df[filtered_df['assignment_date'] <= date_to_dt]

        # Filtrage par NOM du département (depuis hr.department)
        # ✅ REMPLACER
        # if department_id is not None and department_id != "":
        #     try:
        #         dept_id = int(department_id)
        #         filtered_df = filtered_df[filtered_df['department_id'] == dept_id]
        #     except (ValueError, TypeError):
        #         _logger.warning(f"ID département invalide: {department_id}")
        
        if department_id is not None and department_id != "" and department_id != "null":
            try:
                dept_id = int(department_id)
                _logger.info(f"🔹 Filtre département appliqué: {dept_id}")
                filtered_df = filtered_df[filtered_df['department_id'] == dept_id]
            except (ValueError, TypeError):
                _logger.warning(f"ID département invalide: {department_id}")
        else:
            # ✅ CRUCIAL : Quand department_id est None, on ne filtre PAS
            # Le DataFrame contient déjà toutes les données sans filtre département
            _logger.info("🔹 Aucun filtre département appliqué (tous les départements)")

        # Filtrage par responsable ou support
        if responsible_id is not None and responsible_id != "":
            responsible_id = int(responsible_id)
            filtered_df = filtered_df[
                (filtered_df['responsible_id'] == responsible_id) |
                (filtered_df['support_ids'].apply(lambda x: responsible_id in x if isinstance(x, list) else False))
            ]
        

        return filtered_df

    def safe_date_format(self, value):
        """Formate les dates pour l'affichage"""
        import datetime
        if value is None or value == '' or (isinstance(value, float) and pd.isna(value)):
            return ''
        if isinstance(value, bool):
            return ''
        if isinstance(value, (datetime.date, datetime.datetime)):
            return value.strftime('%Y-%m-%d')
        return str(value)