/* ===== Files Page ===== */
const FilesPage = (() => {
  let page = 0;
  const limit = 20;

  async function render() {
    App.updateTopBar('Uploaded Files');
    const content = document.getElementById('page-content');

    let uploadSection = '';
    if (App.isAdmin()) {
      uploadSection = `
        <div class="upload-area" id="upload-area">
          <input type="file" id="file-input" accept=".log,.txt,.json">
          <p><strong>Click to upload</strong> a log file (.log, .txt, .json)</p>
        </div>`;
    }

    content.innerHTML = uploadSection + '<div id="files-table"><div class="loading"><div class="spinner"></div></div></div>';

    if (App.isAdmin()) attachUpload();
    await loadFiles();
  }

  function attachUpload() {
    const area = document.getElementById('upload-area');
    const input = document.getElementById('file-input');
    area.addEventListener('click', () => input.click());
    input.addEventListener('change', async () => {
      const file = input.files[0];
      if (!file) return;
      try {
        area.innerHTML = '<p>Uploading...</p>';
        await API.upload('/logs/upload', file);
        App.toast('File uploaded successfully', 'success');
        page = 0;
        await loadFiles();
      } catch (err) {
        App.toast(err.message, 'error');
      }
      // restore upload area
      area.innerHTML = `<input type="file" id="file-input" accept=".log,.txt,.json"><p><strong>Click to upload</strong> a log file (.log, .txt, .json)</p>`;
      attachUpload();
    });
  }

  async function loadFiles() {
    const container = document.getElementById('files-table');
    container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
      const data = await API.get('/logs/files', { offset: page * limit, limit });
      const items = data.items || data;
      const total = data.total ?? items.length;
      container.innerHTML = buildTable(items) + buildPagination(total);
      attachPaginationEvents(total);
    } catch (err) {
      container.innerHTML = `<div class="empty-state"><p>${esc(err.message)}</p></div>`;
    }
  }

  function statusBadge(status) {
    const map = { completed: 'badge-success', processing: 'badge-info', failed: 'badge-error', pending: 'badge-debug' };
    return `<span class="badge ${map[status] || 'badge-debug'}">${esc(status)}</span>`;
  }

  function buildTable(items) {
    if (!items.length) return '<div class="empty-state"><p>No files uploaded yet</p></div>';
    return `
      <div class="table-wrapper">
        <table>
          <thead><tr>
            <th>Filename</th><th>Status</th><th>Lines</th><th>Parsed</th><th>Failed</th><th>Uploaded</th>
          </tr></thead>
          <tbody>${items.map(f => `
            <tr>
              <td>${esc(f.filename)}</td>
              <td>${statusBadge(f.status)}</td>
              <td>${fmtNum(f.total_lines ?? '-')}</td>
              <td>${fmtNum(f.parsed_lines ?? '-')}</td>
              <td>${fmtNum(f.failed_lines ?? '-')}</td>
              <td>${fmtDate(f.uploaded_at)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  }

  function buildPagination(total) {
    const totalPages = Math.ceil(total / limit) || 1;
    return `
      <div class="pagination">
        <button id="fpg-prev" ${page === 0 ? 'disabled' : ''}>Prev</button>
        <span class="page-info">Page ${page + 1} of ${totalPages}</span>
        <button id="fpg-next" ${page + 1 >= totalPages ? 'disabled' : ''}>Next</button>
      </div>`;
  }

  function attachPaginationEvents(total) {
    const totalPages = Math.ceil(total / limit) || 1;
    document.getElementById('fpg-prev')?.addEventListener('click', () => { if (page > 0) { page--; loadFiles(); } });
    document.getElementById('fpg-next')?.addEventListener('click', () => { if (page + 1 < totalPages) { page++; loadFiles(); } });
  }

  return { render };
})();
