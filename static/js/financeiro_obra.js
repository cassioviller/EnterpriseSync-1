/* Painel Financeiro da Obra — carrega sob demanda e renderiza com Chart.js. */
(function () {
  var BRL = function (v) { return 'R$ ' + Math.round(v || 0).toLocaleString('pt-BR'); };
  var BRLk = function (v) { return 'R$ ' + Math.round((v || 0) / 1000).toLocaleString('pt-BR') + 'k'; };
  var C = {}, loaded = false, ENDPOINT = null, CONFIG_ENDPOINT = null, OBRA_ID = null, cfgBound = false;
  function el(id) { return document.getElementById(id); }
  function csrfToken() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }

  function kpiRow(label, valor, cls) {
    return '<div class="d-flex justify-content-between align-items-baseline py-1 border-bottom">' +
      '<span class="small text-muted">' + label + '</span>' +
      '<span class="fw-bold ' + (cls || '') + '" style="font-variant-numeric:tabular-nums">' +
      BRL(valor) + '</span></div>';
  }
  function renderKPIs(k) {
    var pos = function (v) { return (v || 0) >= 0 ? 'text-success' : 'text-danger'; };
    var pct = (k.lucro_pct != null)
      ? ' <small class="text-muted">(' + (k.lucro_pct * 100).toFixed(1) + '%)</small>' : '';
    el('fin-kpi-resultado').innerHTML =
      kpiRow('Venda (contrato)', k.venda, '') +
      kpiRow('Custo total', k.custo_total, '') +
      kpiRow('Imposto', k.imposto, '') +
      kpiRow('Lucro projetado' + pct, k.lucro_projetado, pos(k.lucro_projetado)).replace('border-bottom', '');
    el('fin-kpi-caixa').innerHTML =
      kpiRow('Recebido até hoje', k.recebido_ate_hoje, '') +
      kpiRow('Verba disponível', k.verba_disponivel, pos(k.verba_disponivel)).replace('border-bottom', '');
    el('fin-kpi-custo').innerHTML =
      kpiRow('Desembolso Veks', k.desembolso_veks, '') +
      kpiRow('Faturamento direto', k.fat_direto, '') +
      kpiRow('Custo realizado', k.custo_realizado, '').replace('border-bottom', '');
  }
  function renderMedicoes(meds) {
    el('fin-medicoes').innerHTML = (meds || []).map(function (m) {
      var d = m.data ? m.data.split('-').reverse().join('/') : '—';
      return '<tr><td>' + m.nome + '</td><td>' + d + '</td><td>' +
        (m.pct * 100).toFixed(1) + '%</td><td class="text-end">' + BRL(m.valor) + '</td></tr>';
    }).join('');
  }
  function renderAlerta(div) {
    if (!div || !div.resumo || Math.abs(div.resumo.delta_veks || 0) <= 1) { el('fin-alerta').innerHTML = ''; return; }
    var r = div.resumo;
    el('fin-alerta').innerHTML = '<div class="alert alert-warning">' +
      '<strong>Inconsistência dos Indiretos:</strong> Veks etapas ' + BRL(r.veks_etapas) +
      ' × planilha ' + BRL(r.veks_verbatim) + ' (Δ ' + BRL(r.delta_veks) + '). ' +
      'Lucro em caixa (planilha) ' + BRL(r.lucro_em_caixa) + '. Decida 3,5 vs 5 meses dos Indiretos.</div>';
  }
  // Alerta de caixa negativo — derivado ao vivo do fluxo recalculado (caixa.meses_negativos).
  // Some/aparece sozinho conforme os valores mudam; nada é persistido.
  function renderAlertaCaixa(caixa) {
    var negs = (caixa && caixa.meses_negativos) || [];
    if (!negs.length) { el('fin-alerta-caixa').innerHTML = ''; return; }
    var lista = negs.map(function (n) {
      return '<strong>' + n.mes + '</strong> (' + BRL(n.caixa_final) + ')';
    }).join(', ');
    var plural = negs.length > 1;
    el('fin-alerta-caixa').innerHTML = '<div class="alert alert-danger mb-0">' +
      '<i class="fas fa-triangle-exclamation me-1"></i>' +
      '<strong>Caixa negativo</strong> ' + (plural ? 'nos meses' : 'no mês') + ': ' + lista +
      '. A Veks desembolsa mais do que recebeu nesse(s) período(s) — avalie adiantar medição ou ' +
      'reescalonar desembolso.</div>';
  }
  function etapaLinhaHTML(it) {
    var sel = function (v) { return it && it.fonte === v ? ' selected' : ''; };
    return '<tr>' +
      '<td><input class="form-control form-control-sm fin-it-desc" value="' +
        ((it && it.descricao) ? String(it.descricao).replace(/"/g, '&quot;') : '') + '"></td>' +
      '<td><input type="number" step="0.01" class="form-control form-control-sm fin-it-valor text-end" value="' +
        (it ? Number(it.valor || 0) : 0) + '"></td>' +
      '<td><select class="form-select form-select-sm fin-it-fonte">' +
        '<option value="veks"' + sel('veks') + '>Veks</option>' +
        '<option value="fat_direto"' + sel('fat_direto') + '>Fat direto</option>' +
      '</select></td>' +
      '<td><input type="date" class="form-control form-control-sm fin-it-ini" value="' +
        ((it && it.data_inicio) ? String(it.data_inicio).slice(0, 10) : '') + '"></td>' +
      '<td><input type="date" class="form-control form-control-sm fin-it-fim" value="' +
        ((it && it.data_fim) ? String(it.data_fim).slice(0, 10) : '') + '"></td>' +
      '<td class="text-center"><button type="button" class="btn btn-sm btn-link text-danger fin-it-del p-0">&times;</button></td>' +
    '</tr>';
  }
  function showEtapa(et) {
    var box = el('fin-etapa-det');
    if (et.osc_id == null) {
      box.innerHTML = '<div class="border rounded p-3 bg-light"><strong>' + et.nome + '</strong>' +
        '<div class="small text-muted mt-1">Etapa sem custo único vinculável — edição indisponível.</div></div>';
      return;
    }
    var linhas = (et.itens || []).map(etapaLinhaHTML).join('');
    box.innerHTML =
      '<div class="border rounded p-3 bg-light">' +
      '<div class="d-flex justify-content-between mb-2"><strong>' + et.nome +
        (et.tipo === 'periodo' ? ' <span class="badge bg-secondary" title="Custo de período — sem avanço físico, fora do RDO/cronograma">período</span>' : '') +
        '</strong>' +
        '<span>Realizado: ' + BRL(et.realizado) + ' / Previsto: <span id="fin-it-prev">' + BRL(et.previsto) + '</span></span></div>' +
      '<table class="table table-sm align-middle mb-2"><thead><tr>' +
        '<th>Descrição</th><th class="text-end" style="width:130px">Valor (R$)</th>' +
        '<th style="width:110px">Tipo</th><th style="width:150px">Desembolso de</th>' +
        '<th style="width:150px">até</th><th style="width:32px"></th></tr></thead>' +
      '<tbody id="fin-it-body">' + linhas + '</tbody></table>' +
      '<div class="d-flex justify-content-between align-items-end flex-wrap gap-2">' +
        '<button type="button" id="fin-it-add" class="btn btn-outline-secondary btn-sm">+ Adicionar linha</button>' +
        '<div class="d-flex align-items-end gap-2">' +
          '<div><label class="small text-muted">Orçado/venda (R$)</label>' +
            '<input id="fin-it-orc" type="number" step="0.01" class="form-control form-control-sm" value="' + Number(et.previsto || 0) + '"></div>' +
          '<button type="button" id="fin-it-save" class="btn btn-primary btn-sm">Salvar etapa</button>' +
        '</div>' +
      '</div></div>';

    function recalcPrev() {
      var total = 0;
      box.querySelectorAll('.fin-it-valor').forEach(function (i) { total += Number(i.value || 0); });
      el('fin-it-prev').textContent = BRL(total);
    }
    function bindRow(tr) {
      tr.querySelector('.fin-it-del').addEventListener('click', function () { tr.remove(); recalcPrev(); });
      tr.querySelector('.fin-it-valor').addEventListener('input', recalcPrev);
    }
    box.querySelectorAll('#fin-it-body tr').forEach(bindRow);
    el('fin-it-add').addEventListener('click', function () {
      var tmp = document.createElement('tbody');
      tmp.innerHTML = etapaLinhaHTML(null);
      var tr = tmp.firstChild;
      el('fin-it-body').appendChild(tr);
      bindRow(tr);
    });
    el('fin-it-save').addEventListener('click', function () {
      var itens = [];
      box.querySelectorAll('#fin-it-body tr').forEach(function (tr) {
        itens.push({
          descricao: tr.querySelector('.fin-it-desc').value,
          valor: tr.querySelector('.fin-it-valor').value || '0',
          fonte: tr.querySelector('.fin-it-fonte').value,
          data_inicio: tr.querySelector('.fin-it-ini').value || '',
          data_fim: tr.querySelector('.fin-it-fim').value || ''
        });
      });
      fetch('/obras/' + OBRA_ID + '/financeiro/etapa/' + et.osc_id + '/itens', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify({ itens: itens, valor_orcado: el('fin-it-orc').value || '0' })
      })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (p) { render(p); box.innerHTML = '<div class="text-success small">Salvo e recalculado.</div>'; })
        .catch(function () { box.innerHTML = '<div class="text-danger small">Falha ao salvar.</div>'; });
    });
  }
  function buildCharts(p) {
    var blue = '#2E6BB0', green = '#198754', amber = '#C8870E', red = '#C0392B', grid = { color: '#E5EBF2' };
    var st = p.etapas.slice().sort(function (a, b) { return b.previsto - a.previsto; });
    C.etapas = new Chart(el('finEtapas'), {
      type: 'bar',
      data: { labels: st.map(function (s) { return s.nome; }), datasets: [
        { label: 'Veks', data: st.map(function (s) { return s.veks; }), backgroundColor: blue, stack: 's' },
        { label: 'Fat direto', data: st.map(function (s) { return s.fat; }), backgroundColor: green, stack: 's' }] },
      options: { indexAxis: 'y', maintainAspectRatio: false,
        onClick: function (e, els) { if (els.length) showEtapa(st[els[0].index]); },
        plugins: { tooltip: { callbacks: { label: function (c) { return c.dataset.label + ': ' + BRL(c.parsed.x); } } } },
        scales: { x: { stacked: true, grid: grid, ticks: { callback: BRLk } }, y: { stacked: true, grid: { display: false } } } }
    });
    var cs = p.curva_s;
    C.curva = new Chart(el('finCurva'), {
      type: 'line',
      data: { labels: cs.meses, datasets: [
        { label: 'Recebido líquido', data: cs.recebido_liquido, borderColor: green, borderDash: [6, 4], tension: .35, pointRadius: 3 },
        { label: 'Gasto Veks (prev.)', data: cs.gasto_veks, borderColor: blue, tension: .35, pointRadius: 3 },
        { label: 'Lucro', data: cs.lucro, borderColor: amber, backgroundColor: 'rgba(200,135,14,.12)', fill: true, tension: .35, pointRadius: 3 },
        { label: 'Custo realizado', data: cs.realizado, borderColor: red, tension: .35, pointRadius: 3 }] },
      options: { maintainAspectRatio: false, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: function (c) { return c.dataset.label + ': ' + BRL(c.parsed.y); } } } }, scales: { y: { grid: grid, ticks: { callback: BRLk } }, x: { grid: { display: false } } } }
    });
    C.split = new Chart(el('finSplit'), {
      type: 'doughnut',
      data: { labels: ['Desembolso Veks', 'Fat direto'], datasets: [{ data: [p.doughnut.veks, p.doughnut.fat], backgroundColor: [blue, green] }] },
      options: { maintainAspectRatio: false, cutout: '62%', plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: function (c) { return c.label + ': ' + BRL(c.parsed); } } } } }
    });
    var caixaLin = (p.caixa && p.caixa.linhas) || [];
    C.caixa = new Chart(el('finCaixa'), {
      type: 'bar',
      data: { labels: caixaLin.map(function (l) { return l.mes; }), datasets: [{ label: 'Caixa final', data: caixaLin.map(function (l) { return l.caixa_final; }), backgroundColor: caixaLin.map(function (l) { return l.caixa_final < 0 ? red : (l.caixa_final < 110000 ? amber : blue); }) }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: function (c) { return BRL(c.parsed.y); } } } }, scales: { y: { grid: grid, ticks: { callback: BRLk } }, x: { grid: { display: false } } } }
    });
  }
  function setCfgMsg(texto, cls) {
    var m = el('fin-fat-competencia-msg');
    if (!m) return;
    if (!texto) { m.style.display = 'none'; m.textContent = ''; return; }
    m.style.display = 'block';
    m.textContent = texto;
    m.className = 'small mt-1 ' + (cls || 'text-muted');
  }
  function saveConfig(valor) {
    var sel = el('fin-fat-competencia');
    if (sel) sel.disabled = true;
    setCfgMsg('Salvando…', 'text-muted');
    fetch(CONFIG_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken(),
                 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify({ fat_competencia: valor })
    })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (p) { render(p); setCfgMsg('Salvo.', 'text-success'); })
      .catch(function () { setCfgMsg('Não foi possível salvar.', 'text-danger'); })
      .finally(function () { if (sel) sel.disabled = false; });
  }
  function renderConfig(cfg) {
    var sel = el('fin-fat-competencia');
    if (!sel) return;
    sel.value = (cfg && cfg.fat_competencia === 'mesma') ? 'mesma' : 'seguinte';
    if (!cfgBound) {
      cfgBound = true;
      sel.addEventListener('change', function () { saveConfig(sel.value); });
    }
  }
  function render(p) {
    renderKPIs(p.kpis); renderMedicoes(p.medicoes); renderAlerta(p.divergencia);
    renderAlertaCaixa(p.caixa);
    renderConfig(p.config);
    Object.keys(C).forEach(function (key) { if (C[key]) C[key].destroy(); });
    C = {};
    buildCharts(p);
  }
  function load() {
    if (loaded) return; loaded = true;
    fetch(ENDPOINT, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (p) { el('fin-loading').style.display = 'none'; el('fin-painel').style.display = 'block'; render(p); })
      .catch(function () { el('fin-loading').style.display = 'none'; el('fin-erro').style.display = 'block'; });
  }
  document.addEventListener('DOMContentLoaded', function () {
    var pane = el('tab-financeiro');
    if (!pane) return;
    ENDPOINT = pane.getAttribute('data-endpoint');
    CONFIG_ENDPOINT = pane.getAttribute('data-config-endpoint');
    OBRA_ID = pane.getAttribute('data-obra-id');
    var btn = document.querySelector('[data-bs-target="#tab-financeiro"]');
    if (btn) btn.addEventListener('shown.bs.tab', load);
    if (pane.classList.contains('active')) load();
  });
})();
