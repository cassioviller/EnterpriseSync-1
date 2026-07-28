"""Módulo 02 — schema do versionamento de cronograma (migrations 207-210).

Cobre: existência de tabelas/colunas/índices, idempotência de reexecução
e backfill (versão nº1 + tipo_apontamento). Padrão de asserts de schema:
test_medicao_contrato_schema_existe (tests/test_importacao_fisico_financeiro.py).
"""
import pytest
from sqlalchemy import text

from app import app, db

TABELAS_NOVAS = [
    'cronograma_importacao',
    'cronograma_versao',
    'cronograma_tarefa_snapshot',
    'cronograma_tarefa_mapeamento',
    'cronograma_importacao_evento',
]

COLUNAS_TAREFA = ['mpp_uid', 'wbs_codigo', 'fingerprint', 'is_marco',
                  'ativa', 'arquivada_em', 'versao_criacao_id']

COLUNAS_APONTAMENTO = ['tipo_apontamento', 'percentual_acumulado',
                       'percentual_incremento_dia',
                       'quantidade_total_snapshot', 'unidade_snapshot']


def _tem_tabela(nome):
    with db.engine.connect() as conn:
        return conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_name = :t)"), {'t': nome}).scalar()


def _colunas(tabela):
    with db.engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t"), {'t': tabela}).fetchall()
    return {r[0] for r in rows}


def test_tabelas_novas_existem():
    with app.app_context():
        faltando = [t for t in TABELAS_NOVAS if not _tem_tabela(t)]
        assert not faltando, f'tabelas ausentes: {faltando}'


def test_colunas_novas_tarefa_cronograma():
    with app.app_context():
        cols = _colunas('tarefa_cronograma')
        faltando = [c for c in COLUNAS_TAREFA if c not in cols]
        assert not faltando, f'colunas ausentes em tarefa_cronograma: {faltando}'


def test_colunas_novas_rdo_apontamento():
    with app.app_context():
        cols = _colunas('rdo_apontamento_cronograma')
        faltando = [c for c in COLUNAS_APONTAMENTO if c not in cols]
        assert not faltando, f'colunas ausentes em rdo_apontamento_cronograma: {faltando}'


def test_unique_uma_versao_ativa_por_obra():
    """Índice parcial: no máximo 1 cronograma_versao ativa por obra."""
    with app.app_context():
        with db.engine.connect() as conn:
            idx = conn.execute(text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename = 'cronograma_versao' "
                "AND indexdef ILIKE '%%status%%ativa%%'")).fetchall()
        assert idx, 'índice parcial WHERE status=ativa não existe'


def test_reexecucao_das_migracoes_e_noop():
    """run_migration_safe pula por migration_history; e o DDL em si é
    idempotente (IF NOT EXISTS) — as funções podem rodar de novo sem erro."""
    from migrations import (_migration_207_cronograma_versionamento,
                            _migration_208_tarefa_cronograma_identidade,
                            _migration_209_rdo_apontamento_semantico)
    with app.app_context():
        _migration_207_cronograma_versionamento()
        _migration_208_tarefa_cronograma_identidade()
        _migration_209_rdo_apontamento_semantico()


# ─────────────────────────────────────────────────────────────────────────────
# Migration 210 — backfill (versão nº1 + snapshots + tipo_apontamento).
# Fixture no padrão dos testes de importação (tests/test_importacao_fisico_
# financeiro.py): admin novo + importar_fisico_financeiro(baias) e, depois,
# limpeza do estado pós-migração para simular o banco PRÉ-210 — tudo filtrado
# por admin_id/obra_id próprios (nunca toca dados de outros admins).
# ─────────────────────────────────────────────────────────────────────────────
import json
import os
from datetime import datetime

from werkzeug.security import generate_password_hash


def _suffix() -> str:
    # Padrão de tests/test_caracterizacao_apontamento_cronograma.py:60
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def _carregar_json():
    caminho = os.path.join(os.path.dirname(__file__), 'fixtures',
                           'cronograma_fisico_financeiro_baias.json')
    with open(caminho, encoding='utf-8') as f:
        return json.load(f)


