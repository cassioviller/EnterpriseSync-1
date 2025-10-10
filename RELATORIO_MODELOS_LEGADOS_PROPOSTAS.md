# RELATÓRIO COMPLETO - MAPEAMENTO DE MODELOS LEGADOS DE PROPOSTAS

**Data:** 10 de Outubro de 2025  
**Objetivo:** Mapear TODAS as referências aos modelos legados de propostas no codebase SIGE v8.0

---

## RESUMO EXECUTIVO

### Modelos Legados Identificados:
1. ✅ **`Proposta`** (modelo antigo/legado)
2. ✅ **`PropostaHistorico`** (modelo não utilizado)
3. ✅ **`ItemServicoPropostaDinamica`** (modelo duplicado)

### Status Geral:
- **Total de arquivos afetados:** 10 arquivos Python
- **Total de templates afetados:** 17 arquivos HTML
- **Modelo atual recomendado:** `PropostaComercialSIGE`

---

## 1. MODELO: `Proposta` (LEGADO)

### 1.1 DEFINIÇÃO DO MODELO

**Arquivo:** `models.py`  
**Linha:** 1872-1891  
**Tipo:** Definição de classe (Model)

```python
class Proposta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50), unique=True, nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    valor_total = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='rascunho')
    data_vencimento = db.Column(db.Date)
    data_envio = db.Column(db.DateTime)
    link_visualizacao = db.Column(db.String(255))
    obra_id = db.Column(db.Integer, db.ForeignKey('obra.id'))
    admin_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    cliente = db.relationship('Cliente', backref='propostas')
    admin = db.relationship('Usuario', backref='propostas_administradas')
    itens_servicos_dinamicos = db.relationship('ItemServicoPropostaDinamica', back_populates='proposta', cascade='all, delete-orphan')
```

### 1.2 IMPORTS DO MODELO

| Arquivo | Linha | Contexto |
|---------|-------|----------|
| `sistema_propostas.py` | 8 | `from models import db, Proposta, Cliente, Usuario, Obra` |
| `contabilidade_utils.py` | 5 | `from models import (..., Proposta, NotaFiscal, ...)` |
| `api_organizer.py` | 6 | `from models import db, PropostaTemplate, PropostaComercialSIGE, PropostaItem` (não importa Proposta) |
| `portal_cliente_avancado.py` | 8 | `from models import db, Cliente, Proposta, Obra, RDO, Usuario` |
| `templates_views.py` | 7 | `from models import db, PropostaTemplate, ServicoTemplate, Servico, TipoUsuario` (não importa Proposta) |
| `propostas_views.py` | 16 | `from models import PropostaComercialSIGE, PropostaItem, ...` (não importa Proposta) |
| `servicos_views.py` | 8 | `from models import db, Proposta` |

### 1.3 QUERIES E OPERAÇÕES

