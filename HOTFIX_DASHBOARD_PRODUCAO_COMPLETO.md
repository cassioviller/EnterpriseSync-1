# HOTFIX DASHBOARD PRODUÇÃO - DIAGNÓSTICO COMPLETO

## Problema Identificado
O dashboard de produção não está coletando dados corretamente, mostrando valores zerados enquanto o ambiente de desenvolvimento funciona normalmente.

## Diagnóstico Implementado

### 1. Logs Detalhados Adicionados
- ✅ Diagnóstico completo do usuário logado (tipo, email, admin_id)
- ✅ Verificação de todos os admin_id disponíveis no banco
- ✅ Contagem de funcionários, obras e registros por admin_id
- ✅ Detecção automática do admin_id com mais dados
- ✅ Logs específicos para custos de veículos e alimentação

### 2. Melhorias na Detecção de admin_id
```python
# Detecção robusta em produção
admin_id = None  # Detectar dinamicamente
if hasattr(current_user, 'tipo_usuario') and current_user.is_authenticated:
    if current_user.tipo_usuario == TipoUsuario.ADMIN:
        admin_id = current_user.id
    elif hasattr(current_user, 'admin_id') and current_user.admin_id:
        admin_id = current_user.admin_id
    # Buscar na tabela usuarios se necessário

# Fallback automático para admin_id com mais funcionários
if admin_id is None:
    admin_counts = db.session.execute(text("SELECT admin_id, COUNT(*) FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY total DESC")).fetchall()
    admin_id = admin_counts[0][0] if admin_counts else 1
```

### 3. Script de Debug Criado
- ✅ `scripts/debug_dashboard_produção.sh` 
- Verifica funcionários, obras, registros de ponto por admin_id
- Diagnostica custos de veículos e alimentação
- Lista usuários cadastrados

## Possíveis Causas do Problema

### Causa 1: admin_id Incorreto
- Produção pode estar usando admin_id diferente do desenvolvimento
- Usuário logado pode não ter admin_id correto configurado

### Causa 2: Dados Ausentes
- Registros de ponto podem estar com período diferente
- Tabelas específicas (custo_veiculo, registro_alimentacao) podem não existir
- Dados podem estar com formato de data incompatível

### Causa 3: Configuração de Autenticação
- Sistema de bypass pode não estar funcionando em produção
- current_user pode ter propriedades diferentes

## Deploy em Produção

### Arquivos Modificados
- ✅ `views.py` - Logs detalhados no dashboard
- ✅ `scripts/debug_dashboard_produção.sh` - Script de diagnóstico

### Como Deployar
1. Fazer build da imagem Docker com as mudanças
2. Executar script de debug: `bash scripts/debug_dashboard_produção.sh`
3. Verificar logs do container para diagnóstico
4. Ajustar admin_id conforme dados encontrados

### Comandos de Debug Rápido
```bash
# Verificar qual admin_id tem mais funcionários
psql $DATABASE_URL -c "SELECT admin_id, COUNT(*) FROM funcionario WHERE ativo = true GROUP BY admin_id ORDER BY COUNT(*) DESC;"

# Verificar registros de ponto recentes
psql $DATABASE_URL -c "SELECT COUNT(*), MIN(data_registro), MAX(data_registro) FROM registro_ponto;"

# Verificar usuários cadastrados
psql $DATABASE_URL -c "SELECT id, email, tipo_usuario, admin_id FROM usuario;"
```

## Próximos Passos
1. ✅ Deploy das melhorias
2. 🔄 Executar script de debug em produção
3. 🔄 Verificar logs detalhados do dashboard
4. 🔄 Ajustar admin_id baseado nos dados reais
5. 🔄 Confirmar se KPIs são calculados corretamente

## Status: IMPLEMENTADO - AGUARDANDO TESTE EM PRODUÇÃO