/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";


const { Component } = owl;
const { useState, onMounted, useRef, onWillUnmount } = owl.hooks;

export class UserKPIDashboard extends Component {
    setup() {
        console.log("Initialisation du composant UserKPIDashboard avec date range");

        this.state = useState({
            loading: false,
            error: null,
            selectedStartDate: null,
            selectedEndDate: null,
            selectedDepartmentId: null,
            selectedResponsibleId: null,
            dateFrom: null,
            dateTo: null,
            selectedProjectId: null,   
            availableProjects: [], 
            availableDepartments: [],
            availableEmployees: [],
            employeesForDepartment: [],
            isManagerOrAdmin: false,
            employee: {
                id: null,
                name: null,
                department: null,
                image_url: null,
                role: null
            },
            totalTasks: '--',
            totalProjects: '--', 
            tasksValid:'--',
            tasksToValid:'--',
            // totalReports: '--',
            // taskInprogress:'--',
            // taskDelayed:'--',
            // taskOntime:"--",
            // taskLate:'--',
            chartData: {
                statusDistribution: { labels: [], values: [] },
                complexityDistribution: { labels: [], values: [] },
                priorityDistribution: { labels: [], values: [] },
                stateDistribution: { labels: [], values: [] }
                
            },
            tableData: [],
            
        });

        this.rpc = useService("rpc");
        this.orm = useService("orm");
        this.action = useService("action");
        this.user = useService("user"); 

        this.dateFromRef = useRef("dateFrom");
        this.dateToRef = useRef("dateTo");
        this.statusChartRef = useRef("status-distribution-chart");
        this.complexityChartRef = useRef("complexity-distribution-chart"); 
        this.priorityChartRef = useRef("priority-distribution-chart");
        this.stateChartRef = useRef("state-distribution-chart");
        this.gridRef = useRef("tasks-grid");
        this.gridApi = null;
        this.gridColumnApi = null;
        this.gridInitialized = false;

        // Instances flatpickr
        this.flatpickrFrom = null;
        this.flatpickrTo = null;
        this.flatpickrLoaded = false;

        onMounted(async () => {
            await this.checkUserPermissions();
            await this.loadInitialData();
            // Ajouter un délai pour s'assurer que les éléments DOM sont bien montés
            setTimeout(() => {
                this.initializeDatePickers();
            }, 100);
            setTimeout(() => {
                this.initializeGrid();
            }, 100);
        });

        onWillUnmount(() => {
            this.destroyDatePickers();
            this.destroyGrid();
        });
    }

    // ===== IMPROVED FLATPICKR INITIALIZATION =====
    async initializeDatePickers() {
        try {
            if (typeof flatpickr !== 'undefined') {
                this.initFlatpickrInputs();
                return;
            }

            // Try multiple CDN sources in case one fails
            const cdnSources = [
                "https://cdn.jsdelivr.net/npm/flatpickr"
            ];

            const cssSources = [
               "https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css"
            ];

            await this.loadFlatpickrWithFallback(cdnSources, cssSources);
        } catch (error) {
            console.warn("⚠️ Impossible de charger Flatpickr, utilisation d'inputs HTML5 standard");
            this.setupFallbackDateInputs();
        }
    }

    async loadFlatpickrWithFallback(jsSources, cssSources) {
        // Load CSS first
        for (const cssUrl of cssSources) {
            try {
                await this.loadCSS(cssUrl);
                break; // Success, stop trying other CSS sources
            } catch (error) {
                console.warn(`Failed to load CSS from ${cssUrl}, trying next...`);
            }
        }

        // Load JavaScript
        for (const jsUrl of jsSources) {
            try {
                await this.loadScript(jsUrl);
                console.log("✅ Flatpickr chargé avec succès");
                this.initFlatpickrInputs();
                return;
            } catch (error) {
                console.warn(`Failed to load JS from ${jsUrl}, trying next...`);
            }
        }

        throw new Error("All CDN sources failed");
    }

    loadCSS(url) {
        return new Promise((resolve, reject) => {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = url;
            link.onload = resolve;
            link.onerror = reject;
            
            // Check if already loaded
            if (document.querySelector(`link[href="${url}"]`)) {
                resolve();
                return;
            }
            
            document.head.appendChild(link);
        });
    }

    loadScript(url) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = url;
            script.onload = resolve;
            script.onerror = reject;
            
            // Check if already loaded
            if (document.querySelector(`script[src="${url}"]`)) {
                resolve();
                return;
            }
            
            document.head.appendChild(script);
        });
    }

    initFlatpickrInputs() {
        if (typeof flatpickr === 'undefined') {
            this.setupFallbackDateInputs();
            return;
        }

        // Vérifier que les éléments DOM existent
        if (!this.dateFromRef.el || !this.dateToRef.el) {
            console.warn("⚠️ Éléments DOM non trouvés, utilisation d'inputs HTML5 standard");
            this.setupFallbackDateInputs();
            return;
        }

        try {
            this.destroyDatePickers(); // Clean up existing instances

            const commonConfig = {
                dateFormat: "Y-m-d",
                allowInput: true,
                clickOpens: true
            };

            // Add French locale if available
            if (flatpickr.l10ns && flatpickr.l10ns.fr) {
                commonConfig.locale = "fr";
            }

            const fromConfig = {
                ...commonConfig,
                onChange: (selectedDates) => {
                    if (selectedDates.length > 0) {
                        this.state.selectedStartDate = selectedDates[0].toISOString().split('T')[0];
                        this.state.dateFrom = this.state.selectedStartDate;
                    } else {
                        this.state.selectedStartDate = null;
                        this.state.dateFrom = null;
                    }
                }
            };

            const toConfig = {
                ...commonConfig,
                onChange: (selectedDates) => {
                    if (selectedDates.length > 0) {
                        this.state.selectedEndDate = selectedDates[0].toISOString().split('T')[0];
                        this.state.dateTo = this.state.selectedEndDate;
                    } else {
                        this.state.selectedEndDate = null;
                        this.state.dateTo = null;
                    }
                }
            };

            // N'ajouter defaultDate que si on a une valeur
            if (this.state.dateFrom) {
                fromConfig.defaultDate = this.state.dateFrom;
            }
            if (this.state.dateTo) {
                toConfig.defaultDate = this.state.dateTo;
            }

            this.flatpickrFrom = flatpickr(this.dateFromRef.el, fromConfig);
            this.flatpickrTo = flatpickr(this.dateToRef.el, toConfig);

            this.flatpickrLoaded = true;
            console.log("✅ Flatpickr initialisé avec succès");
        } catch (error) {
            console.error("❌ Erreur lors de l'initialisation de Flatpickr:", error);
            this.setupFallbackDateInputs();
        }
    }

    setupFallbackDateInputs() {
        // Use standard HTML5 date inputs as fallback
        if (this.dateFromRef.el) {
            this.dateFromRef.el.type = 'date';
            this.dateFromRef.el.value = this.state.dateFrom || '';
        }
        if (this.dateToRef.el) {
            this.dateToRef.el.type = 'date';
            this.dateToRef.el.value = this.state.dateTo || '';
        }
        console.log("📅 Utilisation des inputs HTML5 date standards");
    }

    destroyDatePickers() {
        try {
            if (this.flatpickrFrom) {
                this.flatpickrFrom.destroy();
                this.flatpickrFrom = null;
            }
            if (this.flatpickrTo) {
                this.flatpickrTo.destroy();
                this.flatpickrTo = null;
            }
        } catch (error) {
            console.warn("Warning during flatpickr cleanup:", error);
        }
    }

    // ===== CHARGEMENT INITIAL =====
    async loadInitialData() {
        this.state.loading = true;
        try {
            await Promise.all([this.loadDepartments(), this.loadEmployees(),this.loadProjects(),this.loadEmployeeInfo()]);
            const now = new Date();
            const startOfYear = new Date(now.getFullYear(), 0, 1);
            const endOfYear = new Date(now.getFullYear(), 11, 31);
            this.state.selectedStartDate = startOfYear.toISOString().split('T')[0];
            this.state.selectedEndDate = endOfYear.toISOString().split('T')[0];
            this.state.dateFrom = this.state.selectedStartDate;
            this.state.dateTo = this.state.selectedEndDate;
            await this.loadAllData();
        } catch (error) {
            console.error("Erreur lors du chargement initial:", error);
            this.state.error = "Erreur lors du chargement des données";
        } finally {
            this.state.loading = false;
        }
    }

    async loadEmployeeInfo() {
    try {
        console.log("Chargement des informations de l'employé...");
        const result = await this.rpc("/dashboard/current_employee_info");
        if (result.error || !result.employee) {
            console.error("Erreur lors du chargement des infos employé:", result.message);
            this.state.employee = {
                id: null,
                name: "Inconnu",
                department: null,
                image_url: "/web/static/src/img/placeholder.png",
                role: "Employé"
            };
        } else {
            this.state.employee = {
                id: result.employee.id,
                name: result.employee.name,
                department: result.employee.department,
                image_url: result.employee.image_url,
                role: result.employee.role
            };
            console.log("✅ Infos employé chargées:", this.state.employee);
        }
    } catch (error) {
        console.error("Erreur lors du chargement des infos employé:", error);
        this.state.employee = {
            id: null,
            name: "Inconnu",
            department: null,
            image_url: "/web/static/src/img/placeholder.png",
            role: "Employé"
        };
    }
}