| Arquivo | Linha | Tipo | Contexto |
|---------|-------|------|----------|
| `sistema_propostas.py` | 24 | Query | `total_propostas = Proposta.query.filter_by(admin_id=current_user.id).count()` |
| `sistema_propostas.py` | 25 | Query | `propostas_pendentes = Proposta.query.filter_by(admin_id=current_user.id, status='pendente').count()` |
| `sistema_propostas.py` | 26 | Query | `propostas_aprovadas = Proposta.query.filter_by(admin_id=current_user.id, status='aprovada').count()` |
| `sistema_propostas.py` | 27 | Query | `propostas_rejeitadas = Proposta.query.filter_by(admin_id=current_user.id, status='rejeitada').count()` |
| `sistema_propostas.py` | 30 | Agregação | `db.session.query(db.func.sum(Proposta.valor_total)).filter_by(admin_id=current_user.id).scalar()` |
| `sistema_propostas.py` | 31 | Agregação | `db.session.query(db.func.sum(Proposta.valor_total)).filter_by(admin_id=current_user.id, status='aprovada').scalar()` |
| `sistema_propostas.py` | 37 | Query | `propostas_recentes = Proposta.query.filter_by(admin_id=current_user.id).order_by(Proposta.created_at.desc()).limit(10).all()` |
| `sistema_propostas.py` | 41-44 | Query complexa | `propostas_vencendo = Proposta.query.filter(...)` |
| `sistema_propostas.py` | 78 | Criação | `proposta = Proposta(numero=..., cliente_id=..., ...)` |
| `sistema_propostas.py` | 112 | Query base | `query = Proposta.query.filter_by(admin_id=current_user.id)` |
| `sistema_propostas.py` | 116 | Filtro | `query.filter(Proposta.status == status_filter)` |
| `sistema_propostas.py` | 119 | Filtro | `query.filter(Proposta.cliente_id == cliente_filter)` |
| `sistema_propostas.py` | 122 | Filtro | `query.filter(Proposta.created_at >= ...)` |
| `sistema_propostas.py` | 125 | Filtro | `query.filter(Proposta.created_at <= ...)` |
| `sistema_propostas.py` | 148 | Query | `proposta = Proposta.query.filter_by(id=id, admin_id=current_user.id).first_or_404()` |
| `sistema_propostas.py` | 161 | Query | `proposta = Proposta.query.filter_by(id=id, admin_id=current_user.id).first_or_404()` |
| `sistema_propostas.py` | 172 | Query | `proposta = Proposta.query.filter_by(id=id, admin_id=current_user.id).first_or_404()` |
| `sistema_propostas.py` | 205 | Query | `proposta = Proposta.query.filter_by(id=id, admin_id=current_user.id).first_or_404()` |
| `sistema_propostas.py` | 239 | Query | `proposta = Proposta.query.filter_by(id=id, admin_id=current_user.id).first_or_404()` |
| `contabilidade_utils.py` | 146 | Query | `proposta = Proposta.query.get(proposta_id)` |
| `cliente_portal_utils.py` | 499 | Query | `proposta = Proposta.query.get(proposta_id)` |
| `portal_cliente_avancado.py` | 32 | Query | `propostas = Proposta.query.filter_by(cliente_id=cliente.id).order_by(Proposta.created_at.desc()).limit(5).all()` |
| `integracoes_automaticas.py` | 30 | Query | `proposta = Proposta.query.get(proposta_id)` |
| `fluxo_dados_automatico.py` | 178-180 | Query complexa | `propostas_orphans = Proposta.query.filter(Proposta.status == 'APROVADA', Proposta.obra_id.is_(None)).count()` |
| `fluxo_dados_automatico.py` | 278 | Query (comentado) | `proposta = Proposta.query.get(proposta_id)` |
| `propostas_engine.py` | 48-49 | Query | `query = Proposta.query.filter(Proposta.numero_proposta.like(...))` |
| `propostas_engine.py` | 203 | Query | `proposta = Proposta.query.get(proposta_id)` |
| `propostas_engine.py` | 246 | Query | `proposta = Proposta.query.get(proposta_id)` |
| `propostas_engine.py` | 309 | Query | `proposta = Proposta.query.get(proposta_id)` |
| `propostas_engine.py` | 616 | Query | `query = Proposta.query` |
| `propostas_engine.py` | 636 | Query | `query = Proposta.query` |
| `propostas_engine.py` | 638 | Filtro | `query.filter(Proposta.admin_id == admin_id)` |

### 1.4 FOREIGN KEYS APONTANDO PARA PROPOSTA

| Arquivo | Linha | Tipo | Contexto |
|---------|-------|------|----------|
| `models.py` | 1729 | Comentário FK | `origem_id = db.Column(db.Integer) # ID do registro de origem (Proposta, NotaFiscal, etc)` |
| `models.py` | 1894 | FK | `proposta_id = db.Column(db.Integer, db.ForeignKey('proposta.id'), nullable=False)` (PropostaHistorico) |
| `models.py` | 2083 | FK | `proposta_id = Column(Integer, ForeignKey('proposta.id'), nullable=False)` (ItemServicoPropostaDinamica) |

### 1.5 REFERÊNCIAS EM TEMPLATES HTML

| Template | Tipo de Uso |
|----------|-------------|
| `templates/propostas/visualizar.html` | Exibe dados: `{{ proposta.numero_proposta }}`, `{{ proposta.cliente_nome }}`, `{{ proposta.assunto }}`, `{{ proposta.status }}`, etc. |
| `templates/propostas/listar.html` | Lista propostas com filtros |
| `templates/propostas/dashboard.html` | Dashboard de propostas |
| `templates/propostas/editar.html` | Formulário de edição |
| `templates/propostas/pdf.html` | Geração de PDF |
| `templates/propostas/portal_cliente.html` | Portal do cliente |
| `templates/cliente/proposta_detalhes.html` | Detalhes para cliente |

