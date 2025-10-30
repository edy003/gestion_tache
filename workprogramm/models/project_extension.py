from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ProjectProject(models.Model):
    _inherit = 'project.project'

    project_type = fields.Selection([
        ('internal', 'Internal Project'),
        ('external', 'External Project')
    ], string='Project Type', default='internal', help='Project Type')
    test_department_ids = fields.Many2many(
        'hr.department',
        # relation='qcproject_project_test_dept_rel',
        relation='project_project_test_dept_rel',  # Nouvelle table de relation
        column1='project_id',
        column2='department_id',
        string='Departments',
        domain="[('dpt_type', '=', project_type)]",
        help="Sélectionnez un ou plusieurs départements associés au projet."
    )
    workflow_hierarchy_ids = fields.One2many('workflow.hierarchy', 'project_id', string='Project')

    project_assistant_id = fields.Many2one('res.users', string='Project Assistant', required=False, ondelete='restrict')

    practice_id = fields.Many2one('practice.practice', string='Practice', help="Pratique pour les projets externes")
    subcategory_ids = fields.Many2many(
        'practice.subcategory',
        relation='project_practice_subcategory_rel',
        column1='project_id',
        column2='subcategory_id',
        string='Subcategories',
        domain="[('practice_id', '=', practice_id)]",
        help="Sous-catégories associées à la pratique sélectionnée."
    )



    @api.onchange('project_type')
    def _onchange_project_type(self):
        """
        Réinitialise test_department_ids, practice_id et subcategory_ids si project_type change.
        """
        self.test_department_ids = [(5, 0, 0)]
        self.practice_id = False
        self.subcategory_ids = [(5, 0, 0)]
        return {
            'domain': {
                'test_department_ids': [('dpt_type', '=', self.project_type)] if self.project_type else [],
                'practice_id': [('type', 'in', ['consulting', 'technology'])] if self.project_type == 'external' else [
                    ('id', '=', False)],
                'subcategory_ids': [('practice_id', '=', self.practice_id.id)] if self.practice_id else []
            }
        }

    @api.onchange('practice_id')
    def _onchange_practice_id(self):
        """
        Réinitialise subcategory_ids si practice_id change.
        """
        self.subcategory_ids = [(5, 0, 0)]
        return {
            'domain': {
                'subcategory_ids': [('practice_id', '=', self.practice_id.id)] if self.practice_id else []
            }
        }

    @api.constrains('test_department_ids', 'project_type')
    def _check_test_department_ids(self):
        """
        Vérifie que test_department_ids correspond au type de projet.
        """
        for record in self:
            if record.project_type:
                valid_dept_ids = self.env['hr.department'].search([('dpt_type', '=', record.project_type)]).ids
                invalid_depts = [dept.id for dept in record.test_department_ids if dept.id not in valid_dept_ids]
                if invalid_depts:
                    raise ValidationError(
                        "Les départements sélectionnés dans 'Departments' doivent correspondre au type de projet.")

    @api.constrains('practice_id', 'project_type')
    def _check_practice_id(self):
        """
        Vérifie que practice_id est défini uniquement pour les projets externes.
        """
        for record in self:
            if record.practice_id and record.project_type != 'external':
                raise ValidationError(
                    "Le champ 'Practice' ne peut être défini que pour les projets de type 'External'.")

    @api.onchange('test_department_ids')
    def _onchange_test_department(self):
        """
        Met à jour workflow_hierarchy_ids en fonction des départements sélectionnés.
        """
        related_workflows = self.env['workflow.hierarchy'].search([
            ('department_id', 'in', self.test_department_ids.ids)
        ])
        self.workflow_hierarchy_ids = [(6, 0, related_workflows.ids)]

    @api.constrains('test_department_ids', 'project_type')
    def _check_test_department_ids(self):
        """
        Vérifie que test_department_ids correspond au type de projet.
        """
        for record in self:
            if record.project_type:
                valid_dept_ids = self.env['hr.department'].search([('dpt_type', '=', record.project_type)]).ids
                invalid_depts = [dept.id for dept in record.test_department_ids if dept.id not in valid_dept_ids]
                if invalid_depts:
                    raise ValidationError(
                        "Les départements sélectionnés dans 'Departments' doivent correspondre au type de projet.")

    @api.constrains('practice_id', 'project_type')
    def _check_practice_id(self):
        """
        Vérifie que practice_id est défini uniquement pour les projets externes.
        """
        for record in self:
            if record.practice_id and record.project_type != 'external':
                raise ValidationError(
                    "Le champ 'Practice' ne peut être défini que pour les projets de type 'External'.")

    @api.onchange('test_department_ids')
    def _onchange_test_department(self):
        """
        Met à jour workflow_hierarchy_ids en fonction des départements sélectionnés.
        """
        related_workflows = self.env['workflow.hierarchy'].search([
            ('department_id', 'in', self.test_department_ids.ids)
        ])
        self.workflow_hierarchy_ids = [(6, 0, related_workflows.ids)]
        om_field_3 = fields.Many2one('res.partner', string='Partenaire Associé')


class Practice(models.Model):
    _name = 'practice.practice'
    _description = 'Practice'

    name = fields.Char(string='Name', required=True)
    sic = fields.Char(string='SIC Code')
    department_ids = fields.Many2many(
        'hr.department',
        relation='practice_department_rel',
        column1='practice_id',
        column2='department_id',
        string='Departments'
    )
    type = fields.Selection([
        ('consulting', 'Consulting'),
        ('technology', 'Technology')
    ], string='Practice Type', required=True)

    # NOUVEAU CHAMP NÉCESSAIRE POUR LA VUE XML
    subcategory_ids = fields.One2many(
        'practice.subcategory',
        'practice_id',  # Champ Many2one dans practice.subcategory
        string='Subcategories'
    )

class PracticeSubcategory(models.Model):
    _name = 'practice.subcategory'
    _description = 'Practice Subcategory'

    name = fields.Char(string='Name', required=True)
    practice_id = fields.Many2one('practice.practice', string='Practice', required=True)