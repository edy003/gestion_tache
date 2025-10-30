# -*- coding: utf-8 -*-
import calendar
import locale
import logging
from email.policy import default
from datetime import datetime, date, timedelta

from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class WorkProgram(models.Model):
    _name = 'work.program'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Programme de travail'

    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, string='Utilisateur Associé')

    # Remplacement du champ 'status' par 'state' pour le workflow
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('ongoing', 'En cours'),
        ('to_validate', 'À Valider'),
        ('validated', 'Validé'),
        ('refused', 'Refusé'),
        ('to_redo', 'À Refaire'),
        ('incomplete', 'Inachevé'),
        ('done', 'Terminé'),
        ('cancelled', 'Annulé')
    ], string='État', default='draft', tracking=True)

    work_programm_department_id = fields.Many2one(
        'hr.department',
        string="Département autorisé",
        help="Sélectionnez le département autorisé pour ce workflow."
    )

    name = fields.Char(string='Nom du programme', default='Nouveau programme')
    week_of = fields.Integer(string='Semaine de', help="Numéro de semaine dans l'année")
    project_id = fields.Many2one('project.project', string='Projet / Programme', ondelete='restrict')
    activity_id = fields.Many2one('workflow.activity', string='Activité', ondelete='restrict')
    procedure_id = fields.Many2one('workflow.procedure', string='Type de tâche (Procédure)', ondelete='restrict')
    task_description_id = fields.Many2one('workflow.task.formulation', string='Description de la tâche',
                                          ondelete='restrict')
    inputs_needed = fields.Text(string='Entrées nécessaires', help="Entrées nécessaires pour la tâche, si applicable")
    deliverable_ids = fields.Many2many('workflow.deliverable', string='Livrables de la tâche')
    priority = fields.Selection([
        ('low', 'Basse'),
        ('medium', 'Moyenne'),
        ('high', 'Haute')
    ], string='Priorité', default='medium')
    complexity = fields.Selection([
        ('low', 'Faible'),
        ('medium', 'Moyenne'),
        ('high', 'Élevée')
    ], string='Complexité', default='medium')
    assignment_date = fields.Date(string='Date d\'assignation')
    duration_effort = fields.Float(string='Durée / Effort (heures)', help="Durée estimée ou effort en heures")
    initial_deadline = fields.Date(string='Date limite initiale')
    nb_postpones = fields.Integer(string='Nombre de reports', default=0)
    actual_deadline = fields.Date(string='Date limite réelle')
    responsible_id = fields.Many2one('hr.employee', string='Responsable', ondelete='restrict')
    support_ids = fields.Many2many('hr.employee', string='Support')

    completion_percentage = fields.Float(string='Pourcentage d\'achèvement', default=0.0)
    satisfaction_level = fields.Selection([
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé')
    ], string='Niveau de satisfaction')
    comments = fields.Text(string='Commentaires / Remarques')
    champ1 = fields.Char(string='Champ 1', help="Champ supplémentaire pour départements externes")
    champ2 = fields.Text(string='Champ 2', help="Champ supplémentaire pour départements externes")

    # Champs de sélection de date/semaine/mois
    def _get_default_current_month(self):
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
        return _(calendar.month_name[int(datetime.now().strftime("%m"))])

    def _get_default_current_month_selection(self):
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
        return [(_(calendar.month_name[i]), _(calendar.month_name[i])) for i in range(1, 13)]

    my_month = fields.Selection(
        selection=_get_default_current_month_selection,
        default=_get_default_current_month,
        string='Mois'
    )

    def _get_default_my_week(self):
        today = date.today()
        current_monday = today - timedelta(days=today.weekday())
        return current_monday.strftime("%Y-%m-%d")

    def _get_week_selection(self):
        my_week = []
        current_year = date.today().year
        january_first = date(current_year, 1, 1)
        monday_first = january_first - timedelta(days=january_first.weekday())
        for i in range(0, 53):
            week_start = monday_first + timedelta(weeks=i)
            if week_start.year > current_year:
                break
            my_day = week_start.day
            my_month_name = _(week_start.strftime("%B"))
            my_label = f"{my_day} - {my_month_name}"
            my_value = week_start.strftime("%Y-%m-%d")
            my_week.append((my_value, my_label))
        return my_week

    my_week_of = fields.Selection(
        selection=_get_week_selection,
        default=_get_default_my_week,
        string="Selection week"
    )

    is_external_department = fields.Boolean(
        string='Département Externe',
        compute='_compute_external_department',
        store=False
    )

    # -------------------------------------------------------------------------
    # WORKFLOW METHODS
    # -------------------------------------------------------------------------

    def action_start(self):
        """ Mettre la tâche en cours. """
        self.write({'state': 'ongoing'})

    def action_submit_for_validation(self):
        """ Soumettre la tâche à validation. """
        if self.filtered(lambda r: r.state not in ('draft', 'ongoing', 'to_redo', 'incomplete')):
            raise UserError(
                _("Seuls les programmes en Brouillon/En cours/À refaire/Inachevé peuvent être soumis à validation."))
        self.write({'state': 'to_validate'})

    def action_validate(self):
        """ Valider la tâche. Passe à l'état 'Validé'. """
        if self.filtered(lambda r: r.state != 'to_validate'):
            raise UserError(_("Seuls les programmes 'À Valider' peuvent être validés."))
        self.write({'state': 'validated'})

    def action_refuse(self):
        """ Refuser la tâche. Passe à l'état 'Refusé'. """
        if self.filtered(lambda r: r.state != 'to_validate'):
            raise UserError(_("Seuls les programmes 'À Valider' peuvent être refusés."))
        self.write({'state': 'refused'})

    def action_to_redo(self):
        """ Marquer la tâche 'À refaire'. """
        if self.filtered(lambda r: r.state not in ('validated', 'refused', 'incomplete')):
            raise UserError(_("L'état actuel de la tâche ne permet pas de la mettre 'À refaire'."))
        self.write({'state': 'to_redo'})

    def action_mark_incomplete(self):
        """ Marquer la tâche comme 'Inachevée'. """
        if self.filtered(lambda r: r.state in ('validated', 'refused', 'cancelled', 'done')):
            raise UserError(_("Cette action est impossible après une validation ou un achèvement."))
        self.write({'state': 'incomplete'})

    def action_done(self):
        """ Mettre la tâche en Terminé. """
        self.write({'state': 'done'})

    def action_cancel(self):
        """ Annuler la tâche. """
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        """ Remettre la tâche en brouillon (pour correction). """
        self.write({'state': 'draft'})

    # -------------------------------------------------------------------------
    # CONSTRAINTS AND COMPUTES
    # -------------------------------------------------------------------------

    @api.constrains('completion_percentage')
    def _check_completion_percentage(self):
        for record in self:
            if record.completion_percentage < 0 or record.completion_percentage > 100:
                raise ValidationError("Le pourcentage d'achèvement doit être compris entre 0 et 100.")

    @api.depends('work_programm_department_id')
    def _compute_external_department(self):
        """Calcule si le département est externe pour contrôler la visibilité des champs."""
        for record in self:
            is_external = record.work_programm_department_id.dpt_type == 'external'
            record.is_external_department = is_external

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------

    @api.onchange('activity_id')
    def _onchange_activity_id(self):
        if self.activity_id:
            return {
                'domain': {
                    'procedure_id': [('activity_id', '=', self.activity_id.id)],
                    'deliverable_ids': [('activity_id', '=', self.activity_id.id)]
                }
            }
        else:
            self.procedure_id = False
            self.deliverable_ids = [(5, 0, 0)]
            return {'domain': {'procedure_id': [], 'deliverable_ids': []}}

    @api.onchange('procedure_id')
    def _onchange_procedure_id(self):
        if self.procedure_id:
            return {'domain': {'task_description_id': [('procedure_id', '=', self.procedure_id.id)]}}
        else:
            self.task_description_id = False
            return {'domain': {'task_description_id': []}}

    # -------------------------------------------------------------------------
    # IMPORT METHOD
    # -------------------------------------------------------------------------

    @api.model
    def import_work_program(self, row):
        try:
            # Note: Le champ 'status' de l'import doit être adapté pour les nouvelles valeurs de 'state'
            vals = {
                'name': row.get('Task Description', 'Nouveau programme'),
                'my_month': row.get('Month', '').lower() if row.get('Month') else False,
                'week_of': int(row.get('Week of')) if row.get('Week of') else False,
                'inputs_needed': row.get('Inputs needed (If applicable)'),
                'priority': row.get('Priority', 'medium').lower() if row.get('Priority') else 'medium',
                'complexity': row.get('Complexity', 'medium').lower() if row.get('Complexity') else 'medium',
                'assignment_date': row.get('Assignment date'),
                'duration_effort': float(row.get('Duration / Effort (Hrs)')) if row.get(
                    'Duration / Effort (Hrs)') else 0.0,
                'initial_deadline': row.get('Initial Dateline'),
                'nb_postpones': int(row.get('Nb of Postpones')) if row.get('Nb of Postpones') else 0,
                'actual_deadline': row.get('Actual Deadline'),
                # Utilisation de 'state' à la place de 'status'
                'state': row.get('Status', 'draft').lower() if row.get('Status') else 'draft',
                'completion_percentage': float(row.get('% of completion')) if row.get('% of completion') else 0.0,
                'satisfaction_level': row.get('Satisfaction Level', '').lower() if row.get(
                    'Satisfaction Level') else False,
                'comments': row.get('Comments / Remarques / Problems encountered / Additionals informations'),
                'champ1': row.get('Champ 1', ''),
                'champ2': row.get('Champ 2', '')
            }

            if row.get('Departments'):
                dept = self.env['hr.department'].search([('name', '=', row['Departments'])], limit=1)
                if dept:
                    vals['work_programm_department_id'] = dept.id

            if row.get('Activity'):
                activity = self.env['workflow.activity'].search([('name', '=', row['Activity'])], limit=1)
                if activity:
                    vals['activity_id'] = activity.id

            if row.get('Task Type (Procedure)'):
                procedure = self.env['workflow.procedure'].search([('name', '=', row['Task Type (Procedure)'])],
                                                                  limit=1)
                if procedure:
                    vals['procedure_id'] = procedure.id

            if row.get('Task Description'):
                task_description = self.env['workflow.task.formulation'].search(
                    [('name', '=', row['Task Description'])], limit=1)
                if task_description:
                    vals['task_description_id'] = task_description.id

            if row.get('Task Deliverable(s)'):
                deliverables = [name.strip() for name in row['Task Deliverable(s)'].split(',') if name.strip()]
                deliverable_ids = []
                for deliverable_name in deliverables:
                    deliverable = self.env['workflow.deliverable'].search([('name', '=', deliverable_name)], limit=1)
                    if deliverable:
                        deliverable_ids.append(deliverable.id)
                vals['deliverable_ids'] = [(6, 0, deliverable_ids)]

            if row.get('Responsible'):
                responsible = self.env['hr.employee'].search([('name', '=', row['Responsible'])], limit=1)
                if responsible:
                    vals['responsible_id'] = responsible.id

            if row.get('Support'):
                supports = [name.strip() for name in row['Support'].split(',') if name.strip()]
                support_ids = []
                for support_name in supports:
                    support = self.env['hr.employee'].search([('name', '=', support_name)], limit=1)
                    if support:
                        support_ids.append(support.id)
                vals['support_ids'] = [(6, 0, support_ids)]

            existing_record = self.search([('name', '=', vals['name'])], limit=1)
            if existing_record:
                _logger.info(f"Mise à jour du programme de travail : {vals['name']}")
                existing_record.write(vals)
                return existing_record
            else:
                _logger.info(f"Création d'un nouveau programme de travail : {vals['name']}")
                return self.create(vals)
        except Exception as e:
            _logger.error(f"Erreur lors de l'importation de la ligne du programme de travail : {row}. Erreur : {e}",
                          exc_info=True)
            return self.create({
                'name': f"ERREUR-IMPORT-{vals.get('name', 'UNKNOWN')}",
                'comments': f"Échec de l'importation : {row}. Erreur : {e}",
                'state': 'cancelled'  # Utilisation de 'state'
            })