# Plano de Implementação — Fatia 1: Resultado por Atividade (só Mão de Obra) + alarme

> Data: 2026-06-15. Branch: `design/espinha-financeira-obra`.
> Spec mestre: `docs/superpowers/specs/2026-06-14-espinha-financeira-obra-design.md` (§ Fatia 1).
> Mapa de código: `docs/superpowers/specs/2026-06-14-mapa-codigo-cronograma-custo-medicao.md`.
> Glossário: `CONTEXT.md`.
> **Integração:** esta fatia é a primeira da espinha; segue o **plano-mestre**
> (`2026-06-15-espinha-financeira-plano-mestre.md`) — em especial DC1 (read-model), DC5 (custo
> orçado sobre snapshot), DC6 (helper de rateio reutilizável) e DC8 (peso da medição). As funções
> aqui são desenhadas para a Fatia 2 estender **sem quebrar assinatura** (ver "Pontos de extensão").
> **Premissa deste plano: o implementador NÃO conhece este código.** Cada passo traz o código
> completo, o caminho exato do arquivo e o comando exato. Nada de "TODO", "similar à Task N" ou
> "tratar erros adequadamente".

---

## Atualização pós-grill (2026-06-15) — status e deltas

**Implementado e commitado:** Fase A (bug RDO), Fase B (read-model), Fase C (tela). A **Fase D**
(habilitação) foi substituída pelo **importador auto-wiring** `services/importar_obra_completa.py`
+ botão "Importar como Obra" na UI (ver plano-mestre DC11, ADR 0004, ADR 0005). A Baia foi
materializada (obra 655).

**Confirmado correto no grill (sem refactor):** o orçado (baseline) é lido do
`PropostaItem.composicao_snapshot` — **congelado**, não acompanha revisões (ADR 0005, _Orçado
(baseline)_ no CONTEXT). É o que a Fatia 1 já faz. O Orçamento operacional **não** é a fonte do
baseline; logo o importador **não** precisa chamar `garantir_operacional` para a espinha.

**Deltas pendentes decididos no grill (alinhar código às decisões):**
1. **Multi-atividade real (corrige o 1:1 — ADR 0004)** — o principal. O 1:1 da Baia foi fallback por
   falta de detalhamento. Construir `CronogramaTemplate` por serviço a partir do
   `2026-06-14-cronograma-refinado-pareto-baia-rev10.md` (30 atividades) com `peso_medicao`
   explícito (migration 193); o importador materializa as N atividades e grava o _Peso da medição_
   do template. **Re-materializar a obra 655** para multi-atividade — possível porque ela ainda
   **não tem RDO apontado** (granularidade não congelou). Onde faltar template, o 1:1 segue fallback.
2. **Proposta de importação marcada** (ADR 0005): coluna `propostas_comerciais.origem` (migration
   193); o importador seta `origem='importacao_obra'`; listagem/KPIs comerciais filtram.
3. **Reconciliar obra 655** (pré-decisão): passo idempotente — setar `proposta.origem`; não apagar.

---

## 0. Objetivo e contexto (leia antes de começar)

O SIGE é um app **Flask + SQLAlchemy** (Postgres). A obra é executada por um **cronograma** de
atividades (`TarefaCronograma`). Hoje o sistema já calcula, por atividade, **a venda e o avanço
físico**; o que falta é o **custo real** e, com ele, o **Resultado** (Valor agregado − Custo
incorrido) e o **alarme de produtividade**.

Esta fatia entrega, ponta a ponta, para uma obra rodando no cronograma:

- **Valor agregado por atividade** (a receber pela produção já feita).
- **Custo incorrido de MO por atividade** (rateio do custo onerado real do dia pelas horas
  apontadas na atividade).
- **Resultado realizado** = Valor agregado − Custo MO (só MO nesta fatia).
- **Alarme em R$** (custo MO real vs. orçado-para-o-avanço) e **índice em horas** (refino, só
  onde a MO foi orçada em hora).
- **Tela** "Resultado por Atividade" da obra, com rollup por Serviço e Obra.

**Decisão central (D1):** o custo de MO por atividade é **computado num read-model**, não gravado.
Fonte: `RDOCustoDiario.custo_total_dia` (custo onerado já persistido por funcionário/RDO) rateado
pelas horas que o funcionário lançou em cada atividade (`RDOMaoObra.horas_trabalhadas` por
`tarefa_cronograma_id`). Não há migration nesta fatia.

**Pré-requisitos que fazem parte da fatia:**
1. Corrigir o **bug da edição do RDO** que perde o vínculo atividade↔funcionário.
2. Materializar o cronograma da obra Baia e colocá-la em `versao_sistema='v2'` (habilitação).

---

## 1. Arquitetura e mapa de arquivos

### Tabelas existentes que vamos LER (nenhuma alteração de schema)
| Modelo | Tabela | Campos usados | `models.py` |
|---|---|---|---|
| `TarefaCronograma` | `tarefa_cronograma` | `id, obra_id, tarefa_pai_id, quantidade_total, percentual_concluido, servico_id, nome_tarefa, duracao_dias` | 4836 |
| `ItemMedicaoComercial` | `item_medicao_comercial` | `id, obra_id, valor_comercial, servico_id, quantidade, proposta_item_id` | 5185 |
| `ItemMedicaoCronogramaTarefa` | `item_medicao_cronograma_tarefa` | `item_medicao_id, cronograma_tarefa_id, peso` | 5218 |
| `PropostaItem` | `proposta_itens` | `id, composicao_snapshot, quantidade` | 3153 |
| `RDOMaoObra` | `rdo_mao_obra` | `rdo_id, funcionario_id, tarefa_cronograma_id, horas_trabalhadas` | 910 |
| `RDOCustoDiario` | `rdo_custo_diario` | `rdo_id, funcionario_id, custo_total_dia, data, tipo_lancamento` | 961 |
| `RDO` | `rdo` | `id, obra_id, data_relatorio` | 827 |

**Cadeia atividade → orçamento (confirmada por leitura de código):**
`TarefaCronograma.id` = `ItemMedicaoCronogramaTarefa.cronograma_tarefa_id` →
`ItemMedicaoCronogramaTarefa.item_medicao_id` = `ItemMedicaoComercial.id` →
`ItemMedicaoComercial.proposta_item_id` = `PropostaItem.id` →
`PropostaItem.composicao_snapshot` (lista JSON com as linhas da composição).

**Formato de uma linha de `composicao_snapshot`** (chaves relevantes):
`{'tipo': 'MAO_OBRA'|'MATERIAL'|..., 'unidade': 'h'|'m2'|..., 'coeficiente': float,
'subtotal_unitario': float, ...}`. `subtotal_unitario` = custo **por unidade de serviço**
(coef × preço). `tipo` é sempre MAIÚSCULO; `unidade` minúsculo (`'h'`).

### Arquivos CRIADOS
- `services/resultado_atividade_service.py` — read-model (funções puras + leitura). **Coração da fatia.**
- `tests/test_resultado_atividade_service.py` — testes unitários do serviço.
- `tests/test_rdo_edicao_preserva_tarefa.py` — regressão do bug de edição.
- `resultado_views.py` — blueprint da tela "Resultado por Atividade".
- `templates/resultado/por_atividade.html` — a tela.
- `scripts/materializar_baia_rev10.py` — habilitação (materializa cronograma + flag v2).

### Arquivos MODIFICADOS
- `templates/rdo/editar_rdo.html` — corrigir o nome do campo emitido (linha ~2454).
- `rdo_editar_sistema.py` — parsear `cron_tarefa_*` e gravar `tarefa_cronograma_id` na edição.
- `main.py` — registrar `resultado_bp`.
- `templates/.../<detalhe da obra>` — link/aba para a nova tela (Task 14).

### Como rodar os testes
```
python -m pytest tests/test_resultado_atividade_service.py -x
```
Convenção da suíte (ver `tests/test_custo_diario.py`): fixture `scope='module'` cria o admin
(`versao_sistema='v2'`) e a obra; builders inline `_func/_rdo/_mo`; tudo dentro de
`with app.app_context():`; sufixos únicos por execução; `pytest.approx(x, abs=0.02)` para floats.

---

## FASE A — Corrigir o bug da edição do RDO (regressão primeiro)

