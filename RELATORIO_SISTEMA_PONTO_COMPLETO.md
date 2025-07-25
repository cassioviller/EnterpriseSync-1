# RELATÓRIO TÉCNICO COMPLETO - Sistema de Registro de Ponto SIGE v8.0

## VISÃO GERAL DO SISTEMA

### Finalidade
O sistema de controle de ponto é usado para:
- **Registrar jornada de trabalho** de funcionários da construção civil
- **Calcular horas extras** com percentuais diferenciados (50% sábado, 100% domingo/feriado)
- **Controlar atrasos e faltas** para cálculo de KPIs de produtividade
- **Gerar custos de mão de obra** precisos por projeto/obra
- **Atender legislação trabalhista** com diferentes tipos de lançamento

## ESQUEMA DO BANCO DE DADOS

### Modelo: RegistroPonto
```sql
CREATE TABLE registro_ponto (
    id INTEGER PRIMARY KEY,
    funcionario_id INTEGER NOT NULL,  -- FK para Funcionario
    data DATE NOT NULL,
    tipo_registro VARCHAR(50) NOT NULL,  -- Enum dos tipos
    obra_id INTEGER,  -- FK para Obra (opcional)
    
    -- HORÁRIOS
    hora_entrada TIME,
    hora_saida TIME,
    hora_almoco_saida TIME,
    hora_almoco_retorno TIME,
    
    -- CÁLCULOS AUTOMÁTICOS
    horas_trabalhadas DECIMAL(4,2) DEFAULT 0,
    horas_extras DECIMAL(4,2) DEFAULT 0,
    percentual_extras INTEGER DEFAULT 0,
    
    -- CONTROLE DE ATRASOS
    minutos_atraso_entrada INTEGER DEFAULT 0,
    minutos_atraso_saida INTEGER DEFAULT 0,
    total_atraso_minutos INTEGER DEFAULT 0,
    total_atraso_horas DECIMAL(4,2) DEFAULT 0,
    
    observacoes TEXT
);
```

### Relacionamentos
- `funcionario_id` → `funcionario.id` (FK obrigatória)
- `obra_id` → `obra.id` (FK opcional para controle de custos)

## TIPOS DE REGISTRO E REGRAS DE NEGÓCIO

### 1. TRABALHO_NORMAL
**Finalidade**: Jornada normal de segunda a sexta
**Horários**: Entrada/Saída/Almoço obrigatórios
**Horas Extras**: Apenas acima de 8h (jornada padrão)
**Atrasos**: SIM - calculados vs horário do funcionário
**Percentual**: 50% para horas extras normais

### 2. SABADO_HORAS_EXTRAS  
**Finalidade**: Trabalho opcional em sábado
**Horários**: Entrada/Saída obrigatórios, Almoço opcional
**Horas Extras**: TODAS as horas = 50% adicional
**Atrasos**: NÃO - não há horário fixo, toda hora é extra
**Percentual**: 50% sobre TODAS as horas

### 3. DOMINGO_HORAS_EXTRAS
**Finalidade**: Trabalho opcional em domingo
**Horários**: Entrada/Saída obrigatórios, Almoço opcional
**Horas Extras**: TODAS as horas = 100% adicional  
**Atrasos**: NÃO - não há horário fixo, toda hora é extra
**Percentual**: 100% sobre TODAS as horas

### 4. FERIADO_TRABALHADO
**Finalidade**: Trabalho em feriado nacional
**Horários**: Entrada/Saída obrigatórios, Almoço opcional
**Horas Extras**: TODAS as horas = 100% adicional
**Atrasos**: NÃO - não há horário fixo, toda hora é extra  
**Percentual**: 100% sobre TODAS as horas

### 5. FALTA / FALTA_JUSTIFICADA
**Finalidade**: Ausência do funcionário
**Horários**: Todos nulos (não trabalhou)
**Horas Extras**: 0
**Atrasos**: 0
**Percentual**: 0

## CÁLCULOS AUTOMÁTICOS

### Motor de Cálculo: `kpis_engine.py`

#### Função: `calcular_e_atualizar_ponto()`
```python
def calcular_e_atualizar_ponto(self, registro_ponto_id):
    # 1. BUSCAR REGISTRO
    registro = RegistroPonto.query.get(registro_ponto_id)
    
    # 2. CALCULAR ATRASOS (apenas para trabalho normal)
    if registro.tipo_registro not in ['sabado_horas_extras', 'domingo_horas_extras', 'feriado_trabalhado']:
        # Calcular atraso entrada + saída antecipada
        
    # 3. CALCULAR HORAS TRABALHADAS
    if entrada and saida:
        total_minutos = saida - entrada - tempo_almoco
        registro.horas_trabalhadas = total_minutos / 60.0
        
    # 4. CALCULAR HORAS EXTRAS
    if tipo_especial:
        registro.horas_extras = registro.horas_trabalhadas  # TODAS
    else:
        registro.horas_extras = max(0, registro.horas_trabalhadas - 8.0)  # Acima de 8h
```

#### KPIs Calculados:
```python
def _calcular_horas_extras(self, funcionario_id, data_inicio, data_fim):
    # Para tipos especiais: usar campo horas_extras diretamente
    if registro.tipo_registro in ['sabado_horas_extras', 'domingo_horas_extras', 'feriado_trabalhado']:
        total_horas_extras += registro.horas_extras  # TODAS as horas
    else:
        # Para trabalho normal: apenas acima da jornada
        if registro.horas_trabalhadas > horas_diarias_padrao:
            total_horas_extras += registro.horas_trabalhadas - horas_diarias_padrao

def _calcular_atrasos_horas(self, funcionario_id, data_inicio, data_fim):
    # EXCLUIR tipos onde toda hora é extra
    ~RegistroPonto.tipo_registro.in_(['sabado_horas_extras', 'domingo_horas_extras', 'feriado_trabalhado'])
```

