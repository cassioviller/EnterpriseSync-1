/**
 * Sistema de auto-complete e herança de dados RDO
 * Carrega serviços e atividades do último RDO da obra
 */

console.log('RDO Autocomplete System Loaded');

// Função principal para carregar dados do último RDO
function carregarDadosUltimoRDO(obraId) {
    if (!obraId) return;
    
    console.log(`🔄 Carregando dados do último RDO para obra ${obraId}`);
    
    fetch(`/api/ultimo-rdo-dados/${obraId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.ultimo_rdo) {
                console.log(`✅ Último RDO encontrado: ${data.ultimo_rdo.numero_rdo}`);
                preencherDadosRDO(data.ultimo_rdo);
            } else {
                console.log('ℹ️ Nenhum RDO anterior encontrado para esta obra');
            }
        })
        .catch(error => {
            console.error('❌ Erro ao carregar último RDO:', error);
        });
}

// Função para preencher dados do RDO
function preencherDadosRDO(ultimoRDO) {
    // Preencher serviços e subatividades
    if (ultimoRDO.servicos && ultimoRDO.servicos.length > 0) {
        ultimoRDO.servicos.forEach(servico => {
            adicionarServicoAoRDO(servico);
        });
    }
    
    // Preencher funcionários
    if (ultimoRDO.funcionarios && ultimoRDO.funcionarios.length > 0) {
        ultimoRDO.funcionarios.forEach(funcionario => {
            adicionarFuncionarioAoRDO(funcionario);
        });
    }
    
    // Preencher observações gerais (opcional)
    const observacoesField = document.querySelector('#observacoes_gerais');
    if (observacoesField && !observacoesField.value) {
        observacoesField.value = 'Baseado no RDO anterior: ' + ultimoRDO.numero_rdo;
    }
}

// Função para adicionar serviço ao RDO
function adicionarServicoAoRDO(servico) {
    console.log(`📝 Adicionando serviço: ${servico.nome}`);
    
    // Lógica específica para adicionar serviço depende da implementação do RDO
    const servicosContainer = document.querySelector('#servicos-container');
    if (servicosContainer) {
        // Implementar lógica de adição de serviço baseada na estrutura do form
    }
}

// Função para adicionar funcionário ao RDO
function adicionarFuncionarioAoRDO(funcionario) {
    console.log(`👤 Adicionando funcionário: ${funcionario.nome}`);
    
    // Lógica específica para adicionar funcionário
    const funcionariosContainer = document.querySelector('#funcionarios-container');
    if (funcionariosContainer) {
        // Implementar lógica de adição de funcionário
    }
}

// Event listener para mudança de obra
document.addEventListener('DOMContentLoaded', function() {
    const obraSelect = document.querySelector('#obra_id');
    if (obraSelect) {
        obraSelect.addEventListener('change', function() {
            const obraId = this.value;
            if (obraId) {
                carregarDadosUltimoRDO(obraId);
            }
        });
    }
    
    console.log('✅ RDO Autocomplete System Initialized');
});

// Exportar funções globalmente
window.carregarDadosUltimoRDO = carregarDadosUltimoRDO;
window.preencherDadosRDO = preencherDadosRDO;