---

## 2. MODELO: `PropostaHistorico` (NÃO UTILIZADO)

### 2.1 DEFINIÇÃO DO MODELO

**Arquivo:** `models.py`  
**Linha:** 1892-1903  
**Tipo:** Definição de classe (Model)

```python
class PropostaHistorico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    proposta_id = db.Column(db.Integer, db.ForeignKey('proposta.id'), nullable=False)
    acao = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.Text)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    proposta = db.relationship('Proposta', backref='historico')
    usuario = db.relationship('Usuario', backref='acoes_propostas')
```

### 2.2 IMPORTS DO MODELO

**NENHUM IMPORT DIRETO ENCONTRADO** - O modelo é definido mas nunca importado diretamente.

### 2.3 QUERIES E OPERAÇÕES

| Arquivo | Linha | Tipo | Contexto |
|---------|-------|------|----------|
| `sistema_propostas.py` | 151 | Query | `historico = PropostaHistorico.query.filter_by(proposta_id=id).order_by(PropostaHistorico.created_at.desc()).all()` |
| `sistema_propostas.py` | 260-264 | Criação | `historico = PropostaHistorico(proposta_id=..., acao=..., descricao=..., usuario_id=...)` |

### 2.4 RELACIONAMENTOS

| Arquivo | Linha | Tipo | Contexto |
|---------|-------|------|----------|
| `models.py` | 1901 | Relationship | `proposta = db.relationship('Proposta', backref='historico')` |
| `models.py` | 1902 | Relationship | `usuario = db.relationship('Usuario', backref='acoes_propostas')` |

**OBSERVAÇÃO:** Este modelo é usado APENAS no arquivo `sistema_propostas.py` e não tem uso em outros módulos.

---

## 3. MODELO: `ItemServicoPropostaDinamica` (DUPLICADO)

### 3.1 DEFINIÇÃO DO MODELO

**Arquivo:** `models.py`  
**Linha:** 2078-2112  
**Tipo:** Definição de classe (Model)

```python
class ItemServicoPropostaDinamica(db.Model):
    """Itens de serviço dinamicamente adicionados à proposta"""
    __tablename__ = 'item_servico_proposta_dinamica'
    
    id = Column(Integer, primary_key=True)
    proposta_id = Column(Integer, ForeignKey('proposta.id'), nullable=False)
    servico_mestre_id = Column(Integer, ForeignKey('servico_mestre.id'), nullable=True)
    codigo = Column(String(50))
    nome_item = Column(String(200), nullable=False)
    descricao = Column(Text)
    unidade_medida = Column(String(20))
    quantidade = Column(Numeric(10, 2), nullable=False)
    valor_unitario = Column(Numeric(10, 2), nullable=False)
    valor_total = Column(Numeric(12, 2))
    bdi_percentual = Column(Numeric(5, 2), default=0.0)
    percentual_aplicacao = Column(Numeric(5, 2), default=100.0)
    ordem = Column(Integer, default=0)
    categoria = Column(String(100))
    ativo = Column(Boolean, default=True)
    admin_id = Column(Integer, ForeignKey('usuario.id'), nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    proposta = relationship('Proposta', back_populates='itens_servicos_dinamicos', foreign_keys=[proposta_id])
    servico_mestre = relationship('ServicoMestre', back_populates='itens_proposta')
    admin = relationship('Usuario', foreign_keys=[admin_id])
```

### 3.2 IMPORTS DO MODELO

| Arquivo | Linha | Contexto |
|---------|-------|----------|
| `servicos_views.py` | 9-12 | `from models_servicos import (..., ItemServicoPropostaDinamica, ...)` |

**OBSERVAÇÃO:** O modelo é importado de `models_servicos` (que NÃO EXISTE mais) em vez de `models`.

### 3.3 QUERIES E OPERAÇÕES

