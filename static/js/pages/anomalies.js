/* ===== Anomalies Page ===== */
const AnomaliesPage = (() => {
  let page = 0;
  const limit = 20;

  async function render() {
    App.updateTopBar('Anomalies');
    const content = document.getElementById('page-content');
    content.innerHTML = '<div id="anomalies-list"><div class="loading"><div class="spinner"></div></div></div>';
    await loadAnomalies();
  }

  async function loadAnomalies() {
    const container = document.getElementById('anomalies-list');
    container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
      const data = await API.get('/analytics/anomalies', { offset: page * limit, limit });
      const items = data.items || data;
      const total = data.total ?? items.length;
      container.innerHTML = buildTable(items) + buildPagination(total);
      attachPaginationEvents(total);
    } catch (err) {
      container.innerHTML = `<div class="empty-state"><p>${esc(err.message)}</p></div>`;
    }
  }

  function scoreBar(score) {
    const pct = Math.round((score || 0) * 100);
    let color = 'var(--success)';
    if (pct > 70) color = 'var(--error)';
    else if (pct > 40) color = 'var(--warning)';
    return `
      <div class="score-bar">
        <div class="score-track">
          <div class="score-fill" style="width:${pct}%; background:${color}"></div>
        </div>
        <span class="score-value" style="color:${color}">${pct}%</span>
      </div>`;
  }

  function buildTable(items) {
    if (!items.length) return '<div class="empty-state"><p>No anomalies detected yet</p></div>';
    return `
      <div class="table-wrapper">
        <table>
          <thead><tr>
            <th>ID</th><th>Window</th><th>Score</th><th>Description</th><th>Detected</th>
          </tr></thead>
          <tbody>${items.map(a => `
            <tr>
              <td>${a.id}</td>
              <td>${fmtDate(a.window_start)} &mdash; ${fmtDate(a.window_end)}</td>
              <td>${scoreBar(a.score)}</td>
              <td class="msg-cell" title="${esc(a.description)}">${esc(a.description || '-')}</td>
              <td>${fmtDate(a.created_at)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  }

  function buildPagination(total) {
    const totalPages = Math.ceil(total / limit) || 1;
    return `
      <div class="pagination">
        <button id="apg-prev" ${page === 0 ? 'disabled' : ''}>Prev</button>
        <span class="page-info">Page ${page + 1} of ${totalPages}</span>
        <button id="apg-next" ${page + 1 >= totalPages ? 'disabled' : ''}>Next</button>
      </div>`;
  }

  function attachPaginationEvents(total) {
    const totalPages = Math.ceil(total / limit) || 1;
    document.getElementById('apg-prev')?.addEventListener('click', () => { if (page > 0) { page--; loadAnomalies(); } });
    document.getElementById('apg-next')?.addEventListener('click', () => { if (page + 1 < totalPages) { page++; loadAnomalies(); } });
  }

  return { render };
})();
