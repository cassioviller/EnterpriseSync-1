# PLANO DE CORREÇÃO RDO FLEXÍVEL

## 🚨 PROBLEMA IDENTIFICADO

### Erro "Funcionário não encontrado" (linha 3001 views.py)
```python
flash('Funcionário não encontrado. Entre em contato com o administrador.', 'error')
return redirect(url_for('main.funcionario_rdo_consolidado'))
```

**Causa:** Sistema não consegue encontrar funcionário vinculado ao usuário atual.

## 📋 PLANO DE AÇÃO

### FASE 1: CORREÇÃO DO ERRO DE FUNCIONÁRIO (PRIORIDADE MÁXIMA)

#### 1.1 Investigar Mapeamento Usuário → Funcionário
- **Problema:** current_user.email não está encontrando funcionário correspondente
- **Verificar:** Tabela funcionarios tem email = admin@valeverde.com.br?
- **Solução:** Criar bypass para desenvolvimento ou ajustar lógica

#### 1.2 Implementar Fallback Robusto
```python
# ANTES (linha 3001):
flash('Funcionário não encontrado. Entre em contato com o administrador.', 'error')

# DEPOIS - Fallback inteligente:
funcionario = get_or_create_funcionario_fallback(current_user, admin_id)
```

### FASE 2: SISTEMA FLEXÍVEL DE SERVIÇOS RDO

#### 2.1 Estrutura de Dados Flexível

**Configuração por Obra:**
```python
CONFIGURACOES_SERVICOS = {
    'obra_1': {
        'servicos': [
            {'nome': 'Estrutura Metálica', 'subatividades': 5},
            {'nome': 'Manta PVC', 'subatividades': 5}
        ]
    },
    'obra_2': {
        'servicos': [
            {'nome': 'Estrutura Metálica', 'subatividades': 3},
            {'nome': 'Manta PVC', 'subatividades': 4},
            {'nome': 'Beiral Metálico', 'subatividades': 4}
        ]
    }
}
```

#### 2.2 Sistema de Templates de Serviços

**Template Tipo A - 2 serviços com 5 subatividades:**
- Estrutura Metálica (5 sub)
- Manta PVC (5 sub)

**Template Tipo B - 3 serviços com variação:**
- Estrutura Metálica (3 sub)
- Manta PVC (4 sub) 
- Beiral Metálico (4 sub)

#### 2.3 API Dinâmica de Serviços
```javascript
function carregarServicosObra(obraId) {
    fetch(`/api/obras/${obraId}/servicos`)
        .then(response => response.json())
        .then(data => renderizarServicos(data.servicos));
}
```

### FASE 3: IMPLEMENTAÇÃO DO SISTEMA FLEXÍVEL

#### 3.1 Backend - Models Flexíveis
```python
class ConfiguracaoServicoObra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    servico_nome = db.Column(db.String(200))
    subatividades_config = db.Column(db.JSON)  # Array de subatividades
    ordem_exibicao = db.Column(db.Integer, default=0)

class RDOServicoFlexivel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rdo_id = db.Column(db.Integer, db.ForeignKey('rdo.id'))
    servico_nome = db.Column(db.String(200))
    subatividade_nome = db.Column(db.String(200))
    percentual_concluido = db.Column(db.Numeric(5,2))
    observacoes = db.Column(db.Text)
```

#### 3.2 Frontend - Renderização Dinâmica
```javascript
function renderizarServicos(servicos) {
    const container = document.getElementById('servicos-container');
    container.innerHTML = '';
    
    servicos.forEach(servico => {
        const servicoCard = criarCardServico(servico);
        container.appendChild(servicoCard);
    });
}

function criarCardServico(servico) {
    return `
        <div class="servico-card mb-3">
            <div class="servico-header" onclick="toggleServico('${servico.id}')">
                <h5>${servico.nome}</h5>
                <span>${servico.subatividades.length} subatividades</span>
            </div>
            <div class="servico-body collapse" id="body-${servico.id}">
                ${renderizarSubatividades(servico.subatividades)}
            </div>
        </div>
    `;
}
```

#### 3.3 Sistema de Salvamento Flexível
```python
def salvar_rdo_flexivel(rdo_data):
    # 1. Criar RDO base
    rdo = RDO(**rdo_data['basico'])
    db.session.add(rdo)
    db.session.flush()
    
    # 2. Salvar serviços dinamicamente
    for servico in rdo_data['servicos']:
        for subatividade in servico['subatividades']:
            rdo_servico = RDOServicoFlexivel(
                rdo_id=rdo.id,
                servico_nome=servico['nome'],
                subatividade_nome=subatividade['nome'],
                percentual_concluido=subatividade['percentual']
            )
            db.session.add(rdo_servico)
    
    # 3. Salvar funcionários
    for funcionario_id in rdo_data['funcionarios']:
        rdo_funcionario = RDOMaoObra(
            rdo_id=rdo.id,
            funcionario_id=funcionario_id
        )
        db.session.add(rdo_funcionario)
    
    db.session.commit()
```

### FASE 4: CONFIGURAÇÃO POR OBRA

#### 4.1 Interface de Configuração
- Página admin para configurar serviços por obra
- Drag & drop para reordenar serviços
- Adicionar/remover subatividades dinamicamente

#### 4.2 Presets Predefinidos
```python
PRESETS_SERVICOS = {
    'construcao_civil_basica': {
        'Estrutura Metálica': ['Montagem', 'Armação', 'Concretagem', 'Cura', 'Acabamento'],
        'Manta PVC': ['Preparação', 'Primer', 'Instalação', 'Vedação', 'Teste']
    },
    'construcao_civil_completa': {
        'Estrutura Metálica': ['Medição', 'Montagem', 'Concretagem'],
        'Manta PVC': ['Preparação', 'Primer', 'Instalação', 'Acabamento'],
        'Beiral Metálico': ['Marcação', 'Corte', 'Fixação', 'Instalação']
    }
}
```

## 🎯 EXECUÇÃO IMEDIATA

### Prioridade 1: Corrigir erro "Funcionário não encontrado"
1. ✅ Investigar mapeamento email → funcionário
2. ✅ Implementar fallback robusto
3. ✅ Testar salvamento RDO

### Prioridade 2: Sistema flexível básico
1. ✅ Criar API dinâmica `/api/obras/{id}/servicos`
2. ✅ Modificar frontend para renderização dinâmica
3. ✅ Implementar salvamento flexível

### Prioridade 3: Configuração de templates
1. ✅ Interface para configurar serviços por obra
2. ✅ Presets predefinidos
3. ✅ Migração dos dados existentes

## 📊 RESULTADO ESPERADO

### Flexibilidade Completa:
- ✅ **Obra A**: 2 serviços × 5 subatividades = 10 campos
- ✅ **Obra B**: 3 serviços × (3+4+4) subatividades = 11 campos
- ✅ **Obra C**: Configuração personalizada ilimitada

### UX Otimizada:
- ✅ Carregamento automático por obra selecionada
- ✅ Interface consistente independente do número de serviços
- ✅ Salvamento robusto com validação

### Manutenibilidade:
- ✅ Configuração via admin, não código
- ✅ Fácil adição de novos templates
- ✅ Histórico de mudanças preservado