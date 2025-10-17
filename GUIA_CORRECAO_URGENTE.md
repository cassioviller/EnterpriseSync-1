# 🚨 GUIA DE CORREÇÃO URGENTE - SIGE v9.0
**Problemas Críticos com Código Pronto para Correção**

---

## 🔴 PRIORIDADE MÁXIMA (FAZER HOJE)

### 1. CORRIGIR kpis_engine.py (4 problemas)

#### Problema 1 - Linha 70
```python
# ❌ ANTES:
def calcular_valor_hora(funcionario):
    return funcionario.salario / horas_mensais if horas_mensais > 0 else 0.0

# ✅ DEPOIS:
from utils import calcular_valor_hora_periodo
from datetime import datetime

def calcular_valor_hora(funcionario, data_inicio=None, data_fim=None):
    if not data_inicio:
        data_inicio = datetime.now().replace(day=1).date()
    if not data_fim:
        data_fim = datetime.now().date()
    
    return calcular_valor_hora_periodo(funcionario, data_inicio, data_fim)
```

#### Problema 2 - Linha 338
```python
# ❌ ANTES:
valor_por_dia = (valor_hora_normal * horas_mensais) / 22  # 22 dias úteis

# ✅ DEPOIS:
import calendar

ano = data_referencia.year
mes = data_referencia.month
dias_uteis = sum(1 for dia in range(1, calendar.monthrange(ano, mes)[1] + 1)
                 if datetime(ano, mes, dia).weekday() < 5)
valor_por_dia = (valor_hora_normal * horas_mensais) / dias_uteis if dias_uteis > 0 else 0
```

#### Problema 3 - Linha 506
```python
# ❌ ANTES:
valor_hora = funcionario.salario / 220  # 220 horas/mês

# ✅ DEPOIS:
from utils import calcular_valor_hora_periodo

valor_hora = calcular_valor_hora_periodo(
    funcionario=funcionario,
    data_inicio=periodo_inicio,
    data_fim=periodo_fim
)
```

#### Problema 4 - Linha 826
```python
# ❌ ANTES:
valor_hora_base = funcionario.salario / 220

# ✅ DEPOIS:
from utils import calcular_valor_hora_periodo

valor_hora_base = calcular_valor_hora_periodo(
    funcionario=funcionario,
    data_inicio=data_inicio,
    data_fim=data_fim
)
```

---

### 2. CORRIGIR kpis_engine_v8_1.py

#### Problema - Linha 153
```python
# ❌ ANTES:
def valor_hora_funcionario(funcionario):
    return float(funcionario.salario) / 220.0

# ✅ DEPOIS:
from utils import calcular_valor_hora_periodo
from datetime import datetime

def valor_hora_funcionario(funcionario, data_inicio=None, data_fim=None):
    """
    Calcula valor/hora do funcionário considerando dias úteis do período
    """
    if not data_inicio:
        # Primeiro dia do mês atual
        hoje = datetime.now().date()
        data_inicio = hoje.replace(day=1)
    
    if not data_fim:
        # Dia atual
        data_fim = datetime.now().date()
    
    return calcular_valor_hora_periodo(funcionario, data_inicio, data_fim)
```

---

### 3. CORRIGIR contabilidade_views.py (10 funções)

#### Adicionar função get_admin_id no topo do arquivo
```python
# ✅ ADICIONAR NO INÍCIO DO ARQUIVO (após imports):

def get_admin_id():
    """
    Retorna admin_id correto independente do tipo de usuário
    """
    if not current_user.is_authenticated:
        return None
    
    if current_user.tipo_usuario == TipoUsuario.ADMIN:
        return current_user.id
    elif hasattr(current_user, 'admin_id'):
        return current_user.admin_id
    
    return None
```

#### Função 1 - dashboard_contabilidade (linhas 38-40)
```python
# ❌ ANTES:
dre_atual = DREMensal.query.filter_by(
    admin_id=current_user.id,
    mes_referencia=mes_atual
).first()

# ✅ DEPOIS:
admin_id = get_admin_id()
if not admin_id:
    flash('Erro de autenticação', 'danger')
    return redirect(url_for('main.index'))

dre_atual = DREMensal.query.filter_by(
    admin_id=admin_id,
    mes_referencia=mes_atual
).first()
```