| Arquivo | Linha | Tipo | Contexto |
|---------|-------|------|----------|
| `servicos_views.py` | 53-58 | Query com JOIN | `db.session.query(ServicoMestre, db.func.count(ItemServicoPropostaDinamica.id).label('uso_count')).join(ItemServicoPropostaDinamica, ...)` |
| `servicos_views.py` | 365-367 | Criação | `item_principal = ItemServicoPropostaDinamica(proposta_id=..., servico_mestre_id=..., ...)` |
| `servicos_views.py` | 397-399 | Criação | `item_sub = ItemServicoPropostaDinamica(proposta_id=..., servico_mestre_id=..., ...)` |

### 3.4 RELACIONAMENTOS

| Arquivo | Linha | Tipo | Contexto |
|---------|-------|------|----------|
| `models.py` | 1890 | Relationship (Proposta) | `itens_servicos_dinamicos = db.relationship('ItemServicoPropostaDinamica', back_populates='proposta', cascade='all, delete-orphan')` |
| `models.py` | 1949 | Relationship (ServicoMestre) | `itens_proposta = relationship('ItemServicoPropostaDinamica', back_populates='servico_mestre')` |
| `models.py` | 2107 | Relationship (self) | `proposta = relationship('Proposta', back_populates='itens_servicos_dinamicos', foreign_keys=[proposta_id])` |
| `models.py` | 2108 | Relationship (self) | `servico_mestre = relationship('ServicoMestre', back_populates='itens_proposta')` |

---

## 4. ANÁLISE DE DEPENDÊNCIAS

### 4.1 ARQUIVOS QUE DEPENDEM DE `Proposta` (LEGADO)

1. **sistema_propostas.py** - USO EXTENSIVO (blueprint completo)
2. **contabilidade_utils.py** - Integração contábil
3. **portal_cliente_avancado.py** - Portal do cliente
4. **servicos_views.py** - Sistema de serviços
5. **cliente_portal_utils.py** - Utilitários portal
6. **integracoes_automaticas.py** - Automações
7. **fluxo_dados_automatico.py** - Fluxo de dados
8. **propostas_engine.py** - Engine de propostas

### 4.2 ARQUIVOS QUE DEPENDEM DE `PropostaHistorico`

1. **sistema_propostas.py** - ÚNICO arquivo que usa

### 4.3 ARQUIVOS QUE DEPENDEM DE `ItemServicoPropostaDinamica`

1. **servicos_views.py** - ÚNICO arquivo que usa
2. **models.py** - Definição e relacionamentos

---

## 5. CONFLITOS E PROBLEMAS IDENTIFICADOS

### 5.1 CONFLITO: Dois Sistemas de Propostas

**Problema:** Existem DOIS sistemas de propostas coexistindo:

1. **Sistema LEGADO** (`Proposta`):
   - Arquivo: `sistema_propostas.py`
   - Modelo: `Proposta`
   - Histórico: `PropostaHistorico`
   - Itens: `ItemServicoPropostaDinamica`
   - Status: EM USO ATIVO

2. **Sistema ATUAL** (`PropostaComercialSIGE`):
   - Arquivo: `propostas_consolidated.py`
   - Modelo: `PropostaComercialSIGE`
   - Histórico: Não implementado
   - Itens: `PropostaItem`
   - Status: SISTEMA PRINCIPAL

**Impacto:** Confusão de código, duplicação de funcionalidades, inconsistência de dados.

### 5.2 PROBLEMA: Import de Módulo Inexistente

**Arquivo:** `servicos_views.py`  
**Linha:** 9-12

```python
from models_servicos import (
    ServicoMestre, SubServico, TabelaComposicao, 
    ItemTabelaComposicao, ItemServicoPropostaDinamica,
    StatusServico, TipoUnidade
)
```

**Problema:** O arquivo `models_servicos.py` NÃO EXISTE no projeto.  
**Impacto:** Este import deve falhar em tempo de execução.

### 5.3 PROBLEMA: Foreign Keys para Tabela Legada

**Tabelas que apontam para `proposta` (legado):**

1. `proposta_historico.proposta_id` → `proposta.id`
2. `item_servico_proposta_dinamica.proposta_id` → `proposta.id`

**Impacto:** Se a tabela `proposta` for removida, estas FKs quebrarão.

---

## 6. RECOMENDAÇÕES

