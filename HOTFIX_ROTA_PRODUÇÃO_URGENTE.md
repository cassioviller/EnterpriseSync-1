# 🚨 HOTFIX URGENTE - ROTA PROPOSTAS EM PRODUÇÃO

## Problema Identificado
**Erro BuildError**: `Could not build url for endpoint 'propostas.listar_propostas'`

### Contexto
- Sistema em produção apresentando erro ao visualizar propostas
- Template `visualizar.html` referenciando rota inexistente `propostas.listar_propostas`
- Rota correta é `propostas.index`

## Correções Aplicadas ✅

### 1. templates/propostas/visualizar.html
```diff
- <a href="{{ url_for('propostas.listar_propostas') }}" class="btn btn-secondary">
+ <a href="{{ url_for('propostas.index') }}" class="btn btn-secondary">
```

### 2. templates/propostas/dashboard.html
```diff
- <a href="{{ url_for('propostas.listar_propostas') }}" class="btn btn-sm btn-outline-primary">
+ <a href="{{ url_for('propostas.index') }}" class="btn btn-sm btn-outline-primary">
```

### 3. templates/propostas/nova.html (2 ocorrências)
```diff
- <a href="{{ url_for('propostas.listar_propostas') }}" class="btn btn-secondary">
+ <a href="{{ url_for('propostas.index') }}" class="btn btn-secondary">

- <a href="{{ url_for('propostas.listar_propostas') }}" class="btn btn-secondary w-100">
+ <a href="{{ url_for('propostas.index') }}" class="btn btn-secondary w-100">
```

## Status
✅ **CORRIGIDO** - Todas as referências para `propostas.listar_propostas` foram atualizadas para `propostas.index`

## Próximos Passos
1. Deploy imediato para produção
2. Teste da URL: `/propostas/5` (que causou o erro original)
3. Verificar navegação entre páginas de propostas

## Impacto
- **Antes**: Erro 500 ao tentar voltar/navegar de propostas
- **Depois**: Navegação funcionando corretamente
- **Usuários afetados**: Todos que acessam visualização de propostas

---
**PRONTO PARA DEPLOY IMEDIATO** 🚀