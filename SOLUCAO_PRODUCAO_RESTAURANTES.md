# Solução para Erro do Módulo Restaurantes em Produção

## ✅ IMPLEMENTADO: Diagnóstico Inteligente de Erros

### O que foi feito:
- ✅ Rota `/restaurantes` agora diagnostica problemas automaticamente
- ✅ Rota `/alimentacao` também com diagnóstico detalhado  
- ✅ Template `error_debug.html` criado para mostrar erros específicos
- ✅ Scripts de correção automática prontos

### Como funciona:
Ao invés de mostrar "Internal Server Error", o sistema agora:

1. **Verifica se tabela `restaurante` existe**
2. **Analisa o schema da tabela (colunas)**  
3. **Identifica colunas duplicadas** (`contato_responsavel` vs `responsavel`)
4. **Mostra erro específico com solução**
5. **Exibe scripts para corrigir**

## 🔧 QUANDO ACESSAR EM PRODUÇÃO

### Se o erro for "Tabela não existe":
```
❌ ERRO CRÍTICO: Tabela 'restaurante' não existe no banco de dados
SOLUÇÃO: Execute: CREATE TABLE restaurante (...)
```

### Se o erro for "Colunas faltantes":
```
❌ ERRO DE SCHEMA: Colunas faltantes na tabela restaurante: responsavel, preco_almoco
SOLUÇÃO: Execute: ALTER TABLE restaurante ADD COLUMN responsavel VARCHAR(100);
```

### Se o erro for "Coluna duplicada":
```
❌ ERRO DE SCHEMA: Coluna 'contato_responsavel' duplicada com 'responsavel'  
SOLUÇÃO: Execute: ALTER TABLE restaurante DROP COLUMN contato_responsavel;
```

## 📋 SCRIPTS AUTOMÁTICOS DISPONÍVEIS

Na página de erro, aparecerão 3 opções:

1. **Script Python**:
   ```bash
   cd /app && python fix_restaurante_schema_production.py
   ```

2. **SQL Manual**:
   ```bash
   cd /app && psql $DATABASE_URL -f fix_production_restaurante.sql  
   ```

3. **Via Migração**:
   ```bash
   cd /app && flask db upgrade
   ```

## 🎯 PRÓXIMO PASSO

**Acesse em produção**: `https://sige.cassioviller.tech/restaurantes`

O sistema mostrará **exatamente** qual é o problema e como corrigir!

## ⚡ AUTO-REFRESH

A página de erro faz refresh automático a cada 30 segundos para verificar se foi corrigido.

---

**Status**: ✅ IMPLEMENTADO  
**Testado**: ✅ Local funcionando  
**Produção**: 🔄 Aguardando teste