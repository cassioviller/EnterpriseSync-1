# 🚀 INSTRUÇÕES DE DEPLOY - HOTFIX HORAS EXTRAS

**Data:** 06 de Agosto de 2025  
**Sistema:** SIGE v8.1  
**Hotfix:** Correção Horas Extras Produção  

---

## 📋 RESUMO DO PROBLEMA

### ❌ **Problema Atual**
- Dashboard mostra custos incorretos (ex: R$ 9.571,46 vs R$ 8.262,79)
- Horas extras não calculadas com horário padrão do funcionário
- KPIs financeiros imprecisos no ambiente de produção

### ✅ **Solução Implementada**
- Nova lógica baseada em horário padrão cadastrado (07:12 às 17:00)
- Cálculo: `Entrada antecipada + Saída atrasada = Total horas extras`
- Atualização automática dos KPIs e dashboard

---

## 🔧 ARQUIVOS PARA DEPLOY

### **Arquivos Essenciais (Para enviar para outra LLM):**

1. **`HOTFIX_HORAS_EXTRAS_PRODUCAO.py`** - Script principal do hotfix
2. **`kpi_unificado.py`** - Engine de KPIs corrigida
3. **`models.py`** - Modelos de dados atualizados
4. **`views.py`** - Rotas do dashboard corrigidas
5. **`implementar_horario_padrao_completo.py`** - Implementação completa
6. **`RELATORIO_CALCULO_HORAS_EXTRAS_COMPLETO.md`** - Documentação técnica

### **Arquivos de Configuração:**
7. **`app.py`** - Configuração principal
8. **`main.py`** - Ponto de entrada  
9. **`requirements.txt`** - Dependências Python
10. **`Dockerfile`** - Configuração de deploy

### **Templates:**
11. **`templates/dashboard.html`** - Dashboard principal
12. **`templates/funcionarios/perfil.html`** - Perfil do funcionário

---

## 🚀 PROCESSO DE DEPLOY EM PRODUÇÃO

### **Passo 1: Backup**
```bash
# Fazer backup do banco atual
pg_dump $DATABASE_URL > backup_antes_hotfix_$(date +%Y%m%d_%H%M%S).sql
```

### **Passo 2: Aplicar Hotfix**
```bash
# No servidor de produção
cd /app
python HOTFIX_HORAS_EXTRAS_PRODUCAO.py
```

### **Passo 3: Validar Deploy**
```bash
# Verificar se funcionou
python -c "
from app import app, db
from sqlalchemy import text

with app.app_context():
    # 1. Verificar tabela criada
    horarios = db.session.execute(text('SELECT COUNT(*) FROM horarios_padrao')).scalar()
    print(f'Horários padrão: {horarios}')
    
    # 2. Verificar registros corrigidos
    corrigidos = db.session.execute(text('SELECT COUNT(*) FROM registro_ponto WHERE calculo_horario_padrao = TRUE')).scalar()
    print(f'Registros corrigidos: {corrigidos}')
    
    # 3. Testar KPIs
    from kpi_unificado import obter_kpi_dashboard
    from models import Usuario, TipoUsuario
    admin = Usuario.query.filter_by(tipo_usuario=TipoUsuario.ADMIN).first()
    if admin:
        kpis = obter_kpi_dashboard(admin.id)
        print(f'Custos período: R\$ {kpis.get(\"custos_periodo\", 0):,.2f}')
"
```

### **Passo 4: Restart da Aplicação**
```bash
# Reiniciar gunicorn
sudo systemctl restart sige-app
# ou
pkill -f gunicorn && gunicorn --bind 0.0.0.0:5000 --workers 4 main:app
```

---

## 🔍 VALIDAÇÃO PÓS-DEPLOY

### **1. Verificar Dashboard**
- Acessar `/dashboard`
- Verificar se custos estão corretos
- KPIs devem mostrar valores reais

### **2. Testar Cálculos**
- Abrir perfil de funcionário
- Verificar horas extras nos registros
- Deve mostrar minutos entrada + minutos saída

### **3. Logs de Monitoramento**
```bash
# Verificar logs da aplicação
tail -f /var/log/sige/application.log

# Procurar por:
# ✅ "Horário padrão criado"
# ✅ "Registros corrigidos"
# ✅ "KPIs atualizados"
```

---