def _novo_admin(prefixo: str) -> int:
    from models import Usuario, TipoUsuario
    suf = _suffix()
    u = Usuario(username=f'{prefixo}_{suf}',
                email=f'{prefixo}_{suf}@test.local',
                nome=f'Admin {prefixo} {suf}',
                password_hash=generate_password_hash('Senha@2026'),
                tipo_usuario=TipoUsuario.ADMIN)
    db.session.add(u)
    db.session.commit()
    return u.id


@pytest.fixture
def ambiente_baias(tmp_path):
    """Admin próprio + importação das baias + estado PRÉ-210 simulado:
    apaga versão/snapshots da obra criada e zera as colunas novas (209) dos
    apontamentos DESTE admin — os campos antigos ficam intactos."""
    from services import importacao_fisico_financeiro as ff
    app.config['TESTING'] = True
    # Isola FOTOS_RDO_BASE (padrão do _fotos_base_isolada dos testes de
    # importação) para não processar as fotos reais do repo.
    orig_fotos = ff.FOTOS_RDO_BASE
    vazio = tmp_path / '_fotos_vazio'
    vazio.mkdir(exist_ok=True)
    ff.FOTOS_RDO_BASE = str(vazio)
    try:
        with app.app_context():
            admin_id = _novo_admin('bkf210')
            res = ff.importar_fisico_financeiro(_carregar_json(), admin_id)
            obra_id = res['obra_id']
            with db.engine.begin() as conn:
                conn.execute(text(
                    "DELETE FROM cronograma_tarefa_snapshot WHERE versao_id IN "
                    "(SELECT id FROM cronograma_versao WHERE obra_id = :o)"),
                    {'o': obra_id})
                conn.execute(text(
                    "DELETE FROM cronograma_versao WHERE obra_id = :o"),
                    {'o': obra_id})
                conn.execute(text(
                    "UPDATE rdo_apontamento_cronograma SET "
                    "tipo_apontamento = NULL, percentual_acumulado = NULL, "
                    "percentual_incremento_dia = NULL, "
                    "quantidade_total_snapshot = NULL, unidade_snapshot = NULL "
                    "WHERE admin_id = :a"), {'a': admin_id})
            db.session.expire_all()
        yield {'admin_id': admin_id, 'obra_id': obra_id}
    finally:
        ff.FOTOS_RDO_BASE = orig_fotos


@pytest.mark.integration
def test_backfill_cria_versao_1_e_snapshots(ambiente_baias):
    """Obra com tarefas ganha versão nº1 ativa e 1 snapshot por tarefa.

    A migração é GLOBAL: varre toda obra do banco sem versão (89 num dev
    típico, e cresce a cada suíte que cria tarefas). Este teste falhava
    sozinho porque uma obra alheia quebrando abortava o laço antes de chegar
    na obra da fixture — a 210 agora isola a falha por obra, então o
    resultado desta obra não depende mais do resto do banco.

    O `.one()` de antes agravava: confundia "não criou" com "criou duas" e
    não dizia qual dos dois aconteceu.
    """
    from migrations import _migration_210_backfill_versao_inicial
    from models import CronogramaVersao, CronogramaTarefaSnapshot, TarefaCronograma
    with app.app_context():
        obra_id = ambiente_baias['obra_id']
        admin_id = ambiente_baias['admin_id']

        # Pré-condição explícita: sem isto, um backfill que não fizesse nada
        # passaria despercebido caso a fixture deixasse de zerar as versões.
        assert CronogramaVersao.query.filter_by(obra_id=obra_id).count() == 0, (
            'a fixture deveria ter apagado as versões da obra antes do teste')

        _migration_210_backfill_versao_inicial()

        versoes = CronogramaVersao.query.filter_by(
            obra_id=obra_id, status='ativa').all()
        assert len(versoes) == 1, (
            f'esperava 1 versão ativa para a obra {obra_id}, achei '
            f'{len(versoes)}: {[(v.id, v.numero, v.observacao) for v in versoes]}')
        v = versoes[0]
        assert v.numero == 1
        assert v.observacao == 'backfill inicial'
        n_tarefas = TarefaCronograma.query.filter_by(obra_id=obra_id, admin_id=admin_id).count()
        n_snaps = CronogramaTarefaSnapshot.query.filter_by(versao_id=v.id).count()
        assert n_snaps == n_tarefas


