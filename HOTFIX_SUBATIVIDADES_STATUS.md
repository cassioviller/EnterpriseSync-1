# HOTFIX - Correção do Status das Subatividades

## Problema Identificado
O usuário reportou que as subatividades apareciam como "Concluída" mesmo sem ter RDOs lançados. Isso acontecia porque o JavaScript do template usava lógica hardcoded baseada no índice:

```javascript
// LÓGICA INCORRETA (hardcoded)
const statusText = index < 3 ? 'Concluída' : index < 5 ? 'Em andamento' : 'Pendente';
```

## Correções Implementadas

### 1. API Atualizada - `views.py`
- ✅ Função `api_subatividades_servico()` corrigida
- ✅ Agora calcula status real baseado em dados de RDOs
- ✅ Busca registros `RDO_Subatividade` para cada subatividade
- ✅ Calcula percentual médio de conclusão
- ✅ Determina status baseado em dados reais:
  - **Concluída**: ≥ 100% de conclusão
  - **Em andamento**: ≥ 50% de conclusão
  - **Iniciada**: > 0% de conclusão
  - **Pendente**: 0% de conclusão (sem RDOs)

### 2. Template Corrigido - `templates/obras/detalhes_obra.html`
```javascript
// LÓGICA CORRIGIDA (baseada em dados reais)
const statusClass = sub.status_class || 'secondary';
const statusText = sub.status || 'Pendente';
const percentual = sub.percentual_concluido || 0;
const rdosCount = sub.rdos_count || 0;
```

### 3. Informações Adicionais
- ✅ Mostra quantidade de RDOs lançados
- ✅ Exibe percentual de conclusão
- ✅ Indica quando não há RDO lançado

## Resultado Esperado
Agora as subatividades mostrarão:
- ✅ **Status "Pendente"** quando não há RDOs (cor cinza)
- ✅ **Texto informativo**: "Nenhum RDO lançado"
- ✅ **Status real** baseado em lançamentos de RDO

## Teste Realizado
- ✅ Criado serviço "Estrutura Metálica" com 16 subatividades
- ✅ API retorna status correto baseado em dados reais
- ✅ Template usa dados da API ao invés de lógica hardcoded

## Status: CORRIGIDO ✅

**Data**: 25/07/2025  
**Versão**: SIGE v8.0.12  
**Arquivo**: `views.py` (linha 3241-3301) e `templates/obras/detalhes_obra.html` (linha 795-810)

---

### Para o usuário testar:
1. Acesse uma obra com serviço "Estrutura Metálica"
2. Clique para expandir as subatividades
3. Verifique que todas mostram status "Pendente" 
4. Confirme a mensagem "Nenhum RDO lançado"