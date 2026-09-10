let autoScroll = true;
let scannerPollTimer = null;
let currentPollingInterval = 3000;
let currentRegionMeta = { total_items: 0, available_pages: 25 };
let logLevelFilter = 'ALL';
let lastLogSignature = '';
let clearedMarker = null;

// Funkcja „Monitoring" (tryb watch) tymczasowo wyłączona w web dashboardzie.
// Aby przywrócić: ustaw true (i zsynchronizuj WATCH_MODE_ENABLED w app.py).
const WATCH_MODE_ENABLED = false;

// Stałe kosztowe (deepseek-v4-flash-vision-exp)
const COST_OFFER_STANDARD_USD = 0.00024578;
const COST_OFFER_OFFPEAK_USD = 0.00012289;
const COST_OFFER_PESSIMISTIC_USD = 0.00036080;
const USD_TO_PLN = 4.00;
const ITEMS_PER_PAGE = 52;

document.addEventListener('DOMContentLoaded', async () => {
  paintRange(document.getElementById('cfg-pages'));
  await loadRegions();
  await loadScannerConfig();
  startScannerPolling();
});

function paintRange(el) {
  if (!el) return;
  const min = +el.min || 0, max = +el.max || 100, val = +el.value;
  const pct = max > min ? ((val - min) / (max - min)) * 100 : 0;
  el.style.setProperty('--fill', `${pct}%`);
}

async function loadRegions() {
  try {
    const data = await API.getRegions();
    const sel = document.getElementById('cfg-region');
    for (const [slug, name] of Object.entries(data)) {
      const opt = document.createElement('option');
      opt.value = slug; opt.textContent = name;
      sel.appendChild(opt);
    }
  } catch (e) { console.error('Błąd regionów:', e); }
}

async function loadScannerConfig() {
  try {
    const cfg = await API.getScannerConfig();
    if (cfg.region) document.getElementById('cfg-region').value = cfg.region;
    
    // Ustawienie wybranego języka AI
    if (cfg.ai_language) {
      document.getElementById('cfg-ai-lang').value = cfg.ai_language;
    } else if (cfg.language) {
      document.getElementById('cfg-ai-lang').value = cfg.language;
    }

    const pages = cfg.pages || 3;
    const slider = document.getElementById('cfg-pages');
    slider.value = pages;
    onPagesSlider(pages);
    document.getElementById('cfg-threads').value = cfg.threads || 8;
    document.getElementById('cfg-interval').value = cfg.interval || 120;
    document.getElementById('cfg-proxy').value = cfg.custom_proxy || '';
    if (cfg.watch && WATCH_MODE_ENABLED) { document.getElementById('cfg-mode-watch').checked = true; toggleWatchOptions(true); }

    const st = document.getElementById('cfg-api-key-status');
    st.innerHTML = cfg.api_key_masked
      ? `<i data-lucide="check-circle-2" class="w-3 h-3 text-mint-700"></i> ${t('set_api_active')} <span class="font-mono">${escapeHtml(cfg.api_key_masked)}</span>`
      : `<i data-lucide="alert-circle" class="w-3 h-3 text-accent"></i> ${t('set_api_missing')}`;
    refreshIcons();
    probeRegion();
  } catch (e) { console.error('Błąd konfiguracji:', e); }
}

function collectRunPayload() {
  return {
    region: document.getElementById('cfg-region').value,
    ai_language: document.getElementById('cfg-ai-lang').value,
    pages: parseInt(document.getElementById('cfg-pages').value, 10),
    watch: WATCH_MODE_ENABLED && document.getElementById('cfg-mode-watch').checked,
    interval: parseInt(document.getElementById('cfg-interval').value, 10),
    threads: parseInt(document.getElementById('cfg-threads').value, 10),
  };
}

async function probeRegion() {
  const sel = document.getElementById('cfg-region');
  const reg = sel.value;
  document.getElementById('probe-region-name').textContent = sel.options[sel.selectedIndex]?.textContent || reg;
  document.getElementById('probe-total-items').textContent = '…';
  document.getElementById('probe-total-pages').textContent = '…';

  try {
    const data = await API.probeRegion(reg);
    currentRegionMeta.total_items = data.total_items;
    currentRegionMeta.available_pages = Math.max(1, data.available_pages || 1);

    document.getElementById('probe-region-name').textContent = data.region_display || reg;
    document.getElementById('probe-total-items').textContent = fmtInt(data.total_items);
    document.getElementById('probe-total-pages').textContent = fmtInt(currentRegionMeta.available_pages);

    const slider = document.getElementById('cfg-pages');
    slider.max = Math.min(25, currentRegionMeta.available_pages);
    document.getElementById('cfg-pages-max').textContent = slider.max;
    if (parseInt(slider.value, 10) > slider.max) slider.value = slider.max;
    onPagesSlider(slider.value);
  } catch (e) {
    document.getElementById('probe-total-items').textContent = t('na');
    document.getElementById('probe-total-pages').textContent = t('na');
  }
}

