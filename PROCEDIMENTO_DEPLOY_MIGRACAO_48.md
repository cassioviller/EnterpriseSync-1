# Procedimento de Deploy - Migração 48 em Produção Easypanel

**Data:** 30/10/2025  
**Versão:** 1.0  
**Severidade:** 🔴 CRÍTICA - Sistema quebrará se migração não for executada

---

## 🚨 Situação Atual

### Problema Identificado
```
ERRO: column funcao.admin_id does not exist
```

**Causa Raiz:**
- ✅ Desenvolvimento: Migração 48 executada (todas as 20 tabelas têm admin_id)
- ❌ Produção Easypanel: Migração 48 **NÃO executada** (funcao sem admin_id)
- ❌ Código Python já espera admin_id em funcao
- ❌ Sistema em produção está **QUEBRADO**

### Tabelas Afetadas (20 no total)
```
departamento, funcao, horario_trabalho, servico_obra,
historico_produtividade_servico, tipo_ocorrencia, ocorrencia,
calendario_util, centro_custo, receita, orcamento_obra,
fluxo_caixa, registro_alimentacao, rdo_mao_obra, rdo_equipamento,
rdo_ocorrencia, rdo_foto, notificacao_cliente, proposta_itens,
proposta_arquivos
```

---

## 📋 Pré-Requisitos

### 1. Backup Completo
```bash
# Via Easypanel - fazer backup completo do banco
# OU via pg_dump:
pg_dump -h <HOST> -U <USER> -d <DATABASE> > backup_pre_migracao_48_$(date +%Y%m%d_%H%M%S).sql
```

### 2. Validação Pré-Migração
Execute o script `migration_48_validation.sql` no banco de produção:

```bash
psql -h <HOST> -U <USER> -d <DATABASE> -f migration_48_validation.sql > validacao_pre_migracao.txt
```

**Revise o output:**
- ✅ Quais tabelas JÁ têm admin_id?
- 📊 Quantos registros em cada tabela?
- 👥 Quantos admins ativos no sistema?
- ⚠️ Há registros órfãos?

---

## 🚀 Procedimento de Deploy

### Opção A: Deploy Automático (Recomendado)
A migração 48 executará automaticamente no próximo deploy via Easypanel.

**Passos:**
1. ✅ **Backup completo** (pré-requisito obrigatório)
2. ✅ **Validação pré-migração** (executar migration_48_validation.sql)
3. 🚀 **Deploy no Easypanel** (git push → rebuild → restart)
4. 📊 **Monitorar logs** durante inicialização
5. ✅ **Validação pós-migração** (verificar se erro sumiu)

**Logs Esperados:**
```
INFO:migrations:🔄 MIGRAÇÃO 48: Multi-tenancy completo com backfill por relacionamento
INFO:migrations:  ✅ departamento: 29 registros atualizados
INFO:migrations:  ✅ funcao: 48 registros atualizados
...
INFO:migrations:🔍 VALIDAÇÕES PÓS-BACKFILL: Verificando integridade multi-tenant
INFO:migrations:✅ VALIDAÇÕES CONCLUÍDAS: Integridade multi-tenant verificada!
INFO:migrations:✅ MIGRAÇÃO 48 CONCLUÍDA!
```

### Opção B: Deploy Manual (Se Opção A Falhar)
**⚠️ Apenas se a migração automática falhar**

1. **Conectar ao banco de produção**
2. **Executar migração manualmente** (via migrations.py)
3. **Reiniciar aplicação**

---

## 🔍 Validações Pós-Migração

### 1. Verificar Logs
```bash
# Via Easypanel, verificar logs de inicialização
# Buscar por: "MIGRAÇÃO 48 CONCLUÍDA"
```

### 2. Verificar Tabelas
```sql
-- Verificar que todas as 20 tabelas têm admin_id
SELECT 
    table_name,
    column_name,
    is_nullable,
    data_type
FROM information_schema.columns
WHERE table_name IN (
    'departamento', 'funcao', 'horario_trabalho'
    -- ... (todas as 20 tabelas)
)
AND column_name = 'admin_id'
ORDER BY table_name;

-- Deve retornar 20 linhas com admin_id NOT NULL
```

