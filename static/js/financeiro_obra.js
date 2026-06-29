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
        mapa[chave] = { descricao: desc, fonte: fonte, periodos: [], previsto: 0 };
        ordem.push(chave);
      }
      mapa[chave].periodos.push(it);
      mapa[chave].previsto += Number(it.valor || 0);
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
      '<td class="text-center"><button type="button" class="btn btn-sm btn-link fin-grp-open p-0" ' +
        'data-grupo="' + idx + '" title="Abrir períodos">&#9656;</button></td>' +
    '</tr>';
  }
  function previsaoTabelaHTML(box) {
    var linhas = box._grupos.map(grupoLinhaHTML).join('') ||
      '<tr><td colspan="5" class="text-muted small">Sem custos lançados.</td></tr>';
    return '<table class="table table-sm align-middle mb-2"><thead><tr>' +
        '<th>Custo</th><th style="width:90px">Fonte</th>' +
        '<th class="text-center" style="width:80px">Períodos</th>' +
        '<th class="text-end" style="width:130px">Previsto</th>' +
        '<th style="width:36px"></th></tr></thead>' +
      '<tbody id="fin-grp-body">' + linhas + '</tbody></table>' +
      '<div class="d-flex justify-content-end">' +
        '<button type="button" id="fin-it-save" class="btn btn-primary btn-sm">Salvar etapa</button>' +
      '</div>';
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
    box.innerHTML =
      '<div class="border rounded p-3 bg-light">' +
      '<div class="d-flex justify-content-between mb-2"><strong>' + et.nome +
        (et.tipo === 'periodo' ? ' <span class="badge bg-secondary" title="Custo de período — sem avanço físico, fora do RDO/cronograma">período</span>' : '') +
        '</strong>' +
        '<span>Realizado: <span id="fin-et-real">' + BRL(et.realizado) + '</span>' +
        ' / Previsto: <span id="fin-it-prev">' + BRL(et.previsto) + '</span></span></div>' +
      '<ul class="nav nav-tabs mb-2"><li class="nav-item">' +
        '<button class="nav-link active" id="fin-et-tab-prev" type="button">Previsão (por grupo)</button></li>' +
        '<li class="nav-item"><button class="nav-link" id="fin-et-tab-real" type="button">Realizado — lançamentos</button></li></ul>' +
      '<div id="fin-et-pane-prev">' + previsaoTabelaHTML(box) + '</div>' +
      '<div id="fin-et-pane-real" style="display:none"></div>' +
      '</div>';

    box.querySelectorAll('.fin-grp-open').forEach(function (btn) {
      btn.addEventListener('click', function () {
        abrirModuloPeriodos(box, parseInt(btn.getAttribute('data-grupo'), 10));
      });
    });
    el('fin-it-save').addEventListener('click', function () { salvarEtapa(box); });

    function showPane(which) {
      el('fin-et-pane-prev').style.display = which === 'prev' ? '' : 'none';
      el('fin-et-pane-real').style.display = which === 'real' ? '' : 'none';
      el('fin-et-tab-prev').classList.toggle('active', which === 'prev');
      el('fin-et-tab-real').classList.toggle('active', which === 'real');
      if (which === 'real') carregarRealizado(box, et);
    }
    el('fin-et-tab-prev').addEventListener('click', function () { showPane('prev'); });
    el('fin-et-tab-real').addEventListener('click', function () { showPane('real'); });
  }

  function carregarRealizado(box, et) {
    var pane = el('fin-et-pane-real');
    pane.innerHTML = '<div class="text-muted small">Carregando…</div>';
    fetch('/obras/' + OBRA_ID + '/financeiro/etapa/' + et.osc_id + '/lancamentos',
          { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) { renderRealizado(box, et, d.lancamentos || []); })
      .catch(function () { pane.innerHTML = '<div class="text-danger small">Falha ao carregar lançamentos.</div>'; });
  }
  function renderRealizado(box, et, lancs) {
    var porMes = {}, ordem = [];
    lancs.forEach(function (l) {
      var chave = l.data ? String(l.data).slice(0, 7) : 'sem-data';
      if (!porMes[chave]) { porMes[chave] = []; ordem.push(chave); }
      porMes[chave].push(l);
    });
    ordem.sort();
    var total = 0, html = '';
    ordem.forEach(function (chave) {
      var linhas = porMes[chave], sub = 0;
      var rotulo = chave === 'sem-data' ? 'sem data' : rotuloMes(chave + '-01');
      html += '<div class="fw-bold mt-2">' + rotulo + '</div><table class="table table-sm mb-1"><tbody>';
      linhas.forEach(function (l) {
        sub += Number(l.valor || 0); total += Number(l.valor || 0);
        var acoes = l.editavel
          ? '<button type="button" class="btn btn-sm btn-link p-0 fin-lc-edit" data-id="' + l.id + '">✎</button> ' +
            '<button type="button" class="btn btn-sm btn-link text-danger p-0 fin-lc-del" data-id="' + l.id + '">×</button>'
          : '<span class="badge bg-light text-dark border">' + (l.origem_label || 'Sistema') + '</span>';
        html += '<tr><td style="width:90px">' + (l.data ? String(l.data).slice(8, 10) + '/' + String(l.data).slice(5, 7) : '—') + '</td>' +
          '<td>' + String(l.descricao || '').replace(/</g, '&lt;') + '</td>' +
          '<td class="text-end" style="width:120px">' + BRL(l.valor) + '</td>' +
          '<td class="text-end" style="width:90px">' + acoes + '</td></tr>';
      });
      html += '</tbody></table><div class="small text-muted">Subtotal ' + rotulo + ': ' + BRL(sub) + '</div>';
    });
    if (!ordem.length) html = '<div class="text-muted small">Sem lançamentos. Use "+ Novo lançamento".</div>';
    el('fin-et-pane-real').innerHTML =
      html +
      '<div class="d-flex justify-content-between align-items-center mt-2">' +
        '<button type="button" id="fin-lc-novo" class="btn btn-outline-primary btn-sm">+ Novo lançamento</button>' +
        '<span class="small">Total realizado: <strong>' + BRL(total) + '</strong></span></div>' +
      '<div id="fin-lc-form"></div>';
    el('fin-lc-novo').addEventListener('click', function () { lancamentoForm(box, et, null); });
    el('fin-et-pane-real').querySelectorAll('.fin-lc-edit').forEach(function (b) {
      b.addEventListener('click', function () {
        var l = lancs.filter(function (x) { return String(x.id) === b.getAttribute('data-id'); })[0];
        lancamentoForm(box, et, l);
      });
    });
    el('fin-et-pane-real').querySelectorAll('.fin-lc-del').forEach(function (b) {
      b.addEventListener('click', function () { excluirLancamento(box, et, b.getAttribute('data-id')); });
    });
  }
  function lancamentoForm(box, et, l) {
    var hoje = (l && l.data) ? String(l.data).slice(0, 10) : '';
    el('fin-lc-form').innerHTML =
      '<div class="border rounded p-2 mt-2"><div class="row g-2">' +
        '<div class="col-3"><input type="date" id="fin-lc-data" class="form-control form-control-sm" value="' + hoje + '"></div>' +
        '<div class="col-5"><input type="text" id="fin-lc-desc" class="form-control form-control-sm" placeholder="Descrição" value="' + (l ? String(l.descricao || '').replace(/"/g, '&quot;') : '') + '"></div>' +
        '<div class="col-2"><input type="number" step="0.01" id="fin-lc-valor" class="form-control form-control-sm text-end" placeholder="Valor" value="' + (l ? Number(l.valor || 0) : '') + '"></div>' +
        '<div class="col-2"><button type="button" id="fin-lc-salvar" class="btn btn-primary btn-sm w-100">Salvar</button></div>' +
      '</div></div>';
    el('fin-lc-salvar').addEventListener('click', function () {
      var payload = {
        data: el('fin-lc-data').value || '',
        descricao: el('fin-lc-desc').value || '',
        valor: el('fin-lc-valor').value || '0'
      };
      var url = '/obras/' + OBRA_ID + '/financeiro/etapa/' + et.osc_id + '/lancamentos' + (l ? '/' + l.id : '');
      fetch(url, {
        method: l ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify(payload)
      })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) { if (d.painel) { render(d.painel); atualizarCabecalhoEtapa(et, d.painel); } carregarRealizado(box, et); })
        .catch(function () { el('fin-lc-form').innerHTML = '<div class="text-danger small">Falha ao salvar.</div>'; });
    });
  }
  function atualizarCabecalhoEtapa(et, painel) {
    if (!painel || !painel.etapas) return;
    var fresh = painel.etapas.filter(function (e) { return e.osc_id === et.osc_id; })[0];
    if (!fresh) return;
    et.realizado = fresh.realizado; et.previsto = fresh.previsto;
    var r = el('fin-et-real'), pv = el('fin-it-prev');
    if (r) r.textContent = BRL(et.realizado);
    if (pv) pv.textContent = BRL(et.previsto);
  }
  function excluirLancamento(box, et, id) {
    fetch('/obras/' + OBRA_ID + '/financeiro/etapa/' + et.osc_id + '/lancamentos/' + id, {
      method: 'DELETE', headers: { 'X-CSRFToken': csrfToken() }
    })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) { if (d.painel) { render(d.painel); atualizarCabecalhoEtapa(et, d.painel); } carregarRealizado(box, et); })
      .catch(function () {});
  }

  function recalcGrupo(box, idx) {
    var g = box._grupos[idx];
    g.previsto = g.periodos.reduce(function (s, p) { return s + Number(p.valor || 0); }, 0);
    var tr = box.querySelector('#fin-grp-body tr[data-grupo="' + idx + '"]');
    if (tr) {
      tr.querySelector('[data-grp-previsto]').textContent = BRL(g.previsto);
      tr.querySelector('td:nth-child(3)').textContent = g.periodos.length;
    }
    var prev = box._grupos.reduce(function (s, gg) { return s + gg.previsto; }, 0);
    el('fin-it-prev').textContent = BRL(prev);
  }

  function coletarItensDaEtapa(box) {
    var itens = [];
    box._grupos.forEach(function (g) {
      g.periodos.forEach(function (p) {
        itens.push({
          descricao: g.descricao,
          fonte: g.fonte,
          valor: String(p.valor || 0),
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
  function abrirModuloPeriodos(box, idx) {
    var g = box._grupos[idx];
    el('fin-pm-titulo').innerHTML = (g.descricao || 'Períodos') +
      ' <span class="badge bg-light text-dark border">' + fonteLabel(g.fonte) + '</span>';

    function renderAbas() {
      el('fin-pm-prev-body').innerHTML = g.periodos.map(periodoRowPrevHTML).join('');
      totais();
      el('fin-pm-prev-body').querySelectorAll('tr').forEach(bindPrevRow);
    }
    function totais() {
      var tp = g.periodos.reduce(function (s, p) { return s + Number(p.valor || 0); }, 0);
      el('fin-pm-prev-total').textContent = BRL(tp);
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
    el('fin-pm-add').onclick = function () {
      g.periodos.push({ valor: 0, data_inicio: null, data_fim: null, fonte: g.fonte });
      renderAbas();
    };
    el('fin-pm-aplicar').onclick = function () { recalcGrupo(box, idx); };

    renderAbas();
    var modalEl = el('fin-periodos-modal');
    // O modal mora dentro do pane #tab-financeiro, cujo ancestral cria um stacking
    // context — o .modal-backdrop (anexado ao <body>) ficaria ACIMA do modal e
    // interceptaria os cliques. Reparentar para o <body> escapa esse contexto.
    if (modalEl.parentNode !== document.body) document.body.appendChild(modalEl);
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
