# SIGE v8.0 - Guia de Deploy Unificado

## Visão Geral

Este guia descreve o sistema de deploy unificado do SIGE v8.0, que garante consistência total entre desenvolvimento e produção.

## Arquivos de Deploy

### 1. `Dockerfile.unified`
- **Propósito**: Dockerfile único para dev e produção
- **Benefícios**: Elimina divergências entre ambientes
- **Features**: 
  - Multi-stage build otimizado
  - Security hardening
  - Health checks robustos
  - Suporte completo a todos os módulos

### 2. `docker-entrypoint-unified.sh`
- **Propósito**: Script de inicialização inteligente
- **Features**:
  - Detecção automática de ambiente
  - Verificação de dependências
  - Migrações automáticas
  - Validação de templates e rotas

### 3. `docker-compose.unificado.yml`
- **Propósito**: Orquestração completa dos serviços
- **Serviços**:
  - PostgreSQL com persistência
  - Aplicação SIGE
  - Redis (opcional)
- **Volumes persistentes** para dados críticos

### 4. `deploy-script.sh`
- **Propósito**: Automação completa do deploy
- **Features**:
  - Verificação de pré-requisitos
  - Testes de consistência
  - Deploy zero-downtime
  - Validação pós-deploy

## Como Usar

### Deploy Rápido (Produção)
```bash
chmod +x deploy-script.sh
./deploy-script.sh
```

### Deploy em Desenvolvimento
```bash
AMBIENTE=development ./deploy-script.sh
```

### Deploy Manual (Passo a Passo)
```bash
# 1. Verificar consistência
python verificar_consistencia.py

# 2. Build
docker build -f Dockerfile.unified -t sige:latest .

# 3. Deploy
docker-compose -f docker-compose.unificado.yml up -d
```

## Variáveis de Ambiente

### Essenciais
- `DATABASE_URL`: URL de conexão PostgreSQL
- `SESSION_SECRET`: Chave secreta do Flask
- `FLASK_ENV`: production/development

### Opcionais
- `PORT`: Porta da aplicação (padrão: 5000)
- `TZ`: Timezone (padrão: America/Sao_Paulo)
- `LIMPAR_IMAGENS`: true para limpar imagens antigas

## Estrutura de Arquivos Críticos

```
SIGE/
├── Dockerfile.unified              # Dockerfile unificado
├── docker-entrypoint-unified.sh   # Script de entrada
├── docker-compose.unificado.yml   # Orquestração
├── deploy-script.sh              # Automação de deploy
├── verificar_consistencia.py     # Testes de consistência
├── main.py                       # Entrada da aplicação
├── app.py                        # Configuração Flask
├── models.py                     # Modelos de dados
├── views.py                      # Rotas e lógica
├── templates/
│   ├── base_completo.html        # Template base unificado
│   ├── dashboard.html            # Dashboard principal
│   ├── funcionarios.html         # Gestão funcionários
│   └── rdo/novo.html            # Formulário RDO
└── static/
    ├── css/app.css              # CSS unificado
    ├── js/app.js                # JavaScript principal
    └── js/charts.js             # Gráficos e dashboards
```

## Verificações de Consistência

O script `verificar_consistencia.py` testa:
- ✅ Presença de templates essenciais
- ✅ Funcionamento de rotas críticas
- ✅ Registro de blueprints
- ✅ Arquivos estáticos
- ✅ Modelos de banco de dados
- ✅ Funcionalidades RDO

## Troubleshooting

### Erro: Template não encontrado
```bash
# Verificar se todos os templates existem
find templates -name "*.html" | wc -l
```

### Erro: Rota não encontrada
```bash
# Testar rotas críticas
python verificar_consistencia.py
```

### Erro: Conexão com banco
```bash
# Verificar status do PostgreSQL
docker-compose -f docker-compose.unificado.yml exec postgres pg_isready
```

### Erro: Health check falhando
```bash
# Ver logs detalhados
docker-compose -f docker-compose.unificado.yml logs sige
```

## Manutenção

### Backup do Banco
```bash
docker-compose -f docker-compose.unificado.yml exec postgres \
    pg_dump -U postgres sige > backup.sql
```

### Restaurar Backup
```bash
cat backup.sql | docker-compose -f docker-compose.unificado.yml exec -T postgres \
    psql -U postgres sige
```

### Logs da Aplicação
```bash
# Logs em tempo real
docker-compose -f docker-compose.unificado.yml logs -f sige

# Logs dos últimos 100 registros
docker-compose -f docker-compose.unificado.yml logs --tail=100 sige
```

### Monitoramento
- **Health Check**: http://localhost:5000/health
- **Métricas**: Disponíveis no dashboard
- **Logs**: Persistidos em volume Docker

## Performance

### Configurações Recomendadas

**Desenvolvimento:**
- 1 worker Gunicorn
- Debug habilitado
- Reload automático

**Produção:**
- 2+ workers Gunicorn
- Debug desabilitado
- Cache habilitado
- SSL/TLS configurado

## Segurança

### Implementado
- ✅ Usuário não-root no container
- ✅ Health checks robustos
- ✅ Variáveis sensíveis via environment
- ✅ Validação de entrada
- ✅ CSRF protection

### Recomendações Adicionais
- Use HTTPS em produção
- Configure firewall apropriado
- Monitore logs de segurança
- Atualize dependências regularmente

## Suporte

Para problemas ou dúvidas:
1. Verificar logs: `docker-compose logs`
2. Executar verificação: `python verificar_consistencia.py`
3. Consultar este guia
4. Contatar equipe de desenvolvimento

---

**SIGE v8.0** - Sistema Integrado de Gestão Empresarial
*Deploy unificado e confiável para todos os ambientes*