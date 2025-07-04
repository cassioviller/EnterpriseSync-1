# RELATÓRIO TÉCNICO COMPLETO - SISTEMA SIGE v3.0
## Sistema Integrado de Gestão Empresarial - Estruturas do Vale

**Data:** 04 de Julho de 2025
**Versão:** 3.0 
**Tecnologia:** Flask + SQLAlchemy + PostgreSQL + Bootstrap 5

---

## 1. VISÃO GERAL DO SISTEMA

O SIGE é um sistema web completo de gestão empresarial desenvolvido especificamente para empresas de construção civil. O sistema gerencia funcionários, obras, veículos, controle de ponto, alimentação e relatórios operacionais.

### Características Principais:
- **Linguagem:** Português brasileiro
- **Setor:** Construção civil e engenharia
- **Funcionalidades:** Gestão de RH, controle de ponto, obras, veículos, custos e relatórios
- **Interface:** Responsiva com Bootstrap 5 (tema escuro)
- **Autenticação:** Sistema de login com Flask-Login

---

## 2. ARQUITETURA TÉCNICA

### 2.1 Stack Tecnológica
- **Backend:** Flask (Python)
- **Database:** PostgreSQL com SQLAlchemy ORM
- **Frontend:** Bootstrap 5 + JavaScript vanilla + Chart.js
- **Autenticação:** Flask-Login
- **Formulários:** Flask-WTF + WTForms
- **Servidor:** Gunicorn (produção)

### 2.2 Estrutura de Arquivos
```
/
├── app.py              # Configuração principal Flask
├── main.py             # Ponto de entrada
├── models.py           # Modelos SQLAlchemy
├── views.py            # Rotas e controladores
├── forms.py            # Formulários WTF
├── auth.py             # Sistema de autenticação
├── utils.py            # Funções auxiliares
├── kpis_engine_v3.py   # Engine de cálculo KPIs v3.0
├── templates/          # Templates Jinja2
├── static/             # CSS, JS, imagens
└── *.py               # Scripts de população/migração
```

---

## 3. MODELO DE DADOS (BANCO DE DADOS)

### 3.1 Tabelas Principais

#### **Usuario** (Sistema de Login)
```sql
- id (PK)
- username (unique)
- email (unique) 
- password_hash
- nome
- ativo
- created_at
```

#### **Funcionario** (Funcionários)
```sql
- id (PK)
- codigo (unique) # F0001, F0002, etc.
- nome
- cpf (unique)
- rg, data_nascimento, endereco, telefone, email
- data_admissao
- salario
- ativo
- foto
- departamento_id (FK)
- funcao_id (FK)
- horario_trabalho_id (FK)
- created_at
```

#### **HorarioTrabalho** (Horários de Trabalho)
```sql
- id (PK)
- nome
- entrada (time)
- saida_almoco (time)
- retorno_almoco (time)
- saida (time)
- dias_semana # "1,2,3,4,5"
- created_at
```

#### **RegistroPonto** (Controle de Ponto)
```sql
- id (PK)
- funcionario_id (FK)
- obra_id (FK) # opcional
- data
- hora_entrada, hora_saida
- hora_almoco_saida, hora_almoco_retorno
- horas_trabalhadas (calculado)
- horas_extras (calculado)
- minutos_atraso_entrada (calculado)
- minutos_atraso_saida (calculado)
- total_atraso_minutos (calculado)
- total_atraso_horas (calculado)
- observacoes
- created_at
```

#### **RegistroAlimentacao** (Alimentação)
```sql
- id (PK)
- funcionario_id (FK)
- obra_id (FK) # opcional
- restaurante_id (FK) # opcional
- data
- tipo # marmita, refeicao_local, cafe, jantar, lanche, outros
- valor
- observacoes
- created_at
```

#### **Obra** (Projetos/Obras)
```sql
- id (PK)
- nome
- endereco
- data_inicio, data_previsao_fim
- orcamento
- status # Em andamento, Concluída, Pausada, Cancelada
- responsavel_id (FK)
- created_at
```

#### **Veiculo** (Frota)
```sql
- id (PK)
- placa (unique)
- marca, modelo, ano
- tipo # Carro, Caminhão, Moto, Van, Outro
- status # Disponível, Em uso, Manutenção, Indisponível
- km_atual
- data_ultima_manutencao, data_proxima_manutencao
- created_at
```

#### **Ocorrencia** (Faltas/Licenças)
```sql
- id (PK)
- funcionario_id (FK)
- tipo_ocorrencia # Atestado Médico, Falta Justificada, Licença Médica, etc.
- data_inicio, data_fim
- descricao
- status # Pendente, Aprovado, Rejeitado
- created_at
```