async checkUserPermissions() {
    try {
        const userId = this.user.userId; // ✅ MODIFIER ICI
        console.log("Vérification des permissions pour user ID:", userId);
        
        const isManager = await this.user.hasGroup('workprogramm.workprogramm_group_manager'); // ✅ MODIFIER ICI
        const isAdmin = await this.user.hasGroup('workprogramm.workprogramm_group_admin'); // ✅ MODIFIER ICI
        
        this.state.isManagerOrAdmin = isManager || isAdmin;
        console.log("✅ Utilisateur est manager ou admin :", this.state.isManagerOrAdmin);
    } catch (error) {
        console.error("Erreur lors de la vérification des permissions:", error);
        this.state.isManagerOrAdmin = false;
    }
}

    async loadProjects() {
    try {
        const projects = await this.orm.searchRead("project.project", [], ["name"]);
        this.state.availableProjects = projects.sort((a,b) => a.name.localeCompare(b.name));
    } catch (error) {
        console.error("Erreur chargement projets:", error);
        this.state.availableProjects = [];
    }
}


    async loadDepartments() {
        try {
            const departments = await this.orm.searchRead("hr.department", [], ["name"]);
            this.state.availableDepartments = departments.sort((a,b)=>a.name.localeCompare(b.name));
        } catch (error) {
            console.error("Erreur chargement départements:", error);
            this.state.availableDepartments = [];
        }
    }

    async loadEmployees() {
        try {
            const employees = await this.orm.searchRead("hr.employee", [['active','=',true]], ["name"]);
            this.state.availableEmployees = employees.sort((a,b)=>a.name.localeCompare(b.name));
            this.state.employeesForDepartment = this.state.availableEmployees;
        } catch (error) {
            console.error("Erreur chargement employés:", error);
            this.state.availableEmployees = [];
            this.state.employeesForDepartment = [];
        }
    }

    async loadEmployeesForDepartment(deptId) {
        if (!deptId) {
            this.state.employeesForDepartment = this.state.availableEmployees;
            return;
        }
        try {
            const employees = await this.orm.searchRead("hr.employee", [
                ["department_id","=",deptId],
                ['active','=',true]
            ], ["name"]);
            this.state.employeesForDepartment = employees.sort((a,b)=>a.name.localeCompare(b.name));
            if (this.state.selectedResponsibleId && !this.state.employeesForDepartment.find(emp => emp.id === this.state.selectedResponsibleId)) {
                this.state.selectedResponsibleId = null;
            }
        } catch (error) {
            console.error("Erreur chargement employés du département:", error);
            this.state.employeesForDepartment = [];
        }
    }

    // ===== GESTION DES FILTRES =====
    onDateFromChange(event) {
        this.state.dateFrom = event.target.value;
        this.state.selectedStartDate = event.target.value;
        if (this.flatpickrFrom && this.flatpickrLoaded) {
            try {
                this.flatpickrFrom.setDate(this.state.selectedStartDate);
            } catch (error) {
                console.warn("Erreur mise à jour flatpickr:", error);
            }
        }
    }

    onDateToChange(event) {
        this.state.dateTo = event.target.value;
        this.state.selectedEndDate = event.target.value;
        if (this.flatpickrTo && this.flatpickrLoaded) {
            try {
                this.flatpickrTo.setDate(this.state.selectedEndDate);
            } catch (error) {
                console.warn("Erreur mise à jour flatpickr:", error);
            }
        }
    }



async onDepartmentChange(event) {
    const value = event.target.value;
    // ✅ Convertir "" en null pour le backend, mais garder "" pour le frontend
    const deptId = value === "" ? null : parseInt(value);
    
    console.log("Changement de département:", { value, deptId, previous: this.state.selectedDepartmentId });
    
    // ✅ Garder "" pour que le select affiche "Tous"
    this.state.selectedDepartmentId = value; // Garder la valeur brute
    this.state.selectedResponsibleId = "";

    await this.loadEmployeesForDepartment(deptId); // Passer null au backend
}

onResponsibleChange(event) {
    const value = event.target.value;
    const respId = (value === "" || value === null) ? null : parseInt(value);
    
    console.log("Changement de responsable:", { value, respId, previous: this.state.selectedResponsibleId });
    
    this.state.selectedResponsibleId = value;
}