> Por quê primeiro: o read-model de custo depende de `RDOMaoObra.tarefa_cronograma_id`. Hoje a
> **edição** de um RDO V2 apaga esse vínculo (`rdo_editar_sistema.py:374` trata o campo de
> cronograma como subatividade). Se não corrigirmos, todo custo-por-atividade se corrompe ao editar.
> O caminho de **salvar novo** (`views/rdo.py:salvar_rdo_flexivel`) já está correto e é o espelho.

### Task A1 — Teste de regressão (RED): editar um RDO preserva `tarefa_cronograma_id`

- [ ] Criar `tests/test_rdo_edicao_preserva_tarefa.py` com o conteúdo abaixo (completo):

```python
"""Regressão do bug: editar um RDO V2 perdia RDOMaoObra.tarefa_cronograma_id
(rdo_editar_sistema.py tratava o campo de cronograma como subatividade).

O POST de edição emite, para equipe de cronograma, campos no formato
    cron_tarefa_<tarefa_id>_func_<func_id>_horas = <horas>
(espelho de views/rdo.py:salvar_rdo_flexivel). Após salvar a edição, a linha
RDOMaoObra correspondente deve ter tarefa_cronograma_id == tarefa.id.
"""
import os
import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (
    Usuario, TipoUsuario, Funcionario, Obra, Cliente,
    RDO, RDOMaoObra, TarefaCronograma,
)
from werkzeug.security import generate_password_hash


def _suffix():
    return datetime.utcnow().strftime('%H%M%S%f')


@pytest.fixture(scope='module', autouse=True)
def ambiente():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        s = _suffix()
        admin = Usuario(
            username=f'edit_rdo_{s}', email=f'edit_rdo_{s}@sige.test',
            nome='Edit RDO', tipo_usuario=TipoUsuario.ADMIN,
            password_hash=generate_password_hash('Test@1234'),
            versao_sistema='v2', ativo=True,
        )
        db.session.add(admin); db.session.flush()
        cli = Cliente(nome=f'CLI-ED-{s}', admin_id=admin.id)
        db.session.add(cli); db.session.flush()
        obra = Obra(
            nome=f'Obra ED {s}', codigo=f'OED{s[:6]}',
            data_inicio=date(2026, 1, 1), admin_id=admin.id,
            cliente_id=cli.id, valor_contrato=100000,
        )
        db.session.add(obra); db.session.flush()
        tarefa = TarefaCronograma(
            obra_id=obra.id, nome_tarefa='Alvenaria', ordem=1,
            duracao_dias=5, quantidade_total=100.0, percentual_concluido=0.0,
            admin_id=admin.id,
        )
        db.session.add(tarefa)
        func = Funcionario(
            nome=f'Func ED {s}', cpf=f'222{s}'.ljust(14, '0')[:14],
            codigo=f'FE{s[:8]}', data_admissao=date(2025, 1, 1),
            admin_id=admin.id, tipo_remuneracao='salario', salario=3000.0,
            ativo=True,
        )
        db.session.add(func)
        rdo = RDO(
            numero_rdo=f'RDO-ED-{s}', obra_id=obra.id,
            data_relatorio=date(2026, 2, 10), admin_id=admin.id,
            status='Finalizado', criado_por_id=admin.id,
        )
        db.session.add(rdo); db.session.commit()

        # linha de MO já existente, ligada à tarefa (estado pré-edição correto)
        mo = RDOMaoObra(
            rdo_id=rdo.id, funcionario_id=func.id, funcao_exercida='Pedreiro',
            horas_trabalhadas=8.0, admin_id=admin.id,
            subatividade_id=None, tarefa_cronograma_id=tarefa.id,
        )
        db.session.add(mo); db.session.commit()

        ambiente.admin_id = admin.id
        ambiente.obra_id = obra.id
        ambiente.rdo_id = rdo.id
        ambiente.tarefa_id = tarefa.id
        ambiente.func_id = func.id
        yield


def test_edicao_preserva_tarefa_cronograma_id():
    with app.app_context():
        admin = db.session.get(Usuario, ambiente.admin_id)
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin.id)
                sess['_fresh'] = True
            resp = c.post(
                f'/rdo/editar/{ambiente.rdo_id}',
                data={
                    'data_relatorio': '2026-02-10',
                    'obra_id': str(ambiente.obra_id),
                    f'cron_tarefa_{ambiente.tarefa_id}_func_{ambiente.func_id}_horas': '8',
                },
                follow_redirects=False,
            )
        assert resp.status_code in (200, 302), resp.status_code

        linhas = RDOMaoObra.query.filter_by(rdo_id=ambiente.rdo_id).all()
        assert len(linhas) >= 1
        ligadas = [m for m in linhas if m.tarefa_cronograma_id == ambiente.tarefa_id]
        assert ligadas, (
            'edição apagou tarefa_cronograma_id — bug não corrigido. '
            f'linhas={[(m.tarefa_cronograma_id, m.subatividade_id) for m in linhas]}'
        )
        assert all(m.subatividade_id is None for m in ligadas)
```

- [ ] Rodar e **confirmar que falha** (RED):
  `python -m pytest tests/test_rdo_edicao_preserva_tarefa.py -x`
  Esperado: falha porque a edição grava o vínculo como subatividade (ou perde a linha).
- [ ] Confirmar a rota real de edição antes de prosseguir:
  `grep -n "rdo/editar\|salvar_edicao_rdo\|editar_rdo_form\|methods=\['POST'\]" rdo_editar_sistema.py`
  Se o prefixo do blueprint não for `/rdo/editar`, ajustar a URL do teste para a rota real
  (ver `app.url_map` ou `grep -n register_blueprint.*rdo_editar main.py`). Não seguir sem a rota certa.

### Task A2 — Corrigir o template (`templates/rdo/editar_rdo.html`)

- [ ] Localizar a função `_syncHiddenInputsEquipeV2Edit` (~linha 2446) e a linha do `h.name`.
- [ ] Trocar o nome do campo emitido. **De:**
```javascript
            h.name = `sub_func_${tarefaId}_${f.id}_horas`;
```
  **Para:**
```javascript
            h.name = `cron_tarefa_${tarefaId}_func_${f.id}_horas`;
```
  Motivo: `tarefaId` é um `TarefaCronograma.id`. O padrão `cron_tarefa_<id>_func_<id>_horas` é o
  mesmo que `templates/rdo/novo.html` emite e que `salvar_rdo_flexivel` sabe parsear.
- [ ] Verificar que o seletor de limpeza acima ainda remove os hidden antigos. Se o seletor for
  `input[name^="sub_func_"][data-v2edit="1"]`, trocar para
  `input[name^="cron_tarefa_"][data-v2edit="1"]` para não deixar resíduo. Manter o `data-v2edit="1"`
  no novo input.

### Task A3 — Parsear `cron_tarefa_*` na edição e gravar `tarefa_cronograma_id` (GREEN)

Espelhar `views/rdo.py:salvar_rdo_flexivel` (linhas 4283–4340 e 4395–4411).

- [ ] Em `rdo_editar_sistema.py`, no handler POST (`salvar_edicao_rdo`, ~linha 168), **depois** do
  bloco que monta `entradas_brutas` para subatividades (após a linha ~399, antes de chamar
  `normalizar_horas_funcionario`), adicionar a coleta de cronograma:

```python
        # ── Equipe por atividade do cronograma (V2) ──────────────────────────
        # Espelha views/rdo.py:salvar_rdo_flexivel. O template emite
        # cron_tarefa_<tarefa_id>_func_<func_id>_horas. Sem isto, a edição
        # perdia o vínculo atividade↔funcionário (bug rdo_editar_sistema.py:374).
        _cron_tarefa_pattern = _re.compile(r'^cron_tarefa_(\d+)_func_(\d+)_horas$')
        seen_cron_keys = set()
        for campo, valor in request.form.items():
            if not valor:
                continue
            m_cron = _cron_tarefa_pattern.match(campo)
            if not m_cron:
                continue
            try:
                tarefa_id_cron = int(m_cron.group(1))
                func_id_cron = int(m_cron.group(2))
                horas_cron = float(valor)
            except (ValueError, TypeError):
                continue
            if horas_cron <= 0:
                continue
            cron_key = (func_id_cron, tarefa_id_cron)
            if cron_key in seen_cron_keys:
                continue
            seen_cron_keys.add(cron_key)
            entradas_brutas.append(
                (func_id_cron, ('cron', tarefa_id_cron), horas_cron)
            )
```

