/* ===== SPA Router & App Init ===== */
const App = (() => {
  let currentUser = null;

  const routes = {
    '#/login':      () => LoginPage.render(),
    '#/dashboard':  () => DashboardPage.render(),
    '#/logs':       () => LogsPage.render(),
    '#/files':      () => FilesPage.render(),
    '#/anomalies':  () => AnomaliesPage.render(),
    '#/clusters':   () => ClustersPage.render(),
    '#/settings':   () => SettingsPage.render(),
  };

  function getUser() {
    if (currentUser) return currentUser;
    const stored = localStorage.getItem('user');
    if (stored) {
      try { currentUser = JSON.parse(stored); } catch { currentUser = null; }
    }
    return currentUser;
  }

  function setUser(user) {
    currentUser = user;
    if (user) {
      localStorage.setItem('user', JSON.stringify(user));
    } else {
      localStorage.removeItem('user');
    }
  }

  function isAdmin() {
    const u = getUser();
    return u && u.role === 'admin';
  }

  function isLoggedIn() {
    return !!localStorage.getItem('token');
  }

  function logout() {
    localStorage.removeItem('token');
    setUser(null);
    window.location.hash = '#/login';
  }

  function navigate(hash) {
    window.location.hash = hash;
  }

  function updateSidebar() {
    const user = getUser();
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');

    if (!isLoggedIn()) {
      sidebar.style.display = 'none';
      mainContent.style.marginLeft = '0';
      return;
    }

    sidebar.style.display = 'flex';
    mainContent.style.marginLeft = '';

    // update user info
    const usernameEl = document.getElementById('sidebar-username');
    const roleEl = document.getElementById('sidebar-role');
    if (user && usernameEl) {
      usernameEl.textContent = user.username;
      roleEl.textContent = user.role;
    }

    // highlight active link
    document.querySelectorAll('.sidebar-nav a').forEach(a => {
      a.classList.toggle('active', a.getAttribute('href') === window.location.hash);
    });
  }

  function updateTopBar(title) {
    const titleEl = document.getElementById('page-title');
    const logoutBtn = document.getElementById('logout-btn');
    if (titleEl) titleEl.textContent = title || '';
    if (logoutBtn) logoutBtn.style.display = isLoggedIn() ? '' : 'none';
  }

  async function route() {
    const hash = window.location.hash || '#/login';

    if (!isLoggedIn() && hash !== '#/login') {
      window.location.hash = '#/login';
      return;
    }

    if (isLoggedIn() && hash === '#/login') {
      window.location.hash = '#/dashboard';
      return;
    }

    const handler = routes[hash] || routes['#/dashboard'];
    updateSidebar();
    handler();
  }

  // Toast system
  function toast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }

  function init() {
    window.addEventListener('hashchange', route);

    document.getElementById('logout-btn').addEventListener('click', logout);

    // load user info if logged in
    if (isLoggedIn() && !getUser()) {
      API.get('/auth/me').then(u => {
        setUser(u);
        updateSidebar();
      }).catch(() => logout());
    }

    route();
  }

  return { init, getUser, setUser, isAdmin, isLoggedIn, logout, navigate, toast, updateTopBar };
})();

document.addEventListener('DOMContentLoaded', App.init);
