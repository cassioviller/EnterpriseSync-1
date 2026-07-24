"""Fase 5 — assinatura do RDO.

Antes desta fase não existia assinatura nenhuma: o PDF imprimia uma
LINHA EM BRANCO para caneta (services/rdo_pdf_service.py:798-865) e o
único vínculo com uma pessoa era `RDO.criado_por_id` → `usuario.id`,
sem papel, sem carimbo de tempo, sem integridade.

Decisão jurídica adotada (ver seção "A decisão jurídica" do plano):
registro de autoria + integridade (hash SHA-256 + timestamp + IP),
NÃO ICP-Brasil. Base: MP 2.200-2/2001, art. 10, §2º. `provedor` nasce
'interno' para que Clicksign/D4Sign entre depois sem migração.
"""
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os 54 blueprints antes de qualquer request
from app import app, db
from models import (Cliente, Funcionario, Obra, PapelObra, RDO, TipoUsuario,
                    Usuario, UsuarioObra)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-fase5-assinatura'
    yield


def _sfx():
    return uuid.uuid4().hex[:8]


def _admin(nome='Admin F5A'):
    suf = _sfx()
    u = Usuario(
        username=f'f5s_{suf}', email=f'f5s_{suf}@test.local',
        nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
    )
    db.session.add(u)
    db.session.commit()
    return u


def _funcionario(admin_id, nome='Encarregado'):
    suf = _sfx()
    f = Funcionario(
        codigo=f'F5{suf[:6].upper()}', nome=f'{nome} {suf}',
        cpf=suf.ljust(14, '0')[:14], email=f'f5f_{suf}@test.local',
        data_admissao=date(2025, 1, 1), admin_id=admin_id, ativo=True,
    )
    db.session.add(f)
    db.session.commit()
    return f


