// File: src/olx_scanner/web/static/js/offers.js
let state = { page: 1, pageSize: 25, totalPages: 1, debounceTimer: null };
const modelStatsCache = new Map();
let activeRow = null;
let openTimer = null;
let lastDockY = null;
const DOCK_OPEN_DELAY = 70;
const DOCK_GAP = 3;     // odstęp od wiersza (px)
const DOCK_INSET = 6;   // wcięcie boczne

document.addEventListener('DOMContentLoaded', () => {
  applyQueryDefaults();
  loadModelsFilter();
  initRowComparison();
  fetchData(1);
});

function tr(key, fallback) {
  const v = window.TRANSLATIONS && window.TRANSLATIONS[key];
  return typeof v === 'string' ? v : fallback;
}

/* ------------------------------------------------------------------ */
/* Dock porównawczy                                                   */
/* ------------------------------------------------------------------ */
function initRowComparison() {
  const wrap = document.getElementById('offers-scroll');
  const dock = document.getElementById('compare-dock');
  if (!wrap || !dock) return;

  dock.innerHTML = `<div class="cd-inner">${dockTemplate()}</div>`;
  refreshIcons();

  wrap.addEventListener('mouseover', (e) => {
    const row = e.target.closest('tr.offer-row');
    clearTimeout(openTimer);
    if (row === activeRow) return;
    if (!row) { closeDock(); return; }
    openTimer = setTimeout(() => openDock(row), DOCK_OPEN_DELAY);
  });

  wrap.addEventListener('mouseleave', () => {
    clearTimeout(openTimer);
    closeDock();
  });

  window.addEventListener('resize', closeDock);
}

function closeDock() {
  const dock = document.getElementById('compare-dock');
  if (dock) dock.classList.remove('is-open');
  if (activeRow) activeRow.classList.remove('is-active');
  activeRow = null;
  lastDockY = null;
}

function openDock(row) {
  const dock = document.getElementById('compare-dock');
  const wasOpen = dock.classList.contains('is-open') && !!activeRow;

  if (activeRow && activeRow !== row) activeRow.classList.remove('is-active');
  activeRow = row;
  row.classList.add('is-active');

  const y = placeDock(row, dock);

  if (!wasOpen) {
    void dock.offsetHeight;
    dock.classList.add('is-open');
    animateContent(dock, 0);
  } else {
    animateContent(dock, Math.sign(y - (lastDockY ?? y)));
  }
  lastDockY = y;

  fillDock(row, dock);
}

function placeDock(row, dock) {
  const wrap = document.getElementById('offers-scroll');
  const r = row.getBoundingClientRect();
  const w = wrap.getBoundingClientRect();

  const h = Math.max(48, Math.round(r.height));
  const rowTop = r.top - w.top + wrap.scrollTop;
  const rowLeft = r.left - w.left + wrap.scrollLeft;
  const viewTop = wrap.scrollTop;
  const viewBottom = wrap.scrollTop + wrap.clientHeight;

  let y = rowTop - h - DOCK_GAP;
  let below = false;
  if (y < viewTop) {
    const under = rowTop + r.height + DOCK_GAP;
    if (under + h <= viewBottom) { y = under; below = true; }
    else y = rowTop;
  }

  dock.classList.toggle('from-below', below);
  dock.style.top = `${Math.round(y)}px`;
  dock.style.left = `${Math.round(rowLeft + DOCK_INSET)}px`;
  dock.style.width = `${Math.round(r.width - DOCK_INSET * 2)}px`;
  dock.style.height = `${h}px`;
  return y;
}

function animateContent(dock, dir) {
  const inner = dock.querySelector('.cd-inner');
  if (!inner || typeof inner.animate !== 'function') return;
  if (inner.getAnimations) inner.getAnimations().forEach(a => a.cancel());

  const offset = dir === 0 ? 0 : dir * 7;
  inner.animate(
    [
      { opacity: dir === 0 ? 0 : .2, transform: `translateY(${offset}px)` },
      { opacity: 1, transform: 'none' },
    ],
    { duration: dir === 0 ? 200 : 280, delay: dir === 0 ? 70 : 40, easing: 'cubic-bezier(.2,.7,.2,1)', fill: 'backwards' }
  );
}