### 3.2 Relacionamentos
- Funcionario → HorarioTrabalho (N:1)
- Funcionario → Departamento (N:1)
- Funcionario → Funcao (N:1)
- RegistroPonto → Funcionario (N:1)
- RegistroPonto → Obra (N:1)
- RegistroAlimentacao → Funcionario (N:1)
- RegistroAlimentacao → Obra (N:1)
- RegistroAlimentacao → Restaurante (N:1)
- Ocorrencia → Funcionario (N:1)

---

## 4. SISTEMA DE KPIs v3.0

### 4.1 Engine de Cálculo (kpis_engine_v3.py)

O sistema implementa um engine específico para cálculo de KPIs seguindo regras de negócio da construção civil:

#### **Função Principal:** `calcular_kpis_funcionario_v3(funcionario_id, data_inicio, data_fim)`

### 4.2 Os 10 KPIs Calculados (Layout 4-4-2)

#### **Primeira Linha (4 KPIs):**
1. **Horas Trabalhadas**
   - Fonte: `RegistroPonto.horas_trabalhadas`
   - Cálculo: `SUM(horas_trabalhadas) WHERE hora_entrada IS NOT NULL`

2. **Horas Extras**
   - Fonte: `RegistroPonto.horas_extras`
   - Cálculo: `SUM(horas_extras) WHERE horas_extras > 0`

3. **Faltas**
   - Fonte: Calculado
   - Cálculo: `dias_úteis - dias_com_presença`
   - Regra: Dias úteis sem registro de entrada

4. **Atrasos (Horas)**
   - Fonte: `RegistroPonto.total_atraso_horas`
   - Cálculo: `SUM(total_atraso_horas) WHERE total_atraso_horas > 0`
   - Regra: Entrada tardia + saída antecipada

#### **Segunda Linha (4 KPIs):**
5. **Produtividade (%)**
   - Cálculo: `(horas_trabalhadas / horas_esperadas) × 100`
   - Horas esperadas: `dias_úteis × 8`

6. **Absenteísmo (%)**
   - Cálculo: `(faltas / dias_úteis) × 100`

7. **Média Diária**
   - Cálculo: `horas_trabalhadas / dias_com_presença`

8. **Horas Perdidas**
   - Cálculo: `(faltas × 8) + total_atrasos_horas`
   - Regra: Faltas em horas + atrasos

#### **Terceira Linha (2 KPIs):**
9. **Custo Mão de Obra (R$)**
   - Cálculo: `(horas_trabalhadas + faltas_justificadas × 8) × salario_hora`
   - Salário hora: `salario / 220`
   - Regra: Inclui trabalho real + faltas justificadas

10. **Custo Alimentação (R$)**
    - Fonte: `RegistroAlimentacao.valor`
    - Cálculo: `SUM(valor)`

### 4.3 Lógica de Dias Úteis
- **Função:** `calcular_dias_uteis(data_inicio, data_fim)`
- **Regra:** Segunda a sexta, exceto feriados nacionais
- **Feriados 2025:** Incluídos no cálculo

### 4.4 Cálculo Automático de Atrasos
- **Função:** `atualizar_calculos_ponto(registro_ponto_id)`
- **Trigger:** Executado ao salvar/editar registro de ponto
- **Lógica:** Compara horários reais vs. HorarioTrabalho do funcionário

---

## 5. INTERFACE DE USUÁRIO

### 5.1 Layout Principal
- **Framework:** Bootstrap 5 (tema escuro)
- **Tema:** `https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css`
- **Cores:** Paleta escura com acentos azuis
- **Responsivo:** Mobile-first design

### 5.2 Navegação
```
Header:
- Logo SIGE
- Dashboard
- Funcionários
- Obras  
- Veículos
- Ponto
- Alimentação
- Relatórios
- Logout
```

### 5.3 Página de Perfil do Funcionário
**Rota:** `/funcionarios/{id}/perfil`

#### **Seções:**
1. **Cabeçalho:** Foto, nome, código, cargo
2. **Filtros:** Botões rápidos (7 dias, 30 dias, último mês, etc.)
3. **Indicadores de Desempenho:** Layout 4-4-2 com 10 KPIs
4. **Controle de Ponto:** Tabela com histórico
5. **Alimentação:** Registros de gastos
6. **Ocorrências:** Faltas, licenças, atestados

#### **Filtros Implementados:**
- 7 dias, 30 dias, último mês
- Trimestre, semestre, ano
- Período customizado

---

## 6. FUNCIONALIDADES PRINCIPAIS

### 6.1 Gestão de Funcionários
- Cadastro completo com foto
- Códigos únicos (F0001, F0002, etc.)
- Vinculação a departamentos, funções, horários
- Perfil individual com KPIs

### 6.2 Controle de Ponto
- Registro manual de entrada/saída
- Controle de almoço
- Cálculo automático de horas e atrasos
- Histórico completo por funcionário

### 6.3 Gestão de Obras
- Cadastro de projetos
- Controle de orçamento e prazo
- Vinculação de funcionários e veículos
- Status de acompanhamento