@pytest.mark.integration
def test_backfill_isola_a_obra_que_falha_e_depois_levanta(ambiente_baias):
    """Obra quebrada não bloqueia as outras — mas a migração AINDA falha.

    Duas propriedades numa tacada, e as duas importam:

    1. **Isolamento** — a 210 roda no startup e varre o banco inteiro; uma
       obra com problema não pode impedir a versão de todas as demais.
    2. **Propagação no fim** — `run_migration_safe` (migrations.py:168-199)
       já engolia toda exceção e registrava 'failed' SEM derrubar o boot; o
       comentário dele é literal ("Não propagar exceção - apenas logar").
       Quem levanta é RETENTADO na próxima subida, porque
       `is_migration_executed` só pula status 'success'. Uma versão anterior
       desta correção engolia a falha e retornava normal — a migração era
       carimbada 'success' e a obra pulada nunca mais era revisitada, ficando
       para sempre sem linha de base (e a 1ª importação .mpp dela,
       irreversível).

    A falha é INJETADA, não construída a partir de um defeito de dado: o
    defeito que a versão anterior deste teste usava (tarefas com admin_id
    divergente) é exatamente o que a correção do agrupamento eliminou, então
    o `except` virou código morto e o teste passava com ou sem isolamento.
    """
    from unittest.mock import patch
    from migrations import _migration_210_backfill_versao_inicial
    from models import CronogramaVersao, Obra, TarefaCronograma
    from sqlalchemy import text as sa_text

    with app.app_context():
        obra_boa = ambiente_baias['obra_id']
        molde = db.session.get(Obra, obra_boa)
        ruim = Obra(nome=f'{molde.nome} RUIM', codigo=f'{molde.codigo}R',
                    data_inicio=molde.data_inicio, admin_id=molde.admin_id,
                    cliente_id=molde.cliente_id, valor_contrato=1000)
        db.session.add(ruim)
        db.session.commit()
        obra_ruim = ruim.id
        db.session.add(TarefaCronograma(
            obra_id=obra_ruim, admin_id=molde.admin_id,
            nome_tarefa='Tarefa da obra ruim', ordem=1, duracao_dias=1))
        db.session.commit()

        real_begin = db.engine.begin

        def begin_que_falha_na_obra_ruim(*a, **kw):
            # Falha UMA vez, na última transação de obra: prova que as
            # anteriores foram commitadas. Uma vez só porque logo depois do
            # laço a 210 abre outra transação (o UPDATE de tipo_apontamento)
            # que NÃO está sob o `try` por obra — se o mock continuasse
            # levantando, o teste mediria aquela falha, não a da obra.
            f = begin_que_falha_na_obra_ruim
            if f.restantes == 0 and not f.ja_falhou:
                f.ja_falhou = True
                raise RuntimeError('falha injetada nesta obra')
            f.restantes = max(0, f.restantes - 1)
            return real_begin(*a, **kw)

        n_obras = db.session.execute(sa_text("""
            SELECT count(*) FROM (
              SELECT t.obra_id FROM tarefa_cronograma t
              JOIN obra o ON o.id = t.obra_id
              WHERE NOT EXISTS (SELECT 1 FROM cronograma_versao v
                                WHERE v.obra_id = t.obra_id)
              GROUP BY t.obra_id, o.admin_id) x""")).scalar()
        assert n_obras >= 2, (
            f'o teste precisa de ao menos 2 obras pendentes, achei {n_obras}')
        begin_que_falha_na_obra_ruim.restantes = n_obras - 1
        begin_que_falha_na_obra_ruim.ja_falhou = False

        try:
            with patch.object(db.engine, 'begin',
                              side_effect=begin_que_falha_na_obra_ruim):
                with pytest.raises(Exception) as exc:
                    _migration_210_backfill_versao_inicial()
            assert 'sem versão' in str(exc.value), (
                f'esperava o erro do backfill incompleto, veio: {exc.value}')

            # ...e mesmo assim as obras que deram certo ficaram gravadas.
            assert CronogramaVersao.query.filter_by(
                obra_id=obra_boa, status='ativa').count() == 1, (
                'a obra da fixture ficou sem versão — o laço parou na obra '
                'que falhou, em vez de isolá-la')
        finally:
            db.session.rollback()
            db.session.execute(sa_text('DELETE FROM obra WHERE id = :o'),
                               {'o': obra_ruim})
            db.session.commit()


