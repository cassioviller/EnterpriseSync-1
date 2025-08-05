# 🚀 SISTEMA DE DEPLOY AUTOMÁTICO - SIGE v8.1

## Visão Geral

Sistema completo de deploy automático que aplica todas as correções de horas extras sem intervenção manual. Inclui validação, backup e relatórios automáticos.

## 🎯 Funcionalidades

### ✅ Deploy Automático Completo
- Aplica correção de horas extras automaticamente
- Valida casos críticos após aplicação
- Gera backup de segurança antes das alterações
- Cria relatórios detalhados do processo

### ✅ Múltiplas Formas de Execução
1. **Script Python**: `auto_deploy_producao.py`
2. **Script Shell**: `deploy_automatico.sh`
3. **Webhook HTTP**: `webhook_deploy.py`

### ✅ Validação Automática
- João Silva Santos 31/07: 0.95h extras ✅
- Ana Paula Rodrigues 29/07: 1.0h extras + 0.3h atrasos ✅
- Verificação de conexão com banco de dados
- Health checks automáticos

## 🚀 Como Usar

### Opção 1: Script Python (Mais Completo)
```bash
# Modo automático (sem interação)
python3 auto_deploy_producao.py --auto

# Modo manual (com confirmação)
python3 auto_deploy_producao.py
```

### Opção 2: Script Shell (Mais Simples)
```bash
# Executar deploy completo
./deploy_automatico.sh
```

### Opção 3: Webhook HTTP (Para Integração)
```bash
# Iniciar servidor webhook
python3 webhook_deploy.py

# Enviar request de deploy
curl -X POST http://localhost:8080/deploy \
  -H "Authorization: Bearer sua_chave_secreta_aqui"

# Verificar status
curl http://localhost:8080/status
```

## 🛡️ Segurança

### Backup Automático
- Criado antes de qualquer alteração
- Log de todos os registros existentes
- Timestamp para identificação

### Validação Rigorosa
- Verificação de ambiente antes do deploy
- Teste de casos críticos após aplicação
- Rollback automático em caso de erro

### Logs Detalhados
- `deploy_producao.log`: Log principal
- `backup_TIMESTAMP.log`: Log do backup
- `relatorio_deploy_TIMESTAMP.md`: Relatório final

## 📊 O Que É Corrigido

### Lógica de Horas Extras Consolidada
- **Horário Padrão**: 07:12 - 17:00 para todos funcionários
- **Tipos Normais**: Extras e atrasos calculados independentemente
- **Tipos Especiais**: Sábado/domingo com todas horas como extras

### Cálculos Específicos
- **Extras**: Entrada antes 07:12 + Saída após 17:00
- **Atrasos**: Entrada após 07:12 + Saída antes 17:00
- **Sábado**: 50% sobre todas as horas trabalhadas
- **Domingo/Feriado**: 100% sobre todas as horas trabalhadas

## 🔧 Configuração em Produção

### Variáveis de Ambiente
```bash
export DATABASE_URL="postgresql://usuario:senha@host:porta/database"
export WEBHOOK_SECRET="sua_chave_secreta_muito_forte"
export WEBHOOK_PORT="8080"
```

### Execução Automática via Cron
```bash
# Executar deploy automático toda madrugada
0 2 * * * cd /caminho/do/projeto && ./deploy_automatico.sh
```

### Integração com CI/CD
```yaml
# Exemplo para GitHub Actions
- name: Deploy Automático
  run: |
    python3 auto_deploy_producao.py --auto
```

## 📈 Monitoramento

### Health Check
```bash
curl http://localhost:8080/health
```

### Status do Webhook
```bash
curl http://localhost:8080/status
```

### Logs em Tempo Real
```bash
tail -f deploy_producao.log
```

## 🚨 Solução de Problemas

### Deploy Falha
1. Verificar logs em `deploy_producao.log`
2. Validar conexão com banco de dados
3. Verificar permissões de escrita
4. Executar health check

### Casos Críticos Falham
1. Verificar se os registros existem no banco
2. Validar horários específicos
3. Confirmar funcionários corretos

### Webhook Não Responde
1. Verificar se porta 8080 está livre
2. Validar token de segurança
3. Verificar logs do webhook

## 📋 Checklist de Deploy

- [ ] ✅ Backup criado automaticamente
- [ ] ✅ Correção de horas extras aplicada
- [ ] ✅ João Silva Santos 31/07 validado (0.95h)
- [ ] ✅ Ana Paula 29/07 validada (1.0h + 0.3h)
- [ ] ✅ Sistema testado e funcional
- [ ] ✅ Relatório de deploy gerado
- [ ] ✅ Logs salvos para auditoria

## 🎉 Resultado Final

Após executar qualquer uma das opções:

1. **Sistema Atualizado**: Todas as correções aplicadas
2. **Casos Validados**: Funcionários específicos corretos
3. **Relatório Gerado**: Documentação completa do processo
4. **Logs Disponíveis**: Para auditoria e debug
5. **Pronto para Uso**: Interface e backend sincronizados

---

**Versão**: SIGE v8.1  
**Data**: Agosto 2025  
**Status**: ✅ PRONTO PARA PRODUÇÃO