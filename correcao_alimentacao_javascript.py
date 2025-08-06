#!/usr/bin/env python3
"""
CORREÇÃO COMPLETA DO JAVASCRIPT DE ALIMENTAÇÃO
Remove código duplicado e malformado, restaura funcionalidade dos botões
"""

def corrigir_javascript_alimentacao():
    """Corrige o JavaScript malformado no template de alimentação"""
    
    javascript_correto = '''
<script>
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Sistema de alimentação carregado');
    
    // =================== FILTROS ===================
    function aplicarFiltros() {
        const obra = document.getElementById('filtro_obra').value;
        const funcionario = document.getElementById('filtro_funcionario').value;
        const tipo = document.getElementById('filtro_tipo').value;
        const dataInicio = document.getElementById('filtro_data_inicio').value;
        const dataFim = document.getElementById('filtro_data_fim').value;
        
        const url = new URL(window.location.href);
        
        if (obra) url.searchParams.set('obra', obra);
        else url.searchParams.delete('obra');
        
        if (funcionario) url.searchParams.set('funcionario', funcionario);
        else url.searchParams.delete('funcionario');
        
        if (tipo) url.searchParams.set('tipo', tipo);
        else url.searchParams.delete('tipo');
        
        if (dataInicio) url.searchParams.set('data_inicio', dataInicio);
        else url.searchParams.delete('data_inicio');
        
        if (dataFim) url.searchParams.set('data_fim', dataFim);
        else url.searchParams.delete('data_fim');
        
        window.location.href = url.toString();
    }
    
    function limparFiltros() {
        window.location.href = '/alimentacao';
    }
    
    // Tornar funções globais
    window.aplicarFiltros = aplicarFiltros;
    window.limparFiltros = limparFiltros;
    
    // =================== VALIDAÇÃO ===================
    function validarDataSelecionada() {
        const dataInput = document.getElementById('data');
        const dataInicioInput = document.getElementById('data_inicio');
        const dataFimInput = document.getElementById('data_fim');
        
        const temDataUnica = dataInput && dataInput.value;
        const temPeriodo = dataInicioInput && dataInicioInput.value && dataFimInput && dataFimInput.value;
        
        if (!temDataUnica && !temPeriodo) {
            alert('⚠️ Selecione uma data ou período antes de salvar!');
            return false;
        }
        
        return true;
    }
    
    // Aplicar validação no submit do formulário
    const formAlimentacao = document.getElementById('alimentacaoForm');
    if (formAlimentacao) {
        formAlimentacao.addEventListener('submit', function(e) {
            if (!validarDataSelecionada()) {
                e.preventDefault();
                return false;
            }
        });
    }
    
    // =================== EDIÇÃO INLINE ===================
    let registroEditandoId = null;
    let dadosOriginais = {};
    
    function editarRegistroInline(id) {
        if (registroEditandoId && registroEditandoId !== id) {
            cancelarEdicao(registroEditandoId);
        }
        
        registroEditandoId = id;
        const row = document.getElementById(`registro-${id}`);
        
        if (!row) {
            console.error('Linha não encontrada:', id);
            return;
        }
        
        // Salvar dados originais
        dadosOriginais[id] = {
            data: row.querySelector('.data-registro').textContent,
            tipo: row.querySelector('.tipo-refeicao .badge').textContent,
            valor: row.querySelector('.valor-registro').textContent,
            observacoes: row.querySelector('.observacoes-registro').textContent
        };
        
        converterParaEdicao(row, id);
    }
    
    function converterParaEdicao(row, id) {
        // Data
        const dataCell = row.querySelector('.data-registro');
        const dataAtual = dataCell.textContent.split('/').reverse().join('-');
        dataCell.innerHTML = `<input type="date" class="form-control form-control-sm" value="${dataAtual}" id="edit-data-${id}">`;
        
        // Tipo
        const tipoCell = row.querySelector('.tipo-refeicao');
        const tipoAtual = tipoCell.querySelector('.badge').textContent.toLowerCase();
        let tipoValue = 'lanche';
        if (tipoAtual.includes('café')) tipoValue = 'cafe';
        else if (tipoAtual.includes('almoço')) tipoValue = 'almoco';
        else if (tipoAtual.includes('jantar')) tipoValue = 'jantar';
        
        tipoCell.innerHTML = `
            <select class="form-select form-select-sm" id="edit-tipo-${id}">
                <option value="cafe" ${tipoValue === 'cafe' ? 'selected' : ''}>Café da Manhã</option>
                <option value="almoco" ${tipoValue === 'almoco' ? 'selected' : ''}>Almoço</option>
                <option value="lanche" ${tipoValue === 'lanche' ? 'selected' : ''}>Lanche</option>
                <option value="jantar" ${tipoValue === 'jantar' ? 'selected' : ''}>Jantar</option>
            </select>
        `;
        
        // Valor
        const valorCell = row.querySelector('.valor-registro');
        const valorAtual = valorCell.textContent.replace('R$ ', '').replace(',', '.');
        valorCell.innerHTML = `<input type="number" class="form-control form-control-sm" step="0.01" value="${valorAtual}" id="edit-valor-${id}">`;
        
        // Observações
        const obsCell = row.querySelector('.observacoes-registro');
        const obsAtual = obsCell.textContent === '-' ? '' : obsCell.textContent;
        obsCell.innerHTML = `<input type="text" class="form-control form-control-sm" value="${obsAtual}" id="edit-obs-${id}" placeholder="Observações">`;
        
        // Botões de ação
        const actionsCell = row.querySelector('td:last-child');
        actionsCell.innerHTML = `
            <div class="btn-group btn-group-sm">
                <button class="btn btn-success" onclick="salvarEdicao(${id})">
                    <i class="fas fa-check"></i>
                </button>
                <button class="btn btn-secondary" onclick="cancelarEdicao(${id})">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
    }
    
    function salvarEdicao(id) {
        const dados = {
            data: document.getElementById(`edit-data-${id}`).value,
            tipo: document.getElementById(`edit-tipo-${id}`).value,
            valor: document.getElementById(`edit-valor-${id}`).value,
            observacoes: document.getElementById(`edit-obs-${id}`).value
        };
        
        fetch(`/alimentacao/editar/${id}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(dados)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const row = document.getElementById(`registro-${id}`);
                atualizarLinhaTabela(row, dados, id);
                registroEditandoId = null;
                delete dadosOriginais[id];
                showToast('Registro atualizado com sucesso!', 'success');
            } else {
                showToast('Erro ao atualizar registro: ' + data.message, 'error');
            }
        })
        .catch(error => {
            console.error('Erro:', error);
            showToast('Erro de conexão', 'error');
        });
    }
    
    function cancelarEdicao(id) {
        if (!dadosOriginais[id]) return;
        
        const row = document.getElementById(`registro-${id}`);
        const original = dadosOriginais[id];
        
        // Restaurar dados originais
        row.querySelector('.data-registro').textContent = original.data;
        row.querySelector('.tipo-refeicao').innerHTML = original.tipo.includes('badge') ? original.tipo : obterBadgeTipo(original.tipo);
        row.querySelector('.valor-registro').textContent = original.valor;
        row.querySelector('.observacoes-registro').textContent = original.observacoes;
        
        // Restaurar botões
        row.querySelector('td:last-child').innerHTML = `
            <div class="btn-group btn-group-sm">
                <button class="btn btn-outline-primary btn-editar" onclick="editarRegistroInline(${id})">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn btn-outline-danger" onclick="excluirRegistro(${id})">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        
        registroEditandoId = null;
        delete dadosOriginais[id];
    }
    
    function atualizarLinhaTabela(row, dados, id) {
        // Data
        const dataFormatada = dados.data.split('-').reverse().join('/');
        row.querySelector('.data-registro').textContent = dataFormatada;
        
        // Tipo
        row.querySelector('.tipo-refeicao').innerHTML = obterBadgeTipo(dados.tipo);
        
        // Valor
        const valorFormatado = 'R$ ' + parseFloat(dados.valor || 0).toFixed(2).replace('.', ',');
        row.querySelector('.valor-registro').textContent = valorFormatado;
        
        // Observações
        row.querySelector('.observacoes-registro').textContent = dados.observacoes || '-';
        
        // Restaurar botões
        row.querySelector('td:last-child').innerHTML = `
            <div class="btn-group btn-group-sm">
                <button class="btn btn-outline-primary btn-editar" onclick="editarRegistroInline(${id})">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn btn-outline-danger" onclick="excluirRegistro(${id})">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
    }
    
    // =================== EXCLUSÃO ===================
    function excluirRegistro(id) {
        if (confirm('Tem certeza que deseja excluir este registro?')) {
            const btn = event.target.closest('button');
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            btn.disabled = true;
            
            fetch(`/alimentacao/${id}/excluir`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({})
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    const row = document.getElementById(`registro-${id}`);
                    if (row) {
                        row.remove();
                    }
                    showToast('Registro excluído com sucesso!', 'success');
                    setTimeout(() => location.reload(), 1000);
                } else {
                    showToast('Erro ao excluir: ' + (data.message || 'Erro desconhecido'), 'error');
                    btn.innerHTML = originalHtml;
                    btn.disabled = false;
                }
            })
            .catch(error => {
                console.error('Erro na exclusão:', error);
                showToast('Erro de conexão: ' + error.message, 'error');
                btn.innerHTML = originalHtml;
                btn.disabled = false;
            });
        }
    }
    
    // =================== UTILITÁRIOS ===================
    function obterBadgeTipo(tipo) {
        if (typeof tipo === 'string') {
            if (tipo.includes('Café') || tipo === 'cafe') return '<span class="badge bg-warning">Café da Manhã</span>';
            if (tipo.includes('Almoço') || tipo === 'almoco') return '<span class="badge bg-success">Almoço</span>';
            if (tipo.includes('Jantar') || tipo === 'jantar') return '<span class="badge bg-primary">Jantar</span>';
            return '<span class="badge bg-secondary">Lanche</span>';
        }
        
        const badges = {
            'cafe': '<span class="badge bg-warning">Café da Manhã</span>',
            'almoco': '<span class="badge bg-success">Almoço</span>',
            'jantar': '<span class="badge bg-primary">Jantar</span>',
            'lanche': '<span class="badge bg-secondary">Lanche</span>'
        };
        return badges[tipo] || '<span class="badge bg-secondary">Lanche</span>';
    }
    
    function showToast(message, type = 'success') {
        const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
        const alertHtml = `
            <div class="alert ${alertClass} alert-dismissible fade show position-fixed" 
                 style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
                <strong>${type === 'success' ? '✓' : '✗'}</strong> ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', alertHtml);
        
        setTimeout(() => {
            const alerts = document.querySelectorAll('.alert');
            alerts.forEach(alert => {
                if (alert.textContent.includes(message)) {
                    alert.remove();
                }
            });
        }, 5000);
    }
    
    // Tornar funções globais
    window.editarRegistroInline = editarRegistroInline;
    window.salvarEdicao = salvarEdicao;
    window.cancelarEdicao = cancelarEdicao;
    window.excluirRegistro = excluirRegistro;
    window.obterBadgeTipo = obterBadgeTipo;
    window.showToast = showToast;
    
    console.log('✅ JavaScript de alimentação carregado com sucesso');
});
</script>
'''
    
    return javascript_correto

if __name__ == "__main__":
    print("🔧 Gerando JavaScript corrigido para alimentação...")
    js_correto = corrigir_javascript_alimentacao()
    print("✅ JavaScript corrigido gerado!")
    print("📁 Salvando em arquivo temporário...")
    
    with open('/tmp/alimentacao_js_correto.html', 'w', encoding='utf-8') as f:
        f.write(js_correto)
    
    print("✅ JavaScript salvo em /tmp/alimentacao_js_correto.html")
    print("🔧 Aplique este JavaScript ao final do template alimentacao.html")