def _operador(admin_id, funcionario, nome='Apontador'):
    """Usuário FUNCIONARIO já vinculado à pessoa de RH (Fase 1)."""
    suf = _sfx()
    u = Usuario(
        username=f'f5o_{suf}', email=f'f5o_{suf}@test.local', nome=f'{nome} {suf}',
        password_hash=generate_password_hash('Senha@2026'),
        tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
        admin_id=admin_id, funcionario_id=funcionario.id,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _obra(admin_id, nome='Obra F5A'):
    suf = _sfx()
    cli = Cliente(nome=f'CLI-F5A-{suf}', admin_id=admin_id)
    db.session.add(cli)
    db.session.flush()
    o = Obra(
        nome=f'{nome} {suf}', codigo=f'OA5{suf[:6].upper()}',
        data_inicio=date(2026, 1, 1), admin_id=admin_id,
        cliente_id=cli.id, valor_contrato=250000,
    )
    db.session.add(o)
    db.session.commit()
    return o


def _vincular(usuario, obra, papel):
    v = UsuarioObra(usuario_id=usuario.id, obra_id=obra.id, papel=papel,
                    admin_id=obra.admin_id, ativo=True)
    db.session.add(v)
    db.session.commit()
    return v


def _rdo(obra, admin_id, criado_por_id=None):
    suf = _sfx()
    r = RDO(
        numero_rdo=f'RDO-F5A-{suf}', data_relatorio=date(2026, 6, 22),
        obra_id=obra.id, admin_id=admin_id, criado_por_id=criado_por_id,
        comentario_geral='Montagem dos perfis de aço do painel P3.',
        clima_geral='Ensolarado', temperatura_media='28°C',
    )
    db.session.add(r)
    db.session.commit()
    return r


def _cliente_de(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

def test_modelo_de_assinatura_existe_e_persiste():
    from models import RDOAssinatura

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        rdo = _rdo(obra, admin.id, criado_por_id=op.id)

        a = RDOAssinatura(
            rdo_id=rdo.id, admin_id=admin.id, usuario_id=op.id,
            funcionario_id=func.id, papel='executor',
            nome_signatario=op.nome, cargo_signatario='Encarregado',
            hash_conteudo='a' * 64, algoritmo='sha256', provedor='interno',
            ip='203.0.113.9', user_agent='pytest/1.0',
        )
        db.session.add(a)
        db.session.commit()
        aid = a.id

    with app.app_context():
        r = db.session.get(RDOAssinatura, aid)
        assert r.papel == 'executor'
        assert r.algoritmo == 'sha256'
        assert r.provedor == 'interno'
        assert r.assinado_em is not None
        assert r.hash_conteudo == 'a' * 64


def test_uma_assinatura_por_papel_por_rdo():
    """O mesmo papel não assina duas vezes o mesmo RDO."""
    from sqlalchemy.exc import IntegrityError

    from models import RDOAssinatura

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        rdo = _rdo(obra, admin.id)

        for i in range(2):
            db.session.add(RDOAssinatura(
                rdo_id=rdo.id, admin_id=admin.id, usuario_id=op.id,
                funcionario_id=func.id, papel='executor',
                nome_signatario=op.nome, hash_conteudo='b' * 64,
                algoritmo='sha256', provedor='interno'))
            if i == 0:
                db.session.commit()
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_assinatura_e_apagada_junto_com_o_rdo():
    from models import RDOAssinatura
    from services.rdo_ciclo_vida import escrita_de_ciclo_de_vida

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        rdo = _rdo(obra, admin.id)
        db.session.add(RDOAssinatura(
            rdo_id=rdo.id, admin_id=admin.id, usuario_id=op.id,
            funcionario_id=func.id, papel='executor',
            nome_signatario=op.nome, hash_conteudo='c' * 64,
            algoritmo='sha256', provedor='interno'))
        db.session.commit()
        rid = rdo.id
        # O RDO ainda está em rascunho, então a guarda não bloqueia o delete.
        db.session.delete(rdo)
        db.session.commit()
        assert RDOAssinatura.query.filter_by(rdo_id=rid).count() == 0


# ---------------------------------------------------------------------------
# Hash canônico
# ---------------------------------------------------------------------------

def test_hash_e_determinista():
    from services.rdo_hash import calcular_hash

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        assert calcular_hash(rdo) == calcular_hash(rdo)


def test_hash_tem_64_hex():
    from services.rdo_hash import calcular_hash

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        h = calcular_hash(rdo)
        assert len(h) == 64
        assert all(c in '0123456789abcdef' for c in h)


def test_hash_muda_quando_o_comentario_muda():
    from services.rdo_hash import calcular_hash

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        antes = calcular_hash(rdo)
        rdo.comentario_geral = 'Choveu; frente parada após as 14h.'
        db.session.commit()
        assert calcular_hash(rdo) != antes


def test_hash_muda_quando_a_mao_de_obra_muda():
    from models import RDOMaoObra
    from services.rdo_hash import calcular_hash

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        rdo = _rdo(obra, admin.id)
        antes = calcular_hash(rdo)
        db.session.add(RDOMaoObra(
            rdo_id=rdo.id, admin_id=admin.id, funcionario_id=func.id,
            funcao_exercida='Montador', horas_trabalhadas=8.0))
        db.session.commit()
        db.session.refresh(rdo)
        assert calcular_hash(rdo) != antes


def test_hash_nao_depende_da_ordem_de_insercao_da_mao_de_obra():
    """Duas linhas iguais em ordem trocada têm que dar o mesmo hash."""
    from models import RDOMaoObra
    from services.rdo_hash import calcular_hash

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        f1, f2 = _funcionario(admin.id, 'A'), _funcionario(admin.id, 'B')
        r1, r2 = _rdo(obra, admin.id), _rdo(obra, admin.id)
        for func, horas in ((f1, 8.0), (f2, 6.0)):
            db.session.add(RDOMaoObra(rdo_id=r1.id, admin_id=admin.id,
                                      funcionario_id=func.id,
                                      funcao_exercida='Montador',
                                      horas_trabalhadas=horas))
        for func, horas in ((f2, 6.0), (f1, 8.0)):
            db.session.add(RDOMaoObra(rdo_id=r2.id, admin_id=admin.id,
                                      funcionario_id=func.id,
                                      funcao_exercida='Montador',
                                      horas_trabalhadas=horas))
        db.session.commit()
        db.session.refresh(r1)
        db.session.refresh(r2)
        from services.rdo_hash import payload_canonico
        assert payload_canonico(r1)['mao_obra'] == \
            payload_canonico(r2)['mao_obra']


def test_hash_nao_inclui_os_bytes_da_foto():
    """A assinatura não pode amarrar-se ao formato de armazenamento.

    A Task 15 migra as fotos de base64 no banco para arquivo em disco.
    Se o hash cobrisse os bytes, toda assinatura anterior à migração
    ficaria inválida por uma mudança que não alterou o conteúdo
    declarado.
    """
    from models import RDOFoto
    from services.rdo_hash import calcular_hash, payload_canonico

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        foto = RDOFoto(
            admin_id=admin.id, rdo_id=rdo.id,
            nome_arquivo='p3.webp', caminho_arquivo='uploads/rdo/x/p3.webp',
            nome_original='p3.jpg', descricao='Painel P3 montado',
            ordem=0, imagem_otimizada_base64='data:image/webp;base64,AAAA')
        db.session.add(foto)
        db.session.commit()
        db.session.refresh(rdo)

        antes = calcular_hash(rdo)
        assert payload_canonico(rdo)['fotos'] == \
            [[foto.id, 'p3.jpg', 'Painel P3 montado']]

        foto.imagem_otimizada_base64 = None
        foto.arquivo_otimizado = 'uploads/rdo/x/p3.webp'
        db.session.commit()
        db.session.refresh(rdo)
        assert calcular_hash(rdo) == antes, (
            'mover a foto de base64 para disco invalidou a assinatura — o '
            'hash está cobrindo bytes de armazenamento')


def test_verificar_integridade_detecta_adulteracao():
    from models import RDOAssinatura
    from services.rdo_hash import calcular_hash, verificar_integridade

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        rdo = _rdo(obra, admin.id)
        a = RDOAssinatura(
            rdo_id=rdo.id, admin_id=admin.id, usuario_id=op.id,
            funcionario_id=func.id, papel='executor',
            nome_signatario=op.nome, hash_conteudo=calcular_hash(rdo),
            algoritmo='sha256', provedor='interno')
        db.session.add(a)
        db.session.commit()

        assert verificar_integridade(a) is True

        # Adulteração por fora do ORM: UPDATE direto no banco, que é
        # exatamente o cenário contra o qual o hash existe.
        from sqlalchemy import text
        db.session.execute(
            text("UPDATE rdo SET comentario_geral = :c WHERE id = :i"),
            {'c': 'texto trocado no banco', 'i': rdo.id})
        db.session.commit()
        db.session.expire_all()

        assert verificar_integridade(a) is False


# ---------------------------------------------------------------------------
# Rota de assinatura
# ---------------------------------------------------------------------------

def _liga_escopo(admin_id):
    """Revisão de premissas 23/07, item 20: sem `escopo_obra_ativo=TRUE`
    todo autenticado do tenant é GESTOR e a distinção de papel não vale."""
    from scripts.flag_escopo_obra import definir_flag
    definir_flag(admin_id, True)


def _preencher(rdo, usuario):
    from services.rdo_ciclo_vida import PREENCHIDO, transicionar
    transicionar(rdo, PREENCHIDO, usuario=usuario)
    db.session.commit()


def test_apontador_assina_e_o_rdo_fica_assinado():
    from models import RDOAssinatura
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id, criado_por_id=op.id)
        _preencher(rdo, op)
        rid, opid, fid = rdo.id, op.id, func.id

    cliente = _cliente_de(opid)
    resposta = cliente.post(f'/rdo/{rid}/assinar',
                            data={'observacao': 'conferido em campo'},
                            follow_redirects=False)
    assert resposta.status_code in (200, 302)

    with app.app_context():
        rdo = db.session.get(RDO, rid)
        assert rdo.estado == ASSINADO
        assinaturas = RDOAssinatura.query.filter_by(rdo_id=rid).all()
        assert len(assinaturas) == 1
        a = assinaturas[0]
        assert a.papel == RDOAssinatura.PAPEL_EXECUTOR
        assert a.funcionario_id == fid, (
            'a assinatura não ficou ancorada na identidade real da Fase 1')
        assert a.usuario_id == opid
        assert len(a.hash_conteudo) == 64
        assert a.provedor == 'interno'
        assert a.assinado_em is not None


def test_assinatura_grava_ip_e_user_agent():
    from models import RDOAssinatura

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, op)
        rid, opid = rdo.id, op.id

    cliente = _cliente_de(opid)
    cliente.post(f'/rdo/{rid}/assinar',
                 headers={'X-Forwarded-For': '203.0.113.42',
                          'User-Agent': 'SIGE-Teste/9.0'})

    with app.app_context():
        a = RDOAssinatura.query.filter_by(rdo_id=rid).first()
        assert a is not None
        assert a.ip == '203.0.113.42', (
            f'IP gravado foi {a.ip!r} — ProxyFix(x_for=1) está em app.py:94')
        assert a.user_agent == 'SIGE-Teste/9.0'