function onRegionChange() { probeRegion(); }

function onPagesSlider(val) {
  const p = parseInt(val, 10) || 1;
  document.getElementById('cfg-pages-val').textContent = `${p} ${pluralize(p, 'pages_n')}`;
  const estOffers = p * ITEMS_PER_PAGE;
  document.getElementById('probe-items-scan').textContent = t('set_items_est', {
    offers: `${fmtInt(estOffers)} ${pluralize(estOffers, 'offers_n')}`,
  });
  paintRange(document.getElementById('cfg-pages'));
  updateCostLocally(p);
}

function updateCostLocally(pages) {
  const items = (parseInt(pages, 10) || 1) * ITEMS_PER_PAGE;
  const stdUsd = items * COST_OFFER_STANDARD_USD;
  const minUsd = items * COST_OFFER_OFFPEAK_USD;
  const maxUsd = items * COST_OFFER_PESSIMISTIC_USD;
  const curr = t('cost_currency');

  document.getElementById('probe-cost-pln').textContent = (stdUsd * USD_TO_PLN).toFixed(2);
  document.getElementById('probe-cost-usd').textContent = t('cost_standard', { usd: stdUsd.toFixed(3) });
  document.getElementById('probe-cost-range').textContent =
    `$${minUsd.toFixed(3)} – $${maxUsd.toFixed(3)} (${(minUsd * USD_TO_PLN).toFixed(2)} – ${(maxUsd * USD_TO_PLN).toFixed(2)} ${curr})`;
}

function toggleWatchOptions(isWatch) {
  document.getElementById('cfg-interval-container').classList.toggle('hidden', !isWatch);
}

function collectRunPayload() {
  return {
    region: document.getElementById('cfg-region').value,
    pages: parseInt(document.getElementById('cfg-pages').value, 10),
    watch: WATCH_MODE_ENABLED && document.getElementById('cfg-mode-watch').checked,
    interval: parseInt(document.getElementById('cfg-interval').value, 10),
    threads: parseInt(document.getElementById('cfg-threads').value, 10),
  };
}

async function saveScannerSettings() {
  const payload = collectRunPayload();
  payload.custom_proxy = document.getElementById('cfg-proxy').value.trim() || null;
  const apiKey = document.getElementById('cfg-api-key').value.trim();
  if (apiKey) payload.api_key = apiKey;

  const res = await API.saveScannerConfig(payload);
  if (res.ok) {
    toast(t('t_settings_saved'), 'success');
    document.getElementById('cfg-api-key').value = '';
    loadScannerConfig();
  } else {
    toast(t('t_settings_failed'), 'error');
  }
}

async function startScanner() {
  const res = await API.startScanner(collectRunPayload());
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    return toast(t('t_start_failed', { detail: err.detail || t('err_generic') }), 'error');
  }
  toast(t('t_started'), 'success');
  setPollingRate(1000);
  pollScannerStatus();
}

async function stopScanner() {
  const res = await API.stopScanner();
  res.ok ? toast(t('t_stop_sent'), 'warn') : toast(t('t_stop_failed'), 'error');
  pollScannerStatus();
}

function setPollingRate(ms) {
  if (currentPollingInterval === ms) return;
  currentPollingInterval = ms;
  if (scannerPollTimer) clearInterval(scannerPollTimer);
  scannerPollTimer = setInterval(pollScannerStatus, currentPollingInterval);
}

function startScannerPolling() {
  if (scannerPollTimer) clearInterval(scannerPollTimer);
  scannerPollTimer = setInterval(pollScannerStatus, currentPollingInterval);
  pollScannerStatus();
}

async function pollScannerStatus() {
  try {
    const data = await API.getScannerStatus();
    renderScannerState(data);
    setPollingRate(data.is_running ? 1000 : 3000);
  } catch (e) { console.error('Błąd statusu:', e); }
}

