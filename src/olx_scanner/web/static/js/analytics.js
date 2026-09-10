let chartModels = null;
let chartBattery = null;

const PALETTE = { accent: '#E11D48', mint: '#10B981', sun: '#F59E0B', grape: '#8B5CF6', gray: '#A1A1AA' };

const KPI_ICONS = {
  price: 'tag',
  battery: 'battery-charging',
  damaged: 'alert-triangle',
  healthy: 'shield-check',
  analyzed: 'brain',
  favor: 'star',
};

document.addEventListener('DOMContentLoaded', () => {
  if (window.Chart) {
    Chart.defaults.font.family = 'Inter, sans-serif';
    Chart.defaults.font.size = 10.5;
    Chart.defaults.color = '#52525B';
  }
  fetchAnalytics();
});

function humanize(key) {
  const kpiMap = {
    total: t('k_total_offers'), total_offers: t('k_total_offers'), offers: t('k_total_offers'),
    analyzed: t('k_analyzed'), ai_analyzed: t('k_analyzed'),
    pending: t('k_pending'), unanalyzed: t('k_pending'),
    damaged: t('k_damaged'), healthy: t('k_healthy'),
    favorites: t('k_favorites'), favourites: t('k_favorites'),
    avg_price: t('k_avg_price'), median_price: t('k_median_price'),
    min_price: t('k_min_price'), max_price: t('k_max_price'),
    avg_battery: t('k_avg_battery'), avg_battery_pct: t('k_avg_battery'),
    accessories: t('k_accessories'), last_24h: t('k_last_24h'), today: t('k_today'),
  };
  return kpiMap[key] || key.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase());
}

function fmtKpiValue(key, v) {
  if (typeof v !== 'number') return String(v);
  if (/price|pln|cena/.test(key)) return fmtPLN(v);
  if (/pct|battery|percent|ratio/.test(key)) return `${Math.round(v)}%`;
  return fmtInt(v);
}

function kpiIcon(key) {
  for (const k in KPI_ICONS) if (key.includes(k)) return KPI_ICONS[k];
  return 'hash';
}

function renderKpis(kpi) {
  const grid = document.getElementById('analytics-kpi-grid');
  const entries = Object.entries(kpi || {}).filter(([, v]) => v === null || ['number', 'string'].includes(typeof v)).slice(0, 8);
  if (entries.length === 0) {
    grid.innerHTML = `<div class="card kpi col-span-full text-muted text-sm">${escapeHtml(t('an_kpi_empty'))}</div>`;
    return;
  }
  const tone = ['bg-ink text-white', 'bg-accent-50 text-accent-600', 'bg-mint-50 text-mint-700', 'bg-grape-50 text-grape-700', 'bg-sun-50 text-sun-700'];
  grid.innerHTML = entries.map(([k, v], i) => `
    <div class="card kpi">
      <div class="flex items-start justify-between">
        <span class="eyebrow">${escapeHtml(humanize(k))}</span>
        <span class="kpi-icon ${tone[i % tone.length]}"><i data-lucide="${kpiIcon(k)}" class="w-4 h-4"></i></span>
      </div>
      <div class="kpi-value">${v === null ? '—' : escapeHtml(fmtKpiValue(k, v))}</div>
    </div>`).join('');
  refreshIcons();
}