@pytest.mark.integration
def test_versao_do_backfill_pertence_ao_dono_da_obra(ambiente_baias):
    """Posse: a versão é do admin da OBRA, e o snapshot é do admin da versão.

    Nada verificava isto. Uma versão atribuída a outro tenant existe na
    tabela e é inalcançável para quem é dono:
    `views/cronograma_importacao.py:557,637` filtram por
    `admin_id=get_tenant_admin_id()`, e `_restaurar` busca a obra pelo admin
    da versão — dá 404 na restauração. Pior: se o snapshot guarda o admin de
    cada tarefa em vez do da versão, `_restaurar` regrava tudo com o admin da
    versão e tarefa de um tenant reaparece no cronograma de outro.
    """
    from migrations import _migration_210_backfill_versao_inicial
    from models import (CronogramaTarefaSnapshot, CronogramaVersao, Obra,
                        TarefaCronograma)

    with app.app_context():
        obra_id = ambiente_baias['obra_id']
        obra = db.session.get(Obra, obra_id)

        # Pendura na obra uma tarefa de um admin com id MENOR que o dono.
        # Sem isso o teste não vale nada: a fixture cria tudo sob um admin
        # só, e qualquer regra que escolha "um admin entre as tarefas"
        # acerta por coincidência. Com o admin menor presente, um
        # `MIN(t.admin_id)` passa a devolver o tenant errado — que é o
        # defeito real que esta asserção existe para pegar.
        admin_menor = db.session.execute(text(
            'SELECT id FROM usuario WHERE id < :a ORDER BY id LIMIT 1'),
            {'a': obra.admin_id}).scalar()
        if admin_menor is None:
            pytest.skip('sem usuário de id menor para montar a divergência')
        db.session.add(TarefaCronograma(
            obra_id=obra_id, admin_id=admin_menor,
            nome_tarefa='Tarefa de outro tenant', ordem=97, duracao_dias=1))
        db.session.commit()

        _migration_210_backfill_versao_inicial()

        obra = db.session.get(Obra, obra_id)
        v = CronogramaVersao.query.filter_by(
            obra_id=obra_id, status='ativa').one()
        assert v.admin_id == obra.admin_id, (
            f'versão {v.id} ficou com admin {v.admin_id}, mas a obra é do '
            f'admin {obra.admin_id} — o dono não enxerga nem restaura')

        admins_snap = {s.admin_id for s in
                       CronogramaTarefaSnapshot.query.filter_by(versao_id=v.id)}
        assert admins_snap <= {v.admin_id}, (
            f'snapshots com admin fora da versão: {admins_snap - {v.admin_id}} '
            f'— rollback re-hospedaria essas tarefas no tenant da versão')


@pytest.mark.integration
def test_snapshot_do_backfill_ignora_cronograma_do_cliente(ambiente_baias):
    """A linha de base v1 é do cronograma INTERNO, não do plano do cliente.

    A obra tem um cronograma paralelo do cliente (`is_cliente=True`,
    views/obras.py:3049). A 210 fotografava os dois; num rollback,
    `_restaurar` não acha a tarefa de cliente em `por_id` (que filtra
    `is_cliente=False`) e INSERE uma cópia nova — o plano do cliente
    duplicado dentro do Gantt interno, sem a guarda anti-delete disparar
    (a contagem SOBE). A 212 sempre teve o filtro; a 210 nasceu sem ele.
    """
    from migrations import _migration_210_backfill_versao_inicial
    from models import CronogramaTarefaSnapshot, CronogramaVersao, TarefaCronograma

    with app.app_context():
        obra_id = ambiente_baias['obra_id']
        admin_id = ambiente_baias['admin_id']

        db.session.add(TarefaCronograma(
            obra_id=obra_id, admin_id=admin_id, nome_tarefa='Plano do cliente',
            ordem=99, duracao_dias=5, is_cliente=True))
        db.session.add(TarefaCronograma(
            obra_id=obra_id, admin_id=admin_id, nome_tarefa='Tarefa arquivada',
            ordem=98, duracao_dias=5, ativa=False))
        db.session.commit()

        _migration_210_backfill_versao_inicial()

        v = CronogramaVersao.query.filter_by(
            obra_id=obra_id, status='ativa').one()
        nomes = {s.nome_tarefa for s in
                 CronogramaTarefaSnapshot.query.filter_by(versao_id=v.id)}
        assert 'Plano do cliente' not in nomes, (
            'o cronograma do cliente entrou na linha de base interna')
        assert 'Tarefa arquivada' not in nomes, (
            'tarefa arquivada entrou na linha de base e voltaria ativa no '
            'rollback')