#### Função 2 - balanco_patrimonial (linhas 44-46)
```python
# ❌ ANTES:
balanco = BalancoPatrimonial.query.filter_by(
    admin_id=current_user.id,
    data_referencia=data_ref
).first()

# ✅ DEPOIS:
admin_id = get_admin_id()
if not admin_id:
    flash('Erro de autenticação', 'danger')
    return redirect(url_for('main.index'))

balanco = BalancoPatrimonial.query.filter_by(
    admin_id=admin_id,
    data_referencia=data_ref
).first()
```

#### Função 3 - lancamentos_contabeis (linha 49)
```python
# ❌ ANTES:
total = LancamentoContabil.query.filter_by(admin_id=current_user.id).count()

# ✅ DEPOIS:
admin_id = get_admin_id()
if not admin_id:
    flash('Erro de autenticação', 'danger')
    return redirect(url_for('main.index'))

total = LancamentoContabil.query.filter_by(admin_id=admin_id).count()
```

#### Aplicar o MESMO padrão em:
- Linha 72: `PlanoContas.query.filter_by(admin_id=current_user.id)`
- Linha 89: `LancamentoContabil.query.filter_by(admin_id=current_user.id)`
- Linha 110: Queries com `current_user.id`
- Linha 143: Queries com `current_user.id`
- Linha 159: Queries com `current_user.id`
- Linha 187: Queries com `current_user.id`
- Linha 213: Queries com `current_user.id`

**PADRÃO PARA TODAS:**
```python
admin_id = get_admin_id()
if not admin_id:
    flash('Erro de autenticação', 'danger')
    return redirect(url_for('main.index'))

# Substituir current_user.id por admin_id em TODAS as queries
```

---

### 4. CORRIGIR services/folha_service.py

#### Problema 1 - Linha 128
```python
# ❌ ANTES:
valor_hora = config.valor_hora if config else (salario_base / 220)

# ✅ DEPOIS:
from utils import calcular_valor_hora_periodo

if config and config.valor_hora:
    valor_hora = config.valor_hora
else:
    valor_hora = calcular_valor_hora_periodo(
        funcionario=funcionario,
        data_inicio=data_inicio,
        data_fim=data_fim
    )
```

#### Problema 2 - Linha 135
```python
# ❌ ANTES:
valor_hora_normal = salario_base / 220

# ✅ DEPOIS:
from utils import calcular_valor_hora_periodo

valor_hora_normal = calcular_valor_hora_periodo(
    funcionario=funcionario,
    data_inicio=data_inicio,
    data_fim=data_fim
)
```

---

## 🟠 PRIORIDADE ALTA (ESTA SEMANA)

### 5. CORRIGIR relatorios_funcionais.py

#### Problema - Linha 135
```python
# ❌ ANTES:
valor_hora = (r.funcionario.salario / 220) * 1.5 if r.funcionario.salario else 0

# ✅ DEPOIS:
from utils import calcular_valor_hora_periodo

if r.funcionario and r.funcionario.salario:
    valor_hora_normal = calcular_valor_hora_periodo(
        funcionario=r.funcionario,
        data_inicio=periodo_inicio,
        data_fim=periodo_fim
    )
    valor_hora = valor_hora_normal * 1.5  # 50% adicional
else:
    valor_hora = 0
```

---

### 6. CORRIGIR event_manager.py

#### Problema - Linha 193
```python
# ❌ ANTES:
salario_hora = salario_mensal / 220 if salario_mensal > 0 else 0

# ✅ DEPOIS:
from utils import calcular_valor_hora_periodo

if funcionario and salario_mensal > 0:
    salario_hora = calcular_valor_hora_periodo(
        funcionario=funcionario,
        data_inicio=data_inicio,
        data_fim=data_fim
    )
else:
    salario_hora = 0
```

---

### 7. CORRIGIR calculadora_obra.py