function dockTemplate() {
  return `
    <div class="cd-block cd-model cd-data">
      <span class="cd-icon"><i data-lucide="activity" class="w-4 h-4"></i></span>
      <div class="min-w-0">
        <div class="cd-label truncate">${escapeHtml(tr('dock_market', 'Rynek'))} · <b data-dock="model">–</b></div>
        <div class="cd-sub" data-dock="count">…</div>
      </div>
    </div>
    <span class="cd-sep cd-data"></span>
    <div class="cd-block cd-data">
      <div>
        <div class="cd-label">${escapeHtml(tr('dock_avg_price', 'Średnia modelu'))}</div>
        <div class="cd-value display" data-dock="avg-price">–</div>
      </div>
      <span class="cd-badge" data-dock="deal">…</span>
      <span class="cd-sub cd-lg" data-dock="range"></span>
    </div>
    <span class="cd-sep cd-data"></span>
    <div class="cd-block cd-data">
      <div>
        <div class="cd-label">${escapeHtml(tr('dock_avg_battery', 'Śr. bateria'))}</div>
        <div class="cd-value mono" data-dock="avg-bat">–</div>
      </div>
      <span class="cd-badge" data-dock="bat-badge"></span>
    </div>
    <span class="cd-sep cd-lg cd-data"></span>
    <div class="cd-block cd-lg cd-data">
      <span class="cd-stat"><i data-lucide="shield-check" class="w-3.5 h-3.5 text-mint"></i><b data-dock="healthy">0</b> ${escapeHtml(tr('dock_healthy', 'sprawne'))}</span>
      <span class="cd-stat"><i data-lucide="alert-triangle" class="w-3.5 h-3.5 text-accent"></i><b data-dock="damaged">0</b> ${escapeHtml(tr('dock_damaged', 'uszk.'))}</span>
    </div>
    <span class="cd-empty">${escapeHtml(tr('dock_no_model', 'Model nierozpoznany – porównanie niedostępne'))}</span>`;
}

async function fillDock(row, dock) {
  const q = (k) => dock.querySelector(`[data-dock="${k}"]`);
  const model = (row.dataset.model || '').trim();

  if (!model) { dock.classList.add('is-empty'); return; }
  dock.classList.remove('is-empty');
  q('model').textContent = model;

  let stats = modelStatsCache.get(model);
  if (!stats) {
    q('count').textContent = '…';
    q('avg-price').textContent = '–';
    q('avg-bat').textContent = '–';
    q('range').textContent = '';
    q('bat-badge').textContent = '';
    q('deal').className = 'cd-badge';
    q('deal').textContent = '…';
    try {
      stats = await API.getModelStats(model);
      modelStatsCache.set(model, stats);
    } catch (_) {
      q('deal').textContent = tr('dock_error', 'Błąd danych');
      return;
    }
    if (activeRow !== row) return;
  }

  const count = stats.total_count || 0;
  q('count').textContent = `${fmtInt(count)} ${pluralize(count, 'offers_n')} ${tr('dock_in_db', 'w bazie')}`;

  const avgPrice = stats.avg_price;
  q('avg-price').textContent = avgPrice ? fmtPLN(avgPrice) : '—';
  q('range').textContent = (stats.min_price && stats.max_price && stats.min_price !== stats.max_price)
    ? `${fmtInt(stats.min_price)} – ${fmtInt(stats.max_price)} zł`
    : '';

  const price = row.dataset.price ? parseFloat(row.dataset.price) : null;
  const deal = q('deal');
  if (price && avgPrice) {
    const diff = Math.round(price - avgPrice);
    const pct = Math.round((Math.abs(diff) / avgPrice) * 100);
    const tol = Math.max(30, avgPrice * 0.03);
    if (diff < -tol) {
      deal.className = 'cd-badge mint';
      deal.textContent = `−${fmtInt(Math.abs(diff))} zł · ${pct}% ${tr('dock_cheaper', 'TANIEJ')}`;
    } else if (diff > tol) {
      deal.className = 'cd-badge accent';
      deal.textContent = `+${fmtInt(diff)} zł · ${pct}% ${tr('dock_pricier', 'DROŻEJ')}`;
    } else {
      deal.className = 'cd-badge';
      deal.textContent = tr('dock_avg_price_ok', 'CENA W ŚREDNIEJ');
    }
  } else {
    deal.className = 'cd-badge';
    deal.textContent = tr('dock_no_price', 'Brak ceny');
  }

  const bat = row.dataset.battery ? parseInt(row.dataset.battery, 10) : null;
  const avgBat = stats.avg_battery;
  const batBadge = q('bat-badge');
  q('avg-bat').textContent = avgBat ? `${avgBat}%` : '—';
  batBadge.className = 'cd-badge';
  batBadge.textContent = '';
  if (avgBat && bat) {
    const d = Math.round(bat - avgBat);
    if (d > 0)      { batBadge.classList.add('mint');   batBadge.textContent = `+${d}% ${tr('dock_bat_better', 'lepsza')}`; }
    else if (d < 0) { batBadge.classList.add('accent'); batBadge.textContent = `${d}% ${tr('dock_bat_worse', 'niższa')}`; }
    else            { batBadge.textContent = tr('dock_bat_avg', 'Średnia'); }
  }

  q('healthy').textContent = fmtInt(stats.healthy_count || 0);
  q('damaged').textContent = fmtInt(stats.damaged_count || 0);
}

