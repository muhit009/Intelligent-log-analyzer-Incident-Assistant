/* ===== Login Page ===== */
const LoginPage = (() => {
  function render() {
    App.updateTopBar('');
    const content = document.getElementById('page-content');
    content.innerHTML = `
      <div class="login-page">
        <div class="login-box">
          <h1>Log Analyzer</h1>
          <p class="subtitle">Sign in to your account</p>
          <div id="login-error" class="login-error"></div>
          <form id="login-form">
            <div class="form-group">
              <label for="username">Username</label>
              <input type="text" id="username" placeholder="Enter username" required autocomplete="username">
            </div>
            <div class="form-group">
              <label for="password">Password</label>
              <input type="password" id="password" placeholder="Enter password" required autocomplete="current-password">
            </div>
            <button type="submit" class="btn btn-primary">Sign In</button>
          </form>
        </div>
      </div>`;

    document.getElementById('login-form').addEventListener('submit', handleLogin);
  }

  async function handleLogin(e) {
    e.preventDefault();
    const errEl = document.getElementById('login-error');
    errEl.style.display = 'none';

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;

    try {
      const data = await API.post('/auth/login', { username, password });
      localStorage.setItem('token', data.access_token);

      const user = await API.get('/auth/me');
      App.setUser(user);
      App.navigate('#/dashboard');
    } catch (err) {
      errEl.textContent = err.message;
      errEl.style.display = 'block';
    }
  }

  return { render };
})();
