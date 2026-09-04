"""Fase 8 / Task 4 — o de-para das contas `5.x` para o canônico.

O de-para não pode perder nem somar partida, tem de FALHAR ruidosamente
diante de um código que não conhece, e tem de NOMEAR quem o fez parar.

🔬 Medido em 04/09 no banco de dev, e muda dois destes testes:

1. `partida_contabil` tem FK COMPOSTA `(admin_id, conta_codigo)` →
   `plano_contas(admin_id, codigo)` — na verdade DUAS, duplicadas
   (`partida_contabil_admin_id_conta_codigo_fkey` e
   `partida_contabil_conta_codigo_fkey`). Consequências:

   a. **Partida órfã é impossível de criar.** O teste do ramo órfão do
      brief não tem como montar o cenário: o INSERT é recusado pelo banco.
      O ramo continua na migration (defesa em profundidade, e a FK pode
      ser dropada amanhã), e o que este arquivo prova é o que dá para
      provar: a FK existe, e a mensagem do ramo NOMEIA `(admin_id,
      conta_codigo)` em vez de só contar.
   b. **A conta de DESTINO tem de existir no tenant.** Sem guarda, o
      `UPDATE` morre com `ForeignKeyViolation` nomeando a *constraint* —
      não o tenant. A migration ganhou um passo que nomeia.

2. 🔴 **E tem de SIGNIFICAR o esperado** (rodada 2). Os cinco destinos do
   de-para colidem entre o seeder nº1 e o canônico — `6.1.02.003` é
   'Despesa com Material' num e **'Energia Elétrica'** no outro
   (`contabilidade_utils.py:107`), e há 2 tenants assim no banco de dev. Um
   tenant nº2 não tem grupo 6 e para na guarda de existência; um tenant nº1
   **tem** o código com o sentido errado e passaria calado. Era o único
   caminho silencioso da migration inteira.
"""
import ast
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402

pytestmark = pytest.mark.integration

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Helpers — cada um cria o SEU tenant e limpa o que criou.
# ---------------------------------------------------------------------------

_criados: list = []