@pytest.mark.integration
def test_backfill_tipo_apontamento(ambiente_baias):
    """quantidade_total>0 → 'quantitativo'; senão 'percentual' com
    percentual_acumulado=percentual_realizado e incremento=quantidade_executada_dia
    (que no modo percentual guarda o incremento % — importacao_fisico_financeiro:521-532).
    Os campos ANTIGOS ficam byte a byte intactos (spec §13.2)."""
    from migrations import _migration_210_backfill_versao_inicial
    from models import RDOApontamentoCronograma, TarefaCronograma
    with app.app_context():
        admin_id = ambiente_baias['admin_id']
        sql_antigos = text(
            "SELECT id, quantidade_executada_dia, quantidade_acumulada, "
            "percentual_realizado FROM rdo_apontamento_cronograma "
            "WHERE admin_id = :a ORDER BY id LIMIT 3")
        with db.engine.connect() as conn:
            antes = [tuple(r) for r in
                     conn.execute(sql_antigos, {'a': admin_id}).fetchall()]
        assert len(antes) == 3, 'fixture deveria ter >= 3 apontamentos'

        _migration_210_backfill_versao_inicial()
        db.session.expire_all()

        with db.engine.connect() as conn:
            depois = [tuple(r) for r in
                      conn.execute(sql_antigos, {'a': admin_id}).fetchall()]
        assert antes == depois, 'backfill NÃO pode alterar os campos antigos'

        aps = (RDOApontamentoCronograma.query
               .join(TarefaCronograma,
                     TarefaCronograma.id == RDOApontamentoCronograma.tarefa_cronograma_id)
               .filter(RDOApontamentoCronograma.admin_id == admin_id)
               .all())
        assert aps, 'fixture sem apontamentos'
        vistos = set()
        for ap in aps:
            t = ap.tarefa
            if t.quantidade_total and t.quantidade_total > 0:
                assert ap.tipo_apontamento == 'quantitativo'
                assert ap.quantidade_total_snapshot == t.quantidade_total
                vistos.add('quantitativo')
            else:
                assert ap.tipo_apontamento == 'percentual'
                assert ap.percentual_acumulado == ap.percentual_realizado
                assert ap.percentual_incremento_dia == ap.quantidade_executada_dia
                vistos.add('percentual')
        # A fixture das baias exercita os DOIS modos (tarefa 14 = quantitativa)
        assert vistos == {'quantitativo', 'percentual'}


@pytest.mark.integration
def test_backfill_reexecucao_noop(ambiente_baias):
    """Rodar de novo não duplica versão nem snapshots."""
    from migrations import _migration_210_backfill_versao_inicial
    from models import CronogramaVersao
    with app.app_context():
        _migration_210_backfill_versao_inicial()
        _migration_210_backfill_versao_inicial()
        n = CronogramaVersao.query.filter_by(obra_id=ambiente_baias['obra_id']).count()
        assert n == 1


@pytest.mark.integration
def test_backfill_multitenant_admin_sem_tarefas(ambiente_baias):
    """Segundo admin sem tarefas: o backfill não cria versão nem snapshot
    para ele; a versão da obra das baias pertence ao admin da fixture."""
    from migrations import _migration_210_backfill_versao_inicial
    from models import CronogramaVersao, CronogramaTarefaSnapshot
    with app.app_context():
        admin2 = _novo_admin('bkf210_vazio')
        _migration_210_backfill_versao_inicial()
        assert CronogramaVersao.query.filter_by(admin_id=admin2).count() == 0
        assert CronogramaTarefaSnapshot.query.filter_by(admin_id=admin2).count() == 0
        v = CronogramaVersao.query.filter_by(obra_id=ambiente_baias['obra_id']).one()
        assert v.admin_id == ambiente_baias['admin_id']


