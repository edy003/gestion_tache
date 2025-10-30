/**
 * Toggle Sidebar - JavaScript pour EmployeeEvaluationDashboard
 * Version adaptée pour la structure qc_dashboard
 */

odoo.define('qc_dashboard.sidebar_toggle', function (require) {
    'use strict';

    // Variables globales
    let sidebarCollapsed = false;
    let isInitialized = false;
    let currentToggleBtn = null;
    let observer = null;

    // Fonction pour toggle la sidebar
    function toggleSidebar() {
        const sidebar = document.querySelector('.qc_dashboard_sidebar');
        const header = document.querySelector('.qc_dashboard_header');
        const contentGrid = document.querySelector('.qc_content_grid');
        const toggleIcon = document.querySelector('.icon-menu');
        
        if (!sidebar) {
            console.warn('Sidebar introuvable');
            return;
        }

        sidebarCollapsed = !sidebarCollapsed;
        
        console.log('Toggle sidebar:', sidebarCollapsed ? 'collapsed' : 'expanded');
        
        // Basculer les classes pour la sidebar
        if (sidebarCollapsed) {
            sidebar.classList.add('collapsed');
        } else {
            sidebar.classList.remove('collapsed');
        }
        
        // Basculer les classes pour le header
        if (header) {
            if (sidebarCollapsed) {
                header.classList.add('expanded');
            } else {
                header.classList.remove('expanded');
            }
        }
        
        // Basculer les classes pour le content grid
        if (contentGrid) {
            if (sidebarCollapsed) {
                contentGrid.classList.add('expanded');
            } else {
                contentGrid.classList.remove('expanded');
            }
        }
        
        // Changer l'icône
        if (toggleIcon) {
            updateToggleIcon(toggleIcon, sidebarCollapsed);
        }
        
        // Sauvegarder l'état
        localStorage.setItem('qc_sidebar_collapsed', sidebarCollapsed);
        
        console.log('Sidebar state:', sidebarCollapsed ? 'collapsed' : 'expanded');
    }

    // Fonction pour mettre à jour l'icône
    function updateToggleIcon(iconElement, isCollapsed) {
        if (isCollapsed) {
            // Ajouter la classe collapsed pour afficher la flèche
            iconElement.classList.add('collapsed');
        } else {
            // Retirer la classe collapsed pour afficher le hamburger
            iconElement.classList.remove('collapsed');
        }
    }

    // Restaurer l'état sauvegardé
    function restoreSidebarState() {
        const savedState = localStorage.getItem('qc_sidebar_collapsed');
        if (savedState === 'true' && !sidebarCollapsed) {
            toggleSidebar();
        } else if (savedState === 'false' && sidebarCollapsed) {
            toggleSidebar();
        }
    }

    // Nettoyer les anciens événements
    function cleanup() {
        if (currentToggleBtn) {
            currentToggleBtn.removeEventListener('click', toggleSidebar);
            currentToggleBtn = null;
        }
        if (observer) {
            observer.disconnect();
            observer = null;
        }
    }

    // Attacher l'événement au bouton toggle
    function attachToggleEvent() {
        // Nettoyer d'abord
        cleanup();
        
        const toggleBtn = document.querySelector('.toggle_btn_container');
        if (toggleBtn && toggleBtn !== currentToggleBtn) {
            currentToggleBtn = toggleBtn;
            toggleBtn.addEventListener('click', toggleSidebar);
            console.log('Toggle button event attached');
            
            // Restaurer l'état après avoir attaché l'événement
            setTimeout(restoreSidebarState, 100);
            
            return true;
        }
        return false;
    }

    // Fonction principale d'initialisation
    function initializeDashboard() {
        const dashboard = document.querySelector('.qctracker_dashboard_container2');
        if (dashboard) {
            console.log('QC Dashboard détecté, initialisation...');
            attachToggleEvent();
            isInitialized = true;
            return true;
        }
        return false;
    }

    // Observer pour détecter les changements dans le DOM
    function startObserver() {
        if (observer) observer.disconnect();
        
        observer = new MutationObserver(function(mutations) {
            let shouldReinit = false;
            
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList') {
                    // Vérifier si c'est notre dashboard qui apparaît
                    const dashboard = document.querySelector('.qctracker_dashboard_container2');
                    if (dashboard && !document.querySelector('.toggle_btn_container.event-attached')) {
                        shouldReinit = true;
                    }
                    
                    // Vérifier si le bouton toggle a été supprimé
                    if (currentToggleBtn && !document.contains(currentToggleBtn)) {
                        console.log('Toggle button supprimé, nettoyage...');
                        currentToggleBtn = null;
                        isInitialized = false;
                    }
                }
            });
            
            if (shouldReinit) {
                console.log('Réinitialisation détectée');
                setTimeout(initializeDashboard, 50);
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    // Fonction de vérification périodique (fallback)
    function startPeriodicCheck() {
        const checkInterval = setInterval(function() {
            if (!isInitialized || !currentToggleBtn || !document.contains(currentToggleBtn)) {
                const dashboard = document.querySelector('.qctracker_dashboard_container2');
                if (dashboard) {
                    console.log('QC Dashboard trouvé via vérification périodique');
                    initializeDashboard();
                }
            }
        }, 1000);

        // Nettoyer après 30 secondes
        setTimeout(function() {
            clearInterval(checkInterval);
        }, 30000);
    }

    // Écouter les changements de hash/URL (navigation Odoo)
    function listenToNavigation() {
        // Écouter les changements d'historique
        const originalPushState = history.pushState;
        history.pushState = function() {
            originalPushState.apply(history, arguments);
            setTimeout(function() {
                if (document.querySelector('.qctracker_dashboard_container2')) {
                    console.log('Navigation détectée, réinitialisation...');
                    isInitialized = false;
                    initializeDashboard();
                }
            }, 500);
        };
        
        // Écouter les événements popstate
        window.addEventListener('popstate', function() {
            setTimeout(function() {
                if (document.querySelector('.qctracker_dashboard_container2')) {
                    console.log('Retour navigation détecté, réinitialisation...');
                    isInitialized = false;
                    initializeDashboard();
                }
            }, 500);
        });
    }

    // Initialisation principale
    $(document).ready(function() {
        console.log('Initialisation du QC Dashboard toggle sidebar...');
        
        // Récupérer l'état sauvegardé
        const savedState = localStorage.getItem('qc_sidebar_collapsed');
        sidebarCollapsed = savedState === 'true';
        
        // Démarrer l'initialisation
        if (!initializeDashboard()) {
            startObserver();
            startPeriodicCheck();
        }
        
        // Écouter la navigation
        listenToNavigation();
    });

    // Écouter les événements Odoo spécifiques
    $(document).on('DOMSubtreeModified', function() {
        // Fallback pour les anciens navigateurs
        if (!observer && document.querySelector('.qctracker_dashboard_container2') && !isInitialized) {
            initializeDashboard();
        }
    });

    // Fonction globale pour forcer la réinitialisation
    window.qcDashboardToggle = function() {
        if (currentToggleBtn) {
            toggleSidebar();
        } else {
            console.warn('Toggle button non initialisé');
            initializeDashboard();
        }
    };

    // Fonction pour forcer la réinitialisation
    window.qcDashboardReinit = function() {
        console.log('Réinitialisation forcée...');
        cleanup();
        isInitialized = false;
        initializeDashboard();
    };

    // Fonction pour tester le toggle depuis la console
    window.testToggle = function() {
        console.log('Test du toggle...');
        const btn = document.querySelector('.toggle_btn_container');
        if (btn) {
            btn.click();
        } else {
            console.log('Bouton toggle non trouvé');
        }
    };

    return {
        toggleSidebar: toggleSidebar,
        initializeDashboard: initializeDashboard
    };

});