### 6.4 Alimentação
- Registro por funcionário
- Tipos: marmita, refeição local, lanches
- Vinculação a obras e restaurantes
- Lançamento múltiplo

### 6.5 Relatórios
- Dashboard executivo
- Filtros por período
- Gráficos interativos (Chart.js)
- Exportação CSV

---

## 7. REGRAS DE NEGÓCIO ESPECÍFICAS

### 7.1 Cálculo de Faltas
- **Regra:** Dias úteis sem registro de entrada
- **Não conta:** Sábados, domingos, feriados
- **Justificadas:** Ocorrências aprovadas não afetam produtividade

### 7.2 Cálculo de Atrasos
- **Entrada:** Horário real > horário esperado
- **Saída:** Horário real < horário esperado
- **Unidade:** Convertido para horas (não minutos)

### 7.3 Cálculo de Custos
- **Mão de obra:** Trabalho real + faltas justificadas
- **Alimentação:** Soma simples dos valores
- **Não inclui:** Faltas injustificadas no custo

### 7.4 Horários de Trabalho
- **Flexível:** Cada funcionário pode ter horário diferente
- **Padrão:** 8 horas/dia, segunda a sexta
- **Almoço:** Descontado do tempo trabalhado

---

## 8. FLUXO DE DADOS

### 8.1 Cadastro de Ponto
1. Usuário registra entrada/saída
2. Sistema valida horários
3. Calcula horas trabalhadas e extras
4. Calcula atrasos comparando com HorarioTrabalho
5. Atualiza campos calculados
6. Atualiza KPIs em tempo real

### 8.2 Visualização de KPIs
1. Usuário acessa perfil do funcionário
2. Sistema aplica filtros de período
3. Engine v3.0 calcula todos os KPIs
4. Interface exibe layout 4-4-2
5. Dados atualizados em tempo real

---

## 9. CONFIGURAÇÃO E DEPLOYMENT

### 9.1 Variáveis de Ambiente
```bash
DATABASE_URL=postgresql://...
SESSION_SECRET=...
PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
```

### 9.2 Comando de Execução
```bash
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
```

### 9.3 Dependências Principais
```
Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF
WTForms, Werkzeug, SQLAlchemy
psycopg2-binary, gunicorn
```

---

## 10. PROBLEMAS CONHECIDOS E SOLUÇÕES

### 10.1 Relacionamentos SQLAlchemy
- **Problema:** Warnings sobre relacionamentos sobrepostos
- **Status:** Funcional, mas gera warnings no log
- **Solução:** Adicionar parâmetro `overlaps` nos relacionamentos

### 10.2 Cálculo de Atrasos
- **Problema Anterior:** Tentativa de acessar campos inexistentes
- **Solução:** Usar relacionamento `funcionario.horario_trabalho.entrada`
- **Status:** Resolvido na v3.0

### 10.3 Performance
- **Otimização:** Cálculos pré-processados na tabela RegistroPonto
- **Cache:** KPIs calculados sob demanda
- **Índices:** Necessários em data, funcionario_id

---

## 11. ROADMAP E MELHORIAS

### 11.1 Próximas Implementações
- Dashboard executivo consolidado
- Relatórios avançados por obra
- Integração com folha de pagamento
- App mobile para registro de ponto

### 11.2 Otimizações Técnicas
- Cache de KPIs
- Índices de banco otimizados
- Compressão de assets
- PWA para uso offline

---

## 12. GUIA PARA PROMPTS EFICAZES

### 12.1 Contexto Essencial
Ao solicitar modificações, sempre mencione:
- **Versão:** SIGE v3.0
- **Área:** Funcionários, Obras, Veículos, Ponto, Alimentação
- **Contexto:** Construção civil, português brasileiro

### 12.2 Exemplos de Prompts Eficazes

**✅ BOM:**
"No SIGE v3.0, preciso modificar o cálculo de horas extras na página de perfil do funcionário. Atualmente usa 8 horas como base, mas quero usar o horário de trabalho específico do funcionário da tabela HorarioTrabalho."

**❌ RUIM:**
"Arrumar as horas extras."

### 12.3 Informações Críticas
- **Modelos:** Sempre referenciar campos corretos (ex: `funcionario.horario_trabalho.entrada`)
- **Engine:** Usar `kpis_engine_v3.py` para cálculos
- **Layout:** Manter layout 4-4-2 dos KPIs
- **Dados:** Usar dados reais, nunca mock

### 12.4 Áreas Sensíveis
- **Cálculos de KPIs:** Seguir regras de negócio específicas
- **Relacionamentos:** Respeitar estrutura do banco
- **Interface:** Manter consistência com Bootstrap tema escuro
- **Português:** Manter terminologia da construção civil

---

**FIM DO RELATÓRIO**

*Este documento serve como referência completa para entendimento do sistema SIGE v3.0 e criação de prompts eficazes para desenvolvimento futuro.*