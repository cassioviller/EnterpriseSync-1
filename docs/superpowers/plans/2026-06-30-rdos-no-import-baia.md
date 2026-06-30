# RDOs no payload de import da Baia — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O import físico-financeiro da Baia passa a criar os RDOs (com mão de obra e apontamentos de avanço físico) a partir de uma seção `rdos` no JSON, fiel ao relatório semanal 22–27/06 — reimportar deixa de orfanar/zerar o físico.

**Architecture:** Novo helper `_materializar_rdos(obra, admin_id, rdos, tid_to_db)` em `services/importacao_fisico_financeiro.py`, chamado ao fim de `importar_fisico_financeiro` (antes do `commit`), seguido de `sincronizar_percentuais_obra`. Os apontamentos referenciam tarefas pelo id do `.mpp` (`tarefa_mpp`), traduzido pelo `tid_to_db` que o import já monta. A seção `rdos` (6 RDOs da Baia) entra na fixture canônica. Idempotente: o helper apaga os RDOs da obra antes de recriar.

**Tech Stack:** Flask + SQLAlchemy (Postgres), `pytest`. Sem migração (usa tabelas RDO já existentes).

## Global Constraints

- **Obra-piloto:** Baia. **Invariantes financeiros inalterados:** veks 800.960 / fat 550.775 / lucro 24.976 / imposto 128.903 / contrato 1.505.613,76 / data_fim 08/10.
- **Físico vem só do RDO** (não do `pct_fisico` do JSON, zerado no fix `13bca494`).
- **RDO mão de obra NÃO gera custo** no Realizado (custo de mão de obra vem de `registro_ponto`). Mão de obra no RDO é só realismo do documento.
- **`numero_rdo`** é `String(20)` unique: formato `RDO-{admin_id}-{obra.id}-{AAAAMMDD}` (curto, único por obra/dia).
- **`RDOMaoObra.funcionario_id`** é FK não-nula → só anexa mão de obra se houver `Funcionario` ativo; nunca falha o import por falta de funcionário.
- **Idempotência:** reimportar não duplica RDOs.
- **Sem `rdos` no payload** → nenhum RDO criado, import não quebra (regressão p/ outras obras).
- Suíte de regressão (rodar ao fim de cada task):
  ```
  python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q
  ```

---

## File Structure

| Arquivo | Responsabilidade | Mudança |
|---|---|---|
| `services/importacao_fisico_financeiro.py` | Orquestra o import; materializa cronograma | **Modificar** — helper `_materializar_rdos` + chamada + sync (l.343 já produz `tid_to_db`; inserção antes do `commit` l.429) |
| `tests/fixtures/cronograma_fisico_financeiro_baias.json` | Payload canônico da Baia | **Modificar** — nova seção top-level `rdos` (6 RDOs) |
| `tests/test_importacao_fisico_financeiro.py` | Testes do import | **Modificar** — RDOs criados, percentuais por tarefa, idempotência, ausência de `rdos` |

---

## Task 1: Helper `_materializar_rdos` + integração no import

**Files:**
- Modify: `services/importacao_fisico_financeiro.py` (novo helper após `_vincular_etapa_tarefas` ~l.229; chamada antes do `db.session.commit()` ~l.429)
- Test: `tests/test_importacao_fisico_financeiro.py`

**Interfaces:**
- Consumes: `tid_to_db: dict[int,int]` (produzido por `_materializar_cronograma_mpp`, atribuído em `importar_fisico_financeiro` l.343); `_parse_date` (helper do módulo); `sincronizar_percentuais_obra(obra_id, admin_id, cliente=False)` de `utils.cronograma_engine`.
- Produces: `_materializar_rdos(obra, admin_id, rdos: list[dict], tid_to_db: dict) -> int` (nº de RDOs criados). Cria `RDO` + `RDOMaoObra` (opcional) + `RDOApontamentoCronograma`; idempotente (apaga RDOs da obra antes).

- [ ] **Step 1: Write the failing test**