- [ ] No laço que constrói `RDOMaoObra` a partir de `entradas_normalizadas` (~linha 430), distinguir
  a chave `('cron', tarefa_id)` da `('sub', sub_mestre_id)`. A chave da atividade é o **segundo
  elemento** da tupla normalizada. Adaptar o laço para:

```python
        for entrada in entradas_normalizadas:
            func_id = entrada[0]
            atividade_key = entrada[1]   # ('sub', id) | ('cron', tarefa_id)
            horas_norm = float(entrada[2] or 0)
            if horas_norm <= 0:
                continue
            funcionario = Funcionario.query.filter_by(
                id=func_id, admin_id=admin_id
            ).first()
            if not funcionario:
                continue
            funcao_exercida = (funcionario.funcao.nome
                               if getattr(funcionario, 'funcao', None) else 'Operacional')

            if atividade_key[0] == 'cron':
                rdo_mo = RDOMaoObra(
                    rdo_id=rdo_id,
                    funcionario_id=func_id,
                    funcao_exercida=funcao_exercida,
                    horas_trabalhadas=horas_norm,
                    admin_id=admin_id,
                    subatividade_id=None,
                    tarefa_cronograma_id=atividade_key[1],
                )
            else:  # 'sub'
                sub_mestre_id = atividade_key[1]
                sub_db_id = _resolver_sub_db_id(sub_mestre_id)  # lógica já existente no arquivo
                peso_linha = pesos.get((func_id, atividade_key))
                rdo_mo = RDOMaoObra(
                    rdo_id=rdo_id,
                    funcionario_id=func_id,
                    funcao_exercida=funcao_exercida,
                    horas_trabalhadas=horas_norm,
                    admin_id=admin_id,
                    subatividade_id=sub_db_id,
                    peso_distribuicao=peso_linha,
                )
            db.session.add(rdo_mo)
            funcionarios_salvos += 1
```

  **Importante:** este laço SUBSTITUI o laço atual de gravação por subatividade — não duplicar.
  Reaproveitar a resolução de `sub_db_id` e `peso_linha` que já existe no arquivo (chamada
  `_resolver_sub_db_id` é ilustrativa: usar o mesmo código que o arquivo usa hoje para converter
  `sub_mestre_id` → id da `RDOServicoSubatividade`). Antes de editar, **ler** o trecho atual
  (linhas ~399–449) para preservar nomes de variáveis (`funcionarios_salvos`, etc.).
- [ ] Garantir que a edição **apaga** as `RDOMaoObra` antigas do RDO antes de regravar (procurar
  `RDOMaoObra.query.filter_by(rdo_id=...).delete()` no handler; se não existir, adicionar antes do
  laço de gravação). Caso contrário a edição duplica linhas.
- [ ] Após salvar a equipe, recalcular custo e % como o save faz. Conferir se o handler já chama:
  `from services.custo_funcionario_dia import gravar_custo_funcionario_rdo` e
  `from utils.cronograma_engine import atualizar_percentual_tarefa`. Se não chamar, adicionar ao
  final do handler (antes do `db.session.commit()` final):
```python
        from services.custo_funcionario_dia import gravar_custo_funcionario_rdo
        gravar_custo_funcionario_rdo(rdo, admin_id)
```
- [ ] Rodar e **confirmar verde**:
  `python -m pytest tests/test_rdo_edicao_preserva_tarefa.py -x`
- [ ] Rodar a suíte de custo para não regredir:
  `python -m pytest tests/test_custo_diario.py -x`
- [ ] **Commit:** `fix(rdo): edição preserva tarefa_cronograma_id (espelha salvar_rdo_flexivel)`

---

## FASE B — Read-model `resultado_atividade_service` (TDD, funções puras)

> Cada função abaixo é testada antes de implementada. As fórmulas vêm da spec §4 (D1, D5) e §Fatia 1.
> Estilo: `Decimal`, `quantize(Decimal('0.01'), ROUND_HALF_UP)`, espelhando `services/medicao_service.py`.

### Task B1 — Esqueleto do serviço + helpers

- [ ] Criar `services/resultado_atividade_service.py`:

```python
"""Read-model do Resultado por Atividade (Fatia 1 — só Mão de Obra).

Calcula, a partir das fontes que já existem (sem migration):
  - valor_agregado_atividade   : a receber pela produção feita
  - custo_mo_atividade         : custo onerado real de MO rateado por horas (D1)
  - resultado_realizado_atividade = agregado − custo MO
  - custo_mo_orcado_atividade  : MO orçada (composicao_snapshot × quantidade × peso)
  - alarme_mo                  : real vs orçado-para-o-avanço, em R$ (D5 primário)
  - indice_horas               : refino, só onde a MO foi orçada em hora
  - resultado_obra             : rollup por atividade / serviço / obra

O peso Serviço→Atividade é o da medição (ItemMedicaoCronogramaTarefa.peso) — D6,
fonte única de verdade. Nada é gravado: tudo é computado sob demanda.
"""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from app import db
from models import (
    TarefaCronograma, ItemMedicaoComercial, ItemMedicaoCronogramaTarefa,
    PropostaItem, RDOMaoObra, RDOCustoDiario,
)

CEM = Decimal('100')
CENTAVO = Decimal('0.01')


def _D(x):
    """Converte qualquer numérico/None para Decimal de forma segura."""
    return Decimal(str(x)) if x is not None else Decimal('0')


def _q(d):
    return d.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _soma_peso_item(item_id):
    """Soma dos pesos de todas as tarefas vinculadas ao item de medição.
    É o denominador da normalização do peso (D6)."""
    total = (
        db.session.query(
            db.func.coalesce(db.func.sum(ItemMedicaoCronogramaTarefa.peso), 0)
        )
        .filter(ItemMedicaoCronogramaTarefa.item_medicao_id == item_id)
        .scalar()
    )
    return _D(total)


def _links_da_tarefa(tarefa):
    """Vínculos (item_medicao, peso) desta atividade."""
    return (
        ItemMedicaoCronogramaTarefa.query
        .filter_by(cronograma_tarefa_id=tarefa.id)
        .all()
    )
```

- [ ] Criar `tests/test_resultado_atividade_service.py` com a infraestrutura de fixtures (builders).
  Conteúdo inicial (será estendido a cada task):

