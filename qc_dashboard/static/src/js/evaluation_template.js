/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";

const { Component } = owl;
const { useState, onMounted, onWillUnmount, useRef } = owl.hooks;

export class EmployeeEvaluationDashboard extends Component {
    setup() {
        console.log("Initialisation du composant EmployeeEvaluationDashboard principal");

        this.state = useState({
            // État de chargement global
            loading: false,
            error: null,

            // NOUVEAU: État de la sidebar
            sidebarCollapsed: false,

            // Filtres sélectionnés
            selectedYear: new Date().getFullYear(),
            selectedMonth: null,
            selectedDepartmentId: null,
            selectedResponsibleId: null,

            // Options pour les filtres
            availableYears: [],
            availableMonths: [],
            availableDepartments: [],
            availableEmployees: [],

            // Filtres en cascade
            monthsForYear: [],
            employeesForDepartment: [],

            // Données des KPIs avec évolution
            deadlineCompliance: '--',
            deadlineEvolution: null,

            satisfactionRate: '--',
            satisfactionEvolution: null,

            complexResolution: '--',
            complexEvolution: null,
            
            priorityResolution: '--',
            priorityEvolution: null,

            isManagerOrAdmin: false,

            employee: {
                id: null,
                name: null,
                department: null,
                image_url: null,
                role: null
            },

            employeeDisplay: {
    display_name: 'Sélectionner des filtres',
    department_name: 'Tous les départements',
    profile_image: null,
    score: 0,
    category: 'Non évalué',
    is_global: true
},

            // Données des graphiques
            chartData: {
                priorityDeadlineChart: { labels: [], values: [] },
                complexityDeadlineChart: { labels: [], values: [], task_counts: [] },
                monthlyDeadlineChart: { months: [], pct_on_time: [], pct_late: [], count_on_time: [], count_late: [] } 
            }
        });

        this.rpc = useService("rpc");
        this.orm = useService("orm");
        this.user = useService("user");
        this.priorityChartRef = useRef("priority-deadline-chart");
        this.complexityChartRef = useRef("complexity-deadline-chart");
        this.monthlyChartRef = useRef("monthly-deadline-chart");

    

        // Noms des mois pour la conversion (synchronisé avec le contrôleur Python)
        this.monthNames = [
            'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
            'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'
        ];

        onMounted(async () => {
            await this.checkUserPermissions();
            await this.loadInitialData();
            // this.initializeSidebar();
            // this.setupResizeObserver();
        });

        onWillUnmount(() => {
            // this.cleanup();
        });
    }