def test_hash_gravado_confere_com_o_conteudo():
    from models import RDOAssinatura
    from services.rdo_hash import verificar_integridade

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, op)
        rid, opid = rdo.id, op.id

    _cliente_de(opid).post(f'/rdo/{rid}/assinar')

    with app.app_context():
        a = RDOAssinatura.query.filter_by(rdo_id=rid).first()
        assert verificar_integridade(a) is True


def test_leitor_nao_assina():
    from models import RDOAssinatura
    from services.rdo_ciclo_vida import PREENCHIDO

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.LEITOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, op)
        rid, opid = rdo.id, op.id

    resposta = _cliente_de(opid).post(f'/rdo/{rid}/assinar',
                                      follow_redirects=False)
    assert resposta.status_code in (302, 403, 404)

    with app.app_context():
        assert RDOAssinatura.query.filter_by(rdo_id=rid).count() == 0
        assert db.session.get(RDO, rid).estado == PREENCHIDO


def test_anonimo_nao_assina():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, admin)
        rid = rdo.id

    resposta = app.test_client().post(f'/rdo/{rid}/assinar',
                                      follow_redirects=False)
    assert resposta.status_code in (302, 401), (
        f'/rdo/{rid}/assinar devolveu {resposta.status_code} para anônimo')


def test_nao_assina_rdo_em_rascunho():
    from models import RDOAssinatura
    from services.rdo_ciclo_vida import RASCUNHO

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)  # continua rascunho
        rid, opid = rdo.id, op.id

    _cliente_de(opid).post(f'/rdo/{rid}/assinar')

    with app.app_context():
        assert db.session.get(RDO, rid).estado == RASCUNHO
        assert RDOAssinatura.query.filter_by(rdo_id=rid).count() == 0