```python
"""Testes do read-model services/resultado_atividade_service.py."""
import os
import sys
from datetime import date, datetime
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import (
    Usuario, TipoUsuario, Funcionario, Obra, Cliente,
    RDO, RDOMaoObra, RDOCustoDiario, TarefaCronograma,
    ItemMedicaoComercial, ItemMedicaoCronogramaTarefa, PropostaItem,
    PropostaComercial,
)
from werkzeug.security import generate_password_hash


def _sfx():
    return datetime.utcnow().strftime('%H%M%S%f')


class FX:
    admin = None
    obra = None
    s = ''


_fx = FX()


@pytest.fixture(scope='module', autouse=True)
def ambiente():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        s = _sfx()
        admin = Usuario(
            username=f'res_ativ_{s}', email=f'res_ativ_{s}@sige.test',
            nome='Res Ativ', tipo_usuario=TipoUsuario.ADMIN,
            password_hash=generate_password_hash('Test@1234'),
            versao_sistema='v2', ativo=True,
        )
        db.session.add(admin); db.session.flush()
        cli = Cliente(nome=f'CLI-RA-{s}', admin_id=admin.id)
        db.session.add(cli); db.session.flush()
        obra = Obra(
            nome=f'Obra RA {s}', codigo=f'ORA{s[:6]}',
            data_inicio=date(2026, 1, 1), admin_id=admin.id,
            cliente_id=cli.id, valor_contrato=100000,
        )
        db.session.add(obra); db.session.commit()
        _fx.admin = admin; _fx.obra = obra; _fx.s = s
        yield


# ── builders ────────────────────────────────────────────────────────────────

def _tarefa(nome, quantidade_total=100.0, percentual=0.0, servico_id=None, pai=None):
    t = TarefaCronograma(
        obra_id=_fx.obra.id, nome_tarefa=nome, ordem=1, duracao_dias=5,
        quantidade_total=quantidade_total, percentual_concluido=percentual,
        servico_id=servico_id, admin_id=_fx.admin.id,
        tarefa_pai_id=(pai.id if pai else None),
    )
    db.session.add(t); db.session.flush()
    return t


def _proposta_item(composicao_snapshot, quantidade):
    prop = PropostaComercial(
        admin_id=_fx.admin.id, numero=f'PROP-{_sfx()}', cliente_nome='X',
    )
    db.session.add(prop); db.session.flush()
    pi = PropostaItem(
        admin_id=_fx.admin.id, proposta_id=prop.id, item_numero=1,
        descricao='Serviço', quantidade=Decimal(str(quantidade)), unidade='m2',
        preco_unitario=Decimal('1'), ordem=1,
        composicao_snapshot=composicao_snapshot,
    )
    db.session.add(pi); db.session.flush()
    return pi


def _item_medicao(valor_comercial, tarefa, peso, quantidade=None, proposta_item=None):
    imc = ItemMedicaoComercial(
        admin_id=_fx.admin.id, obra_id=_fx.obra.id, nome='IMC',
        valor_comercial=Decimal(str(valor_comercial)),
        quantidade=(Decimal(str(quantidade)) if quantidade is not None else None),
        proposta_item_id=(proposta_item.id if proposta_item else None),
        status='PENDENTE',
    )
    db.session.add(imc); db.session.flush()
    link = ItemMedicaoCronogramaTarefa(
        item_medicao_id=imc.id, cronograma_tarefa_id=tarefa.id,
        peso=Decimal(str(peso)), admin_id=_fx.admin.id,
    )
    db.session.add(link); db.session.flush()
    return imc


def _func(tipo='salario', salario=0.0, valor_diaria=0.0):
    f = Funcionario(
        nome=f'F {_sfx()}', cpf=f'9{_sfx()}'.ljust(14, '0')[:14],
        codigo=f'F{_sfx()[:8]}', data_admissao=date(2025, 1, 1),
        admin_id=_fx.admin.id, tipo_remuneracao=tipo, salario=salario,
        valor_diaria=valor_diaria, valor_va=0.0, valor_vt=0.0, ativo=True,
    )
    db.session.add(f); db.session.flush()
    return f


def _rdo(data):
    r = RDO(
        numero_rdo=f'RDO-RA-{_sfx()}', obra_id=_fx.obra.id, data_relatorio=data,
        admin_id=_fx.admin.id, status='Finalizado', criado_por_id=_fx.admin.id,
    )
    db.session.add(r); db.session.flush()
    return r


def _mo(rdo, func, tarefa, horas):
    mo = RDOMaoObra(
        rdo_id=rdo.id, funcionario_id=func.id, funcao_exercida='Op',
        horas_trabalhadas=horas, admin_id=_fx.admin.id,
        subatividade_id=None, tarefa_cronograma_id=tarefa.id,
    )
    db.session.add(mo); db.session.flush()
    return mo


def _custo_diario(rdo, func, custo_total):
    """Grava direto o RDOCustoDiario (o read-model só LÊ este valor)."""
    c = RDOCustoDiario(
        rdo_id=rdo.id, funcionario_id=func.id, admin_id=_fx.admin.id,
        data=rdo.data_relatorio, tipo_remuneracao_snapshot='salario',
        custo_total_dia=Decimal(str(custo_total)), tipo_lancamento='rdo',
    )
    db.session.add(c); db.session.flush()
    return c
```

- [ ] Confirmar os imports do builder existem: `PropostaComercial` é o nome real da classe da
  proposta? Validar: `grep -n "class PropostaComercial\|__tablename__ = 'propostas_comerciais'" models.py`.
  Ajustar o import/campos obrigatórios de `PropostaComercial` se o construtor exigir mais (ler a
  classe e preencher só os `nullable=False`).
- [ ] Rodar para garantir que o módulo importa:
  `python -m pytest tests/test_resultado_atividade_service.py -x` (sem testes ainda, deve coletar 0).

### Task B2 — `valor_agregado_atividade` (RED→GREEN)

- [ ] Adicionar o teste:

```python
def test_valor_agregado_atividade():
    from services.resultado_atividade_service import valor_agregado_atividade
    with app.app_context():
        t = _tarefa('Alvenaria', percentual=50.0)
        # tarefa é 100% do item (peso 100), valor_comercial 1000 → agregado = 50% × 1000
        _item_medicao(valor_comercial=1000, tarefa=t, peso=100)
        db.session.commit()
        assert valor_agregado_atividade(t) == Decimal('500.00')


def test_valor_agregado_com_peso_parcial():
    from services.resultado_atividade_service import valor_agregado_atividade
    with app.app_context():
        t1 = _tarefa('Parte A', percentual=100.0)
        t2 = _tarefa('Parte B', percentual=0.0)
        imc = _item_medicao(valor_comercial=1000, tarefa=t1, peso=40)
        # t2 também pertence ao MESMO item (peso 60) → soma de pesos = 100
        link2 = ItemMedicaoCronogramaTarefa(
            item_medicao_id=imc.id, cronograma_tarefa_id=t2.id,
            peso=Decimal('60'), admin_id=_fx.admin.id,
        )
        db.session.add(link2); db.session.commit()
        # t1: 100% × (40/100) × 1000 = 400
        assert valor_agregado_atividade(t1) == Decimal('400.00')
        assert valor_agregado_atividade(t2) == Decimal('0.00')
```

- [ ] Rodar (RED): `python -m pytest tests/test_resultado_atividade_service.py -x`
- [ ] Implementar em `services/resultado_atividade_service.py`:

```python
def valor_agregado_atividade(tarefa):
    """Valor a receber pela produção já feita nesta atividade.
    = (percentual_concluido/100) × (peso_norm) × valor_comercial, somado sobre
    os itens de medição a que a atividade está vinculada (D6)."""
    perc = _D(tarefa.percentual_concluido) / CEM
    total = Decimal('0')
    for link in _links_da_tarefa(tarefa):
        item = db.session.get(ItemMedicaoComercial, link.item_medicao_id)
        if not item:
            continue
        soma_peso = _soma_peso_item(item.id)
        if soma_peso <= 0:
            continue
        peso_norm = _D(link.peso) / soma_peso
        total += perc * peso_norm * _D(item.valor_comercial)
    return _q(total)
```

- [ ] Rodar (GREEN) e **commit:** `feat(resultado): valor_agregado_atividade`

### Task B3 — `custo_mo_atividade` (rateio do custo onerado, D1) (RED→GREEN)

- [ ] Adicionar o teste:

```python
def test_custo_mo_atividade_rateio_por_horas():
    from services.resultado_atividade_service import custo_mo_atividade
    with app.app_context():
        t_a = _tarefa('Atividade A')
        t_b = _tarefa('Atividade B')
        f = _func()
        r = _rdo(date(2026, 2, 10))
        # func trabalhou 6h em A e 2h em B no mesmo RDO; custo onerado do dia = 200
        _mo(r, f, t_a, horas=6.0)
        _mo(r, f, t_b, horas=2.0)
        _custo_diario(r, f, custo_total=200)
        db.session.commit()
        # rateio: A = 200 × 6/8 = 150 ; B = 200 × 2/8 = 50
        assert custo_mo_atividade(t_a) == Decimal('150.00')
        assert custo_mo_atividade(t_b) == Decimal('50.00')


def test_custo_mo_atividade_soma_multiplos_dias():
    from services.resultado_atividade_service import custo_mo_atividade
    with app.app_context():
        t = _tarefa('Atividade C')
        f = _func()
        r1 = _rdo(date(2026, 2, 11)); _mo(r1, f, t, 8.0); _custo_diario(r1, f, 100)
        r2 = _rdo(date(2026, 2, 12)); _mo(r2, f, t, 8.0); _custo_diario(r2, f, 120)
        db.session.commit()
        # único func/atividade em cada RDO → 100 + 120
        assert custo_mo_atividade(t) == Decimal('220.00')
```

- [ ] Rodar (RED). Implementar:

```python
def custo_mo_atividade(tarefa):
    """Custo de MO incorrido nesta atividade (D1): para cada (RDO, funcionário)
    que apontou horas na atividade, rateia o custo onerado real daquele RDO
    (RDOCustoDiario.custo_total_dia) pela fração de horas do funcionário gastas
    na atividade naquele RDO. Soma sobre todos os RDOs."""
    horas_ativ = defaultdict(Decimal)        # (rdo_id, func_id) -> horas na atividade
    for mo in RDOMaoObra.query.filter_by(tarefa_cronograma_id=tarefa.id).all():
        horas_ativ[(mo.rdo_id, mo.funcionario_id)] += _D(mo.horas_trabalhadas)

    total = Decimal('0')
    for (rdo_id, func_id), h_ativ in horas_ativ.items():
        h_total = _D(
            db.session.query(
                db.func.coalesce(db.func.sum(RDOMaoObra.horas_trabalhadas), 0)
            )
            .filter(RDOMaoObra.rdo_id == rdo_id,
                    RDOMaoObra.funcionario_id == func_id)
            .scalar()
        )
        if h_total <= 0:
            continue
        custo = (
            RDOCustoDiario.query
            .filter_by(rdo_id=rdo_id, funcionario_id=func_id)
            .first()
        )
        if not custo:
            continue
        total += _D(custo.custo_total_dia) * (h_ativ / h_total)
    return _q(total)
```

- [ ] Rodar (GREEN). **Commit:** `feat(resultado): custo_mo_atividade (rateio onerado por horas, D1)`

### Task B4 — `resultado_realizado_atividade` (RED→GREEN)

- [ ] Teste:

```python
def test_resultado_realizado_atividade():
    from services.resultado_atividade_service import resultado_realizado_atividade
    with app.app_context():
        t = _tarefa('Resultado', percentual=100.0)
        _item_medicao(valor_comercial=1000, tarefa=t, peso=100)
        f = _func()
        r = _rdo(date(2026, 2, 13)); _mo(r, f, t, 8.0); _custo_diario(r, f, 300)
        db.session.commit()
        # agregado 1000 − custo MO 300 = 700
        assert resultado_realizado_atividade(t) == Decimal('700.00')
```

- [ ] Implementar:

```python
def resultado_realizado_atividade(tarefa):
    """Resultado (competência) da atividade na Fatia 1 = Valor agregado − Custo MO.
    Fatias 2+ somarão material/transporte/subempreitada ao custo."""
    return _q(valor_agregado_atividade(tarefa) - custo_mo_atividade(tarefa))
```

- [ ] Rodar (GREEN). **Commit:** `feat(resultado): resultado_realizado_atividade (só MO)`

### Task B5 — `custo_mo_orcado_atividade` (snapshot × quantidade × peso) (RED→GREEN)

- [ ] Teste (inclui a função pura sobre o snapshot):

```python
def test_custo_mo_orcado_unitario_filtra_mao_obra():
    from services.resultado_atividade_service import custo_mo_orcado_unitario
    snap = [
        {'tipo': 'MATERIAL', 'unidade': 'kg', 'coeficiente': 5.0, 'subtotal_unitario': 7.5},
        {'tipo': 'MAO_OBRA', 'unidade': 'h', 'coeficiente': 0.5, 'subtotal_unitario': 15.0},
        {'tipo': 'MAO_OBRA', 'unidade': 'h', 'coeficiente': 0.2, 'subtotal_unitario': 5.0},
    ]
    assert custo_mo_orcado_unitario(snap) == Decimal('20.0')


def test_custo_mo_orcado_atividade():
    from services.resultado_atividade_service import custo_mo_orcado_atividade
    with app.app_context():
        snap = [
            {'tipo': 'MAO_OBRA', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 10.0},
            {'tipo': 'MATERIAL', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 40.0},
        ]
        pi = _proposta_item(composicao_snapshot=snap, quantidade=100)
        t = _tarefa('Orcado')
        # item: MO orçada = 10/m² × 100 m² = 1000; tarefa é 100% do item
        _item_medicao(valor_comercial=5000, tarefa=t, peso=100,
                      quantidade=100, proposta_item=pi)
        db.session.commit()
        assert custo_mo_orcado_atividade(t) == Decimal('1000.00')
```

- [ ] Rodar (RED). Implementar:

```python
def custo_mo_orcado_unitario(composicao_snapshot):
    """Custo de MO orçado por UMA unidade de serviço = Σ subtotal_unitario das
    linhas tipo MAO_OBRA do snapshot. Função pura (sem DB)."""
    total = Decimal('0')
    for linha in (composicao_snapshot or []):
        if (linha.get('tipo') or '').upper() == 'MAO_OBRA':
            total += _D(linha.get('subtotal_unitario'))
    return total


def custo_mo_orcado_atividade(tarefa):
    """MO orçada alocada à atividade = Σ_itens (MO/un × quantidade × peso_norm).
    quantidade vem do ItemMedicaoComercial (fallback PropostaItem)."""
    total = Decimal('0')
    for link in _links_da_tarefa(tarefa):
        item = db.session.get(ItemMedicaoComercial, link.item_medicao_id)
        if not item or not item.proposta_item_id:
            continue
        pi = db.session.get(PropostaItem, item.proposta_item_id)
        if not pi:
            continue
        soma_peso = _soma_peso_item(item.id)
        if soma_peso <= 0:
            continue
        mo_unit = custo_mo_orcado_unitario(pi.composicao_snapshot)
        qtd = _D(item.quantidade) if item.quantidade is not None else _D(pi.quantidade)
        peso_norm = _D(link.peso) / soma_peso
        total += mo_unit * qtd * peso_norm
    return _q(total)
```

- [ ] Rodar (GREEN). **Commit:** `feat(resultado): custo_mo_orcado_atividade (composição × qtd × peso)`

### Task B6 — `alarme_mo` (primário em R$, D5) (RED→GREEN)

- [ ] Teste:

```python
def test_alarme_mo_no_vermelho():
    from services.resultado_atividade_service import alarme_mo
    with app.app_context():
        snap = [{'tipo': 'MAO_OBRA', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 10.0}]
        pi = _proposta_item(composicao_snapshot=snap, quantidade=100)  # MO orçada total = 1000
        t = _tarefa('Alarme', percentual=50.0)                         # avanço 50%
        _item_medicao(valor_comercial=5000, tarefa=t, peso=100,
                      quantidade=100, proposta_item=pi)
        f = _func()
        r = _rdo(date(2026, 2, 14)); _mo(r, f, t, 8.0); _custo_diario(r, f, 700)
        db.session.commit()
        a = alarme_mo(t)
        # orçado_para_avanço = 50% × 1000 = 500 ; real = 700 → estouro
        assert a['orcado_para_avanco'] == Decimal('500.00')
        assert a['real'] == Decimal('700.00')
        assert a['estouro'] is True
        assert a['indice_rs'] == Decimal('0.714')   # 500/700


def test_alarme_mo_no_verde():
    from services.resultado_atividade_service import alarme_mo
    with app.app_context():
        snap = [{'tipo': 'MAO_OBRA', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 10.0}]
        pi = _proposta_item(composicao_snapshot=snap, quantidade=100)
        t = _tarefa('AlarmeOk', percentual=50.0)
        _item_medicao(valor_comercial=5000, tarefa=t, peso=100, quantidade=100, proposta_item=pi)
        f = _func()
        r = _rdo(date(2026, 2, 15)); _mo(r, f, t, 8.0); _custo_diario(r, f, 400)
        db.session.commit()
        a = alarme_mo(t)
        assert a['estouro'] is False        # real 400 < orçado_para_avanço 500
```

- [ ] Rodar (RED). Implementar:

```python
def alarme_mo(tarefa):
    """Alarme primário em R$ (D5): compara o custo MO real incorrido com o
    custo MO orçado para o avanço atual. Vale para qualquer modelo de
    precificação (R$/m², hora, verba)."""
    perc = _D(tarefa.percentual_concluido) / CEM
    orcado_total = custo_mo_orcado_atividade(tarefa)
    orcado_para_avanco = _q(orcado_total * perc)
    real = custo_mo_atividade(tarefa)
    indice = None
    if real > 0:
        indice = (orcado_para_avanco / real).quantize(
            Decimal('0.001'), rounding=ROUND_HALF_UP
        )
    return {
        'orcado_total': orcado_total,
        'orcado_para_avanco': orcado_para_avanco,
        'real': real,
        'estouro': real > orcado_para_avanco,
        'indice_rs': indice,   # <1 = no vermelho; None se sem custo real ainda
    }
```

- [ ] Rodar (GREEN). **Commit:** `feat(resultado): alarme_mo (primário em R$, D5)`

### Task B7 — `indice_horas` (refino, só MO em hora) (RED→GREEN)