onProjectChange(event) {
    const value = event.target.value;
    const projId = value === "" ? null : parseInt(value);
    
    console.log("Changement de projet:", { value, projId, previous: this.state.selectedProjectId });
    
    this.state.selectedProjectId = value; // Garder "" pour le frontend
}

    async onApplyFilters() {
        if (!this.state.selectedStartDate || !this.state.selectedEndDate) {
            console.warn("Dates de début et fin requises");
            return;
        }
        this.state.loading = true;
        try {
            await this.loadAllData();
        } catch (error) {
            console.error("Erreur lors de l'application des filtres:", error);
            this.state.error = "Erreur lors de l'application des filtres";
        } finally {
            this.state.loading = false;
        }
    }

    async onResetFilters() {
        const now = new Date();
        this.state.selectedStartDate = new Date(now.getFullYear(),0,1).toISOString().split('T')[0];
        this.state.selectedEndDate = new Date(now.getFullYear(),11,31).toISOString().split('T')[0];
        this.state.dateFrom = this.state.selectedStartDate;
        this.state.dateTo = this.state.selectedEndDate;
        // this.state.selectedDepartmentId = null;
        // this.state.selectedResponsibleId = null;
        this.state.selectedProjectId = "";
        this.state.selectedDepartmentId = "";
        this.state.selectedResponsibleId = "";
        this.state.employeesForDepartment = this.state.availableEmployees;
        
        // Update flatpickr instances
        if (this.flatpickrFrom && this.flatpickrLoaded) {
            try {
                this.flatpickrFrom.setDate(this.state.selectedStartDate);
            } catch (error) {
                console.warn("Erreur reset flatpickr from:", error);
            }
        }
        if (this.flatpickrTo && this.flatpickrLoaded) {
            try {
                this.flatpickrTo.setDate(this.state.selectedEndDate);
            } catch (error) {
                console.warn("Erreur reset flatpickr to:", error);
            }
        }
        
        try {
            await this.loadAllData();
        } catch (error) {
            console.error("Erreur lors de la réinitialisation:", error);
        }
    }


    // ===== CHARGEMENT DES DONNÉES =====
    async loadAllData() {
        const params = {
            start_date: this.state.selectedStartDate,
            end_date: this.state.selectedEndDate,
            // department_id: this.state.selectedDepartmentId,
            // responsible_id: this.state.selectedResponsibleId
            project_id: this.state.selectedProjectId === "" ? null : this.state.selectedProjectId,
            department_id: this.state.selectedDepartmentId === "" ? null : this.state.selectedDepartmentId,
            responsible_id: this.state.selectedResponsibleId === "" ? null : this.state.selectedResponsibleId

        };
        
        try {
            await Promise.all([this.loadKPIData(params), this.loadChartData(params),this.loadTableData(params)]);
            this.renderCharts();
            this.updateGridData();
        } catch (error) {
            console.error("Erreur lors du chargement des données:", error);
            throw error;
        }
    }

    async loadKPIData(params) {
    try {
        // Préparer les paramètres en convertissant null/undefined en valeurs appropriées
        const apiParams = {
            date_from: params.start_date,
            date_to: params.end_date,
            project_id: params.project_id ?? null,
            department_id: params.department_id ?? null,  // ✅ Utilise ?? au lieu de ||
            responsible_id: params.responsible_id ?? null  
        };

        const [ tasksResponse,projectsResponse,tasksValidResponse,tasksToValidReponse,reportsResponse,completionmeanReports,taskInprogressResponse,taskDelayedResponse,taskOntimeResponse,taskLateResponse] = await Promise.all([
            this.rpc('/dashboard/work_program_count', apiParams),
            this.rpc('/dashboard/work_program_projects_count', apiParams),
            this.rpc('/dashboard/work_program_valid', apiParams),
            this.rpc('/dashboard/work_program_to_validate', apiParams),
            // this.rpc('/dashboard/work_program_total_reports', apiParams),
            // this.rpc('/dashboard/work_program_completion_mean', apiParams),
            // this.rpc('/dashboard/work_program_in_progress', apiParams),
            // this.rpc('/dashboard/work_program_delayed', apiParams),
            // this.rpc('/dashboard/work_program_on_time', apiParams),
            // this.rpc('/dashboard/work_program_late', apiParams),
        ]);
        

        // this.state.deadlineCompliance = deadlineResponse.deadline_compliance;
        this.state.totalTasks = tasksResponse.error ? '--' : tasksResponse.total_tasks;
        this.state.totalProjects = projectsResponse.error ? '--' : projectsResponse.total_projects;
        this.state.tasksValid = tasksValidResponse.error ? '--' : tasksValidResponse.tasks_valid;
        this.state.tasksToValid = tasksToValidReponse.error ? '--' : tasksToValidReponse.tasks_to_validate;
        // this.state.totalReports = reportsResponse.error ? '--' : reportsResponse.total_reports;
        // this.state.completionMean = completionmeanReports.error ? '--' : completionmeanReports.completion_mean;
        // this.state.taskInprogress = taskInprogressResponse.error ? '--' : taskInprogressResponse.in_progress_count;
        // this.state.taskDelayed = taskDelayedResponse.error ? '--' : taskDelayedResponse.delayed_count;
        // this.state.taskOntime = taskOntimeResponse.error ? '--' : taskOntimeResponse.on_time_count;
        // this.state.taskLate = taskLateResponse.error ? '--' : taskLateResponse.late_count;
    } catch (error) {
        console.error("Erreur lors du chargement des KPI:", error);
        this.state.totalTasks = '--';
        this.state.totalProjects = '--';
        this.state.tasksValid = '--';
        this.state.tasksToValid='--';
        this.state.totalReports = '--';
        this.state.completionMean = '--';
    }
}

async onAllTasksClick(e) {
    e.stopPropagation();
    e.preventDefault();
    
    try {
        // Construire le domaine avec les filtres actifs, sans restriction sur state
        const domain = [];
        
        // Ajouter filtre par dates si sélectionnées
          // Ajouter filtre par dates si sélectionnées
        if (this.state.selectedStartDate && this.state.selectedEndDate) {
            domain.push(['assignment_date', '>=', this.state.selectedStartDate]);
            domain.push(['assignment_date', '<=', this.state.selectedEndDate]);
        }
        
        // Ajouter filtre par département si sélectionné (convertir "" en null)
        const deptId = this.state.selectedDepartmentId === "" ? null : parseInt(this.state.selectedDepartmentId);
        if (deptId) {
            domain.push(['responsible_id.department_id', '=', deptId]);
        }
        
        
        // Ajouter filtre par responsable ou support si sélectionné (convertir "" en null)
        const respId = this.state.selectedResponsibleId === "" ? null : parseInt(this.state.selectedResponsibleId);
        if (respId) {
            domain.push('|');
            domain.push(['responsible_id', '=', respId]);
            domain.push(['support_ids', 'in', [respId]]);
        }

        const projId = this.state.selectedProjectId === "" ? null : parseInt(this.state.selectedProjectId);
        if (projId) {
            domain.push(['project_id', '=', projId]);
        }
        
        console.log("📋 Domaine appliqué pour toutes les tâches:", domain);
        
        await this.action.doAction({
            name: "Toutes les Tâches",
            type: 'ir.actions.act_window',
            res_model: 'work.program',
            view_mode: 'kanban,form',
            views: [[false, 'kanban'], [false, 'form']],
            domain: domain,  // ✅ Domaine dynamique avec filtres
            context: {},  // Pas de default_state car toutes les tâches sont incluses
            target: 'current'
        });
    } catch (error) {
        console.error("Erreur navigation toutes les tâches:", error);
    }
}

async onTasksValidatedClick(e) {
    e.stopPropagation();
    e.preventDefault();
    
    try {
        // Construire le domaine avec les filtres actifs
        const domain = [['state', '=', 'validated']];
        
        // Ajouter filtre par dates si sélectionnées
    // Ajouter filtre par dates si sélectionnées
        if (this.state.selectedStartDate && this.state.selectedEndDate) {
            domain.push(['assignment_date', '>=', this.state.selectedStartDate]);
            domain.push(['assignment_date', '<=', this.state.selectedEndDate]);
        }
        
        // Ajouter filtre par département si sélectionné (convertir "" en null)
        const deptId = this.state.selectedDepartmentId === "" ? null : parseInt(this.state.selectedDepartmentId);
        if (deptId) {
            domain.push(['responsible_id.department_id', '=', deptId]);
        }
        
        // Ajouter filtre par responsable ou support si sélectionné (convertir "" en null)
        const respId = this.state.selectedResponsibleId === "" ? null : parseInt(this.state.selectedResponsibleId);
        if (respId) {
            domain.push('|');
            domain.push(['responsible_id', '=', respId]);
            domain.push(['support_ids', 'in', [respId]]);
        }

        const projId = this.state.selectedProjectId === "" ? null : parseInt(this.state.selectedProjectId);
        if (projId) {
            domain.push(['project_id', '=', projId]);
        }
        
        console.log("📋 Domaine appliqué pour tâches validées:", domain);
        
        await this.action.doAction({
            name: "Tâches Validées",
            type: 'ir.actions.act_window',
            res_model: 'work.program',
            view_mode: 'kanban,form',
            views: [[false, 'kanban'], [false, 'form']],
            domain: domain,  // ✅ Domaine dynamique avec filtres
            context: {
                'default_state': 'validated',
            },
            target: 'current'
        });
    } catch (error) {
        console.error("Erreur navigation tâches validées:", error);
    }
}

