# GUIA DE DEPLOY COM DOCKER - SIGE v8.0

## 🔌 **Configuração de Rede e Portas**

### PostgreSQL
- **Porta:** 5432 (padrão PostgreSQL)
- **String de Conexão:** `postgres://sige:sige@viajey_sige:5432/sige?sslmode=disable`
- **Host:** viajey_sige (nome do container/serviço)

### Aplicação SIGE
- **Porta:** 5000 (Gunicorn/Flask)
- **Health Check:** `/api/monitoring/health`
- **Métricas:** `/api/monitoring/metrics`

## 📦 **Arquivos Docker Criados**

### 1. Dockerfile
- Imagem base: `python:3.11-slim-buster`
- Usuário não-root para segurança
- Dependências otimizadas com cache
- Health check integrado
- Configurações de produção

### 2. docker-entrypoint.sh
- Aguarda PostgreSQL estar disponível
- Cria/atualiza estrutura do banco
- Inicia Gunicorn com configurações otimizadas
- 4 workers, timeout 30s, logs estruturados

### 3. docker-compose.yml
- PostgreSQL 15 Alpine (leve e eficiente)
- Volumes persistentes para dados
- Network isolada
- Health checks para ambos serviços
- Otimizações aplicadas automaticamente

### 4. .dockerignore
- Exclui arquivos de desenvolvimento
- Remove relatórios e scripts de teste
- Otimiza tamanho da imagem final

## 🚀 **Deploy no EasyPanel (Hostinger)**

### Passo 1: Preparar Variáveis de Ambiente
```bash
DATABASE_URL=postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable
SECRET_KEY=sua-chave-super-secreta-producao-128-chars
SESSION_SECRET=sua-chave-sessao-secreta-producao
FLASK_ENV=production
PORT=5000
```

### Passo 2: Build da Imagem
```bash
# Build local (teste)
docker build -t sige:v8.0 .

# Build para produção
docker build --platform linux/amd64 -t sige:v8.0-prod .
```

### Passo 3: Deploy no EasyPanel
1. **Upload do Dockerfile** para o repositório
2. **Configurar variáveis** no painel do EasyPanel
3. **Configurar rede** para conectar ao PostgreSQL
4. **Exposição da porta** 5000
5. **Health check** em `/api/monitoring/health`

## 🧪 **Teste Local**

### Usando Docker Compose
```bash
# Iniciar todos os serviços
docker-compose up -d

# Verificar logs
docker-compose logs -f sige

# Verificar saúde
curl http://localhost:5000/api/monitoring/health

# Parar serviços
docker-compose down
```

### Usando Docker Manual
```bash
# 1. Iniciar PostgreSQL
docker run -d \
  --name sige_postgres \
  -e POSTGRES_DB=sige \
  -e POSTGRES_USER=sige \
  -e POSTGRES_PASSWORD=sige \
  -p 5432:5432 \
  postgres:15-alpine

# 2. Build da aplicação
docker build -t sige:v8.0 .

# 3. Iniciar aplicação
docker run -d \
  --name sige_app \
  --link sige_postgres:viajey_sige \
  -e DATABASE_URL=postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable \
  -p 5000:5000 \
  sige:v8.0
```

## 📊 **Monitoramento**

### Health Checks Disponíveis
- **Aplicação:** `http://localhost:5000/api/monitoring/health`
- **Métricas:** `http://localhost:5000/api/monitoring/metrics`
- **Status:** `http://localhost:5000/api/monitoring/status`

### Logs Estruturados
```bash
# Ver logs da aplicação
docker logs -f sige_app

# Ver logs do banco
docker logs -f sige_postgres
```

## 🔧 **Configurações de Produção**

### Gunicorn Workers
- **Workers:** 4 (ajustável conforme CPU)
- **Timeout:** 30 segundos
- **Max Requests:** 1000 (reinicia worker automaticamente)
- **Keep Alive:** 2 segundos

### PostgreSQL Otimizado
- **Pool Size:** 20 conexões
- **Pool Recycle:** 3600 segundos
- **Índices:** Aplicados automaticamente
- **Views otimizadas:** Para consultas frequentes

### Segurança
- **Usuário não-root** no container
- **SSL mode disable** (para rede interna segura)
- **Variables de ambiente** para secrets
- **Health checks** para alta disponibilidade

## 🔄 **Atualizações e Rollback**

### Deploy de Nova Versão
```bash
# 1. Build nova versão
docker build -t sige:v8.1 .

# 2. Parar versão atual
docker stop sige_app

# 3. Backup do banco
docker exec sige_postgres pg_dump -U sige sige > backup_$(date +%Y%m%d).sql

# 4. Iniciar nova versão
docker run -d --name sige_app_new [configurações...] sige:v8.1
```

### Rollback
```bash
# 1. Parar versão nova
docker stop sige_app_new

# 2. Restaurar versão anterior
docker start sige_app

# 3. Verificar saúde
curl http://localhost:5000/api/monitoring/health
```

## 📋 **Checklist de Deploy**

- [ ] Variáveis de ambiente configuradas
- [ ] PostgreSQL disponível na porta 5432
- [ ] Dockerfile revisado e testado
- [ ] Health checks funcionando
- [ ] Logs estruturados habilitados
- [ ] Backup de dados realizado
- [ ] Monitoramento configurado
- [ ] SSL/HTTPS configurado no proxy reverso
- [ ] Domínio apontando corretamente

## 🆘 **Solução de Problemas**

### Erro de Conexão com Banco
```bash
# Verificar se PostgreSQL está rodando
docker ps | grep postgres

# Testar conexão manual
docker exec -it sige_postgres psql -U sige -d sige -c "SELECT 1;"
```

### Erro 500 na Aplicação
```bash
# Ver logs detalhados
docker logs sige_app | tail -50

# Entrar no container para debug
docker exec -it sige_app bash
```

### Performance Lenta
```bash
# Verificar recursos
docker stats sige_app

# Verificar queries SQL lentas
# (configurado para log > 1 segundo)
```

---

**SIGE v8.0 - Sistema Integrado de Gestão Empresarial**  
**Docker configurado para produção com PostgreSQL na porta 5432**