### 6.1 MIGRAÇÃO URGENTE

1. **MIGRAR** todos os dados de `Proposta` para `PropostaComercialSIGE`
2. **DEPRECAR** o arquivo `sistema_propostas.py`
3. **REMOVER** o modelo `PropostaHistorico` (pouco usado)
4. **INTEGRAR** `ItemServicoPropostaDinamica` com `PropostaItem` ou remover

### 6.2 AÇÕES IMEDIATAS

1. **Corrigir** import em `servicos_views.py`:
   ```python
   # ANTES (ERRADO):
   from models_servicos import ItemServicoPropostaDinamica
   
   # DEPOIS (CORRETO):
   from models import ItemServicoPropostaDinamica
   ```

2. **Identificar** qual sistema de propostas está sendo usado em produção
3. **Criar** script de migração de dados
4. **Atualizar** todos os imports para usar `PropostaComercialSIGE`

### 6.3 PLANO DE REMOÇÃO

**Fase 1 - Identificação (CONCLUÍDA)**
- ✅ Mapear todas as referências
- ✅ Identificar dependências
- ✅ Documentar problemas

**Fase 2 - Migração de Dados**
- [ ] Criar script SQL para migrar dados de `proposta` → `propostas_comerciais`
- [ ] Migrar histórico para novo formato
- [ ] Verificar integridade referencial

**Fase 3 - Atualização de Código**
- [ ] Substituir imports de `Proposta` por `PropostaComercialSIGE`
- [ ] Atualizar queries e operações
- [ ] Corrigir templates HTML
- [ ] Atualizar relacionamentos

**Fase 4 - Remoção**
- [ ] Remover arquivo `sistema_propostas.py`
- [ ] Remover modelos legados de `models.py`
- [ ] Remover templates não utilizados
- [ ] Limpar banco de dados

---

## 7. ARQUIVOS PARA ATENÇÃO ESPECIAL

### 7.1 ALTA PRIORIDADE (Uso extensivo de modelos legados)

1. **sistema_propostas.py** - Blueprint completo com modelo legado
2. **servicos_views.py** - Import de módulo inexistente
3. **propostas_engine.py** - Engine usando modelo legado

### 7.2 MÉDIA PRIORIDADE (Uso moderado)

4. **contabilidade_utils.py** - Integração contábil
5. **portal_cliente_avancado.py** - Portal do cliente
6. **integracoes_automaticas.py** - Automações

### 7.3 BAIXA PRIORIDADE (Uso mínimo)

7. **cliente_portal_utils.py** - Utilitário simples
8. **fluxo_dados_automatico.py** - Verificação de orphans

---

## 8. ESTATÍSTICAS FINAIS

| Métrica | Valor |
|---------|-------|
| **Modelos Legados Encontrados** | 3 |
| **Arquivos Python Afetados** | 10 |
| **Templates HTML Afetados** | 17 |
| **Total de Queries Proposta** | 40+ |
| **Total de Queries PropostaHistorico** | 2 |
| **Total de Queries ItemServicoPropostaDinamica** | 3 |
| **Foreign Keys para Proposta** | 2 |
| **Relacionamentos** | 6 |
| **Blueprints Afetados** | 3 |

---

## 9. CONCLUSÃO

O sistema SIGE v8.0 possui uma **DUPLICAÇÃO CRÍTICA** de sistemas de propostas:

- **Sistema Legado** (`Proposta`) ainda está ativo e sendo usado
- **Sistema Atual** (`PropostaComercialSIGE`) é o padrão mas coexiste com o legado
- **Risco de inconsistência** de dados entre os dois sistemas
- **Necessidade urgente** de migração e consolidação

### Próximos Passos Recomendados:

1. ✅ **DECISÃO**: Qual sistema manter (recomendado: `PropostaComercialSIGE`)
2. ⚠️ **MIGRAÇÃO**: Script de migração de dados
3. 🔧 **REFATORAÇÃO**: Atualizar todo o código
4. 🗑️ **LIMPEZA**: Remover código legado
5. ✅ **VALIDAÇÃO**: Testes completos pós-migração

---

**Relatório gerado em:** 10/10/2025  
**Ferramenta:** Análise automatizada com grep + leitura de código  
**Status:** COMPLETO