async onTasksToValidateClick(e) {
    e.stopPropagation();
    e.preventDefault();
    
    try {
        // Construire le domaine avec les filtres actifs
        const domain = [['state', '=', 'to_validate']];
        
           // Ajouter filtre par dates si sélectionnées
        if (this.state.selectedStartDate && this.state.selectedEndDate) {
            domain.push(['assignment_date', '>=', this.state.selectedStartDate]);
            domain.push(['assignment_date', '<=', this.state.selectedEndDate]);
        }
        
        // Ajouter filtre par département si sélectionné (convertir "" en null)
        const deptId = this.state.selectedDepartmentId === "" ? null : parseInt(this.state.selectedDepartmentId);
        if (deptId) {
            domain.push(['responsible_id.department_id', '=', deptId]);
        }
        
        // Ajouter filtre par responsable ou support si sélectionné (convertir "" en null)
       const respId = this.state.selectedResponsibleId === "" ? null : parseInt(this.state.selectedResponsibleId);
        if (respId) {
            domain.push('|');
            domain.push(['responsible_id', '=', respId]);
            domain.push(['support_ids', 'in', [respId]]);
        }

        const projId = this.state.selectedProjectId === "" ? null : parseInt(this.state.selectedProjectId);
        if (projId) {
            domain.push(['project_id', '=', projId]);
        }
        
        console.log("📋 Domaine appliqué pour tâches à valider:", domain);
        
        await this.action.doAction({
            name: "Tâches à Valider",
            type: 'ir.actions.act_window',
            res_model: 'work.program',
            view_mode: 'kanban,form',
            views: [[false, 'kanban'], [false, 'form']],
            domain: domain,  // ✅ Domaine dynamique avec filtres
            context: {
                'default_state': 'to_validate',
            },
            target: 'current'
        });
    } catch (error) {
        console.error("Erreur navigation tâches à valider:", error);
    }
}
 

    async loadChartData(params) {
    try {
        await Promise.all([
            this.loadStatusDistributionChart(params),
            this.loadComplexityDistributionChart(params),
            this.loadPriorityDistributionChart(params),
            this.loadStateDistributionChart(params),
        ]);
    } catch (error) {
        console.error("Erreur lors du chargement des données graphiques:", error);
        this.state.chartData = {
            statusDistribution: { labels: [], values: [] },
            complexityDistribution: { labels: [], values: [] },
            priorityDistribution: { labels: [], values: [] },
            stateDistribution: { labels: [], values: [] },
        };
    }
}

   async loadStatusDistributionChart(params) {
    try {
        console.log("Chargement du graphique de répartition des statuts...");
        
        // Convertir les paramètres date_from/date_to vers le format attendu par le contrôleur
        const apiParams = {
            date_from: params.start_date,
            date_to: params.end_date,
            department_id: params.department_id ?? null,
            project_id: params.project_id ?? null,
            responsible_id: params.responsible_id ?? null
        };

        const result = await this.rpc("/dashboard/work_program_status_distribution", apiParams);

        if (result.error) {
            console.error("Erreur lors du chargement du graphique statuts:", result.message);
            this.state.chartData.statusDistribution = { labels: [], values: [] };
        } else {
            this.state.chartData.statusDistribution = result.status_data;
            console.log("Données du pie chart statuts chargées:", result.status_data);
        }
    } catch (error) {
        console.error("Erreur lors du chargement du graphique statuts:", error);
        this.state.chartData.statusDistribution = { labels: [], values: [] };
    }
}

    async loadComplexityDistributionChart(params) {
    try {
        console.log("Chargement du graphique de répartition des complexités...");

        const apiParams = {
            date_from: params.start_date,
            date_to: params.end_date,
            department_id: params.department_id ?? null,
            project_id: params.project_id ?? null,
            responsible_id: params.responsible_id ?? null
        };

        const result = await this.rpc("/dashboard/work_program_complexity_distribution", apiParams);

        if (result.error) {
            console.error("Erreur lors du chargement du graphique complexités:", result.message);
            this.state.chartData.complexityDistribution = { labels: [], values: [] };
        } else {
            this.state.chartData.complexityDistribution = result.complexity_data;
            console.log("Données du pie chart complexités chargées:", result.complexity_data);
        }
    } catch (error) {
        console.error("Erreur lors du chargement du graphique complexités:", error);
        this.state.chartData.complexityDistribution = { labels: [], values: [] };
    }
}

async loadPriorityDistributionChart(params) {
    try {
        console.log("Chargement du graphique de répartition des priorités...");
        const apiParams = {
            date_from: params.start_date,
            date_to: params.end_date,
            department_id: params.department_id ?? null,
            project_id: params.project_id ?? null,
            responsible_id: params.responsible_id ?? null
        };
        const result = await this.rpc("/dashboard/work_program_priority_distribution", apiParams);
        if (result.error) {
            console.error("Erreur:", result.message);
            this.state.chartData.priorityDistribution = { labels: [], values: [] };
        } else {
            this.state.chartData.priorityDistribution = result.priority_data;
            console.log("Données du pie chart priorités chargées:", result.priority_data);
        }
    } catch (error) {
        console.error("Erreur chargement priorités:", error);
        this.state.chartData.priorityDistribution = { labels: [], values: [] };
    }
}