- [ ] Teste:

```python
def test_indice_horas_quando_mo_em_hora():
    from services.resultado_atividade_service import indice_horas
    with app.app_context():
        snap = [{'tipo': 'MAO_OBRA', 'unidade': 'h', 'coeficiente': 0.1, 'subtotal_unitario': 3.0}]
        pi = _proposta_item(composicao_snapshot=snap, quantidade=100)  # horas orçadas = 0.1×100=10
        t = _tarefa('HoraItem', percentual=50.0)
        _item_medicao(valor_comercial=5000, tarefa=t, peso=100, quantidade=100, proposta_item=pi)
        f = _func()
        r = _rdo(date(2026, 2, 16)); _mo(r, f, t, 8.0); db.session.commit()
        res = indice_horas(t)
        # ganhas = 50% × 10 = 5 ; reais = 8 ; índice = 5/8 = 0.625
        assert res['horas_orcadas'] == Decimal('10.00')
        assert res['horas_ganhas'] == Decimal('5.00')
        assert res['horas_reais'] == Decimal('8.00')
        assert res['indice'] == Decimal('0.625')


def test_indice_horas_none_quando_mo_em_m2():
    from services.resultado_atividade_service import indice_horas
    with app.app_context():
        snap = [{'tipo': 'MAO_OBRA', 'unidade': 'm2', 'coeficiente': 1.0, 'subtotal_unitario': 10.0}]
        pi = _proposta_item(composicao_snapshot=snap, quantidade=100)
        t = _tarefa('M2Item', percentual=50.0)
        _item_medicao(valor_comercial=5000, tarefa=t, peso=100, quantidade=100, proposta_item=pi)
        db.session.commit()
        assert indice_horas(t) is None     # MO não tem insumo horário
```

- [ ] Rodar (RED). Implementar:

```python
def horas_orcadas_unitarias(composicao_snapshot):
    """Horas orçadas por UMA unidade de serviço = Σ coeficiente das linhas
    MAO_OBRA com unidade 'h'. Retorna None se nenhuma linha de MO é horária."""
    total = Decimal('0')
    achou = False
    for linha in (composicao_snapshot or []):
        if (linha.get('tipo') or '').upper() == 'MAO_OBRA' and \
           (linha.get('unidade') or '').lower() == 'h':
            total += _D(linha.get('coeficiente'))
            achou = True
    return total if achou else None


def indice_horas(tarefa):
    """Refino do alarme (D5), só onde a MO foi orçada em hora. Índice =
    horas ganhas (avanço × horas orçadas) / horas reais apontadas.
    Retorna None quando a MO do item não tem insumo horário."""
    horas_orcadas = Decimal('0')
    tem_hora = False
    for link in _links_da_tarefa(tarefa):
        item = db.session.get(ItemMedicaoComercial, link.item_medicao_id)
        if not item or not item.proposta_item_id:
            continue
        pi = db.session.get(PropostaItem, item.proposta_item_id)
        if not pi:
            continue
        unit = horas_orcadas_unitarias(pi.composicao_snapshot)
        if unit is None:
            continue
        tem_hora = True
        soma_peso = _soma_peso_item(item.id)
        if soma_peso <= 0:
            continue
        qtd = _D(item.quantidade) if item.quantidade is not None else _D(pi.quantidade)
        peso_norm = _D(link.peso) / soma_peso
        horas_orcadas += unit * qtd * peso_norm

    if not tem_hora:
        return None

    perc = _D(tarefa.percentual_concluido) / CEM
    horas_ganhas = horas_orcadas * perc
    horas_reais = _D(
        db.session.query(
            db.func.coalesce(db.func.sum(RDOMaoObra.horas_trabalhadas), 0)
        )
        .filter(RDOMaoObra.tarefa_cronograma_id == tarefa.id)
        .scalar()
    )
    indice = None
    if horas_reais > 0:
        indice = (horas_ganhas / horas_reais).quantize(
            Decimal('0.001'), rounding=ROUND_HALF_UP
        )
    return {
        'horas_orcadas': _q(horas_orcadas),
        'horas_ganhas': _q(horas_ganhas),
        'horas_reais': _q(horas_reais),
        'indice': indice,
    }
```

- [ ] Rodar (GREEN). **Commit:** `feat(resultado): indice_horas (refino, só MO em hora)`

### Task B8 — `resultado_obra` (rollup atividade → serviço → obra) (RED→GREEN)

- [ ] Teste:

```python
def test_resultado_obra_rollup():
    from services.resultado_atividade_service import resultado_obra
    with app.app_context():
        # duas atividades-folha com agregado e custo conhecidos
        t1 = _tarefa('Folha 1', percentual=100.0, servico_id=None)
        _item_medicao(valor_comercial=1000, tarefa=t1, peso=100)
        f1 = _func(); r1 = _rdo(date(2026, 2, 17)); _mo(r1, f1, t1, 8.0); _custo_diario(r1, f1, 300)
        t2 = _tarefa('Folha 2', percentual=100.0, servico_id=None)
        _item_medicao(valor_comercial=500, tarefa=t2, peso=100)
        f2 = _func(); r2 = _rdo(date(2026, 2, 18)); _mo(r2, f2, t2, 8.0); _custo_diario(r2, f2, 100)
        db.session.commit()
        res = resultado_obra(_fx.obra.id)
        # agregado total = 1500 ; custo MO total = 400 ; resultado = 1100
        assert res['valor_agregado'] == Decimal('1500.00')
        assert res['custo_mo'] == Decimal('400.00')
        assert res['resultado'] == Decimal('1100.00')
        # uma linha por atividade-folha
        nomes = {a['nome'] for a in res['atividades']}
        assert {'Folha 1', 'Folha 2'} <= nomes
```

- [ ] Rodar (RED). Implementar:

```python
def _folhas_da_obra(obra_id):
    """Atividades-folha (sem filhas) da obra — os centros de custo reais.
    Grupos (que têm filhas) são agregação, não recebem apontamento direto."""
    tarefas = TarefaCronograma.query.filter_by(obra_id=obra_id).all()
    pais = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id is not None}
    return [t for t in tarefas if t.id not in pais]


def resultado_obra(obra_id):
    """Rollup do Resultado da obra a partir das atividades-folha. Retorna o
    detalhe por atividade + totais por serviço + totais da obra."""
    atividades = []
    por_servico = defaultdict(lambda: {
        'valor_agregado': Decimal('0'), 'custo_mo': Decimal('0'),
        'resultado': Decimal('0'),
    })
    tot_agregado = Decimal('0')
    tot_custo = Decimal('0')

    for t in _folhas_da_obra(obra_id):
        agregado = valor_agregado_atividade(t)
        custo = custo_mo_atividade(t)
        resultado = _q(agregado - custo)
        alarme = alarme_mo(t)
        atividades.append({
            'tarefa_id': t.id,
            'nome': t.nome_tarefa,
            'servico_id': t.servico_id,
            'percentual_concluido': float(t.percentual_concluido or 0),
            'quantidade_total': float(t.quantidade_total or 0),
            'valor_agregado': agregado,
            'custo_mo': custo,
            'resultado': resultado,
            'alarme': alarme,
            'indice_horas': indice_horas(t),
        })
        chave = t.servico_id or 0
        por_servico[chave]['valor_agregado'] += agregado
        por_servico[chave]['custo_mo'] += custo
        por_servico[chave]['resultado'] += resultado
        tot_agregado += agregado
        tot_custo += custo

    return {
        'obra_id': obra_id,
        'atividades': atividades,
        'por_servico': {k: {kk: _q(vv) for kk, vv in v.items()}
                        for k, v in por_servico.items()},
        'valor_agregado': _q(tot_agregado),
        'custo_mo': _q(tot_custo),
        'resultado': _q(tot_agregado - tot_custo),
    }
```

- [ ] Rodar (GREEN). Rodar o arquivo inteiro:
  `python -m pytest tests/test_resultado_atividade_service.py -x`
- [ ] **Commit:** `feat(resultado): resultado_obra (rollup atividade→serviço→obra)`

---

## FASE C — Tela "Resultado por Atividade"

### Task C1 — Blueprint `resultado_views.py` + registro + smoke test

- [ ] Criar `resultado_views.py`:

