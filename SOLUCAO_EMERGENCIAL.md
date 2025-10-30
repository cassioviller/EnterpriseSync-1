# 🚨 SOLUÇÃO EMERGENCIAL - Migration 48 Não Funcionando

## Problema
A Migration 48 não está sendo executada automaticamente em produção (Easypanel).

---

## ✅ SOLUÇÃO 1: Diagnóstico + SQL Direto (MAIS RÁPIDO - 2 minutos)

### Passo 1: Conectar ao Easypanel

```bash
# Via terminal do Easypanel ou SSH
docker exec -it <container-sige> bash
```

### Passo 2: Diagnosticar o Problema

```bash
python3 diagnostico_producao.py
```

**Isso vai mostrar EXATAMENTE quais tabelas estão faltando admin_id.**

### Passo 3: Aplicar Correção SQL Direta

```bash
# Backup primeiro (OBRIGATÓRIO)
pg_dump $DATABASE_URL > /tmp/backup_$(date +%Y%m%d_%H%M%S).sql

# Executar correção SQL
psql $DATABASE_URL < correcao_direta_producao.sql
```

**Isso adiciona admin_id nas 3 tabelas em ~30 segundos.**

### Passo 4: Reiniciar Aplicação

```bash
supervisorctl restart all
```

### Passo 5: Validar

```bash
python3 diagnostico_producao.py
# Deve mostrar: ✅ DIAGNÓSTICO: Sistema OK
```

---

## ✅ SOLUÇÃO 2: Via Interface PostgreSQL (Alternativa)

Se você tem acesso ao painel do Neon/PostgreSQL:

1. Abrir console SQL
2. Copiar conteúdo de `correcao_direta_producao.sql`
3. Colar e executar
4. Reiniciar aplicação no Easypanel

---

## ✅ SOLUÇÃO 3: Forçar Migration via Python

Se as soluções acima não funcionarem:

```bash
cd /app  # ou diretório da aplicação

# Executar migration manualmente
python3 -c "
from app import app, db
from migrations import _migration_48_adicionar_admin_id_modelos_faltantes
import logging

logging.basicConfig(level=logging.INFO)

with app.app_context():
    try:
        print('🔄 Executando Migration 48...')
        _migration_48_adicionar_admin_id_modelos_faltantes()
        print('✅ Migration 48 executada!')
    except Exception as e:
        print(f'❌ Erro: {e}')
        import traceback
        traceback.print_exc()
"
```

---

## 🔍 Por Que a Migration Não Executou Automaticamente?

**Possíveis causas:**

1. **Migration já marcada como executada** mas não foi aplicada
   - Solução: SQL direto (Solução 1)

2. **Erro durante execução** (órfãos, etc)
   - Solução: Ver logs `/var/log/app.log`

3. **Tabela migration_history corrompida**
   - Solução: SQL direto (Solução 1)

---

## 🧪 Testar Após Correção

1. **Acessar:** `https://sige.cassiovillar.tech/funcionario/rdo/consolidado`
   - ✅ Deve mostrar porcentagens reais (não 0.0%)

2. **Acessar:** `https://sige.cassiovillar.tech/funcionarios`
   - ✅ Deve carregar sem erros

3. **Verificar logs:**
   ```bash
   tail -50 /var/log/app.log | grep -i error
   # Não deve ter erros de "admin_id does not exist"
   ```

---

## ⏱️ Tempo Estimado por Solução

| Solução | Tempo | Complexidade |
|---------|-------|--------------|
| SQL Direto (Solução 1) | 2 min | Baixa |
| Interface PostgreSQL (Solução 2) | 3 min | Baixa |
| Python Manual (Solução 3) | 5 min | Média |

---

## 📞 Se NADA Funcionar

Execute e envie resultado:

```bash
# Diagnóstico completo
python3 diagnostico_producao.py > /tmp/diagnostico.txt 2>&1

# Logs da aplicação
tail -200 /var/log/app.log > /tmp/app_logs.txt

# Schema das 3 tabelas
psql $DATABASE_URL -c "\d rdo_mao_obra" > /tmp/schema.txt
psql $DATABASE_URL -c "\d funcao" >> /tmp/schema.txt
psql $DATABASE_URL -c "\d registro_alimentacao" >> /tmp/schema.txt

# Ver arquivos
cat /tmp/diagnostico.txt
cat /tmp/app_logs.txt
cat /tmp/schema.txt
```

---

## ✅ Resultado Esperado

**Antes:**
```
❌ column rdo_mao_obra.admin_id does not exist
❌ InFailedSqlTransaction
❌ RDOs: 0.0%
```

**Depois:**
```
✅ Todas as queries funcionam
✅ RDOs: valores reais
✅ Sistema funcional
```