async loadStateDistributionChart(params) {
    try {
        console.log("Chargement du graphique de répartition des états...");
        const apiParams = {
            date_from: params.start_date,
            date_to: params.end_date,
            department_id: params.department_id ?? null,
            project_id: params.project_id ?? null,
            responsible_id: params.responsible_id ?? null
        };
        const result = await this.rpc("/dashboard/work_program_state_distribution", apiParams);
        if (result.error) {
            console.error("Erreur:", result.message);
            this.state.chartData.stateDistribution = { labels: [], values: [] };
        } else {
            this.state.chartData.stateDistribution = result.state_data;
            console.log("Données du bar chart états chargées:", result.state_data);
        }
    } catch (error) {
        console.error("Erreur chargement états:", error);
        this.state.chartData.stateDistribution = { labels: [], values: [] };
    }
}

    renderCharts() {
        console.log("📊 Render charts here");
        this.renderStatusDistributionChart();
        this.renderComplexityDistributionChart();
        this.renderPriorityDistributionChart();
        this.renderStateDistributionChart();
        // TODO: Implement chart rendering
    }
    
   renderStatusDistributionChart() {
    console.log("Tentative de rendu du pie chart statuts...", {
        statusChartRef: this.statusChartRef.el,
        hasData: this.state.chartData.statusDistribution.labels?.length > 0,
        data: this.state.chartData.statusDistribution
    });

    if (!this.statusChartRef.el) {
        console.warn("Élément DOM du pie chart statuts introuvable");
        return;
    }

    if (!this.state.chartData.statusDistribution.labels?.length) {
        console.warn("Aucune donnée pour le pie chart statuts");
        this.statusChartRef.el.innerHTML = '<div class="text-center p-4 text-gray-500">Aucune donnée à afficher pour les filtres sélectionnés</div>';
        return;
    }

    if (typeof Plotly === 'undefined') {
        console.warn("Plotly non disponible pour le pie chart statuts");
        return;
    }

    try {
        // 🎨 Mapping des couleurs par statut
        const colorMap = {
            'Not Started': '#9CA3AF',    // Gris
            'In Progress': '#3B82F6',    // Bleu
            'Done': '#22C55E',           // Vert
            'Unknown': '#EF4444'         // Rouge
        };

        // 🎨 Générer le tableau de couleurs dans l'ordre des labels
        const colors = this.state.chartData.statusDistribution.labels.map(
            label => colorMap[label] || '#6B7280'  // Couleur par défaut si label inconnu
        );

        const data = [{
            values: this.state.chartData.statusDistribution.values,
            labels: this.state.chartData.statusDistribution.labels,
            type: 'pie',
            hole: 0.4,
            marker: {
                colors: colors  // ✅ Couleurs dynamiques basées sur les labels
            },
            textinfo: 'label+percent',
            textposition: 'none',
            hovertemplate: '<b>%{label}</b><br>' +
                          'Nombre de tâches: %{value}<br>' +
                          'Pourcentage: %{percent}<br>' +
                          '<extra></extra>'
        }];

        const layout = {
            paper_bgcolor: '#FFFFFF',
            plot_bgcolor: '#FFFFFF',
            margin: { t: 0, r: 0, b: 0, l: 0 },
            showlegend: true,
            legend: {
                orientation: "v",
                yanchor: "middle",
                y: 0.5,
                xanchor: "left",
                x: 1.05,
                font: { size: 12 }
            },
            font: { family: 'Inter, sans-serif' }
        };

        const config = {
            displayModeBar: false,
            displaylogo: false,
            responsive: true
        };

        Plotly.newPlot(this.statusChartRef.el, data, layout, config);
        console.log("Pie chart statuts rendu avec succès");

    } catch (error) {
        console.error("Erreur lors du rendu du pie chart statuts:", error);
    }
}

    renderComplexityDistributionChart() {
    console.log("Tentative de rendu du pie chart complexités...", {
        complexityChartRef: this.complexityChartRef.el,
        hasData: this.state.chartData.complexityDistribution.labels?.length > 0,
        data: this.state.chartData.complexityDistribution
    });

    if (!this.complexityChartRef.el) {
        console.warn("Élément DOM du pie chart complexités introuvable");
        return;
    }

    if (!this.state.chartData.complexityDistribution.labels?.length) {
        console.warn("Aucune donnée pour le pie chart complexités");
        this.complexityChartRef.el.innerHTML = '<div class="text-center p-4 text-gray-500">Aucune donnée à afficher pour les filtres sélectionnés</div>';
        return;
    }
     // ✅ BON
    if (typeof Plotly !== 'undefined') {
        try {
            Plotly.purge( this.complexityChartRef.el);  // ← Bonne référence
        } catch (e) {
            console.warn("Erreur lors du nettoyage Plotly:", e);
        }
    }
    this.complexityChartRef.el.innerHTML = '';  // ← Bonne référence

    if (typeof Plotly === 'undefined') {
        console.warn("Plotly non disponible pour le pie chart complexités");
        return;
    }

    try {
        // 🎨 Mapping des couleurs par complexité
        const colorMap = {
            'low': '#22C55E',    // Vert
            'medium': '#F59E0B',  // Jaune
            'high': '#EF4444'     // Rouge
        };

        // 🎨 Générer le tableau de couleurs dans l'ordre des labels
        const colors = this.state.chartData.complexityDistribution.labels.map(
            label => colorMap[label] || '#6B7280' // Couleur par défaut si label inconnu
        );

        const data = [{
            values: this.state.chartData.complexityDistribution.values,
            labels: this.state.chartData.complexityDistribution.labels,
            type: 'pie',
            hole: 0.4,
            marker: {
                colors: colors
            },
            textinfo: 'label+percent',
            textposition: 'none',
            hovertemplate: '<b>%{label}</b><br>' +
                          'Nombre de tâches: %{value}<br>' +
                          'Pourcentage: %{percent}<br>' +
                          '<extra></extra>'
        }];

        const layout = {
            paper_bgcolor: '#FFFFFF',
            plot_bgcolor: '#FFFFFF',
            margin: { t: 0, r: 0, b: 0, l: 0 },
            showlegend: true,
            legend: {
                orientation: "v",
                yanchor: "middle",
                y: 0.5,
                xanchor: "left",
                x: 1.05,
                font: { size: 12 }
            },
            font: { family: 'Inter, sans-serif' }
        };

        const config = {
            displayModeBar: false,
            displaylogo: false,
            responsive: true
        };

        Plotly.newPlot(this.complexityChartRef.el, data, layout, config);
        this.complexityChartRef.el.on('plotly_click', (data) => {
            const clickedLabel = data.points[0].label; // Le label du segment cliqué
            console.log("Segment complexité cliqué:", clickedLabel);
            this.onComplexityPieClick(clickedLabel);
        });
        console.log("Pie chart complexités rendu avec succès");

    } catch (error) {
        console.error("Erreur lors du rendu du pie chart complexités:", error);
    }
}

    async onComplexityPieClick(clickedLabel) {
    console.log("🎯 Clic sur la complexité:", clickedLabel);

    try {
        // Construire le domaine avec les filtres actifs
        const domain = [['complexity', '=', clickedLabel]];  // ⚠️ Remplacez 'complexity' par le nom exact du champ dans votre modèle work.program si différent (ex: 'complexity_level')
        
        // Ajouter filtre par dates si sélectionnées
          // Ajouter filtre par dates si sélectionnées
        if (this.state.selectedStartDate && this.state.selectedEndDate) {
            domain.push(['assignment_date', '>=', this.state.selectedStartDate]);
            domain.push(['assignment_date', '<=', this.state.selectedEndDate]);
        }
        
        // Ajouter filtre par département si sélectionné (convertir "" en null)
        const deptId = this.state.selectedDepartmentId === "" ? null : parseInt(this.state.selectedDepartmentId);
        if (deptId) {
            domain.push(['responsible_id.department_id', '=', deptId]);
        }
        
       // Ajouter filtre par responsable ou support si sélectionné (convertir "" en null)
        const respId = this.state.selectedResponsibleId === "" ? null : parseInt(this.state.selectedResponsibleId);
        if (respId) {
            domain.push('|');
            domain.push(['responsible_id', '=', respId]);
            domain.push(['support_ids', 'in', [respId]]);
        }

        const projId = this.state.selectedProjectId === "" ? null : parseInt(this.state.selectedProjectId);
        if (projId) {
            domain.push(['project_id', '=', projId]);
        }
        
        console.log("📋 Domaine appliqué pour complexité:", clickedLabel, domain);
        
        // Nom d'affichage selon la complexité
        const complexityNames = {
            'low': 'Faible',
            'medium': 'Moyenne',
            'high': 'Élevée'
        };
        
        await this.action.doAction({
            name: `Tâches - Complexité ${complexityNames[clickedLabel] || clickedLabel}`,
            type: 'ir.actions.act_window',
            res_model: 'work.program',
            view_mode: 'kanban,form',
            views: [[false, 'kanban'], [false, 'form']],
            domain: domain,
            context: {
                'default_complexity': clickedLabel,  // ⚠️ Remplacez 'default_complexity' par le nom exact du champ
            },
            target: 'current'
        });
    } catch (error) {
        console.error("Erreur navigation complexité:", error);
    }
}

    renderPriorityDistributionChart() {
    console.log("Tentative de rendu du pie chart priorités...", {
        priorityChartRef: this.priorityChartRef.el,
        hasData: this.state.chartData.priorityDistribution.labels?.length > 0,
        data: this.state.chartData.priorityDistribution
    });

    if (!this.priorityChartRef.el) {
        console.warn("Élément DOM du pie chart priorités introuvable");
        return;
    }

    // ✅ BON
    if (typeof Plotly !== 'undefined') {
        try {
            Plotly.purge(this.priorityChartRef.el);  // ← Bonne référence
        } catch (e) {
            console.warn("Erreur lors du nettoyage Plotly:", e);
        }
    }
    this.priorityChartRef.el.innerHTML = '';  // ← Bonne référence

    if (!this.state.chartData.priorityDistribution.labels?.length) {
        console.warn("Aucune donnée pour le pie chart priorités");
        this.priorityChartRef.el.innerHTML = '<div class="text-center p-4 text-gray-500">Aucune donnée à afficher pour les filtres sélectionnés</div>';
        return;
    }

    if (typeof Plotly === 'undefined') {
        console.warn("Plotly non disponible pour le pie chart priorités");
        return;
    }

    try {
        const colorMap = {
            'low': '#22C55E',    // Vert
            'medium': '#F59E0B',  // Jaune
            'high': '#EF4444'     // Rouge
        };
        const colors = this.state.chartData.priorityDistribution.labels.map(
            label => colorMap[label] || '#6B7280'
        );

        const data = [{
            values: this.state.chartData.priorityDistribution.values,
            labels: this.state.chartData.priorityDistribution.labels,
            type: 'pie',
            hole: 0.4,
            marker: { colors: colors },
            textinfo: 'label+percent',
            textposition: 'none',
            hovertemplate: '<b>%{label}</b><br>Nombre: %{value}<br>Pourcentage: %{percent}<br><extra></extra>'
        }];

        const layout = {
            paper_bgcolor: '#FFFFFF',
            plot_bgcolor: '#FFFFFF',
            margin: { t: 0, r: 0, b: 0, l: 0 },
            showlegend: true,
            legend: {
                orientation: "v",
                yanchor: "middle",
                y: 0.5,
                xanchor: "left",
                x: 1.05,
                font: { size: 12 }
            },
            font: { family: 'Inter, sans-serif' }
        };

        const config = {
            displayModeBar: false,
            displaylogo: false,
            responsive: true
        };

        Plotly.newPlot(this.priorityChartRef.el, data, layout, config);
        this.priorityChartRef.el.on('plotly_click', (data) => {
            const clickedLabel = data.points[0].label; // Le label du segment cliqué
            console.log("Segment priorité cliqué:", clickedLabel);
            this.onPriorityPieClick(clickedLabel);
        });
         
        console.log("Pie chart priorités rendu avec succès");
    } catch (error) {
        console.error("Erreur lors du rendu du pie chart priorités:", error);
    }
}