   async getCurrentEmployeeId() {
    try {
        const userId = this.user.userId; // ✅ MODIFIER ICI
        console.log("User ID récupéré:", userId);
        
        const employee = await this.orm.searchRead(
            "hr.employee",
            [['user_id', '=', userId]], // ✅ MODIFIER ICI
            ['id'],
            { limit: 1 }
        );
        
        const empId = employee.length > 0 ? employee[0].id : null;
        console.log("Employee ID trouvé:", empId);
        return empId;
    } catch (error) {
        console.error("Erreur lors de la récupération de l'ID de l'employé connecté:", error);
        return null;
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

async loadInitialData() {
    this.state.loading = true;
    try {
        console.log("Chargement des données initiales...");

        // ✅ Récupérer l'ID de l'employé connecté AVANT tout
        const currentEmployeeId = await this.getCurrentEmployeeId();
        
        // ✅ Si pas manager/admin, définir l'employé connecté comme filtre par défaut
        if (!this.state.isManagerOrAdmin && currentEmployeeId) {
            this.state.selectedResponsibleId = currentEmployeeId;
            console.log("Employé connecté défini comme filtre:", currentEmployeeId);
        }

        await Promise.all([
            this.loadAvailableYears(),
            this.loadDepartments(),
            this.loadEmployees(),
            this.loadEmployeeInfo()
        ]);

        await this.loadMonthsForYear(this.state.selectedYear);

        // ✅ Charger TOUTES les données (y compris employeeDisplay) en une fois
        await this.loadAllData();

    } catch (error) {
        console.error("Erreur lors du chargement initial:", error);
        this.state.error = error.message;
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

    async loadAvailableYears() {
        try {
            const tasks = await this.orm.searchRead("work.program", [
                ['assignment_date', '!=', false]
            ], ["assignment_date"]);
            
            const years = new Set();

            tasks.forEach(task => {
                if (task.assignment_date) {
                    try {
                        const year = parseInt(task.assignment_date.split('-')[0]);
                        if (!isNaN(year)) {
                            years.add(year);
                        }
                    } catch (e) {
                        console.warn(`Date invalide pour la tâche ${task.id}: ${task.assignment_date}`);
                    }
                }
            });

            this.state.availableYears = Array.from(years).sort((a, b) => b - a);
            console.log("Années disponibles:", this.state.availableYears);
            
            if (this.state.availableYears.length > 0 && 
                !this.state.availableYears.includes(this.state.selectedYear)) {
                this.state.selectedYear = this.state.availableYears[0];
            }
        } catch (error) {
            console.error("Erreur lors du chargement des années:", error);
            this.state.error = "Erreur lors du chargement des années: " + error.message;
        }
    }

    async loadMonthsForYear(year) {
        try {
            let domain = [['assignment_date', '!=', false]];
            
            if (year) {
                const yearStart = `${year}-01-01`;
                const yearEnd = `${year}-12-31`;
                domain.push(['assignment_date', '>=', yearStart]);
                domain.push(['assignment_date', '<=', yearEnd]);
            }

            const tasks = await this.orm.searchRead("work.program", domain, ["assignment_date"]);
            const monthsSet = new Set();

            tasks.forEach(task => {
                if (task.assignment_date) {
                    try {
                        const dateParts = task.assignment_date.split('-');
                        if (dateParts.length === 3) {
                            const month = parseInt(dateParts[1]) - 1;
                            if (month >= 0 && month <= 11) {
                                const monthName = this.monthNames[month];
                                monthsSet.add(monthName);
                            }
                        }
                    } catch (e) {
                        console.warn(`Date invalide: ${task.assignment_date}`);
                    }
                }
            });

            const sortedMonths = Array.from(monthsSet).sort((a, b) => {
                const indexA = this.monthNames.indexOf(a);
                const indexB = this.monthNames.indexOf(b);
                return indexA - indexB;
            });

            this.state.monthsForYear = sortedMonths;
            console.log(`Mois disponibles pour ${year || 'toutes années'}:`, this.state.monthsForYear);
            
            if (this.state.selectedMonth && !this.state.monthsForYear.includes(this.state.selectedMonth)) {
                this.state.selectedMonth = null;
            }
            
        } catch (error) {
            console.error("Erreur lors du chargement des mois:", error);
            this.state.monthsForYear = [];
        }
    }

    async loadDepartments() {
        try {
            const departments = await this.orm.searchRead("hr.department", [], ["name"]);
            this.state.availableDepartments = departments.sort((a, b) => a.name.localeCompare(b.name));
            console.log("Départements chargés:", departments.length);
        } catch (error) {
            console.error("Erreur lors du chargement des départements:", error);
            this.state.availableDepartments = [];
        }
    }

    async loadEmployees() {
        try {
            const employees = await this.orm.searchRead("hr.employee", [
                ['active', '=', true]
            ], ["name"]);
            
            this.state.availableEmployees = employees.sort((a, b) => a.name.localeCompare(b.name));
            this.state.employeesForDepartment = this.state.availableEmployees;
            console.log("Employés chargés:", employees.length);
        } catch (error) {
            console.error("Erreur lors du chargement des employés:", error);
            this.state.availableEmployees = [];
            this.state.employeesForDepartment = [];
        }
    }

    async loadEmployeesForDepartment(departmentId) {
        if (!departmentId) {
            this.state.employeesForDepartment = this.state.availableEmployees;
            return;
        }

        try {
            const employees = await this.orm.searchRead("hr.employee", [
                ["department_id", "=", departmentId],
                ['active', '=', true]
            ], ["name"]);
            
            this.state.employeesForDepartment = employees.sort((a, b) => a.name.localeCompare(b.name));
            console.log(`Employés pour département ${departmentId}:`, employees.length);
            
            if (this.state.selectedResponsibleId) {
                const employeeExists = this.state.employeesForDepartment.find(
                    emp => emp.id === this.state.selectedResponsibleId
                );
                if (!employeeExists) {
                    this.state.selectedResponsibleId = null;
                }
            }
        } catch (error) {
            console.error("Erreur lors du chargement des employés par département:", error);
            this.state.employeesForDepartment = [];
        }
    }

    // ===== MÉTHODES DE CHARGEMENT DES DONNÉES =====
    async loadAllData() {
        console.log("Chargement de toutes les données...");

        const params = {
            year: this.state.selectedYear || null,
            month: this.state.selectedMonth,
            department_id: this.state.selectedDepartmentId,
            responsible_id: this.state.selectedResponsibleId
        };

        console.log("Paramètres envoyés au serveur:", params);
        await Promise.all([
            this.loadKPIData(params),
            this.loadChartData(params),
            this.loadEmployeeDisplay(params)
        ]);
        
        setTimeout(() => {
            this.renderChart();
        }, 200);
    }

    async loadChartData(params) {
        try {
            console.log("Chargement des données des graphiques...");
            await Promise.all([
                this.loadPriorityDeadlineChart(params),
                this.loadComplexityDeadlineChart(params),
                this.loadMonthlyDeadlineChart(params)
            ]);
        } catch (error) {
            console.error("Erreur lors du chargement des graphiques:", error);
        }
    }


async loadEmployeeDisplay(params = null) {
    try {
        // ✅ Si pas de paramètres, construire avec les filtres actuels
        if (!params) {
            params = {
                year: this.state.selectedYear || null,
                month: this.state.selectedMonth,
                department_id: this.state.selectedDepartmentId,
                responsible_id: this.state.selectedResponsibleId
            };
        }

        console.log("Chargement employeeDisplay avec params:", params);

        const result = await this.rpc("/dashboard/employee_performance", params);

        if (result.error) {
            console.error("Erreur:", result.message);
            Object.assign(this.state.employeeDisplay, {
                display_name: 'Erreur',
                department_name: 'Erreur',
                profile_image: null,
                category: 'Erreur',
                is_global: true
            });
        } else {
            console.log("Résultat employeeDisplay:", result);
            // ✅ Forcer la réactivité avec Object.assign
            Object.assign(this.state.employeeDisplay, result);
        }
    } catch (error) {
        console.error("Erreur lors du chargement:", error);
        Object.assign(this.state.employeeDisplay, {
            display_name: 'Erreur',
            department_name: 'Erreur',
            profile_image: null,
            category: 'Erreur',
            is_global: true
        });
    }
}

    async loadPriorityDeadlineChart(params) {
        try {
            console.log("Chargement du graphique respect des délais par priorité...");
            const result = await this.rpc("/dashboard/work_program_priority_deadline_chart", params);

            if (result.error) {
                console.error("Erreur lors du chargement du graphique priorités:", result.message);
                this.state.chartData.priorityDeadlineChart = { labels: [], values: [] };
            } else {
                this.state.chartData.priorityDeadlineChart = result.chart_data;
                console.log("Données du pie chart priorités chargées:", result.chart_data);
            }
        } catch (error) {
            console.error("Erreur lors du chargement du graphique priorités:", error);
            this.state.chartData.priorityDeadlineChart = { labels: [], values: [] };
        }
    }

    async loadComplexityDeadlineChart(params) {
        try {
            console.log("Chargement du graphique respect des délais par complexité...");
            const result = await this.rpc("/dashboard/work_program_complexity_deadline_chart", params);

            if (result.error) {
                console.error("Erreur lors du chargement du graphique complexité:", result.message);
                this.state.chartData.complexityDeadlineChart = { labels: [], values: [], task_counts: [] };
            } else {
                this.state.chartData.complexityDeadlineChart = result.chart_data;
                console.log("Données du pie chart complexité chargées:", result.chart_data);
            }
        } catch (error) {
            console.error("Erreur lors du chargement du graphique complexité:", error);
            this.state.chartData.complexityDeadlineChart = { labels: [], values: [], task_counts: [] };
        }
    }

    async loadMonthlyDeadlineChart(params) {
        try {
            console.log("Chargement du graphique mensuel des délais...");
            const result = await this.rpc("/dashboard/work_program_monthly_deadline_chart", params);

            if (result.error) {
                console.error("Erreur lors du chargement du graphique mensuel:", result.message);
                this.state.chartData.monthlyDeadlineChart = { months: [], pct_on_time: [], pct_late: [], count_on_time: [], count_late: [] };
            } else {
                this.state.chartData.monthlyDeadlineChart = result.chart_data;
                console.log("Données du bar chart mensuel chargées:", result.chart_data);
            }
        } catch (error) {
            console.error("Erreur lors du chargement du graphique mensuel:", error);
            this.state.chartData.monthlyDeadlineChart = { months: [], pct_on_time: [], pct_late: [], count_on_time: [], count_late: [] };
        }
    }

    async loadKPIData(params) {
        try {
            console.log("Chargement des données KPI...");

            const [deadlineResult, satisfactionResult, complexResult, priorityResult] = await Promise.all([
                this.rpc("/dashboard/work_program_deadline_compliance", params),
                this.rpc("/dashboard/work_program_satisfaction_rate", params),
                this.rpc("/dashboard/work_program_complex_resolution", params),
                this.rpc("/dashboard/work_program_priority_resolution", params)
            ]);

            // KPI: Respect des délais avec évolution
            if (deadlineResult.error) {
                console.error("Erreur deadline:", deadlineResult.message);
                this.state.deadlineCompliance = '--';
                this.state.deadlineEvolution = null;
            } else {
                this.state.deadlineCompliance = deadlineResult.deadline_compliance;
                this.state.deadlineEvolution = deadlineResult.evolution;
            }

            // KPI: Taux de satisfaction élevé avec évolution
            if (satisfactionResult.error) {
                console.error("Erreur satisfaction:", satisfactionResult.message);
                this.state.satisfactionRate = '--';
                this.state.satisfactionEvolution = null;
            } else {
                this.state.satisfactionRate = satisfactionResult.satisfaction_rate;
                this.state.satisfactionEvolution = satisfactionResult.evolution;
            }
            
            // KPI: Résolution des problèmes complexes avec évolution
            if (complexResult.error) {
                console.error("Erreur complex resolution:", complexResult.message);
                this.state.complexResolution = '--';
                this.state.complexEvolution = null;
            } else {
                this.state.complexResolution = complexResult.complex_resolution;
                this.state.complexEvolution = complexResult.evolution;
            }    
            
            // KPI: Résolution des tâches prioritaires avec évolution
            if (priorityResult.error) {
                console.error("Erreur priority resolution:", priorityResult.message);
                this.state.priorityResolution = '--';
                this.state.priorityEvolution = null;
            } else {
                this.state.priorityResolution = priorityResult.priority_resolution;
                this.state.priorityEvolution = priorityResult.evolution;
            }

        } catch (error) {
            console.error("Erreur lors du chargement des KPIs:", error);
            this.state.error = "Erreur lors du chargement des KPIs: " + error.message;
            
            // Réinitialiser en cas d'erreur
            this.state.deadlineCompliance = '--';
            this.state.deadlineEvolution = null;
            this.state.satisfactionRate = '--';
            this.state.satisfactionEvolution = null;
            this.state.complexResolution = '--';
            this.state.complexEvolution = null;
            this.state.priorityResolution = '--';
            this.state.priorityEvolution = null;
        }
    }

    // ===== MÉTHODES DE RENDU DES GRAPHIQUES (SIMPLIFIÉES) =====
    renderChart() {
        console.log("Rendu de tous les graphiques...");
        this.renderPriorityDeadlineChart();
        this.renderComplexityDeadlineChart();
        this.renderMonthlyDeadlineChart();
    }


    renderPriorityDeadlineChart() {
    console.log("Tentative de rendu du pie chart priorités...", {
        priorityChartRef: this.priorityChartRef.el,
        hasData: this.state.chartData.priorityDeadlineChart.labels.length > 0,
        data: this.state.chartData.priorityDeadlineChart
    });

    if (!this.priorityChartRef.el) {
        console.warn("Élément DOM du pie chart priorités introuvable");
        return;
    }

         if (typeof Plotly !== 'undefined') {
        try {
            Plotly.purge( this.priorityChartRef.el);  // ← Bonne référence
        } catch (e) {
            console.warn("Erreur lors du nettoyage Plotly:", e);
        }
    }
    this.priorityChartRef.el.innerHTML = '';  // ← Bonne référence

    if (!this.state.chartData.priorityDeadlineChart.labels.length) {
        console.warn("Aucune donnée pour le pie chart priorités");
        this.priorityChartRef.el.innerHTML = '<div class="text-center p-4 text-gray-500">Aucune donnée à afficher pour les filtres sélectionnés</div>';
        return;
    }

    if (typeof Plotly === 'undefined') {
        console.warn("Plotly non disponible pour le pie chart priorités");
        return;
    }

    try {
        const data = [{
            values: this.state.chartData.priorityDeadlineChart.task_counts, // ✅ nombre de tâches terminées à temps
            labels: this.state.chartData.priorityDeadlineChart.labels,
            customdata: this.state.chartData.priorityDeadlineChart.values,  // ✅ taux (%) dans customdata
            type: 'pie',
            hole: 0.4,
            marker: {
                colors: ['#FF9999', '#FFCC66', '#66B2FF'] // Palette différente de la complexité
            },
            textinfo: 'label+values', // Label + nombre de tâches
            textposition: 'none',
            hovertemplate:
                '<b>%{label}</b><br>' +
                'Tâches terminées à temps: %{value}<br>' +
                'Taux de respect: %{customdata}%<br>' +
                // 'Part du total: %{percent}<br>' +
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

        Plotly.newPlot(this.priorityChartRef.el, data, layout, config);
        console.log("✅ Pie chart priorités rendu avec succès");

    } catch (error) {
        console.error("❌ Erreur lors du rendu du pie chart priorités:", error);
    }
}

   
    renderComplexityDeadlineChart() {
    console.log("Tentative de rendu du pie chart complexité...", {
        complexityChartRef: this.complexityChartRef.el,
        hasData: this.state.chartData.complexityDeadlineChart.labels.length > 0,
        data: this.state.chartData.complexityDeadlineChart
    });

    if (!this.complexityChartRef.el) {
        console.warn("Élément DOM du pie chart complexité introuvable");
        return;
    }

     if (typeof Plotly !== 'undefined') {
        try {
            Plotly.purge( this.complexityChartRef.el);  // ← Bonne référence
        } catch (e) {
            console.warn("Erreur lors du nettoyage Plotly:", e);
        }
    }
    this.complexityChartRef.el.innerHTML = '';  // ← Bonne référence

    if (!this.state.chartData.complexityDeadlineChart.labels.length) {
        console.warn("Aucune donnée pour le pie chart complexité");
        this.complexityChartRef.el.innerHTML = '<div class="text-center p-4 text-gray-500">Aucune donnée à afficher pour les filtres sélectionnés</div>';
        return;
    }

    if (typeof Plotly === 'undefined') {
        console.warn("Plotly non disponible pour le pie chart complexité");
        return;
    }

    try {
        const data = [{
            values: this.state.chartData.complexityDeadlineChart.task_counts, // UTILISE task_counts comme valeurs
            labels: this.state.chartData.complexityDeadlineChart.labels,
            customdata: this.state.chartData.complexityDeadlineChart.values, // Pourcentages dans customdata
            type: 'pie',
            hole: 0.4,
            marker: {
                colors: ['#98FB98', '#FFD700', '#FF6347'] // Couleurs différentes pour distinguer de priorité
            },
            textinfo: 'label+values', // Affiche le label et le nombre
            textposition: 'none',
            hovertemplate: '<b>%{label}</b><br>' +
                          'Tâches terminées à temps: %{value}<br>' +
                          'Taux de respect: %{customdata}%<br>' +
                        //   'Part du total: %{percent}<br>' +
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
        console.log("Pie chart complexité rendu avec succès");

    } catch (error) {
        console.error("Erreur lors du rendu du pie chart complexité:", error);
    }
}

renderMonthlyDeadlineChart(isReset = false) {
    console.log("Tentative de rendu du bar chart mensuel...", {
        chartRef: this.monthlyChartRef.el,
        hasData: this.state.chartData.monthlyDeadlineChart.months?.length > 0,
        isReset: isReset,
        data: this.state.chartData.monthlyDeadlineChart
    });

    if (!this.monthlyChartRef.el) {
        console.warn("Élément DOM du bar chart mensuel introuvable");
        return;
    }

    // ✅ Nettoyage Plotly
    if (typeof Plotly !== 'undefined') {
        try {
            Plotly.purge(this.monthlyChartRef.el);
        } catch (e) {
            console.warn("Erreur lors du nettoyage Plotly:", e);
        }
    }

    // ✅ Ne pas afficher "Aucune donnée" si c'est un reset (les données arrivent)
    if (!this.state.chartData.monthlyDeadlineChart.months?.length && !isReset) {
        console.warn("Aucune donnée pour le bar chart mensuel");
        this.monthlyChartRef.el.innerHTML = '<div class="text-center p-4 text-gray-500">Aucune donnée à afficher pour les filtres sélectionnés</div>';
        return;
    }

    // ✅ Si reset et pas de données, juste vider
    if (!this.state.chartData.monthlyDeadlineChart.months?.length && isReset) {
        this.monthlyChartRef.el.innerHTML = '';
        return;
    }

    if (typeof Plotly === 'undefined') {
        console.warn("Plotly non disponible pour le bar chart mensuel");
        this.monthlyChartRef.el.innerHTML = '<div class="text-center p-4 text-gray-500">Plotly non disponible</div>';
        return;
    }

    try {
        const data = [
            {
                x: this.state.chartData.monthlyDeadlineChart.months,
                y: this.state.chartData.monthlyDeadlineChart.pct_on_time,
                name: 'Dans les délais',
                type: 'bar',
                marker: { color: '#22C55E' },
                text: this.state.chartData.monthlyDeadlineChart.pct_on_time.map(pct => `${pct}%`),
                textposition: 'outside',
                hovertemplate: '<b>%{x}</b><br>Dans les délais: %{y}%<extra></extra>'
            },
            {
                x: this.state.chartData.monthlyDeadlineChart.months,
                y: this.state.chartData.monthlyDeadlineChart.pct_late,
                name: 'En retard / Non terminées',
                type: 'bar',
                marker: { color: '#EF4444' },
                text: this.state.chartData.monthlyDeadlineChart.pct_late.map(pct => `${pct}%`),
                textposition: 'outside',
                hovertemplate: '<b>%{x}</b><br>En retard/Non terminées: %{y}%<extra></extra>'
            }
        ];

        const layout = {
            paper_bgcolor: '#FFFFFF',
            plot_bgcolor: '#FFFFFF',
            margin: { t: 0, r: 0, b: 20, l: 0 },
            barmode: 'group',
            xaxis: { 
                title: 'Mois',
                tickangle: 0,
                font: { family: 'Inter, sans-serif' }
            },
            yaxis: { 
                title: 'Pourcentage des tâches (%)',
                font: { family: 'Inter, sans-serif' }
            },
            legend: {
                orientation: 'h',
                y: 1.2,
                xanchor: 'center',
                x: 0.5
            },
            font: { family: 'Inter, sans-serif' }
        };

        const config = {
            displayModeBar: false,
            displaylogo: false,
            responsive: true
        };

        this.monthlyChartRef.el.innerHTML = '';
        
        Plotly.newPlot(this.monthlyChartRef.el, data, layout, config);
        console.log("Bar chart mensuel rendu avec succès");
        
    } catch (error) {
        console.error("Erreur lors du rendu du bar chart mensuel:", error);
        this.monthlyChartRef.el.innerHTML = '<div class="text-center p-4 text-red-500">Erreur lors du rendu</div>';
    }
}
    // Remplacez votre méthode getCategoryColor par celle-ci
getCategoryColor(category) {
    const colors = {
        'À risque': 'bg-red-700 hover:bg-red-800',
        'Satisfaisant': 'bg-yellow-600 hover:bg-yellow-700', 
        'Performant': 'bg-blue-700 hover:bg-blue-800',
        'Haut potentiel': 'bg-green-700 hover:bg-green-800',
        'Non évalué': 'bg-gray-600 hover:bg-gray-700',
        'Aucune donnée': 'bg-gray-600 hover:bg-gray-700',
        'Aucune tâche évaluable': 'bg-gray-600 hover:bg-gray-700',
        'Erreur': 'bg-red-700 hover:bg-red-800'
    };
    return colors[category] || 'bg-gray-600 hover:bg-gray-700';
}
    getProfileImageSrc() {
    if (this.state.employeeDisplay.profile_image) {
        return `data:image/png;base64,${this.state.employeeDisplay.profile_image}`;
    }
    return null;
}
    getEvolutionClass(evolution) {
        if (!evolution || evolution.trend === 'neutral') return 'text-gray-500';
        return evolution.trend === 'up' ? 'text-green-500' : 'text-red-500';
    }

    getEvolutionIcon(evolution) {
        if (!evolution || evolution.trend === 'neutral') return '';
        return evolution.trend === 'up' ? '↗' : '↘';
    }

    formatCompliance(value) {
        if (value === '--' || value === null || value === undefined) return '--';
        return `${value}%`;
    }

    formatEvolution(evolution) {
        if (!evolution || !evolution.display) return '';
        return evolution.display;
    }

    formatPreviousPeriod(evolution) {
        if (!evolution || !evolution.previous_period) return '';
        return `par rapport à ${evolution.previous_period}`;
    }

    // ===== GESTIONNAIRES D'ÉVÉNEMENTS =====
    async onYearChange(event) {
        const yearValue = event.target.value;
        const year = yearValue === "" ? null : parseInt(yearValue);
        console.log("Changement d'année vers:", year);

        this.state.selectedYear = year;
        this.state.selectedMonth = null;

        await this.loadMonthsForYear(year);
    }

    async onMonthChange(event) {
        const month = event.target.value || null;
        console.log("Changement de mois vers:", month);
        this.state.selectedMonth = month;
    }

    async onDepartmentChange(event) {
        const deptId = parseInt(event.target.value) || null;
        console.log("Changement de département vers:", deptId);

        this.state.selectedDepartmentId = deptId;
        this.state.selectedResponsibleId = null;

        await this.loadEmployeesForDepartment(deptId);
    }

    onResponsibleChange(event) {
        const respId = parseInt(event.target.value) || null;
        console.log("Changement de responsable vers:", respId);
        this.state.selectedResponsibleId = respId;
    }

    async onApplyFilters() {
        console.log("Application des filtres...");
        this.state.loading = true;
        this.state.error = null;

        try {
            await this.loadAllData();
            console.log("Filtres appliqués avec succès");
        } catch (error) {
            console.error("Erreur lors de l'application des filtres:", error);
            this.state.error = error.message;
        } finally {
            this.state.loading = false;
        }
    }

    async onResetFilters() {
        console.log("Réinitialisation des filtres...");
        this.state.loading = true;

        try {
            const currentYear = new Date().getFullYear();
            this.state.selectedYear = this.state.availableYears.includes(currentYear) 
                ? currentYear 
                : (this.state.availableYears[0] || null);
            this.state.selectedMonth = null;
            this.state.selectedDepartmentId = null;
            this.state.selectedResponsibleId = null;
            this.renderMonthlyDeadlineChart(true);

            await this.loadMonthsForYear(this.state.selectedYear);
            this.state.employeesForDepartment = this.state.availableEmployees;
            await this.loadAllData();

            console.log("Filtres réinitialisés avec succès");
        } catch (error) {
            console.error("Erreur lors de la réinitialisation:", error);
            this.state.error = error.message;
        } finally {
            this.state.loading = false;
        }
    }
}

EmployeeEvaluationDashboard.template = "qc_dashboard.EmployeeEvaluationDashboard";
registry.category('actions').add('qc_dashboard.action_employee_dashboard', EmployeeEvaluationDashboard);