```python
import logging

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required

logger = logging.getLogger(__name__)

resultado_bp = Blueprint('resultado', __name__)


def _admin_id():
    from utils.tenant import get_tenant_admin_id
    return get_tenant_admin_id()


def _check_v2():
    from utils.tenant import is_v2_active
    if not is_v2_active():
        flash('Esta funcionalidade está disponível apenas no plano V2.', 'warning')
        return redirect(url_for('main.dashboard'))
    return None


@resultado_bp.route('/obras/<int:obra_id>/resultado/')
@resultado_bp.route('/obras/<int:obra_id>/resultado')
@login_required
def resultado_por_atividade(obra_id):
    guard = _check_v2()
    if guard:
        return guard

    from models import Obra
    from services.resultado_atividade_service import resultado_obra

    admin_id = _admin_id()
    obra = Obra.query.filter_by(id=obra_id, admin_id=admin_id).first_or_404()
    dados = resultado_obra(obra_id)
    return render_template('resultado/por_atividade.html', obra=obra, dados=dados)
```

- [ ] Confirmar o helper de tenant existe: `grep -n "def get_tenant_admin_id" utils/tenant.py`.
  Se o nome for outro, usar o mesmo que `medicao_views.py` importa (já confirmado: `_admin_id`
  delega para `utils.tenant.get_tenant_admin_id`).
- [ ] Registrar em `main.py`, logo após o registro do `medicao_bp`:

```python
try:
    from resultado_views import resultado_bp
    app.register_blueprint(resultado_bp)
    logger.info("[OK] Blueprint RESULTADO POR ATIVIDADE registrado")
except Exception as e:
    logger.error(f"[ERROR] Erro ao registrar Resultado: {e}")
```

- [ ] Adicionar smoke test em `tests/test_resultado_atividade_service.py`:

```python
def test_rota_resultado_responde():
    with app.app_context():
        admin = _fx.admin
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin.id)
                sess['_fresh'] = True
            resp = c.get(f'/obras/{_fx.obra.id}/resultado')
        assert resp.status_code == 200
```

- [ ] Rodar: `python -m pytest tests/test_resultado_atividade_service.py::test_rota_resultado_responde -x`
  (a Task C2 cria o template; se rodar antes, espera-se `TemplateNotFound` — rodar este teste só
  depois da C2.)

### Task C2 — Template `templates/resultado/por_atividade.html`

- [ ] Criar `templates/resultado/por_atividade.html`:

```html
{% extends "base_completo.html" %}
{% block title %}Resultado por Atividade — {{ obra.nome }}{% endblock %}

{% block content %}
<div class="container-fluid py-3">
  <h3 class="mb-3">Resultado por Atividade — {{ obra.nome }}</h3>

  <div class="row g-3 mb-4">
    <div class="col-md-4">
      <div class="card shadow-sm"><div class="card-body">
        <div class="text-muted small">Valor agregado</div>
        <div class="h4 mb-0">R$ {{ '%.2f'|format(dados.valor_agregado) }}</div>
      </div></div>
    </div>
    <div class="col-md-4">
      <div class="card shadow-sm"><div class="card-body">
        <div class="text-muted small">Custo incorrido (MO)</div>
        <div class="h4 mb-0">R$ {{ '%.2f'|format(dados.custo_mo) }}</div>
      </div></div>
    </div>
    <div class="col-md-4">
      <div class="card shadow-sm"><div class="card-body">
        <div class="text-muted small">Resultado realizado</div>
        <div class="h4 mb-0 {{ 'text-danger' if dados.resultado < 0 else 'text-success' }}">
          R$ {{ '%.2f'|format(dados.resultado) }}
        </div>
      </div></div>
    </div>
  </div>

  <div class="table-responsive">
    <table class="table table-sm table-hover align-middle">
      <thead class="table-light">
        <tr>
          <th>Atividade</th>
          <th class="text-end">% concl.</th>
          <th class="text-end">Valor agregado</th>
          <th class="text-end">Custo MO</th>
          <th class="text-end">Resultado</th>
          <th class="text-center">Alarme (R$)</th>
          <th class="text-end">Índice horas</th>
        </tr>
      </thead>
      <tbody>
        {% for a in dados.atividades %}
        <tr>
          <td>{{ a.nome }}</td>
          <td class="text-end">{{ '%.1f'|format(a.percentual_concluido) }}%</td>
          <td class="text-end">R$ {{ '%.2f'|format(a.valor_agregado) }}</td>
          <td class="text-end">R$ {{ '%.2f'|format(a.custo_mo) }}</td>
          <td class="text-end {{ 'text-danger' if a.resultado < 0 else '' }}">
            R$ {{ '%.2f'|format(a.resultado) }}
          </td>
          <td class="text-center">
            {% if a.alarme.estouro %}
              <span class="badge bg-danger" title="real R$ {{ '%.2f'|format(a.alarme.real) }} > orçado p/ avanço R$ {{ '%.2f'|format(a.alarme.orcado_para_avanco) }}">
                ⚠ {{ '%.0f'|format((a.alarme.indice_rs or 0) * 100) }}%
              </span>
            {% elif a.alarme.real > 0 %}
              <span class="badge bg-success">ok</span>
            {% else %}
              <span class="text-muted">—</span>
            {% endif %}
          </td>
          <td class="text-end">
            {% if a.indice_horas %}{{ '%.3f'|format(a.indice_horas.indice or 0) }}{% else %}—{% endif %}
          </td>
        </tr>
        {% else %}
        <tr><td colspan="7" class="text-center text-muted py-4">
          Nenhuma atividade com apontamento ainda.
        </td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

- [ ] Confirmar o nome do template-base: `ls templates/base_completo.html` (medicao usa
  `base_completo.html`). Se não existir, usar o mesmo `{% extends %}` de `templates/medicao/gestao_itens.html`.
- [ ] Rodar o smoke test (agora deve passar):
  `python -m pytest tests/test_resultado_atividade_service.py::test_rota_resultado_responde -x`
- [ ] **Commit:** `feat(resultado): tela Resultado por Atividade (view + template + smoke test)`

### Task C3 — Link de navegação na obra

- [ ] Localizar o template de detalhe da obra que lista as abas/ações V2:
  `grep -rln "url_for('medicao" templates/ | head` (a aba de Resultado fica ao lado da de Medição).
- [ ] Adicionar, no mesmo grupo de botões/abas, o link (dentro de `{% if is_v2_active() %}` se o
  template já usa esse gate — `is_v2_active` está exposto ao Jinja via context_processor):

```html
<a class="btn btn-outline-primary btn-sm"
   href="{{ url_for('resultado.resultado_por_atividade', obra_id=obra.id) }}">
  Resultado por Atividade
</a>
```

- [ ] Abrir a obra no app e confirmar o link aparece e navega (ver FASE E para subir o app).
- [ ] **Commit:** `feat(resultado): link 'Resultado por Atividade' no detalhe da obra`

---

## FASE D — Habilitação: materializar o cronograma da Baia + v2

> A Baia é greenfield (`tarefa_cronograma = 0`). Esta fase tira a obra do estado dormente.
> O cronograma-de-controle de referência (~30 atividades) está em
> `docs/superpowers/specs/2026-06-14-cronograma-refinado-pareto-baia-rev10.md`.

### Task D1 — Levantar o estado atual da Baia

- [ ] Rodar um diagnóstico (somente leitura) para saber o que já existe:

```python
# scripts/diag_baia.py
from app import app, db
from models import Orcamento, Obra, Proposta, TarefaCronograma  # ajustar nomes reais

with app.app_context():
    orc = Orcamento.query.filter_by(numero='ORC-BAIA-REV10').first()
    print('orcamento:', orc and orc.id, 'admin:', orc and orc.admin_id)
    # localizar proposta/obra ligadas e contagem de tarefas
