/** Centralna warstwa komunikacji z REST API backendu */
const API = {
  async getScannerStatus() { return (await fetch('/api/scanner/status')).json(); },
  async startScanner(payload) {
    return fetch('/api/scanner/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  },
  async getModelStats(model) {
    const url = model ? `/api/models/stats?model=${encodeURIComponent(model)}` : '/api/models/stats';
    return (await fetch(url)).json();
  },
  async stopScanner() { return fetch('/api/scanner/stop', { method: 'POST' }); },
  async getScannerConfig() { return (await fetch('/api/scanner/config')).json(); },
  async saveScannerConfig(payload) {
    return fetch('/api/scanner/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  },
  async probeRegion(region) { return (await fetch(`/api/scanner/probe?region=${encodeURIComponent(region)}`)).json(); },
  async getRegions() { return (await fetch('/api/regions')).json(); },
  async getModels() { return (await fetch('/api/models')).json(); },
  async getOffers(searchParams) { return (await fetch(`/api/offers?${searchParams.toString()}`)).json(); },
  async getOfferDetails(id) { return (await fetch(`/api/offers/${id}`)).json(); },
  async toggleFavorite(id) { return fetch(`/api/offers/${id}/favorite`, { method: 'POST' }); },
  async deleteOffer(id) { return fetch(`/api/offers/${id}`, { method: 'DELETE' }); },
  async saveNotes(id, notes) {
    return fetch(`/api/offers/${id}/notes`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ notes }) });
  },
  async getStats() { return (await fetch('/api/stats')).json(); },
  async setLanguage(lang) {
    return fetch('/api/language', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ language: lang }),
    });
  },
};

/* ------------------------------------------------------------------ */
/* i18n Translation & Pluralization Helpers                           */
/* ------------------------------------------------------------------ */
function t(key, params = {}) {
  const dict = window.TRANSLATIONS || {};
  let text = dict[key] !== undefined ? dict[key] : key;
  for (const [k, v] of Object.entries(params)) {
    text = text.replaceAll(`{${k}}`, v);
  }
  return text;
}

function pluralize(count, key) {
  const raw = t(key);
  const parts = raw.split('|');
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return count === 1 ? parts[0] : parts[1];
  // Obsługa odmiany słowiańskiej (3 formy: 1, 2-4, 5+)
  const m10 = count % 10, m100 = count % 100;
  if (m10 === 1 && m100 !== 11) return parts[0];
  if (m10 >= 2 && m10 <= 4 && !(m100 >= 12 && m100 <= 14)) return parts[1];
  return parts[2] || parts[1];
}

/* ------------------------------------------------------------------ */
/* Helpers                                                            */
/* ------------------------------------------------------------------ */
function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function fmtInt(v) {
  const lang = window.CURRENT_LANG || 'pl';
  const locale = lang === 'en' ? 'en-US' : (lang === 'de' ? 'de-DE' : 'pl-PL');
  return Number(v || 0).toLocaleString(locale);
}
function fmtPLN(v) {
  if (v === null || v === undefined) return '—';
  const curr = t('cost_currency');
  return `${fmtInt(Math.round(v))} ${curr}`;
}
function refreshIcons() { if (window.lucide) lucide.createIcons(); }

/* ------------------------------------------------------------------ */
/* Toasts                                                             */
/* ------------------------------------------------------------------ */
function toast(message, type = 'info', timeout = 3200) {
  const stack = document.getElementById('toast-stack');
  if (!stack) return;
  const icons = { success: 'check-circle-2', error: 'alert-triangle', warn: 'alert-circle', info: 'info' };
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `<i data-lucide="${icons[type] || icons.info}" class="w-4 h-4 shrink-0"></i><span>${escapeHtml(message)}</span>`;
  stack.appendChild(el);
  refreshIcons();
  setTimeout(() => { el.classList.add('toast-out'); setTimeout(() => el.remove(), 260); }, timeout);
}

/* ------------------------------------------------------------------ */
/* Navbar scanner status (shared across all pages)                    */
/* ------------------------------------------------------------------ */
function setNavStatus(code, seconds = 0) {
  const el = document.getElementById('nav-scanner-status');
  if (!el) return;
  const map = {
    running:  ['status-running', t('st_running')],
    waiting:  ['status-waiting', t('st_waiting', { sec: seconds })],
    stopping: ['status-waiting', t('st_stopping')],
    error:    ['status-error',   t('st_error')],
    idle:     ['',               t('st_idle')],
  };
  const [cls, label] = map[code] || map.idle;
  el.className = `status-chip ${cls}`;
  el.innerHTML = `<span class="dot"></span>${label}`;
}

(function initNavPolling() {
  if (document.body.dataset.page === 'scanner') return;
  const tick = async () => {
    try { const d = await API.getScannerStatus(); setNavStatus(d.status_code, d.next_scan_seconds); } catch (_) {}
  };
  tick();
  setInterval(tick, 5000);
})();

/* ------------------------------------------------------------------ */
/* Language Switcher Dropdown Interaction                             */
/* ------------------------------------------------------------------ */
function toggleLangMenu() {
  const dropdown = document.getElementById('lang-dropdown');
  if (dropdown) dropdown.classList.toggle('hidden');
}

window.addEventListener('click', (e) => {
  const wrapper = document.getElementById('lang-picker-wrapper');
  const dropdown = document.getElementById('lang-dropdown');
  if (wrapper && dropdown && !wrapper.contains(e.target)) {
    dropdown.classList.add('hidden');
  }
});

