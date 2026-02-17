/* ===== Error Clusters Page ===== */
const ClustersPage = (() => {
  let page = 0;
  const limit = 20;

  async function render() {
    App.updateTopBar('Error Clusters');
    const content = document.getElementById('page-content');
    content.innerHTML = '<div id="clusters-list"><div class="loading"><div class="spinner"></div></div></div>';
    await loadClusters();
  }

  async function loadClusters() {
    const container = document.getElementById('clusters-list');
    container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
      const data = await API.get('/analytics/clusters', { offset: page * limit, limit });
      const items = data.items || data;
      const total = data.total ?? items.length;
      container.innerHTML = buildCards(items) + buildPagination(total);
      attachPaginationEvents(total);
    } catch (err) {
      container.innerHTML = `<div class="empty-state"><p>${esc(err.message)}</p></div>`;
    }
  }

  function buildCards(items) {
    if (!items.length) return '<div class="empty-state"><p>No error clusters found</p></div>';
    return `<div class="cluster-grid">${items.map(c => `
      <div class="cluster-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span class="cluster-count">${fmtNum(c.count)} occurrences</span>
          <span class="badge badge-error">Cluster #${c.label ?? c.id}</span>
        </div>
        <div class="cluster-msg">${esc(c.example_message)}</div>
        <div class="cluster-keywords">
          ${(c.keywords || '').split(',').filter(Boolean).map(k => `<span>${esc(k.trim())}</span>`).join('')}
        </div>
        <div class="cluster-meta">
          First seen: ${fmtDate(c.first_seen)} &mdash; Last seen: ${fmtDate(c.last_seen)}
        </div>
      </div>`).join('')}</div>`;
  }

  function buildPagination(total) {
    const totalPages = Math.ceil(total / limit) || 1;
    return `
      <div class="pagination">
        <button id="cpg-prev" ${page === 0 ? 'disabled' : ''}>Prev</button>
        <span class="page-info">Page ${page + 1} of ${totalPages}</span>
        <button id="cpg-next" ${page + 1 >= totalPages ? 'disabled' : ''}>Next</button>
      </div>`;
  }

  function attachPaginationEvents(total) {
    const totalPages = Math.ceil(total / limit) || 1;
    document.getElementById('cpg-prev')?.addEventListener('click', () => { if (page > 0) { page--; loadClusters(); } });
    document.getElementById('cpg-next')?.addEventListener('click', () => { if (page + 1 < totalPages) { page++; loadClusters(); } });
  }

  return { render };
})();
