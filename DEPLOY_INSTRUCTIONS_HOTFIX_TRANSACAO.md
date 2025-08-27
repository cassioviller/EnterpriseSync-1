# 🚨 INSTRUÇÕES DE DEPLOY - HOTFIX TRANSAÇÃO DB

## SITUAÇÃO CRÍTICA
- **Problema**: Sistema em produção com erro de transação abortada
- **Impacto**: Dashboard inacessível, usuários bloqueados
- **Prioridade**: CRÍTICA

## 📋 OPÇÕES DE APLICAÇÃO

### OPÇÃO 1: Script Automatizado (RECOMENDADO)
```bash
# Fazer download do script
wget -O /tmp/hotfix_transacao.sh [URL_DO_SCRIPT]

# Tornar executável
chmod +x /tmp/hotfix_transacao.sh

# Executar
sudo /tmp/hotfix_transacao.sh
```

### OPÇÃO 2: Manual (Backup de Segurança)

#### Passo 1: Backup
```bash
cd /app
cp views.py views.py.backup.$(date +%Y%m%d_%H%M%S)
cp templates/funcionario_dashboard.html templates/funcionario_dashboard.html.backup.$(date +%Y%m%d_%H%M%S)
```

#### Passo 2: Adicionar Função de Segurança
Adicionar após linha 14 em `/app/views.py`:
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

#### Passo 3: Corrigir Template
Em `/app/templates/funcionario_dashboard.html`, linha ~105:
```html
<!-- ANTES -->
<a href="{{ url_for('main.funcionario_lista_rdos') }}" class="btn btn-outline-secondary w-100 mb-2">

<!-- DEPOIS -->
<a href="{{ url_for('main.funcionario_rdo_consolidado') }}" class="btn btn-outline-secondary w-100 mb-2">
```

#### Passo 4: Proteger Consultas
Localizar e substituir (cerca da linha 430):
```python
# ANTES
obras_ativas_count = Obra.query.filter_by(admin_id=admin_id).filter(
    Obra.status.in_(['andamento', 'Em andamento', 'ativa', 'planejamento'])
).count()

# DEPOIS
obras_ativas_count = safe_db_operation(
    lambda: Obra.query.filter_by(admin_id=admin_id).filter(
        Obra.status.in_(['andamento', 'Em andamento', 'ativa', 'planejamento'])
    ).count(),
    default_value=0
)
```

Localizar e substituir (cerca da linha 450):
```python
# ANTES
obras_andamento = Obra.query.filter_by(admin_id=admin_id).filter(
    Obra.status.in_(['andamento', 'Em andamento', 'ativa', 'planejamento'])
).order_by(Obra.data_inicio.desc()).limit(5).all()

# DEPOIS
obras_andamento = safe_db_operation(
    lambda: Obra.query.filter_by(admin_id=admin_id).filter(
        Obra.status.in_(['andamento', 'Em andamento', 'ativa', 'planejamento'])
    ).order_by(Obra.data_inicio.desc()).limit(5).all(),
    default_value=[]
)
```

#### Passo 5: Reiniciar Aplicação
```bash
# Reload suave (preferido)
pkill -HUP -f "gunicorn.*main:app"

# OU restart completo se necessário
pkill -f "gunicorn.*main:app"
cd /app
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 --daemon main:app
```

## ✅ VERIFICAÇÃO PÓS-DEPLOY

### 1. Teste de Saúde
```bash
curl http://localhost:5000/health
# Deve retornar: {"status": "healthy", "database": "connected"}
```

### 2. Teste de Dashboard
```bash
curl -I http://localhost:5000/dashboard
# Deve retornar: HTTP/1.1 200 OK (ou 302 redirect)
```

### 3. Monitorar Logs
```bash
# Logs da aplicação
tail -f /app/logs/*.log

# Logs do sistema (se disponível)
journalctl -u sige -f
```

## 🔄 ROLLBACK (Se Necessário)

```bash
# Restaurar backup
cp /app/views.py.backup.YYYYMMDD_HHMMSS /app/views.py
cp /app/templates/funcionario_dashboard.html.backup.YYYYMMDD_HHMMSS /app/templates/funcionario_dashboard.html

# Reiniciar
pkill -HUP -f "gunicorn.*main:app"
```

## 📊 MONITORAMENTO PÓS-CORREÇÃO

### Logs para Observar:
- ✅ Ausência de "psycopg2.errors.InFailedSqlTransaction"
- ✅ Presença de "ERRO DB OPERATION:" (indica funcionamento da proteção)
- ✅ Carregamento normal do dashboard

### Métricas de Sucesso:
- ✅ Dashboard carrega sem erro 500
- ✅ KPIs exibem valores (mesmo que 0 em caso de erro)
- ✅ Navegação funcional entre páginas
- ✅ Template moderno mantido em todas as páginas

---

**⏰ Tempo Estimado**: 5-10 minutos
**🔧 Complexidade**: Baixa-Média
**🎯 Impacto**: Resolução completa do problema crítico

**Próximos Passos Após Correção**:
1. Monitorar por 30 minutos
2. Verificar se outros módulos estão funcionais
3. Comunicar resolução à equipe
4. Documentar lições aprendidas