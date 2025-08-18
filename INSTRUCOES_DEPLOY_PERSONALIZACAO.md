# INSTRUÇÕES DE DEPLOY - SISTEMA DE PERSONALIZAÇÃO

## 1. PROBLEMA IDENTIFICADO
- ✅ Sistema funciona em desenvolvimento
- ❌ Configurações não aplicam em propostas existentes na produção
- ❌ admin_id pode estar NULL em produção

## 2. CORREÇÕES IMPLEMENTADAS

### 2.1 Fallback Robusto no Código
```python
# Buscar admin_id através do usuário que criou a proposta
admin_id = None
if proposta.criado_por:
    usuario = Usuario.query.get(proposta.criado_por)
    if usuario:
        admin_id = usuario.admin_id or usuario.id  # Se admin_id for null, usa o próprio id

# Fallback: se não conseguir admin_id, usar ID padrão
if not admin_id:
    admin_id = 10
```

### 2.2 Script de Migração para Produção
Execute no ambiente de produção:
```bash
python script_migracao_producao.py
```

### 2.3 Comandos SQL Diretos (Alternativa)
Execute diretamente no banco de produção:
```sql
-- 1. Corrigir admin_id de usuários administradores
UPDATE usuario 
SET admin_id = id 
WHERE tipo_usuario IN ('admin', 'super_admin') 
AND admin_id IS NULL;

-- 2. Verificar configurações da empresa
SELECT admin_id, nome_empresa, cor_primaria, cor_secundaria 
FROM configuracao_empresa;

-- 3. Se não existir configuração, criar uma:
INSERT INTO configuracao_empresa 
(admin_id, nome_empresa, cnpj, cor_primaria, cor_secundaria, cor_fundo_proposta)
VALUES 
(10, 'Estruturas do Vale', '00.000.000/0001-00', '#008B3A', '#FFA500', '#F0F8FF')
ON CONFLICT (admin_id) DO NOTHING;
```

## 3. VERIFICAÇÃO DO FUNCIONAMENTO

### 3.1 Teste Local (Desenvolvimento)
- ✅ Funcionando corretamente
- ✅ Cores aplicadas: verde/laranja
- ✅ Nome da empresa personalizado

### 3.2 Teste Produção
Acesse com tokens válidos:
```
/propostas/cliente/qqmzTc7MhGdxtCf69GNdbi7BlZa4VbSNMV6AvTiU23A
/propostas/cliente/UfpoaiLdWhbI_PYJpUQ_UFN4-M8SSimtyNW5EYG4lOg
```

### 3.3 Sinais de Sucesso
- Fundo em gradiente com cores personalizadas
- Nome da empresa no cabeçalho
- Logo personalizada (se configurada)
- Cores aplicadas nos elementos (títulos, botões)

## 4. DEPLOY SEGURO

### 4.1 Backup Antes do Deploy
```bash
# Backup do banco antes das alterações
pg_dump $DATABASE_URL > backup_antes_personalizacao.sql
```

### 4.2 Deploy das Alterações
1. Fazer push do código atualizado
2. Executar script de migração
3. Testar portal do cliente
4. Verificar todas as propostas existentes

### 4.3 Rollback (Se Necessário)
```bash
# Restaurar backup se algo der errado
psql $DATABASE_URL < backup_antes_personalizacao.sql
```

## 5. ARQUIVOS MODIFICADOS

- `propostas_views.py` - Rota portal_cliente com fallbacks
- `templates/propostas/portal_cliente.html` - Template com personalização
- `script_migracao_producao.py` - Script de migração
- `migrations.py` - Migrações automáticas das colunas

## 6. STATUS FINAL

- ✅ Sistema de personalização completo
- ✅ Fallbacks implementados para produção
- ✅ Script de migração criado
- ✅ Documentação completa
- 🔄 Aguardando deploy em produção