# 🔧 DEPLOY CORREÇÃO TIPOS VEÍCULOS - PRODUÇÃO

## 🎯 Problema Resolvido
**Erro:** `operator does not exist: character varying = integer`  
**Causa:** Campos `veiculo_id` sendo tratados como string em vez de integer  
**Solução:** Conversão automática de tipos + alteração da estrutura da tabela

---

## 🚀 Deploy via Dockerfile (EasyPanel/Hostinger)

### ✅ Arquivos Criados/Modificados:
1. **`fix_type_error_veiculos_production.py`** - Script de correção automática
2. **`docker-entrypoint-easypanel-auto.sh`** - Entrypoint atualizado
3. **`Dockerfile`** - Configurado para usar entrypoint automático
4. **`vehicle_usage_service.py`** - Validação de tipos corrigida

### 📋 Instruções de Deploy:

#### 1. **Build da Nova Imagem Docker:**
```bash
docker build -t sige:v10.1-fix-tipos .
```

#### 2. **Deploy no EasyPanel/Hostinger:**
```bash
# Fazer backup do banco antes do deploy
# O sistema fará backup automático, mas é recomendado manual também

# Deploy da nova versão
docker stop sige-container
docker run -d \
  --name sige-container \
  --env DATABASE_URL="postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable" \
  --env FORCE_TYPE_FIX=1 \
  -p 5000:5000 \
  sige:v10.1-fix-tipos
```

#### 3. **Variáveis de Ambiente (Opcionais):**
```bash
FORCE_TYPE_FIX=1          # Força execução da correção
ENABLE_ROLLBACK=true      # Ativa rollback automático em caso de erro
MIGRATION_TIMEOUT=300     # Timeout para migrações (5 min)
```

---

## 🔍 Monitoramento do Deploy

### **Logs Importantes:**
```bash
# Log principal do deploy
docker logs sige-container | grep "FIX-TYPES"

# Log específico da correção
docker exec sige-container cat /tmp/fix_types_veiculos.log

# Health check pós-correção
docker exec sige-container cat /tmp/health_check_result.json
```

### **Verificações Pós-Deploy:**
1. ✅ **Sistema iniciou sem erros**
2. ✅ **Páginas de veículos carregam**
3. ✅ **Detalhes de uso funcionando**
4. ✅ **Logs mostram "CORREÇÃO DE TIPOS CONCLUÍDA"**

---

## 🛠️ O Que a Correção Faz

### **Automática durante o Deploy:**
1. **Analisa estrutura das tabelas** críticas de veículos
2. **Detecta campos** com tipo incorreto (`character varying` vs `integer`)
3. **Converte dados** existentes de forma segura
4. **Altera estrutura** das tabelas (`ALTER TABLE`)
5. **Recria índices** otimizados
6. **Valida funcionamento** com testes

### **Tabelas Corrigidas:**
- `veiculo`: `id`, `admin_id`
- `uso_veiculo`: `id`, `veiculo_id`, `funcionario_id`, `admin_id`
- `custo_veiculo`: `id`, `veiculo_id`, `admin_id`  
- `passageiro_veiculo`: `id`, `uso_veiculo_id`, `funcionario_id`, `admin_id`

---

## 🚨 Plano de Rollback

### **Se algo der errado:**
```bash
# 1. Parar container atual
docker stop sige-container

# 2. Voltar versão anterior
docker run -d \
  --name sige-container \
  --env DATABASE_URL="postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable" \
  -p 5000:5000 \
  sige:v10.0-estavel

# 3. Restaurar backup do banco (se necessário)
```

### **Backup Automático:**
- Sistema cria backup antes de aplicar correções
- Logs indicam localização do backup
- Rollback automático em caso de erro crítico

---

## ✅ Resultado Esperado

**Antes:** Erro `character varying = integer` ao acessar detalhes de veículos  
**Depois:** 
- ✅ Páginas carregam sem erro
- ✅ Filtros funcionam
- ✅ Consultas SQL otimizadas
- ✅ Performance melhorada

---

## 📞 Suporte

**Logs para Debug:**
- `/tmp/fix_types_veiculos.log` - Log da correção
- `/tmp/sige_deployment.log` - Log do deploy
- `/tmp/health_check_result.json` - Status final

**Status esperado:** `"status": "healthy"` ou `"status": "warning"`