@pytest.mark.integration
def test_migration_265_carimba_linhas_sem_rotulo(ambiente_baias):
    """A 265 fecha o que a 210 não alcançava: linha criada DEPOIS dela, por
    caminho de escrita que não carimbava (import físico-financeiro e
    views/rdo). Sem rótulo, a leitura do avanço tinha de adivinhar pela
    `quantidade_total` vigente da tarefa — e mudava de resposta no dia em que
    alguém cadastrasse o quantitativo.

    A fixture zera os rótulos justamente para reproduzir esse estado.
    """
    from migrations import migration_265_backfill_tipo_apontamento_restante
    from models import RDOApontamentoCronograma, TarefaCronograma
    with app.app_context():
        admin_id = ambiente_baias['admin_id']
        sem_rotulo = RDOApontamentoCronograma.query.filter_by(
            admin_id=admin_id, tipo_apontamento=None).count()
        assert sem_rotulo, 'fixture deveria ter linhas sem rótulo'

        # os campos antigos são fato bruto e não podem ser tocados
        sql_antigos = text(
            "SELECT id, quantidade_executada_dia, quantidade_acumulada, "
            "percentual_realizado FROM rdo_apontamento_cronograma "
            "WHERE admin_id = :a ORDER BY id")
        with db.engine.connect() as conn:
            antes = [tuple(r) for r in
                     conn.execute(sql_antigos, {'a': admin_id}).fetchall()]

        migration_265_backfill_tipo_apontamento_restante()
        db.session.expire_all()

        with db.engine.connect() as conn:
            depois = [tuple(r) for r in
                      conn.execute(sql_antigos, {'a': admin_id}).fetchall()]
        assert antes == depois, 'backfill NÃO pode alterar os campos antigos'

        assert RDOApontamentoCronograma.query.filter_by(
            admin_id=admin_id, tipo_apontamento=None).count() == 0

        vistos = set()
        for ap in RDOApontamentoCronograma.query.filter_by(
                admin_id=admin_id).all():
            t = db.session.get(TarefaCronograma, ap.tarefa_cronograma_id)
            esperado = ('quantitativo'
                        if (t.quantidade_total or 0) > 0 else 'percentual')
            assert ap.tipo_apontamento == esperado
            vistos.add(esperado)
        assert vistos == {'quantitativo', 'percentual'}, \
            f'fixture deveria exercitar os dois modos, veio {vistos}'


@pytest.mark.integration
def test_migration_265_e_idempotente(ambiente_baias):
    """Roda duas vezes sem mudar nada na segunda — e não reescreve o rótulo
    que já existe (a 210 e a escrita nova são donas dele)."""
    from migrations import migration_265_backfill_tipo_apontamento_restante
    from models import RDOApontamentoCronograma
    with app.app_context():
        admin_id = ambiente_baias['admin_id']
        migration_265_backfill_tipo_apontamento_restante()
        db.session.expire_all()
        primeira = {ap.id: ap.tipo_apontamento for ap in
                    RDOApontamentoCronograma.query.filter_by(
                        admin_id=admin_id).all()}
        migration_265_backfill_tipo_apontamento_restante()
        db.session.expire_all()
        segunda = {ap.id: ap.tipo_apontamento for ap in
                   RDOApontamentoCronograma.query.filter_by(
                       admin_id=admin_id).all()}
        assert primeira == segunda