Adicionar a `tests/test_importacao_fisico_financeiro.py` (no topo do arquivo já há `from main import app` / `app`, `db`, `_novo_admin`; seguir o padrão dos testes existentes):

```python
def test_import_cria_rdos_da_secao_rdos():
    """Import com seção `rdos` cria 1 RDO por item e sincroniza o % das tarefas."""
    import json, os
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import RDO, TarefaCronograma
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        payload = json.load(open(caminho, encoding='utf-8'))
        # injeta uma seção rdos mínima (independente do conteúdo final da fixture)
        payload['rdos'] = [
            {"data": "2026-06-22", "clima": "Nublado", "precipitacao": "Sem chuva",
             "comentario": "Topografia.", "mao_de_obra": 0,
             "apontamentos": [{"tarefa_mpp": 3, "pct": 100}, {"tarefa_mpp": 4, "pct": 50}]},
            {"data": "2026-06-27", "clima": "Ensolarado", "precipitacao": "Sem chuva",
             "comentario": "Nivelamento galpão B.", "mao_de_obra": 0,
             "apontamentos": [{"tarefa_mpp": 3, "pct": 100}, {"tarefa_mpp": 4, "pct": 65},
                              {"tarefa_mpp": 6, "pct": 20}]},
        ]
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        assert RDO.query.filter_by(obra_id=oid, admin_id=aid).count() == 2
        por_nome = {t.nome_tarefa: t for t in
                    TarefaCronograma.query.filter_by(obra_id=oid, admin_id=aid).all()}
        assert float(por_nome['ESTUDO DE SOLO SPT'].percentual_concluido) == 100.0
        assert float(por_nome['EXECUÇÃO DE PROJETOS. LSF, TELHADO, PISO, BALDRAME, FUNDAÇÃO PARA PILARES DE MADEIRA'].percentual_concluido) == 65.0
        assert float(por_nome['FAZENDA: NIVELAMENTO DO PLATÔ'].percentual_concluido) == 20.0
        assert float(por_nome['MOBILIZAÇÃO EQUIPE'].percentual_concluido) == 0.0
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_import_cria_rdos_da_secao_rdos -v`
Expected: FAIL — nenhum RDO é criado (`count() == 0`), pois o import ainda ignora `rdos`.

- [ ] **Step 3: Escrever o helper `_materializar_rdos`**

Em `services/importacao_fisico_financeiro.py`, logo após a função `_vincular_etapa_tarefas` (~l.229), adicionar:

```python
def _materializar_rdos(obra, admin_id, rdos, tid_to_db):
    """Cria os RDOs da obra a partir do payload (seção `rdos`), referenciando as
    tarefas pelo id do .mpp (traduzido por `tid_to_db`). Idempotente: apaga os RDOs
    da obra antes de recriar. Mão de obra é só realismo do documento (não gera
    custo). Retorna o nº de RDOs criados. Ver spec 2026-06-30-rdos-no-import-baia."""
    from app import db
    from models import RDO, RDOMaoObra, RDOApontamentoCronograma, Funcionario

    if not rdos:
        return 0

    # Idempotência: remove RDOs anteriores desta obra (cascata limpa mão de obra
    # e apontamentos).
    for r in RDO.query.filter_by(obra_id=obra.id, admin_id=admin_id).all():
        db.session.delete(r)
    db.session.flush()

    funcs = Funcionario.query.filter_by(admin_id=admin_id, ativo=True).limit(10).all()
    criados = 0
    for item in rdos:
        dia = _parse_date(item.get('data'))
        if dia is None:
            continue
        rdo = RDO(
            numero_rdo=f"RDO-{admin_id}-{obra.id}-{dia.strftime('%Y%m%d')}",
            obra_id=obra.id, admin_id=admin_id, criado_por_id=admin_id,
            data_relatorio=dia, local='Campo', status='Finalizado',
            clima_geral=(item.get('clima') or 'Não informado')[:50],
            precipitacao=(item.get('precipitacao') or '')[:20],
            comentario_geral=item.get('comentario') or '',
        )
        db.session.add(rdo)
        db.session.flush()

        qtd_mo = int(item.get('mao_de_obra') or 0)
        for f in funcs[:qtd_mo]:
            funcao_nome = getattr(getattr(f, 'funcao_ref', None), 'nome', None) \
                or getattr(f, 'funcao', None) or 'Operário'
            db.session.add(RDOMaoObra(
                rdo_id=rdo.id, admin_id=admin_id, funcionario_id=f.id,
                funcao_exercida=str(funcao_nome)[:100], horas_trabalhadas=8.0))

        for ap in (item.get('apontamentos') or []):
            db_id = tid_to_db.get(ap.get('tarefa_mpp'))
            if db_id is None:
                continue
            pct = float(ap.get('pct') or 0)
            db.session.add(RDOApontamentoCronograma(
                rdo_id=rdo.id, tarefa_cronograma_id=db_id, admin_id=admin_id,
                quantidade_executada_dia=0.0, quantidade_acumulada=0.0,
                percentual_realizado=pct, percentual_planejado=None))
        criados += 1

    db.session.flush()
    return criados
```

