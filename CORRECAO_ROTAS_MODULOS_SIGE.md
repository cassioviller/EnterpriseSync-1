# 🔧 CORREÇÃO URGENTE - Rotas dos Módulos SIGE v8.0

**Data:** 11 de Agosto de 2025 - 21:37 BRT  
**Prioridade:** ALTA  
**Status:** 🔄 **EM ANDAMENTO**

---

## 🚨 **PROBLEMAS IDENTIFICADOS**

### **1. Rotas de Navegação Quebradas**
```
❌ Propostas: url_for('main.propostas') não existe
❌ Equipes: url_for('main.equipes') não existe  
❌ Folha Pagamento: url_for('folha_pagamento.dashboard') incorreto
❌ Contabilidade: url_for('contabilidade.dashboard') verificando
❌ Almoxarifado: /produtos/novo com Internal Server Error
```

### **2. Nomes de Blueprints Incorretos**
```python
# IDENTIFICADO:
folha_pagamento_views.py -> Blueprint: 'folha' (não 'folha_pagamento')
contabilidade_views.py -> Blueprint: 'contabilidade' (verificar)
```

---

## 🔧 **CORREÇÕES IMPLEMENTADAS**

### **✅ 1. Rotas Adicionadas no views.py**
```python
# Adicionado linhas 165-180:
@main_bp.route('/propostas')
@admin_required
def propostas():
    return render_template('propostas/lista_propostas.html')

@main_bp.route('/propostas/nova')
@admin_required
def nova_proposta():
    return render_template('propostas/nova_proposta.html')

@main_bp.route('/equipes')
@admin_required
def equipes():
    return render_template('equipes/gestao_equipes.html')
```

### **✅ 2. Correção Blueprint Folha Pagamento**
```html
<!-- templates/base.html linha 762 -->
<!-- ANTES: -->
{{ url_for('folha_pagamento.dashboard') }}
<!-- DEPOIS: -->
{{ url_for('folha.dashboard') }}
```

### **✅ 3. Template Almoxarifado Criado**
```
✓ templates/almoxarifado/notas_fiscais.html criado
✓ Template completo com funcionalidades de import XML
```

---

## 🔍 **VALIDAÇÃO EM ANDAMENTO**

### **📋 Checklist de Verificação:**
- [x] Identificar nomes corretos dos blueprints
- [x] Corrigir template base.html
- [x] Adicionar rotas faltantes em views.py
- [ ] Testar todas as rotas de navegação
- [ ] Corrigir erros LSP no almoxarifado_views.py
- [ ] Validar sistema completo

### **🎯 Próximas Ações:**
1. Verificar nome do blueprint contabilidade
2. Corrigir problemas de sintaxe no almoxarifado
3. Testar navegação completa
4. Validar todos os módulos

---

**Status Atual:** Sistema com navegação parcialmente corrigida, finalizando correções