# ─────────────────────────────────────────────────────────────────────────────
# Migration 266 — reparo das linhas de base v1 criadas torto pela 210/212.
# O banco de dev não ofereceu um caso natural para validar (as obras afetadas
# foram apagadas por corridas de teste, deixando snapshot órfão que não casa
# mais com `tarefa_cronograma`), então o estado defeituoso é CONSTRUÍDO aqui.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def versao_v1_torta(ambiente_baias):
    """Linha de base v1 com os dois defeitos: snapshot de tarefa do cliente
    e versão atribuída a um tenant que não é o dono da obra."""
    from models import (CronogramaTarefaSnapshot, CronogramaVersao, Obra,
                        TarefaCronograma)
    with app.app_context():
        obra_id = ambiente_baias['obra_id']
        admin_id = ambiente_baias['admin_id']
        obra = db.session.get(Obra, obra_id)

        interna = TarefaCronograma(
            obra_id=obra_id, admin_id=admin_id, nome_tarefa='Interna legítima',
            ordem=1, duracao_dias=3)
        cliente = TarefaCronograma(
            obra_id=obra_id, admin_id=admin_id, nome_tarefa='Plano do cliente',
            ordem=2, duracao_dias=3, is_cliente=True)
        db.session.add_all([interna, cliente])
        db.session.flush()

        alheio = _novo_admin('m266alheio')
        v = CronogramaVersao(obra_id=obra_id, admin_id=alheio, numero=1,
                             status='ativa', observacao='backfill inicial')
        db.session.add(v)
        db.session.flush()
        for t in (interna, cliente):
            db.session.add(CronogramaTarefaSnapshot(
                versao_id=v.id, admin_id=t.admin_id, tarefa_id=t.id,
                nome_tarefa=t.nome_tarefa, ordem=t.ordem))
        db.session.commit()
        yield {'obra_id': obra_id, 'dono': obra.admin_id, 'alheio': alheio,
               'versao_id': v.id, 'interna_id': interna.id,
               'cliente_id': cliente.id}


@pytest.mark.integration
def test_266_remove_snapshot_do_cliente_e_preserva_o_interno(versao_v1_torta):
    """O snapshot do plano do cliente sai; o da tarefa interna fica.

    Sem isto, um rollback para a v1 não acha a tarefa de cliente em `por_id`
    (que filtra `is_cliente=False`) e INSERE uma cópia nova como interna —
    o plano do cliente duplicado dentro do Gantt.
    """
    from migrations import migration_266_reparar_linhas_de_base_do_backfill
    from models import CronogramaTarefaSnapshot

    with app.app_context():
        v_id = versao_v1_torta['versao_id']
        migration_266_reparar_linhas_de_base_do_backfill()

        alvos = {s.tarefa_id for s in
                 CronogramaTarefaSnapshot.query.filter_by(versao_id=v_id)}
        assert versao_v1_torta['cliente_id'] not in alvos, (
            'snapshot do cronograma do cliente sobreviveu ao reparo')
        assert versao_v1_torta['interna_id'] in alvos, (
            'o reparo levou junto a tarefa interna — linha de base destruída')


@pytest.mark.integration
def test_266_devolve_a_versao_ao_dono_da_obra(versao_v1_torta):
    """Versão presa em tenant alheio volta para o dono, e os snapshots junto.

    Enquanto está errada, ela é invisível na listagem de histórico e dá 404
    na restauração (`views/cronograma_importacao.py:557,637` filtram por
    admin_id).
    """
    from migrations import migration_266_reparar_linhas_de_base_do_backfill
    from models import CronogramaTarefaSnapshot, CronogramaVersao

    with app.app_context():
        v_id = versao_v1_torta['versao_id']
        assert db.session.get(CronogramaVersao, v_id).admin_id == \
            versao_v1_torta['alheio'], 'a fixture não montou o defeito'

        migration_266_reparar_linhas_de_base_do_backfill()

        db.session.expire_all()
        v = db.session.get(CronogramaVersao, v_id)
        assert v.admin_id == versao_v1_torta['dono'], (
            f'versão seguiu no tenant {v.admin_id}, dono é '
            f'{versao_v1_torta["dono"]}')
        admins = {s.admin_id for s in
                  CronogramaTarefaSnapshot.query.filter_by(versao_id=v_id)}
        assert admins <= {v.admin_id}, (
            f'snapshot com admin fora da versão: {admins - {v.admin_id}}')


@pytest.mark.integration
def test_266_e_idempotente(versao_v1_torta):
    """Rodar duas vezes não muda mais nada — nem apaga snapshot legítimo."""
    from migrations import migration_266_reparar_linhas_de_base_do_backfill
    from models import CronogramaTarefaSnapshot

    with app.app_context():
        v_id = versao_v1_torta['versao_id']
        migration_266_reparar_linhas_de_base_do_backfill()
        depois_1 = {s.tarefa_id for s in
                    CronogramaTarefaSnapshot.query.filter_by(versao_id=v_id)}
        migration_266_reparar_linhas_de_base_do_backfill()
        depois_2 = {s.tarefa_id for s in
                    CronogramaTarefaSnapshot.query.filter_by(versao_id=v_id)}
        assert depois_1 == depois_2 == {versao_v1_torta['interna_id']}