## PROBLEMAS IDENTIFICADOS E BUGS

### 🔴 PROBLEMA 1: Sábado sem Horário de Almoço
**Sintoma**: Registros de sábado não salvam hora_almoco_saida/retorno
**Causa**: JavaScript ou backend não processa almoço para tipos especiais
**Impacto**: Cálculo incorreto de horas trabalhadas

### 🔴 PROBLEMA 2: Cálculo de Horas Inconsistente  
**Sintoma**: Horas extras não seguem regra "TODAS as horas em sábado/domingo"
**Causa**: Lógica de cálculo não diferencia tipos especiais
**Impacto**: Pagamento incorreto de horas extras

### 🔴 PROBLEMA 3: CRUD com Erros de Campo
**Sintoma**: `AttributeError: 'entrada' object has no attribute`
**Causa**: Inconsistência entre nomes de campos no modelo vs código
**Impacto**: Funcionalidade de edição quebrada

### 🔴 PROBLEMA 4: Validação de Tipos Especiais
**Sintoma**: Sistema permite atrasos em sábado/domingo
**Causa**: Lógica de atraso não exclui tipos especiais
**Impacto**: KPIs incorretos

## FLUXO CORRETO DE FUNCIONAMENTO

### Criação de Registro:
1. **Frontend**: Modal coleta dados (data, tipo, horários)
2. **Backend**: `criar_registro_ponto()` salva dados básicos
3. **Engine**: `calcular_e_atualizar_ponto()` processa cálculos
4. **Resultado**: Registro com horas e atrasos calculados

### Edição de Registro:
1. **Frontend**: `obter_registro_ponto()` carrega dados existentes  
2. **Modal**: Exibe dados para edição
3. **Backend**: `atualizar_registro_ponto()` aplica mudanças
4. **Engine**: Recalcula automática ou manualmente

### Cálculo de KPIs:
1. **Consulta**: Busca registros por funcionário/período
2. **Filtros**: Separa tipos normais vs especiais  
3. **Soma**: Agrega horas trabalhadas, extras, atrasos
4. **Exibição**: Perfil do funcionário mostra resultados

## REGRAS CRÍTICAS DE IMPLEMENTAÇÃO

### ✅ REGRA 1: Horários de Almoço
- **Trabalho Normal**: OBRIGATÓRIO (desconta 1h padrão)
- **Sábado/Domingo**: OPCIONAL (pode trabalhar sem parar)
- **Falta**: NÃO SE APLICA (nulos)

### ✅ REGRA 2: Cálculo de Horas Extras
```python
if tipo_registro in ['sabado_horas_extras', 'domingo_horas_extras', 'feriado_trabalhado']:
    # TODAS as horas são extras
    registro.horas_extras = registro.horas_trabalhadas
else:
    # Apenas acima da jornada normal
    registro.horas_extras = max(0, registro.horas_trabalhadas - jornada_normal)
```

### ✅ REGRA 3: Atrasos
```python
if tipo_registro not in ['sabado_horas_extras', 'domingo_horas_extras', 'feriado_trabalhado']:
    # Só calcula atraso para trabalho com horário fixo
    calcular_atrasos()
else:
    # Tipos especiais: zero atraso sempre
    registro.total_atraso_horas = 0
```

### ✅ REGRA 4: Percentuais
- **Trabalho Normal**: 50% apenas para horas acima de 8h
- **Sábado**: 50% sobre TODAS as horas
- **Domingo/Feriado**: 100% sobre TODAS as horas

## CORREÇÕES NECESSÁRIAS

### 1. Corrigir CRUD (views.py)
```python
# ❌ ERRO ATUAL
'entrada': registro.entrada.strftime('%H:%M')

# ✅ CORREÇÃO  
'entrada': registro.hora_entrada.strftime('%H:%M')
```

### 2. Corrigir Motor de Cálculo
```python
# ❌ LÓGICA INCORRETA
if registro.horas_trabalhadas > 8:
    registro.horas_extras = registro.horas_trabalhadas - 8

# ✅ LÓGICA CORRETA
if registro.tipo_registro in tipos_especiais:
    registro.horas_extras = registro.horas_trabalhadas  # TODAS
else:
    registro.horas_extras = max(0, registro.horas_trabalhadas - 8)  # Acima de 8h
```

### 3. Corrigir Horário de Almoço
```python
# Permitir almoço opcional em sábado/domingo
if tipo_registro in ['sabado_horas_extras', 'domingo_horas_extras']:
    tempo_almoco = 0 if not almoco_saida else (almoco_retorno - almoco_saida)
```

## ARQUIVOS PRINCIPAIS ENVOLVIDOS

- **models.py**: Estrutura do banco (RegistroPonto)
- **views.py**: APIs REST (CRUD do ponto) 
- **kpis_engine.py**: Motor de cálculos e KPIs
- **templates/funcionario_perfil.html**: Interface de controle
- **static/js/**: JavaScript do modal de edição

## COMANDOS DE TESTE E VALIDAÇÃO

```python
# Testar cálculos
python -c "from kpis_engine import KPIsEngine; engine = KPIsEngine(); engine.calcular_e_atualizar_ponto(991)"

# Verificar inconsistências  
python debug_calculos_ponto.py

# Corrigir dados existentes
python corrigir_calculos_sabado.py
```

Este relatório fornece visão completa para qualquer LLM corrigir os problemas do sistema de ponto.