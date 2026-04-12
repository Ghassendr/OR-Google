/**
 * SIDEBAR COMPONENT
 * Centrally manages navigation, auth-aware links, and toggle state.
 */

window.SidebarComponent = {
    async init() {
        const container = document.getElementById('sidebar-container');
        if (!container) return;

        // 1. Fetch Auth Status
        let user = null;
        try {
            const resp = await fetch('/api/me');
            if (resp.ok) {
                const data = await resp.json();
                if (data.logged_in) user = data.user;
            }
        } catch (e) {
            console.warn('Sidebar: Auth check failed', e);
        }

        // 2. Build Sidebar HTML
        container.innerHTML = this.template(user);

        // 3. Attach Events
        this.attachEvents();

        // 4. Highlight Active Link
        this.highlightActive();

        // 5. Initialize State
        this.initSidebarState();
    },

    template(user) {
        const name = user ? user.full_name : 'Invité';
        const role = user ? user.role : 'PUBLIC';
        const initials = name.charAt(0).toUpperCase();

        // Get state from URL if present
        const params = new URLSearchParams(window.location.search);
        const currentBloc = params.get('bloc') || (window.bloc ? window.bloc : 'matin');
        const currentView = params.get('view') || (window.view ? window.view : 'salle');

        return `
            <div class="sidebar-overlay" id="sidebar-overlay" onclick="SidebarComponent.toggleMobile()"></div>
            
            <button class="mobile-menu-btn" onclick="SidebarComponent.toggleMobile()">
                <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/></svg>
            </button>
+
            <button class="sidebar-edge-tab" id="sidebar-edge-tab" onclick="SidebarComponent.toggle()" title="Rétracter / Étendre">
                <svg width="10" height="10" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>
            </button>

            <nav class="side-nav" id="side-nav">
                <div class="nav-logo">
                    <img src="/logo%20issat-small.jpg" alt="Logo">
                    <div class="nav-logo-text">
                        <h2>ISSAT<br>Sousse</h2>
                        <p>Examens 2026</p>
                    </div>
                </div>

                <div class="nav-links">
                    ${role === 'ADMIN' ? `
                    <div class="nav-section-label">Navigation</div>
                    <a href="/" class="nav-item" id="nav-home">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>
                        <span class="nav-item-label">Tableau de Bord</span>
                    </a>
                    <a href="/prof" class="nav-item" id="nav-prof">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
                        <span class="nav-item-label">Répertoire Académique</span>
                    </a>

                    <div class="nav-section-label">Administration</div>
                    <a href="/import-page" class="nav-item" id="nav-import" style="color:var(--gold)">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>
                        <span class="nav-item-label">Importer Données</span>
                    </a>
                    ` : ''}

                    ${role === 'PROFESSOR' ? `
                    <div class="nav-section-label">Mon Espace</div>
                    <a href="/prof" class="nav-item active" id="nav-mes-matieres">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5s3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/></svg>
                        <span class="nav-item-label">Mes Matières</span>
                    </a>
                    ` : ''}

                    ${(window.location.pathname === '/' || window.location.pathname.endsWith('report.html')) && role === 'ADMIN' ? `
                    <div class="nav-section-label">Bloc Actuel</div>
                    <a class="nav-item ${currentBloc === 'matin' ? 'selected' : ''}" id="btn-bloc-matin" onclick="SidebarComponent.updateURLState('bloc', 'matin')">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M12 3v1m0 16v1m8.66-13l-.87.5M4.21 17.5l-.87.5M20.66 17.5l-.87-.5M4.21 6.5l-.87-.5M21 12h-1M4 12H3"/><circle cx="12" cy="12" r="4"/></svg>
                        <span class="nav-item-label">Bloc Matin</span>
                    </a>
                    <a class="nav-item ${currentBloc === 'apmidi' ? 'selected' : ''}" id="btn-bloc-apmidi" onclick="SidebarComponent.updateURLState('bloc', 'apmidi')">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>
                        <span class="nav-item-label">Bloc Après-midi</span>
                    </a>

                    <div class="nav-section-label">Vues de Distribution</div>
                    <a class="nav-item ${currentView === 'salle' ? 'selected' : ''}" id="btn-view-salle" onclick="SidebarComponent.updateURLState('view', 'salle')">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>
                        <span class="nav-item-label">Par Salle</span>
                    </a>
                    <a class="nav-item ${currentView === 'filiere' ? 'selected' : ''}" id="btn-view-filiere" onclick="SidebarComponent.updateURLState('view', 'filiere')">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg>
                        <span class="nav-item-label">Par Filière</span>
                    </a>
                    <a class="nav-item ${currentView === 'db' ? 'selected' : ''}" id="btn-view-db" onclick="SidebarComponent.updateURLState('view', 'db')">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M4 7v10c0 2 1.5 3 3.5 3h9c2 0 3.5-1 3.5-3V7M4 7c0-2 1.5-3 3.5-3h9C18.5 4 20 5 20 7M4 7h16M12 11v6"/></svg>
                        <span class="nav-item-label">Vue DB</span>
                    </a>
                    <a class="nav-item ${currentView === 'calendrier' ? 'selected' : ''}" id="btn-view-calendrier" onclick="SidebarComponent.updateURLState('view', 'calendrier')">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
                        <span class="nav-item-label">Calendrier</span>
                    </a>
                    <a class="nav-item ${currentView === 'surveillance' ? 'selected' : ''}" id="nav-surveillance" onclick="SidebarComponent.updateURLState('view', 'surveillance')">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
                        <span class="nav-item-label">Surveillance</span>
                    </a>
                    ` : ''}

                    ${(window.location.pathname.includes('/prof') && role === 'ADMIN') ? `
                    <div class="nav-section-label">Vues Académiques</div>
                    <a class="nav-item ${currentView === 'professeurs' ? 'selected' : ''}" id="nav-professeurs" onclick="window.setView ? window.setView('professeurs') : null">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/></svg>
                        <span class="nav-item-label">Professeurs</span>
                    </a>
                    <a class="nav-item ${currentView === 'matieres' ? 'selected' : ''}" id="nav-matieres" onclick="window.setView ? window.setView('matieres') : null">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5s3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/></svg>
                        <span class="nav-item-label">Matières</span>
                    </a>
                    <a class="nav-item ${currentView === 'filieres' ? 'selected' : ''}" id="nav-filieres" onclick="window.setView ? window.setView('filieres') : null">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>
                        <span class="nav-item-label">Filières</span>
                    </a>
                    <a class="nav-item ${currentView === 'timetable' ? 'selected' : ''}" id="nav-timetable" onclick="window.setView ? window.setView('timetable') : null">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
                        <span class="nav-item-label">Emplois du temps</span>
                    </a>
                    <a class="nav-item ${currentView === 'relations' ? 'selected' : ''}" id="nav-relations" onclick="window.setView ? window.setView('relations') : null">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
                        <span class="nav-item-label">Relations &amp; Analyse</span>
                    </a>
                    <a class="nav-item ${currentView === 'surveillance' ? 'selected' : ''}" id="nav-surveillance-prof" onclick="window.setView ? window.setView('surveillance') : null">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
                        <span class="nav-item-label">Surveillance</span>
                    </a>
                    ` : ''}

                    <div class="nav-section-label">Session</div>
                    <a href="/login-page" class="nav-item" id="nav-login" style="${user ? 'display:none' : ''}">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
                        <span class="nav-item-label">Connexion</span>
                    </a>
                    <a href="/register-page" class="nav-item" id="nav-register" style="${user ? 'display:none' : ''}">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"/></svg>
                        <span class="nav-item-label">Inscription</span>
                    </a>
                </div>

                <div class="nav-footer">
                    <div class="user-profile">
                        <div class="user-avatar">${initials}</div>
                        <div class="user-info">
                            <div class="user-name">${name}</div>
                            <div class="user-role-badge">${role}</div>
                        </div>
                    </div>
                    ${user ? `
                    <button class="logout-btn" onclick="SidebarComponent.handleLogout()">
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
                        <span class="logout-btn-label">Déconnexion</span>
                    </button>
                    ` : ''}
                </div>
            </nav>
        `;
    },

    updateURLState(key, value) {
        const url = new URL(window.location.href);
        url.searchParams.set(key, value);
        
        const isDashboard = window.location.pathname === '/' || window.location.pathname === '' || window.location.pathname.endsWith('report.html');
        
        if (!isDashboard) {
            // Redirect back to home with the selected parameters
            window.location.href = '/' + url.search;
            return;
        }

        window.history.pushState({}, '', url);
        
        // If we are on report.html and the functions exist, call them
        if (key === 'bloc' && window.setBloc) window.setBloc(value);
        if (key === 'view' && window.setView) window.setView(value);
        
        // Re-init sidebar to update active classes
        this.init();
    },

    toggle() {
        const nav = document.getElementById('side-nav');
        const collapsed = nav.classList.toggle('collapsed');
        document.body.classList.toggle('sidebar-collapsed', nav.classList.contains('collapsed'));
        
        // Match standard body class if used elsewhere
        if (nav.classList.contains('collapsed')) {
            document.body.classList.add('sidebar-collapsed');
        } else {
            document.body.classList.remove('sidebar-collapsed');
        }

        localStorage.setItem('sidebar-collapsed', nav.classList.contains('collapsed') ? '1' : '0');
    },

    toggleMobile() {
        document.getElementById('side-nav').classList.toggle('mobile-open');
        document.getElementById('sidebar-overlay').classList.toggle('active');
    },

    highlightActive() {
        const path = window.location.pathname;
        let activeId = 'nav-home';
        if (path.includes('/prof')) activeId = 'nav-prof';
        if (path.includes('/import')) activeId = 'nav-import';
        if (path.includes('/login')) activeId = 'nav-login';
        if (path.includes('/register')) activeId = 'nav-register';
        
        // If professor, they might only have nav-mes-matieres
        if (document.getElementById('nav-mes-matieres')) {
            activeId = 'nav-mes-matieres';
        }
        
        const el = document.getElementById(activeId);
        if (el) el.classList.add('active');
    },

    initSidebarState() {
        if (localStorage.getItem('sidebar-collapsed') === '1') {
            const nav = document.getElementById('side-nav');
            if (nav) nav.classList.add('collapsed');
            document.body.classList.add('sidebar-collapsed');
        }
    },

    async handleLogout() {
        try {
            await fetch('/logout', { method: 'POST' });
            window.location.href = '/login-page';
        } catch (e) {
            console.error('Logout failed', e);
        }
    },

    attachEvents() {
        // Handle back/forward buttons
        window.onpopstate = () => {
            const params = new URLSearchParams(window.location.search);
            if (window.setBloc && params.get('bloc')) window.setBloc(params.get('bloc'));
            if (window.setView && params.get('view')) window.setView(params.get('view'));
            this.init();
        };
    }
};

// Auto-init when script is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => window.SidebarComponent.init());
} else {
    window.SidebarComponent.init();
}
