/* Painel Financeiro da Obra — carrega sob demanda e renderiza com Chart.js. */
(function () {
  var BRL = function (v) { return 'R$ ' + Math.round(v || 0).toLocaleString('pt-BR'); };
  var BRLk = function (v) { return 'R$ ' + Math.round((v || 0) / 1000).toLocaleString('pt-BR') + 'k'; };
  var MESES_ABREV = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
  function rotuloMes(iso) {
    if (!iso) return '—';
    var s = String(iso).slice(0, 10), m = parseInt(s.slice(5, 7), 10);
    if (!m || m < 1 || m > 12) return '—';
    return MESES_ABREV[m - 1] + '/' + s.slice(2, 4);
  }
  function agruparPeriodos(itens) {
    var mapa = {}, ordem = [];
    (itens || []).forEach(function (it) {
      var fonte = it.fonte === 'fat_direto' ? 'fat_direto' : 'veks';
      var desc = (it.descricao || '').trim();
      var chave = desc + '||' + fonte;
      if (!mapa[chave]) {
        mapa[chave] = { descricao: desc, fonte: fonte, periodos: [], previsto: 0, realizado: 0 };
        ordem.push(chave);
      }
      mapa[chave].periodos.push(it);
      mapa[chave].previsto += Number(it.valor || 0);
      mapa[chave].realizado += Number(it.valor_realizado || 0);
    });
    return ordem.map(function (k) { return mapa[k]; }).sort(function (a, b) {
      return a.descricao.localeCompare(b.descricao) || a.fonte.localeCompare(b.fonte);
    });
  }
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
  function fonteLabel(f) { return f === 'fat_direto' ? 'Fat direto' : 'Veks'; }
  function grupoLinhaHTML(g, idx) {
    return '<tr data-grupo="' + idx + '">' +
      '<td>' + String(g.descricao || '').replace(/</g, '&lt;') + '</td>' +
      '<td>' + fonteLabel(g.fonte) + '</td>' +
      '<td class="text-center">' + g.periodos.length + '</td>' +
      '<td class="text-end" data-grp-previsto>' + BRL(g.previsto) + '</td>' +
      '<td class="text-end" data-grp-realizado>' + BRL(g.realizado) + '</td>' +
      '<td class="text-center"><button type="button" class="btn btn-sm btn-link fin-grp-open p-0" ' +
        'data-grupo="' + idx + '" title="Abrir períodos">&#9656;</button></td>' +
    '</tr>';
  }
  function showEtapa(et) {
    var box = el('fin-etapa-det');
    if (et.osc_id == null) {
      box.innerHTML = '<div class="border rounded p-3 bg-light"><strong>' + et.nome + '</strong>' +
        '<div class="small text-muted mt-1">Etapa sem custo único vinculável — edição indisponível.</div></div>';
      return;
    }
    box._etapa = et;
    box._grupos = agruparPeriodos(et.itens);
    var linhas = box._grupos.map(grupoLinhaHTML).join('') ||
      '<tr><td colspan="6" class="text-muted small">Sem custos lançados.</td></tr>';
    box.innerHTML =
      '<div class="border rounded p-3 bg-light">' +
      '<div class="d-flex justify-content-between mb-2"><strong>' + et.nome +
        (et.tipo === 'periodo' ? ' <span class="badge bg-secondary" title="Custo de período — sem avanço físico, fora do RDO/cronograma">período</span>' : '') +
        '</strong>' +
        '<span>Realizado: <span id="fin-et-real">' + BRL(et.realizado) + '</span>' +
        ' / Previsto: <span id="fin-it-prev">' + BRL(et.previsto) + '</span></span></div>' +
      '<table class="table table-sm align-middle mb-2"><thead><tr>' +
        '<th>Custo</th><th style="width:90px">Fonte</th>' +
        '<th class="text-center" style="width:80px">Períodos</th>' +
        '<th class="text-end" style="width:130px">Previsto</th>' +
        '<th class="text-end" style="width:130px">Realizado</th>' +
        '<th style="width:36px"></th></tr></thead>' +
      '<tbody id="fin-grp-body">' + linhas + '</tbody></table>' +
      '<div class="d-flex justify-content-end">' +
        '<button type="button" id="fin-it-save" class="btn btn-primary btn-sm">Salvar etapa</button>' +
      '</div></div>';

    box.querySelectorAll('.fin-grp-open').forEach(function (btn) {
      btn.addEventListener('click', function () {
        abrirModuloPeriodos(box, parseInt(btn.getAttribute('data-grupo'), 10));
      });
    });
    el('fin-it-save').addEventListener('click', function () { salvarEtapa(box); });
  }

  function recalcGrupo(box, idx) {
    var g = box._grupos[idx];
    g.previsto = g.periodos.reduce(function (s, p) { return s + Number(p.valor || 0); }, 0);
    g.realizado = g.periodos.reduce(function (s, p) { return s + Number(p.valor_realizado || 0); }, 0);
    var tr = box.querySelector('#fin-grp-body tr[data-grupo="' + idx + '"]');
    if (tr) {
      tr.querySelector('[data-grp-previsto]').textContent = BRL(g.previsto);
      tr.querySelector('[data-grp-realizado]').textContent = BRL(g.realizado);
      tr.querySelector('td:nth-child(3)').textContent = g.periodos.length;
    }
    var prev = box._grupos.reduce(function (s, gg) { return s + gg.previsto; }, 0);
    var real = box._grupos.reduce(function (s, gg) { return s + gg.realizado; }, 0);
    el('fin-it-prev').textContent = BRL(prev);
    el('fin-et-real').textContent = BRL(real);
  }

  function coletarItensDaEtapa(box) {
    var itens = [];
    box._grupos.forEach(function (g) {
      g.periodos.forEach(function (p) {
        itens.push({
          descricao: g.descricao,
          fonte: g.fonte,
          valor: String(p.valor || 0),
          valor_realizado: String(p.valor_realizado || 0),
          data_inicio: p.data_inicio ? String(p.data_inicio).slice(0, 10) : '',
          data_fim: p.data_fim ? String(p.data_fim).slice(0, 10) : ''
        });
      });
    });
    return itens;
  }

  function salvarEtapa(box) {
    var et = box._etapa;
    var prevTotal = box._grupos.reduce(function (s, g) { return s + g.previsto; }, 0);
    fetch('/obras/' + OBRA_ID + '/financeiro/etapa/' + et.osc_id + '/itens', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify({ itens: coletarItensDaEtapa(box), valor_orcado: String(prevTotal) })
    })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (p) { render(p); box.innerHTML = '<div class="text-success small">Salvo e recalculado.</div>'; })
      .catch(function () { box.innerHTML = '<div class="text-danger small">Falha ao salvar.</div>'; });
  }

  function ultimoDiaMes(ano, mes) { return new Date(ano, mes, 0).getDate(); }
  function periodoRowPrevHTML(p, i) {
    return '<tr data-p="' + i + '">' +
      '<td>' + rotuloMes(p.data_inicio) + '</td>' +
      '<td><input type="date" class="form-control form-control-sm fin-pm-ini" value="' +
        (p.data_inicio ? String(p.data_inicio).slice(0, 10) : '') + '"></td>' +
      '<td><input type="date" class="form-control form-control-sm fin-pm-fim" value="' +
        (p.data_fim ? String(p.data_fim).slice(0, 10) : '') + '"></td>' +
      '<td><input type="number" step="0.01" class="form-control form-control-sm text-end fin-pm-valor" value="' +
        Number(p.valor || 0) + '"></td>' +
      '<td class="text-center"><button type="button" class="btn btn-sm btn-link text-danger fin-pm-del p-0">&times;</button></td>' +
    '</tr>';
  }
  function periodoRowRealHTML(p, i) {
    return '<tr data-p="' + i + '">' +
      '<td>' + rotuloMes(p.data_inicio) + '</td>' +
      '<td><input type="number" step="0.01" class="form-control form-control-sm text-end fin-pm-realval" value="' +
        Number(p.valor_realizado || 0) + '"></td>' +
    '</tr>';
  }
  function abrirModuloPeriodos(box, idx) {
    var g = box._grupos[idx];
    el('fin-pm-titulo').innerHTML = (g.descricao || 'Períodos') +
      ' <span class="badge bg-light text-dark border">' + fonteLabel(g.fonte) + '</span>';

    function renderAbas() {
      el('fin-pm-prev-body').innerHTML = g.periodos.map(periodoRowPrevHTML).join('');
      el('fin-pm-real-body').innerHTML = g.periodos.map(periodoRowRealHTML).join('');
      totais();
      el('fin-pm-prev-body').querySelectorAll('tr').forEach(bindPrevRow);
      el('fin-pm-real-body').querySelectorAll('tr').forEach(bindRealRow);
    }
    function totais() {
      var tp = g.periodos.reduce(function (s, p) { return s + Number(p.valor || 0); }, 0);
      var tr = g.periodos.reduce(function (s, p) { return s + Number(p.valor_realizado || 0); }, 0);
      el('fin-pm-prev-total').textContent = BRL(tp);
      el('fin-pm-real-total').textContent = BRL(tr);
    }
    function bindPrevRow(trEl) {
      var i = parseInt(trEl.getAttribute('data-p'), 10);
      trEl.querySelector('.fin-pm-valor').addEventListener('input', function () {
        g.periodos[i].valor = Number(this.value || 0); totais();
      });
      trEl.querySelector('.fin-pm-ini').addEventListener('change', function () {
        g.periodos[i].data_inicio = this.value || null;
        trEl.querySelector('td:first-child').textContent = rotuloMes(this.value);
      });
      trEl.querySelector('.fin-pm-fim').addEventListener('change', function () {
        g.periodos[i].data_fim = this.value || null;
      });
      trEl.querySelector('.fin-pm-del').addEventListener('click', function () {
        g.periodos.splice(i, 1); renderAbas();
      });
    }
    function bindRealRow(trEl) {
      var i = parseInt(trEl.getAttribute('data-p'), 10);
      trEl.querySelector('.fin-pm-realval').addEventListener('input', function () {
        g.periodos[i].valor_realizado = Number(this.value || 0); totais();
      });
    }
    el('fin-pm-add').onclick = function () {
      g.periodos.push({ valor: 0, valor_realizado: 0, data_inicio: null, data_fim: null, fonte: g.fonte });
      renderAbas();
    };
    el('fin-pm-aplicar').onclick = function () { recalcGrupo(box, idx); };

    renderAbas();
    var modalEl = el('fin-periodos-modal');
    var modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
    modal.show();
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
