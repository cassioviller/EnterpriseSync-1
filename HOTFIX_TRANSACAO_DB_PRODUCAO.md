# HOTFIX URGENTE: Erro de Transação em Produção

## 🚨 PROBLEMA IDENTIFICADO
- Erro: `psycopg2.errors.InFailedSqlTransaction: current transaction is aborted`
- Local: Linha 430 do views.py em produção
- Causa: Transações de banco abortadas não tratadas adequadamente

## ✅ CORREÇÕES IMPLEMENTADAS NO CÓDIGO

### 1. Função de Segurança para Operações DB
```python
def safe_db_operation(operation, default_value=None):
    """Executa operação no banco com tratamento seguro de transação"""
    try:
        return operation()
    except Exception as e:
        print(f"ERRO DB OPERATION: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        return default_value
```

### 2. Correções nas Consultas Problemáticas
- **Linha 432-438**: Contagem de obras ativas com tratamento de erro
- **Linha 459-464**: Busca de obras em andamento com proteção

### 3. Rota Corrigida no Template
- **Arquivo**: `templates/funcionario_dashboard.html`
- **Correção**: `funcionario_lista_rdos` → `funcionario_rdo_consolidado`

## 📋 INSTRUÇÕES PARA DEPLOY EM PRODUÇÃO

### Passo 1: Backup de Segurança
```bash
# Fazer backup do views.py atual
cp /app/views.py /app/views.py.backup.$(date +%Y%m%d_%H%M%S)
```

### Passo 2: Aplicar Correções no Código
1. **Adicionar função safe_db_operation** após a linha 14 em views.py
2. **Substituir consultas problemáticas** nas linhas 430-438 e 448-456
3. **Corrigir template funcionário** - linha 105 em funcionario_dashboard.html

### Passo 3: Restart da Aplicação
```bash
# Reiniciar workers do gunicorn
pkill -f gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 2 --reload main:app
```

## 🔧 CÓDIGO ESPECÍFICO PARA PRODUÇÃO

### views.py - Adicionar após linha 14:
```python
def safe_db_operation(operation, default_value=None):
    """Executa operação no banco com tratamento seguro de transação"""
    try:
        return operation()
    except Exception as e:
        print(f"ERRO DB OPERATION: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        return default_value
```

### views.py - Substituir linhas 430-438:
```python
# Adicionar contagem correta de obras ativas com tratamento de erro
obras_ativas_count = safe_db_operation(
    lambda: Obra.query.filter_by(admin_id=admin_id).filter(
        Obra.status.in_(['andamento', 'Em andamento', 'ativa', 'planejamento'])
    ).count(),
    default_value=0
)
```

### views.py - Substituir linhas 448-456:
```python
# Buscar obras em andamento para a tabela com tratamento de erro
obras_andamento = safe_db_operation(
    lambda: Obra.query.filter_by(admin_id=admin_id).filter(
        Obra.status.in_(['andamento', 'Em andamento', 'ativa', 'planejamento'])
    ).order_by(Obra.data_inicio.desc()).limit(5).all(),
    default_value=[]
)
```

### funcionario_dashboard.html - Linha 105:
```html
<a href="{{ url_for('main.funcionario_rdo_consolidado') }}" class="btn btn-outline-secondary w-100 mb-2">
```

## 🎯 RESULTADO ESPERADO
- ✅ Fim dos erros de transação abortada
- ✅ Sistema resiliente a falhas de conexão DB
- ✅ Páginas carregam com dados padrão em caso de erro
- ✅ Logs detalhados para debugging

## ⚠️ NOTAS IMPORTANTES
- **Backup obrigatório** antes de aplicar
- **Teste em ambiente de staging** se disponível
- **Monitorar logs** após aplicação
- **Rollback disponível** via backup

---
**Status**: Pronto para aplicação em produção
**Prioridade**: CRÍTICA - Sistema inacessível
**Tempo estimado**: 5-10 minutos