#### Problema - Linha 72
```python
# ❌ ANTES:
def obter_valor_hora(funcionario):
    return funcionario.salario / 220  # 220h padrão

# ✅ DEPOIS:
from utils import calcular_valor_hora_periodo
from datetime import datetime

def obter_valor_hora(funcionario, data_inicio=None, data_fim=None):
    """
    Obtém valor/hora do funcionário considerando dias úteis do período
    """
    if not data_inicio:
        hoje = datetime.now().date()
        data_inicio = hoje.replace(day=1)
    
    if not data_fim:
        data_fim = datetime.now().date()
    
    return calcular_valor_hora_periodo(funcionario, data_inicio, data_fim)
```

---

### 8. REFATORAR TRATAMENTO DE EXCEÇÕES

#### Criar arquivo exceptions.py (NOVO ARQUIVO)
```python
"""
Exceções customizadas do SIGE
"""

class SIGEException(Exception):
    """Exceção base do SIGE"""
    pass

class DatabaseError(SIGEException):
    """Erro de banco de dados"""
    pass

class ValidationError(SIGEException):
    """Erro de validação de dados"""
    pass

class BusinessLogicError(SIGEException):
    """Erro de regra de negócio"""
    pass

class AuthenticationError(SIGEException):
    """Erro de autenticação"""
    pass

class MultiTenancyError(SIGEException):
    """Erro de isolamento multi-tenant"""
    pass
```

#### Padrão para substituir em views.py (194 ocorrências)
```python
# ❌ ANTES:
try:
    # código
except Exception as e:
    print(f"Erro: {e}")
    return redirect(url_for('main.index'))

# ✅ DEPOIS:
from exceptions import DatabaseError, ValidationError, BusinessLogicError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging

logger = logging.getLogger(__name__)

try:
    # código
except IntegrityError as e:
    db.session.rollback()
    logger.error(f"Erro de integridade no banco: {e}", exc_info=True)
    flash('Erro: Dados já existentes ou violação de chave única', 'error')
    return redirect(request.referrer or url_for('main.index'))

except SQLAlchemyError as e:
    db.session.rollback()
    logger.error(f"Erro de banco de dados: {e}", exc_info=True)
    flash('Erro ao acessar banco de dados. Tente novamente.', 'error')
    return redirect(url_for('main.index'))

except ValueError as e:
    logger.warning(f"Erro de validação: {e}")
    flash(f'Dados inválidos: {e}', 'warning')
    return redirect(request.referrer or url_for('main.index'))

except BusinessLogicError as e:
    logger.info(f"Erro de negócio: {e}")
    flash(str(e), 'info')
    return redirect(request.referrer or url_for('main.index'))
```

#### Exemplo específico - views.py linha 182
```python
# ❌ ANTES (LINHA 182):
except:
    pass

# ✅ DEPOIS:
except (ValueError, AttributeError) as e:
    logger.warning(f"Erro ao processar KPI: {e}")
    # Retornar valor padrão ou None
    return None
```

---

## 🟡 MELHORIAS (PRÓXIMA SEMANA)

### 9. OTIMIZAR Query N+1 - views.py linha 164

```python
# ❌ ANTES (LINHA 164):
for registro in registros_obra:
    funcionario = Funcionario.query.get(registro.funcionario_id)
    if funcionario and funcionario.salario:
        # processar

# ✅ DEPOIS:
from sqlalchemy.orm import joinedload

# Carregar tudo de uma vez
registros_obra = RegistroPonto.query.filter(
    RegistroPonto.obra_id == obra.id,
    RegistroPonto.data >= data_inicio,
    RegistroPonto.data <= data_fim
).options(
    joinedload(RegistroPonto.funcionario_ref)  # Eager loading
).all()

# Agora funciona sem query adicional
for registro in registros_obra:
    funcionario = registro.funcionario_ref  # Já está carregado!
    if funcionario and funcionario.salario:
        # processar
```

---

### 10. LIMPAR utils.py (remover versões antigas)

#### Remover linhas 494, 599, 665, 725
```python
# ❌ REMOVER:
salario_hora = funcionario.salario / 220

# ✅ MANTER (linha 566):
def calcular_valor_hora_periodo(funcionario, data_inicio, data_fim):
    """Esta é a função correta!"""
    # ... implementação existente
    return funcionario.salario / horas_mensais if horas_mensais > 0 else 0.0
```