- [ ] **Step 4: Ligar o helper no orquestrador + sincronizar**

Em `services/importacao_fisico_financeiro.py`, no fim de `importar_fisico_financeiro`, substituir o bloco (l.427-429):

```python
    obra.fluxo_caixa_planilha = payload.get('fluxo_caixa_mensal')

    db.session.commit()
```

por:

```python
    obra.fluxo_caixa_planilha = payload.get('fluxo_caixa_mensal')

    # RDOs (físico real) a partir do payload; depois sincroniza o % das tarefas
    # pelo último apontamento. `tid_to_db` foi montado em _materializar_cronograma_mpp.
    _materializar_rdos(obra, admin_id, payload.get('rdos', []), tid_to_db)
    db.session.flush()
    from utils.cronograma_engine import sincronizar_percentuais_obra
    sincronizar_percentuais_obra(obra.id, admin_id)

    db.session.commit()
```

- [ ] **Step 5: Run it — expect PASS**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_import_cria_rdos_da_secao_rdos -v`
Expected: PASS.

- [ ] **Step 6: Teste de idempotência + ausência de `rdos`**

Adicionar a `tests/test_importacao_fisico_financeiro.py`:

```python
def test_import_rdos_idempotente_e_opcional():
    """Reimportar não duplica RDOs; payload sem `rdos` não cria nada e não quebra."""
    import json, os
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import RDO
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        payload = json.load(open(caminho, encoding='utf-8'))
        payload['rdos'] = [
            {"data": "2026-06-22", "apontamentos": [{"tarefa_mpp": 3, "pct": 100}]},
        ]
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        importar_fisico_financeiro(payload, aid)  # reimport
        assert RDO.query.filter_by(obra_id=oid, admin_id=aid).count() == 1

        sem = json.load(open(caminho, encoding='utf-8'))
        sem.pop('rdos', None)
        aid2 = _novo_admin()
        oid2 = importar_fisico_financeiro(sem, aid2)['obra_id']
        assert RDO.query.filter_by(obra_id=oid2, admin_id=aid2).count() == 0
```

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_import_rdos_idempotente_e_opcional -v`
Expected: PASS.

- [ ] **Step 7: Suíte de regressão**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde (a fixture ainda não tem `rdos`; os testes novos injetam a seção no payload — invariantes da Baia preservados).

- [ ] **Step 8: Commit**

```bash
git add services/importacao_fisico_financeiro.py tests/test_importacao_fisico_financeiro.py
git commit -m "feat(baia): import materializa RDOs da seção 'rdos' do payload (físico pelo RDO)"
```

---

## Task 2: Seção `rdos` da Baia na fixture (relatório 22–27/06)

**Files:**
- Modify: `tests/fixtures/cronograma_fisico_financeiro_baias.json` (nova chave top-level `rdos`)
- Test: `tests/test_importacao_fisico_financeiro.py`

