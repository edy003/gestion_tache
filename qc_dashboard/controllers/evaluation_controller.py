# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

class WorkProgramDashboardController(http.Controller):
    
   
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

    @http.route('/dashboard/work_program_deadline_compliance', type='json', auth='user', methods=['POST'], csrf=False)
    def get_work_program_deadline_compliance(self, year=None, month=None, department_id=None, responsible_id=None):
        """
        Récupère le pourcentage de respect des délais des tâches supposées terminées
        """
        try:
            _logger.info(f"Début avec filtres: year={year}, month={month}, dept={department_id}, resp={responsible_id}")

            current_compliance = self._calculate_deadline_compliance_for_period(year, month, department_id, responsible_id)
            evolution_data = None

            if year and month:
                evolution_data = self._calculate_evolution(year, month, department_id, responsible_id, current_compliance)

            return {
                'deadline_compliance': current_compliance,
                'evolution': evolution_data,
                'error': False
            }

        except Exception as e:
            _logger.error(f"Erreur dans get_work_program_deadline_compliance: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'deadline_compliance': '--',
                'evolution': None
            }


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
            
    def _calculate_deadline_compliance_for_period(self, year, month, department_id, responsible_id):
        """Calcule le pourcentage de tâches terminées à temps parmi les tâches supposées terminées"""
        tasks = request.env['work.program'].sudo().search([])

        if not tasks:
            return '--'

        task_data_list = []
        for task in tasks:
            task_year = None
            task_month = None

            if task.assignment_date:
                try:
                    assignment_date = datetime.strptime(str(task.assignment_date), '%Y-%m-%d')
                    task_year = assignment_date.year
                    task_month = self._get_month_name(assignment_date.month)
                except (ValueError, TypeError):
                    _logger.warning(f"Format assignment_date invalide pour tâche {task.id}: {task.assignment_date}")
                    continue

            # 🔹 Récupérer les IDs des supports pour cette tâche
            support_ids = [employee.id for employee in task.support_ids] if task.support_ids else []

            task_data_list.append({
                'id': task.id,
                'year': task_year,
                'month': task_month,
                'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                'responsible_id': task.responsible_id.id if task.responsible_id else None,
                'support_ids': support_ids,  # 🔹 Liste des IDs des supports
                'initial_deadline': task.initial_deadline,
                'actual_deadline': task.actual_deadline,
                'state': task.state,
            })

        df = pd.DataFrame(task_data_list)
        if df.empty:
            return '--'
        # 🔹 Appliquer le filtre de sécurité
        df = self._apply_security_filter(df)
        if df.empty:
            return '--'

        # 🔹 Filtrage de base
        filtered_df = self._apply_filters_with_support(df, year, month, department_id, responsible_id)
        if filtered_df.empty:
            return '--'

        # 🔹 Conversion des dates
        filtered_df['initial_deadline'] = pd.to_datetime(filtered_df['initial_deadline'], errors='coerce')
        filtered_df['actual_deadline'] = pd.to_datetime(filtered_df['actual_deadline'], errors='coerce')

        today = pd.Timestamp.today()

        # 🔹 Tâches supposées être terminées à ce jour
        tasks_supposed_done = filtered_df[filtered_df['initial_deadline'].notna() & (filtered_df['initial_deadline'] <= today)]
        if tasks_supposed_done.empty:
            return '--'

        tasks_supposed_done = tasks_supposed_done.copy()
        # 🔹 Tâches terminées à temps : actual_deadline <= initial_deadline, actual_deadline non nul, et état 'validated' ou 'done'
        tasks_supposed_done['is_completed'] = tasks_supposed_done['actual_deadline'].notna()
        tasks_supposed_done['done_on_time'] = (
            tasks_supposed_done['is_completed'] &
            (tasks_supposed_done['actual_deadline'] <= tasks_supposed_done['initial_deadline']) &
            tasks_supposed_done['state'].isin(['validated', 'done'])
        )

        total_tasks = len(tasks_supposed_done)
        done_on_time = tasks_supposed_done['done_on_time'].sum()

        if total_tasks == 0:
            return '--'

        respect_delais = (done_on_time / total_tasks) * 100
        return round(respect_delais, 2)
    
    def _calculate_evolution(self, current_year, current_month, department_id, responsible_id, current_kpi):
        """Calcule l'évolution par rapport au mois précédent."""
        try:
            current_month_num = self._get_month_number(current_month)
            if current_month_num is None:
                return None

            current_date = datetime(int(current_year), current_month_num, 1)
            previous_date = current_date - relativedelta(months=1)

            previous_year = previous_date.year
            previous_month = self._get_month_name(previous_date.month)

            previous_kpi = self._calculate_deadline_compliance_for_period(
                previous_year, previous_month, department_id, responsible_id
            )

            if current_kpi == '--' or previous_kpi == '--':
                return {
                    'previous_kpi': previous_kpi,
                    'evolution_value': None,
                    'evolution_percentage': None,
                    'trend': 'neutral',
                    'display': '--',
                    'previous_period': f"{previous_month} {previous_year}"
                }

            evolution_value = current_kpi - previous_kpi
            evolution_percentage = None if previous_kpi == 0 else (evolution_value / previous_kpi) * 100

            if evolution_value > 0:
                trend = 'up'
                display = f"+{evolution_value:.1f}%"
            elif evolution_value < 0:
                trend = 'down'
                display = f"{evolution_value:.1f}%"
            else:
                trend = 'neutral'
                display = "0.0%"

            return {
                'previous_kpi': previous_kpi,
                'evolution_value': round(evolution_value, 1),
                'evolution_percentage': round(evolution_percentage, 1) if evolution_percentage is not None else None,
                'trend': trend,
                'display': display,
                'previous_period': f"{previous_month} {previous_year}"
            }

        except Exception as e:
            _logger.error(f"Erreur calcul évolution: {str(e)}", exc_info=True)
            return None

    @http.route('/dashboard/work_program_satisfaction_rate', type='json', auth='user', methods=['POST'], csrf=False)
    def get_work_program_satisfaction_rate(self, year=None, month=None, department_id=None, responsible_id=None):
        """
        Récupère le pourcentage de tâches avec satisfaction élevée (et terminées à temps)
        """
        try:
            _logger.info(f"Début satisfaction avec filtres: year={year}, month={month}, dept={department_id}, resp={responsible_id}")

            current_satisfaction = self._calculate_satisfaction_rate_for_period(year, month, department_id, responsible_id)
            
            evolution_data = None
            if year and month:
                evolution_data = self._calculate_satisfaction_evolution(year, month, department_id, responsible_id, current_satisfaction)

            return {
                'satisfaction_rate': current_satisfaction,
                'evolution': evolution_data,
                'error': False
            }

        except Exception as e:
            _logger.error(f"Erreur dans get_work_program_satisfaction_rate: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'satisfaction_rate': '--',
                'evolution': None
            }

    def _calculate_satisfaction_rate_for_period(self, year, month, department_id, responsible_id):
        """Calcule le taux de satisfaction élevé pour les tâches terminées à temps (état validé ou done)."""
        tasks = request.env['work.program'].sudo().search([])
        if not tasks:
            return '--'

        task_data_list = []
        for task in tasks:
            satisfaction = task.satisfaction_level
            if not satisfaction or satisfaction not in ['low', 'medium', 'high']:
                continue

            # Extraire les infos temporelles
            task_year = None
            task_month = None
            if task.assignment_date:
                try:
                    assignment_date = datetime.strptime(str(task.assignment_date), '%Y-%m-%d')
                    task_year = assignment_date.year
                    task_month = self._get_month_name(assignment_date.month)
                except Exception:
                    continue

            task_data_list.append({
                'id': task.id,
                'year': task_year,
                'month': task_month,
                'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                'responsible_id': task.responsible_id.id if task.responsible_id else None,
                'satisfaction_level': satisfaction,
                'initial_deadline': task.initial_deadline,
                'actual_deadline': task.actual_deadline,
                'state': task.state,
            })

        df = pd.DataFrame(task_data_list)
        if df.empty:
            return '--'
        
        # 🔹 Appliquer le filtre de sécurité
        df = self._apply_security_filter(df)
        if df.empty:
            return '--'

        # 🔹 Filtrage de base
        filtered_df = self._apply_filters(df, year, month, department_id, responsible_id)
        if filtered_df.empty:
            return '--'

        # 🔹 Conversion des dates
        filtered_df['initial_deadline'] = pd.to_datetime(filtered_df['initial_deadline'], errors='coerce')
        filtered_df['actual_deadline'] = pd.to_datetime(filtered_df['actual_deadline'], errors='coerce')

        today = pd.Timestamp.today()

        # 🔹 Tâches supposées être terminées à ce jour
        tasks_supposed_done = filtered_df[filtered_df['initial_deadline'].notna() & (filtered_df['initial_deadline'] <= today)]
        if tasks_supposed_done.empty:
            return '--'

        tasks_supposed_done = tasks_supposed_done.copy()
        # 🔹 Tâches terminées à temps : actual_deadline <= initial_deadline, actual_deadline non nul, état 'validated' ou 'done'
        tasks_supposed_done['is_completed'] = tasks_supposed_done['actual_deadline'].notna()
        tasks_supposed_done['done_on_time'] = (
            tasks_supposed_done['is_completed'] &
            (tasks_supposed_done['actual_deadline'] <= tasks_supposed_done['initial_deadline']) &
            tasks_supposed_done['state'].isin(['validated', 'done'])
        )

        # 🔹 Calcul du taux de satisfaction élevé parmi les tâches terminées à temps
        total_tasks = len(tasks_supposed_done)
        high_count = (tasks_supposed_done['done_on_time'] & (tasks_supposed_done['satisfaction_level'] == 'high')).sum()

        if total_tasks == 0:
            return '--'

        percentage_high = (high_count / total_tasks) * 100
        return round(percentage_high, 2)

    def _calculate_satisfaction_evolution(self, current_year, current_month, department_id, responsible_id, current_kpi):
        """Calcule l'évolution du taux de satisfaction par rapport au mois précédent."""
        from dateutil.relativedelta import relativedelta
        try:
            current_month_num = self._get_month_number(current_month)
            if current_month_num is None:
                return None

            current_date = datetime(int(current_year), current_month_num, 1)
            previous_date = current_date - relativedelta(months=1)

            previous_year = previous_date.year
            previous_month = self._get_month_name(previous_date.month)

            previous_kpi = self._calculate_satisfaction_rate_for_period(
                previous_year, previous_month, department_id, responsible_id
            )

            if current_kpi == '--' or previous_kpi == '--':
                return {
                    'previous_kpi': previous_kpi,
                    'evolution_value': None,
                    'evolution_percentage': None,
                    'trend': 'neutral',
                    'display': '--',
                    'previous_period': f"{previous_month} {previous_year}"
                }

            evolution_value = current_kpi - previous_kpi
            evolution_percentage = None if previous_kpi == 0 else (evolution_value / previous_kpi) * 100

            if evolution_value > 0:
                trend = 'up'
                display = f"+{evolution_value:.1f}%"
            elif evolution_value < 0:
                trend = 'down'
                display = f"{evolution_value:.1f}%"
            else:
                trend = 'neutral'
                display = "0.0%"

            return {
                'previous_kpi': previous_kpi,
                'evolution_value': round(evolution_value, 1),
                'evolution_percentage': round(evolution_percentage, 1) if evolution_percentage is not None else None,
                'trend': trend,
                'display': display,
                'previous_period': f"{previous_month} {previous_year}"
            }

        except Exception as e:
            _logger.error(f"Erreur calcul évolution satisfaction: {str(e)}", exc_info=True)
            return None


    @http.route('/dashboard/work_program_complex_resolution', type='json', auth='user', methods=['POST'], csrf=False)
    def get_work_program_complex_resolution(self, year=None, month=None, department_id=None, responsible_id=None):
        """
        Récupère le pourcentage de respect des délais pour les tâches complexes (état validé ou done)
        """
        try:
            _logger.info(f"Début complex resolution avec filtres: year={year}, month={month}, dept={department_id}, resp={responsible_id}")

            current_complex = self._calculate_complex_resolution_for_period(year, month, department_id, responsible_id)
            
            evolution_data = None
            if year and month:
                evolution_data = self._calculate_complex_evolution(year, month, department_id, responsible_id, current_complex)

            return {
                'complex_resolution': current_complex,
                'evolution': evolution_data,
                'error': False
            }

        except Exception as e:
            _logger.error(f"Erreur dans get_work_program_complex_resolution: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'complex_resolution': '--',
                'evolution': None
            }

    def _calculate_complex_resolution_for_period(self, year, month, department_id, responsible_id):
        """Calcule le respect des délais pour les tâches complexes validées ou terminées."""
        tasks = request.env['work.program'].sudo().search([])
        if not tasks:
            return '--'

        task_data_list = []
        for task in tasks:
            if not hasattr(task, 'complexity') or not task.complexity:
                continue

            task_year, task_month = None, None
            if task.assignment_date:
                try:
                    assignment_date = datetime.strptime(str(task.assignment_date), '%Y-%m-%d')
                    task_year = assignment_date.year
                    task_month = self._get_month_name(assignment_date.month)
                except Exception:
                    continue

            task_data_list.append({
                'id': task.id,
                'year': task_year,
                'month': task_month,
                'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                'responsible_id': task.responsible_id.id if task.responsible_id else None,
                'complexity': task.complexity,
                'initial_deadline': task.initial_deadline,
                'actual_deadline': task.actual_deadline,
                'state': task.state,
            })

        df = pd.DataFrame(task_data_list)
        if df.empty:
            return '--'
        
        # 🔹 Appliquer le filtre de sécurité
        df = self._apply_security_filter(df)
        if df.empty:
            return '--'

        # Appliquer les filtres Odoo -> pandas
        filtered_df = self._apply_filters(df, year, month, department_id, responsible_id)
        if filtered_df.empty:
            return '--'

        # Conversion des dates
        filtered_df['initial_deadline'] = pd.to_datetime(filtered_df['initial_deadline'], errors='coerce')
        filtered_df['actual_deadline'] = pd.to_datetime(filtered_df['actual_deadline'], errors='coerce')

        today = pd.Timestamp.today()

        # 1️⃣ Ne garder que les tâches complexes avec complexité "high"
        filtered_df = filtered_df[filtered_df['complexity'] == 'high']
        if filtered_df.empty:
            return '--'

        # 2️⃣ Tâches supposées être terminées à ce jour
        tasks_supposed_done = filtered_df[filtered_df['initial_deadline'].notna() & (filtered_df['initial_deadline'] <= today)]
        if tasks_supposed_done.empty:
            return '--'

        tasks_supposed_done = tasks_supposed_done.copy()
        # 3️⃣ Tâches terminées à temps : actual_deadline <= initial_deadline, actual_deadline non nul, état 'validated' ou 'done'
        tasks_supposed_done['is_completed'] = tasks_supposed_done['actual_deadline'].notna()
        tasks_supposed_done['done_on_time'] = (
            tasks_supposed_done['is_completed'] &
            (tasks_supposed_done['actual_deadline'] <= tasks_supposed_done['initial_deadline']) &
            tasks_supposed_done['state'].isin(['validated', 'done'])
        )

        # 4️⃣ Calcul du respect des délais
        total_tasks = len(tasks_supposed_done)
        done_on_time = tasks_supposed_done['done_on_time'].sum()

        if total_tasks == 0:
            return '--'

        respect_delais = (done_on_time / total_tasks) * 100
        return round(respect_delais, 2)

    def _calculate_complex_evolution(self, current_year, current_month, department_id, responsible_id, current_kpi):
        """Calcule l'évolution du respect des délais pour les tâches complexes par rapport au mois précédent."""
        try:
            current_month_num = self._get_month_number(current_month)
            if current_month_num is None:
                return None
                
            current_date = datetime(int(current_year), current_month_num, 1)
            previous_date = current_date - relativedelta(months=1)
            
            previous_year = previous_date.year
            previous_month = self._get_month_name(previous_date.month)
            
            previous_kpi = self._calculate_complex_resolution_for_period(
                previous_year, previous_month, department_id, responsible_id
            )
            
            if current_kpi == '--' or previous_kpi == '--':
                return {
                    'previous_kpi': previous_kpi,
                    'evolution_value': None,
                    'evolution_percentage': None,
                    'trend': 'neutral',
                    'display': '--',
                    'previous_period': f"{previous_month} {previous_year}"
                }
            
            evolution_value = current_kpi - previous_kpi
            evolution_percentage = None if previous_kpi == 0 else (evolution_value / previous_kpi) * 100
            
            if evolution_value > 0:
                trend = 'up'
                display = f"+{evolution_value:.1f}%"
            elif evolution_value < 0:
                trend = 'down'
                display = f"{evolution_value:.1f}%"
            else:
                trend = 'neutral'
                display = "0.0%"
            
            return {
                'previous_kpi': previous_kpi,
                'evolution_value': round(evolution_value, 1),
                'evolution_percentage': round(evolution_percentage, 1) if evolution_percentage is not None else None,
                'trend': trend,
                'display': display,
                'previous_period': f"{previous_month} {previous_year}"
            }
            
        except Exception as e:
            _logger.error(f"Erreur calcul évolution complexe: {str(e)}", exc_info=True)
            return None

    @http.route('/dashboard/work_program_priority_resolution', type='json', auth='user', methods=['POST'], csrf=False)
    def get_work_program_priority_resolution(self, year=None, month=None, department_id=None, responsible_id=None):
        """
        Récupère le pourcentage de respect des délais pour les tâches prioritaires (état validé ou done) avec évolution
        """
        try:
            _logger.info(f"Début priority resolution avec filtres: year={year}, month={month}, dept={department_id}, resp={responsible_id}")

            # Calcul du KPI actuel
            current_priority = self._calculate_priority_resolution_for_period(year, month, department_id, responsible_id)

            # Calcul de l'évolution si on a un mois et une année
            evolution_data = None
            if year and month:
                evolution_data = self._calculate_priority_evolution(year, month, department_id, responsible_id, current_priority)

            return {
                'priority_resolution': current_priority,
                'evolution': evolution_data,
                'error': False
            }

        except Exception as e:
            _logger.error(f"Erreur dans get_work_program_priority_resolution: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'priority_resolution': '--',
                'evolution': None
            }

    def _calculate_priority_resolution_for_period(self, year, month, department_id, responsible_id):
        """Calcule le respect des délais pour les tâches prioritaires (état validé ou done)."""
        tasks = request.env['work.program'].sudo().search([])
        if not tasks:
            return '--'

        task_data_list = []
        for task in tasks:
            if not hasattr(task, 'priority') or not task.priority:
                continue

            task_year, task_month = None, None
            if task.assignment_date:
                try:
                    assignment_date = datetime.strptime(str(task.assignment_date), '%Y-%m-%d')
                    task_year = assignment_date.year
                    task_month = self._get_month_name(assignment_date.month)
                except Exception:
                    continue

            task_data_list.append({
                'id': task.id,
                'year': task_year,
                'month': task_month,
                'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                'responsible_id': task.responsible_id.id if task.responsible_id else None,
                'priority': task.priority,
                'initial_deadline': task.initial_deadline,
                'actual_deadline': task.actual_deadline,
                'state': task.state,
            })

        df = pd.DataFrame(task_data_list)
        if df.empty:
            return '--'
        # 🔹 Appliquer le filtre de sécurité
        df = self._apply_security_filter(df)
        if df.empty:
            return '--'

        # Application des filtres
        filtered_df = self._apply_filters(df, year, month, department_id, responsible_id)
        if filtered_df.empty:
            return '--'

        # Conversion des dates
        filtered_df['initial_deadline'] = pd.to_datetime(filtered_df['initial_deadline'], errors='coerce')
        filtered_df['actual_deadline'] = pd.to_datetime(filtered_df['actual_deadline'], errors='coerce')

        today = pd.Timestamp.today()

        # 1️⃣ Filtrer uniquement les tâches prioritaires avec priorité "high"
        filtered_df = filtered_df[filtered_df['priority'] == 'high']
        if filtered_df.empty:
            _logger.info("Aucune tâche prioritaire trouvée après filtres")
            return '--'

        # 2️⃣ Tâches supposées être terminées à ce jour
        tasks_supposed_done = filtered_df[filtered_df['initial_deadline'].notna() & (filtered_df['initial_deadline'] <= today)]
        if tasks_supposed_done.empty:
            return '--'

        tasks_supposed_done = tasks_supposed_done.copy()
        # 3️⃣ Tâches terminées à temps : actual_deadline <= initial_deadline, actual_deadline non nul, état 'validated' ou 'done'
        tasks_supposed_done['is_completed'] = tasks_supposed_done['actual_deadline'].notna()
        tasks_supposed_done['done_on_time'] = (
            tasks_supposed_done['is_completed'] &
            (tasks_supposed_done['actual_deadline'] <= tasks_supposed_done['initial_deadline']) &
            tasks_supposed_done['state'].isin(['validated', 'done'])
        )

        # 4️⃣ Calcul du respect des délais
        total_tasks = len(tasks_supposed_done)
        done_on_time = tasks_supposed_done['done_on_time'].sum()

        if total_tasks == 0:
            return '--'

        respect_delais = (done_on_time / total_tasks) * 100
        _logger.info(f"Respect des délais (tâches prioritaires validées/done): {respect_delais}")
        return round(respect_delais, 2)

    def _calculate_priority_evolution(self, current_year, current_month, department_id, responsible_id, current_kpi):
        """Calcule l'évolution du respect des délais pour les tâches prioritaires par rapport au mois précédent."""
        try:
            current_month_num = self._get_month_number(current_month)
            if current_month_num is None:
                return None

            current_date = datetime(int(current_year), current_month_num, 1)
            previous_date = current_date - relativedelta(months=1)

            previous_year = previous_date.year
            previous_month = self._get_month_name(previous_date.month)

            previous_kpi = self._calculate_priority_resolution_for_period(
                previous_year, previous_month, department_id, responsible_id
            )

            if current_kpi == '--' or previous_kpi == '--':
                return {
                    'previous_kpi': previous_kpi,
                    'evolution_value': None,
                    'evolution_percentage': None,
                    'trend': 'neutral',
                    'display': '--',
                    'previous_period': f"{previous_month} {previous_year}"
                }

            evolution_value = current_kpi - previous_kpi
            evolution_percentage = None if previous_kpi == 0 else (evolution_value / previous_kpi) * 100

            if evolution_value > 0:
                trend = 'up'
                display = f"+{evolution_value:.1f}%"
            elif evolution_value < 0:
                trend = 'down'
                display = f"{evolution_value:.1f}%"
            else:
                trend = 'neutral'
                display = "0.0%"

            return {
                'previous_kpi': previous_kpi,
                'evolution_value': round(evolution_value, 1),
                'evolution_percentage': round(evolution_percentage, 1) if evolution_percentage is not None else None,
                'trend': trend,
                'display': display,
                'previous_period': f"{previous_month} {previous_year}"
            }

        except Exception as e:
            _logger.error(f"Erreur calcul évolution prioritaire: {str(e)}", exc_info=True)
            return None

    @http.route('/dashboard/work_program_priority_deadline_chart', type='json', auth='user', methods=['POST'], csrf=False)
    def get_work_program_priority_deadline_chart(self, year=None, month=None, department_id=None, responsible_id=None):
        """
        Récupère les données pour le pie chart du respect des délais par priorité.
        Seules les tâches 'validated' ou 'done' sont considérées comme complétées.
        """
        try:
            _logger.info(
                f"📊 Début priority deadline chart avec filtres: "
                f"year={year}, month={month}, dept={department_id}, resp={responsible_id}"
            )

            # 🔹 Récupération des tâches
            tasks = request.env['work.program'].sudo().search([])
            if not tasks:
                return self._empty_chart_response()

            # 🔹 Transformation en liste de dictionnaires
            task_data_list = []
            for task in tasks:
                if not hasattr(task, 'priority') or not task.priority:
                    continue

                # Extraire année et mois
                task_year, task_month = None, None
                if task.assignment_date:
                    try:
                        assignment_date = datetime.strptime(str(task.assignment_date), '%Y-%m-%d')
                        task_year = assignment_date.year
                        task_month = self._get_month_name(assignment_date.month)
                    except Exception:
                        _logger.warning(f"⚠️ Format assignment_date invalide pour tâche {task.id}")
                        continue

                task_data_list.append({
                    'id': task.id,
                    'state': task.state,
                    'year': task_year,
                    'month': task_month,
                    'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                    'responsible_id': task.responsible_id.id if task.responsible_id else None,
                    'priority': task.priority,
                    'initial_deadline': task.initial_deadline,
                    'actual_deadline': task.actual_deadline,
                })

            df = pd.DataFrame(task_data_list)
            if df.empty:
                return self._empty_chart_response()
            # 🔹 Appliquer le filtre de sécurité
            df = self._apply_security_filter(df)
            if df.empty:
                return '--'

            # 🔹 Application des filtres
            filtered_df = self._apply_filters(df, year, month, department_id, responsible_id)
            if filtered_df.empty:
                return self._empty_chart_response()

            # 🔹 Conversion des dates
            filtered_df['initial_deadline'] = pd.to_datetime(filtered_df['initial_deadline'], errors='coerce')
            filtered_df['actual_deadline'] = pd.to_datetime(filtered_df['actual_deadline'], errors='coerce')

            today = pd.Timestamp.today()
            valid_priorities = ['low', 'medium', 'high']
            labels, values, task_counts = [], [], []

            # 🔹 Calcul du respect des délais par priorité
            for prio in valid_priorities:
                tasks_priority = filtered_df[filtered_df['priority'] == prio]
                if tasks_priority.empty:
                    continue

                tasks_supposed_done = tasks_priority[
                    tasks_priority['initial_deadline'].notna() &
                    (tasks_priority['initial_deadline'] <= today)
                ].copy()

                if tasks_supposed_done.empty:
                    continue

                tasks_supposed_done['is_completed'] = tasks_supposed_done['actual_deadline'].notna()
                tasks_supposed_done['done_on_time'] = (
                    tasks_supposed_done['is_completed'] &
                    (tasks_supposed_done['actual_deadline'] <= tasks_supposed_done['initial_deadline']) &
                    (tasks_supposed_done['state'].isin(['validated', 'done']))  # ✅ mêmes contraintes que complexité
                )

                total_tasks = len(tasks_supposed_done)
                done_on_time = tasks_supposed_done['done_on_time'].sum()

                if total_tasks > 0 and done_on_time > 0: 
                    percent_done = round((done_on_time / total_tasks) * 100, 2)

                    priority_names = {
                        'low': 'Priorité Faible',
                        'medium': 'Priorité Moyenne',
                        'high': 'Priorité Élevée'
                    }

                    labels.append(priority_names.get(prio, prio.title()))
                    values.append(percent_done)
                    task_counts.append(int(done_on_time))

            return {
                'chart_data': {
                    'labels': labels,
                    'values': values,
                    'task_counts': task_counts
                },
                'error': False
            }

        except Exception as e:
            _logger.error(f"❌ Erreur dans get_work_program_priority_deadline_chart: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'chart_data': {'labels': [], 'values': [], 'task_counts': []}
            } 
    

    @http.route('/dashboard/work_program_complexity_deadline_chart',type='json',auth='user',methods=['POST'],csrf=False)
    def get_work_program_complexity_deadline_chart(self, year=None, month=None, department_id=None, responsible_id=None):
        """
        Récupère les données pour le pie chart du respect des délais par complexité
        (seules les tâches 'validated' ou 'done' sont considérées terminées à temps)
        """
        try:
            _logger.info(
                f"Début complexity deadline chart avec filtres: year={year}, month={month}, dept={department_id}, resp={responsible_id}"
            )

            # 🔹 Récupération des tâches
            tasks = request.env['work.program'].sudo().search([])

            if not tasks:
                return self._empty_chart_response()

            # 🔹 Transformation en liste de dicts
            task_data_list = []
            for task in tasks:
                if not hasattr(task, 'complexity') or not task.complexity:
                    continue

                task_year = None
                task_month = None

                if task.assignment_date:
                    try:
                        assignment_date = datetime.strptime(str(task.assignment_date), '%Y-%m-%d')
                        task_year = assignment_date.year
                        task_month = self._get_month_name(assignment_date.month)
                    except (ValueError, TypeError):
                        _logger.warning(
                            f"Format assignment_date invalide pour tâche {task.id}: {task.assignment_date}"
                        )
                        continue

                task_data_list.append({
                    'id': task.id,
                    'state': task.state,
                    'year': task_year,
                    'month': task_month,
                    'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                    'responsible_id': task.responsible_id.id if task.responsible_id else None,
                    'complexity': task.complexity,
                    'initial_deadline': task.initial_deadline,
                    'actual_deadline': task.actual_deadline,
                })

            df = pd.DataFrame(task_data_list)
            if df.empty:
                return self._empty_chart_response()
            
            # 🔹 Appliquer le filtre de sécurité
            df = self._apply_security_filter(df)
            if df.empty:
                return '--'

            # 🔹 Application des filtres
            filtered_df = self._apply_filters(df, year, month, department_id, responsible_id)
            if filtered_df.empty:
                return self._empty_chart_response()

            # Conversion des dates
            filtered_df['initial_deadline'] = pd.to_datetime(filtered_df['initial_deadline'], errors='coerce')
            filtered_df['actual_deadline'] = pd.to_datetime(filtered_df['actual_deadline'], errors='coerce')

            today = pd.Timestamp.today()
            valid_complexities = ['low', 'medium', 'high']
            labels, values, task_counts = [], [], []

            # 🔹 Calcul du respect des délais par complexité
            for complexity in valid_complexities:
                tasks_complexity = filtered_df[filtered_df['complexity'] == complexity]
                if tasks_complexity.empty:
                    continue

                tasks_supposed_done = tasks_complexity[
                    tasks_complexity['initial_deadline'].notna() &
                    (tasks_complexity['initial_deadline'] <= today)
                ].copy()

                if tasks_supposed_done.empty:
                    continue

                tasks_supposed_done['is_completed'] = tasks_supposed_done['actual_deadline'].notna()
                tasks_supposed_done['done_on_time'] = (
                    tasks_supposed_done['is_completed'] &
                    (tasks_supposed_done['actual_deadline'] <= tasks_supposed_done['initial_deadline']) &
                    (tasks_supposed_done['state'].isin(['validated', 'done']))  # ✅ filtre ajouté ici
                )

                total_tasks = len(tasks_supposed_done)
                done_on_time = tasks_supposed_done['done_on_time'].sum()

                if total_tasks > 0 and done_on_time > 0:
                    percent_done = round((done_on_time / total_tasks) * 100, 2)

                    complexity_names = {
                        'low': 'Complexité Faible',
                        'medium': 'Complexité Moyenne',
                        'high': 'Complexité Élevée'
                    }

                    labels.append(complexity_names.get(complexity, complexity.title()))
                    values.append(percent_done)
                    task_counts.append(int(done_on_time))

            return {
                'chart_data': {
                    'labels': labels,
                    'values': values,
                    'task_counts': task_counts
                },
                'error': False
            }

        except Exception as e:
            _logger.error(f"Erreur dans get_work_program_complexity_deadline_chart: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'chart_data': {'labels': [], 'values': [], 'task_counts': []}
            }
    
    @http.route('/dashboard/work_program_monthly_deadline_chart', type='json', auth='user', methods=['POST'], csrf=False)
    def get_work_program_monthly_deadline_chart(self, year=None, month=None, department_id=None, responsible_id=None):
        """
        Récupère les données pour le bar chart du respect des délais par mois d'assignation.
        Seules les tâches terminées ('validated' ou 'done') et dans les délais sont considérées "done on time".
        Les tâches en retard sont les tâches supposées être terminées moins celles terminées dans les délais.
        """
        try:
            _logger.info(f"Début monthly deadline chart avec filtres: year={year}, month={month}, dept={department_id}, resp={responsible_id}")

            # Récupération des tâches
            tasks = request.env['work.program'].sudo().search([])
            if not tasks:
                return {
                    'chart_data': {'months': [], 'pct_on_time': [], 'pct_late': [], 'count_on_time': [], 'count_late': []},
                    'error': False
                }

            # Collecte des données brutes
            task_data_list = []
            for task in tasks:
                if not task.assignment_date:
                    continue

                try:
                    assignment_date = datetime.strptime(str(task.assignment_date), '%Y-%m-%d')
                except (ValueError, TypeError):
                    _logger.warning(f"Format assignment_date invalide pour tâche {task.id}: {task.assignment_date}")
                    continue

                task_data_list.append({
                    'id': task.id,
                    'state': task.state,
                    'year': assignment_date.year,
                    'month': self._get_month_name(assignment_date.month),
                    'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                    'responsible_id': task.responsible_id.id if task.responsible_id else None,
                    'initial_deadline': task.initial_deadline,
                    'actual_deadline': task.actual_deadline,
                    'assignment_date': task.assignment_date,
                })

            # Création du DataFrame
            df = pd.DataFrame(task_data_list)
            if df.empty:
                return {
                    'chart_data': {'months': [], 'pct_on_time': [], 'pct_late': [], 'count_on_time': [], 'count_late': []},
                    'error': False
                }
            # 🔹 Appliquer le filtre de sécurité
            df = self._apply_security_filter(df)
            if df.empty:
                return '--'

            # Application des filtres
            filtered_df = self._apply_filters(df, year, month, department_id, responsible_id)
            if filtered_df.empty:
                return {
                    'chart_data': {'months': [], 'pct_on_time': [], 'pct_late': [], 'count_on_time': [], 'count_late': []},
                    'error': False
                }

            # Conversion des dates
            for col in ['initial_deadline', 'actual_deadline', 'assignment_date']:
                filtered_df[col] = pd.to_datetime(filtered_df[col], errors='coerce')

            today = pd.Timestamp.today()

            # Tâches censées être terminées
            tasks_supposed_done = filtered_df[
                filtered_df['initial_deadline'].notna() &
                (filtered_df['initial_deadline'] <= today)
            ].copy()

            if tasks_supposed_done.empty:
                return {
                    'chart_data': {'months': [], 'pct_on_time': [], 'pct_late': [], 'count_on_time': [], 'count_late': []},
                    'error': False
                }

            # Respect des délais (avec contrainte sur l’état)
            tasks_supposed_done['is_completed'] = tasks_supposed_done['actual_deadline'].notna()
            tasks_supposed_done['done_on_time'] = (
                tasks_supposed_done['is_completed'] &
                (tasks_supposed_done['actual_deadline'] <= tasks_supposed_done['initial_deadline']) &
                (tasks_supposed_done['state'].isin(['validated', 'done']))
            )

            # Tâches en retard : tâches supposées terminées moins celles terminées dans les délais
            tasks_supposed_done['is_late'] = (~tasks_supposed_done['done_on_time'])

            # Regroupement par mois
            tasks_supposed_done['assign_period'] = tasks_supposed_done['assignment_date'].dt.to_period('M')
            monthly_stats = tasks_supposed_done.groupby('assign_period').agg(
                total_tasks=('done_on_time', 'size'),
                count_on_time=('done_on_time', 'sum'),
                count_late=('is_late', 'sum')
            ).reset_index()

            monthly_stats['pct_on_time'] = (monthly_stats['count_on_time'] / monthly_stats['total_tasks'] * 100).round(2)
            monthly_stats['pct_late'] = (monthly_stats['count_late'] / monthly_stats['total_tasks'] * 100).round(2)

            # Formatage pour affichage
            def period_to_display(period):
                try:
                    year, month_num = str(period).split('-')
                    month_name = self._get_month_name(int(month_num))
                    return f"{month_name} {year}"
                except:
                    return str(period)

            monthly_stats['display_period'] = monthly_stats['assign_period'].apply(period_to_display)
            monthly_stats = monthly_stats.sort_values('assign_period')

            # Retour des données
            return {
                'chart_data': {
                    'months': monthly_stats['display_period'].tolist(),
                    'pct_on_time': monthly_stats['pct_on_time'].tolist(),
                    'pct_late': monthly_stats['pct_late'].tolist(),
                    'count_on_time': monthly_stats['count_on_time'].astype(int).tolist(),
                    'count_late': monthly_stats['count_late'].astype(int).tolist()
                },
                'error': False
            }

        except Exception as e:
            _logger.error(f"Erreur dans get_work_program_monthly_deadline_chart: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'chart_data': {'months': [], 'pct_on_time': [], 'pct_late': [], 'count_on_time': [], 'count_late': []}
            }
            
    @http.route('/dashboard/employee_performance', type='json', auth='user', methods=['POST'], csrf=False)
    def get_employee_performance(self, year=None, month=None, department_id=None, responsible_id=None):
        """
        Récupère soit les données d'un employé spécifique, soit la performance globale
        """
        try:
            if responsible_id:
                return self._get_specific_employee_data(responsible_id, year, month, department_id)
            else:
                return self._get_global_performance_data(year, month, department_id)
        except Exception as e:
            _logger.error(f"Erreur dans get_employee_performance: {str(e)}", exc_info=True)
            return {
                'error': True,
                'message': str(e),
                'display_name': 'Erreur',
                'department_name': 'Erreur',
                'profile_image': None,
                'category': 'Erreur',
                'score': 0
            }

    def _get_specific_employee_data(self, responsible_id, year, month, department_id):
        """Retourne les données d'un employé spécifique avec SA catégorie ET son score"""
        employee = request.env['hr.employee'].sudo().browse(int(responsible_id))
        if not employee.exists():
            return {
                'error': True,
                'message': 'Employé non trouvé',
                'score': 0
            }
        
        result = self._calculate_employee_category(responsible_id, year, month, department_id)
        
        if isinstance(result, tuple):
            category, score = result
        else:
            category = result
            score = 0
        
        return {
            'error': False,
            'display_name': employee.name,
            'department_name': employee.department_id.name if employee.department_id else 'Non assigné',
            'profile_image': employee.image_1920 if employee.image_1920 else None,
            'category': category,
            'score': round(score, 2),
            'is_global': False
        }

    def _get_global_performance_data(self, year, month, department_id):
        """Retourne les données globales avec catégorie ET score de l'ensemble"""
        result = self._calculate_global_category(year, month, department_id)
        
        if isinstance(result, tuple):
            category, score = result
        else:
            category = result
            score = 0
        
        return {
            'error': False,
            'display_name': 'Tous les employés',
            'department_name': 'Tous les départements',
            'profile_image': None,
            'category': category,
            'score': round(score, 2),
            'is_global': True
        }

    def _calculate_employee_category(self, responsible_id, year=None, month=None, department_id=None):
        """Calcule la catégorie ET le score d'UN employé spécifique"""
        try:
            employee_id = int(responsible_id)
            tasks = request.env['work.program'].sudo().search([])
            
            if not tasks:
                return ('Aucune donnée', 0)
            task_data_list = []
            for task in tasks:
                task_year = None
                task_month = None
            
                if task.assignment_date:
                    try:
                        assignment_date = datetime.strptime(str(task.assignment_date), '%Y-%m-%d')
                        task_year = assignment_date.year
                        task_month = self._get_month_name(assignment_date.month)
                    except (ValueError, TypeError):
                        continue
            
                support_ids = [emp.id for emp in task.support_ids] if task.support_ids else []
                
                task_data_list.append({
                    'year': task_year,
                    'month': task_month,
                    'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                    'responsible_id': task.responsible_id.id if task.responsible_id else None,
                    'support_ids': support_ids,
                    'initial_deadline': task.initial_deadline,
                    'actual_deadline': task.actual_deadline,
                    'satisfaction_level': task.satisfaction_level,
                    'complexity': task.complexity,
                    'priority': task.priority,
                    'state': task.state,
                })
            df = pd.DataFrame(task_data_list)
            if df.empty:
                return ('Aucune donnée', 0)
        
            df = df[
                (df['responsible_id'] == employee_id) |
                (df['support_ids'].apply(lambda x: employee_id in x if isinstance(x, list) else False))
            ]
        
            if df.empty:
                return ('Aucune donnée', 0)
            filtered_df = self._apply_filtersk(df, year, month, department_id, None)
            if filtered_df.empty:
                return ('Aucune donnée', 0)
            return self._apply_categorization_algorithm_with_support(filtered_df, employee_id)
        
        except Exception as e:
            _logger.error(f"Erreur calcul catégorie employé: {str(e)}")
            return ('Erreur', 0)

    def _calculate_global_category(self, year=None, month=None, department_id=None):
        """Calcule la catégorie ET le score globaux"""
        try:
            _logger.info("=" * 60)
            _logger.info("CALCUL GLOBAL DÉMARRÉ")
            _logger.info(f"Filtres: year={year}, month={month}, dept={department_id}")
            
            tasks = request.env['work.program'].sudo().search([])
            
            if not tasks:
                return ('Aucune donnée', 0)
            task_data_list = []
            for task in tasks:
                task_year = None
                task_month = None
                
                if task.assignment_date:
                    try:
                        assignment_date = datetime.strptime(str(task.assignment_date), '%Y-%m-%d')
                        task_year = assignment_date.year
                        task_month = self._get_month_name(assignment_date.month)
                    except (ValueError, TypeError):
                        continue
                support_ids = [emp.id for emp in task.support_ids] if task.support_ids else []
                task_data_list.append({
                    'year': task_year,
                    'month': task_month,
                    'department_id': task.responsible_id.department_id.id if task.responsible_id and task.responsible_id.department_id else None,
                    'responsible_id': task.responsible_id.id if task.responsible_id else None,
                    'support_ids': support_ids,
                    'initial_deadline': task.initial_deadline,
                    'actual_deadline': task.actual_deadline,
                    'satisfaction_level': task.satisfaction_level,
                    'complexity': task.complexity,
                    'priority': task.priority,
                    'state': task.state,
                })
            df = pd.DataFrame(task_data_list)
            if df.empty:
                return ('Aucune donnée', 0)
            filtered_df = self._apply_filtersk(df, year, month, department_id, None)
            if filtered_df.empty:
                _logger.warning("DataFrame vide après filtrage")
                return ('Aucune donnée', 0)
            _logger.info(f"Tâches après filtrage: {len(filtered_df)}")
            
            result = self._apply_categorization_algorithm_global_with_support(filtered_df)
            _logger.info(f"Résultat: {result}")
            _logger.info("=" * 60)
            
            return result
            
        except Exception as e:
            _logger.error(f"Erreur calcul global: {str(e)}", exc_info=True)
            return ('Erreur', 0)

    def _apply_categorization_algorithm_with_support(self, filtered_df, employee_id):
        """Algorithme avec support - Retourne (catégorie, score)"""
        try:
            if filtered_df.empty:
                return ('Aucune donnée', 0)
                
            df = filtered_df.copy()
            df['initial_deadline'] = pd.to_datetime(df['initial_deadline'], errors='coerce')
            df['actual_deadline'] = pd.to_datetime(df['actual_deadline'], errors='coerce')
            today = pd.Timestamp.today()
            
            tasks_supposed_done = df[
                df['initial_deadline'].notna() &
                (df['initial_deadline'] <= today)
            ].copy()
            
            if tasks_supposed_done.empty:
                return ('Aucune tâche évaluable', 0)
            
            tasks_supposed_done['is_responsible'] = (tasks_supposed_done['responsible_id'] == employee_id)
            tasks_supposed_done['is_support'] = tasks_supposed_done['support_ids'].apply(
                lambda x: employee_id in x if isinstance(x, list) else False
            )
            
            tasks_supposed_done['is_completed'] = tasks_supposed_done['actual_deadline'].notna()
            tasks_supposed_done['done_on_time'] = (
                tasks_supposed_done['is_completed'] &
                (tasks_supposed_done['actual_deadline'] <= tasks_supposed_done['initial_deadline']) &
                tasks_supposed_done['state'].isin(['validated', 'done'])
            )
            
            # Responsable
            tasks_as_responsible = tasks_supposed_done[tasks_supposed_done['is_responsible']]
            pct_done_as_responsible = 0
            if len(tasks_as_responsible) > 0:
                pct_done_as_responsible = (tasks_as_responsible['done_on_time'].sum() / len(tasks_as_responsible)) * 100
            
            # Support
            tasks_as_support = tasks_supposed_done[tasks_supposed_done['is_support'] & ~tasks_supposed_done['is_responsible']]
            pct_done_as_support = 0
            if len(tasks_as_support) > 0:
                pct_done_as_support = (tasks_as_support['done_on_time'].sum() / len(tasks_as_support)) * 100
            
            # Mapping
            score_map = {'low': 1, 'medium': 2, 'high': 3}
            
            tasks_supposed_done['satisfaction_score'] = tasks_supposed_done['satisfaction_level'].map(score_map)
            tasks_supposed_done['complexity_score'] = tasks_supposed_done['complexity'].map(score_map)
            tasks_supposed_done['priority_score'] = tasks_supposed_done['priority'].map(score_map)
            
            tasks_supposed_done['satisfaction_norm'] = ((tasks_supposed_done['satisfaction_score'] - 1) / 2) * 100
            tasks_supposed_done['complexity_norm'] = (tasks_supposed_done['complexity_score'] / 3) * 100
            tasks_supposed_done['priority_norm'] = (tasks_supposed_done['priority_score'] / 3) * 100
            
            avg_satisfaction_norm = tasks_supposed_done['satisfaction_norm'].mean()
            avg_complexity_norm = tasks_supposed_done['complexity_norm'].mean()
            avg_priority_norm = tasks_supposed_done['priority_norm'].mean()
            
            # Remplacer NaN par 0
            avg_satisfaction_norm = 0 if pd.isna(avg_satisfaction_norm) else avg_satisfaction_norm
            avg_complexity_norm = 0 if pd.isna(avg_complexity_norm) else avg_complexity_norm
            avg_priority_norm = 0 if pd.isna(avg_priority_norm) else avg_priority_norm
            
            score = (
                pct_done_as_responsible * 0.35 +
                pct_done_as_support * 0.25 +
                avg_satisfaction_norm * 0.20 +
                avg_complexity_norm * 0.10 +
                avg_priority_norm * 0.10
            )
            
            if pd.isna(score):
                return ('Erreur', 0)
            
            _logger.info(f"Employé {employee_id} - Score: {score:.2f}")
            
            if score < 60:
                category = 'À risque'
            elif score < 75:
                category = 'Satisfaisant'
            elif score < 90:
                category = 'Performant'
            else:
                category = 'Haut potentiel'
            
            return (category, round(float(score), 2))
            
        except Exception as e:
            _logger.error(f"Erreur algorithme employé {employee_id}: {str(e)}", exc_info=True)
            return ('Erreur', 0)

    def _apply_categorization_algorithm_global_with_support(self, filtered_df):
        """Calcul global - Retourne (catégorie, score)"""
        try:
            if filtered_df.empty:
                return ('Aucune donnée', 0)
            
            all_employee_ids = set()
            
            for _, row in filtered_df.iterrows():
                if pd.notna(row['responsible_id']):
                    all_employee_ids.add(int(row['responsible_id']))
                if isinstance(row['support_ids'], list):
                    all_employee_ids.update(row['support_ids'])
            
            if not all_employee_ids:
                return ('Aucune donnée', 0)
            
            _logger.info(f"Calcul pour {len(all_employee_ids)} employés")
            
            employee_scores = []
            
            for emp_id in all_employee_ids:
                emp_df = filtered_df[
                    (filtered_df['responsible_id'] == emp_id) |
                    (filtered_df['support_ids'].apply(
                        lambda x: emp_id in x if isinstance(x, list) else False
                    ))
                ].copy()
                
                if not emp_df.empty:
                    try:
                        result = self._apply_categorization_algorithm_with_support(emp_df, emp_id)
                        
                        if isinstance(result, tuple) and len(result) == 2:
                            category, score = result
                        else:
                            continue
                        
                        invalid_cats = ['Aucune donnée', 'Aucune tâche évaluable', 'Erreur']
                        
                        if category not in invalid_cats and isinstance(score, (int, float)) and score > 0:
                            employee_scores.append(score)
                            _logger.info(f"✓ Emp {emp_id}: {category} ({score:.2f})")
                            
                    except Exception as e:
                        _logger.error(f"✗ Erreur emp {emp_id}: {str(e)}")
                        continue
            
            if not employee_scores:
                _logger.warning("Aucun score valide")
                return ('Aucune donnée', 0)
            
            average_global_score = sum(employee_scores) / len(employee_scores)
            
            _logger.info(f"Score moyen: {average_global_score:.2f} ({len(employee_scores)}/{len(all_employee_ids)} employés)")
            
            # Catégorisation basée sur le score moyen
            if average_global_score < 60:
                category = 'À risque'
            elif average_global_score < 75:
                category = 'Satisfaisant'
            elif average_global_score < 90:
                category = 'Performant'
            else:
                category = 'Haut potentiel'
            
            _logger.info(f"Catégorie globale finale: {category}")
            
            # ✅ TOUJOURS retourner un tuple (catégorie, score)
            return (category, round(float(average_global_score), 2))
            
        except Exception as e:
            _logger.error(f"Erreur calcul global: {str(e)}", exc_info=True)
            return ('Erreur', 0)

    # def _apply_filters1(self, df, year, month, department_id, employee_id):
    #     """Applique les filtres sur le DataFrame"""
    #     filtered_df = df.copy()
    #     if year:
    #         filtered_df = filtered_df[filtered_df['year'] == int(year)]
    #     if month:
    #         filtered_df = filtered_df[filtered_df['month'] == month]
    #     if department_id:
    #         filtered_df = filtered_df[filtered_df['department_id'] == int(department_id)]
    #     if employee_id:
    #         filtered_df = filtered_df[
    #             (filtered_df['responsible_id'] == int(employee_id)) |
    #             (filtered_df['support_ids'].apply(lambda x: int(employee_id) in x if isinstance(x, list) else False))
    #         ]
    #     return filtered_df

    def _get_month_name(self, month_number):
        """Retourne le nom du mois à partir de son numéro"""
        months = {
            1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
            7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
        }
        return months.get(month_number, '')
    


    # ===== FONCTIONS UTILITAIRES =====
    
    def _get_month_number(self, month_name):
        """Convertit le nom du mois en numéro"""
        if not month_name:
            return None
            
        months = {
            'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4,
            'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8,
            'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12,
            # Versions anglaises au cas où
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        return months.get(month_name.lower())
    
    def _get_month_name(self, month_number):
        """Convertit le numéro du mois en nom"""
        months = {
            1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril',
            5: 'mai', 6: 'juin', 7: 'juillet', 8: 'août',
            9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre'
        }
        return months.get(month_number, 'janvier')

    def _apply_filtersk(self, df, year, month, department_id, responsible_id):
        """Applique les filtres sur le DataFrame"""
        filtered_df = df.copy()
    
        try:
            if year is not None:
                year = int(year)
                filtered_df = filtered_df[filtered_df['year'] == year]
    
            if month:
                filtered_df = filtered_df[filtered_df['month'] == month]
    
            if department_id:
                department_id = int(department_id)
                filtered_df = filtered_df[filtered_df['department_id'] == department_id]
    
            if responsible_id:
                responsible_id = int(responsible_id)
                # Filtrer par responsable OU support
                if 'support_ids' in filtered_df.columns:
                    filtered_df = filtered_df[
                        (filtered_df['responsible_id'] == responsible_id) |
                        (filtered_df['support_ids'].apply(
                            lambda x: responsible_id in x if isinstance(x, list) else False
                        ))
                    ]
                else:
                    filtered_df = filtered_df[filtered_df['responsible_id'] == responsible_id]
    
            return filtered_df
    
        except Exception as e:
            _logger.error(f"Erreur dans _apply_filters: {str(e)}")
            return df



    

    
    
    def _get_month_number(self, month_name):
        """Convertit le nom du mois en numéro"""
        if not month_name:
            return None
            
        months = {
            'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4,
            'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8,
            'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12,
            # Versions anglaises au cas où
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        return months.get(month_name.lower())
    
    def _get_month_name(self, month_number):
        """Convertit le numéro du mois en nom"""
        months = {
            1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril',
            5: 'mai', 6: 'juin', 7: 'juillet', 8: 'août',
            9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre'
        }
        return months.get(month_number, 'janvier')


    def _apply_filters(self, df, year, month, department_id, responsible_id):
        """Applique les filtres sur le DataFrame"""
        filtered_df = df.copy()
    
        try:
            if year is not None:
                year = int(year)
                filtered_df = filtered_df[filtered_df['year'] == year]
    
            if month:
                filtered_df = filtered_df[filtered_df['month'] == month]
    
            if department_id:
                department_id = int(department_id)
                filtered_df = filtered_df[filtered_df['department_id'] == department_id]
    
            if responsible_id:
                responsible_id = int(responsible_id)
                filtered_df = filtered_df[filtered_df['responsible_id'] == responsible_id]
    
            return filtered_df
    
        except Exception as e:
            _logger.error(f"Erreur dans _apply_filters: {str(e)}")
            return df
        
    def _apply_filters_with_support(self, df, year, month, department_id, responsible_id):
        """Applique les filtres sur le DataFrame - AVEC support pour deadline_compliance"""
        filtered_df = df.copy()

        try:
            if year is not None:
                year = int(year)
                filtered_df = filtered_df[filtered_df['year'] == year]
    
            if month:
                filtered_df = filtered_df[filtered_df['month'] == month]

            if department_id:
                department_id = int(department_id)
                filtered_df = filtered_df[filtered_df['department_id'] == department_id]

            # 🔹 CORRECTION : Filtrage par responsible_id qui inclut les supports ET le responsable
            if responsible_id:
                responsible_id = int(responsible_id)
                # Vérifier si la colonne support_ids existe
                if 'support_ids' in filtered_df.columns:
                    # ✅ MODIFICATION ICI : Garder les tâches où l'employé est responsable OU support
                    filtered_df = filtered_df[
                        (filtered_df['responsible_id'] == responsible_id) |  # ← AJOUT DE CETTE LIGNE
                        (filtered_df['support_ids'].apply(
                            lambda x: responsible_id in x if isinstance(x, list) else False
                        ))
                    ]
                else:
                    # Fallback : si pas de support_ids, filtrer uniquement sur responsible_id
                    filtered_df = filtered_df[filtered_df['responsible_id'] == responsible_id]
    
            return filtered_df

        except Exception as e:
            _logger.error(f"Erreur dans _apply_filters_with_support: {str(e)}")
            return df
        



