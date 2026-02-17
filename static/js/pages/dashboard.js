/* ===== Dashboard Page ===== */
const DashboardPage = (() => {
  let chartInstances = [];

  function destroyCharts() {
    chartInstances.forEach(c => c.destroy());
    chartInstances = [];
  }

  async function render() {
    App.updateTopBar('Dashboard');
    destroyCharts();

    const content = document.getElementById('page-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading stats...</p></div>';

    // Fetch all endpoints in parallel
    let stats = null, anomalies = null, clusters = null, logs = null;

    try {
      const results = await Promise.allSettled([
        API.get('/stats/summary'),
        API.get('/analytics/anomalies', { limit: 100 }),
        API.get('/analytics/clusters', { limit: 20 }),
        API.get('/logs', { limit: 200 })
      ]);

      stats     = results[0].status === 'fulfilled' ? results[0].value : null;
      anomalies = results[1].status === 'fulfilled' ? results[1].value : null;
      clusters  = results[2].status === 'fulfilled' ? results[2].value : null;
      logs      = results[3].status === 'fulfilled' ? results[3].value : null;

      console.log('[Dashboard] stats:', stats);
      console.log('[Dashboard] anomalies:', anomalies, 'items:', extractList(anomalies).length);
      console.log('[Dashboard] clusters:', clusters, 'items:', extractList(clusters).length);
      console.log('[Dashboard] logs:', logs, 'items:', extractList(logs).length);

      if (results[1].status === 'rejected') console.warn('[Dashboard] anomalies failed:', results[1].reason);
      if (results[2].status === 'rejected') console.warn('[Dashboard] clusters failed:', results[2].reason);
      if (results[3].status === 'rejected') console.warn('[Dashboard] logs failed:', results[3].reason);
    } catch (e) {
      console.error('[Dashboard] unexpected error:', e);
    }

    if (!stats) {
      content.innerHTML = '<div class="empty-state"><p>Failed to load dashboard stats.</p></div>';
      return;
    }

    content.innerHTML = buildDashboard(stats, anomalies, clusters, logs);
    initCharts(stats, anomalies, clusters, logs);
    attachEvents();
  }

  function extractList(response) {
    if (!response) return [];
    if (Array.isArray(response)) return response;
    if (Array.isArray(response.items)) return response.items;
    return [];
  }

  function buildDashboard(s, anomalies, clusters, logs) {
    const totalEntries = s.total_entries || 0;
    const totalFiles = s.total_files || 0;
    const levels = s.level_breakdown || [];
    const services = s.top_services || [];

    const errorCount = levels.find(l => l.level === 'ERROR')?.count || 0;
    const warnCount = levels.find(l => l.level === 'WARNING' || l.level === 'WARN')?.count || 0;

    const anomalyList = extractList(anomalies);
    const clusterList = extractList(clusters);
    const logList = extractList(logs);
    const hasAnomalies = anomalyList.length > 0;
    const hasClusters = clusterList.length > 0;
    const hasLogs = logList.length > 0;
    const hasAnalytics = hasAnomalies || hasClusters;

    // Analytics action bar — always show if admin
    const analyticsBar = App.isAdmin() ? `
      <div class="card" style="margin-bottom:24px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px;">
        <div>
          <strong style="font-size:15px;">ML Analytics</strong>
          <span style="color:var(--text-secondary); font-size:13px; margin-left:8px;">
            ${hasAnalytics
              ? `${anomalyList.length} anomaly windows, ${clusterList.length} error clusters detected`
              : 'No analytics data yet — run the pipeline to detect anomalies and cluster errors'}
          </span>
        </div>
        <button class="btn btn-primary" id="run-analytics-btn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16" style="margin-right:4px">
            <polygon points="5 3 19 12 5 21 5 3"/>
          </svg>
          Run Analytics
        </button>
      </div>` : (!hasAnalytics ? `
      <div class="card" style="margin-bottom:24px; text-align:center; color:var(--text-secondary); font-size:13px; padding:16px;">
        No analytics data yet — ask an admin to run the ML pipeline
      </div>` : '');

    return `
      <!-- Row 1: Stat Cards -->
      <div class="card-grid">
        <div class="stat-card info">
          <div class="stat-label">Total Log Entries</div>
          <div class="stat-value">${fmtNum(totalEntries)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Files Processed</div>
          <div class="stat-value">${fmtNum(totalFiles)}</div>
        </div>
        <div class="stat-card error">
          <div class="stat-label">Errors</div>
          <div class="stat-value">${fmtNum(errorCount)}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">Warnings</div>
          <div class="stat-value">${fmtNum(warnCount)}</div>
        </div>
      </div>

      ${analyticsBar}

      <!-- Row 2: Log Level Doughnut + Top Services -->
      <div class="chart-section">
        <div class="chart-card">
          <h3>Log Level Breakdown</h3>
          ${levels.length
            ? '<canvas id="chart-level-doughnut"></canvas>'
            : '<div class="chart-empty"><p>No log data</p></div>'}
        </div>
        <div class="chart-card">
          <h3>Top Services</h3>
          ${services.length
            ? '<canvas id="chart-services-bar"></canvas>'
            : '<div class="chart-empty"><p>No service data</p></div>'}
        </div>
      </div>

      <!-- Row 3: Log Volume Over Time + Severity Radar -->
      <div class="chart-section">
        <div class="chart-card">
          <h3>Log Volume Timeline</h3>
          ${hasLogs
            ? '<canvas id="chart-log-timeline"></canvas>'
            : levels.length
              ? '<canvas id="chart-level-bar-fallback"></canvas>'
              : '<div class="chart-empty"><p>No log entries found</p></div>'}
        </div>
        <div class="chart-card">
          <h3>Severity Radar</h3>
          ${levels.length >= 2
            ? '<canvas id="chart-severity-radar"></canvas>'
            : '<div class="chart-empty"><p>Need at least 2 log levels</p></div>'}
        </div>
      </div>

      <!-- Row 4: Anomaly Score Timeline + Error Rate & Volume -->
      <div class="chart-section">
        <div class="chart-card">
          <h3>Anomaly Score Timeline</h3>
          ${hasAnomalies
            ? '<canvas id="chart-anomaly-timeline"></canvas>'
            : '<div class="chart-empty"><p>No anomaly data — click "Run Analytics" above</p></div>'}
        </div>
        <div class="chart-card">
          <h3>Error Rate & Event Volume</h3>
          ${hasAnomalies
            ? '<canvas id="chart-error-volume"></canvas>'
            : '<div class="chart-empty"><p>No anomaly data — click "Run Analytics" above</p></div>'}
        </div>
      </div>

      <!-- Row 5: Log Composition Over Time + Anomaly Score Distribution -->
      <div class="chart-section">
        <div class="chart-card">
          <h3>Log Composition Over Time</h3>
          ${hasAnomalies
            ? '<canvas id="chart-log-composition"></canvas>'
            : '<div class="chart-empty"><p>No anomaly data — click "Run Analytics" above</p></div>'}
        </div>
        <div class="chart-card">
          <h3>Anomaly Score Distribution</h3>
          ${hasAnomalies
            ? '<canvas id="chart-score-distribution"></canvas>'
            : '<div class="chart-empty"><p>No anomaly data — click "Run Analytics" above</p></div>'}
        </div>
      </div>

      <!-- Row 6: Top Error Clusters + Service Activity -->
      <div class="chart-section">
        <div class="chart-card">
          <h3>Top Error Clusters</h3>
          ${hasClusters
            ? '<canvas id="chart-clusters"></canvas>'
            : '<div class="chart-empty"><p>No cluster data — click "Run Analytics" above</p></div>'}
        </div>
        <div class="chart-card">
          <h3>Service Activity Over Time</h3>
          ${hasAnomalies
            ? '<canvas id="chart-service-activity"></canvas>'
            : '<div class="chart-empty"><p>No anomaly data — click "Run Analytics" above</p></div>'}
        </div>
      </div>`;
  }

  /* ===== Run Analytics Button ===== */
  function attachEvents() {
    const btn = document.getElementById('run-analytics-btn');
    if (!btn) return;

    btn.addEventListener('click', async () => {
      btn.disabled = true;
      btn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px;margin-right:6px;display:inline-block;vertical-align:middle;"></div> Running...';

      try {
        await API.post('/analytics/run');
        App.toast('Analytics pipeline started! Refreshing in a few seconds...', 'success');

        // Poll until data appears (check every 3s, up to 60s)
        let attempts = 0;
        const poll = setInterval(async () => {
          attempts++;
          try {
            const check = await API.get('/analytics/anomalies', { limit: 1 });
            const items = extractList(check);
            if (items.length > 0 || attempts >= 20) {
              clearInterval(poll);
              render(); // re-render dashboard with new data
            }
          } catch {
            if (attempts >= 20) clearInterval(poll);
          }
        }, 3000);
      } catch (err) {
        App.toast('Failed to start analytics: ' + err.message, 'error');
        btn.disabled = false;
        btn.innerHTML = 'Run Analytics';
      }
    });
  }

  /* ===== Chart.js Initialization ===== */
  function initCharts(stats, anomalies, clusters, logs) {
    Chart.defaults.color = '#7a7f96';
    Chart.defaults.borderColor = 'rgba(162,89,255,0.07)';
    Chart.defaults.font.family = 'Inter, sans-serif';

    const anomalyList = extractList(anomalies);
    const clusterList = extractList(clusters);
    const logList = extractList(logs);
    const levels = stats?.level_breakdown || [];
    const services = stats?.top_services || [];

    // Stats-based charts (always available if logs exist)
    if (levels.length > 0) initLevelDoughnut(levels);
    if (services.length > 0) initServicesBar(services);
    if (levels.length >= 2) initSeverityRadar(levels);

    // Log-entry-based charts
    if (logList.length > 0) {
      initLogTimeline(logList);
    } else if (levels.length > 0) {
      // Fallback: show a vertical bar chart of levels if we couldn't fetch log entries
      initLevelBarFallback(levels);
    }

    // Analytics-based charts (only if analytics have been run)
    if (anomalyList.length > 0) {
      initAnomalyTimeline(anomalyList);
      initErrorVolume(anomalyList);
      initLogComposition(anomalyList);
      initScoreDistribution(anomalyList);
      initServiceActivity(anomalyList);
    }
    if (clusterList.length > 0) {
      initClustersBar(clusterList);
    }
  }

  /* ============================================
     CHARTS THAT ALWAYS WORK (stats-based)
     ============================================ */

  function initLevelDoughnut(levels) {
    const canvas = document.getElementById('chart-level-doughnut');
    if (!canvas) return;

    const colorMap = {
      ERROR: '#f43f5e', WARNING: '#f59e0b', WARN: '#f59e0b',
      INFO: '#38bdf8', DEBUG: '#5c6178'
    };

    const labels = levels.map(l => l.level);
    const data = levels.map(l => l.count);
    const colors = levels.map(l => colorMap[l.level] || '#a259ff');
    const total = data.reduce((s, v) => s + v, 0);

    const chart = new Chart(canvas.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{ data, backgroundColor: colors, borderColor: '#111320', borderWidth: 2, hoverOffset: 6 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '65%',
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 12, padding: 14 } },
          tooltip: { ...tooltipStyle(), callbacks: {
            label: (item) => `${item.label}: ${fmtNum(item.raw)} (${((item.raw / total) * 100).toFixed(1)}%)`
          }}
        }
      },
      plugins: [{
        id: 'centerText',
        afterDraw(chart) {
          const { ctx, chartArea: { top, bottom, left, right } } = chart;
          const cx = (left + right) / 2, cy = (top + bottom) / 2;
          ctx.save();
          ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
          ctx.font = '700 22px Inter, sans-serif'; ctx.fillStyle = '#d8dce8';
          ctx.fillText(fmtNum(total), cx, cy - 8);
          ctx.font = '500 11px Inter, sans-serif'; ctx.fillStyle = '#5c6178';
          ctx.fillText('TOTAL', cx, cy + 12);
          ctx.restore();
        }
      }]
    });
    chartInstances.push(chart);
  }

  function initServicesBar(services) {
    const canvas = document.getElementById('chart-services-bar');
    if (!canvas) return;

    const labels = services.map(s => s.service || 'unknown');
    const data = services.map(s => s.count);

    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, ctx.canvas.width, 0);
    gradient.addColorStop(0, 'rgba(162, 89, 255, 0.7)');
    gradient.addColorStop(1, 'rgba(108, 43, 217, 0.4)');

    const chart = new Chart(ctx, {
      type: 'bar',
      data: { labels, datasets: [{ label: 'Log Entries', data, backgroundColor: gradient, borderColor: 'rgba(162,89,255,0.5)', borderWidth: 1, borderRadius: 4 }] },
      options: {
        responsive: true, maintainAspectRatio: false, indexAxis: 'y',
        plugins: { legend: { display: false }, tooltip: tooltipStyle() },
        scales: {
          x: { grid: { color: 'rgba(162,89,255,0.05)' } },
          y: { grid: { display: false }, ticks: { font: { size: 11 } } }
        }
      }
    });
    chartInstances.push(chart);
  }

  function initSeverityRadar(levels) {
    const canvas = document.getElementById('chart-severity-radar');
    if (!canvas) return;

    const labels = levels.map(l => l.level);
    const data = levels.map(l => l.count);
    const pointColors = levels.map(l => {
      const map = { ERROR: '#f43f5e', WARNING: '#f59e0b', WARN: '#f59e0b', INFO: '#38bdf8', DEBUG: '#5c6178' };
      return map[l.level] || '#a259ff';
    });

    const chart = new Chart(canvas.getContext('2d'), {
      type: 'radar',
      data: {
        labels,
        datasets: [{
          label: 'Log Count', data,
          backgroundColor: 'rgba(162, 89, 255, 0.15)', borderColor: '#a259ff', borderWidth: 2,
          pointBackgroundColor: pointColors, pointBorderColor: '#111320',
          pointBorderWidth: 2, pointRadius: 5, pointHoverRadius: 7
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { ...tooltipStyle(), callbacks: { label: (item) => `${item.label}: ${fmtNum(item.raw)} entries` } }
        },
        scales: {
          r: {
            beginAtZero: true,
            grid: { color: 'rgba(162,89,255,0.08)' },
            angleLines: { color: 'rgba(162,89,255,0.08)' },
            pointLabels: { color: '#d8dce8', font: { size: 12, weight: '600' } },
            ticks: { display: false }
          }
        }
      }
    });
    chartInstances.push(chart);
  }

  /* Fallback bar chart when /logs fetch fails but we have level stats */
  function initLevelBarFallback(levels) {
    const canvas = document.getElementById('chart-level-bar-fallback');
    if (!canvas) return;

    const colorMap = {
      ERROR: '#f43f5e', WARNING: '#f59e0b', WARN: '#f59e0b',
      INFO: '#38bdf8', DEBUG: '#5c6178'
    };

    const chart = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels: levels.map(l => l.level),
        datasets: [{
          label: 'Count',
          data: levels.map(l => l.count),
          backgroundColor: levels.map(l => (colorMap[l.level] || '#a259ff') + 'bb'),
          borderColor: levels.map(l => colorMap[l.level] || '#a259ff'),
          borderWidth: 1, borderRadius: 4
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: tooltipStyle() },
        scales: {
          x: { grid: { display: false } },
          y: { grid: { color: 'rgba(162,89,255,0.05)' } }
        }
      }
    });
    chartInstances.push(chart);
  }

  /* ============================================
     LOG ENTRY BASED CHARTS
     ============================================ */

  function initLogTimeline(logEntries) {
    const canvas = document.getElementById('chart-log-timeline');
    if (!canvas) return;

    const withTime = logEntries.filter(l => l.timestamp);
    if (!withTime.length) return;

    withTime.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    const minT = new Date(withTime[0].timestamp).getTime();
    const maxT = new Date(withTime[withTime.length - 1].timestamp).getTime();
    const range = maxT - minT || 1;
    const bucketCount = Math.min(20, withTime.length);
    const bucketSize = range / bucketCount;

    const buckets = Array.from({ length: bucketCount }, (_, i) => ({
      start: minT + i * bucketSize, total: 0, errors: 0, warnings: 0
    }));

    withTime.forEach(entry => {
      const t = new Date(entry.timestamp).getTime();
      const idx = Math.min(Math.floor((t - minT) / bucketSize), bucketCount - 1);
      buckets[idx].total++;
      if (entry.level === 'ERROR') buckets[idx].errors++;
      if (entry.level === 'WARNING' || entry.level === 'WARN') buckets[idx].warnings++;
    });

    const labels = buckets.map(b => new Date(b.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));

    const ctx = canvas.getContext('2d');
    const totalGrad = ctx.createLinearGradient(0, 0, 0, 280);
    totalGrad.addColorStop(0, 'rgba(162, 89, 255, 0.3)');
    totalGrad.addColorStop(1, 'rgba(162, 89, 255, 0.0)');

    const chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'Total Events', data: buckets.map(b => b.total), borderColor: '#a259ff', backgroundColor: totalGrad, fill: true, tension: 0.3, borderWidth: 2, pointRadius: 3, pointHoverRadius: 5 },
          { label: 'Errors', data: buckets.map(b => b.errors), borderColor: '#f43f5e', backgroundColor: 'rgba(244,63,94,0.1)', fill: true, tension: 0.3, borderWidth: 1.5, pointRadius: 2 },
          { label: 'Warnings', data: buckets.map(b => b.warnings), borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.1)', fill: true, tension: 0.3, borderWidth: 1.5, pointRadius: 2 }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { boxWidth: 10, padding: 12 } }, tooltip: tooltipStyle() },
        scales: {
          x: { ticks: { maxTicksLimit: 10, maxRotation: 0 }, grid: { display: false } },
          y: { min: 0, grid: { color: 'rgba(162,89,255,0.05)' } }
        }
      }
    });
    chartInstances.push(chart);
  }

  /* ============================================
     ANALYTICS-BASED CHARTS (need Run Analytics)
     ============================================ */

  function initAnomalyTimeline(anomalies) {
    const canvas = document.getElementById('chart-anomaly-timeline');
    if (!canvas) return;

    const sorted = [...anomalies].sort((a, b) => new Date(a.window_start) - new Date(b.window_start));
    const labels = sorted.map(a => fmtTime(a.window_start));
    const scores = sorted.map(a => a.score);
    const pointColors = scores.map(s => s > 0.7 ? '#f43f5e' : s > 0.4 ? '#f59e0b' : '#10b981');

    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, 'rgba(162, 89, 255, 0.25)');
    gradient.addColorStop(1, 'rgba(162, 89, 255, 0.0)');

    const chart = new Chart(ctx, {
      type: 'line',
      data: { labels, datasets: [{
        label: 'Anomaly Score', data: scores, borderColor: '#a259ff', backgroundColor: gradient,
        fill: true, tension: 0.3, pointBackgroundColor: pointColors, pointBorderColor: pointColors,
        pointRadius: 4, pointHoverRadius: 6, borderWidth: 2
      }]},
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { ...tooltipStyle(), callbacks: {
          title: (items) => sorted[items[0].dataIndex].window_start,
          label: (item) => { const s = item.raw; return `Score: ${(s*100).toFixed(1)}% — ${s>0.7?'High anomaly':s>0.4?'Moderate':'Normal'}`; }
        }}},
        scales: {
          x: { ticks: { maxTicksLimit: 10, maxRotation: 0 }, grid: { display: false } },
          y: { min: 0, max: 1, ticks: { callback: v => (v*100).toFixed(0)+'%', stepSize: 0.2 }, grid: { color: 'rgba(162,89,255,0.05)' } }
        }
      }
    });
    chartInstances.push(chart);
  }

  function initErrorVolume(anomalies) {
    const canvas = document.getElementById('chart-error-volume');
    if (!canvas) return;

    const sorted = [...anomalies].sort((a, b) => new Date(a.window_start) - new Date(b.window_start));
    const labels = sorted.map(a => fmtTime(a.window_start));

    const chart = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: { labels, datasets: [
        { type: 'line', label: 'Error Rate %', data: sorted.map(a => (a.features?.error_rate||0)*100), borderColor: '#f43f5e', backgroundColor: 'rgba(244,63,94,0.1)', fill: true, tension: 0.3, pointRadius: 2, borderWidth: 2, yAxisID: 'y' },
        { type: 'bar', label: 'Event Volume', data: sorted.map(a => a.features?.total_count||0), backgroundColor: 'rgba(162,89,255,0.3)', borderColor: 'rgba(162,89,255,0.5)', borderWidth: 1, borderRadius: 3, yAxisID: 'y1' }
      ]},
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { boxWidth: 12, padding: 16 } }, tooltip: tooltipStyle() },
        scales: {
          x: { ticks: { maxTicksLimit: 10, maxRotation: 0 }, grid: { display: false } },
          y: { position: 'left', min: 0, ticks: { callback: v => v.toFixed(0)+'%' }, grid: { color: 'rgba(162,89,255,0.05)' }, title: { display: true, text: 'Error Rate %', color: '#f43f5e' } },
          y1: { position: 'right', min: 0, grid: { drawOnChartArea: false }, title: { display: true, text: 'Event Volume', color: '#a259ff' } }
        }
      }
    });
    chartInstances.push(chart);
  }

  function initLogComposition(anomalies) {
    const canvas = document.getElementById('chart-log-composition');
    if (!canvas) return;

    const sorted = [...anomalies].sort((a, b) => new Date(a.window_start) - new Date(b.window_start));
    const labels = sorted.map(a => fmtTime(a.window_start));

    const chart = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: { labels, datasets: [
        { label: 'ERROR', data: sorted.map(a => a.features?.error_count||0), borderColor: '#f43f5e', backgroundColor: 'rgba(244,63,94,0.3)', fill: true, tension: 0.3, pointRadius: 0, borderWidth: 1.5 },
        { label: 'WARNING', data: sorted.map(a => a.features?.warn_count||0), borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.25)', fill: true, tension: 0.3, pointRadius: 0, borderWidth: 1.5 },
        { label: 'INFO', data: sorted.map(a => a.features?.info_count||0), borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.2)', fill: true, tension: 0.3, pointRadius: 0, borderWidth: 1.5 },
        { label: 'DEBUG', data: sorted.map(a => a.features?.debug_count||0), borderColor: '#5c6178', backgroundColor: 'rgba(92,97,120,0.2)', fill: true, tension: 0.3, pointRadius: 0, borderWidth: 1.5 }
      ]},
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { boxWidth: 10, padding: 12 } }, tooltip: tooltipStyle() },
        scales: {
          x: { ticks: { maxTicksLimit: 10, maxRotation: 0 }, grid: { display: false }, stacked: true },
          y: { stacked: true, grid: { color: 'rgba(162,89,255,0.05)' }, title: { display: true, text: 'Event Count', color: '#7a7f96' } }
        }
      }
    });
    chartInstances.push(chart);
  }

  function initScoreDistribution(anomalies) {
    const canvas = document.getElementById('chart-score-distribution');
    if (!canvas) return;

    const buckets = [
      { label: '0-10%', min: 0, max: 0.1, color: '#10b981' },
      { label: '10-20%', min: 0.1, max: 0.2, color: '#10b981' },
      { label: '20-30%', min: 0.2, max: 0.3, color: '#10b981' },
      { label: '30-40%', min: 0.3, max: 0.4, color: '#10b981' },
      { label: '40-50%', min: 0.4, max: 0.5, color: '#f59e0b' },
      { label: '50-60%', min: 0.5, max: 0.6, color: '#f59e0b' },
      { label: '60-70%', min: 0.6, max: 0.7, color: '#f59e0b' },
      { label: '70-80%', min: 0.7, max: 0.8, color: '#f43f5e' },
      { label: '80-90%', min: 0.8, max: 0.9, color: '#f43f5e' },
      { label: '90-100%', min: 0.9, max: 1.01, color: '#f43f5e' }
    ];
    const counts = buckets.map(b => anomalies.filter(a => a.score >= b.min && a.score < b.max).length);

    const chart = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: { labels: buckets.map(b => b.label), datasets: [{
        label: 'Windows', data: counts,
        backgroundColor: buckets.map(b => b.color + 'aa'), borderColor: buckets.map(b => b.color),
        borderWidth: 1, borderRadius: 3
      }]},
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { ...tooltipStyle(), callbacks: {
          label: (item) => `${item.raw} windows (${((item.raw/anomalies.length)*100).toFixed(1)}%)`
        }}},
        scales: {
          x: { grid: { display: false }, title: { display: true, text: 'Score Range', color: '#7a7f96' } },
          y: { grid: { color: 'rgba(162,89,255,0.05)' }, ticks: { stepSize: 1 }, title: { display: true, text: 'Windows', color: '#7a7f96' } }
        }
      }
    });
    chartInstances.push(chart);
  }

  function initClustersBar(clusters) {
    const canvas = document.getElementById('chart-clusters');
    if (!canvas) return;

    const top10 = clusters.slice(0, 10);
    const labels = top10.map(c => { const kw = c.keywords || String(c.label) || 'Cluster'; return kw.length > 30 ? kw.substring(0,30)+'...' : kw; });

    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, ctx.canvas.width, 0);
    gradient.addColorStop(0, 'rgba(244,63,94,0.7)');
    gradient.addColorStop(1, 'rgba(244,63,94,0.3)');

    const chart = new Chart(ctx, {
      type: 'bar',
      data: { labels, datasets: [{ label: 'Occurrences', data: top10.map(c => c.count), backgroundColor: gradient, borderColor: 'rgba(244,63,94,0.6)', borderWidth: 1, borderRadius: 4 }] },
      options: {
        responsive: true, maintainAspectRatio: false, indexAxis: 'y',
        plugins: { legend: { display: false }, tooltip: { ...tooltipStyle(), callbacks: {
          title: (items) => top10[items[0].dataIndex].keywords || 'Cluster',
          afterTitle: (items) => { const msg = top10[items[0].dataIndex].example_message; return msg ? (msg.length>80 ? msg.substring(0,80)+'...' : msg) : ''; }
        }}},
        scales: {
          x: { grid: { color: 'rgba(162,89,255,0.05)' }, ticks: { stepSize: 1 } },
          y: { grid: { display: false }, ticks: { font: { size: 11 } } }
        }
      }
    });
    chartInstances.push(chart);
  }

  function initServiceActivity(anomalies) {
    const canvas = document.getElementById('chart-service-activity');
    if (!canvas) return;

    const sorted = [...anomalies].sort((a, b) => new Date(a.window_start) - new Date(b.window_start));
    const labels = sorted.map(a => fmtTime(a.window_start));

    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, 'rgba(56,189,248,0.2)');
    gradient.addColorStop(1, 'rgba(56,189,248,0.0)');

    const chart = new Chart(ctx, {
      type: 'line',
      data: { labels, datasets: [
        { label: 'Unique Services', data: sorted.map(a => a.features?.unique_services||0), borderColor: '#38bdf8', backgroundColor: gradient, fill: true, tension: 0.3, pointRadius: 3, pointHoverRadius: 5, borderWidth: 2, yAxisID: 'y' },
        { label: 'Warnings', data: sorted.map(a => a.features?.warn_count||0), borderColor: '#f59e0b', backgroundColor: 'transparent', fill: false, tension: 0.3, pointRadius: 2, borderWidth: 1.5, borderDash: [4,3], yAxisID: 'y1' }
      ]},
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { boxWidth: 12, padding: 14 } }, tooltip: tooltipStyle() },
        scales: {
          x: { ticks: { maxTicksLimit: 10, maxRotation: 0 }, grid: { display: false } },
          y: { position: 'left', min: 0, ticks: { stepSize: 1 }, grid: { color: 'rgba(162,89,255,0.05)' }, title: { display: true, text: 'Unique Services', color: '#38bdf8' } },
          y1: { position: 'right', min: 0, grid: { drawOnChartArea: false }, title: { display: true, text: 'Warning Count', color: '#f59e0b' } }
        }
      }
    });
    chartInstances.push(chart);
  }

  /* ===== Helpers ===== */
  function tooltipStyle() {
    return { backgroundColor: '#161923', borderColor: 'rgba(162,89,255,0.2)', borderWidth: 1, titleColor: '#d8dce8', bodyColor: '#d8dce8', padding: 10 };
  }

  function fmtTime(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  return { render };
})();

/* ===== Shared Helpers ===== */
function esc(str) {
  const d = document.createElement('div');
  d.textContent = str ?? '';
  return d.innerHTML;
}

function fmtNum(n) {
  return Number(n).toLocaleString();
}

function fmtDate(iso) {
  if (!iso) return '-';
  return new Date(iso).toLocaleString();
}
