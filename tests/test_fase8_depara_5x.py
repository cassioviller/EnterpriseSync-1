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
    Se este teste passar com um de-para chaveado só por código, o de-para
    está errado e o teste é que não presta.
    """
    from services.plano_contas_depara import DEPARA_5X
    assert DEPARA_5X[('contabilidade_utils', '5.1.01')] == '6.1.02.003'
    assert DEPARA_5X[('financeiro_seeds', '5.1.01.001')] == '6.1.01.001'


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

# Onde literal `5.x` AINDA pode aparecer, e por quê. Qualquer outro arquivo
# que ganhe um literal 5.x reprova este censo — é o caminho de escrita novo
# voltando calado, o defeito que a Fase 8 existe para remover.
_ARQUIVOS_QUE_PODEM_TER_5X = {
    # Os DOIS seeders aposentados (Task 3). São a definição do legado.
    'financeiro_seeds.py',
    'contabilidade_utils.py',
    # O de-para: a tabela de origem→destino é feita de códigos 5.x.
    'services/plano_contas_depara.py',
    # Este censo, e os cenários que ele monta.
    'tests/test_fase8_depara_5x.py',
    # Narrativa: o PDF que EXPLICA a colisão 5.1.01. Não lê nem escreve conta.
    'scripts/gerar_pdf_caminho_dinheiro.py',
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
        if rel.replace(os.sep, '/') in _ARQUIVOS_QUE_PODEM_TER_5X:
            continue
        for n, literal in _literais_5x(caminho):
            infratores.append(f'{rel}:{n}: {literal!r}')
    assert not infratores, (
        'literal de conta 5.x fora dos dois seeders aposentados — a conta foi '
        'migrada pela migration 324 e este código aponta para o vazio:\n  '
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
    fonte = open(event_manager.__file__, encoding='utf-8').read()
    assert f"codigo='{destino}'" in fonte, (
        f'event_manager tem de gravar a folha em {destino} — o mesmo destino '
        f'que o DEPARA_5X dá para {origem}'
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
