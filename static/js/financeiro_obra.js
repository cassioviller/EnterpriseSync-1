/* Painel Financeiro da Obra — carrega sob demanda e renderiza com Chart.js. */
(function () {
  var BRL = function (v) { return 'R$ ' + Math.round(v || 0).toLocaleString('pt-BR'); };
  var BRLk = function (v) { return 'R$ ' + Math.round((v || 0) / 1000).toLocaleString('pt-BR') + 'k'; };
  var C = {}, loaded = false, ENDPOINT = null, OBRA_ID = null;
  function el(id) { return document.getElementById(id); }

  function renderKPIs(k) {
    var cards = [
      ['Venda (contrato)', k.venda, ''], ['Custo total', k.custo_total, ''],
      ['Lucro projetado', k.lucro_projetado, 'text-success'],
      ['Desembolso Veks', k.desembolso_veks, ''],
      ['Faturamento direto', k.fat_direto, 'text-success'],
      ['Recebido até hoje', k.recebido_ate_hoje, ''],
      ['Verba disponível (caixa)', k.verba_disponivel, (k.verba_disponivel >= 0 ? 'text-success' : 'text-danger')],
      ['Custo realizado', k.custo_realizado, '']
    ];
    el('fin-kpis').innerHTML = cards.map(function (c) {
      return '<div class="col-6 col-md-3"><div class="card h-100"><div class="card-body p-2">' +
        '<div class="small text-muted">' + c[0] + '</div>' +
        '<div class="fw-bold ' + c[2] + '" style="font-variant-numeric:tabular-nums">' + BRL(c[1]) + '</div>' +
        '</div></div></div>';
    }).join('');
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
  function showEtapa(et) {
    var box = el('fin-etapa-det');
    box.innerHTML =
      '<div class="border rounded p-3 bg-light"><div class="d-flex justify-content-between mb-2">' +
      '<strong>' + et.nome + '</strong><span>Realizado: ' + BRL(et.realizado) + ' / Previsto: ' + BRL(et.previsto) + '</span></div>' +
      '<div class="row g-2 align-items-end">' +
      '<div class="col-auto"><label class="small text-muted">Veks (R$)</label>' +
      '<input id="ed-veks" type="number" class="form-control form-control-sm" value="' + Math.round(et.veks) + '"></div>' +
      '<div class="col-auto"><label class="small text-muted">Fat direto (R$)</label>' +
      '<input id="ed-fat" type="number" class="form-control form-control-sm" value="' + Math.round(et.fat) + '"></div>' +
      '<div class="col-auto"><label class="small text-muted">Orçado (R$)</label>' +
      '<input id="ed-orc" type="number" class="form-control form-control-sm" value="' + Math.round(et.previsto) + '"></div>' +
      '<div class="col-auto"><button id="ed-save" class="btn btn-primary btn-sm">Salvar</button></div>' +
      '</div></div>';
    if (et.osc_id == null) {
      box.querySelector('#ed-save').disabled = true;
      box.insertAdjacentHTML('beforeend', '<div class="small text-muted mt-1">Etapa sem custo único vinculável — edição indisponível.</div>');
      return;
    }
    el('ed-save').addEventListener('click', function () {
      var fd = new FormData();
      fd.append('veks', el('ed-veks').value || '0');
      fd.append('fat', el('ed-fat').value || '0');
      fd.append('valor_orcado', el('ed-orc').value || '0');
      fetch('/obras/' + OBRA_ID + '/financeiro/etapa/' + et.osc_id, { method: 'POST', body: fd })
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
      data: { labels: caixaLin.map(function (l) { return l.mes; }), datasets: [{ label: 'Caixa final', data: caixaLin.map(function (l) { return l.caixa_final; }), backgroundColor: caixaLin.map(function (l) { return l.caixa_final < 110000 ? amber : blue; }) }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: function (c) { return BRL(c.parsed.y); } } } }, scales: { y: { grid: grid, ticks: { callback: BRLk } }, x: { grid: { display: false } } } }
    });
  }
  function render(p) {
    renderKPIs(p.kpis); renderMedicoes(p.medicoes); renderAlerta(p.divergencia);
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
    OBRA_ID = pane.getAttribute('data-obra-id');
    var btn = document.querySelector('[data-bs-target="#tab-financeiro"]');
    if (btn) btn.addEventListener('shown.bs.tab', load);
    if (pane.classList.contains('active')) load();
  });
})();
