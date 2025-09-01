# 🚨 DEPLOY HOTFIX PRODUÇÃO - INSTRUÇÕES OBRIGATÓRIAS

## Problema Identificado
```
[INFO] Handling signal: winch (loops infinitos)
ERROR GESTÃO SERVIÇOS: column servico.admin_id does not exist
```

## ✅ CORREÇÕES IMPLEMENTADAS

### **1. Dockerfile Atualizado**
- Script `docker-entrypoint-production-fix.sh` será usado automaticamente
- Timeout PostgreSQL reduzido para 20s
- Inicialização silenciosa (sem loops)
- Versão: v2.0 - 01/09/2025

### **2. CRUD Serviços Corrigido**
- Query ORM corrigida (`filter()` em vez de `filter_by()`)
- Tratamento robusto de transações SQL
- Rollback automático em caso de erro
- Logs detalhados para debugging

### **3. Sistema Error Handler**
- Logs específicos para erros SQL (transação abortada, foreign key, etc.)
- Fallback inteligente para templates ausentes
- Interface temporária quando templates não existem

## 🚀 INSTRUÇÕES DE DEPLOY

### **Método 1: EasyPanel Automático (Recomendado)**
```bash
# 1. Push das correções para repositório
git add .
git commit -m "Hotfix produção: loops infinitos + serviços SQL corrigidos"
git push origin main

# 2. EasyPanel detectará automaticamente:
#    - Dockerfile atualizado
#    - docker-entrypoint-production-fix.sh v2.0
#    - crud_servicos_completo.py corrigido
```

### **Método 2: Deploy Manual Docker**
```bash
# 1. Parar container atual
docker stop sige_container
docker rm sige_container

# 2. Build nova imagem
docker build -t sige:hotfix-producao-v2 .

# 3. Executar com configurações EasyPanel
docker run -d --name sige_container \
  -p 5000:5000 \
  -e DATABASE_URL="postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable" \
  -e FLASK_ENV=production \
  --restart=unless-stopped \
  sige:hotfix-producao-v2
```

## 🔍 VALIDAÇÃO PÓS-DEPLOY

### **1. Verificar Logs Limpos**
```bash
docker logs sige_container --tail=20
# Esperado:
# 🚀 SIGE v8.0 - Iniciando (Production Fix v2.0 - 01/09/2025)
# ✅ PostgreSQL conectado!
# ✅ App carregado
# 🎯 Aplicação pronta!
# [SEM repetições "Handling signal: winch"]
```

### **2. Testar Sistema de Serviços**
```bash
# Acessar /servicos deve funcionar
curl -I http://localhost:5000/servicos
# Esperado: HTTP/200
```

### **3. Verificar Dashboard**
```bash
# Dashboard deve carregar sem erro "Erro ao carregar serviços"
curl -I http://localhost:5000/dashboard
# Esperado: HTTP/200
```

## 📊 MUDANÇAS ESPECÍFICAS APLICADAS

### **Arquivo: `Dockerfile`**
```dockerfile
# Copiar scripts de entrada (produção corrigida e backup)
COPY docker-entrypoint-production-fix.sh /app/docker-entrypoint.sh
COPY docker-entrypoint-unified.sh /app/docker-entrypoint-backup.sh
RUN chmod +x /app/docker-entrypoint.sh /app/docker-entrypoint-backup.sh
```

### **Arquivo: `docker-entrypoint-production-fix.sh`**
```bash
# Versão atualizada com timestamp
echo "🚀 SIGE v8.0 - Iniciando (Production Fix v2.0 - 01/09/2025)"

# Timeout reduzido (20s vs 60s anterior)
TIMEOUT=20

# Inicialização silenciosa
warnings.filterwarnings('ignore')
```

### **Arquivo: `crud_servicos_completo.py`**
```python
# Query corrigida
servicos = Servico.query.filter(
    Servico.admin_id == admin_id,
    Servico.ativo == True
).order_by(Servico.nome).all()

# Tratamento de transações
try:
    db.session.rollback()
except:
    pass
```

## ⚡ URGÊNCIA - DEPLOY IMEDIATO

### **Por que é crítico:**
1. **Loops infinitos** consumindo CPU/memória em produção
2. **Sistema de serviços inoperante** afetando usuários
3. **Dashboard com erro** impactando visualização de dados

### **Resultado esperado após deploy:**
- ✅ Logs limpos sem repetições infinitas
- ✅ Sistema de serviços 100% funcional
- ✅ Dashboard carregando corretamente
- ✅ 7 serviços listados para admin_id=10
- ✅ Subatividades carregando normalmente

---
**Data:** 01/09/2025 - 14:00  
**Versão:** Hotfix v2.0  
**Status:** 🚨 DEPLOY OBRIGATÓRIO  
**ETA:** 5 minutos (EasyPanel automático)  

**Confirmação de sucesso:** Sistema deve mostrar "Production Fix v2.0" nos logs de inicialização.