async function prefetchModelStats(items) {
  for (const r of items) {
    const m = (r.model_name || '').trim();
    if (m && !modelStatsCache.has(m) && r.avg_model_price) {
      modelStatsCache.set(m, {
        model_name: m,
        avg_price: r.avg_model_price,
        total_count: r.model_offers_count || 1,
        avg_battery: null,
      });
    }
  }
  const modelsToFetch = [...new Set(items.map(r => (r.model_name || '').trim()).filter(m => m && (!modelStatsCache.has(m) || modelStatsCache.get(m).avg_battery === null)))];
  for (const m of modelsToFetch) {
    try { modelStatsCache.set(m, await API.getModelStats(m)); } catch (_) {}
  }
}

/* ------------------------------------------------------------------ */
/* Filtry i zapytania (w tym obsługa marży)                           */
/* ------------------------------------------------------------------ */
function applyQueryDefaults() {
  const qs = new URLSearchParams(location.search);
  if (qs.get('sort_by')) document.getElementById('filter-sort').value = qs.get('sort_by');
  if (qs.get('is_favorite') === 'true') document.getElementById('filter-fav-only').checked = true;
  if (qs.get('only_deals') === 'true') {
    const el = document.getElementById('filter-deals-only');
    if (el) el.checked = true;
  }
  if (qs.get('min_margin')) {
    const el = document.getElementById('filter-min-margin');
    if (el) el.value = qs.get('min_margin');
  }
}

async function loadModelsFilter() {
  try {
    const models = await API.getModels();
    const sel = document.getElementById('filter-model');
    models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m; opt.textContent = m;
      sel.appendChild(opt);
    });
  } catch (_) {}
}

function debounceFetch() {
  clearTimeout(state.debounceTimer);
  state.debounceTimer = setTimeout(() => fetchData(1), 350);
}

function setDamagedFilter(v) {
  document.getElementById('filter-damaged').value = v;
  fetchData(1);
}

function setPageSize(v) {
  state.pageSize = parseInt(v, 10) || 25;
  fetchData(1);
}

function getFilterParams() {
  const p = new URLSearchParams();
  const q = document.getElementById('filter-q').value.trim();
  const model = document.getElementById('filter-model').value;
  const minPrice = document.getElementById('filter-min-price').value;
  const maxPrice = document.getElementById('filter-max-price').value;
  const damaged = document.getElementById('filter-damaged').value;
  const sort = document.getElementById('filter-sort').value;
  const favOnly = document.getElementById('filter-fav-only').checked;
  const analyzedOnly = document.getElementById('filter-analyzed-only').checked;
  const dealsOnly = document.getElementById('filter-deals-only')?.checked;
  const minMargin = document.getElementById('filter-min-margin')?.value?.trim();

  if (q) p.append('q', q);
  if (model !== 'ALL') p.append('model', model);
  if (minPrice) p.append('min_price', minPrice);
  if (maxPrice) p.append('max_price', maxPrice);
  if (damaged !== 'ALL') p.append('is_damaged', damaged);
  if (favOnly) p.append('is_favorite', 'true');
  if (analyzedOnly) p.append('only_analyzed', 'true');
  if (dealsOnly) p.append('only_deals', 'true');
  if (minMargin) p.append('min_margin', minMargin);
  if (sort) p.append('sort_by', sort);
  return p;
}