**Interfaces:**
- Consumes: `_materializar_rdos` (Task 1) — lê `data`, `clima`, `precipitacao`, `comentario`, `mao_de_obra`, `apontamentos[].tarefa_mpp`, `apontamentos[].pct`.
- Produces: a fixture importável já traz os 6 RDOs da Baia; reimportar restaura o físico do relatório.

- [ ] **Step 1: Write the failing test**

Adicionar a `tests/test_importacao_fisico_financeiro.py` (importa a fixture **sem** injetar `rdos` — depende do conteúdo do arquivo):

```python
def test_fixture_baia_traz_rdos_do_relatorio():
    """A fixture canônica da Baia já contém os 6 RDOs do relatório 22–27/06 e o
    import reproduz o físico: solo 100%, projetos 65%, nivelamento 20%."""
    import json, os
    from services.importacao_fisico_financeiro import importar_fisico_financeiro
    from models import RDO, TarefaCronograma
    with app.app_context():
        aid = _novo_admin()
        caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                               'cronograma_fisico_financeiro_baias.json')
        payload = json.load(open(caminho, encoding='utf-8'))
        assert len(payload.get('rdos', [])) == 6
        oid = importar_fisico_financeiro(payload, aid)['obra_id']
        assert RDO.query.filter_by(obra_id=oid, admin_id=aid).count() == 6
        por_nome = {t.nome_tarefa: float(t.percentual_concluido or 0) for t in
                    TarefaCronograma.query.filter_by(obra_id=oid, admin_id=aid).all()}
        assert por_nome['ESTUDO DE SOLO SPT'] == 100.0
        assert por_nome['EXECUÇÃO DE PROJETOS. LSF, TELHADO, PISO, BALDRAME, FUNDAÇÃO PARA PILARES DE MADEIRA'] == 65.0
        assert por_nome['FAZENDA: NIVELAMENTO DO PLATÔ'] == 20.0
        assert por_nome['MOBILIZAÇÃO EQUIPE'] == 0.0
        assert por_nome['MARCAÇÃO DE OBRA'] == 0.0
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_fixture_baia_traz_rdos_do_relatorio -v`
Expected: FAIL — `len(payload['rdos'])` é 0 (a fixture ainda não tem a seção).

- [ ] **Step 3: Adicionar a seção `rdos` à fixture**

Em `tests/fixtures/cronograma_fisico_financeiro_baias.json`, adicionar a chave top-level `"rdos"` (ao lado de `"fluxo_caixa_mensal"`), com exatamente este conteúdo:

