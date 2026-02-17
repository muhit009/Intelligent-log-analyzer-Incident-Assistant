/* ===== Settings Page ===== */
const SettingsPage = (() => {
  async function render() {
    App.updateTopBar('Settings');
    const content = document.getElementById('page-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    try {
      const [user, keys] = await Promise.all([
        API.get('/auth/me'),
        API.get('/auth/api-keys'),
      ]);
      App.setUser(user);
      content.innerHTML = buildPage(user, keys);
      attachEvents();
    } catch (err) {
      content.innerHTML = `<div class="empty-state"><p>${esc(err.message)}</p></div>`;
    }
  }

  function buildPage(user, keys) {
    return `
      <div class="settings-section">
        <h3>Profile</h3>
        <dl class="profile-info">
          <dt>Username</dt><dd>${esc(user.username)}</dd>
          <dt>Email</dt><dd>${esc(user.email || '-')}</dd>
          <dt>Role</dt><dd><span class="badge ${user.role === 'admin' ? 'badge-error' : 'badge-info'}">${esc(user.role)}</span></dd>
          <dt>Created</dt><dd>${fmtDate(user.created_at)}</dd>
        </dl>
      </div>

      <div class="settings-section">
        <h3>API Keys</h3>
        <div style="margin-bottom:12px;">
          <button class="btn btn-primary btn-sm" id="create-key-btn">Create API Key</button>
        </div>
        <div id="api-key-created" style="display:none; margin-bottom:12px; padding:12px; background:var(--bg-tertiary); border-radius:8px;">
          <p style="font-size:13px; margin-bottom:6px; color:var(--warning);">Save this key now — you won't see it again!</p>
          <code id="new-key-value" style="font-size:14px; color:var(--success); word-break:break-all;"></code>
        </div>
        <div id="api-keys-table">${buildKeysTable(keys)}</div>
      </div>

      ${App.isAdmin() ? buildCreateUserSection() : ''}
    `;
  }

  function buildKeysTable(keys) {
    if (!keys.length) return '<div class="empty-state"><p>No API keys</p></div>';
    return `
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Name</th><th>Prefix</th><th>Status</th><th>Created</th><th></th></tr></thead>
          <tbody>${keys.map(k => `
            <tr>
              <td>${esc(k.name)}</td>
              <td><code>${esc(k.key_prefix)}...</code></td>
              <td><span class="badge ${k.is_active ? 'badge-success' : 'badge-error'}">${k.is_active ? 'Active' : 'Revoked'}</span></td>
              <td>${fmtDate(k.created_at)}</td>
              <td>${k.is_active ? `<button class="btn btn-danger btn-sm revoke-btn" data-id="${k.id}">Revoke</button>` : ''}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  }

  function buildCreateUserSection() {
    return `
      <div class="settings-section">
        <h3>Create User (Admin)</h3>
        <form id="create-user-form" style="display:flex; flex-wrap:wrap; gap:10px; align-items:flex-end;">
          <div class="filter-group">
            <label>Username</label>
            <input type="text" id="new-username" required>
          </div>
          <div class="filter-group">
            <label>Email</label>
            <input type="email" id="new-email">
          </div>
          <div class="filter-group">
            <label>Password</label>
            <input type="password" id="new-password" required>
          </div>
          <div class="filter-group">
            <label>Role</label>
            <select id="new-role">
              <option value="viewer">Viewer</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div class="filter-group" style="align-self:flex-end">
            <button type="submit" class="btn btn-primary">Create</button>
          </div>
        </form>
      </div>`;
  }

  function attachEvents() {
    // Create API key
    document.getElementById('create-key-btn')?.addEventListener('click', async () => {
      const name = prompt('API key name:');
      if (!name) return;
      try {
        const result = await API.post('/auth/api-keys', { name });
        document.getElementById('new-key-value').textContent = result.raw_key;
        document.getElementById('api-key-created').style.display = 'block';
        App.toast('API key created', 'success');
        // refresh keys list
        const keys = await API.get('/auth/api-keys');
        document.getElementById('api-keys-table').innerHTML = buildKeysTable(keys);
        attachRevokeEvents();
      } catch (err) {
        App.toast(err.message, 'error');
      }
    });

    attachRevokeEvents();

    // Create user form
    document.getElementById('create-user-form')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        await API.post('/auth/users', {
          username: document.getElementById('new-username').value.trim(),
          email: document.getElementById('new-email').value.trim() || null,
          password: document.getElementById('new-password').value,
          role: document.getElementById('new-role').value,
        });
        App.toast('User created', 'success');
        document.getElementById('create-user-form').reset();
      } catch (err) {
        App.toast(err.message, 'error');
      }
    });
  }

  function attachRevokeEvents() {
    document.querySelectorAll('.revoke-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        if (!confirm('Revoke this API key?')) return;
        try {
          await API.del(`/auth/api-keys/${btn.dataset.id}`);
          App.toast('API key revoked', 'success');
          const keys = await API.get('/auth/api-keys');
          document.getElementById('api-keys-table').innerHTML = buildKeysTable(keys);
          attachRevokeEvents();
        } catch (err) {
          App.toast(err.message, 'error');
        }
      });
    });
  }

  return { render };
})();