async function fetchData(targetPage = state.page) {
  state.page = targetPage;
  const p = getFilterParams();
  p.append('page', state.page);
  p.append('page_size', state.pageSize);

  closeDock();
  const tbody = document.getElementById('offers-tbody');
  tbody.innerHTML = `<tr><td colspan="7" class="!py-14 text-center text-muted">
    <i data-lucide="loader-2" class="w-4 h-4 animate-spin inline-block mr-2 align-[-2px]"></i>${escapeHtml(t('of_loading'))}</td></tr>`;
  refreshIcons();

  try {
    const data = await API.getOffers(p);
    renderTable(data.items);
    updatePagination(data.total, data.page, data.total_pages);
    prefetchModelStats(data.items || []);
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" class="!py-16 text-center text-muted">
      <i data-lucide="alert-triangle" class="w-4 h-4 inline-block mr-2 align-[-2px] text-rose-600"></i>${escapeHtml(t('of_error', { msg: e.message }))}</td></tr>`;
  }
}

function batteryCell(bat) {
  if (bat === null || bat === undefined) return '<span class="text-faint font-mono text-xs">—</span>';
  const bar = bat >= 85 ? 'bg-mint' : bat >= 80 ? 'bg-sun' : 'bg-accent';
  const pct = bat >= 85 ? 'text-mint-700' : bat >= 80 ? 'text-sun-700' : 'text-accent-700';
  return `<div class="flex items-center justify-center gap-2">
    <div class="bat"><div class="${bar}" style="width:${Math.min(100, bat)}%"></div></div>
    <span class="font-mono text-[11px] font-semibold tabular-nums ${pct}">${bat}%</span></div>`;
}

function stateChip(r) {
  if (r.is_damaged === 1) return `<span class="chip chip-accent">${escapeHtml(t('chip_damaged'))}</span>`;
  if (r.ai_analyzed) return `<span class="chip chip-mint">${escapeHtml(t('chip_healthy'))}</span>`;
  return `<span class="chip chip-gray">${escapeHtml(t('chip_pending'))}</span>`;
}

/* Etykieta marży – precyzyjny mini-chip pod ceną */
function marginChip(r) {
  const pct = r.margin_pct !== null && r.margin_pct !== undefined;
  const avg = r.avg_model_price !== null && r.avg_model_price !== undefined ? fmtPLN(r.avg_model_price) : '';
  if (r.margin_pln > 0) {
    return `<span class="margin-chip pos" title="Średnia rynkowa: ${avg}"><i data-lucide="trending-up" class="w-2.5 h-2.5"></i>+${fmtInt(r.margin_pln)} zł${pct ? ` · +${r.margin_pct}%` : ''}</span>`;
  }
  if (r.margin_pln < 0) {
    return `<span class="margin-chip neg" title="Średnia rynkowa: ${avg}"><i data-lucide="trending-down" class="w-2.5 h-2.5"></i>${fmtInt(r.margin_pln)} zł${pct ? ` · ${r.margin_pct}%` : ''}</span>`;
  }
  return `<span class="margin-chip flat" title="Cena równa średniej rynkowej">0 zł</span>`;
}

/* ------------------------------------------------------------------ */
/* Render tabeli z wizualizacją marży                                 */
/* ------------------------------------------------------------------ */
function renderTable(items) {
  const tbody = document.getElementById('offers-tbody');
  closeDock();

  if (!items || items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="!py-16 text-center text-muted">
      <div class="w-10 h-10 rounded-lg bg-paper border border-line-soft grid place-items-center mx-auto mb-2.5"><i data-lucide="search-x" class="w-4 h-4 text-faint"></i></div>
      ${escapeHtml(t('of_empty'))}</td></tr>`;
    refreshIcons();
    return;
  }

  tbody.innerHTML = items.map(r => {
    const isFav = r.is_favorite === 1;
    const hasPrice = r.price !== null && r.price !== undefined;
    const hasBat = r.battery_health_pct !== null && r.battery_health_pct !== undefined;
    const hasMargin = r.margin_pln !== null && r.margin_pln !== undefined;
    const model = (r.model_name && r.model_name.trim()) || '';

    // Sygnatura wiersza: OKAZJA (zysk + czysty stan) / RYZYKO (uszkodzenie lub strata)
    const isDeal = hasMargin && r.margin_pln > 0 && r.is_damaged !== 1 && !!r.ai_analyzed;
    const isRisk = r.is_damaged === 1 || (hasMargin && r.margin_pln < 0);
    const rowCls = `offer-row${isDeal ? ' row-deal' : ''}${isRisk ? ' row-risk' : ''}`;

    const m = hasMargin ? marginChip(r) : '';
    const priceHtml = hasPrice
      ? `<div class="text-right">
          <span class="font-mono text-[13.5px] font-semibold tabular-nums leading-none">${fmtPLN(r.price)}</span>
          ${m ? `<div class="mt-1.5">${m}</div>` : ''}
        </div>`
      : '<span class="text-faint">—</span>';

    return `
      <tr class="${rowCls}"
          data-olx-id="${escapeHtml(r.olx_id)}"
          data-model="${escapeHtml(model)}"
          data-price="${hasPrice ? r.price : ''}"
          data-battery="${hasBat ? r.battery_health_pct : ''}"
          data-margin="${hasMargin ? r.margin_pln : ''}"
          data-avg-price="${r.avg_model_price !== null && r.avg_model_price !== undefined ? r.avg_model_price : ''}">
        <td class="text-center">
          <button onclick="toggleFavorite('${r.olx_id}')" class="star-btn ${isFav ? 'is-fav' : ''}" title="${escapeHtml(t('a_fav'))}">
            <i data-lucide="star" class="w-3.5 h-3.5"></i>
          </button>
        </td>
        <td>
          <div class="flex items-center gap-1.5 min-w-0">
            <span class="offer-title text-[12.5px] clamp-1">${escapeHtml(model || r.title)}</span>
            ${r.storage_gb ? `<span class="chip chip-gray shrink-0">${r.storage_gb} GB</span>` : ''}
          </div>
          <div class="offer-sub clamp-1">${escapeHtml(r.title)}</div>
        </td>
        <td class="whitespace-nowrap">${priceHtml}</td>
        <td class="whitespace-nowrap">${batteryCell(r.battery_health_pct)}</td>
        <td>
          <div class="flex items-center gap-1.5 min-w-0">${stateChip(r)}<span class="text-[11px] font-medium text-muted clamp-1">${escapeHtml(r.condition_state || '')}</span></div>
          <p class="offer-sub clamp-2">${escapeHtml(r.ai_summary || '—')}</p>
        </td>
        <td class="hidden xl:table-cell text-[11.5px]"><span class="text-muted clamp-1">${escapeHtml(r.location || '—')}</span></td>
        <td class="text-right whitespace-nowrap">
          <div class="inline-flex items-center gap-0.5">
            <button onclick="openDetailsModal('${r.olx_id}')" class="row-action" title="${escapeHtml(t('a_details'))}"><i data-lucide="eye" class="w-3.5 h-3.5"></i></button>
            <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener" class="row-action" title="${escapeHtml(t('a_open_olx'))}"><i data-lucide="external-link" class="w-3.5 h-3.5"></i></a>
            <button onclick="deleteOffer('${r.olx_id}')" class="row-action danger" title="${escapeHtml(t('a_delete'))}"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button>
          </div>
        </td>
      </tr>`;
  }).join('');
  refreshIcons();
}

