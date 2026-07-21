/**
 * M08 — Prévia de importação de cronograma: filtros, busca, decisão de
 * mapeamentos (PATCH), aplicação e cancelamento. Dados vêm embutidos em
 * #dadosPrevia; TODO texto de tarefa passa por _esc (arquivo não confiável).
 */
(function () {
    'use strict';

    const el = document.getElementById('dadosPrevia');
    if (!el) return;
    const DADOS = JSON.parse(el.textContent);
    const BASE = `/obras/${DADOS.obra_id}/cronograma/importacoes/${DADOS.importacao_id}`;

    let filtroAtivo = 'tudo';
    let busca = '';
    let linhaEmDecisao = null;

    function _esc(s) {
        const d = document.createElement('div');
        d.textContent = s == null ? '' : String(s);
        return d.innerHTML;
    }

    function _csrf() {
        const m = document.querySelector('meta[name="csrf-token"]');
        return m ? m.getAttribute('content') : '';
    }

    async function _json(url, opts) {
        const res = await fetch(url, Object.assign({
            headers: { 'Content-Type': 'application/json',
                       'X-CSRFToken': _csrf() },
        }, opts || {}));
        let corpo = {};
        try { corpo = await res.json(); } catch (e) { /* noop */ }
        return { ok: res.ok, status: res.status, corpo };
    }

    const ROTULOS = {
        exata: ['Exata', 'success'], renomeada: ['Renomeada', 'primary'],
        nova: ['Nova', 'info'], removida: ['Removida', 'secondary'],
        ambigua: ['Ambígua', 'warning'], revisao_manual: ['Revisão manual', 'danger'],
        dividida: ['Dividida?', 'warning'], fundida: ['Fundida?', 'warning'],
        movida_hierarquia: ['Movida', 'dark'], datas_alteradas: ['Datas', 'primary'],
        duracao_alterada: ['Duração', 'primary'],
        predecessoras_alteradas: ['Predecessoras', 'primary'],
        quantidade_alterada: ['Qtd.', 'primary'], unidade_alterada: ['Unid.', 'primary'],
    };

    function _badges(tipos) {
        return (tipos || []).map(t => {
            const [rot, cor] = ROTULOS[t] || [t, 'secondary'];
            return `<span class="badge bg-${cor} me-1" style="font-size:.68rem">${_esc(rot)}</span>`;
        }).join('');
    }

    function _alteracoes(l) {
        const d = l.detalhes || {};
        const partes = [];
        if (d.nome_de !== undefined && d.nome_para !== undefined) {
            partes.push(`nome: <s>${_esc(d.nome_de)}</s> → ${_esc(d.nome_para)}`);
        }
        if (d.datas_de) partes.push(`datas: ${_esc((d.datas_de || []).join(' – '))} → ${_esc((d.datas_para || []).join(' – '))}`);
        if (d.duracao_de !== undefined) partes.push(`duração: ${_esc(d.duracao_de)} → ${_esc(d.duracao_para)}d`);
        if (d.predecessoras_de) partes.push('predecessoras alteradas');
        if (d.quantidade_de !== undefined) partes.push(`qtd: ${_esc(d.quantidade_de)} → ${_esc(d.quantidade_para)}`);
        if (d.unidade_de !== undefined) partes.push(`unid: ${_esc(d.unidade_de)} → ${_esc(d.unidade_para)}`);
        return partes.join('<br>') || '<span class="text-muted">—</span>';
    }

    function _pendente(l) { return l.decisao_requerida && !l.decisao; }

    function _casaFiltro(l) {
        if (filtroAtivo === 'pendentes') return _pendente(l);
        if (filtroAtivo === 'novas') return (l.tipo || []).includes('nova');
        if (filtroAtivo === 'removidas') {
            return (l.tipo || []).some(t => ['removida', 'dividida', 'fundida',
                                             'revisao_manual'].includes(t));
        }
        if (filtroAtivo === 'alteradas') {
            return (l.tipo || []).some(t => t.endsWith('_alteradas') ||
                t.endsWith('_alterada') || t === 'renomeada' ||
                t === 'movida_hierarquia');
        }
        return true;
    }

    function _casaBusca(l) {
        if (!busca) return true;
        const alvo = `${l.tarefa_atual_nome || ''} ${l.tarefa_nova_nome || ''}`
            .toLowerCase();
        return alvo.includes(busca);
    }

    function render() {
        const corpo = document.getElementById('previaCorpo');
        const visiveis = DADOS.linhas.filter(l => _casaFiltro(l) && _casaBusca(l));
        corpo.innerHTML = visiveis.map(l => `
            <tr class="${_pendente(l) ? 'table-warning' : ''}">
                <td>${l.tarefa_atual_nome ? _esc(l.tarefa_atual_nome)
                     : '<span class="text-muted">—</span>'}</td>
                <td>${l.tarefa_nova_nome ? _esc(l.tarefa_nova_nome)
                     : '<span class="text-muted">—</span>'}</td>
                <td>${_badges(l.tipo)}</td>
                <td class="text-muted">${_esc(l.nivel_match || '')}</td>
                <td class="text-muted">${l.score != null ? l.score.toFixed(2) : '—'}</td>
                <td>${_alteracoes(l)}</td>
                <td class="text-end">
                    ${l.decisao ? `<span class="badge bg-success"
                        style="font-size:.68rem">${_esc(l.decisao.acao)}${
                        l.decisao.chave_nova ? ' → ' + _esc(l.decisao.chave_nova) : ''}</span>` : ''}
                    ${l.decisao_requerida ? `
                    <button class="btn btn-sm ${l.decisao ? 'btn-outline-secondary' : 'btn-warning'}"
                            data-decidir="${l.id}">
                        ${l.decisao ? 'Alterar' : 'Decidir'}
                    </button>` : ''}
                </td>
            </tr>`).join('') ||
            '<tr><td colspan="7" class="text-center text-muted p-3">Nenhuma linha para o filtro atual.</td></tr>';

        corpo.querySelectorAll('[data-decidir]').forEach(btn => {
            btn.addEventListener('click', () =>
                abrirDecisao(Number(btn.dataset.decidir)));
        });

        const pend = DADOS.linhas.filter(_pendente).length;
        document.getElementById('previaPendencias').textContent = pend;
        const btnAplicar = document.getElementById('btnAplicarVersao');
        btnAplicar.disabled = pend > 0;
        document.getElementById('previaMsgAplicar').textContent =
            pend > 0 ? `Resolva as ${pend} pendência(s) para liberar a aplicação.` : '';
    }

    // ── Decisão ─────────────────────────────────────────────────────────
    function abrirDecisao(mapeamentoId) {
        linhaEmDecisao = DADOS.linhas.find(l => l.id === mapeamentoId);
        if (!linhaEmDecisao) return;
        const l = linhaEmDecisao;
        document.getElementById('decisaoContexto').innerHTML = `
            ${l.tarefa_atual_nome ? `Tarefa atual: <b>${_esc(l.tarefa_atual_nome)}</b><br>` : ''}
            ${l.tarefa_nova_nome ? `Tarefa nova: <b>${_esc(l.tarefa_nova_nome)}</b><br>` : ''}
            ${_badges(l.tipo)}`;

        // Opções coerentes com o tipo da linha (o servidor valida sempre).
        const ehNova = l.tarefa_atual_id === null;
        document.getElementById('acaoCasar').parentElement.style.display =
            ehNova ? 'none' : '';
        document.getElementById('acaoArquivar').parentElement.style.display =
            ehNova ? 'none' : '';
        document.getElementById('acaoNova').parentElement.style.display =
            ehNova ? '' : 'none';

        const sel = document.getElementById('decisaoChave');
        const candidatos = (l.candidatos && l.candidatos.length)
            ? l.candidatos.map(c => ({ chave: c.chave_nova, nome: c.nome,
                                       score: c.score }))
            : DADOS.chaves_novas.map(c => ({ chave: c.chave, nome: c.nome }));
        sel.innerHTML = candidatos.map(c =>
            `<option value="${_esc(c.chave)}">${_esc(c.nome || c.chave)}${
                c.score != null ? ` (score ${c.score.toFixed(2)})` : ''}</option>`).join('');
        sel.classList.add('d-none');
        document.querySelectorAll('input[name="decisaoAcao"]').forEach(r => {
            r.checked = false;
            r.onchange = () => sel.classList.toggle(
                'd-none', document.getElementById('acaoCasar').checked !== true);
        });
        document.getElementById('decisaoErro').classList.add('d-none');
        window.bootstrap.Modal.getOrCreateInstance(
            document.getElementById('modalDecisao')).show();
    }

    async function salvarDecisao() {
        if (!linhaEmDecisao) return;
        const acaoEl = document.querySelector('input[name="decisaoAcao"]:checked');
        const erroBox = document.getElementById('decisaoErro');
        if (!acaoEl) {
            erroBox.textContent = 'Escolha uma ação.';
            erroBox.classList.remove('d-none');
            return;
        }
        const corpo = { acao: acaoEl.value };
        if (acaoEl.value === 'casar') {
            corpo.chave_nova = document.getElementById('decisaoChave').value;
        }
        const r = await _json(`${BASE}/mapeamentos/${linhaEmDecisao.id}`,
                              { method: 'PATCH', body: JSON.stringify(corpo) });
        if (!r.ok) {
            erroBox.textContent = r.corpo.erro || 'Não foi possível salvar.';
            erroBox.classList.remove('d-none');
            return;
        }
        Object.assign(linhaEmDecisao, {
            decisao: r.corpo.decisao,
            origem_decisao: r.corpo.origem_decisao,
        });
        window.bootstrap.Modal.getOrCreateInstance(
            document.getElementById('modalDecisao')).hide();
        render();
    }

    // ── Aplicar / cancelar ──────────────────────────────────────────────
    async function aplicar() {
        const r0 = DADOS.linhas;
        const novas = r0.filter(l => (l.tipo || []).includes('nova')).length;
        const removidas = r0.filter(l => (l.tipo || []).some(
            t => ['removida', 'dividida', 'fundida'].includes(t))).length;
        const alteradas = r0.filter(l => l.tarefa_atual_id && l.chave_nova).length;
        if (!confirm(
            `Aplicar a nova versão do cronograma?\n\n` +
            `${alteradas} tarefa(s) atualizada(s), ${novas} nova(s), ` +
            `${removidas} arquivada(s).\n` +
            `RDOs, medições e fotos são preservados.`)) return;
        const btn = document.getElementById('btnAplicarVersao');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Aplicando…';
        const r = await _json(`${BASE}/aplicar`, { method: 'POST' });
        if (r.ok) {
            window.location.href = `${BASE}/resultado`;
        } else {
            alert(r.corpo.erro || 'Não foi possível aplicar a versão.');
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-check me-1"></i> Aplicar nova versão';
        }
    }

    async function cancelar() {
        if (!confirm('Cancelar esta importação? O arquivo poderá ser reenviado depois.')) return;
        const r = await _json(`${BASE}/cancelar`, { method: 'POST' });
        if (r.ok) {
            window.location.href = document.referrer || '/obras';
        } else {
            alert(r.corpo.erro || 'Não foi possível cancelar.');
        }
    }

    // ── Bindings ────────────────────────────────────────────────────────
    document.querySelectorAll('#previaFiltros [data-filtro]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#previaFiltros .active')
                .forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filtroAtivo = btn.dataset.filtro;
            render();
        });
    });
    document.getElementById('previaBusca').addEventListener('input', e => {
        busca = e.target.value.trim().toLowerCase();
        render();
    });
    document.getElementById('btnSalvarDecisao')
        .addEventListener('click', salvarDecisao);
    document.getElementById('btnAplicarVersao')
        .addEventListener('click', aplicar);
    document.getElementById('btnCancelarImportacao')
        .addEventListener('click', cancelar);

    render();
})();