```
  `python scripts/diag_baia.py`
- [ ] Confirmar: existe `Proposta` aprovada para a Baia? Existe `Obra`? O admin da Baia está em
  `versao_sistema`? Anotar os ids reais (orçamento id 98 segundo o mapa de código).
- [ ] **Decisão de rota** (anotar no commit): se NÃO há proposta/obra, o caminho mais curto é gerar
  proposta→obra a partir do orçamento (fluxo existente) e então materializar. Se já há obra sem
  cronograma, basta materializar.

### Task D2 — Script de materialização da Baia

- [ ] Criar `scripts/materializar_baia_rev10.py` espelhando `seed_demo_alfa.py:1101-1118`:

```python
"""Habilita a obra Baia REV10 para a espinha financeira (Fatia 1):
1) garante o admin em versao_sistema='v2';
2) materializa o cronograma da obra (TarefaCronograma + pesos) a partir do
   snapshot da proposta;
3) cria os ItemMedicaoComercial 1:1 (se ainda não existirem).

Idempotente: materializar_cronograma pula proposta_item já materializado.
"""
from app import app, db
from models import Usuario, Obra, ItemMedicaoComercial  # + Proposta/PropostaItem reais
from services.cronograma_proposta import materializar_cronograma, montar_arvore_preview


def run():
    with app.app_context():
        # --- ids reais confirmados na Task D1 ---
        ADMIN_ID = None   # preencher
        PROPOSTA_ID = None
        OBRA_ID = None

        admin = db.session.get(Usuario, ADMIN_ID)
        if admin.versao_sistema != 'v2':
            admin.versao_sistema = 'v2'
            db.session.commit()
            print('admin -> v2')

        from models import Proposta  # nome real confirmado na D1
        proposta = db.session.get(Proposta, PROPOSTA_ID)
        if not proposta.cronograma_default_json:
            proposta.cronograma_default_json = montar_arvore_preview(proposta, ADMIN_ID)
            db.session.commit()

        n = materializar_cronograma(
            proposta, ADMIN_ID, OBRA_ID, proposta.cronograma_default_json
        )
        db.session.commit()
        print(f'materializadas {n} tarefas')
        print('IMC:', ItemMedicaoComercial.query.filter_by(obra_id=OBRA_ID).count())


if __name__ == '__main__':
    run()
```

- [ ] Preencher os ids reais da Task D1 e os nomes de classe corretos (`Proposta` vs
  `PropostaComercial` — confirmar com `grep -n "class Proposta" models.py`).
- [ ] Rodar: `python scripts/materializar_baia_rev10.py`
- [ ] Verificar no diagnóstico que `TarefaCronograma` da Baia > 0 e que há `ItemMedicaoComercial`.
- [ ] **Ajustar pesos da medição se vierem por divisão igual** (mitigação do mapa §6): abrir a tela
  `/obras/<id>/medicao` e conferir/editar os pesos (editor `medicao_views.vincular_tarefa` já pronto;
  validação soma=100% em `medicao_service.py:68`). Isso afeta diretamente o agregado/orçado por
  atividade do read-model (D6 — fonte única).
- [ ] **Commit:** `chore(baia): materializa cronograma REV10 + flag v2 (habilita Fatia 1)`

---

## FASE E — Cenário end-to-end e fechamento

### Task E1 — Teste end-to-end na Baia (ou fixture equivalente)

- [ ] Adicionar a `tests/test_resultado_atividade_service.py` um teste que reproduz a jornada:
  materializar (via builders) uma atividade da Baia → lançar 2 RDOs por atividade →
  conferir Resultado, alarme e que a **soma do custo MO das atividades = custo de MO apontado**:

```python
def test_e2e_soma_custo_mo_fecha_com_apontado():
    from services.resultado_atividade_service import resultado_obra
    with app.app_context():
        t = _tarefa('E2E', percentual=100.0)
        _item_medicao(valor_comercial=2000, tarefa=t, peso=100)
        f = _func()
        r = _rdo(date(2026, 3, 1)); _mo(r, f, t, 8.0); _custo_diario(r, f, 500)
        db.session.commit()
        res = resultado_obra(_fx.obra.id)
        # custo MO somado nas atividades == custo apontado (500) para esta obra-cenário
        soma_ativ = sum((a['custo_mo'] for a in res['atividades']
                         if a['tarefa_id'] == t.id), Decimal('0'))
        assert soma_ativ == Decimal('500.00')
```

- [ ] Rodar a suíte completa da fatia:
  `python -m pytest tests/test_resultado_atividade_service.py tests/test_rdo_edicao_preserva_tarefa.py -x`

### Task E2 — Verificação manual no app

- [ ] Subir o app (ver skill `run` / `replit.md`); logar com o admin da Baia (v2).
- [ ] Abrir `/obras/<baia_id>/resultado` e conferir: atividades listadas, valores coerentes,
  selo de alarme aparecendo onde `real > orçado_para_avanço`.
- [ ] Editar um RDO da Baia e reabrir a tela — o custo da atividade **não pode** zerar (prova de
  que o bug da Fase A está corrigido em produção, não só no teste).

### Task E3 — Atualizar o estado do design

- [ ] Em `ESTADO_design_espinha_financeira.md`, marcar a Fatia 1 como implementada e listar o que
  ficou para a Fatia 2 (material/alimentação/transporte + subempreitada/telhado viga I).
- [ ] **Commit:** `docs: Fatia 1 implementada; aponta Fatia 2`

---

## Pontos de extensão para as fatias seguintes (não criar dívida)

Para a Fatia 2 reusar sem retrabalho (DC5/DC6 do plano-mestre), ao implementar a Fase B já deixar:

- **Helper de horas extraído** (DC6): dentro de `custo_mo_atividade` (Task B3), a soma de horas do
  funcionário no RDO já é uma subconsulta isolável. Extrair como função de módulo
  `_horas_func_no_rdo(rdo_id, func_id)` (e, opcionalmente, `_horas_atividade_no_rdo`) — a Fatia 2
  reusa o mesmo mecanismo para ratear custos compartilhados por hora-homem/dia. Não duplicar lógica
  de rateio depois.
- **Nome genérico do orçado** (DC5): `custo_mo_orcado_unitario(snapshot)` (Task B5) será, na Fatia 2,
  um caso particular de `custo_orcado_unitario(snapshot, tipos={'MAO_OBRA'})`. Escrever já delegando
  a um núcleo que filtra por `tipos` facilita — mas não é obrigatório nesta fatia; a Fatia 2 refatora.
- **`resultado_obra` com dict extensível**: as chaves `valor_agregado`, `custo_mo`, `resultado` são
  o contrato; a Fatia 2 acrescenta `custo_nao_mo` e `custo_incorrido` **sem remover** as existentes.
- **MO sempre do `RDOCustoDiario`** (DC3): manter `custo_mo_atividade` lendo só `RDOCustoDiario` —
  a Fatia 2 lê o ledger `GestaoCustoFilho` **apenas** para categorias não-MO, evitando dupla contagem.

## Revisão final (checklist do skill writing-plans)

1. **Cobertura da spec (§Fatia 1):**
   - valor_agregado ✅ B2 · custo_mo (D1) ✅ B3 · resultado ✅ B4 · custo_mo_orcado ✅ B5 ·
     alarme R$ (D5) ✅ B6 · índice horas ✅ B7 · peso da medição (D6) ✅ usado em B2/B5/B7 ·
     rollup ✅ B8 · UI ✅ C1–C3 · bug edição RDO ✅ A1–A3 · materialização + v2 ✅ D · sem migration ✅.
   - Critérios de aceite da spec cobertos por E1 (soma custo = apontado) e E2 (edição não quebra).
2. **Sem placeholders:** todo passo de código traz o código completo; os 3 pontos que dependem de
   dado real do ambiente (ids da Baia, nome exato da classe `Proposta`, rota real de edição do RDO,
   nome do template-base) estão marcados como **passo de verificação explícito com o comando `grep`
   a rodar** — não como "TODO".
3. **Consistência de tipos:** todas as funções do serviço retornam `Decimal` quantizado a `0.01`
   (índices a `0.001`); os modelos e campos batem com `models.py` (tabela do §1); `composicao_snapshot`
   usa `tipo='MAO_OBRA'` (maiúsc.) e `unidade='h'` (minúsc.), como nos dados reais.

## Riscos conhecidos (herdados do design)
- Pesos semeados por divisão igual na materialização → ajustar na tela de medição (D6), não é campo
  novo (Task D2 último passo).
- Gate v2: a tela e o cálculo só fazem sentido com a obra/admin em `versao_sistema='v2'` (Task D2).
- `montar_arvore_preview`/`materializar_cronograma` dependem de um template/serviços já cadastrados
  para a Baia; se o orçamento 98 não tem composição completa, `custo_mo_orcado` virá zerado para os
  itens sem snapshot — o alarme degrada para "sem orçado", não quebra (verificar na E2).
