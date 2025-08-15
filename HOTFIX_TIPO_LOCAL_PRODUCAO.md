# HOTFIX: Erro tipo_local em Produção

## 🚨 ERRO EM PRODUÇÃO
```
DEBUG FUNCIONÁRIOS: 27 funcionários para admin_id=2
psycopg2.errors.UndefinedColumn: column registro_ponto.tipo_local does not exist
LINE 1: ...co_retorno AS registro_ponto_hora_almoco_retorno, registro_p...
```

## ✅ CORREÇÃO APLICADA

### 1. Campo Faltante Identificado
- **Tabela**: `registro_ponto`
- **Campo**: `tipo_local VARCHAR(50)`
- **Erro**: Campo não existe em produção mas é usado no código

### 2. Script Deploy Atualizado
```sql
-- ADICIONAR CAMPO FALTANTE EM REGISTRO_PONTO
ALTER TABLE registro_ponto ADD COLUMN IF NOT EXISTS tipo_local VARCHAR(50) DEFAULT 'obra';
```

### 3. Logs de Produção
- **27 funcionários** detectados com admin_id=2 ✅
- **Sistema funcionando** até encontrar campo faltante
- **Auto-detecção** do admin_id funcionando corretamente

## 🎯 RESULTADO ESPERADO
Após deploy com correção:
1. Campo `tipo_local` será criado automaticamente
2. Sistema funcionará sem erro UndefinedColumn
3. 27 funcionários aparecerão corretamente
4. KPIs serão calculados normalmente

## 🚀 STATUS
- **Deploy Script**: ✅ Atualizado com campo faltante
- **Sistema**: ✅ Detectando dados corretos (admin_id=2)
- **Produção**: 🔄 Aguardando deploy com correção

---
**Data**: 15 de Agosto de 2025 - 11:08 BRT  
**Status**: ✅ CORREÇÃO PRONTA PARA DEPLOY  
**Problema**: Campo tipo_local faltante em registro_ponto