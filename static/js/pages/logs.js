/* ===== Log Explorer Page ===== */
const LogsPage = (() => {
  let page = 0;
  const limit = 50;

  async function render() {
    App.updateTopBar('Log Explorer');
    const content = document.getElementById('page-content');
    content.innerHTML = buildFilters() + '<div id="logs-table"><div class="loading"><div class="spinner"></div></div></div>';
    attachFilterEvents();
    await loadLogs();
  }

  function buildFilters() {
    return `
      <div class="filter-bar" id="log-filters">
        <div class="filter-group">
          <label>Level</label>
          <select id="f-level">
            <option value="">All</option>
            <option value="ERROR">ERROR</option>
            <option value="WARNING">WARNING</option>
            <option value="INFO">INFO</option>
            <option value="DEBUG">DEBUG</option>
          </select>
        </div>
        <div class="filter-group">
          <label>Service</label>
          <input type="text" id="f-service" placeholder="e.g. api-gateway">
        </div>
        <div class="filter-group">
          <label>Keyword</label>
          <input type="text" id="f-keyword" placeholder="Search message...">
        </div>
        <div class="filter-group">
          <label>Start</label>
          <input type="datetime-local" id="f-start">
        </div>
        <div class="filter-group">
          <label>End</label>
          <input type="datetime-local" id="f-end">
        </div>
        <div class="filter-group" style="align-self:flex-end">
          <button class="btn btn-primary" id="apply-filters">Apply</button>
        </div>
      </div>`;
  }

  function attachFilterEvents() {
    document.getElementById('apply-filters').addEventListener('click', () => {
      page = 0;
      loadLogs();
    });
  }

  function getFilters() {
    const params = { offset: page * limit, limit };
    const level = document.getElementById('f-level')?.value;
    const service = document.getElementById('f-service')?.value.trim();
    const keyword = document.getElementById('f-keyword')?.value.trim();
    const start = document.getElementById('f-start')?.value;
    const end = document.getElementById('f-end')?.value;

    if (level) params.level = level;
    if (service) params.service = service;
    if (keyword) params.keyword = keyword;
    if (start) params.start = new Date(start).toISOString();
    if (end) params.end = new Date(end).toISOString();
    return params;
  }

  async function loadLogs() {
    const container = document.getElementById('logs-table');
    container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
      const data = await API.get('/logs', getFilters());
      const items = data.items || data;
      const total = data.total ?? items.length;
      container.innerHTML = buildTable(items) + buildPagination(total);
      attachPaginationEvents(total);
    } catch (err) {
      container.innerHTML = `<div class="empty-state"><p>${esc(err.message)}</p></div>`;
    }
  }

  function levelBadge(level) {
    const cls = { ERROR: 'badge-error', WARNING: 'badge-warning', WARN: 'badge-warning', INFO: 'badge-info', DEBUG: 'badge-debug' };
    return `<span class="badge ${cls[level] || 'badge-debug'}">${esc(level)}</span>`;
  }

  function buildTable(items) {
    if (!items.length) return '<div class="empty-state"><p>No log entries found</p></div>';
    return `
      <div class="table-wrapper">
        <table>
          <thead><tr>
            <th>Timestamp</th><th>Level</th><th>Service</th><th>Message</th>
          </tr></thead>
          <tbody>${items.map(i => `
            <tr>
              <td>${fmtDate(i.timestamp)}</td>
              <td>${levelBadge(i.level || '')}</td>
              <td>${esc(i.service || '-')}</td>
              <td class="msg-cell" title="${esc(i.message)}">${esc(i.message)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  }

  function buildPagination(total) {
    const totalPages = Math.ceil(total / limit) || 1;
    return `
      <div class="pagination">
        <button id="pg-prev" ${page === 0 ? 'disabled' : ''}>Prev</button>
        <span class="page-info">Page ${page + 1} of ${totalPages}</span>
        <button id="pg-next" ${page + 1 >= totalPages ? 'disabled' : ''}>Next</button>
      </div>`;
  }

  function attachPaginationEvents(total) {
    const totalPages = Math.ceil(total / limit) || 1;
    document.getElementById('pg-prev')?.addEventListener('click', () => { if (page > 0) { page--; loadLogs(); } });
    document.getElementById('pg-next')?.addEventListener('click', () => { if (page + 1 < totalPages) { page++; loadLogs(); } });
  }

  return { render };
})();