async onPriorityPieClick(clickedLabel) {
    console.log("🎯 Clic sur la priorité:", clickedLabel);

    try {
        // Construire le domaine avec les filtres actifs
        const domain = [['priority', '=', clickedLabel]];
        
           // Ajouter filtre par dates si sélectionnées
        if (this.state.selectedStartDate && this.state.selectedEndDate) {
            domain.push(['assignment_date', '>=', this.state.selectedStartDate]);
            domain.push(['assignment_date', '<=', this.state.selectedEndDate]);
        }
        
        // Ajouter filtre par département si sélectionné (convertir "" en null)
        const deptId = this.state.selectedDepartmentId === "" ? null : parseInt(this.state.selectedDepartmentId);
        if (deptId) {
            domain.push(['responsible_id.department_id', '=', deptId]);
        }
        
       
       // Ajouter filtre par responsable ou support si sélectionné (convertir "" en null)
        const respId = this.state.selectedResponsibleId === "" ? null : parseInt(this.state.selectedResponsibleId);
        if (respId) {
            domain.push('|');
            domain.push(['responsible_id', '=', respId]);
            domain.push(['support_ids', 'in', [respId]]);
        }

        const projId = this.state.selectedProjectId === "" ? null : parseInt(this.state.selectedProjectId);
        if (projId) {
            domain.push(['project_id', '=', projId]);
        }
        
        console.log("📋 Domaine appliqué pour priorité:", clickedLabel, domain);
        
        // Nom d'affichage selon la priorité
        const priorityNames = {
            'low': 'Basse',
            'medium': 'Moyenne',
            'high': 'Haute'
        };
        
        await this.action.doAction({
            name: `Tâches - Priorité ${priorityNames[clickedLabel] || clickedLabel}`,
            type: 'ir.actions.act_window',
            res_model: 'work.program',
            view_mode: 'kanban,form',
            views: [[false, 'kanban'], [false, 'form']],
            domain: domain,
            context: {
                'default_priority': clickedLabel,
            },
            target: 'current'
        });
    } catch (error) {
        console.error("Erreur navigation priorité:", error);
    }
}

renderStateDistributionChart() {
    console.log("Tentative de rendu du bar chart états...", {
        chartRef: this.stateChartRef.el,
        hasData: this.state.chartData.stateDistribution.labels?.length > 0,
        data: this.state.chartData.stateDistribution
    });

    if (!this.stateChartRef.el) {
        console.warn("Élément DOM du bar chart états introuvable");
        return;
    }

     if (typeof Plotly !== 'undefined') {
        try {
            Plotly.purge( this.stateChartRef.el);  // ← Bonne référence
        } catch (e) {
            console.warn("Erreur lors du nettoyage Plotly:", e);
        }
    }
    this.stateChartRef.el.innerHTML = '';  // ← Bonne référence

    if (!this.state.chartData.stateDistribution.labels?.length) {
        console.warn("Aucune donnée pour le bar chart états");
        this.stateChartRef.el.innerHTML = '<div class="text-center p-4 text-gray-500">Aucune donnée à afficher pour les filtres sélectionnés</div>';
        return;
    }

    if (typeof Plotly === 'undefined') {
        console.warn("Plotly non disponible pour le bar chart états");
        return;
    }

    try {
        const data = [{
            x: this.state.chartData.stateDistribution.labels,
            y: this.state.chartData.stateDistribution.values,
            type: 'bar',
            marker: { color: '#3B82F6' },
            text: this.state.chartData.stateDistribution.values.map(String),
            textposition: 'outside',
            hovertemplate: '<b>%{x}</b><br>Nombre: %{y}<br><extra></extra>'
        }];

        const layout = {
            paper_bgcolor: '#FFFFFF',
            plot_bgcolor: '#FFFFFF',
            margin: { t:0, r: 50, b: 20, l: 50 },
            xaxis: { title: 'État' },
            yaxis: { title: 'Nombre de tâches' },
            font: { family: 'Inter, sans-serif' },
        };

        const config = {
            displayModeBar: false,
            displaylogo: false,
            responsive: true
        };

        Plotly.newPlot(this.stateChartRef.el, data, layout, config);
        
        // ✅ AJOUT DE L'ÉVÉNEMENT DE CLIC
        this.stateChartRef.el.on('plotly_click', (data) => {
            const clickedLabel = data.points[0].x; // Le label de la barre cliquée
            console.log("Barre cliquée:", clickedLabel);
            this.onStateBarClick(clickedLabel);
        });
        
        console.log("Bar chart états rendu avec succès");
    } catch (error) {
        console.error("Erreur lors du rendu du bar chart états:", error);
    }
}

async onStateBarClick(clickedLabel) {
    console.log("🎯 Clic sur la barre:", clickedLabel);

    // Mapping inverse : Français → Technique
    const stateMap = {
        'Brouillon':'draft',
        'En cours': 'ongoing',
        'À valider': 'to_validate',
        'Validé': 'validated',
        'Refusé': 'refused',
        'À refaire': 'to_redo',
        'Inachevé': 'incomplete',
        'Terminé': 'done',
        'Annulé': 'cancelled'
    };

    const technicalState = stateMap[clickedLabel];

    if (!technicalState) {
        console.warn("État inconnu:", clickedLabel);
        return;
    }

    try {
        // Construire le domaine avec les filtres actifs
        const domain = [['state', '=', technicalState]];
        
        // Ajouter filtre par dates si sélectionnées
           // Ajouter filtre par dates si sélectionnées
        if (this.state.selectedStartDate && this.state.selectedEndDate) {
            domain.push(['assignment_date', '>=', this.state.selectedStartDate]);
            domain.push(['assignment_date', '<=', this.state.selectedEndDate]);
        }
        
        // Ajouter filtre par département si sélectionné (convertir "" en null)
        const deptId = this.state.selectedDepartmentId === "" ? null : parseInt(this.state.selectedDepartmentId);
        if (deptId) {
            domain.push(['responsible_id.department_id', '=', deptId]);
        }
        
        // Ajouter filtre par responsable si sélectionné (convertir "" en null)
        // const respId = this.state.selectedResponsibleId === "" ? null : parseInt(this.state.selectedResponsibleId);
        // if (respId) {
        //     domain.push(['responsible_id', '=', respId]);
        // }

        const respId = this.state.selectedResponsibleId === "" ? null : parseInt(this.state.selectedResponsibleId);
        if (respId) {
            domain.push('|');
            domain.push(['responsible_id', '=', respId]);
            domain.push(['support_ids', 'in', [respId]]);
        }

        const projId = this.state.selectedProjectId === "" ? null : parseInt(this.state.selectedProjectId);
        if (projId) {
            domain.push(['project_id', '=', projId]);
        }
        
        console.log("📋 Domaine appliqué pour état:", clickedLabel, domain);
        
        await this.action.doAction({
            name: `Tâches - ${clickedLabel}`,
            type: 'ir.actions.act_window',
            res_model: 'work.program',
            view_mode: 'kanban,form',
            views: [[false, 'kanban'], [false, 'form']],
            domain: domain,
            context: {
                'default_state': technicalState,
            },
            target: 'current'
        });
    } catch (error) {
        console.error("Erreur navigation état:", error);
    }
}


    async loadTableData(params) {
    try {
        console.log("Chargement des données du tableau...");
        const apiParams = {
            date_from: params.start_date,
            date_to: params.end_date,
            department_id: params.department_id ?? null,
            project_id: params.project_id ?? null,
            responsible_id: params.responsible_id ?? null
        };
        const result = await this.rpc("/dashboard/work_program_grid", apiParams);
        if (result.error) {
            console.error("Erreur lors du chargement du tableau:", result.message);
            this.state.tableData = [];
        } else {
            this.state.tableData = result.data;
            console.log("Données du tableau chargées:", result.data.length, "lignes");
        }
    } catch (error) {
        console.error("Erreur lors du chargement du tableau:", error);
        this.state.tableData = [];
    }
}



