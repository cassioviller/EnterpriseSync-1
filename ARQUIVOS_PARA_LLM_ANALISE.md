# 📋 ARQUIVOS ESSENCIAIS PARA ANÁLISE DE LLM

## 🎯 ARQUIVOS PRINCIPAIS (OBRIGATÓRIOS)

### 1. MODELOS DE DADOS
```
models.py
```
**Por quê**: Define a estrutura do banco, relacionamentos entre tabelas e campos dos registros de ponto.

### 2. ENGINE DE KPIs ATUAL
```
kpis_engine.py
```
**Por quê**: Contém toda a lógica atual de cálculo de KPIs, métodos de agregação e fórmulas.

### 3. ENGINE CORRIGIDO
```
kpis_engine_corrigido.py
```
**Por quê**: Implementação corrigida com validações e lógica melhorada.

### 4. CORREÇÃO COMPLETA
```
correcao_completa_kpis.py
```
**Por quê**: Classes principais com tipos padronizados e serviços de cálculo.

## 🔍 ARQUIVOS DE VALIDAÇÃO (RECOMENDADOS)

### 5. VALIDAÇÃO CRUZADA
```
teste_validacao_kpis.py
```
**Por quê**: Mostra como comparar diferentes métodos de cálculo.

### 6. SCRIPT DE CORREÇÃO DE TIPOS
```
correcao_tipos_ponto.py
```
**Por quê**: Demonstra padronização de tipos de registro.

### 7. VIEWS/ROTAS
```
views.py (seções relevantes)
```
**Por quê**: Mostra como os KPIs são calculados e exibidos na interface.

## 📊 ARQUIVOS DE DADOS DE EXEMPLO

### 8. DADOS DE TESTE
Se possível, exporte alguns registros de exemplo:
```sql
-- Exemplo de consulta para exportar dados
SELECT 
    funcionario_id,
    data,
    tipo_registro,
    hora_entrada,
    hora_saida,
    horas_trabalhadas,
    horas_extras,
    total_atraso_horas
FROM registro_ponto 
WHERE funcionario_id IN (SELECT id FROM funcionario LIMIT 3)
ORDER BY data DESC 
LIMIT 50;
```

## 📚 DOCUMENTAÇÃO DE CONTEXTO

### 9. DOCUMENTAÇÃO PRINCIPAL
```
replit.md
RELATORIO_IMPLEMENTACAO_COMPLETA.md
VALIDACAO_CORRECOES_FINALIZADAS.md
```
**Por quê**: Contexto do projeto, mudanças recentes e status atual.

## 🎯 PROMPT SUGERIDO PARA LLM

```
CONTEXTO: Sistema de gestão empresarial (SIGE) com módulo de controle de ponto e KPIs.

PROBLEMA: Preciso analisar e entender completamente como os cálculos de KPIs funcionam.

ARQUIVOS ANEXADOS:
- models.py: Estrutura do banco de dados
- kpis_engine.py: Engine atual de cálculos  
- correcao_completa_kpis.py: Implementação corrigida
- [outros arquivos conforme necessário]

ANÁLISE SOLICITADA:
1. Como são calculados os KPIs principais (horas trabalhadas, custo mão de obra, etc)?
2. Quais tipos de registro de ponto existem e como cada um afeta os cálculos?
3. Onde estão as possíveis inconsistências ou problemas na lógica atual?
4. Como validar se os cálculos estão corretos?

FOQUE EM: Lógica de negócio, fórmulas matemáticas, tipos de registro e suas regras.
```

## 🔧 ORDEM DE ENVIO RECOMENDADA

1. **models.py** (primeiro - base estrutural)
2. **kpis_engine.py** (segundo - lógica atual)  
3. **correcao_completa_kpis.py** (terceiro - melhorias)
4. **teste_validacao_kpis.py** (quarto - validações)
5. **replit.md** (quinto - contexto geral)

## ⚠️ INFORMAÇÕES IMPORTANTES A MENCIONAR

### Tipos de Registro Principais:
- `trabalho_normal`: Trabalho segunda a sexta
- `sabado_trabalhado`: Sábado com 50% extra  
- `domingo_trabalhado`: Domingo com 100% extra
- `falta_injustificada`: Sem custo
- `falta_justificada`: Com custo normal

### KPIs Principais:
- Horas Trabalhadas
- Horas Extras  
- Custo Mão de Obra
- Produtividade
- Absenteísmo
- Eficiência

### Regras de Negócio:
- 22 dias úteis por mês
- 8 horas por dia padrão
- Faltas injustificadas = custo ZERO
- Sábado = 50% adicional
- Domingo/Feriado = 100% adicional