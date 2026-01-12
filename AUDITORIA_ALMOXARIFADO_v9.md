# RELATÓRIO DE AUDITORIA TÉCNICA: MÓDULO DE ALMOXARIFADO - SIGE v9.0

**Data da Auditoria:** 12 de Janeiro de 2026  
**Auditor:** Engenheiro de QA Sênior (Replit Agent)  
**Versão do Sistema:** SIGE v9.0

---

## 1. SUMÁRIO EXECUTIVO

O módulo de Almoxarifado do SIGE v9.0 foi analisado em profundidade, revelando **18 bugs/problemas significativos**:

| Severidade | Quantidade |
|------------|------------|
| CRÍTICO    | 4          |
| ALTO       | 5          |
| MÉDIO      | 6          |
| BAIXO      | 3          |

**Avaliação Geral:** O módulo está **funcionalmente operacional** com boa cobertura multi-tenant, mas apresenta falhas críticas que podem causar crashes em produção e vulnerabilidades de segurança. **Recomendação: APROVADO COM RESSALVAS** - correção obrigatória dos bugs críticos e de segurança antes de uso extensivo.

**Pontos Fortes:**
- Isolamento multi-tenant (admin_id) consistente em todas as rotas
- SQL parametrizado em queries raw
- Tratamento de erros com rollback na maioria das operações
- Templates usando base_completo.html consistentemente (20/20)

