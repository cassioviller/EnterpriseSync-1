/**
 * M08 — Seção "Importação de Cronograma" na aba Cronograma da obra.
 *
 * Views são finas: este JS só busca JSON dos endpoints tenant-scoped
 * (M03/M05/M08), renderiza listas e dispara ações. Nenhuma fórmula aqui.
 * Todos os textos vindos de arquivo/banco passam por _esc() (dados do
 * .mpp são não confiáveis).
 */
(function () {
    'use strict';

    const secao = document.getElementById('secaoCronogramaMpp');
    if (!secao) return;

    const OBRA_ID = Number(secao.dataset.obraId);
    const BASE = `/obras/${OBRA_ID}/cronograma`;
    const TAMANHO_MAX = 20 * 1024 * 1024;
    const ESTADOS_TERMINAIS = ['aguardando_revisao', 'aplicado', 'falhou', 'cancelado'];

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
            headers: { 'X-CSRFToken': _csrf() },
        }, opts || {}));
        let corpo = null;
        try { corpo = await res.json(); } catch (e) { /* páginas de erro */ }
        return { ok: res.ok, status: res.status, corpo: corpo || {} };
    }

    function _fmtData(iso) {
        if (!iso) return '—';
        const d = new Date(iso);
        return isNaN(d) ? '—' : d.toLocaleString('pt-BR', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    }

    function _dur(ms) {
        if (ms == null) return null;
        return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
    }

    // Métricas §4.3 do M10 — a visão de suporte: quanto demorou, quanto o
    // matching resolveu sozinho e quanto exigiu decisão humana.
    function _metricas(m) {
        if (!m) return '—';
        const linhas = [];
        if (m.n_tarefas != null) linhas.push(`${m.n_tarefas} tarefas`);
        const parse = _dur(m.tempo_parse_ms);
        if (parse) linhas.push(`parse ${parse}`);
        const total = _dur(m.tempo_total_ms);
        if (total) linhas.push(`total ${total}`);
        if (m.n_auto != null) {
            linhas.push(`${m.n_auto} auto / ${m.n_conflitos || 0} conflito(s)`);
        }
        if (m.n_manuais) linhas.push(`${m.n_manuais} decisão(ões) manual(is)`);
        if (m.n_avisos) linhas.push(`${m.n_avisos} aviso(s)`);
        if (m.rollbacks) linhas.push(`${m.rollbacks} rollback(s)`);
        const niveis = m.matches_por_nivel || {};
        // Nunca interpolado em atributo: _esc não escapa aspas.
        const detalheNiveis = Object.keys(niveis).length
            ? `<br><span class="text-muted" style="font-size:.75rem">${
                _esc(Object.entries(niveis).map(([k, v]) => `${k}=${v}`)
                    .join(', '))}</span>`
            : '';
        if (!linhas.length && !detalheNiveis) return '—';
        return `${_esc(linhas.join(' · '))}${detalheNiveis}`;
    }

    const BADGES = {
        recebido: 'bg-secondary', parseado: 'bg-secondary',
        normalizado: 'bg-info text-dark',
        aguardando_revisao: 'bg-warning text-dark',
        aplicado: 'bg-success', falhou: 'bg-danger', cancelado: 'bg-dark',
    };

    function _badge(status) {
        return `<span class="badge ${BADGES[status] || 'bg-secondary'}"
                      style="font-size:.7rem">${_esc(status)}</span>`;
    }

    // ── Versões ──────────────────────────────────────────────────────────
    async function carregarVersoes() {
        const r = await _json(`${BASE}/versoes`);
        const boxStatus = document.getElementById('cronMppStatusVersao');
        const boxLista = document.getElementById('cronMppListaVersoes');
        if (!r.ok) {
            boxStatus.innerHTML = '<span class="text-danger small">Erro ao carregar versões.</span>';
            return;
        }
        const versoes = r.corpo.versoes || [];
        const ativa = versoes.find(v => v.status === 'ativa');

        boxStatus.innerHTML = ativa ? `
            <div class="d-flex flex-wrap align-items-center gap-3">
                <div>
                    <div class="fw-bold" style="font-size:1.05rem">
                        <i class="fas fa-check-circle text-success me-1"></i>
                        Versão ativa: nº ${ativa.numero}
                    </div>
                    <div class="small text-muted">
                        Aplicada em ${_fmtData(ativa.aplicada_em)}
                        ${ativa.aplicada_por ? ` por ${_esc(ativa.aplicada_por)}` : ''}
                    </div>
                </div>
                <div class="small text-muted">
                    ${ativa.arquivo_nome
                        ? `<i class="fas fa-file me-1"></i>${_esc(ativa.arquivo_nome)}
                           <span class="text-muted">(sha ${_esc((ativa.arquivo_sha256 || '').slice(0, 12))}…)</span>`
                        : '<i class="fas fa-pen me-1"></i>Origem: edição manual / histórico'}
                </div>
            </div>`
            : '<span class="text-muted small">Nenhuma versão registrada ainda — a primeira importação aplicada cria a versão nº 1.</span>';

        boxLista.innerHTML = versoes.length ? `
            <div class="table-responsive">
            <table class="table table-sm align-middle mb-0" style="font-size:.85rem">
                <thead><tr>
                    <th>Nº</th><th>Status</th><th>Aplicada em</th><th>Por</th>
                    <th>Origem</th><th>Observação</th><th class="text-end">Ações</th>
                </tr></thead>
                <tbody>
                ${versoes.map(v => `
                    <tr>
                        <td class="fw-bold">v${v.numero}</td>
                        <td>${_badge(v.status)}</td>
                        <td>${_fmtData(v.aplicada_em)}</td>
                        <td>${_esc(v.aplicada_por || '—')}</td>
                        <td>${_esc(v.arquivo_nome || 'manual')}</td>
                        <td class="text-muted">${_esc(v.observacao || '')}</td>
                        <td class="text-end">
                            ${v.restauravel ? `
                            <button class="btn btn-sm btn-outline-warning"
                                    data-restaurar="${v.id}" data-numero="${v.numero}">
                                <i class="fas fa-rotate-left me-1"></i>Restaurar
                            </button>` : ''}
                        </td>
                    </tr>`).join('')}
                </tbody>
            </table></div>`
            : '<span class="text-muted small">Sem versões.</span>';

        boxLista.querySelectorAll('[data-restaurar]').forEach(btn => {
            btn.addEventListener('click', () => restaurarVersao(
                Number(btn.dataset.restaurar), Number(btn.dataset.numero)));
        });
    }

    async function restaurarVersao(versaoId, numero) {
        // Confirmação dupla: digitar o nº da versão (spec §11).
        const digitado = prompt(
            `Restaurar o cronograma desta obra para a versão v${numero}?\n` +
            `Isso cria uma NOVA versão (nada é apagado) e recalcula as curvas.\n\n` +
            `Para confirmar, digite o número da versão (${numero}):`);
        if (digitado === null) return;
        if (String(digitado).trim() !== String(numero)) {
            alert('Número não confere — restauração cancelada.');
            return;
        }
        const r = await _json(`${BASE}/versoes/${versaoId}/restaurar`,
                              { method: 'POST' });
        if (r.ok) {
            alert(`Versão v${numero} restaurada como v${r.corpo.versao_numero}.`);
            carregarTudo();
        } else {
            alert(r.corpo.erro || 'Não foi possível restaurar a versão.');
        }
    }

    // ── Importações ──────────────────────────────────────────────────────
    async function carregarImportacoes() {
        const r = await _json(`${BASE}/importacoes`);
        const box = document.getElementById('cronMppListaImportacoes');
        if (!r.ok) {
            box.innerHTML = '<span class="text-danger small">Erro ao carregar importações.</span>';
            return;
        }
        const imps = r.corpo.importacoes || [];
        if (!imps.length) {
            box.innerHTML = '<span class="text-muted small">Nenhuma importação ainda.</span>';
            return;
        }
        box.innerHTML = `
            <div class="table-responsive">
            <table class="table table-sm align-middle mb-0" style="font-size:.85rem">
                <thead><tr>
                    <th>Arquivo</th><th>Status</th><th>Enviada em</th>
                    <th>Detalhe</th><th>Métricas</th><th class="text-end">Ações</th>
                </tr></thead>
                <tbody>
                ${imps.map(i => `
                    <tr data-imp-linha="${i.id}">
                        <td><i class="fas fa-file me-1 text-muted"></i>${_esc(i.arquivo_nome)}</td>
                        <td data-imp-status="${i.id}">${_badge(i.status)}</td>
                        <td>${_fmtData(i.criado_em)}</td>
                        <td class="text-muted" style="max-width:260px">
                            ${i.status === 'falhou' ? `<span class="text-danger">${_esc(i.erro || 'Falha no processamento')}</span>`
                              : i.status === 'aguardando_revisao' && i.pendencias
                                ? `<span class="text-warning fw-semibold">${i.pendencias} pendência(s) de revisão</span>`
                              : i.status === 'aplicado' ? `Aplicada em ${_fmtData(i.aplicado_em)}` : ''}
                        </td>
                        <td class="text-muted small" data-imp-metricas="${i.id}">
                            ${_metricas(i.metricas)}
                        </td>
                        <td class="text-end text-nowrap">
                            ${['normalizado', 'aguardando_revisao'].includes(i.status) ? `
                                <a class="btn btn-sm btn-primary"
                                   href="${BASE}/importacoes/${i.id}/previa">
                                    <i class="fas fa-eye me-1"></i>Ver prévia
                                </a>
                                <button class="btn btn-sm btn-outline-danger"
                                        data-cancelar="${i.id}">Cancelar</button>` : ''}
                            ${i.status === 'aplicado' ? `
                                <a class="btn btn-sm btn-outline-success"
                                   href="${BASE}/importacoes/${i.id}/resultado">
                                    <i class="fas fa-clipboard-check me-1"></i>Resultado
                                </a>` : ''}
                        </td>
                    </tr>`).join('')}
                </tbody>
            </table></div>`;

        box.querySelectorAll('[data-cancelar]').forEach(btn => {
            btn.addEventListener('click', () => cancelarImportacao(
                Number(btn.dataset.cancelar)));
        });
        // Polling dos não-terminais (upload .mpp pode demorar).
        imps.filter(i => !ESTADOS_TERMINAIS.includes(i.status) &&
                         i.status !== 'normalizado')
            .forEach(i => _pollStatus(i.id));
    }

    async function cancelarImportacao(impId) {
        if (!confirm('Cancelar esta importação? O arquivo poderá ser reenviado depois.')) return;
        const r = await _json(`${BASE}/importacoes/${impId}/cancelar`,
                              { method: 'POST' });
        if (!r.ok) alert(r.corpo.erro || 'Não foi possível cancelar.');
        carregarImportacoes();
    }

    function _pollStatus(impId) {
        const t = setInterval(async () => {
            const r = await _json(`${BASE}/importacoes/${impId}/status`);
            if (!r.ok || ESTADOS_TERMINAIS.includes(r.corpo.status) ||
                r.corpo.status === 'normalizado') {
                clearInterval(t);
                carregarImportacoes();
            }
        }, 2000);
    }

    // ── Upload ───────────────────────────────────────────────────────────
    function _feedback(msg, tipo) {
        const box = document.getElementById('uploadCronogramaFeedback');
        box.className = `small mt-2 text-${tipo || 'muted'}`;
        box.innerHTML = msg;
    }

    async function enviarArquivo() {
        const input = document.getElementById('inputArquivoCronograma');
        const arquivo = input.files && input.files[0];
        if (!arquivo) { _feedback('Escolha um arquivo .xml ou .mpp.', 'danger'); return; }
        if (arquivo.size > TAMANHO_MAX) {
            _feedback('Arquivo excede o limite de 20 MB.', 'danger'); return;
        }
        if (!/\.(xml|mpp)$/i.test(arquivo.name)) {
            _feedback('Extensão não suportada — envie .xml (MSPDI) ou .mpp.', 'danger');
            return;
        }
        _feedback('<i class="fas fa-spinner fa-spin me-1"></i>Enviando e processando…');
        const fd = new FormData();
        fd.append('arquivo', arquivo);
        const res = await fetch(`${BASE}/importacoes`, {
            method: 'POST', body: fd,
            headers: { 'X-CSRFToken': _csrf() },
        });
        let corpo = {};
        try { corpo = await res.json(); } catch (e) { /* noop */ }
        if (res.ok) {
            _feedback(`<i class="fas fa-check text-success me-1"></i>Arquivo processado
                       (importação #${corpo.importacao_id}). Abra a prévia para revisar.`, 'success');
            input.value = '';
            carregarImportacoes();
        } else {
            console.error('upload cronograma falhou', res.status, corpo);
            _feedback(_esc(corpo.erro || 'Falha no envio do arquivo.'), 'danger');
            if (corpo.importacao_id || corpo.importacao_existente_id) carregarImportacoes();
        }
    }

    function carregarTudo() {
        carregarVersoes();
        carregarImportacoes();
    }

    document.getElementById('btnAbrirModalImportarCronograma')
        ?.addEventListener('click', () => {
            _feedback('', 'muted');
            const el = document.getElementById('modalImportarCronograma');
            if (el && window.bootstrap) {
                // O modal nasce dentro do tab-pane (que tem transform de
                // animação) — position:fixed quebraria e o backdrop
                // engoliria os cliques. Movê-lo para o body resolve.
                if (el.parentElement !== document.body) {
                    document.body.appendChild(el);
                }
                window.bootstrap.Modal.getOrCreateInstance(el).show();
            }
        });
    document.getElementById('btnEnviarCronograma')
        ?.addEventListener('click', enviarArquivo);

    carregarTudo();
})();
