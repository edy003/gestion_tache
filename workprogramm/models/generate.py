
# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta
import random
from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WorkProgramDataGenerator(models.Model):
    _name = 'work.program.data.generator'
    _description = 'Générateur de données pour Work Programs'

    @api.model
    def generate_work_programs(self, months_past=6, months_future=6, programs_per_month=5):
        """
        Point d'entrée principal pour générer les WorkPrograms
        
        :param months_past: Nombre de mois dans le passé (défaut: 6)
        :param months_future: Nombre de mois dans le futur (défaut: 6)
        :param programs_per_month: Nombre de programmes par mois et par département (défaut: 5)
        """
        _logger.info("=== DÉBUT GÉNÉRATION WORK PROGRAMS ===")
        
        try:
            # Validation des prérequis
            if not self._validate_prerequisites():
                raise UserError("Données de base manquantes. Vérifiez les départements, employés, projets et workflows.")
            
            # Récupération des données de base
            base_data = self._get_base_data()
            
            # Génération des programmes
            programs_created = self._generate_programs_for_period(
                base_data, 
                months_past, 
                months_future, 
                programs_per_month
            )
            
            self.env.cr.commit()
            
            _logger.info(f"=== GÉNÉRATION TERMINÉE: {programs_created} programmes créés ===")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Succès',
                    'message': f'{programs_created} programmes de travail générés avec succès !',
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"ERREUR GÉNÉRATION: {e}", exc_info=True)
            self.env.cr.rollback()
            raise UserError(f"Erreur lors de la génération: {str(e)}")

    @api.model
    def _validate_prerequisites(self):
        """Vérifie que toutes les données nécessaires existent"""
        validations = {
            'hr.department': "Aucun département trouvé",
            'hr.employee': "Aucun employé trouvé",
            'project.project': "Aucun projet trouvé",
            'workflow.activity': "Aucune activité workflow trouvée",
        }
        
        for model, error_msg in validations.items():
            if not self.env[model].search_count([]):
                _logger.error(error_msg)
                return False
        
        # Vérifier spécifiquement les départements Support Technique et Conseil en Stratégie
        support_dept = self.env['hr.department'].search([('name', '=', 'Support Technique')], limit=1)
        conseil_dept = self.env['hr.department'].search([('name', '=', 'Conseil en Stratégie')], limit=1)
        
        if not support_dept or not conseil_dept:
            _logger.error("Départements 'Support Technique' et/ou 'Conseil en Stratégie' manquants")
            return False
        
        return True

    @api.model
    def _get_base_data(self):
        """Récupère et organise toutes les données nécessaires"""
        
        # Départements par type (internal/external)
        internal_depts = self.env['hr.department'].search([('dpt_type', '=', 'internal')])
        external_depts = self.env['hr.department'].search([('dpt_type', '=', 'external')])
        
        # Prendre le premier de chaque type
        internal_dept = internal_depts[0] if internal_depts else False
        external_dept = external_depts[0] if external_depts else False
        
        # Employés par département
        all_employees = self.env['hr.employee'].search([])
        internal_employees = [emp for emp in all_employees if emp.department_id.dpt_type == 'internal']
        external_employees = [emp for emp in all_employees if emp.department_id.dpt_type == 'external']
        
        # Projets
        projects = self.env['project.project'].search([])
        
        # Activités par domaine
        all_activities = self.env['workflow.activity'].search([])
        internal_activities = []
        external_activities = []
        
        for activity in all_activities:
            activity_name = activity.name or ''
            # Activités INTERNES: contiennent PS4 ou PR5
            if 'PS4' in activity_name or 'PR5' in activity_name:
                internal_activities.append(activity)
            # Activités EXTERNES: contiennent PR1 ou PR2
            elif 'PR1' in activity_name or 'PR2' in activity_name:
                external_activities.append(activity)
        
        _logger.info(f"Données chargées: {len(internal_employees)} employés internes, "
                    f"{len(external_employees)} employés externes, "
                    f"{len(projects)} projets, "
                    f"{len(internal_activities)} activités internes, "
                    f"{len(external_activities)} activités externes")
        
        return {
            'internal_dept': internal_dept,
            'external_dept': external_dept,
            'internal_employees': internal_employees,
            'external_employees': external_employees,
            'projects': projects,
            'internal_activities': internal_activities,
            'external_activities': external_activities,
        }

    @api.model
    def _generate_programs_for_period(self, base_data, months_past, months_future, programs_per_month):
        """Génère les programmes pour toute la période"""
        
        WorkProgram = self.env['work.program']
        programs_created = 0
        
        # Date de référence: 1er septembre 2024
        base_date = datetime(2025, 10, 10)
        
        # Générer pour chaque mois
        for month_offset in range(-months_past, months_future + 1):
            month_start, month_end = self._calculate_month_boundaries(base_date, month_offset)
            
            # Programmes pour départements internes
            if base_data['internal_dept'] and base_data['internal_employees'] and base_data['internal_activities']:
                for _ in range(programs_per_month):
                    program_data = self._generate_single_program(
                        base_data['internal_employees'],
                        base_data['projects'],
                        base_data['internal_activities'],
                        base_data['internal_dept'],
                        month_start,
                        month_end
                    )
                    
                    if program_data:
                        try:
                            WorkProgram.create(program_data)
                            programs_created += 1
                        except Exception as e:
                            _logger.error(f"Erreur création programme interne: {e}")
            
            # Programmes pour départements externes
            if base_data['external_dept'] and base_data['external_employees'] and base_data['external_activities']:
                for _ in range(programs_per_month):
                    program_data = self._generate_single_program(
                        base_data['external_employees'],
                        base_data['projects'],
                        base_data['external_activities'],
                        base_data['external_dept'],
                        month_start,
                        month_end
                    )
                    
                    if program_data:
                        try:
                            WorkProgram.create(program_data)
                            programs_created += 1
                        except Exception as e:
                            _logger.error(f"Erreur création programme externe: {e}")
        
        return programs_created

    @api.model
    def _calculate_month_boundaries(self, base_date, month_offset):
        """Calcule les dates de début et fin d'un mois"""
        year = base_date.year
        month = base_date.month + month_offset
        
        # Ajuster année si nécessaire
        while month <= 0:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        
        month_start = datetime(year, month, 1)
        
        # Calculer le dernier jour du mois
        if month == 12:
            next_month_start = datetime(year + 1, 1, 1)
        else:
            next_month_start = datetime(year, month + 1, 1)
        
        month_end = next_month_start - timedelta(days=1)
        
        return month_start, month_end

    @api.model
    def _generate_single_program(self, employees, projects, activities, department, month_start, month_end):
        """Génère un programme de travail individuel"""
        
        try:
            # Sélections aléatoires
            employee = random.choice(employees)
            project = random.choice(projects)
            activity = random.choice(activities)
            
            # Date d'assignation dans le mois
            day = random.randint(1, month_end.day)
            assignment_date = datetime(month_start.year, month_start.month, day)
            
            # Construire les données complètes
            return self._build_program_data(
                employee, 
                project, 
                activity, 
                department, 
                assignment_date
            )
            
        except Exception as e:
            _logger.error(f"Erreur génération programme: {e}")
            return None

    @api.model
    def _build_program_data(self, employee, project, activity, department, assignment_date):
        """Construit toutes les données d'un programme de travail"""
        
        # === CALCULS TEMPORELS ===
        initial_deadline = assignment_date + timedelta(days=random.randint(7, 28))
        
        # État réaliste selon ancienneté
        state = self._get_state_by_age(assignment_date)
        
        # Reports possibles pour états avancés
        nb_postpones = 0
        actual_deadline = initial_deadline
        
        if state in ['ongoing', 'to_validate', 'validated', 'to_redo', 'done'] and random.random() < 0.35:
            nb_postpones = random.randint(1, 3)
            actual_deadline = initial_deadline + timedelta(days=nb_postpones * random.randint(3, 7))
        
        # === MÉTRIQUES SELON ÉTAT ===
        completion_percentage = self._get_completion_by_state(state)
        satisfaction_level = self._get_satisfaction_by_state(state)
        comments = self._generate_comments(state, activity.name, department.name)
        
        # === RELATIONS WORKFLOW (utilise la hiérarchie existante) ===
        procedure = self.env['workflow.procedure'].search([('activity_id', '=', activity.id)], limit=1)
        
        task_description = False
        if procedure:
            task_description = self.env['workflow.task.formulation'].search(
                [('procedure_id', '=', procedure.id)], 
                limit=1
            )
        
        # Livrables (1 à 3 max)
        deliverables = self.env['workflow.deliverable'].search([('activity_id', '=', activity.id)])
        deliverable_ids = False
        if deliverables:
            nb_deliverables = random.randint(1, min(3, len(deliverables)))
            selected_deliverables = random.sample(deliverables.ids, nb_deliverables)
            deliverable_ids = [(6, 0, selected_deliverables)]
        
        # === COLLABORATEURS SUPPORT ===
        dept_type = department.dpt_type
        support_pool = self.env['hr.employee'].search([
            ('department_id.dpt_type', '=', dept_type),
            ('id', '!=', employee.id)
        ])
        
        support_ids = False
        if support_pool:
            # Entre 0 et 3 collaborateurs support
            nb_support = random.randint(0, min(3, len(support_pool)))
            if nb_support > 0:
                selected_support = random.sample(support_pool.ids, nb_support)
                support_ids = [(6, 0, selected_support)]
        
        # === INPUTS ET DESCRIPTIONS ===
        inputs_needed = self._generate_inputs(activity.name, department.name)
        
        # === EFFORT SELON DÉPARTEMENT ===
        if department.name == 'Support':
            base_effort = random.choice([4, 8, 12, 16, 24, 32])
        else:  # Consulting
            base_effort = random.choice([8, 16, 24, 32, 40, 56, 72])
        
        duration_effort = base_effort + random.randint(-4, 8)
        
        # === NOM DU PROGRAMME ===
        month_name = self._get_month_name(assignment_date)
        week_number = assignment_date.isocalendar()[1]
        monday_str = self._get_monday_str(assignment_date)
        
        program_name = (f"{department.name[:3].upper()}-"
                       f"{project.name[:12]}-"
                       f"{activity.name[:20]}-"
                       f"S{week_number:02d}")
        
        # === CONSTRUCTION DU DICTIONNAIRE FINAL ===
        return {
            'name': program_name,
            'my_month': month_name,
            'week_of': week_number,
            'my_week_of': monday_str,
            
            # Relations
            'project_id': project.id,
            'activity_id': activity.id,
            'procedure_id': procedure.id if procedure else False,
            'task_description_id': task_description.id if task_description else False,
            'deliverable_ids': deliverable_ids,
            'support_ids': support_ids,
            'work_programm_department_id': department.id,
            'responsible_id': employee.id,
            
            # Caractéristiques
            'priority': random.choice(['low', 'medium', 'high']),
            'complexity': random.choice(['low', 'medium', 'high']),
            'duration_effort': duration_effort,
            
            # Dates
            'assignment_date': assignment_date.date(),
            'initial_deadline': initial_deadline.date(),
            'actual_deadline': actual_deadline.date(),
            'nb_postpones': nb_postpones,
            
            # État et progression
            'state': state,
            'completion_percentage': completion_percentage,
            'satisfaction_level': satisfaction_level,
            
            # Descriptions
            'inputs_needed': inputs_needed,
            'comments': comments,
            
            # Champs externes (si applicable)
            'champ1': f"Données {department.name}" if department.dpt_type == 'external' else '',
            'champ2': f"Contexte mission {activity.name[:30]}" if department.dpt_type == 'external' else '',
        }

    # =========================================================================
    # MÉTHODES DE GÉNÉRATION INTELLIGENTE
    # =========================================================================

    @api.model
    def _get_state_by_age(self, assignment_date):
        """Détermine un état réaliste selon l'ancienneté de la tâche"""
        today = datetime.now().date()
        days_ago = (today - assignment_date.date()).days
        
        if days_ago < 0:  # Futur
            return 'draft'
        elif days_ago <= 2:
            return random.choices(['draft', 'ongoing'], weights=[30, 70])[0]
        elif days_ago <= 5:
            return random.choices(['draft', 'ongoing', 'to_validate'], weights=[10, 75, 15])[0]
        elif days_ago <= 10:
            return random.choices(
                ['ongoing', 'to_validate', 'validated', 'to_redo'],
                weights=[55, 25, 15, 5]
            )[0]
        elif days_ago <= 15:
            return random.choices(
                ['ongoing', 'to_validate', 'validated', 'refused', 'to_redo', 'done'],
                weights=[30, 20, 15, 8, 12, 15]
            )[0]
        elif days_ago <= 25:
            return random.choices(
                ['to_validate', 'validated', 'refused', 'to_redo', 'incomplete', 'done', 'cancelled'],
                weights=[12, 18, 5, 10, 10, 40, 5]
            )[0]
        elif days_ago <= 40:
            return random.choices(
                ['validated', 'to_redo', 'incomplete', 'done', 'cancelled'],
                weights=[15, 5, 10, 65, 5]
            )[0]
        else:  # Ancien (40+ jours)
            return random.choices(
                ['validated', 'incomplete', 'done', 'cancelled'],
                weights=[10, 8, 75, 7]
            )[0]

    @api.model
    def _get_completion_by_state(self, state):
        """Pourcentage de complétion selon l'état"""
        completion_map = {
            'draft': random.randint(0, 10),
            'ongoing': random.randint(20, 80),
            'to_validate': random.randint(85, 99),
            'validated': 100,
            'refused': random.randint(70, 95),
            'to_redo': random.randint(50, 85),
            'incomplete': random.randint(30, 75),
            'done': 100,
            'cancelled': random.randint(5, 60)
        }
        return completion_map.get(state, 50)

    @api.model
    def _get_satisfaction_by_state(self, state):
        """Niveau de satisfaction selon l'état"""
        if state in ['draft', 'ongoing', 'to_validate']:
            return False
        elif state == 'done':
            return random.choices(['high', 'medium', 'low'], weights=[70, 25, 5])[0]
        elif state == 'validated':
            return random.choices(['high', 'medium', 'low'], weights=[60, 30, 10])[0]
        elif state in ['refused', 'to_redo']:
            return random.choices(['low', 'medium', 'high'], weights=[60, 30, 10])[0]
        elif state == 'incomplete':
            return random.choices(['low', 'medium'], weights=[65, 35])[0]
        else:  # cancelled
            return random.choice([False, 'low'])

    @api.model
    def _generate_comments(self, state, activity_name, dept_name):
        """Génère des commentaires contextuels"""
        
        comments_templates = {
            'draft': [
                "Programme planifié - En attente de démarrage",
                "Nouvellement créé - Ressources à allouer",
                "Initialisé - Briefing prévu prochainement"
            ],
            'ongoing': [
                f"Travail en cours sur {activity_name[:40]}",
                "Progression selon planning établi",
                "Avancement satisfaisant avec quelques ajustements mineurs",
                "Coordination active avec les parties prenantes"
            ],
            'to_validate': [
                "Livrable finalisé - En attente de validation hiérarchique",
                "Travail terminé - Soumis pour revue qualité",
                "Prêt pour validation formelle du responsable",
                "Documentation complétée - Approbation requise"
            ],
            'validated': [
                "Validé avec succès par le responsable",
                "Conformité confirmée - Tâche clôturée",
                "Validation obtenue - Standards respectés",
                "Approuvé formellement - Mission accomplie"
            ],
            'refused': [
                "Validation refusée - Corrections majeures nécessaires",
                "Non-conformité détectée - Reprise complète demandée",
                "Standards non atteints - Réajustements requis",
                "Refus motivé - Nouvelle soumission attendue"
            ],
            'to_redo': [
                "À reprendre suite feedbacks - Ajustements ciblés",
                "Corrections mineures à apporter avant revalidation",
                "Quelques points à revoir selon remarques",
                "Reprise partielle nécessaire"
            ],
            'incomplete': [
                "Travail suspendu - Attente informations complémentaires",
                "Bloqué par dépendance externe non résolue",
                "En pause temporaire - Réaffectation priorités",
                "Ressources manquantes pour finalisation"
            ],
            'done': [
                "Terminé avec succès - Objectifs atteints",
                f"Mission accomplie pour {dept_name}",
                "Clôturé satisfaisant - Livrable opérationnel",
                "Finalisé conformément aux attentes"
            ],
            'cancelled': [
                "Annulé suite changement stratégique",
                "Programme abandonné - Contexte modifié",
                "Annulation décidée par la direction",
                "Plus nécessaire suite réorganisation"
            ]
        }
        
        templates = comments_templates.get(state, ["Programme en cours"])
        return random.choice(templates)

    @api.model
    def _generate_inputs(self, activity_name, dept_name):
        """Génère des inputs réalistes selon l'activité"""
        
        support_inputs = {
            'PS4.1_A1': "Bon de commande, spécifications techniques, validation budgétaire",
            'PS4.1_A2': "Contrat de licence, liste utilisateurs, budget approuvé",
            'PS4.1_A3': "Documentation fabricant, prérequis système, accès administrateur",
            'PS4.2_A1': "Formulaire de compte, validation RH, politique sécurité SI",
            'PS4.2_A2': "Rapport incident, logs système, backup complet",
            'PR5.1_A1': "Cahier des charges, compétences requises, disponibilités ressources",
        }
        
        consulting_inputs = {
            'PR1.1_A1': "CV consultants, modèles corporate, photos professionnelles",
            'PR1.1_A3': "Profils experts, portfolio réalisations, certifications",
            'PR1.2_A1': "Fiches capitalisation, témoignages clients, métriques performance",
            'PR1.2_A2': "Rapports fin mission, feedback client, durée et budget",
            'PR2.1_A1': "Appel d'offres, contraintes temporelles, contexte client",
        }
        
        # Rechercher correspondance
        inputs_dict = support_inputs if dept_name == 'Support' else consulting_inputs
        
        for key, value in inputs_dict.items():
            if key in activity_name:
                return value
        
        # Fallback générique
        return "Spécifications requises, validation managériale, documentation de référence"

    # =========================================================================
    # UTILITAIRES
    # =========================================================================

    @api.model
    def _get_month_name(self, date_obj):
        """Retourne le nom du mois en français"""
        months = {
            1: 'janvier', 2: 'fevrier', 3: 'mars', 4: 'avril',
            5: 'mai', 6: 'juin', 7: 'juillet', 8: 'aout',
            9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'decembre'
        }
        return months.get(date_obj.month, 'janvier')

    @api.model
    def _get_monday_str(self, date_obj):
        """Retourne la date du lundi de la semaine au format YYYY-MM-DD"""
        monday = date_obj - timedelta(days=date_obj.weekday())
        return monday.strftime('%Y-%m-%d')