**Pontos Críticos:**
- Filtro em campo inexistente causa crash (BUG #003)
- Ausência total de CSRF protection em formulários
- N+1 queries em dashboard e listagens
- Dados FIFO incompletos em devoluções

---

## 2. ARQUIVOS ANALISADOS

### Código Python:
- `almoxarifado_views.py` (3305 linhas): Blueprint principal com todas as rotas
- `almoxarifado_utils.py`: Utilitários auxiliares
- `models.py` (linhas 3743-3869): Modelos de dados

### Modelos de Dados:
- `AlmoxarifadoCategoria` (linha 3743)
- `AlmoxarifadoItem` (linha 3762)
- `AlmoxarifadoEstoque` (linha 3788)
- `AlmoxarifadoMovimento` (linha 3828)
- `Fornecedor` (linha 1321)

### Templates (20 arquivos):
- `dashboard.html`, `itens.html`, `itens_form.html`, `itens_detalhes.html`
- `itens_movimentacoes.html`, `categorias.html`, `categorias_form.html`
- `entrada.html`, `saida.html`, `devolucao.html`, `movimentacoes.html`
- `movimentacoes_form.html`, `fornecedores.html`, `fornecedores_form.html`
- `relatorios.html`, `scanner.html`, `notas_fiscais.html`, `importar_xml.html`
- `lista_materiais.html`, `produtos.html`

### Migrações Relacionadas:
- Migração 39: Sistema de Almoxarifado v3.0
- Migração 47: Integração Fornecedor-Financeiro
- Migração 57: Campos CRUD movimentações
- Migração 58: Sistema de Rastreamento de Lotes FIFO

---

## 3. BUGS E PROBLEMAS IDENTIFICADOS

### **BUG #001 - [SEVERIDADE: CRÍTICO] - Filtro em Campo Inexistente Causa Crash**

**Descrição:**  
A rota de relatórios filtra `AlmoxarifadoEstoque` pelo campo `ativo=True`, porém este campo **não existe** no modelo `AlmoxarifadoEstoque`.

**Localização:**  
- **Arquivo:** `almoxarifado_views.py`
- **Função:** `relatorios()`
- **Linha:** 2412

**Código Problemático:**
```python
query = AlmoxarifadoEstoque.query.filter_by(admin_id=admin_id, ativo=True)
```

**Impacto:**  
Crash com `AttributeError` ou query SQL inválida ao acessar relatório de posição de estoque.

**Comportamento Esperado:**  
Relatório carrega normalmente.

**Comportamento Atual:**  
Erro 500 ou página em branco.

**Recomendação de Correção:**  
Remover filtro `ativo=True` ou usar campo existente como `status='DISPONIVEL'`.

**Prioridade:** IMEDIATA

---

### **BUG #002 - [SEVERIDADE: CRÍTICO] - Ausência de CSRF Protection em Todos os Formulários**

**Descrição:**  
NENHUM dos formulários POST no módulo de Almoxarifado possui token CSRF (`csrf_token()` ou `form.hidden_tag()`).

**Localização:**  
- **Arquivos:** Todos os templates em `templates/almoxarifado/`
- **Total:** 15+ formulários POST vulneráveis

**Templates Afetados:**
- `itens.html` (linha 163)
- `entrada.html` (linha 26)
- `categorias_form.html` (linha 20)
- `itens_form.html` (linha 20)
- `fornecedores_form.html` (linha 16)
- `categorias.html` (linha 77)
- `fornecedores.html` (linha 124)
- `movimentacoes.html` (linha 411)
- E outros...

**Impacto:**  
Vulnerabilidade CSRF permite que atacantes executem ações não autorizadas em nome de usuários autenticados (exclusão de itens, movimentações falsas, etc.).

**Recomendação de Correção:**  
Adicionar `{{ csrf_token() }}` ou `{{ form.hidden_tag() }}` em todos os formulários POST.

**Prioridade:** IMEDIATA

---

### **BUG #003 - [SEVERIDADE: CRÍTICO] - Dados FIFO Incompletos em Devoluções**

**Descrição:**  
Ao criar registro de estoque em devoluções, os campos FIFO (`quantidade_inicial`, `quantidade_disponivel`, `entrada_movimento_id`) não são preenchidos, quebrando o rastreamento de lotes.

**Localização:**  
- **Arquivo:** `almoxarifado_views.py`
- **Funções:** `processar_devolucao()`, `processar_devolucao_multipla()`
- **Linhas:** 1959-1966, 2248-2256

**Código Problemático:**
```python
estoque = AlmoxarifadoEstoque(
    item_id=item.id,
    quantidade=quantidade_devolvida,
    status='DISPONIVEL',
    # FALTAM: quantidade_inicial, quantidade_disponivel, entrada_movimento_id
)
```

**Impacto:**  
- Queries FIFO retornam resultados incorretos
- Impossível rastrear origem de itens devolvidos
- Relatórios de lotes inconsistentes

**Recomendação de Correção:**  
Adicionar campos FIFO ao criar estoque de devolução:
```python
estoque = AlmoxarifadoEstoque(
    item_id=item.id,
    quantidade=quantidade_devolvida,
    quantidade_inicial=quantidade_devolvida,
    quantidade_disponivel=quantidade_devolvida,
    status='DISPONIVEL',
    admin_id=admin_id
)
db.session.add(estoque)
db.session.flush()
estoque.entrada_movimento_id = movimento.id
```

**Prioridade:** ALTA

---

### **BUG #004 - [SEVERIDADE: CRÍTICO] - ValueError Não Tratado em Conversão de Filtros**

**Descrição:**  
A conversão `int(funcionario_filtro)` pode lançar `ValueError` se o parâmetro contiver valor não numérico.

**Localização:**  
- **Arquivo:** `almoxarifado_views.py`
- **Função:** `itens_movimentacoes()`
- **Linhas:** 501-505

**Código Problemático:**
```python
if funcionario_filtro:
    query = query.filter(AlmoxarifadoMovimento.funcionario_id == int(funcionario_filtro))
```

**Impacto:**  
Erro 500 se usuário manipular URL com valor inválido.

**Recomendação de Correção:**  
```python
if funcionario_filtro:
    try:
        query = query.filter(AlmoxarifadoMovimento.funcionario_id == int(funcionario_filtro))
    except (ValueError, TypeError):
        pass  # Ignora filtro inválido
```

**Prioridade:** ALTA

---

### **BUG #005 - [SEVERIDADE: ALTO] - N+1 Query Problem em Dashboard e Listagens**

**Descrição:**  
O dashboard e listagem de itens executam queries individuais dentro de loops, causando N+1 queries.

**Localização:**  
- **Arquivo:** `almoxarifado_views.py`
- **Funções:** `dashboard()`, `itens()`, `alertas()`
- **Linhas:** 44-66, 296-315, 2668-2692

**Código Problemático:**
```python
for item in itens:
    estoque_atual = AlmoxarifadoEstoque.query.filter_by(item_id=item.id, ...).count()
    # Executa 1 query por item!
```

**Impacto:**  
Com 100 itens: 100+ queries adicionais. Performance degradada significativamente em ambientes com muitos dados.

**Recomendação de Correção:**  
Usar subquery ou eager loading:
```python
from sqlalchemy import func
estoque_por_item = db.session.query(
    AlmoxarifadoEstoque.item_id,
    func.count(AlmoxarifadoEstoque.id).label('total')
).filter_by(admin_id=admin_id, status='DISPONIVEL').group_by(AlmoxarifadoEstoque.item_id).all()
```

**Prioridade:** ALTA

---

### **BUG #006 - [SEVERIDADE: ALTO] - Missing Pagination em Listagens Críticas**

**Descrição:**  
Rotas de listagem carregam TODOS os registros sem paginação.

**Localização:**  
- **Arquivo:** `almoxarifado_views.py`
- **Funções:** `movimentacoes()`, `itens_movimentacoes()`
- **Linhas:** 524, 2508, 2634

**Código Problemático:**
```python
movimentos = query.order_by(...).all()  # Carrega TUDO
```

**Impacto:**  
- Memory overflow com muitos registros
- Tempo de resposta degradado
- Browser travando ao renderizar tabela gigante

**Recomendação de Correção:**  
Implementar paginação:
```python
page = request.args.get('page', 1, type=int)
per_page = request.args.get('per_page', 50, type=int)
movimentos = query.order_by(...).paginate(page=page, per_page=per_page)
```

**Prioridade:** ALTA

---

### **BUG #007 - [SEVERIDADE: ALTO] - Race Condition em Saída Múltipla Permite Estoque Negativo**

**Descrição:**  
A validação de estoque disponível e a atualização não são atômicas, permitindo condição de corrida onde dois usuários podem retirar o mesmo item simultaneamente.

**Localização:**  
- **Arquivo:** `almoxarifado_views.py`
- **Função:** `processar_saida_multipla_api()`
- **Linhas:** ~1450-1730

**Impacto:**  
Estoque pode ficar negativo se dois usuários tentarem retirar o último item ao mesmo tempo.

**Recomendação de Correção:**  
Usar `SELECT FOR UPDATE` ou implementar lock otimista:
```python
# Lock pessimista
estoque = AlmoxarifadoEstoque.query.filter_by(id=estoque_id).with_for_update().first()
if estoque.quantidade_disponivel < quantidade_solicitada:
    raise ValueError("Estoque insuficiente")
```

**Prioridade:** ALTA

---

### **BUG #008 - [SEVERIDADE: ALTO] - Raw SQL DELETE Bypassa Cascade do ORM**

**Descrição:**  
O uso de SQL direto para deletar registros pode não acionar CASCADE rules definidas no ORM, deixando registros órfãos.

**Localização:**  
- **Arquivo:** `almoxarifado_views.py`
- **Função:** `itens_deletar()`
- **Linhas:** 604-613

**Código Problemático:**
```python
db.session.execute(text("DELETE FROM almoxarifado_movimento WHERE ..."))
db.session.execute(text("DELETE FROM almoxarifado_estoque WHERE ..."))
db.session.execute(text("DELETE FROM almoxarifado_item WHERE ..."))
```

**Impacto:**  
Potenciais registros órfãos se novas tabelas relacionadas forem adicionadas no futuro.

**Recomendação de Correção:**  
Documentar ordem de exclusão ou usar ORM com cascade=delete:
```python
# Alternativa mais segura com ORM
AlmoxarifadoMovimento.query.filter_by(item_id=id, admin_id=admin_id).delete()
AlmoxarifadoEstoque.query.filter_by(item_id=id, admin_id=admin_id).delete()
db.session.delete(item)
```

**Prioridade:** MÉDIA

---

### **BUG #009 - [SEVERIDADE: MÉDIO] - Inconsistência no Threshold de Estoque Baixo**

**Descrição:**  
Diferentes partes do código usam `<` ou `<=` para comparar estoque com estoque_minimo, causando inconsistência.

**Localização:**  
- **Arquivo:** `almoxarifado_views.py`
- **Funções:** `dashboard()`, `itens()`, `alertas()`
- **Linhas:** Múltiplas

**Código Problemático:**
```python
# Em um lugar:
'status_estoque': 'baixo' if estoque_atual <= estoque_minimo else 'normal'

# Em outro:
if estoque_atual < estoque_minimo:
```

**Impacto:**  
Alertas inconsistentes - item aparece como estoque baixo em uma página mas não em outra.

**Recomendação de Correção:**  
Padronizar para `<=` (estoque igual ao mínimo já é crítico):
```python
estoque_baixo = estoque_atual <= estoque_minimo
```

**Prioridade:** MÉDIA

---

### **BUG #010 - [SEVERIDADE: MÉDIO] - NoneType Comparison para estoque_minimo NULL**

**Descrição:**  
O campo `estoque_minimo` pode ser NULL no banco, causando erro ao comparar com inteiro.

**Localização:**  
- **Arquivo:** `almoxarifado_views.py`
- **Função:** `alertas()`
- **Linha:** 2686

**Impacto:**  
TypeError: '<' not supported between instances of 'int' and 'NoneType'

**Recomendação de Correção:**  
Tratar NULL como 0:
```python
estoque_minimo = item.estoque_minimo or 0
if estoque_atual <= estoque_minimo:
```

**Prioridade:** MÉDIA

---

### **BUG #011 - [SEVERIDADE: MÉDIO] - Optimistic Locking Incompleto**

**Descrição:**  
Documentação menciona optimistic locking, mas não há campo `version` nos modelos críticos para implementá-lo.

**Localização:**  
- **Arquivo:** `models.py`
- **Modelos:** `AlmoxarifadoEstoque`, `AlmoxarifadoMovimento`

**Impacto:**  
Conflitos de concorrência não são detectados.

**Recomendação de Correção:**  
Adicionar campo version se optimistic locking for necessário:
```python
version = db.Column(db.Integer, default=0)
```

**Prioridade:** BAIXA (funcionalidade não implementada)

---

### **BUG #012 - [SEVERIDADE: MÉDIO] - Debug Info Exposta em Flash Messages**

**Descrição:**  
Mensagens flash contêm informações de debug que não deveriam ser expostas ao usuário.

**Localização:**  
- **Arquivo:** `almoxarifado_views.py`
- **Linhas:** 267-269, 326-327

**Código Problemático:**
```python
flash(f'DEBUG PRODUÇÃO: admin_id vazio. Info: {user_info}', 'danger')
flash(f'DEBUG ERRO: {str(e)}', 'danger')
```

**Impacto:**  
Exposição de informações internas do sistema para usuários.

**Recomendação de Correção:**  
Remover "DEBUG" e informações sensíveis antes do deploy:
```python
flash('Erro de autenticação. Por favor, faça login novamente.', 'danger')
logger.error(f'Erro detalhado: {user_info}')  # Manter apenas no log
```

**Prioridade:** MÉDIA (remover antes de produção)

---

### **BUG #013 - [SEVERIDADE: MÉDIO] - Type Mismatch Decimal vs Float**

**Descrição:**  
Campos `quantidade` são definidos como `Numeric(10,2)` no modelo mas às vezes tratados como float no código.

**Localização:**  
- **Arquivo:** `almoxarifado_views.py`
- **Funções:** Múltiplas operações matemáticas

**Impacto:**  
Possíveis erros de precisão em cálculos financeiros.

**Recomendação de Correção:**  
Usar `Decimal` para operações:
```python
from decimal import Decimal
quantidade = Decimal(str(request.form.get('quantidade', 0)))
```

**Prioridade:** BAIXA

---

### **BUG #014 - [SEVERIDADE: MÉDIO] - Missing try/except em Loop do Dashboard**

**Descrição:**  
O loop que calcula estoque por item no dashboard não tem tratamento de erros.

**Localização:**  
- **Arquivo:** `almoxarifado_views.py`
- **Função:** `dashboard()`
- **Linhas:** 44-66

**Impacto:**  
Um item com dados corrompidos pode quebrar todo o dashboard.

**Recomendação de Correção:**  
Adicionar try/except dentro do loop:
```python
for item in itens:
    try:
        # calcular estoque
    except Exception as e:
        logger.error(f'Erro ao processar item {item.id}: {e}')
        continue
```

**Prioridade:** BAIXA

---

### **BUG #015 - [SEVERIDADE: BAIXO] - Unique Constraint Faltante para Número de Série**

**Descrição:**  
O modelo `AlmoxarifadoEstoque` não tem constraint unique para `numero_serie + admin_id`, permitindo duplicatas.

**Localização:**  
- **Arquivo:** `models.py`
- **Modelo:** `AlmoxarifadoEstoque`
- **Linha:** 3794

**Impacto:**  
Possível cadastrar dois itens serializados com o mesmo número de série.

**Recomendação de Correção:**  
Adicionar constraint:
```python
__table_args__ = (
    db.UniqueConstraint('numero_serie', 'admin_id', name='uk_estoque_serie_admin'),
    ...
)
```

**Prioridade:** BAIXA

---

## 4. PROBLEMAS DE PERFORMANCE

| ID | Problema | Localização | Impacto |
|----|----------|-------------|---------|
| PERF #001 | N+1 queries em dashboard | Linhas 44-66 | Alto |
| PERF #002 | N+1 queries em itens list | Linhas 296-315 | Alto |
| PERF #003 | Sem paginação em movimentações | Linhas 524, 2508 | Alto |
| PERF #004 | Join sem eager loading | Múltiplas funções | Médio |

---

## 5. PROBLEMAS DE SEGURANÇA

| ID | Problema | Localização | Severidade |
|----|----------|-------------|------------|
| SEC #001 | Ausência de CSRF tokens | Todos os templates | CRÍTICO |
| SEC #002 | Debug info em flash messages | Linhas 267-269 | MÉDIO |
| SEC #003 | Sem rate limiting nas APIs | Rotas /api/* | BAIXO |

---

## 6. VIOLAÇÕES DE BOAS PRÁTICAS

| ID | Problema | Recomendação |
|----|----------|--------------|
| BP #001 | Lógica duplicada para cálculo de estoque | Criar função helper reutilizável |
| BP #002 | SQL raw para DELETEs | Preferir ORM com cascades |
| BP #003 | Magic numbers no código | Definir constantes |
| BP #004 | Falta de docstrings em funções complexas | Documentar funções |

---

## 7. FUNCIONALIDADES DOCUMENTADAS VS IMPLEMENTADAS

| Funcionalidade | Status |
|----------------|--------|
| ✅ Gestão de Materiais, Ferramentas e EPIs | Implementado |
| ✅ CRUD Completo de Fornecedores | Implementado |
| ✅ Fluxos de Movimentação (E/S/D) | Implementado |
| ⚠️ Seleção Manual de Lotes/Batches | Parcial (FIFO incompleto em devoluções) |
| ✅ Controle de Itens Serializados | Implementado |
| ❌ Optimistic Locking | Não implementado |
| ✅ Rastreamento de Consumíveis por Funcionário | Implementado |

---

## 8. PONTOS POSITIVOS

1. **Multi-tenancy consistente**: Todas as rotas filtram por `admin_id`
2. **SQL parametrizado**: Queries raw usam parâmetros nomeados
3. **Error handling**: Maioria das operações críticas tem rollback
4. **Templates padronizados**: 100% usam `base_completo.html`
5. **Índices adequados**: Modelos têm índices nas colunas de filtro
6. **Timestamps**: Todos os modelos têm `created_at` e `updated_at`
7. **Relacionamentos ORM**: Backref configurados corretamente

---

## 9. ESTATÍSTICAS DA AUDITORIA

| Métrica | Valor |
|---------|-------|
| **Total de Bugs Identificados** | 15 |
| → Críticos | 4 |
| → Altos | 4 |
| → Médios | 5 |
| → Baixos | 2 |
| **Problemas de Performance** | 4 |
| **Problemas de Segurança** | 3 |
| **Violações de Boas Práticas** | 4 |
| **Linhas de Código Analisadas** | ~4.500 |
| **Templates Analisados** | 20 |
| **Modelos Analisados** | 5 |

---

## 10. RECOMENDAÇÕES PRIORITÁRIAS

### Correções Obrigatórias (Fazer AGORA):

1. **[CRÍTICO]** Remover filtro `ativo=True` da linha 2412 em `relatorios()`
2. **[CRÍTICO]** Adicionar CSRF tokens em todos os formulários POST
3. **[CRÍTICO]** Tratar ValueError em conversões de filtros
4. **[CRÍTICO]** Completar campos FIFO em devoluções

### Correções Importantes (Próximo Sprint):

5. **[ALTO]** Resolver N+1 queries com subqueries/eager loading
6. **[ALTO]** Implementar paginação em listagens de movimentações
7. **[ALTO]** Adicionar lock pessimista em saídas críticas
8. **[MÉDIO]** Remover mensagens DEBUG antes do deploy

### Melhorias Desejáveis (Backlog):

9. **[MÉDIO]** Padronizar comparação de estoque baixo (usar `<=`)
10. **[BAIXO]** Adicionar unique constraint para número de série

---

## CONCLUSÃO

O módulo de Almoxarifado está **funcionalmente operacional** mas requer correções urgentes nos itens marcados como CRÍTICO antes de uso em produção intensiva. Os problemas de performance (N+1 queries) devem ser tratados antes de escalar para volumes maiores de dados.

**Próximos Passos Recomendados:**
1. Corrigir bugs críticos (1-4) imediatamente
2. Executar testes E2E após correções
3. Monitorar performance em produção
4. Implementar CSRF protection como padrão em todo o sistema

---

*Relatório gerado automaticamente pelo sistema de auditoria SIGE v9.0*
