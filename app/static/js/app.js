// ── BolsaTracker SPA ─────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const API = '';  // same origin

async function api(path, opts = {}) {
  const r = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  return r.json();
}

// ── Router ───────────────────────────────────────────────
const pages = { dashboard: renderDashboard, buffett: renderBuffett, sentiment: renderSentiment, approvals: renderApprovals, history: renderHistory };
let currentPage = 'dashboard';

function navigate(page) {
  currentPage = page;
  $$('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.page === page));
  pages[page]();
}

// ── Pending count polling ────────────────────────────────
async function updatePendingBadge() {
  try {
    const proposals = await api('/api/proposals?status=pending');
    const badge = $('#pending-badge');
    if (proposals.length > 0) {
      badge.textContent = proposals.length;
      badge.style.display = 'inline';
    } else {
      badge.style.display = 'none';
    }
  } catch {}
}
setInterval(updatePendingBadge, 30000);

// ── Helpers ──────────────────────────────────────────────
function fmtARS(v) { return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(v || 0); }
function fmtNum(v) { return (v || 0).toLocaleString(); }
function fmtDate(d) { return new Date(d).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: '2-digit' }); }
function fmtTime(d) { return new Date(d).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' }); }
function scoreColor(s) { return s > 20 ? 'var(--green)' : s < -20 ? 'var(--red)' : 'var(--yellow)'; }
function scoreBadge(s) { return s > 0 ? 'badge-green' : s < 0 ? 'badge-red' : 'badge-yellow'; }
function changeBadge(c) { return c === 'new' || c === 'increased' ? 'badge-green' : c === 'decreased' || c === 'exited' ? 'badge-red' : 'badge-blue'; }
function loading(n = 5) { return Array(n).fill('<div class="loading"></div>').join(''); }

// ── Dashboard ────────────────────────────────────────────
async function renderDashboard() {
  const main = $('#content');
  main.innerHTML = `
    <div class="page-header"><div><h2>📊 Dashboard</h2></div></div>
    <div class="grid grid-4 mb-6" id="stats">${loading(4)}</div>
    <div class="grid grid-2 mb-6">
      <div class="card"><h3>Portfolio Argentina</h3><div id="portfolio-ar">${loading(3)}</div></div>
      <div class="card"><h3>Ultimos Trades</h3><div id="recent-trades">${loading(3)}</div></div>
    </div>
  `;

  const [account, portfolioAr, trades, proposals] = await Promise.allSettled([
    api('/api/account'), api('/api/portfolio/argentina'), api('/api/trades?limit=5'), api('/api/proposals?status=pending')
  ]);

  const acc = account.status === 'fulfilled' ? account.value : {};
  const total = acc.totalEnPesos || 0;
  const pending = proposals.status === 'fulfilled' ? proposals.value.length : 0;

  $('#stats').innerHTML = `
    <div class="card stat-card"><div class="stat-icon">💰</div><div><div class="stat-label">Capital Total</div><div class="stat-value">${fmtARS(total)}</div></div></div>
    <div class="card stat-card"><div class="stat-icon">📈</div><div><div class="stat-label">Buffett (70%)</div><div class="stat-value">${fmtARS(total * 0.7)}</div><div class="stat-sub">Replica 13F</div></div></div>
    <div class="card stat-card"><div class="stat-icon">🧠</div><div><div class="stat-label">Sentiment (30%)</div><div class="stat-value">${fmtARS(total * 0.3)}</div><div class="stat-sub">AI Trading</div></div></div>
    <div class="card stat-card"><div class="stat-icon">⏳</div><div><div class="stat-label">Pendientes</div><div class="stat-value">${pending}</div><div class="stat-sub">Trades por aprobar</div></div></div>
  `;

  // Portfolio
  const port = portfolioAr.status === 'fulfilled' ? portfolioAr.value : {};
  if (port.activos?.length) {
    $('#portfolio-ar').innerHTML = `<table><thead><tr><th>Ticker</th><th class="text-right">Cant</th><th class="text-right">Precio</th><th class="text-right">P&L</th></tr></thead><tbody>
      ${port.activos.map(a => `<tr><td class="font-mono text-brand">${a.simbolo}</td><td class="text-right">${a.cantidad}</td><td class="text-right">$${a.ultimoPrecio?.toFixed(2) || 0}</td><td class="text-right ${a.gananciaPorcentaje >= 0 ? 'text-green' : 'text-red'}">${a.gananciaPorcentaje >= 0 ? '+' : ''}${a.gananciaPorcentaje?.toFixed(1) || 0}%</td></tr>`).join('')}
    </tbody></table>`;
  } else {
    $('#portfolio-ar').innerHTML = `<div class="empty"><div class="icon">📂</div><p>${port.error ? 'Error: ' + port.error : 'Sin posiciones. Configura tus credenciales IOL en .env'}</p></div>`;
  }

  // Trades
  const tradeList = trades.status === 'fulfilled' ? trades.value : [];
  if (tradeList.length) {
    $('#recent-trades').innerHTML = tradeList.map(t => `
      <div class="flex items-center justify-between" style="padding:8px 0;border-bottom:1px solid var(--border)">
        <div class="flex items-center gap-4"><span class="badge ${t.action === 'buy' ? 'badge-green' : 'badge-red'}">${t.action === 'buy' ? 'COMPRA' : 'VENTA'}</span><div><div class="font-mono" style="font-weight:600">${t.ticker}</div><div class="text-muted" style="font-size:11px">${t.strategy} - ${fmtDate(t.timestamp)}</div></div></div>
        <div class="text-right"><div style="font-weight:600">${t.quantity} x $${t.price?.toFixed(2)}</div><div class="text-muted" style="font-size:11px">${t.currency} ${fmtNum(t.total_amount)}</div></div>
      </div>
    `).join('');
  } else {
    $('#recent-trades').innerHTML = '<div class="empty"><div class="icon">📭</div><p>No hay trades todavia</p></div>';
  }
}

// ── Buffett ──────────────────────────────────────────────
async function renderBuffett() {
  const main = $('#content');
  main.innerHTML = `
    <div class="page-header"><div><h2>📈 Estrategia Buffett (70%)</h2><p>Replica del portfolio de Berkshire Hathaway basado en 13F filings</p></div>
      <button class="btn btn-primary" id="sync-btn" onclick="syncBuffett()">🔄 Sincronizar 13F</button></div>
    <div class="card mb-6" id="filings-box"><h3>Ultimos Filings</h3><div id="filings">${loading(1)}</div></div>
    <div class="card" id="holdings-box"><h3>Holdings de Berkshire Hathaway</h3><div id="holdings">${loading(5)}</div></div>
    <div id="sync-status"></div>
  `;

  const [filings, holdings] = await Promise.allSettled([api('/api/buffett/filings'), api('/api/buffett/holdings')]);

  const fList = filings.status === 'fulfilled' ? filings.value : [];
  if (fList.length && !fList.error) {
    $('#filings').innerHTML = `<div class="grid grid-3">${fList.slice(0, 3).map(f => `
      <div style="background:rgba(255,255,255,.03);border-radius:8px;padding:12px">
        <div style="font-weight:600">Q ending ${f.report_date}</div>
        <div class="text-muted" style="font-size:12px">Filed: ${f.filing_date}</div>
        <a href="${f.primary_doc_url}" target="_blank" style="font-size:12px">Ver filing en SEC →</a>
      </div>
    `).join('')}</div>
    <div class="text-muted" style="font-size:11px;margin-top:8px">Fuente: SEC EDGAR en tiempo real (CIK 0001067983). Los 13F se publican ~45 dias despues del cierre del quarter.</div>`;
  } else {
    const err = fList.error || (filings.status === 'rejected' ? 'Network error' : '');
    $('#filings').innerHTML = `<div class="text-muted">${err ? 'Error cargando filings: ' + err + '. ' : ''}Hace click en Sincronizar para obtener holdings.</div>`;
  }

  const hList = holdings.status === 'fulfilled' ? holdings.value : [];
  if (hList.length) {
    $('#holdings').innerHTML = `<table><thead><tr><th>Issuer</th><th>Ticker</th><th class="text-right">Shares</th><th class="text-right">Value ($K)</th><th class="text-center">Cambio</th><th class="text-right">Delta</th></tr></thead><tbody>
      ${hList.map(h => `<tr><td>${h.issuer}</td><td class="font-mono text-brand">${h.ticker || h.cusip}</td><td class="text-right">${fmtNum(h.shares)}</td><td class="text-right">$${fmtNum(h.value_thousands)}</td><td class="text-center"><span class="badge ${changeBadge(h.change_type)}">${h.change_type || '?'}</span></td><td class="text-right font-mono">${h.change_shares ? (h.change_shares > 0 ? '+' : '') + fmtNum(h.change_shares) : '-'}</td></tr>`).join('')}
    </tbody></table>`;
  } else {
    $('#holdings').innerHTML = '<div class="empty"><div class="icon">📊</div><p>No hay holdings cargados. Hace click en "Sincronizar 13F".</p></div>';
  }
}

async function syncBuffett() {
  const btn = $('#sync-btn');
  btn.disabled = true;
  btn.textContent = '⏳ Sincronizando...';
  try {
    const result = await api('/api/buffett/sync', { method: 'POST' });
    if (result.error) {
      $('#sync-status').innerHTML = `<div class="card mt-2" style="border-color:var(--red);color:var(--red)">Error: ${result.error}</div>`;
    } else {
      $('#sync-status').innerHTML = `<div class="card mt-2" style="border-color:var(--green);color:var(--green)">Sincronizado: ${result.holdings_count} holdings, ${result.new_positions} nuevas, ${result.exits} exits (Q ${result.quarter_end})</div>`;
      renderBuffett();
    }
  } catch (e) {
    $('#sync-status').innerHTML = `<div class="card mt-2" style="border-color:var(--red);color:var(--red)">Error: ${e.message}</div>`;
  }
  btn.disabled = false;
  btn.textContent = '🔄 Sincronizar 13F';
}

// ── Sentiment ────────────────────────────────────────────
let sentimentResult = null;

async function renderSentiment() {
  const main = $('#content');
  main.innerHTML = `
    <div class="page-header"><div><h2>🧠 Estrategia Sentiment (30%)</h2><p>Escaneo de mercado via StockTwits, Reddit, Finnhub + AI</p></div>
      <button class="btn btn-primary" id="scan-btn" onclick="scanMarket()" style="background:var(--purple)">🔎 Escanear Mercado</button>
    </div>
    <div id="scan-results"></div>
    <div class="card mb-6"><h3>Analizar Ticker Individual</h3><div class="search-row mt-2"><input type="text" id="ticker-input" placeholder="Ingresa un ticker (ej: AAPL, MSFT, NVDA)" onkeydown="if(event.key==='Enter')analyzeTicker()"><button class="btn btn-primary" id="analyze-btn" onclick="analyzeTicker()">🔍 Analizar</button></div></div>
    <div id="sentiment-results"></div>
  `;
}

async function scanMarket() {
  const btn = $('#scan-btn');
  btn.disabled = true;
  btn.innerHTML = '⏳ Escaneando watchlist...';

  try {
    const result = await api('/api/scan', { method: 'POST' });
    if (result.error) {
      $('#scan-results').innerHTML = `<div class="card mb-6" style="border-color:var(--red);color:var(--red)">Error: ${result.error}</div>`;
      return;
    }

    let html = `<div class="card mb-6">
      <div class="flex justify-between items-center mb-4">
        <h3>Resultado del Escaneo</h3>
        <div><span class="badge badge-blue">${result.scanned} escaneados</span> <span class="badge badge-green" style="margin-left:6px">${result.proposals_created} propuestas creadas</span></div>
      </div>`;

    if (result.proposals_created > 0) {
      html += `<div style="background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.3);border-radius:8px;padding:12px;margin-bottom:16px;font-size:13px;color:var(--green)">
        Se crearon ${result.proposals_created} propuesta(s) de trade. Anda a <a href="#" onclick="navigate('approvals');return false" style="color:var(--green);text-decoration:underline">Approvals</a> para revisarlas.
      </div>`;
    }

    html += `<table><thead><tr><th>Ticker</th><th class="text-right">Score</th><th class="text-right">Confianza</th><th class="text-right">Menciones</th><th class="text-center">Signal</th><th>Propuesta</th></tr></thead><tbody>`;

    for (const r of result.results) {
      const absScore = Math.abs(r.score || 0);
      const signal = absScore > 35 ? (r.score > 0 ? 'BULLISH' : 'BEARISH') : 'NEUTRAL';
      const signalBadge = absScore > 35 ? (r.score > 0 ? 'badge-green' : 'badge-red') : 'badge-yellow';

      let proposalCell = '-';
      if (r.proposal && typeof r.proposal === 'object') {
        proposalCell = `<span class="badge ${r.proposal.action === 'buy' ? 'badge-green' : 'badge-red'}">${r.proposal.action.toUpperCase()} ${r.proposal.qty}x $${r.proposal.price?.toFixed(2)}</span>`;
      } else if (r.proposal === 'already_pending') {
        proposalCell = '<span class="badge badge-yellow">ya pendiente</span>';
      } else if (r.error) {
        proposalCell = `<span class="text-muted" style="font-size:11px">${r.error}</span>`;
      }

      html += `<tr>
        <td class="font-mono text-brand" style="font-weight:600">${r.ticker}</td>
        <td class="text-right font-mono" style="color:${scoreColor(r.score)};font-weight:600">${r.score > 0 ? '+' : ''}${(r.score||0).toFixed(1)}</td>
        <td class="text-right">${((r.confidence||0) * 100).toFixed(0)}%</td>
        <td class="text-right">${r.mentions || 0}</td>
        <td class="text-center"><span class="badge ${signalBadge}">${signal}</span></td>
        <td>${proposalCell}</td>
      </tr>`;
    }

    html += '</tbody></table></div>';
    $('#scan-results').innerHTML = html;

    updatePendingBadge();
  } catch (e) {
    $('#scan-results').innerHTML = `<div class="card mb-6" style="border-color:var(--red);color:var(--red)">Error: ${e.message}</div>`;
  }

  btn.disabled = false;
  btn.innerHTML = '🔎 Escanear Mercado';
}

async function analyzeTicker() {
  const input = $('#ticker-input');
  const ticker = input.value.trim().toUpperCase();
  if (!ticker) return;

  const btn = $('#analyze-btn');
  btn.disabled = true;
  btn.textContent = '⚡ Analizando...';
  $('#sentiment-results').innerHTML = loading(3);

  try {
    const result = await api(`/api/analyze/${ticker}`, { method: 'POST' });
    sentimentResult = result;

    if (result.error) {
      $('#sentiment-results').innerHTML = `<div class="card" style="border-color:var(--red);color:var(--red)">Error: ${result.error}</div>`;
      return;
    }

    const s = result.sentiment || {};
    const g = result.grok;
    const m = result.gemini;

    let html = '<div class="grid grid-3 mb-6">';

    // Sentiment card
    html += `<div class="card"><h3>Sentiment Agregado</h3>
      <div class="flex justify-between" style="font-size:13px"><span class="text-muted">Composite</span><span style="color:${scoreColor(s.composite_score)}">${s.composite_score > 0 ? '+' : ''}${s.composite_score}</span></div>
      <div class="score-bar"><div class="score-fill" style="width:${(s.composite_score + 100) / 2}%;background:${scoreColor(s.composite_score)}"></div></div>
      <div style="margin-top:12px;font-size:13px;color:var(--muted)">Confidence: ${(s.confidence * 100).toFixed(0)}% | Menciones: ${s.total_mentions}</div>
      <div style="margin-top:12px;border-top:1px solid var(--border);padding-top:12px;font-size:12px">`;
    if (s.sources?.stocktwits) html += `<div class="flex justify-between mb-4"><span class="text-muted">StockTwits</span><span>${s.sources.stocktwits.bullish}B/${s.sources.stocktwits.bearish}b → <span style="color:${scoreColor(s.sources.stocktwits.score)}">${s.sources.stocktwits.score > 0 ? '+' : ''}${s.sources.stocktwits.score}</span></span></div>`;
    if (s.sources?.reddit) html += `<div class="flex justify-between mb-4"><span class="text-muted">Reddit</span><span>${s.sources.reddit.length} subs</span></div>`;
    if (s.sources?.finnhub) html += `<div class="flex justify-between"><span class="text-muted">Finnhub</span><span style="color:${scoreColor(s.sources.finnhub.score)}">${s.sources.finnhub.score > 0 ? '+' : ''}${s.sources.finnhub.score}</span></div>`;
    html += '</div></div>';

    // Grok card
    html += `<div class="card"><h3>Grok Analysis ${g && !g.error ? `<span class="badge ${scoreBadge(g.score)}">${g.recommendation}</span>` : ''}</h3>`;
    if (g && !g.error) {
      html += `<div class="flex justify-between" style="font-size:13px"><span class="text-muted">Score</span><span style="color:${scoreColor(g.score)}">${g.score > 0 ? '+' : ''}${g.score}</span></div>
        <div class="score-bar"><div class="score-fill" style="width:${(g.score + 100) / 2}%;background:${scoreColor(g.score)}"></div></div>
        <p style="margin-top:12px;font-size:13px">${g.reasoning}</p>
        <p style="margin-top:8px;font-size:12px;color:var(--muted);font-style:italic">${g.insight || ''}</p>`;
    } else {
      html += `<p class="text-muted" style="font-size:13px">${g?.error || 'Grok no disponible (configurar GROK_API_KEY)'}</p>`;
    }
    html += '</div>';

    // Gemini card
    html += `<div class="card"><h3>Gemini Analysis ${m && !m.error ? `<span class="badge ${scoreBadge(m.score)}">${m.recommendation}</span>` : ''}</h3>`;
    if (m && !m.error) {
      html += `<div class="flex justify-between" style="font-size:13px"><span class="text-muted">Score</span><span style="color:${scoreColor(m.score)}">${m.score > 0 ? '+' : ''}${m.score}</span></div>
        <div class="score-bar"><div class="score-fill" style="width:${(m.score + 100) / 2}%;background:${scoreColor(m.score)}"></div></div>
        <p style="margin-top:12px;font-size:13px">${m.reasoning}</p>
        <p style="margin-top:8px;font-size:12px;color:var(--muted);font-style:italic">${m.insight || ''}</p>`;
    } else {
      html += `<p class="text-muted" style="font-size:13px">${m?.error || 'Gemini no disponible (configurar GEMINI_API_KEY)'}</p>`;
    }
    html += '</div></div>';

    // Proposal
    if (result.proposal) {
      const p = result.proposal;
      html += `<div class="card mb-6" style="border:1px solid var(--green);background:rgba(34,197,94,.05)">
        <h3 style="color:var(--green)">⚡ Trade Propuesto</h3>
        <p style="font-size:14px">Ambas IAs coinciden: <strong>${p.action.toUpperCase()}</strong> <strong>${p.ticker}</strong> en ${p.market}</p>
        <p class="text-muted" style="font-size:12px;margin-top:4px">Score prom: ${p.avg_score} | Grok: ${p.grok_rec} | Gemini: ${p.gemini_rec}</p>
        <p style="font-size:12px;color:var(--yellow);margin-top:8px">Ve a Approvals para revisar y aprobar este trade.</p>
      </div>`;
    }

    $('#sentiment-results').innerHTML = html;
  } catch (e) {
    $('#sentiment-results').innerHTML = `<div class="card" style="border-color:var(--red);color:var(--red)">Error: ${e.message}</div>`;
  }

  btn.disabled = false;
  btn.textContent = '🔍 Analizar';
}

// ── Approvals ────────────────────────────────────────────
async function renderApprovals() {
  const main = $('#content');
  main.innerHTML = `
    <div class="page-header"><div><h2>✅ Aprobaciones</h2><p>Revisa y aprueba los trades propuestos por la IA</p></div></div>
    <h3 class="mb-4" id="pending-title">Pendientes</h3>
    <div id="pending-list">${loading(2)}</div>
    <div class="card mt-2"><h3>Historial de Propuestas</h3><div id="all-proposals">${loading(3)}</div></div>
  `;

  const [pending, all] = await Promise.allSettled([api('/api/proposals?status=pending'), api('/api/proposals?status=all')]);
  const pList = pending.status === 'fulfilled' ? pending.value : [];
  const aList = all.status === 'fulfilled' ? all.value : [];

  $('#pending-title').textContent = `Pendientes (${pList.length})`;

  if (pList.length === 0) {
    $('#pending-list').innerHTML = '<div class="card empty"><div class="icon">✅</div><p>No hay trades pendientes</p><p style="font-size:12px;margin-top:4px">Las propuestas aparecen cuando Grok y Gemini coinciden</p></div>';
  } else {
    $('#pending-list').innerHTML = pList.map(p => {
      let reasoning = {};
      try { reasoning = JSON.parse(p.ai_reasoning || '{}'); } catch {}
      const isExpiring = new Date(p.expires_at) - Date.now() < 3600000;
      const timeLeft = getTimeLeft(p.expires_at);

      return `<div class="card mb-4 proposal-card ${p.action === 'sell' ? 'sell' : ''}" style="display:flex">
        <div class="proposal-body">
          <div class="flex items-center gap-4 mb-4">
            <span style="font-size:18px;font-weight:700;color:${p.action === 'buy' ? 'var(--green)' : 'var(--red)'}">${p.action === 'buy' ? 'COMPRAR' : 'VENDER'}</span>
            <span style="font-size:20px;font-weight:700">${p.ticker}</span>
            <span class="badge badge-blue">${p.market}</span>
            <span class="badge badge-yellow">${p.strategy}</span>
          </div>
          <div class="proposal-grid">
            <div><label>Cantidad</label><div style="font-weight:600">${p.suggested_qty}</div></div>
            <div><label>Precio Est.</label><div style="font-weight:600">${p.currency} ${p.suggested_price?.toFixed(2) || 'market'}</div></div>
            <div><label>Score</label><div style="font-weight:600;color:${scoreColor(p.sentiment_score)}">${p.sentiment_score > 0 ? '+' : ''}${p.sentiment_score?.toFixed(1)}</div></div>
          </div>
          <div class="ai-box">
            ${reasoning.grok && !reasoning.grok.error ? `<div class="mb-4"><span class="provider text-brand">Grok (${reasoning.grok.recommendation}):</span> ${reasoning.grok.reasoning}</div>` : ''}
            ${reasoning.gemini && !reasoning.gemini.error ? `<div><span class="provider" style="color:var(--purple)">Gemini (${reasoning.gemini.recommendation}):</span> ${reasoning.gemini.reasoning}</div>` : ''}
          </div>
          <div style="margin-top:8px;font-size:11px;color:${isExpiring ? 'var(--yellow)' : 'var(--muted)'}">${isExpiring ? '⚠️' : '🕐'} Expira en ${timeLeft}</div>
        </div>
        <div class="proposal-actions">
          <button class="btn btn-primary" onclick="approveProposal(${p.id})">✅ Aprobar</button>
          <button class="btn btn-outline" onclick="modifyProposal(${p.id}, ${p.suggested_qty})">✏️ Modificar</button>
          <button class="btn btn-danger" onclick="rejectProposal(${p.id})">❌ Rechazar</button>
        </div>
      </div>`;
    }).join('');
  }

  // All proposals history
  if (aList.length) {
    $('#all-proposals').innerHTML = `<table><thead><tr><th>Fecha</th><th>Ticker</th><th>Accion</th><th class="text-center">Status</th><th class="text-right">Score</th></tr></thead><tbody>
      ${aList.map(p => `<tr><td class="text-muted">${fmtDate(p.created_at)}</td><td class="font-mono" style="font-weight:600">${p.ticker}</td><td><span class="badge ${p.action === 'buy' ? 'badge-green' : 'badge-red'}">${p.action}</span></td><td class="text-center"><span class="badge ${p.status === 'executed' ? 'badge-green' : p.status === 'rejected' ? 'badge-red' : p.status === 'expired' ? 'badge-yellow' : 'badge-blue'}">${p.status}</span></td><td class="text-right font-mono">${p.sentiment_score?.toFixed(1) || '-'}</td></tr>`).join('')}
    </tbody></table>`;
  } else {
    $('#all-proposals').innerHTML = '<div class="text-muted" style="padding:12px">Sin historial</div>';
  }
}

function getTimeLeft(expiresAt) {
  const diff = new Date(expiresAt) - Date.now();
  if (diff <= 0) return 'Expirado';
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  return `${h}h ${m}m`;
}

async function approveProposal(id, qty) {
  const url = qty ? `/api/proposals/${id}/approve?qty=${qty}` : `/api/proposals/${id}/approve`;
  const result = await api(url, { method: 'POST' });
  if (result.error) alert('Error: ' + result.error);
  else alert(`Orden ejecutada! #${result.order_id}`);
  renderApprovals();
  updatePendingBadge();
}

async function rejectProposal(id) {
  await api(`/api/proposals/${id}/reject`, { method: 'POST' });
  renderApprovals();
  updatePendingBadge();
}

function modifyProposal(id, currentQty) {
  const qty = prompt(`Modificar cantidad (actual: ${currentQty}):`, currentQty);
  if (qty && !isNaN(qty)) approveProposal(id, parseInt(qty));
}

// ── History ──────────────────────────────────────────────
async function renderHistory() {
  const main = $('#content');
  main.innerHTML = `
    <div class="page-header"><div><h2>📜 Historial de Trades</h2><p>Registro completo de operaciones ejecutadas</p></div>
      <select id="strategy-filter" onchange="renderHistory()" style="width:160px"><option value="">Todas</option><option value="buffett">Buffett (70%)</option><option value="sentiment">Sentiment (30%)</option></select>
    </div>
    <div class="grid grid-3 mb-6">
      <div class="card stat-card"><div class="stat-icon">📊</div><div><div class="stat-label">Total Trades</div><div class="stat-value" id="total-trades">-</div></div></div>
      <div class="card stat-card"><div class="stat-icon" style="color:var(--green)">🟢</div><div><div class="stat-label">Compras</div><div class="stat-value text-green" id="buy-count">-</div></div></div>
      <div class="card stat-card"><div class="stat-icon" style="color:var(--red)">🔴</div><div><div class="stat-label">Ventas</div><div class="stat-value text-red" id="sell-count">-</div></div></div>
    </div>
    <div class="card"><div id="trades-table">${loading(5)}</div></div>
  `;

  const filter = $('#strategy-filter')?.value || '';
  const url = filter ? `/api/trades?strategy=${filter}&limit=100` : '/api/trades?limit=100';
  const trades = await api(url);

  $('#total-trades').textContent = trades.length;
  $('#buy-count').textContent = trades.filter(t => t.action === 'buy').length;
  $('#sell-count').textContent = trades.filter(t => t.action === 'sell').length;

  if (trades.length) {
    $('#trades-table').innerHTML = `<table><thead><tr><th>Fecha</th><th>Estrategia</th><th>Accion</th><th>Ticker</th><th>Mercado</th><th class="text-right">Cant</th><th class="text-right">Precio</th><th class="text-right">Total</th><th class="text-center">Status</th><th>IOL #</th></tr></thead><tbody>
      ${trades.map(t => `<tr>
        <td class="text-muted">${fmtDate(t.timestamp)}</td>
        <td><span class="badge ${t.strategy === 'buffett' ? 'badge-blue' : 'badge-purple'}">${t.strategy}</span></td>
        <td><span class="badge ${t.action === 'buy' ? 'badge-green' : 'badge-red'}">${t.action === 'buy' ? 'COMPRA' : 'VENTA'}</span></td>
        <td class="font-mono text-brand" style="font-weight:600">${t.ticker}</td>
        <td class="text-muted">${t.market}</td>
        <td class="text-right">${fmtNum(t.quantity)}</td>
        <td class="text-right">$${t.price?.toFixed(2)}</td>
        <td class="text-right" style="font-weight:600">${t.currency} ${fmtNum(t.total_amount)}</td>
        <td class="text-center"><span class="badge ${t.status === 'executed' ? 'badge-green' : t.status === 'failed' ? 'badge-red' : 'badge-yellow'}">${t.status}</span></td>
        <td class="font-mono text-muted" style="font-size:11px">${t.iol_order_id || '-'}</td>
      </tr>`).join('')}
    </tbody></table>`;
  } else {
    $('#trades-table').innerHTML = '<div class="empty"><div class="icon">📜</div><p>No hay trades en el historial</p></div>';
  }
}

// ── Init ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  $$('.nav-item').forEach(n => n.addEventListener('click', () => navigate(n.dataset.page)));
  navigate('dashboard');
  updatePendingBadge();
});