initializeGrid() {
    console.log("Initialisation de la grille AG Grid personnalisée...");
    console.log("Grid element:", this.gridRef.el);
    console.log("AG Grid disponible:", typeof agGrid !== 'undefined');

    if (!this.gridRef.el) {
        console.warn("Élément DOM de la table introuvable");
        this.state.error = "Erreur: Élément DOM de la grille introuvable";
        return;
    }
    if (typeof agGrid === 'undefined') {
        console.error("AG Grid n'est pas chargé");
        this.gridRef.el.innerHTML = '<div class="text-center p-4 text-red-500">AG Grid n\'est pas disponible</div>';
        this.state.error = "Erreur: AG Grid non chargé";
        return;
    }

    try {
        this.gridRef.el.innerHTML = '';

        const columnDefs = [
            {
                field: "project",
                headerName: "Projet",
                width: 400,
                filter: true,
                sortable: false,
                tooltipField: "project",
                cellClass: 'flex items-center '
            },
            {
                field: "description",
                headerName: "Description",
                width: 400,
                filter: true,
                sortable: false,
                tooltipField: "description",
                cellClass: 'flex items-center '
                // wrapText: true,
                // cellStyle: { 'white-space': 'normal' }
            },
            {
                field: "responsible_display",
                headerName: "Responsable",
                sortable: false,
                width: 380,
                filter: true,
                cellRenderer: (params) => {
                    const img = params.data.responsible_image
                        ? `<img src="${params.data.responsible_image}" alt="${params.data.responsible_display}" class="w-9 h-9 rounded-full object-cover border border-gray-300" onerror="this.style.display='none'">`
                        : `<div class="w-9 h-9 rounded-full bg-gray-200 flex items-center justify-center text-gray-500">👤</div>`;

                    const name = params.data.responsible_display || 'Non défini';
                    const dept = params.data.department_display || 'Département inconnu';

                    return `
                        <div class="flex items-center gap-3 h-full" style="">
                            ${img}
                            <div class="flex flex-col leading-tight">
                                <span class="font-medium text-gray-900">${name}</span>
                                <span class="text-xs text-gray-500">${dept}</span>
                            </div>
                        </div>
                    `;
                }
            },
            {
    field: "support",
    headerName: "Support",
    sortable: false,
    width: 250,
    cellClass: 'flex flex-wrap gap-2 items-center',
    // sortable: true,
    tooltipValueGetter: (params) => {
        if (!params.value || !params.value.length) return null;  // <-- retourne null si pas de support
        return Array.isArray(params.value) ? params.value.join(', ') : params.value;
    },
    cellRenderer: (params) => {
        if (!params.value || !params.value.length) return '';  // <-- rien si pas de support
        
        const supports = Array.isArray(params.value) ? params.value : params.value.split(', ');

        return supports.map(name => 
            `<span class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm inline-block">
                ${name}
            </span>`
        ).join(' ');
    },
    valueFormatter: (params) => params.value || ''   // <-- rien si pas de support
},


            {
                field: "start_date",
                headerName: "Date d'assignation",
                width: 230,
                cellClass: 'flex items-center justify-center text-gray-700',
                filter: 'agDateColumnFilter',
                valueFormatter: (params) => params.value || 'N/A'
            },
            {
                field: "due_date",
                headerName: "Date d'Échéance",
                width: 200,
                cellClass: 'flex items-center justify-center text-gray-700',
                 filter: 'agDateColumnFilter',
                valueFormatter: (params) => params.value || 'N/A'
            },
            {
                field: "completion_date",
                headerName: "Date de Fin",
                width: 200,
                cellClass: 'flex items-center justify-center text-gray-700',
                filter: 'agDateColumnFilter',
                valueFormatter: (params) => params.value || 'N/A'
            },
            {
    field: "priority",
    headerName: "Priorité",
    sortable: false,
    width: 150,
    filter: 'agTextColumnFilter',
    filterParams: {
        filterOptions: ['contains', 'equals'],
        textFormatter: (value) => {
            const priorityConfig = {
                'high': 'Haute',
                'medium': 'Moyenne',
                'low': 'Basse',
                'unknown': 'Inconnue'
            };
            const formattedValue = priorityConfig[value] || value || 'Inconnue';
            // Normalisation pour gérer les accents et la casse
            return formattedValue
                .normalize('NFD') // Décompose les caractères accentués
                .replace(/[\u0300-\u036f]/g, '') // Supprime les diacritiques
                .toLowerCase(); // Convertit en minuscules
        },
        textMatcher: ({ value, filterText }) => {
            if (!filterText) return true;
            const normalizedValue = value
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '')
                .toLowerCase();
            const normalizedFilterText = filterText
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '')
                .toLowerCase();
            return normalizedValue.includes(normalizedFilterText);
        },
        buttons: ['reset', 'apply'],
        closeOnApply: true,
        caseSensitive: false
    },
    cellRenderer: (params) => {
        const priority = params.value || 'unknown';
        const priorityConfig = {
            'high': { label: 'Haute', color: 'bg-red-100 text-red-800 border-red-200' },
            'medium': { label: 'Moyenne', color: 'bg-yellow-100 text-yellow-800 border-yellow-200' },
            'low': { label: 'Basse', color: 'bg-green-100 text-green-800 border-green-200' },
            'unknown': { label: 'Inconnue', color: 'bg-gray-100 text-gray-700 border-gray-300' }
        };
        const config = priorityConfig[priority] || { label: 'Inconnue', color: 'bg-gray-100 text-gray-700 border-gray-300' };
        return `
            <div class="flex items-center justify-center h-full">
                <span class="px-3 py-1 rounded-full text-xs font-semibold border ${config.color}">
                    ${config.label}
                </span>
            </div>
        `;
    },
    cellClass: 'flex items-center justify-center'
},
            {
    field: "complexity",
    headerName: "Complexité",
    sortable: false,
    width: 150,
    filter: 'agTextColumnFilter',
    filterParams: {
        filterOptions: ['contains', 'equals'],
        textFormatter: (value) => {
            const complexityConfig = {
                'high': 'Élevée',
                'medium': 'Moyenne',
                'low': 'Faible',
                'unknown': 'Inconnue'
            };
            const formattedValue = complexityConfig[value] || value || '';
            // Normalisation pour gérer les accents et la casse
            return formattedValue
                .normalize('NFD') // Décompose les caractères accentués
                .replace(/[\u0300-\u036f]/g, '') // Supprime les diacritiques
                .toLowerCase(); // Convertit en minuscules
        },
        textMatcher: ({ value, filterText }) => {
            if (!filterText) return true;
            const normalizedValue = value
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '')
                .toLowerCase();
            const normalizedFilterText = filterText
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '')
                .toLowerCase();
            return normalizedValue.includes(normalizedFilterText);
        },
        buttons: ['reset', 'apply'],
        closeOnApply: true,
        caseSensitive: false // Déjà présent, mais conservé pour clarté
    },
    cellRenderer: (params) => {
        const complexity = params.value || 'unknown';
        const complexityConfig = {
            'high': { label: 'Élevée', color: 'bg-red-100 text-red-800 border-red-200' },
            'medium': { label: 'Moyenne', color: 'bg-yellow-100 text-yellow-800 border-yellow-200' },
            'low': { label: 'Faible', color: 'bg-green-100 text-green-800 border-green-200' },
            'unknown': { label: 'Inconnue', color: 'bg-gray-100 text-gray-700 border-gray-300' }
        };
        const config = complexityConfig[complexity] || { label: 'Inconnue', color: 'bg-gray-100 text-gray-700 border-gray-300' };
        return `
            <div class="flex items-center justify-center h-full">
                <span class="px-3 py-1 rounded-full text-xs font-semibold border ${config.color}">
                    ${config.label}
                </span>
            </div>
        `;
    },
    cellClass: 'flex items-center justify-center'
},
    {
    field: "state",
    headerName: "État",
    width: 180,
    filter: 'agTextColumnFilter',
    filterParams: {
        textFormatter: (value) => {
            const statesConfig = {
                'incomplete': 'Inachevé',
                'cancelled': 'Annulé',
                'done': 'Terminé',
                'validated': 'Validé',
                'refused': 'Refusé',
                'to_validate': 'À valider',
                'draft': 'Brouillon',
                'ongoing': 'En cours',
                'to_redo': 'À refaire'
            };
            const formattedValue = statesConfig[value] || value || 'Inconnu';
            // Normalisation pour gérer les accents et la casse
            return formattedValue
                .normalize('NFD') // Décompose les caractères accentués
                .replace(/[\u0300-\u036f]/g, '') // Supprime les diacritiques
                .toLowerCase(); // Convertit en minuscules
        },
        textMatcher: ({ value, filterText }) => {
            if (!filterText) return true;
            const normalizedValue = value
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '')
                .toLowerCase();
            const normalizedFilterText = filterText
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '')
                .toLowerCase();
            return normalizedValue.includes(normalizedFilterText);
        },
        buttons: ['reset', 'apply'],
        closeOnApply: true,
        caseSensitive: false
    },
    cellRenderer: (params) => {
        const state = params.value || 'draft';
        const statesConfig = {
            'incomplete': { label: 'Inachevé', color: 'bg-gray-200 text-gray-800 border-gray-300' },
            'cancelled': { label: 'Annulé', color: 'bg-slate-200 text-slate-800 border-slate-300' },
            'done': { label: 'Terminé', color: 'bg-emerald-200 text-emerald-800 border-emerald-200' },
            'validated': { label: 'Validé', color: 'bg-green-200 text-green-800 border-green-200' },
            'refused': { label: 'Refusé', color: 'bg-red-200 text-red-800 border-red-200' },
            'to_validate': { label: 'À valider', color: 'bg-amber-200 text-amber-800 border-amber-200' },
            'draft': { label: 'Brouillon', color: 'bg-gray-200 text-gray-800 border-gray-300' },
            'ongoing': { label: 'En cours', color: 'bg-blue-200 text-blue-800 border-blue-200' },
            'to_redo': { label: 'À refaire', color: 'bg-orange-200 text-orange-800 border-orange-200' }
        };
        const config = statesConfig[state] || { label: 'Inconnu', color: 'bg-gray-100 text-gray-700 border-gray-300' };
        return `
            <div class="flex items-center justify-center h-full">
                <span class="px-3 py-1 rounded-full text-xs font-semibold border ${config.color}">
                    ${config.label}
                </span>
            </div>
        `;
    },
    cellClass: 'flex items-center justify-center'
}
        ];

        const gridOptions = {
            rowData: this.state.tableData,
            columnDefs: columnDefs,
            defaultColDef: {
                sortable: true,
                resizable: true,
                filter: 'agTextColumnFilter',
                minWidth: 150,
                filterParams: {
                    buttons: ['reset', 'apply'],
                    closeOnApply: true
                }
            },
            rowSelection: 'multiple',
            animateRows: true,
            rowHeight: 70,
            headerHeight: 55,
            pagination: true,
            paginationPageSize: 4,
            paginationPageSizeSelector: [4, 10, 20, 50],
            suppressRowClickSelection: true,
            suppressCellFocus: true,
            suppressColumnVirtualisation: false,
            suppressHorizontalScroll: false,
           getRowStyle: (params) => {
    // Zebra striping par défaut
    let style = {
        background: params.node.rowIndex % 2 === 0 ? '#FFFFFF' : '#F3F4F6'
    };

    // Couleurs et bordures pour les états spécifiques
    if (params.data.state === 'validated') {
        style.background = '#F0FDF4'; // vert clair
        style.borderLeft = '4px solid #16A34A';
    } else if (params.data.state === 'refused') {
        style.background = '#FEE2E2'; // rouge clair
        style.borderLeft = '4px solid #B91C1C';
    }

    return style;
},

            onGridReady: (params) => {
                console.log("✅ AG Grid personnalisée prête");
                this.gridApi = params.api;
                this.gridColumnApi = params.columnApi;
                this.gridInitialized = true;
                setTimeout(() => {
                    if (this.gridApi) {
                        this.gridApi.sizeColumnsToFit();
                    }
                }, 100);
            },
            onRowClicked: (event) => {
                console.log('Ligne cliquée:', event.data);
            }
        };

        this.destroyGrid();
        this.gridInstance = agGrid.createGrid(this.gridRef.el, gridOptions);
        console.log("✅ Grille AG Grid personnalisée créée avec succès");
    } catch (error) {
        console.error("Erreur lors de l'initialisation de la grille:", error);
        this.state.error = "Erreur: " + error.message;
        this.gridRef.el.innerHTML = `<div class="text-center p-4 text-red-500">Erreur d'initialisation de la grille: ${error.message}</div>`;
    }
}

