#!/usr/bin/env python3
"""
INTERFACE ATUALIZADA - Tipos de Registro de Ponto
Implementa dropdown melhorado com indicação de custo
"""

# Definição dos tipos para interface (JavaScript/Jinja2)
RECORD_TYPES_INTERFACE = [
    # TRABALHO (COM CUSTO)
    {
        'value': 'trabalho_normal',
        'label': '👷 Trabalho Normal',
        'description': 'Segunda a sexta-feira - até 8h normal, acima 50% extra',
        'has_cost': True,
        'color': 'success',
        'category': 'trabalho'
    },
    {
        'value': 'sabado_trabalhado',
        'label': '📅 Sábado Trabalhado',
        'description': 'Trabalho em sábado - 50% adicional sobre todas as horas',
        'has_cost': True,
        'color': 'warning',
        'category': 'trabalho'
    },
    {
        'value': 'domingo_trabalhado',
        'label': '📅 Domingo Trabalhado',
        'description': 'Trabalho em domingo - 100% adicional sobre todas as horas',
        'has_cost': True,
        'color': 'danger',
        'category': 'trabalho'
    },
    {
        'value': 'feriado_trabalhado',
        'label': '🎉 Feriado Trabalhado',
        'description': 'Trabalho em feriado - 100% adicional',
        'has_cost': True,
        'color': 'danger',
        'category': 'trabalho'
    },
    {
        'value': 'meio_periodo',
        'label': '⏰ Meio Período',
        'description': 'Trabalho em meio período - custo proporcional às horas',
        'has_cost': True,
        'color': 'info',
        'category': 'trabalho'
    },
    
    # FOLGAS (SEM CUSTO)
    {
        'value': 'sabado_folga',
        'label': '🏠 Sábado Folga',
        'description': 'Sábado de descanso - sem custo para empresa',
        'has_cost': False,
        'color': 'secondary',
        'category': 'folga'
    },
    {
        'value': 'domingo_folga',
        'label': '🏠 Domingo Folga',
        'description': 'Domingo de descanso - sem custo para empresa',
        'has_cost': False,
        'color': 'secondary',
        'category': 'folga'
    },
    {
        'value': 'feriado_folga',
        'label': '🏠 Feriado Folga',
        'description': 'Feriado de descanso - sem custo para empresa',
        'has_cost': False,
        'color': 'secondary',
        'category': 'folga'
    },
    
    # AUSÊNCIAS
    {
        'value': 'falta_injustificada',
        'label': '❌ Falta Injustificada',
        'description': 'Falta sem justificativa - SEM remuneração',
        'has_cost': False,
        'color': 'danger',
        'category': 'ausencia'
    },
    {
        'value': 'falta_justificada',
        'label': '📋 Falta Justificada',
        'description': 'Falta com justificativa aprovada - COM remuneração',
        'has_cost': True,
        'color': 'warning',
        'category': 'ausencia'
    },
    {
        'value': 'atestado_medico',
        'label': '🏥 Atestado Médico',
        'description': 'Ausência por motivo médico - COM remuneração',
        'has_cost': True,
        'color': 'info',
        'category': 'ausencia'
    },
    
    # BENEFÍCIOS
    {
        'value': 'ferias',
        'label': '🏖️ Férias',
        'description': 'Período de férias - COM 1/3 adicional',
        'has_cost': True,
        'color': 'success',
        'category': 'beneficio'
    },
    {
        'value': 'licenca',
        'label': '📄 Licença',
        'description': 'Licença aprovada - COM remuneração',
        'has_cost': True,
        'color': 'primary',
        'category': 'beneficio'
    }
]

