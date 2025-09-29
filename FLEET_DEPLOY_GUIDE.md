# 🚀 GUIA DE DEPLOY DO SISTEMA FLEET

## Visão Geral

Este guia documenta o processo completo de deploy do novo sistema FLEET de veículos, que substitui completamente o sistema legacy com uma arquitetura limpa e sem conflitos.

## 📋 O Que Foi Implementado

### ✅ Sistema Completo Reconstruído

1. **NOVO SCHEMA FLEET** (`fleet_models.py`)
   - `fleet_vehicle` - substitui `veiculo`
   - `fleet_vehicle_usage` - substitui `uso_veiculo` 
   - `fleet_vehicle_cost` - substitui `custo_veiculo`
   - Nomes únicos evitam conflitos com sistema legacy

2. **CAMADA DE SERVIÇO** (`fleet_service.py`)
   - FleetService com adapter pattern
   - Interface 100% compatível com frontend
   - Feature flag `FLEET_CUTOVER` para controle

3. **ROTAS REFATORADAS** (`fleet_routes.py`)
   - URLs idênticas mantidas
   - Payloads compatíveis
   - Ativação via feature flag

4. **MIGRAÇÃO ROBUSTA** (`fleet_migration_production.py`)
   - Backup automático
   - Validação completa
   - Rollback em caso de erro

5. **DEPLOY CONTROLADO** (`fleet_deploy_controller.py`)
   - Processo automatizado
   - Testes integrados
   - Relatórios detalhados

## 🎯 Vantagens da Solução

- ✅ **Zero alterações no frontend** - URLs e dados mantidos
- ✅ **Nomes únicos** - sem conflitos com sistema antigo
- ✅ **Migração segura** - backup e rollback garantidos
- ✅ **Feature flag** - ativação controlada
- ✅ **Multi-tenant robusto** - admin_id consistente
- ✅ **Performance otimizada** - índices desde o início

## 🚀 Processo de Deploy

### Pré-requisitos

```bash
# Verificar arquivos necessários
ls fleet_models.py fleet_service.py fleet_routes.py fleet_migration_production.py fleet_deploy_controller.py

# Verificar variáveis de ambiente
echo $DATABASE_URL
echo $FLEET_CUTOVER  # deve estar false ou undefined
```

### Deploy Automatizado

```bash
# Deploy completo automático
python fleet_deploy_controller.py --auto

# Deploy com remoção de tabelas legacy
python fleet_deploy_controller.py --auto --remove-legacy

# Apenas testar sistema atual
python fleet_deploy_controller.py --test-only
```

### Deploy Manual (Produção)

```bash
# 1. Executar migração de dados
python fleet_migration_production.py

# 2. Ativar sistema FLEET
export FLEET_CUTOVER=true
export FLEET_CUTOVER_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# 3. Reiniciar aplicação
systemctl restart your-app
# ou
docker-compose restart

# 4. Validar funcionamento
python fleet_deploy_controller.py --test-only
```

## 🔧 Configuração Via Docker

### docker-compose.yml
```yaml
environment:
  - FLEET_CUTOVER=true
  - FLEET_CUTOVER_TIMESTAMP=2025-09-29T14:00:00Z
  - DATABASE_URL=postgresql://user:pass@host:5432/db
```

### Dockerfile/Entrypoint
```bash
# Adicionar ao docker-entrypoint-easypanel-auto.sh
export FLEET_CUTOVER=true
export FLEET_CUTOVER_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

## 🧪 Validação e Testes

### Health Check
```bash
curl http://localhost:5000/health
curl http://localhost:5000/api/fleet/status
```

### Testes Funcionais
```bash
# Testar cadastro de veículo
curl -X POST http://localhost:5000/veiculos/novo \
  -d "placa=ABC1234&marca=Ford&modelo=Ranger&ano=2020&tipo=Utilitário"

# Testar listagem
curl http://localhost:5000/veiculos
```

## 🔄 Rollback em Caso de Problemas

### Reversão Rápida
```bash
# Desativar FLEET
export FLEET_CUTOVER=false
unset FLEET_CUTOVER_TIMESTAMP

# Reiniciar aplicação
systemctl restart your-app
```

### Restaurar Backup (Se Necessário)
```bash
# Encontrar arquivo de backup
ls fleet_backup_*.json

# Restaurar dados (implementar se necessário)
python restore_from_backup.py fleet_backup_20250929_140000.json
```

## 📊 Monitoramento

### Logs Importantes
```bash
# Logs de deploy
tail -f fleet_deploy.log

# Logs da aplicação
tail -f /var/log/your-app/app.log | grep -i fleet

# Logs de migração
tail -f fleet_migration.log
```

### Métricas de Validação
- Contagem de registros migrados
- Tempo de resposta das APIs
- Integridade referencial
- Erros de sistema

## 🚨 Troubleshooting

### Sistema FLEET Não Ativa
```bash
# Verificar variável de ambiente
echo $FLEET_CUTOVER

# Verificar logs de inicialização
grep -i "fleet" /var/log/app.log

# Verificar imports
python -c "from fleet_models import FleetVehicle; print('OK')"
```

### Dados Não Migrados
```bash
# Executar migração manualmente
python fleet_migration_production.py --force

# Verificar contadores
python -c "
from app import app, db
from fleet_models import FleetVehicle
with app.app_context():
    print(f'FLEET Vehicles: {FleetVehicle.query.count()}')
"
```

### Frontend Não Funcionando
```bash
# Verificar se URLs são idênticas
curl -I http://localhost:5000/veiculos

# Verificar formato de dados
curl http://localhost:5000/api/veiculos/1

# Verificar logs do browser
# Deve mostrar dados normalmente
```

## 📋 Checklist Final

### ✅ Deploy Bem-sucedido
- [ ] Migração executada sem erros
- [ ] FLEET_CUTOVER=true ativo
- [ ] Aplicação reiniciada
- [ ] Health checks passando
- [ ] Frontend funcionando normalmente
- [ ] Dados migrados corretamente
- [ ] Logs sem erros críticos

### 🎯 Próximos Passos (Opcional)
- [ ] Remover tabelas legacy após 1 semana
- [ ] Remover scripts de migração
- [ ] Atualizar documentação do sistema
- [ ] Treinar equipe no novo sistema

## 📞 Suporte

Em caso de problemas:
1. Verificar logs detalhados
2. Executar troubleshooting
3. Fazer rollback se necessário
4. Contatar equipe de desenvolvimento

---

**🎉 Sucesso!** O sistema FLEET está agora ativo e funcionando sem conflitos!