```json
"rdos": [
  {
    "data": "2026-06-22",
    "clima": "Nublado",
    "precipitacao": "Sem chuva",
    "comentario": "Responsabilidades repassadas à equipe da Fazenda para liberação das frentes. Apresentada à Kabod a necessidade de instalações provisórias (container com banheiro). Topógrafo realizou o levantamento dos níveis do terreno; dados enviados para análise da engenharia.",
    "mao_de_obra": 2,
    "apontamentos": [
      {"tarefa_mpp": 3, "pct": 100},
      {"tarefa_mpp": 4, "pct": 50}
    ]
  },
  {
    "data": "2026-06-23",
    "clima": "Chuvoso",
    "precipitacao": "Chuva forte",
    "comentario": "Análise topográfica identificou desnível de ~35 cm entre o terreno das baias e a calçada da Cabana; a marcação prevista para 24/06 foi suspensa até o nivelamento dos platôs pela Fazenda. Visita técnica do Eng. Alan. Relatório de sondagem enviado à Kabod. Fortes chuvas impediram a terraplenagem; executadas apenas a retirada da caixa d'água e a remoção parcial do morro.",
    "mao_de_obra": 2,
    "apontamentos": [
      {"tarefa_mpp": 3, "pct": 100},
      {"tarefa_mpp": 4, "pct": 55}
    ]
  },
  {
    "data": "2026-06-24",
    "clima": "Chuvoso",
    "precipitacao": "Chuva forte",
    "comentario": "Chuvas pela manhã impediram novamente a terraplenagem. Reunião com o Sr. André (AJR): cerca de 2 dias de estiagem necessários para a entrada dos equipamentos. Reunião com a Sra. Ana (Fazenda) sobre a adequação do platô. Solicitados projetos hidráulico/elétrico e detalhes das calçadas. Enviados os projetos de cobertura e pilares metálicos e o cronograma com entrega em 08/10/26. Reforçada a infraestrutura provisória (energia/água por galpão, containers, caçamba, remoção de entulho).",
    "mao_de_obra": 2,
    "apontamentos": [
      {"tarefa_mpp": 3, "pct": 100},
      {"tarefa_mpp": 4, "pct": 65}
    ]
  },
  {
    "data": "2026-06-25",
    "clima": "Parcialmente nublado",
    "precipitacao": "Garoa",
    "comentario": "Redução das chuvas pela manhã. A empresa de terraplenagem confirmou a autorização da Fazenda para o nivelamento dos platôs, tomando como referência a cota da calçada da Cabana existente.",
    "mao_de_obra": 1,
    "apontamentos": [
      {"tarefa_mpp": 3, "pct": 100},
      {"tarefa_mpp": 4, "pct": 65}
    ]
  },
  {
    "data": "2026-06-26",
    "clima": "Nublado",
    "precipitacao": "Sem chuva",
    "comentario": "Terreno ainda saturado pelas chuvas acumuladas; possível início do nivelamento em 27/06, conforme as condições climáticas. A equipe de fundação permanece mobilizada, com início previsto em 29/06 (montagem dos gabaritos e recebimento dos materiais de fundação).",
    "mao_de_obra": 1,
    "apontamentos": [
      {"tarefa_mpp": 3, "pct": 100},
      {"tarefa_mpp": 4, "pct": 65}
    ]
  },
  {
    "data": "2026-06-27",
    "clima": "Ensolarado",
    "precipitacao": "Sem chuva",
    "comentario": "A equipe de terraplenagem da AJR (contratada pela Fazenda) iniciou o nivelamento do platô do galpão B. Mantidos os piquetes das 4 extremidades do platô. A equipe trabalhará no domingo (28/06) para tentar concluir o galpão B; segunda-feira depende do jogo do Brasil.",
    "mao_de_obra": 3,
    "apontamentos": [
      {"tarefa_mpp": 3, "pct": 100},
      {"tarefa_mpp": 4, "pct": 65},
      {"tarefa_mpp": 6, "pct": 20}
    ]
  }
]
```

- [ ] **Step 4: Validar o JSON**

Run: `python -c "import json; d=json.load(open('tests/fixtures/cronograma_fisico_financeiro_baias.json')); print('rdos', len(d['rdos']))"`
Expected: `rdos 6` (sem erro de parse).

- [ ] **Step 5: Run it — expect PASS**

Run: `python -m pytest tests/test_importacao_fisico_financeiro.py::test_fixture_baia_traz_rdos_do_relatorio -v`
Expected: PASS.

- [ ] **Step 6: Suíte de regressão**

Run: `python -m pytest tests/test_cronograma_fisico_financeiro.py tests/test_painel_financeiro.py tests/test_importacao_fisico_financeiro.py -q`
Expected: verde; invariantes financeiros da Baia preservados (os RDOs só afetam o físico, não os custos).

- [ ] **Step 7: Commit**

```bash
git add tests/fixtures/cronograma_fisico_financeiro_baias.json tests/test_importacao_fisico_financeiro.py
git commit -m "feat(baia): fixture traz os 6 RDOs do relatório semanal 22-27/06 (físico real no reimport)"
```

---

## Task 3: Verificação no app real + fechamento

**Files:**
- (sem código novo) — verificação manual e suíte ampla.

- [ ] **Step 1: App importa**

Run: `python -c "from app import app; print('app import ok')"`
Expected: `app import ok`.

- [ ] **Step 2: Reimportar a Baia e conferir no cronograma físico (browser real)**

