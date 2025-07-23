# DEPLOY NO EASYPANEL - SIGE v8.0

## ✅ **Correção Aplicada**

O erro de build foi corrigido:
- ❌ **Erro:** `python:3.11-slim-buster` (repositórios descontinuados)
- ✅ **Correção:** `python:3.11-slim-bullseye` (versão suportada)
- ✅ **Segurança:** Variáveis sensíveis removidas do Dockerfile
- ✅ **Otimização:** Conexão dinâmica ao PostgreSQL

## 🚀 **Configuração no EasyPanel**

### 1. Variáveis de Ambiente Obrigatórias
Configure no painel do EasyPanel:

```bash
DATABASE_URL=postgresql://sige:sige@viajey_sige:5432/sige?sslmode=disable
SECRET_KEY=sua-chave-super-secreta-producao-minimo-128-caracteres
SESSION_SECRET=sua-chave-sessao-secreta-producao-minimo-64-caracteres
FLASK_ENV=production
PORT=5000
```

### 2. Gerar Chaves Seguras
Execute localmente para gerar chaves:
```bash
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(64))"
python -c "import secrets; print('SESSION_SECRET=' + secrets.token_urlsafe(32))"
```

### 3. Configuração de Rede
- **Porta da Aplicação:** 5000
- **PostgreSQL:** viajey_sige:5432
- **Health Check:** `/api/monitoring/health`

## 📦 **Arquivos do Projeto**

### Dockerfile (Corrigido)
```dockerfile
FROM python:3.11-slim-bullseye
# Sem variáveis sensíveis
# Otimizado para build rápido
# Health check automático
```

### docker-entrypoint.sh
- Aguarda PostgreSQL automaticamente
- Cria tabelas na inicialização
- Conexão dinâmica baseada em DATABASE_URL
- Logs estruturados

## 🔧 **Processo de Deploy**

### 1. Build da Imagem
O EasyPanel executará automaticamente:
```bash
docker build -t easypanel/viajey/sige1 .
```

### 2. Inicialização
O container executará:
1. Aguardar PostgreSQL disponível
2. Criar/atualizar tabelas do banco
3. Iniciar Gunicorn com 4 workers
4. Habilitar health checks

### 3. Verificação
- **URL:** `https://seu-dominio.com`
- **Health:** `https://seu-dominio.com/api/monitoring/health`
- **Login:** Usar credenciais do sistema multi-tenant

## 🏥 **Monitoramento**

### Endpoints Disponíveis
```bash
GET /api/monitoring/health  # Status da aplicação
GET /api/monitoring/metrics # Métricas do sistema
GET /api/monitoring/status  # Status resumido
```

### Resposta Health Check
```json
{
  "status": "healthy",
  "timestamp": "2025-07-23T14:43:01.123Z",
  "version": "8.0",
  "database": "connected"
}
```

## 🔍 **Solução de Problemas**

### Build Failed (404 Not Found)
✅ **Resolvido:** Atualizado para `slim-bullseye`

### Connection Refused (PostgreSQL)
- Verificar `DATABASE_URL` correta
- Confirmar que PostgreSQL está rodando
- Verificar network entre containers

### 500 Internal Server Error
- Verificar logs do container no EasyPanel
- Confirmar variáveis de ambiente definidas
- Testar health check endpoint

### Variáveis de Ambiente
- `SECRET_KEY` e `SESSION_SECRET` são obrigatórias
- `DATABASE_URL` deve apontar para o PostgreSQL correto
- `PORT=5000` deve coincidir com a exposição do container

## 📊 **Especificações Técnicas**

### Recursos Recomendados
- **CPU:** 1-2 vCPUs
- **RAM:** 512MB - 1GB
- **Storage:** 10GB SSD
- **Network:** Conexão com PostgreSQL

### Performance Esperada
- **Startup:** < 60 segundos
- **Health Check:** < 10 segundos
- **Response Time:** < 2 segundos
- **Workers:** 4 Gunicorn workers

### Banco de Dados
- **PostgreSQL:** Porta 5432
- **Pool Size:** 20 conexões
- **Índices:** Aplicados automaticamente
- **Backup:** Via EasyPanel ou manual

## ✅ **Checklist de Deploy**

- [ ] Dockerfile atualizado para `bullseye`
- [ ] Variáveis de ambiente configuradas
- [ ] PostgreSQL disponível na porta 5432
- [ ] Network configurada entre containers
- [ ] Domínio/subdomínio configurado
- [ ] SSL/TLS habilitado
- [ ] Health checks funcionando
- [ ] Backup de dados realizado

---

**SIGE v8.0 pronto para deploy no EasyPanel com PostgreSQL na porta 5432**

**Última atualização:** 23/07/2025 - Build corrigido e otimizado