async function switchLanguage(code) {
  try {
    await API.setLanguage(code);
    const url = new URL(window.location.href);
    url.searchParams.delete('lang');
    window.location.href = url.toString();
  } catch (err) {
    console.error('Błąd zmiany języka:', err);
  }
}

/* ------------------------------------------------------------------ */
/* Offer details modal                                                */
/* ------------------------------------------------------------------ */
let currentOffer = null;

function tri(v, yes, no, unknown = t('v_unknown')) {
  return v === 1 ? yes : (v === 0 ? no : unknown);
}

async function openDetailsModal(olxId) {
  try {
    const d = await API.getOfferDetails(olxId);
    if (d.detail) throw new Error(d.detail);
    currentOffer = d;

    document.getElementById('modal-title').textContent =
      `${d.model_name || d.title}${d.storage_gb ? ` · ${d.storage_gb} GB` : ''}`;
    document.getElementById('modal-sub').textContent =
      `ID ${d.olx_id}${d.location ? ` · ${d.location}` : ''}${d.posted_at ? ` · ${d.posted_at}` : ''}`;

    const state = document.getElementById('modal-state');
    if (d.is_damaged === 1) {
      state.className = 'chip chip-accent';
      state.textContent = t('chip_damaged');
    } else if (d.ai_analyzed) {
      state.className = 'chip chip-mint';
      state.textContent = t('chip_healthy');
    } else {
      state.className = 'chip chip-gray';
      state.textContent = t('chip_pending_ai');
    }

    document.getElementById('modal-price').textContent = fmtPLN(d.price);

    // NOWE: Wypełnienie paska porównania rynkowego i marży
    const strip = document.getElementById('modal-market-strip');
    if (strip) {
      if (d.avg_model_price && d.price) {
        strip.classList.remove('hidden');
        document.getElementById('modal-market-avg').textContent = fmtPLN(d.avg_model_price);
        const marginEl = document.getElementById('modal-market-margin');
        const diff = d.margin_pln !== undefined && d.margin_pln !== null ? d.margin_pln : Math.round(d.avg_model_price - d.price);
        const pct = d.margin_pct !== undefined && d.margin_pct !== null ? d.margin_pct : Math.round((diff / d.avg_model_price) * 100);

        if (diff > 0) {
          marginEl.className = 'chip chip-mint font-mono text-xs font-bold';
          marginEl.textContent = `+${fmtInt(diff)} zł (+${pct}%)`;
        } else if (diff < 0) {
          marginEl.className = 'chip chip-accent font-mono text-xs font-bold';
          marginEl.textContent = `${fmtInt(diff)} zł (${pct}%)`;
        } else {
          marginEl.className = 'chip chip-gray font-mono text-xs';
          marginEl.textContent = '0 zł (w średniej)';
        }
      } else {
        strip.classList.add('hidden');
      }
    }

    const bat = document.getElementById('modal-battery');
    bat.textContent = d.battery_health_pct ? `${d.battery_health_pct}%` : '—';
    bat.className = 'v ' + (d.battery_health_pct >= 85 ? 'text-mint-700' : d.battery_health_pct >= 80 ? 'text-sun-700' : d.battery_health_pct ? 'text-accent-600' : 'text-muted');

    const face = document.getElementById('modal-faceid');
    face.textContent = tri(d.face_id_working, t('v_working'), t('v_broken'), t('v_unknown'));
    face.className = 'v text-lg ' + (d.face_id_working === 1 ? 'text-mint-700' : d.face_id_working === 0 ? 'text-accent-600' : 'text-muted');

    const icl = document.getElementById('modal-icloud');
    icl.textContent = tri(d.icloud_clean, t('v_clean'), t('v_locked'), t('v_unknown'));
    icl.className = 'v text-lg ' + (d.icloud_clean === 1 ? 'text-mint-700' : d.icloud_clean === 0 ? 'text-accent-600' : 'text-muted');

    document.getElementById('modal-condition').textContent = d.condition_state || '—';
    document.getElementById('modal-verdict').textContent = d.ai_summary || t('m_verdict_empty');
    document.getElementById('modal-notes').value = d.user_notes || '';
    document.getElementById('modal-description').textContent = d.description || t('m_no_description');
    document.getElementById('modal-olx-link').href = d.url || '#';
    renderModalFav();

    document.getElementById('details-modal').classList.add('open');
    document.body.style.overflow = 'hidden';
    refreshIcons();
  } catch (err) {
    toast(t('t_details_failed', { msg: err.message }), 'error');
  }
}

function renderModalFav() {
  const b = document.getElementById('modal-fav-btn');
  if (b && currentOffer) b.classList.toggle('is-fav', currentOffer.is_favorite === 1);
}

function closeDetailsModal() {
  const m = document.getElementById('details-modal');
  if (!m) return;
  m.classList.remove('open');
  document.body.style.overflow = '';
  currentOffer = null;
}

async function saveModalNotes() {
  if (!currentOffer) return;
  const notes = document.getElementById('modal-notes').value;
  const res = await API.saveNotes(currentOffer.olx_id, notes);
  res.ok ? toast(t('t_note_saved'), 'success') : toast(t('t_note_failed'), 'error');
}

async function toggleModalFavorite() {
  if (!currentOffer) return;
  const res = await API.toggleFavorite(currentOffer.olx_id);
  if (!res.ok) return toast(t('t_fav_failed'), 'error');
  const j = await res.json();
  currentOffer.is_favorite = j.is_favorite ? 1 : 0;
  renderModalFav();
  toast(j.is_favorite ? t('t_fav_added') : t('t_fav_removed'), 'success');
  if (typeof fetchData === 'function' && typeof state !== 'undefined') fetchData(state.page);
}