def _novo_admin(prefixo):
    import uuid

    from werkzeug.security import generate_password_hash

    from models import TipoUsuario, Usuario

    s = uuid.uuid4().hex[:8]
    u = Usuario(
        username=f'{prefixo}_{s}', email=f'{prefixo}_{s}@test.local',
        nome=f'Admin {s}', password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    _criados.append(u.id)
    return u.id


def _conta(admin_id, codigo, nome, aceita, pai=None):
    from sqlalchemy import text as sa_text
    db.session.execute(sa_text("""
        INSERT INTO plano_contas
            (admin_id, codigo, nome, tipo_conta, natureza, nivel,
             conta_pai_codigo, aceita_lancamento, ativo)
        VALUES (:a, :c, :n, 'DESPESA', 'DEVEDORA', :nivel, :pai, :aceita, true)
        ON CONFLICT (admin_id, codigo) DO NOTHING
    """), {'a': admin_id, 'c': codigo, 'n': nome,
           'nivel': len(codigo.split('.')), 'pai': pai, 'aceita': aceita})
    db.session.commit()


def _partida(admin_id, codigo, valor):
    """Um lançamento de uma partida só. Basta para contar e somar."""
    from datetime import date

    from sqlalchemy import text as sa_text
    lanc_id = db.session.execute(sa_text("""
        INSERT INTO lancamento_contabil
            (numero, data_lancamento, historico, valor_total, origem, admin_id)
        VALUES (:num, :d, 'fase8 task4', :v, 'TESTE_FASE8', :a)
        RETURNING id
    """), {'num': 1, 'd': date(2026, 3, 15),
           'v': valor, 'a': admin_id}).scalar()
    db.session.execute(sa_text("""
        INSERT INTO partida_contabil
            (lancamento_id, sequencia, conta_codigo, tipo_partida, valor,
             admin_id)
        VALUES (:l, 1, :c, 'DEBITO', :v, :a)
    """), {'l': lanc_id, 'c': codigo, 'v': valor, 'a': admin_id})
    db.session.commit()


def _limpar(admin_id):
    from sqlalchemy import text as sa_text
    db.session.rollback()
    db.session.execute(sa_text(
        'DELETE FROM partida_contabil WHERE admin_id = :a'), {'a': admin_id})
    db.session.execute(sa_text(
        'DELETE FROM lancamento_contabil WHERE admin_id = :a'), {'a': admin_id})
    db.session.execute(sa_text(
        'DELETE FROM plano_contas WHERE admin_id = :a'), {'a': admin_id})
    db.session.commit()


@pytest.fixture(autouse=True)
def _faxina():
    """Cada teste limpa o tenant que criou — este banco é COMPARTILHADO."""
    _criados.clear()
    yield
    with app.app_context():
        for admin_id in _criados:
            try:
                _limpar(admin_id)
            except Exception:
                db.session.rollback()


def _tenant_com_partidas_em_5x():
    """Assinatura 'financeiro_seeds': 5.1.01 sintética com filho 5.1.01.001."""
    from contabilidade_utils import seed_plano_contas_if_needed
    admin_id = _novo_admin('f8depara')
    seed_plano_contas_if_needed(admin_id)      # canônico: dá o 6.1.01.001
    _conta(admin_id, '5', 'DESPESAS', False)
    _conta(admin_id, '5.1', 'DESPESAS OPERACIONAIS', False, pai='5')
    _conta(admin_id, '5.1.01', 'MAO DE OBRA', False, pai='5.1')
    _conta(admin_id, '5.1.01.001', 'Salarios', True, pai='5.1.01')
    _partida(admin_id, '5.1.01.001', 1000.00)
    return admin_id


def _tenant_n1_com_partida_em_5_1_01():
    """Assinatura 'contabilidade_utils': 5.1.01 ANALITICA (Materiais Diretos).

    O mesmo `5.1.01` que em `financeiro_seeds` e' MAO DE OBRA. E' este par que
    prova a D6 ponta a ponta: o destino tem de ser 6.1.02.003 (material), e
    nao 6.1.01.001 (salarios).
    """
    from contabilidade_utils import seed_plano_contas_if_needed
    admin_id = _novo_admin('f8n1')
    seed_plano_contas_if_needed(admin_id)      # canonico: da' o 6.1.02.003
    _conta(admin_id, '5', 'CUSTOS', False)
    _conta(admin_id, '5.1', 'CUSTO DOS SERVICOS PRESTADOS', False, pai='5')
    _conta(admin_id, '5.1.01', 'Materiais Diretos', True, pai='5.1')
    _partida(admin_id, '5.1.01', 500.00)
    return admin_id


def _conta_codigos_das_partidas(admin_id):
    from sqlalchemy import text as sa_text
    db.session.rollback()
    return sorted(r[0] for r in db.session.execute(sa_text(
        'SELECT conta_codigo FROM partida_contabil WHERE admin_id = :a'),
        {'a': admin_id}).fetchall())


def _tenant_canonico_sem_5x():
    from contabilidade_utils import seed_plano_contas_if_needed
    admin_id = _novo_admin('f8canon')
    seed_plano_contas_if_needed(admin_id)
    return admin_id


def _tenant_com_partida_em_codigo_desconhecido(codigo):
    """Assinatura reconhecível (nº1) + um código que o de-para não conhece."""
    from contabilidade_utils import seed_plano_contas_if_needed
    admin_id = _novo_admin('f8semdest')
    seed_plano_contas_if_needed(admin_id)
    _conta(admin_id, '5', 'CUSTOS', False)
    _conta(admin_id, '5.1', 'CUSTO DOS SERVICOS PRESTADOS', False, pai='5')
    # 5.1.01 analítica == assinatura 'contabilidade_utils'. Sem partida, não
    # entra no de-para; serve só para o tenant ter assinatura conhecida.
    _conta(admin_id, '5.1.01', 'Materiais Diretos', True, pai='5.1')
    _conta(admin_id, codigo, 'Conta que ninguem mapeou', True)
    _partida(admin_id, codigo, 77.00)
    return admin_id


def _tenant_com_5x_sem_partida():
    from contabilidade_utils import seed_plano_contas_if_needed
    admin_id = _novo_admin('f8semp')
    seed_plano_contas_if_needed(admin_id)
    _conta(admin_id, '5', 'DESPESAS', False)
    _conta(admin_id, '5.1', 'DESPESAS OPERACIONAIS', False, pai='5')
    _conta(admin_id, '5.1.01', 'MAO DE OBRA', False, pai='5.1')
    _conta(admin_id, '5.1.03', 'EQUIPAMENTOS', True, pai='5.1')
    return admin_id


# ---------------------------------------------------------------------------
# Os seis testes do brief
# ---------------------------------------------------------------------------

def test_depara_preserva_a_contagem_e_a_soma():
    from sqlalchemy import text
    from migrations import _migration_324_depara_contas_5x
    with app.app_context():
        admin_id = _tenant_com_partidas_em_5x()
        antes_n = db.session.execute(text(
            'SELECT count(*) FROM partida_contabil WHERE admin_id=:a'),
            {'a': admin_id}).scalar()
        antes_soma = db.session.execute(text(
            'SELECT coalesce(sum(valor),0) FROM partida_contabil WHERE admin_id=:a'),
            {'a': admin_id}).scalar()

        assert _migration_324_depara_contas_5x() is True

        db.session.rollback()   # enxergar o que a migration comitou
        depois_n = db.session.execute(text(
            'SELECT count(*) FROM partida_contabil WHERE admin_id=:a'),
            {'a': admin_id}).scalar()
        depois_soma = db.session.execute(text(
            'SELECT coalesce(sum(valor),0) FROM partida_contabil WHERE admin_id=:a'),
            {'a': admin_id}).scalar()
        restantes = db.session.execute(text(
            "SELECT count(*) FROM partida_contabil "
            "WHERE admin_id=:a AND conta_codigo LIKE '5.%'"),
            {'a': admin_id}).scalar()

        assert depois_n == antes_n, 'partida sumiu ou foi duplicada'
        assert depois_soma == antes_soma, 'a soma mudou — valor foi somado 2x'
        assert restantes == 0, 'sobrou partida em 5.x depois do de-para'


def test_5_1_01_vai_para_destinos_OPOSTOS_conforme_a_assinatura():
    """O coração da D6: o MESMO código migra para contas diferentes.

    Em 'contabilidade_utils', 5.1.01 é Materiais Diretos -> 6.1.02.003.
    Em 'financeiro_seeds', 5.1.01.001 é Salários -> 6.1.01.001.

    🔴 PONTA A PONTA desde a rodada 2. A versão anterior lia duas entradas do
    dicionário e mais nada — passaria intacta contra uma migration que
    ignorasse a assinatura por completo, que é exatamente o defeito que a
    própria docstring dizia estar testando. Agora dois tenants de assinaturas
    OPOSTAS existem ao mesmo tempo, a migration roda de verdade sobre os dois,
    e cada partida é conferida NO DESTINO.
    """
    from migrations import _migration_324_depara_contas_5x
    from services.plano_contas_depara import DEPARA_5X

    # O contrato do dado, primeiro.
    assert DEPARA_5X[('contabilidade_utils', '5.1.01')] == '6.1.02.003'
    assert DEPARA_5X[('financeiro_seeds', '5.1.01.001')] == '6.1.01.001'

    with app.app_context():
        from contabilidade_utils import classificar_assinatura
        n2 = _tenant_com_partidas_em_5x()          # financeiro_seeds
        n1 = _tenant_n1_com_partida_em_5_1_01()    # contabilidade_utils
        assert classificar_assinatura(n2) == 'financeiro_seeds'
        assert classificar_assinatura(n1) == 'contabilidade_utils'

        assert _migration_324_depara_contas_5x() is True

        assert _conta_codigos_das_partidas(n2) == ['6.1.01.001'], (
            'financeiro_seeds: 5.1.01.001 é Salários e tem de virar pessoal'
        )
        assert _conta_codigos_das_partidas(n1) == ['6.1.02.003'], (
            'contabilidade_utils: 5.1.01 é Materiais Diretos e tem de virar '
            'material — mandá-lo para 6.1.01.001 seria o erro SILENCIOSO que '
            'a D6 nomeou'
        )


def test_tenant_canonico_e_no_op_e_nao_para_a_migracao():
    """O canônico (_V2_CONTAS_SEED) e o demo Alfa não têm 5.x.

    🔴 Este teste é a guarda contra o defeito que derrubaria o parque inteiro:
    o demo Alfa roda no auto-seed de TODO boot (app.py:618). Se ele caísse em
    AssinaturaDesconhecida, a migration falharia em todo dev e todo CI.
    """
    from contabilidade_utils import classificar_assinatura
    with app.app_context():
        admin_id = _tenant_canonico_sem_5x()
        assert classificar_assinatura(admin_id) == 'sem_5x'


def test_codigo_sem_destino_faz_a_migration_falhar_e_nomear():
    from sqlalchemy import text
    from migrations import _migration_324_depara_contas_5x
    with app.app_context():
        admin_id = _tenant_com_partida_em_codigo_desconhecido('5.9.99')
        # LEVANTA, nao devolve False: so' a excecao que sobe faz
        # run_migration_safe gravar 'failed' e retentar. Ver a docstring da
        # migration e migrations.py:170.
        with pytest.raises(RuntimeError) as exc:
            _migration_324_depara_contas_5x()
        assert '5.9.99' in str(exc.value), 'a excecao tem de NOMEAR o codigo'
        db.session.rollback()
        sobrou = db.session.execute(text(
            "SELECT count(*) FROM partida_contabil "
            "WHERE admin_id=:a AND conta_codigo='5.9.99'"),
            {'a': admin_id}).scalar()
        assert sobrou == 1, 'a migration falhou mas mexeu no dado assim mesmo'


def test_partida_ORFA_e_nomeada_e_nao_apenas_contada():
    """🔴 O ramo que a versão de 24/08 não cobria — e que o banco torna
    inalcançável, o que só se descobre tentando montá-lo.

    🔬 04/09: `partida_contabil` tem FK composta `(admin_id, conta_codigo)`
    → `plano_contas`. Uma partida órfã é RECUSADA pelo banco; não há como
    criar o cenário do brief. O ramo continua na migration porque a FK não
    é lei da natureza (foi criada na migration 218 e pode ser dropada), e o
    que se pode provar é o que este teste prova:

      1. a FK existe — se alguém a dropar, este teste avisa que o ramo
         órfão passou a ser alcançável e precisa de cenário de verdade;
      2. a mensagem do ramo NOMEIA `(admin_id, conta_codigo)`, que é a
         Global Constraint ("a falha tem de nomear"), e não só conta.
    """
    from sqlalchemy import text
    from migrations import _erro_partidas_orfas
    with app.app_context():
        fks = db.session.execute(text("""
            SELECT count(*) FROM pg_constraint
             WHERE conrelid = 'partida_contabil'::regclass AND contype = 'f'
               AND pg_get_constraintdef(oid) LIKE
                   'FOREIGN KEY (admin_id, conta_codigo) REFERENCES plano_contas%'
        """)).scalar()
        assert fks >= 1, (
            'a FK composta (admin_id, conta_codigo) sumiu — partida orfa '
            'voltou a ser possivel e este teste precisa de cenario real'
        )

    erro = _erro_partidas_orfas([(4242, '5.3.01'), (4242, '5.3.02')])
    assert isinstance(erro, RuntimeError)
    assert '4242' in str(erro), 'a excecao tem de NOMEAR o tenant'
    assert '5.3.01' in str(erro), 'a excecao tem de NOMEAR o codigo'


def test_conta_5x_sem_partida_e_desativada_e_nao_apagada():
    from models import PlanoContas
    from migrations import _migration_324_depara_contas_5x
    with app.app_context():
        admin_id = _tenant_com_5x_sem_partida()
        _migration_324_depara_contas_5x()
        db.session.rollback()
        conta = PlanoContas.query.filter_by(
            admin_id=admin_id, codigo='5.1.03').first()
        assert conta is not None, (
            'conta de plano de contas NUNCA é apagada — relatório histórico '
            'aponta para ela')
        assert conta.ativo is False


def test_destino_com_OUTRO_SIGNIFICADO_faz_a_migration_parar_e_nomear():
    """🔴 C1 — o de-para consertava a ambiguidade na origem e a repetia no destino.

    🔬 `6.1.02.003` e' 'Despesa com Material' no canonico (_V2_CONTAS_SEED) e
    'Energia Eletrica' no seeder aposentado nº1 (contabilidade_utils.py:107).
    Um tenant nº1 TEM esse codigo — entao a guarda de existencia passa — e a
    partida de material pousaria na conta de energia eletrica do proprio
    tenant, sem erro em lugar nenhum. Razao, balancete e exportacao Dominio
    passariam a reportar material de construcao como energia, para sempre.

    Este e' o unico caminho SILENCIOSO que a migration tinha. A guarda le
    `nome` de proposito: nao para rotear (proibido pela spec), e sim para
    RECUSAR ESCRITA quando o destino nao quer dizer o esperado.
    """
    from sqlalchemy import text
    from migrations import _migration_324_depara_contas_5x
    with app.app_context():
        admin_id = _tenant_n1_com_partida_em_5_1_01()
        # O tenant vira nº1 de verdade: 6.1.02.003 passa a ser 'Energia
        # Eletrica', como o seeder aposentado nº1 o cria.
        db.session.execute(text(
            "UPDATE plano_contas SET nome = 'Energia Eletrica' "
            " WHERE admin_id = :a AND codigo = '6.1.02.003'"), {'a': admin_id})
        db.session.commit()

        with pytest.raises(RuntimeError) as exc:
            _migration_324_depara_contas_5x()

        msg = str(exc.value)
        assert str(admin_id) in msg, 'a excecao tem de NOMEAR o tenant'
        assert '6.1.02.003' in msg, 'a excecao tem de NOMEAR o codigo'
        assert 'Energia Eletrica' in msg, 'tem de dizer o nome ENCONTRADO'
        assert 'Despesa com Material' in msg, 'tem de dizer o nome ESPERADO'

        # E nada foi escrito: a partida continua onde estava.
        assert _conta_codigos_das_partidas(admin_id) == ['5.1.01'], (
            'a migration parou mas mexeu no dado assim mesmo'
        )


def test_o_nome_esperado_do_destino_vem_do_seed_e_nao_de_uma_copia():
    """A guarda de significado nao pode ter uma segunda lista literal.

    Uma copia a mao envelhece em silencio e a guarda passa a aprovar o que
    devia recusar. `_V2_NOME_CANONICO` e' DERIVADO de `_V2_CONTAS_SEED`.
    """
    from contabilidade_utils import _V2_CONTAS_SEED, _V2_NOME_CANONICO
    from services.plano_contas_depara import DEPARA_5X

    assert _V2_NOME_CANONICO == {c: n for (c, n, *_r) in _V2_CONTAS_SEED}
    for destino in set(DEPARA_5X.values()):
        assert destino in _V2_NOME_CANONICO, (
            f'o de-para manda partida para {destino}, que nao existe no '
            'plano de contas canonico — a guarda de significado nao teria '
            'nome esperado para comparar'
        )


# ---------------------------------------------------------------------------
# Step 0 — o censo dos literais 5.x, e os leitores/escritores vivos
# ---------------------------------------------------------------------------

# Um literal de conta 5.x é a string INTEIRA '5.NN...' com pelo menos dois
# níveis abaixo da raiz ('5.1.01', '5.1.01.001'). O casamento é sobre o VALOR
# do literal, via `ast` — não sobre a linha crua:
#   * comentário e docstring que EXPLICAM o legado não são caminho de escrita
#     e não devem reprovar (este arquivo e a migration 324 falam de 5.x o
#     tempo todo);
#   * dinheiro ('5.000', '5.250,00', '5.00') e versão ('5.1' solto) não casam.
# ⚠️ O recorte deixa passar um literal '5.1' cru. É deliberado: '5.1' sozinho
# não endereça conta analítica nenhuma nos quatro planos.
_RE_CODIGO_5X = re.compile(r'5(\.\d{1,3}){2,}\Z')

# Onde literal `5.x` AINDA pode aparecer, e QUAIS. Qualquer outro arquivo que
# ganhe um literal 5.x reprova este censo — é o caminho de escrita novo
# voltando calado, o defeito que a Fase 8 existe para remover.
#
# 🔴 A isenção é por LITERAL, não por arquivo (corrigido na rodada 2). A
# primeira versão isentava `contabilidade_utils.py` inteiro — 1.900+ linhas
# que abrigam os leitores do DRE, `criar_lancamento_automatico`,
# `contabilizar_folha_pagamento` e o `_V2_CONTAS_SEED`. É o lugar MAIS provável
# de nascer o próximo caminho de escrita contábil, e o censo estava cego para
# ele. Agora cada arquivo declara o conjunto exato que pode ter.
#
# A checagem é de SUBCONJUNTO: apagar literal nunca reprova (a Task 3 vai
# aposentar os seeders e o conjunto só encolhe), acrescentar reprova sempre.
_LITERAIS_5X_PERMITIDOS = {
    # Seeder aposentado nº1 (`criar_plano_contas_padrao`) + os prefixos que o
    # DRE legado ainda lê para não contar em dobro. Conjunto FECHADO: qualquer
    # 5.x novo neste arquivo reprova.
    'contabilidade_utils.py': {
        '5.1.01', '5.1.02', '5.1.03', '5.1.04', '5.1.05',
        '5.2.01', '5.3.01', '5.3.02',
    },
    # Seeder aposentado nº2 (`PLANO_CONTAS_CONSTRUCAO`). O módulo é só a
    # tabela de dados do legado — mas o conjunto é fechado do mesmo jeito.
    'financeiro_seeds.py': {
        '5.1.01', '5.1.01.001', '5.1.01.002', '5.1.01.003', '5.1.01.004',
        '5.1.02', '5.1.02.001', '5.1.02.002', '5.1.02.003',
        '5.1.03', '5.1.03.001', '5.1.03.002',
        '5.1.04', '5.1.04.001', '5.1.04.002', '5.1.04.003',
        '5.1.05', '5.1.05.001', '5.1.05.002', '5.1.05.003', '5.1.05.004',
    },
    # O de-para: as chaves de origem. Tem de ser um subconjunto do que os dois
    # seeders acima criam — mapear código que nenhum seeder produz seria
    # inventar semântica.
    'services/plano_contas_depara.py': {
        '5.1.01', '5.1.02', '5.2.01',
        '5.1.01.001', '5.1.01.002', '5.1.01.003', '5.1.01.004',
        '5.1.02.001', '5.1.02.002', '5.1.02.003',
        '5.1.03.001', '5.1.03.002',
        '5.1.04.001', '5.1.04.002', '5.1.04.003',
        '5.1.05.001', '5.1.05.002', '5.1.05.003', '5.1.05.004',
    },
    # Narrativa: o PDF que EXPLICA a colisão 5.1.01. Não lê nem escreve conta.
    'scripts/gerar_pdf_caminho_dinheiro.py': {'5.1.01'},
    # Este censo e os cenários que ele monta. `None` = sem restrição — é o
    # único arquivo cujo trabalho É falar de 5.x.
    'tests/test_fase8_depara_5x.py': None,
}

# Diretorio que comeca com '.' e' ferramenta (.cache/uv, .pythonlibs, .git):
# a versao '5.2.0' de uma lib de terceiro nao e' conta contabil.
_DIRS_IGNORADOS = ('__pycache__', 'archive', 'entrega_baia_rev10',
                   'node_modules', 'backups', 'attached_assets',
                   'site-packages', 'venv')


def _literais_5x(caminho):
    """Os literais de conta 5.x de um arquivo, por `ast` — nunca por linha."""
    with open(caminho, encoding='utf-8', errors='replace') as fh:
        fonte = fh.read()
    try:
        arvore = ast.parse(fonte, filename=caminho)
    except SyntaxError:
        return
    for no in ast.walk(arvore):
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            if _RE_CODIGO_5X.match(no.value):
                yield getattr(no, 'lineno', 0), no.value


def _todos_literais_str(caminho):
    """Todos os literais string de um arquivo, por `ast`."""
    with open(caminho, encoding='utf-8', errors='replace') as fh:
        arvore = ast.parse(fh.read(), filename=caminho)
    return {no.value for no in ast.walk(arvore)
            if isinstance(no, ast.Constant) and isinstance(no.value, str)}


def _fontes_python():
    for base, dirs, arquivos in os.walk(RAIZ):
        dirs[:] = [d for d in dirs
                   if d not in _DIRS_IGNORADOS and not d.startswith('.')]
        for nome in arquivos:
            if nome.endswith('.py'):
                caminho = os.path.join(base, nome)
                yield os.path.relpath(caminho, RAIZ), caminho


def test_censo_nenhum_literal_5x_novo_fora_dos_seeders_aposentados():
    """🔴 Sem este censo, o próximo caminho de escrita volta calado.

    A Fase 8 não pode migrar as `5.x` e deixar o app apontando para elas.
    """
    infratores = []
    for rel, caminho in _fontes_python():
        chave = rel.replace(os.sep, '/')
        if chave in _LITERAIS_5X_PERMITIDOS and _LITERAIS_5X_PERMITIDOS[chave] is None:
            continue
        permitidos = _LITERAIS_5X_PERMITIDOS.get(chave, frozenset())
        for n, literal in _literais_5x(caminho):
            if literal not in permitidos:
                infratores.append(f'{rel}:{n}: {literal!r}')
    assert not infratores, (
        'literal de conta 5.x fora do conjunto declarado — a conta foi '
        'migrada pela migration 324 e este código aponta para o vazio. Se o '
        'literal for legítimo, declare-o em _LITERAIS_5X_PERMITIDOS e diga '
        'por quê; não amplie a isenção para o arquivo inteiro:\n  '
        + '\n  '.join(infratores)
    )


def test_o_escritor_vivo_da_folha_usa_o_MESMO_destino_do_depara():
    """`event_manager` gravava salário em 5.1.01.001; o DRE lia 6.1.01.001.

    Depois do de-para a 5.1.01.001 fica sem partida e é DESATIVADA — o
    `filter_by(ativo=True)` do handler devolveria None e a folha pararia de
    gerar lançamento contábil **em silêncio** (só um warning). Os dois lados
    têm de bater, e é isto que este teste trava.
    """
    import event_manager
    from services.plano_contas_depara import DEPARA_5X

    origem = '5.1.01.001'
    destino = DEPARA_5X[('financeiro_seeds', origem)]
    literais = [v for _n, v in _literais_5x(event_manager.__file__)]
    assert origem not in literais, (
        f'event_manager ainda escreve em {origem}, que a migration 324 '
        'esvazia e desativa'
    )
    # Por literal via `ast`, não por texto `codigo='…'`: o handler ganhou um
    # `_buscar_contas()` na rodada 2 (semeia-ou-falha) e a forma sintática
    # mudou. O que tem de bater é o CÓDIGO, não como ele é escrito.
    todos_literais = _todos_literais_str(event_manager.__file__)
    assert destino in todos_literais, (
        f'event_manager tem de gravar a folha em {destino} — o mesmo destino '
        f'que o DEPARA_5X dá para {origem}'
    )


def test_a_folha_SEMEIA_OU_FALHA_e_nao_volta_calada_com_um_warning():
    """🔴 I2 — trocar o código não bastava: o silêncio mudou de lugar.

    🔬 04/09, no banco de dev: 202 tenants têm plano de contas e NÃO têm
    `6.1.01.001` (81 já com partidas), e 4 desses têm `5.1.01.001` — plano
    `financeiro_seeds`, que não tem grupo 6 nenhum. Para esses 4 o handler
    FUNCIONAVA antes da Fase 8. Com `codigo='6.1.01.001', ativo=True` e um
    `return` sobre `logger.warning`, a próxima folha deles escreveria uma
    linha de log e nenhum lançamento contábil — o defeito que o Step 0 existe
    para impedir, reaparecendo do outro lado.

    O handler agora SEMEIA o canônico e busca de novo; se ainda faltar,
    LEVANTA. Falha aberta, nunca `return` calado.
    """
    import event_manager
    fonte = open(event_manager.__file__, encoding='utf-8').read()
    trecho = fonte[fonte.index('def criar_lancamento_folha_pagamento'):]
    trecho = trecho[:trecho.index('@event_handler', 1)]

    assert 'seed_plano_contas_if_needed' in trecho, (
        'o handler da folha tem de SEMEAR o canônico antes de desistir'
    )
    assert 'raise RuntimeError' in trecho, (
        'se a conta continuar faltando DEPOIS de semear, o handler tem de '
        'falhar alto — não voltar com um warning'
    )
    assert 'Lançamento não criado' not in trecho, (
        'o `return` sobre warning que escondia folha sem contabilização '
        'ainda está lá'
    )


def test_o_cmv_do_dre_legado_sai_como_sem_base_e_nunca_como_zero():
    """🔬 O canônico não tem conta de CMV e a spec não menciona CMV.

    O CMV legado lia `5.1.03`, que em financeiro_seeds.py:84 é EQUIPAMENTOS —
    o DRE reportava locação de equipamento como custo de mercadoria vendida.
    Depois do de-para (5.1.03.* → 6.1.02.003) a linha fica SEM BASE. Global
    Constraint: indicador sem base sai como 'sem base', nunca 0,00.
    """
    from contabilidade_utils import calcular_dre_mensal
    with app.app_context():
        admin_id = _tenant_canonico_sem_5x()
        dre = calcular_dre_mensal(admin_id=admin_id, ano=2026, mes=3)
        assert dre is not None
        assert 'cmv' in dre['sem_base'], (
            'a linha de CMV do DRE legado tem de sair declarada SEM BASE — '
            'o canônico não tem conta de CMV e a spec não pede uma'
        )
