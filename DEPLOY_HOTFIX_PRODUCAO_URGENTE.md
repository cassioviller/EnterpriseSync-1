# 🚨 HOTFIX PRODUÇÃO URGENTE - Interface RDO Moderna

## Problema Identificado
- **Produção:** Interface RDO antiga (lista de funcionários) 
- **Desenvolvimento:** Interface RDO moderna (subatividades)
- **Conexão PostgreSQL:** Instável em produção

## Solução Implementada

### 1. Dockerfile Corrigido
```dockerfile
# Dockerfile.producao-corrigido
- Health check robusto
- Verificação PostgreSQL automática  
- Timeout aumentado para 120s
- Workers otimizados para produção
```

### 2. Script de Deploy Automático
```bash
# deploy-producao-corrigido.sh
- Para container atual
- Build imagem corrigida
- Deploy com health check
- Verificação automática
```

## Instruções de Deploy

### Passo 1: Configurar Variáveis de Ambiente
```bash
export DATABASE_URL='postgresql://usuario:senha@host:5432/database'
export SESSION_SECRET='sua-chave-secreta-segura'
export PGHOST='seu-host-postgresql'
export PGUSER='seu-usuario'  
export PGPASSWORD='sua-senha'
export PGDATABASE='sua-database'
```

### Passo 2: Executar Deploy
```bash
# No servidor de produção
./deploy-producao-corrigido.sh
```

### Passo 3: Verificar Status
```bash
# Verificar container
docker ps | grep sige-producao

# Verificar logs
docker logs -f sige-producao

# Teste manual
curl http://localhost:5000/health
```

## Verificações Pós-Deploy

### ✅ Interface RDO Moderna
- Acessar: `/funcionario/rdo/novo`
- Verificar: Subatividades em vez de funcionários
- Testar: Botão "Testar Último RDO"

### ✅ Conectividade Database
- Health check: `/health`
- Logs sem erros PostgreSQL
- Transações funcionando

### ✅ Performance
- Workers: 2 (otimizado)
- Timeout: 120s
- Restart: unless-stopped

## Rollback (Se Necessário)

```bash
# Parar nova versão
docker stop sige-producao
docker rm sige-producao

# Voltar versão anterior (substituir por sua imagem anterior)
docker run -d --name sige-producao -p 5000:5000 sige:versao-anterior
```

## Monitoramento

```bash
# Logs em tempo real
docker logs -f sige-producao

# Status do container
docker stats sige-producao

# Health check manual
curl -I http://localhost:5000/health
```

## Resultado Esperado

- ✅ Interface RDO moderna em produção
- ✅ PostgreSQL conectando corretamente  
- ✅ Subatividades funcionando
- ✅ Deploy zero-downtime
- ✅ Health check passando

---

**Data:** 29/08/2025  
**Urgência:** Alta  
**Impacto:** Crítico - Interface inconsistente entre ambientes  
**Solução:** Deploy automatizado com verificações robustas