function renderScannerState(d) {
  const isRun = d.is_running;
  document.getElementById('btn-start-scanner').disabled = isRun;
  document.getElementById('btn-stop-scanner').disabled = !isRun;

  const stateMeta = {
    running:  { ind: 'ind ind-running', pill: 'chip chip-mint',   pillTxt: 'RUNNING',  desc: t('sc_desc_running') },
    waiting:  { ind: 'ind ind-waiting', pill: 'chip chip-sun',    pillTxt: 'WATCH',    desc: t('sc_desc_waiting') },
    stopping: { ind: 'ind ind-waiting', pill: 'chip chip-sun',    pillTxt: 'STOPPING', desc: t('sc_desc_stopping') },
    error:    { ind: 'ind ind-error',   pill: 'chip chip-accent', pillTxt: 'ERROR',    desc: t('sc_desc_error') },
    idle:     { ind: 'ind',             pill: 'chip chip-gray',   pillTxt: 'IDLE',     desc: t('sc_desc_idle') },
  };

  const meta = stateMeta[d.status_code] || stateMeta.idle;
  document.getElementById('scanner-indicator-dot').className = meta.ind;
  const pill = document.getElementById('scanner-status-pill');
  pill.className = meta.pill; pill.textContent = meta.pillTxt;
  document.getElementById('scanner-state-desc').textContent = meta.desc;
  setNavStatus(d.status_code, d.next_scan_seconds);

  document.getElementById('scanner-state-title').textContent = d.status_message;
  document.getElementById('scanner-cycle-badge').textContent = t('sc_cycle', { n: d.current_cycle });

  const pct = Math.round(d.progress * 100);
  document.getElementById('scanner-progress-bar').style.width = `${pct}%`;
  document.getElementById('scanner-progress-pct').textContent = `${pct}%`;
  document.getElementById('scanner-progress-label').textContent = d.progress_label;

  const cd = document.getElementById('scanner-countdown');
  if (d.next_scan_seconds > 0) {
    cd.classList.remove('hidden');
    cd.querySelector('span').textContent = t('sc_next_cycle', { sec: d.next_scan_seconds });
  } else {
    cd.classList.add('hidden');
  }

  const m = d.metrics || {};
  document.getElementById('metric-session-found').textContent = fmtInt(m.total_found);
  document.getElementById('metric-session-analyzed').textContent = fmtInt(m.ai_analyzed);
  document.getElementById('metric-session-healthy').textContent = fmtInt(m.healthy);
  document.getElementById('metric-session-damaged').textContent = fmtInt(m.damaged);
  document.getElementById('metric-session-dups').textContent = fmtInt(m.duplicates_skipped);
  document.getElementById('metric-session-acc').textContent = fmtInt(m.accessories_filtered);

  const curBox = document.getElementById('live-current-offer-box');
  if (d.current_offer_title) {
    curBox.classList.remove('hidden');
    document.getElementById('live-current-offer-title').textContent = d.current_offer_title;
  } else {
    curBox.classList.add('hidden');
  }

  renderLogs(d.recent_logs || []);
}

function renderLogs(allLogs) {
  const container = document.getElementById('scanner-logs-container');
  let logs = allLogs;

  if (clearedMarker) {
    const idx = logs.findIndex(l => l.timestamp === clearedMarker.timestamp && l.message === clearedMarker.message);
    logs = idx >= 0 ? logs.slice(idx + 1) : logs;
  }
  if (logLevelFilter !== 'ALL') logs = logs.filter(l => l.level === logLevelFilter);

  document.getElementById('log-count').textContent = logs.length;

  const last = logs[logs.length - 1];
  const signature = `${logs.length}|${last ? last.timestamp + last.message : ''}|${logLevelFilter}`;
  if (signature === lastLogSignature) return;
  lastLogSignature = signature;

  if (logs.length === 0) {
    container.innerHTML = `<div class="log-empty">${t('log_empty_filter')}</div>`;
    return;
  }

  container.innerHTML = logs.map(l => {
    const lvl = ['SUCCESS', 'WARN', 'ERROR', 'AI', 'SMART'].includes(l.level) ? l.level : 'INFO';
    const idxTag = l.idx
      ? `<span class="log-idx" onclick="openDetailsModal('${escapeHtml(l.idx)}')">#${escapeHtml(l.idx)}</span>`
      : '<span></span>';
    return `
      <div class="log-line">
        <span class="log-ts">${l.timestamp}</span>
        <span class="log-lvl lvl-${lvl}">${lvl}</span>
        ${idxTag}
        <span class="log-msg">${escapeHtml(l.message)}</span>
      </div>`;
  }).join('');

  if (autoScroll) container.scrollTop = container.scrollHeight;
}

function setLogFilter(v) { logLevelFilter = v; lastLogSignature = ''; pollScannerStatus(); }

function toggleAutoScroll() {
  autoScroll = !autoScroll;
  const b = document.getElementById('btn-autoscroll');
  b.className = `btn btn-xs ${autoScroll ? 'btn-black' : 'btn-white'}`;
  b.innerHTML = `<i data-lucide="arrow-down-to-line" class="w-3.5 h-3.5"></i> ${autoScroll ? t('log_auto') : t('log_auto_off')}`;
  refreshIcons();
}

async function clearLogs() {
  try {
    const d = await API.getScannerStatus();
    const logs = d.recent_logs || [];
    const last = logs[logs.length - 1];
    clearedMarker = last ? { timestamp: last.timestamp, message: last.message } : null;
  } catch (_) {}
  lastLogSignature = '';
  document.getElementById('scanner-logs-container').innerHTML = `<div class="log-empty">${t('log_cleared')}</div>`;
  document.getElementById('log-count').textContent = '0';
}