---

## 📋 CHECKLIST DE EXECUÇÃO

### Fase 1 - HOJE (2-3 horas)
```
[ ] 1. Backup do banco de dados
[ ] 2. Criar branch: git checkout -b fix/security-audit-v9.0
[ ] 3. Corrigir kpis_engine.py (4 problemas)
[ ] 4. Corrigir kpis_engine_v8_1.py (1 problema)
[ ] 5. Corrigir contabilidade_views.py (10 funções)
[ ] 6. Rodar testes: pytest tests/
[ ] 7. Testar manualmente: login funcionário + admin
[ ] 8. Commit: git commit -m "fix: correção cálculos hardcoded e multi-tenancy"
```

### Fase 2 - ESTA SEMANA (2-3 dias)
```
[ ] 9. Corrigir services/folha_service.py
[ ] 10. Corrigir relatorios_funcionais.py
[ ] 11. Corrigir event_manager.py
[ ] 12. Corrigir calculadora_obra.py
[ ] 13. Criar exceptions.py
[ ] 14. Refatorar 50 primeiros "except Exception" em views.py
[ ] 15. Rodar testes + code review
[ ] 16. Commit: git commit -m "fix: cálculos e tratamento de exceções"
```

### Fase 3 - PRÓXIMA SEMANA
```
[ ] 17. Otimizar Query N+1
[ ] 18. Limpar utils.py
[ ] 19. Remover/corrigir propostas_views.py
[ ] 20. Configurar Sentry/Rollbar
[ ] 21. Adicionar testes multi-tenancy
[ ] 22. Deploy staging
[ ] 23. Validação usuários beta
[ ] 24. Deploy produção
```

---

## 🧪 TESTES DE VALIDAÇÃO

### Teste 1: Multi-Tenancy Contabilidade
```python
# tests/test_contabilidade_multitenancy.py

def test_funcionario_nao_ve_dados_outra_empresa():
    # Login como funcionário da empresa A
    funcionario_a = login_funcionario(empresa_a)
    
    # Acessar contabilidade
    response = client.get('/contabilidade/dashboard')
    
    # Não deve ver dados da empresa B
    assert 'Empresa B' not in response.data
    assert empresa_a.razao_social in response.data
```

### Teste 2: Cálculo Correto de Valor Hora
```python
# tests/test_calculos_precisos.py

def test_valor_hora_considera_dias_uteis():
    from utils import calcular_valor_hora_periodo
    from datetime import date
    
    func = criar_funcionario(salario=5000)
    
    # Fevereiro 2025 tem 20 dias úteis
    valor = calcular_valor_hora_periodo(
        func, 
        date(2025, 2, 1), 
        date(2025, 2, 28)
    )
    
    # 5000 / (20 dias * 8h) = 31.25
    assert valor == 31.25
    
    # NÃO deve ser 5000/220 = 22.72
    assert valor != 22.72
```

---

## 🚀 COMANDOS RÁPIDOS

### Executar Correções
```bash
# 1. Criar branch
git checkout -b fix/security-audit-v9.0

# 2. Fazer correções (usar código acima)

# 3. Testar
pytest tests/ -v

# 4. Commit
git add .
git commit -m "fix: correção crítica segurança multi-tenant e cálculos"

# 5. Push
git push origin fix/security-audit-v9.0
```

### Validar em Staging
```bash
# Deploy staging
git checkout staging
git merge fix/security-audit-v9.0
git push origin staging

# Verificar logs
tail -f /var/log/sige/app.log | grep ERROR
```

---

## 📞 SUPORTE

**Dúvidas?** Consulte:
- Relatório completo: `RELATORIO_AUDITORIA_SEGURANCA_v9.0.md`
- Resumo: `RESUMO_EXECUTIVO_AUDITORIA.md`
- Documentação: `/docs/security/multi-tenancy.md`

**Emergência?** Rollback:
```bash
git checkout main
git revert HEAD
git push origin main --force
```
