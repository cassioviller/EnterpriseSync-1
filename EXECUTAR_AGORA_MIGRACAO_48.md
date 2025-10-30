# 🚀 GUIA RÁPIDO: Executar Migração 48 em Produção (Easypanel)

## ⏱️ Tempo Estimado: 5-10 minutos

---

## 📋 PASSO 1: Backup do Banco (OBRIGATÓRIO)

Acesse o console do Easypanel e execute:

```bash
# Conectar ao container
docker exec -it <nome-container-sige> bash

# Fazer backup
pg_dump $DATABASE_URL > /tmp/backup_migracao48_$(date +%Y%m%d_%H%M%S).sql

# Confirmar que backup foi criado
ls -lh /tmp/backup_migracao48_*
```

**✅ Confirmação:** Você deve ver um arquivo `.sql` com tamanho > 0 bytes

---

## 📋 PASSO 2: Validar Estado Atual

Ainda no console do container:

```bash
cd /app  # ou diretório onde está o código
python3 pre_migration_48_check.py
```

**O que esperar:**
```
PRÉ-VALIDAÇÃO MIGRAÇÃO 48 - SIGE
================================================================================
📊 RESUMO GERAL:
- Total de tabelas: 20
- Tabelas com admin_id: ~10  ← Algumas já têm
- Tabelas sem admin_id: ~10  ← Estas precisam da migração
- Admins cadastrados: X

❌ TABELAS PENDENTES (sem admin_id):
1. funcao - X registros
2. departamento - X registros
3. registro_alimentacao - X registros
...

✅ STATUS: PRONTO PARA MIGRAÇÃO
```

---

## 📋 PASSO 3: Executar Migração

### Opção A: Reiniciar via Easypanel UI (RECOMENDADO)

1. Acesse painel do Easypanel
2. Encontre o serviço SIGE
3. Clique em **"Restart"**
4. Aguarde 30-60 segundos

**A migração executa AUTOMATICAMENTE no startup!**

### Opção B: Reiniciar via console

```bash
# Se preferir via comando
supervisorctl restart all
# OU
pkill gunicorn && gunicorn --bind 0.0.0.0:5000 main:app
```

---

## 📋 PASSO 4: Verificar Logs de Sucesso

Monitore os logs em tempo real:

```bash
tail -f /var/log/app.log | grep "Migração 48"
```

**Procure por estas linhas:**

```
INFO:migrations:▶️  Migração 48 (Adicionar admin_id em 17 modelos faltantes) EXECUTANDO...
INFO:migrations:  📝 Adicionando admin_id em departamento...
INFO:migrations:  ✅ departamento: admin_id adicionado (X registros)
INFO:migrations:  📝 Adicionando admin_id em funcao...
INFO:migrations:  ✅ funcao: admin_id adicionado (X registros)
...
INFO:migrations:✅ Migração 48 completada com sucesso
```

**⚠️ SE VER ERRO:**
- **Órfãos detectados:** Significa que há dados sem referência válida
- **AÇÃO:** Restaurar backup e revisar dados manualmente
- **Comando rollback:** `python3 rollback_migration_48.py`

---

## 📋 PASSO 5: Validar que Funcionou

### 5.1 Verificar via Script

```bash
python3 pre_migration_48_check.py
```

**Deve mostrar:**
```
📊 RESUMO GERAL:
- Tabelas com admin_id: 20/20  ← 100%!
- Tabelas sem admin_id: 0

✅ STATUS: MIGRAÇÃO 48 COMPLETA
```

### 5.2 Verificar via Interface Web

1. Acesse: `https://sige.cassiovillar.tech/admin/database-diagnostics`
2. **Deve mostrar:** Progress bar 100% (20/20 tabelas)

### 5.3 Testar Funcionalidades

**Teste 1: RDOs**
- Acesse: `/funcionario/rdo/consolidado`
- **Esperado:** RDOs com porcentagens reais (não mais 0.0%)
- **Esperado:** Atividades, funcionários e horas aparecem corretamente

**Teste 2: Funcionários**
- Acesse: `/funcionarios`
- **Esperado:** Lista carrega sem erros
- **Esperado:** Funções aparecem corretamente (não mais "N/A")

**Teste 3: Obras**
- Acesse: `/detalhes_obra/<id>`
- **Esperado:** Registros de alimentação aparecem

---

## ⚠️ TROUBLESHOOTING

### Problema: "Órfãos detectados"

```
❌ ERRO: X registros órfãos em funcao
```

**Solução:**
1. Restaurar backup: `psql $DATABASE_URL < /tmp/backup_migracao48_*.sql`
2. Revisar dados: Qual admin_id deve ser usado?
3. Corrigir manualmente ou solicitar suporte

### Problema: Migração não executa

**Sintomas:** Logs não mostram "Migração 48 EXECUTANDO"

**Solução:**
1. Verificar se já foi executada antes:
   ```bash
   psql $DATABASE_URL -c "SELECT * FROM migration_history WHERE migration_id = 48;"
   ```
2. Se retornar linha, migração JÁ FOI EXECUTADA ✅
3. Se não retornar nada, reiniciar aplicação novamente

### Problema: Aplicação não inicia após migração

**Sintomas:** Erro 500 ou timeout

**Solução RÁPIDA - Rollback:**
```bash
# Parar aplicação
supervisorctl stop all

# Restaurar backup
psql $DATABASE_URL < /tmp/backup_migracao48_*.sql

# Reiniciar aplicação
supervisorctl start all
```

---

## ✅ CHECKLIST FINAL

Marque conforme completa:

- [ ] Backup criado e verificado
- [ ] Script de validação executado (estado inicial)
- [ ] Aplicação reiniciada (migração executada)
- [ ] Logs verificados (sem erros)
- [ ] Script de validação executado (20/20 tabelas)
- [ ] Dashboard `/admin/database-diagnostics` mostra 100%
- [ ] RDOs mostram porcentagens corretas (não mais 0.0%)
- [ ] Funcionários carregam sem erros
- [ ] Obras carregam sem erros

---

## 📞 SUPORTE

Se encontrar problemas:

1. **Backup existe?** → Rollback é seguro
2. **Logs de erro?** → Copiar e analisar via `/admin/database-diagnostics`
3. **Tudo falhou?** → Restaurar backup e pedir ajuda

**Arquivos de Diagnóstico:**
- Logs principais: `/var/log/app.log`
- Diagnósticos: `/tmp/db_diagnostics.log`
- Backup: `/tmp/backup_migracao48_*.sql`

---

## 🎯 RESUMO

**Antes da Migração:**
- RDOs: 0.0% progresso ❌
- Funcionários: "N/A (erro de schema)" ❌
- Erros nos logs ❌

**Depois da Migração:**
- RDOs: Porcentagens reais ✅
- Funcionários: Funções corretas ✅
- Sem erros ✅

**Tempo total:** 5-10 minutos
**Risco:** Baixo (com backup)
**Complexidade:** Média