updateGridData() {
    console.log("Mise à jour des données de la grille...", {
        hasGridApi: !!this.gridApi,
        dataLength: this.state.tableData.length,
        initialized: this.gridInitialized
    });
    if (!this.gridApi || !this.gridInitialized) {
        console.warn("Grille non initialisée, impossible de mettre à jour les données");
        return;
    }
    try {
        this.gridApi.setGridOption('rowData', this.state.tableData);
        console.log(`✅ Données mises à jour: ${this.state.tableData.length} lignes`);
        setTimeout(() => {
            if (this.gridApi) {
                this.gridApi.sizeColumnsToFit();
            }
        }, 100);
    } catch (error) {
        console.error("❌ Erreur lors de la mise à jour des données de la grille:", error);
        this.reinitializeGrid();
    }
}

reinitializeGrid() {
    console.log("Réinitialisation de la grille suite à une erreur...");
    this.destroyGrid();
    setTimeout(() => {
        this.initializeGrid();
    }, 100);
}

destroyGrid() {
    console.log("🗑️ Destruction de la grille...");
    if (this.gridInstance && typeof this.gridInstance.destroy === 'function') {
        this.gridInstance.destroy();
    }
    this.gridInstance = null;
    this.gridApi = null;
    this.gridColumnApi = null;
    this.gridInitialized = false;
    console.log("✅ Grille détruite");
}

debugGridState() {
    console.log("🔍 État de la grille:", {
        gridInitialized: this.gridInitialized,
        hasGridApi: !!this.gridApi,
        hasGridElement: !!this.gridRef.el,
        dataLength: this.state.tableData.length,
        currentFilters: {
            start_date: this.state.selectedStartDate,
            end_date: this.state.selectedEndDate,
            department: this.state.selectedDepartmentId,
            responsible: this.state.selectedResponsibleId
        }
    });
}

    formatValue(value) {
        if (value === '--' || value === null || value === undefined) return '--';
        return value.toString();
    }
}

UserKPIDashboard.template = "qc_dashboard.UserKPIDashboard";

registry.category('actions').add('qc_dashboard.action_user_dashboard', UserKPIDashboard);