Subir a app (`gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app`). Logar como
`admin@construtoraalfa.com.br` / `Alfa@2026`. Reimportar a Baia (Importação → JSON, a fixture
`cronograma_fisico_financeiro_baias.json`) e conferir, no **cronograma físico** da obra:
1. ESTUDO DE SOLO SPT = **100%**; EXECUÇÃO DE PROJETOS = **65%**; FAZENDA: NIVELAMENTO DO PLATÔ = **20%**.
2. MOBILIZAÇÃO EQUIPE / MARCAÇÃO / FUNDAÇÃO e demais = **0%**.
3. Aba de RDOs da obra: **6 RDOs** (22→27/06), com clima e comentários do relatório.
4. Reimportar de novo → continua com **6 RDOs** (sem duplicar) e os mesmos percentuais.

- [ ] **Step 3: Suíte ampla (não-browser)**

Run: `python -m pytest -q --ignore=scripts --ignore=archive -k "not playwright and not browser"`
Expected: sem regressões fora do escopo (falhas pré-existentes são Playwright/ambiente e os erros de coleta em `scripts/`/`archive/`).

- [ ] **Step 4: Atualizar o handoff**

Em `ESTADO_ATUALIZACAO_BAIA.md`, registrar (1-2 linhas) que os RDOs da Baia agora vêm do import
(seção `rdos`) e que `seed_rdos_baias.py` não é mais necessário para a Baia.

```bash
git add ESTADO_ATUALIZACAO_BAIA.md
git commit -m "docs(baia): RDOs da Baia migram para o import; seed_rdos_baias dispensável"
```

---

## Sequência de dependências

```
T1 (helper + integração) → T2 (fixture com os 6 RDOs) → T3 (verificação + fechamento)
```

## Rollback

Cada task é um commit isolado. Reverter T2 deixa o mecanismo (T1) intacto, sem RDOs na fixture
(import volta a não criar RDOs). Reverter T1 remove o helper; a chave `rdos` na fixture passa a
ser ignorada (nenhum consumidor) — sem quebra. Não há migração de schema.

---

## Self-Review

**1. Spec coverage**

| Requisito da spec | Task |
|---|---|
| Seção `rdos` no payload (formato data/clima/precip/comentario/mao_de_obra/apontamentos) | T1 (consumo) + T2 (dados) |
| Helper `_materializar_rdos` + idempotência (apaga RDOs antes) | T1 |
| Referência por `tarefa_mpp` via `tid_to_db` | T1 |
| Sincronização do `percentual_concluido` (`sincronizar_percentuais_obra`) | T1 |
| Mão de obra opcional, não-nula, sem quebrar sem funcionário | T1 (helper `funcs[:qtd_mo]`) |
| Sem `rdos` → import não quebra | T1 Step 6 |
| 6 RDOs fiéis ao relatório 22–27/06 | T2 |
| Físico resultante: solo 100 / projetos 65 / nivelamento 20 / demais 0 | T1 Step 1 + T2 Step 1 |
| Invariantes financeiros preservados | T1 Step 7 / T2 Step 6 |
| Verificação no app real | T3 Step 2 |

**2. Placeholder scan** — sem TBD/TODO; cada step de código mostra o código completo; comandos com expected output. Verificação de UI é manual (T3), mesmo padrão das rodadas anteriores.

**3. Type consistency** —
- `_materializar_rdos(obra, admin_id, rdos, tid_to_db) -> int` definida em T1 Step 3 e chamada em T1 Step 4 com a mesma assinatura (`payload.get('rdos', [])`, `tid_to_db`).
- `tid_to_db` é o dict `{mpp_id: tarefa_cronograma_id}` produzido por `_materializar_cronograma_mpp` (l.343); `tarefa_mpp` do JSON é a chave; valores são ids de `TarefaCronograma`.
- `RDOApontamentoCronograma.percentual_realizado` (float) ← `apontamentos[].pct`; `sincronizar_percentuais_obra` copia para `TarefaCronograma.percentual_concluido` (tarefas sem `quantidade_total`).
- `nome_tarefa` usado nos asserts é o campo do modelo `TarefaCronograma` (preenchido em `_materializar_cronograma_mpp` a partir de `cronograma_tarefas[].nome`).
</content>