### 3. Testar Página de Funcionários
```bash
# Acessar: https://<seu-dominio>/funcionarios
# Verificar que NÃO ocorre erro "column funcao.admin_id does not exist"
```

### 4. Verificar Integridade Multi-Tenant
```sql
-- Verificar distribuição de admin_id em funcao
SELECT 
    admin_id,
    COUNT(*) as total_funcoes
FROM funcao
GROUP BY admin_id
ORDER BY admin_id;

-- Verificar se há registros órfãos (NULL)
SELECT COUNT(*) as orfaos 
FROM funcao 
WHERE admin_id IS NULL;
-- Deve retornar 0
```

---

## ⚠️ Troubleshooting

### Erro: "órfãos detectados"
**Sintoma:**
```
ERRO: 🔴 departamento: 5 registros órfãos encontrados
MIGRAÇÃO ABORTADA
```

**Solução:**
1. Verificar quais registros são órfãos:
```sql
SELECT * FROM departamento d
WHERE NOT EXISTS (
    SELECT 1 FROM funcionario f WHERE f.departamento_id = d.id
);
```

2. Corrigir manualmente:
   - Deletar registros órfãos OU
   - Associar a um admin válido

3. Re-executar migração (é idempotente)

### Erro: "column admin_id already exists"
**Sintoma:**
```
ERROR: column "admin_id" already exists
```

**Solução:**
Migração já foi executada. Verificar se foi concluída com sucesso:
```sql
SELECT migration_id, status, executed_at 
FROM migration_history 
WHERE migration_id = 48;
```

### Erro: "current transaction is aborted"
**Sintoma:**
```
psycopg2.errors.InFailedSqlTransaction
```

**Solução:**
1. Reiniciar aplicação Easypanel
2. Verificar se migração foi concluída:
```sql
SELECT * FROM migration_history WHERE migration_id = 48;
```

---

## 📊 Checklist de Deploy

- [ ] Backup completo do banco de produção realizado
- [ ] Script migration_48_validation.sql executado
- [ ] Logs de validação revisados
- [ ] Órfãos identificados e corrigidos (se houver)
- [ ] Deploy realizado (Easypanel rebuild)
- [ ] Logs de migração verificados
- [ ] Erro "column funcao.admin_id does not exist" desapareceu
- [ ] Página /funcionarios funcionando normalmente
- [ ] Validação pós-migração executada
- [ ] Sistema estável por 24h

---

## 🔄 Rollback (Emergência)

**⚠️ APENAS EM CASO DE FALHA CRÍTICA**

### Pré-Requisitos
- Backup completo disponível
- Sistema completamente quebrado

### Procedimento
1. **Restaurar backup:**
```bash
psql -h <HOST> -U <USER> -d <DATABASE> < backup_pre_migracao_48_YYYYMMDD_HHMMSS.sql
```

2. **Reverter código:**
```bash
# Fazer rollback do código para versão anterior à migração 48
git revert <commit-hash>
git push
# Rebuild no Easypanel
```

3. **Verificar sistema:**
   - Acessar páginas críticas
   - Confirmar funcionalidade básica

---

## 📞 Contato de Emergência

**Se houver problemas:**
1. Verificar logs detalhados no Easypanel
2. Executar queries de troubleshooting
3. Considerar rollback se sistema crítico

---

## ✅ Conclusão

**Migração 48 é:**
- ✅ Idempotente (pode executar múltiplas vezes)
- ✅ Tenant-aware (preserva isolamento multi-tenant)
- ✅ Auto-validada (detecta problemas antes de commit)
- ✅ Production-ready (aprovada por architect)

**Após deploy bem-sucedido:**
- Sistema voltará a funcionar normalmente
- Erro "column funcao.admin_id does not exist" desaparecerá
- Isolamento multi-tenant estará completo em todas as 20 tabelas