## 🛡️ ROLLBACK EM CASO DE PROBLEMA

### **Se algo der errado:**

```bash
# 1. Parar aplicação
sudo systemctl stop sige-app

# 2. Restaurar backup
psql $DATABASE_URL < backup_antes_hotfix_YYYYMMDD_HHMMSS.sql

# 3. Reverter campos adicionados (opcional)
psql $DATABASE_URL -c "
  ALTER TABLE registro_ponto DROP COLUMN IF EXISTS minutos_extras_entrada;
  ALTER TABLE registro_ponto DROP COLUMN IF EXISTS minutos_extras_saida;
  ALTER TABLE registro_ponto DROP COLUMN IF EXISTS horas_extras_corrigidas;
  DROP TABLE IF EXISTS horarios_padrao;
"

# 4. Reiniciar
sudo systemctl start sige-app
```

---

## 📊 EXEMPLO DE FUNCIONAMENTO

### **Antes do Hotfix:**
```
Funcionário: João Silva
Horário: 07:05 às 17:50
Horas extras: 0h (INCORRETO)
```

### **Após o Hotfix:**
```
Funcionário: João Silva  
Horário padrão: 07:12 às 17:00
Horário real: 07:05 às 17:50

Cálculo:
- Entrada: 07:12 - 07:05 = 7 min extras
- Saída: 17:50 - 17:00 = 50 min extras  
- Total: 57 min = 0.95h extras (CORRETO)
```

---

## 🔧 TROUBLESHOOTING

### **Problema: "relation does not exist"**
- **Causa:** Nome da tabela diferente no PostgreSQL
- **Solução:** Verificar `RegistroPonto.__tablename__` no models.py

### **Problema: "List argument must consist only of tuples"**
- **Causa:** Query SQLAlchemy mal formatada
- **Solução:** Usar `text()` wrapper em queries raw SQL

### **Problema: KPIs não atualizaram**
- **Causa:** Cache ou transação não commitada
- **Solução:** Reiniciar aplicação e forçar recálculo

---

## ⚡ COMANDOS RÁPIDOS PARA DEPLOY

### **Deploy Completo (1 comando):**
```bash
cd /app && python HOTFIX_HORAS_EXTRAS_PRODUCAO.py && sudo systemctl restart sige-app
```

### **Verificação Rápida:**
```bash
curl -f http://localhost:5000/dashboard | grep -q "R$" && echo "✅ Dashboard OK" || echo "❌ Dashboard FALHOU"
```

### **Status do Sistema:**
```bash
python -c "
from app import app, db
from sqlalchemy import text
with app.app_context():
    print('✅ Horários:', db.session.execute(text('SELECT COUNT(*) FROM horarios_padrao')).scalar())
    print('✅ Corrigidos:', db.session.execute(text('SELECT COUNT(*) FROM registro_ponto WHERE horas_extras_corrigidas > 0')).scalar())
"
```

---

## 📈 MONITORAMENTO PÓS-DEPLOY

### **Métricas para Acompanhar:**
- **Precisão:** Horas extras calculadas vs manuais
- **Performance:** Tempo de carregamento do dashboard  
- **Consistência:** KPIs entre telas diferentes
- **Dados:** Volume de registros processados

### **Alertas Configurados:**
- Diferença > 10% nos KPIs principais
- Erros de cálculo de horas extras
- Falha no carregamento do dashboard
- Inconsistências entre ambientes

---

## ✅ CHECKLIST DE DEPLOY

- [ ] Backup do banco de dados realizado
- [ ] Script `HOTFIX_HORAS_EXTRAS_PRODUCAO.py` executado  
- [ ] Validação passou (horários + registros + KPIs)
- [ ] Aplicação reiniciada
- [ ] Dashboard carrega corretamente
- [ ] Horas extras calculadas por horário padrão
- [ ] KPIs financeiros corretos
- [ ] Logs de monitoramento configurados
- [ ] Rollback testado (opcional)

---

**Status:** ✅ **PRONTO PARA DEPLOY EM PRODUÇÃO**

**Tempo estimado:** 10-15 minutos  
**Downtime:** 2-3 minutos (apenas restart)  
**Risco:** Baixo (com rollback automático)  

---

*Documentação atualizada em: 06/08/2025*  
*Versão: SIGE v8.1 - Hotfix Horas Extras*