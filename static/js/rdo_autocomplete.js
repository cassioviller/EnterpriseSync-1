// Sistema de Autocomplete para RDO - Funcionários
// SIGE v8.0 - Sistema limpo e funcional

let funcionariosSelecionados = [];
let timeoutBusca = null;

function inicializarAutocomplete() {
    console.log('🚀 Inicializando sistema de autocomplete...');
    
    const input = document.getElementById('buscarFuncionario');
    const sugestoes = document.getElementById('sugestoesFuncionarios');
    
    if (!input || !sugestoes) {
        console.warn('⚠️ Elementos de autocomplete não encontrados');
        return;
    }
    
    input.addEventListener('input', function() {
        clearTimeout(timeoutBusca);
        const termo = this.value.trim();
        
        if (termo.length < 2) {
            sugestoes.style.display = 'none';
            return;
        }
        
        timeoutBusca = setTimeout(() => {
            buscarFuncionarios(termo);
        }, 300);
    });
    
    // Fechar sugestões ao clicar fora
    document.addEventListener('click', function(e) {
        if (!input.contains(e.target) && !sugestoes.contains(e.target)) {
            sugestoes.style.display = 'none';
        }
    });
    
    console.log('✅ Autocomplete inicializado com sucesso');
}

function buscarFuncionarios(termo) {
    console.log(`🔍 Buscando funcionários: "${termo}"`);
    
    const sugestoes = document.getElementById('sugestoesFuncionarios');
    
    sugestoes.innerHTML = '<div class="p-2 text-center"><i class="fas fa-spinner fa-spin"></i> Buscando...</div>';
    sugestoes.style.display = 'block';
    
    fetch(`/api/funcionarios/buscar?q=${encodeURIComponent(termo)}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log(`📋 Funcionários encontrados:`, data);
            
            if (data.success && data.funcionarios.length > 0) {
                mostrarSugestoes(data.funcionarios);
            } else {
                sugestoes.innerHTML = '<div class="p-2 text-muted text-center">Nenhum funcionário encontrado</div>';
            }
        })
        .catch(error => {
            console.error('❌ Erro na busca:', error);
            sugestoes.innerHTML = '<div class="p-2 text-danger text-center">Erro na busca de funcionários</div>';
        });
}

function mostrarSugestoes(funcionarios) {
    const sugestoes = document.getElementById('sugestoesFuncionarios');
    let html = '';
    
    funcionarios.forEach(func => {
        // Verificar se já foi selecionado
        const jaSelecionado = funcionariosSelecionados.find(f => f.id === func.id);
        if (!jaSelecionado) {
            html += `
                <div class="suggestion-item" onclick="selecionarFuncionario(${func.id}, '${func.nome.replace(/'/g, "\\'")}', ${func.valor_hora})">
                    <div class="d-flex justify-content-between">
                        <div>
                            <strong>${func.nome}</strong>
                            <br><small class="text-muted">${func.cargo}</small>
                        </div>
                        <div class="text-end">
                            <small>R$ ${func.valor_hora.toFixed(2)}/h</small>
                        </div>
                    </div>
                </div>
            `;
        }
    });
    
    if (html) {
        sugestoes.innerHTML = html;
    } else {
        sugestoes.innerHTML = '<div class="p-2 text-muted text-center">Todos os funcionários já foram selecionados</div>';
    }
}

function selecionarFuncionario(id, nome, valorHora) {
    console.log(`👤 Selecionando funcionário: ${nome} (ID: ${id})`);
    
    // Adicionar à lista de selecionados
    funcionariosSelecionados.push({
        id: id,
        nome: nome,
        valor_hora: valorHora,
        horas: 8.0,
        funcao: 'Executante'
    });
    
    // Limpar campo de busca
    document.getElementById('buscarFuncionario').value = '';
    document.getElementById('sugestoesFuncionarios').style.display = 'none';
    
    // Atualizar interface
    renderizarFuncionariosSelecionados();
    
    console.log(`✅ Funcionário ${nome} adicionado à equipe`);
}

function renderizarFuncionariosSelecionados() {
    const container = document.getElementById('funcionarios-selecionados');
    const nenhumFuncionario = document.getElementById('nenhumFuncionario');
    
    if (funcionariosSelecionados.length === 0) {
        if (nenhumFuncionario) nenhumFuncionario.style.display = 'block';
        return;
    }
    
    if (nenhumFuncionario) nenhumFuncionario.style.display = 'none';
    
    let html = '<div class="funcionarios-selected-list">';
    
    funcionariosSelecionados.forEach((func, index) => {
        html += `
            <div class="funcionario-selected-card mb-3">
                <div class="card">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <div>
                                <h6 class="card-title mb-1">${func.nome}</h6>
                                <small class="text-muted">R$ ${func.valor_hora.toFixed(2)}/hora</small>
                            </div>
                            <button type="button" class="btn btn-outline-danger btn-sm" onclick="removerFuncionario(${index})">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-6">
                                <label class="form-label">Função</label>
                                <select class="form-select form-select-sm" onchange="atualizarFuncao(${index}, this.value)">
                                    <option value="Executante" ${func.funcao === 'Executante' ? 'selected' : ''}>Executante</option>
                                    <option value="Operador" ${func.funcao === 'Operador' ? 'selected' : ''}>Operador</option>
                                    <option value="Auxiliar" ${func.funcao === 'Auxiliar' ? 'selected' : ''}>Auxiliar</option>
                                    <option value="Encarregado" ${func.funcao === 'Encarregado' ? 'selected' : ''}>Encarregado</option>
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">Horas Trabalhadas</label>
                                <input type="number" class="form-control form-control-sm" 
                                       min="0" max="24" step="0.5" 
                                       value="${func.horas}"
                                       onchange="atualizarHoras(${index}, this.value)"
                                       name="funcionario_${func.id}_horas">
                            </div>
                        </div>
                        
                        <!-- Campos hidden para envio do form -->
                        <input type="hidden" name="funcionarios_selecionados" value="${func.id}">
                        <input type="hidden" name="funcionario_${func.id}_funcao" value="${func.funcao}">
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

function removerFuncionario(index) {
    const funcionario = funcionariosSelecionados[index];
    console.log(`🗑️ Removendo funcionário: ${funcionario.nome}`);
    
    funcionariosSelecionados.splice(index, 1);
    renderizarFuncionariosSelecionados();
}

function atualizarFuncao(index, novaFuncao) {
    funcionariosSelecionados[index].funcao = novaFuncao;
    // Atualizar campo hidden
    const hiddenInput = document.querySelector(`input[name="funcionario_${funcionariosSelecionados[index].id}_funcao"]`);
    if (hiddenInput) {
        hiddenInput.value = novaFuncao;
    }
}

function atualizarHoras(index, novasHoras) {
    funcionariosSelecionados[index].horas = parseFloat(novasHoras) || 0;
}

// Inicializar quando a página carregar
document.addEventListener('DOMContentLoaded', function() {
    console.log('📋 DOM carregado - inicializando autocomplete...');
    inicializarAutocomplete();
});