def test_usuario_sem_vinculo_de_funcionario_nao_assina():
    """Sem identidade real (Fase 1), não há autoria a registrar."""
    from models import RDOAssinatura

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        suf = _sfx()
        sem_vinculo = Usuario(
            username=f'f5n_{suf}', email=f'f5n_{suf}@test.local',
            nome='Sem vinculo', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(sem_vinculo)
        db.session.commit()
        _vincular(sem_vinculo, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, admin)
        rid, uid = rdo.id, sem_vinculo.id

    _cliente_de(uid).post(f'/rdo/{rid}/assinar')

    with app.app_context():
        assert RDOAssinatura.query.filter_by(rdo_id=rid).count() == 0, (
            'assinou sem identidade — voltamos a adivinhar quem é a pessoa')


def test_rdo_assinado_nao_aceita_mais_edicao_pela_rota():
    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, op)
        rid, oid, opid, aid = rdo.id, obra.id, op.id, admin.id

    _cliente_de(opid).post(f'/rdo/{rid}/assinar')

    _cliente_de(aid).post('/salvar-rdo-flexivel', data={
        'rdo_id': str(rid), 'obra_id': str(oid),
        'data_relatorio': '2026-06-22',
        'comentario_geral': 'reescrita pós-assinatura',
    }, follow_redirects=True)

    with app.app_context():
        assert db.session.get(RDO, rid).comentario_geral == \
            'Montagem dos perfis de aço do painel P3.'
