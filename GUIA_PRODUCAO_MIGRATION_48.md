# 🚀 Guia Executivo - Migration 48 em Produção (Easypanel)

## ⚡ Quick Start (5 minutos)

### 1️⃣ Conectar ao Container

```bash
# Via Easypanel UI
# Vá para: Services → SIGE → Terminal
# OU via SSH:
ssh usuario@servidor
docker exec -it <container-sige> bash
```

### 2️⃣ Fazer Backup (OBRIGATÓRIO)

```bash
# Dentro do container
pg_dump $DATABASE_URL > /tmp/backup_pre_migration48_$(date +%Y%m%d_%H%M%S).sql

# Confirmar backup criado
ls -lh /tmp/backup_pre_migration48_*
# Deve mostrar arquivo com tamanho > 0 bytes
```

### 3️⃣ Verificar Status Atual

```bash
cd /app  # ou onde está o código
python3 check_migration_48.py
```

**Esperado:**
```
❌ rdo_mao_obra.admin_id NÃO EXISTE
❌ funcao.admin_id NÃO EXISTE  
❌ registro_alimentacao.admin_id NÃO EXISTE

Tabelas com admin_id: 0/3
🔧 AÇÃO NECESSÁRIA: Executar Migration 48
```

### 4️⃣ Executar Migration 48

**Opção A: Via Restart (RECOMENDADO - Automático)**

```bash
# No painel Easypanel UI
# Clicar em "Restart" no serviço SIGE

# OU via comando
supervisorctl restart all
```

**A migração executa AUTOMATICAMENTE no startup!**

**Opção B: Script Manual (se restart não funcionar)**

```bash
python3 force_migration_48.py
# Digite: EXECUTAR (quando solicitado)
```

### 5️⃣ Monitorar Logs

```bash
# Acompanhar execução em tempo real
tail -f /var/log/app.log | grep -i "migr"

# OU logs do Easypanel UI
# Services → SIGE → Logs
```

**Procure por:**
```
INFO:migrations:▶️  Migração 48 [...] EXECUTANDO...
INFO:migrations:✅ Migração 48 completada com sucesso
```

### 6️⃣ Validar Sucesso

```bash
python3 validate_migration_48.py
```

**Esperado:**
```
✅ VALIDAÇÃO COMPLETA - MIGRATION 48 EXECUTADA COM SUCESSO
🎉 Sistema está pronto para uso!
```

### 7️⃣ Testar Interface

1. Acesse: `https://sige.cassiovillar.tech/funcionarios`
   - ✅ Deve carregar sem erros
   - ✅ Funções devem aparecer

2. Acesse: `https://sige.cassiovillar.tech/funcionario/rdo/consolidado`
   - ✅ RDOs devem mostrar porcentagens reais
   - ✅ Atividades, funcionários e horas devem aparecer

3. Acesse: `https://sige.cassiovillar.tech/detalhes_obra/<id>`
   - ✅ Registros de alimentação devem aparecer

---

## ⚠️ Troubleshooting

### Problema: "Registros órfãos detectados"

```
❌ ERRO: X registros órfãos em funcao
```

**Solução:**
```bash
# Rollback
python3 rollback_migration_48.py

# Restaurar backup
psql $DATABASE_URL < /tmp/backup_pre_migration48_*.sql

# Corrigir dados órfãos manualmente
# (Entre em contato para suporte)
```

### Problema: Migration não executa no restart

**Causa:** Já foi executada antes

**Verificar:**
```bash
psql $DATABASE_URL -c "SELECT * FROM migration_history WHERE migration_number = 48;"
```

**Se retornar linha:** Migration já foi executada ✅

**Se não retornar:** Forçar execução:
```bash
python3 force_migration_48.py --force
```

### Problema: Aplicação não inicia após migration

**Solução RÁPIDA:**
```bash
# Parar aplicação
supervisorctl stop all

# Restaurar backup
psql $DATABASE_URL < /tmp/backup_pre_migration48_*.sql

# Reiniciar
supervisorctl start all
```

---

## 📋 Checklist Completo

- [ ] Conectado ao container Easypanel
- [ ] Backup criado e verificado (`ls -lh /tmp/backup_*`)
- [ ] Status atual verificado (`python3 check_migration_48.py`)
- [ ] Aplicação reiniciada (migration executada)
- [ ] Logs monitorados (sem erros)
- [ ] Validação executada (`python3 validate_migration_48.py`)
- [ ] Teste 1: `/funcionarios` carrega sem erros
- [ ] Teste 2: `/funcionario/rdo/consolidado` mostra dados reais
- [ ] Teste 3: `/detalhes_obra` mostra registros de alimentação

---

## 🎯 Resultado Esperado

**ANTES:**
```
❌ Erro: column rdo_mao_obra.admin_id does not exist
❌ Erro: column funcao.admin_id does not exist
❌ RDOs mostram 0.0% progresso
❌ Interface quebrada
```

**DEPOIS:**
```
✅ Todas as queries funcionam
✅ RDOs mostram porcentagens reais (10%, 50%, 82%, 100%)
✅ Atividades, funcionários e horas aparecem
✅ Interface funcional
```

---

## 📞 Suporte

**Se encontrar problemas:**

1. **Backup existe?** → Rollback é seguro
2. **Capturar logs:** 
   ```bash
   tail -200 /var/log/app.log > /tmp/error_log.txt
   ```
3. **Executar diagnóstico:**
   ```bash
   python3 check_migration_48.py > /tmp/diagnostic.txt
   ```

**Arquivos importantes:**
- Backup: `/tmp/backup_pre_migration48_*.sql`
- Logs: `/var/log/app.log`
- Diagnóstico: `/tmp/diagnostic.txt`

---

## ⏱️ Estimativa de Tempo

| Etapa | Tempo |
|-------|-------|
| Backup | 30s |
| Verificação | 10s |
| Execução | 2-5 min |
| Validação | 10s |
| Testes | 2 min |
| **TOTAL** | **5-10 min** |

---

## 🔐 Segurança

✅ **Backup criado ANTES** de qualquer mudança  
✅ **Rollback disponível** via script dedicado  
✅ **Validação automática** pós-execução  
✅ **Sem perda de dados** - apenas adiciona colunas  

**Risco:** ⚠️ Baixo (com backup)  
**Complexidade:** ⚠️⚠️ Média  
**Impacto:** 🎯 Alto (resolve todos os erros)