/* ------------------------------------------------------------------ */
/* Paginacja i akcje                                                  */
/* ------------------------------------------------------------------ */
function updatePagination(total, page, totalPages) {
  state.totalPages = Math.max(1, totalPages || 1);
  document.getElementById('offers-total-badge').textContent = fmtInt(total);
  const offersStr = `${fmtInt(total)} ${pluralize(total, 'offers_n')}`;
  document.getElementById('pagination-info').textContent = t('pg_info', {
    page: page,
    total: state.totalPages,
    offers: offersStr,
  });
  document.getElementById('pagination-current').textContent = `${page} / ${state.totalPages}`;
  document.getElementById('page-prev-btn').disabled = page <= 1;
  document.getElementById('page-next-btn').disabled = page >= state.totalPages;
}

function changePage(delta) {
  const target = state.page + delta;
  if (target >= 1 && target <= state.totalPages) fetchData(target);
}

async function toggleFavorite(olxId) {
  const res = await API.toggleFavorite(olxId);
  if (!res.ok) return toast(t('t_fav_failed'), 'error');
  fetchData(state.page);
}

async function deleteOffer(olxId) {
  if (!confirm(t('confirm_delete', { id: olxId }))) return;
  const res = await API.deleteOffer(olxId);
  res.ok ? toast(t('t_deleted'), 'success') : toast(t('t_delete_failed'), 'error');
  fetchData(state.page);
}

function resetFilters() {
  document.getElementById('filter-q').value = '';
  document.getElementById('filter-model').value = 'ALL';
  document.getElementById('filter-min-price').value = '';
  document.getElementById('filter-max-price').value = '';
  document.getElementById('filter-sort').value = 'newest';
  document.getElementById('filter-fav-only').checked = false;
  document.getElementById('filter-analyzed-only').checked = false;
  const dealsEl = document.getElementById('filter-deals-only');
  if (dealsEl) dealsEl.checked = false;
  const minMarginEl = document.getElementById('filter-min-margin');
  if (minMarginEl) minMarginEl.value = '';
  document.getElementById('filter-damaged').value = 'ALL';
  document.querySelector('input[name="filter-damaged-r"][value="ALL"]').checked = true;
  fetchData(1);
}