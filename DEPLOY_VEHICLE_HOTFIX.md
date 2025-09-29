# 🚨 DEPLOY VEÍCULO HOTFIX - PRODUÇÃO

## PROBLEMA
Sistema de cadastro de veículos falhando em produção devido a colunas faltantes na tabela `veiculo`:
```
column veiculo.chassi does not exist
```

## SOLUÇÃO
Script de migração automática que adiciona as colunas faltantes de forma segura.

## ⚡ DEPLOY RÁPIDO

### 1. Upload do Script
```bash
# Upload o arquivo migrations_veiculo_hotfix_production.py para seu servidor
```

### 2. Executar Hotfix
```bash
# No seu servidor de produção:
cd /caminho/para/seu/projeto
python migrations_veiculo_hotfix_production.py --force
```

### 3. Verificar Resultado
O script irá mostrar:
- ✅ `MIGRATION CONCLUÍDA COM SUCESSO!` - Hotfix aplicado
- ✅ `TODAS AS COLUNAS JÁ EXISTEM` - Sistema já corrigido

## 🔒 GARANTIAS DE SEGURANÇA

✅ **Transação Segura** - Rollback automático em caso de erro  
✅ **Preserva Dados** - Zero risco de perda de dados existentes  
✅ **Detecta Estado** - Só adiciona colunas que realmente faltam  
✅ **Log Completo** - Registro detalhado de todas as operações  
✅ **Testado** - Validado em ambiente de desenvolvimento  

## 📋 COLUNAS ADICIONADAS

O script adiciona automaticamente (se faltando):

| Coluna | Tipo | Padrão | Descrição |
|--------|------|---------|-----------|
| `chassi` | VARCHAR(50) | NULL | Chassi do veículo |
| `renavam` | VARCHAR(20) | NULL | Código RENAVAM |
| `combustivel` | VARCHAR(20) | 'Gasolina' | Tipo de combustível |
| `data_ultima_manutencao` | DATE | NULL | Data última manutenção |
| `data_proxima_manutencao` | DATE | NULL | Data próxima manutenção |
| `km_proxima_manutencao` | INTEGER | NULL | KM próxima manutenção |
| `created_at` | TIMESTAMP | CURRENT_TIMESTAMP | Data criação |
| `updated_at` | TIMESTAMP | CURRENT_TIMESTAMP | Data atualização |

## ⏱️ TEMPO ESTIMADO
- **Execução**: 10-30 segundos
- **Downtime**: Zero (operação não-destrutiva)

## 🔄 ROLLBACK
Se houver problema, o script automaticamente:
1. Detecta o erro
2. Executa ROLLBACK da transação
3. Restaura o banco ao estado anterior
4. Registra o erro nos logs

## 📞 SUPORTE
Após executar, verifique se o cadastro de veículos está funcionando normalmente.

---
**Status**: ✅ PRONTO PARA PRODUÇÃO  
**Testado**: ✅ Desenvolvimento  
**Segurança**: ✅ Transaction-safe  