async function fetchAnalytics() {
  try {
    const d = await API.getStats();
    const a = d.analytics || {};
    renderKpis(d.kpi);

    /* --- Ceny wg modelu --- */
    const models = a.models_price || [];
    document.getElementById('models-count-badge').textContent = `${models.length} ${pluralize(models.length, 'models_n')}`;
    const curr = t('cost_currency');

    if (chartModels) chartModels.destroy();
    chartModels = new Chart(document.getElementById('chart-models-price'), {
      type: 'bar',
      data: {
        labels: models.map(m => m.model_name),
        datasets: [{
          data: models.map(m => Math.round(m.avg_price)),
          backgroundColor: PALETTE.grape, hoverBackgroundColor: '#7C3AED',
          borderRadius: 6, borderSkipped: false, maxBarThickness: 34,
          categoryPercentage: 0.72, barPercentage: 0.9,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#18181B', padding: 10, cornerRadius: 8, displayColors: false,
            callbacks: { label: ctx => ` ${fmtPLN(ctx.parsed.y)}` },
          },
        },
        scales: {
          x: { grid: { display: false }, border: { display: false }, ticks: { maxRotation: 0, autoSkip: false, font: { size: 9.5 }, callback: v => (v.length > 16 ? `${v.slice(0, 15)}…` : v) } },
          y: { grid: { color: '#F0F1F3' }, border: { display: false }, ticks: { callback: v => `${fmtInt(v)} ${curr}` } },
        },
      },
    });

    /* --- Bateria --- */
    const b = a.battery_distribution || {};
    const buckets = [
      { label: '90–100%', v: b.bat_90_100 || 0,  color: '#10B981', cls: 'bg-emerald-500' },
      { label: '85–89%',  v: b.bat_85_89 || 0,   color: '#34D399', cls: 'bg-emerald-400' },
      { label: '80–84%',  v: b.bat_80_84 || 0,   color: '#F59E0B', cls: 'bg-amber-500' },
      { label: '< 80%',   v: b.bat_below_80 || 0, color: '#F43F5E', cls: 'bg-rose-500' },
      { label: t('b_unknown'), v: b.bat_unknown || 0, color: PALETTE.gray, cls: 'bg-zinc-400' },
    ];

    if (chartBattery) chartBattery.destroy();
    chartBattery = new Chart(document.getElementById('chart-battery-dist'), {
      type: 'doughnut',
      data: { labels: buckets.map(x => x.label), datasets: [{ data: buckets.map(x => x.v), backgroundColor: buckets.map(x => x.color), borderWidth: 3, borderColor: '#fff', hoverOffset: 6 }] },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '72%',
        plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, pointStyle: 'circle', padding: 12, font: { size: 10 } } },
                   tooltip: { backgroundColor: '#18181B', cornerRadius: 8, padding: 10 } },
      },
    });

    /* --- Segmenty kondycji --- */
    const total = buckets.reduce((s, x) => s + x.v, 0);
    const max = Math.max(1, ...buckets.map(x => x.v));
    document.getElementById('battery-bars').innerHTML = total === 0
      ? `<p class="text-sm text-muted">${escapeHtml(t('an_no_battery'))}</p>`
      : buckets.map(x => `
        <div class="flex items-center gap-4">
          <span class="w-24 text-xs font-semibold text-zinc-700">${x.label}</span>
          <div class="flex-1 h-7 rounded-full bg-paper overflow-hidden">
            <div class="h-full rounded-full ${x.cls} transition-all duration-700" style="width:${Math.max(2, (x.v / max) * 100)}%"></div>
          </div>
          <span class="w-24 text-right font-mono text-xs"><b>${fmtInt(x.v)}</b> <span class="text-muted">· ${total ? Math.round((x.v / total) * 100) : 0}%</span></span>
        </div>`).join('');

    /* --- Zdrowa bateria card --- */
    const known = total - (b.bat_unknown || 0);
    const healthy = (b.bat_90_100 || 0) + (b.bat_85_89 || 0);
    const pctEl = document.getElementById('battery-share-pct');
    const descEl = document.getElementById('battery-share-desc');
    if (known > 0) {
      pctEl.textContent = Math.round((healthy / known) * 100);
      descEl.textContent = t('an_health_desc', {
        healthy: fmtInt(healthy),
        known: fmtInt(known),
        unknown: fmtInt(b.bat_unknown || 0),
      });
    } else {
      pctEl.textContent = '–';
      descEl.textContent = t('an_health_none');
    }
  } catch (e) {
    console.error('Błąd analityki:', e);
    toast(t('t_stats_failed'), 'error');
  }
}