# Template Jinja2 para dropdown melhorado
DROPDOWN_TEMPLATE = """
<div class="form-group">
    <label for="tipo_registro" class="form-label">
        <i class="fas fa-clock"></i> Tipo de Lançamento
    </label>
    <select name="tipo_registro" id="tipo_registro" class="form-select" required>
        <option value="">Selecione o tipo de lançamento...</option>
        
        <!-- TRABALHO -->
        <optgroup label="💼 TRABALHO (com custo)">
            <option value="trabalho_normal" data-cost="true" data-color="success">
                👷 Trabalho Normal - até 8h normal, acima 50% extra
            </option>
            <option value="sabado_trabalhado" data-cost="true" data-color="warning">
                📅 Sábado Trabalhado - 50% adicional
            </option>
            <option value="domingo_trabalhado" data-cost="true" data-color="danger">
                📅 Domingo Trabalhado - 100% adicional
            </option>
            <option value="feriado_trabalhado" data-cost="true" data-color="danger">
                🎉 Feriado Trabalhado - 100% adicional
            </option>
            <option value="meio_periodo" data-cost="true" data-color="info">
                ⏰ Meio Período - proporcional
            </option>
        </optgroup>
        
        <!-- FOLGAS -->
        <optgroup label="🏠 FOLGAS (sem custo)">
            <option value="sabado_folga" data-cost="false" data-color="secondary">
                🏠 Sábado Folga - sem custo
            </option>
            <option value="domingo_folga" data-cost="false" data-color="secondary">
                🏠 Domingo Folga - sem custo
            </option>
            <option value="feriado_folga" data-cost="false" data-color="secondary">
                🏠 Feriado Folga - sem custo
            </option>
        </optgroup>
        
        <!-- AUSÊNCIAS -->
        <optgroup label="⚠️ AUSÊNCIAS">
            <option value="falta_injustificada" data-cost="false" data-color="danger">
                ❌ Falta Injustificada - SEM remuneração
            </option>
            <option value="falta_justificada" data-cost="true" data-color="warning">
                📋 Falta Justificada - COM remuneração
            </option>
            <option value="atestado_medico" data-cost="true" data-color="info">
                🏥 Atestado Médico - COM remuneração
            </option>
        </optgroup>
        
        <!-- BENEFÍCIOS -->
        <optgroup label="🎁 BENEFÍCIOS (com custo)">
            <option value="ferias" data-cost="true" data-color="success">
                🏖️ Férias - COM 1/3 adicional
            </option>
            <option value="licenca" data-cost="true" data-color="primary">
                📄 Licença - COM remuneração
            </option>
        </optgroup>
    </select>
    
    <!-- Indicador de custo -->
    <div id="cost-indicator" class="mt-2" style="display: none;">
        <div class="alert alert-info alert-sm">
            <i class="fas fa-info-circle"></i>
            <span id="cost-text"></span>
        </div>
    </div>
</div>

<script>
document.getElementById('tipo_registro').addEventListener('change', function() {
    const option = this.options[this.selectedIndex];
    const hasCost = option.getAttribute('data-cost') === 'true';
    const indicator = document.getElementById('cost-indicator');
    const costText = document.getElementById('cost-text');
    
    if (this.value) {
        indicator.style.display = 'block';
        
        if (hasCost) {
            indicator.className = 'mt-2 alert alert-success alert-sm';
            costText.innerHTML = '<strong>COM CUSTO:</strong> Este lançamento gera custo para a empresa.';
        } else {
            indicator.className = 'mt-2 alert alert-warning alert-sm';
            costText.innerHTML = '<strong>SEM CUSTO:</strong> Este lançamento não gera custo para a empresa.';
        }
    } else {
        indicator.style.display = 'none';
    }
});
</script>
"""

# JavaScript para validação de tipos
VALIDATION_SCRIPT = """
// Validação de tipos de registro
const TimeRecordTypes = {
    // Tipos com custo
    COST_TYPES: [
        'trabalho_normal', 'sabado_trabalhado', 'domingo_trabalhado',
        'feriado_trabalhado', 'meio_periodo', 'falta_justificida',
        'atestado_medico', 'ferias', 'licenca'
    ],
    
    // Tipos sem custo
    NO_COST_TYPES: [
        'sabado_folga', 'domingo_folga', 'feriado_folga', 'falta_injustificada'
    ],
    
    // Tipos que representam trabalho efetivo
    WORK_TYPES: [
        'trabalho_normal', 'sabado_trabalhado', 'domingo_trabalhado',
        'feriado_trabalhado', 'meio_periodo'
    ],
    
    hasCost: function(type) {
        return this.COST_TYPES.includes(type);
    },
    
    isWork: function(type) {
        return this.WORK_TYPES.includes(type);
    },
    
    getMultiplier: function(type) {
        switch(type) {
            case 'trabalho_normal': return 1.0;
            case 'sabado_trabalhado': return 1.5;
            case 'domingo_trabalhado': 
            case 'feriado_trabalhado': return 2.0;
            case 'ferias': return 1.33;
            default: return 1.0;
        }
    }
};

// Validação antes de envio
function validateTimeRecord(formData) {
    const type = formData.get('tipo_registro');
    const hours = parseFloat(formData.get('horas_trabalhadas') || 0);
    
    // Validar horas para tipos de trabalho
    if (TimeRecordTypes.isWork(type) && hours <= 0) {
        alert('Para lançamentos de trabalho, é necessário informar as horas trabalhadas.');
        return false;
    }
    
    // Validar tipos sem custo
    if (TimeRecordTypes.NO_COST_TYPES.includes(type)) {
        const confirmation = confirm(
            'Este tipo de lançamento NÃO gera custo para a empresa. Confirma?'
        );
        if (!confirmation) return false;
    }
    
    return true;
}
"""

def exportar_configuracao_interface():
    """Exporta configuração para uso em templates"""
    return {
        'record_types': RECORD_TYPES_INTERFACE,
        'dropdown_template': DROPDOWN_TEMPLATE,
        'validation_script': VALIDATION_SCRIPT
    }

if __name__ == "__main__":
    import json
    config = exportar_configuracao_interface()
    
    print("CONFIGURAÇÃO DE INTERFACE - TIPOS DE REGISTRO")
    print("=" * 60)
    print(f"Total de tipos: {len(config['record_types'])}")
    
    # Agrupar por categoria
    categorias = {}
    for tipo in config['record_types']:
        cat = tipo['category']
        if cat not in categorias:
            categorias[cat] = []
        categorias[cat].append(tipo)
    
    for categoria, tipos in categorias.items():
        com_custo = sum(1 for t in tipos if t['has_cost'])
        sem_custo = len(tipos) - com_custo
        print(f"\n{categoria.upper()}:")
        print(f"  • Com custo: {com_custo}")
        print(f"  • Sem custo: {sem_custo}")
        
    print(f"\nConfiguração exportada com sucesso!")
    print(f"Use em templates Jinja2 ou componentes React/Vue")