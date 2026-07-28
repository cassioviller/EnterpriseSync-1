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


# ---------------------------------------------------------------------------
# Aprovação e reabertura
# ---------------------------------------------------------------------------

def _assinar_pela_rota(rdo_id, usuario_id):
    _cliente_de(usuario_id).post(f'/rdo/{rdo_id}/assinar')


def test_gestor_aprova_rdo_assinado():
    from models import RDOAssinatura
    from services.rdo_ciclo_vida import APROVADO

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        f_ap, f_ge = _funcionario(admin.id, 'Ap'), _funcionario(admin.id, 'Ge')
        ap, ge = _operador(admin.id, f_ap), _operador(admin.id, f_ge, 'Gestor')
        _vincular(ap, obra, PapelObra.APONTADOR)
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ap)
        rid, apid, geid = rdo.id, ap.id, ge.id

    _assinar_pela_rota(rid, apid)
    resposta = _cliente_de(geid).post(f'/rdo/{rid}/aprovar',
                                      follow_redirects=False)
    assert resposta.status_code in (200, 302)

    with app.app_context():
        assert db.session.get(RDO, rid).estado == APROVADO
        papeis = {a.papel for a in RDOAssinatura.query.filter_by(rdo_id=rid)}
        assert papeis == {RDOAssinatura.PAPEL_EXECUTOR,
                          RDOAssinatura.PAPEL_GESTOR}


def test_apontador_nao_aprova():
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        ap = _operador(admin.id, func)
        _vincular(ap, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ap)
        rid, apid = rdo.id, ap.id

    _assinar_pela_rota(rid, apid)
    _cliente_de(apid).post(f'/rdo/{rid}/aprovar')

    with app.app_context():
        assert db.session.get(RDO, rid).estado == ASSINADO, (
            'APONTADOR aprovou o próprio RDO — aprovação é do GESTOR')


def test_nao_aprova_rdo_apenas_preenchido():
    from services.rdo_ciclo_vida import PREENCHIDO

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        func = _funcionario(admin.id, 'Ge')
        ge = _operador(admin.id, func, 'Gestor')
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ge)
        rid, geid = rdo.id, ge.id

    _cliente_de(geid).post(f'/rdo/{rid}/aprovar')

    with app.app_context():
        assert db.session.get(RDO, rid).estado == PREENCHIDO


def test_gestor_reabre_rdo_preenchido():
    from models import RDOTransicaoEstado
    from services.rdo_ciclo_vida import RASCUNHO

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        func = _funcionario(admin.id, 'Ge')
        ge = _operador(admin.id, func, 'Gestor')
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ge)
        rid, geid = rdo.id, ge.id

    _cliente_de(geid).post(f'/rdo/{rid}/reabrir',
                           data={'motivo': 'horas lançadas erradas'})

    with app.app_context():
        assert db.session.get(RDO, rid).estado == RASCUNHO
        ultima = (RDOTransicaoEstado.query.filter_by(rdo_id=rid)
                  .order_by(RDOTransicaoEstado.id.desc()).first())
        assert ultima.estado_novo == RASCUNHO
        assert ultima.motivo == 'horas lançadas erradas'


def test_apontador_nao_reabre():
    from services.rdo_ciclo_vida import PREENCHIDO

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        ap = _operador(admin.id, func)
        _vincular(ap, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ap)
        rid, apid = rdo.id, ap.id

    _cliente_de(apid).post(f'/rdo/{rid}/reabrir', data={'motivo': 'quero'})

    with app.app_context():
        assert db.session.get(RDO, rid).estado == PREENCHIDO


def test_nao_reabre_rdo_assinado():
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        f_ap, f_ge = _funcionario(admin.id, 'Ap'), _funcionario(admin.id, 'Ge')
        ap, ge = _operador(admin.id, f_ap), _operador(admin.id, f_ge, 'Gestor')
        _vincular(ap, obra, PapelObra.APONTADOR)
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ap)
        rid, apid, geid = rdo.id, ap.id, ge.id

    _assinar_pela_rota(rid, apid)
    _cliente_de(geid).post(f'/rdo/{rid}/reabrir', data={'motivo': 'errei'})

    with app.app_context():
        assert db.session.get(RDO, rid).estado == ASSINADO, (
            'RDO assinado foi reaberto — imutabilidade furada')


def test_finalizar_rdo_leva_de_rascunho_para_preenchido():
    """`finalizar_rdo` (views/rdo.py:1521) é a rota de SUBMISSÃO.

    Ela já gravava `status='Finalizado'` e emitia `rdo_finalizado` +
    `obra.rdo_publicado`. O que faltava era mover o `estado` — sem isso o
    RDO nunca sai de rascunho e nunca pode ser assinado.
    """
    from services.rdo_ciclo_vida import PREENCHIDO, RASCUNHO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        ap = _operador(admin.id, func)
        _vincular(ap, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id, criado_por_id=ap.id)
        assert rdo.estado == RASCUNHO
        rid, aid = rdo.id, admin.id

    _cliente_de(aid).post(f'/rdo/{rid}/finalizar', follow_redirects=True)

    with app.app_context():
        recarregado = db.session.get(RDO, rid)
        assert recarregado.estado == PREENCHIDO
        assert recarregado.status == 'Finalizado', (
            'o status legado tem que continuar Finalizado — ≥9 '
            'consumidores filtram por ele')


def test_finalizar_rdo_ja_preenchido_e_no_op():
    """Reenvio de formulário não pode duplicar trilha nem quebrar."""
    from models import RDOTransicaoEstado
    from services.rdo_ciclo_vida import PREENCHIDO

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    cliente = _cliente_de(aid)
    cliente.post(f'/rdo/{rid}/finalizar', follow_redirects=True)
    cliente.post(f'/rdo/{rid}/finalizar', follow_redirects=True)

    with app.app_context():
        assert db.session.get(RDO, rid).estado == PREENCHIDO
        transicoes = RDOTransicaoEstado.query.filter_by(
            rdo_id=rid, estado_novo=PREENCHIDO).count()
        assert transicoes == 1, (
            f'{transicoes} transições para preenchido — o no-op de '
            f'`transicionar` não está funcionando')


# ---------------------------------------------------------------------------
# RDO retificador
# ---------------------------------------------------------------------------

def test_retificar_cria_rdo_novo_e_marca_o_original():
    from services.rdo_ciclo_vida import RASCUNHO, RETIFICADO

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        f_ap, f_ge = _funcionario(admin.id, 'Ap'), _funcionario(admin.id, 'Ge')
        ap, ge = _operador(admin.id, f_ap), _operador(admin.id, f_ge, 'Gestor')
        _vincular(ap, obra, PapelObra.APONTADOR)
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ap)
        rid, apid, geid, oid = rdo.id, ap.id, ge.id, obra.id

    _assinar_pela_rota(rid, apid)
    resposta = _cliente_de(geid).post(
        f'/rdo/{rid}/retificar',
        data={'motivo': 'horas do Márcio lançadas em dobro'},
        follow_redirects=False)
    assert resposta.status_code in (200, 302)

    with app.app_context():
        original = db.session.get(RDO, rid)
        assert original.estado == RETIFICADO

        novo = RDO.query.filter_by(rdo_retificado_id=rid).first()
        assert novo is not None, 'nenhum RDO retificador foi criado'
        assert novo.id != rid
        assert novo.estado == RASCUNHO
        assert novo.obra_id == oid
        assert novo.data_relatorio == original.data_relatorio, (
            'o retificador tem que ser do MESMO dia do original')
        assert novo.numero_rdo != original.numero_rdo


def test_retificador_copia_o_conteudo_do_original():
    from models import RDOMaoObra, RDOServicoSubatividade

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        f_ap, f_ge = _funcionario(admin.id, 'Ap'), _funcionario(admin.id, 'Ge')
        ap, ge = _operador(admin.id, f_ap), _operador(admin.id, f_ge, 'Gestor')
        _vincular(ap, obra, PapelObra.APONTADOR)
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        db.session.add(RDOMaoObra(
            rdo_id=rdo.id, admin_id=admin.id, funcionario_id=f_ap.id,
            funcao_exercida='Montador', horas_trabalhadas=8.0))
        db.session.add(RDOServicoSubatividade(
            rdo_id=rdo.id, admin_id=admin.id,
            nome_subatividade='Montagem de painel', percentual_conclusao=40.0,
            ordem_execucao=1))
        db.session.commit()
        _preencher(rdo, ap)
        rid, apid, geid = rdo.id, ap.id, ge.id

    _assinar_pela_rota(rid, apid)
    _cliente_de(geid).post(f'/rdo/{rid}/retificar', data={'motivo': 'ajuste'})

    with app.app_context():
        novo = RDO.query.filter_by(rdo_retificado_id=rid).first()
        assert novo.comentario_geral == \
            'Montagem dos perfis de aço do painel P3.'
        assert RDOMaoObra.query.filter_by(rdo_id=novo.id).count() == 1
        assert RDOServicoSubatividade.query.filter_by(
            rdo_id=novo.id).count() == 1
        sub = RDOServicoSubatividade.query.filter_by(rdo_id=novo.id).first()
        assert sub.percentual_conclusao == 40.0


def test_original_retificado_continua_imutavel():
    from services.rdo_ciclo_vida import RDOImutavel

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        f_ap, f_ge = _funcionario(admin.id, 'Ap'), _funcionario(admin.id, 'Ge')
        ap, ge = _operador(admin.id, f_ap), _operador(admin.id, f_ge, 'Gestor')
        _vincular(ap, obra, PapelObra.APONTADOR)
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ap)
        rid, apid, geid = rdo.id, ap.id, ge.id

    _assinar_pela_rota(rid, apid)
    _cliente_de(geid).post(f'/rdo/{rid}/retificar', data={'motivo': 'ajuste'})

    with app.app_context():
        original = db.session.get(RDO, rid)
        original.comentario_geral = 'mexendo no retificado'
        with pytest.raises(RDOImutavel):
            db.session.commit()
        db.session.rollback()


def test_retificar_exige_motivo():
    from services.rdo_ciclo_vida import ASSINADO

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        f_ap, f_ge = _funcionario(admin.id, 'Ap'), _funcionario(admin.id, 'Ge')
        ap, ge = _operador(admin.id, f_ap), _operador(admin.id, f_ge, 'Gestor')
        _vincular(ap, obra, PapelObra.APONTADOR)
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, ap)
        rid, apid, geid = rdo.id, ap.id, ge.id

    _assinar_pela_rota(rid, apid)
    _cliente_de(geid).post(f'/rdo/{rid}/retificar', data={'motivo': '  '})

    with app.app_context():
        assert db.session.get(RDO, rid).estado == ASSINADO
        assert RDO.query.filter_by(rdo_retificado_id=rid).count() == 0


def test_nao_retifica_rdo_em_rascunho():
    """RDO não assinado se corrige editando, não retificando."""
    from services.rdo_ciclo_vida import RASCUNHO

    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        func = _funcionario(admin.id, 'Ge')
        ge = _operador(admin.id, func, 'Gestor')
        _vincular(ge, obra, PapelObra.GESTOR)
        rdo = _rdo(obra, admin.id)
        rid, geid = rdo.id, ge.id

    _cliente_de(geid).post(f'/rdo/{rid}/retificar', data={'motivo': 'x'})

    with app.app_context():
        assert db.session.get(RDO, rid).estado == RASCUNHO
        assert RDO.query.filter_by(rdo_retificado_id=rid).count() == 0


# ---------------------------------------------------------------------------
# UI e PDF
# ---------------------------------------------------------------------------

def test_tela_do_rdo_mostra_o_selo_de_estado():
    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        rid, aid = rdo.id, admin.id

    corpo = _cliente_de(aid).get(f'/rdo/{rid}').get_data(as_text=True)
    assert 'Rascunho' in corpo, 'o selo de estado não apareceu na tela'


def test_tela_mostra_botao_de_assinar_para_quem_pode():
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

    corpo = _cliente_de(opid).get(f'/rdo/{rid}').get_data(as_text=True)
    assert f'/rdo/{rid}/assinar' in corpo


def test_tela_nao_mostra_botao_de_assinar_para_leitor():
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

    corpo = _cliente_de(opid).get(f'/rdo/{rid}').get_data(as_text=True)
    assert f'/rdo/{rid}/assinar' not in corpo


def test_tela_do_rdo_assinado_mostra_quem_assinou():
    with app.app_context():
        admin = _admin()
        _liga_escopo(admin.id)
        obra = _obra(admin.id)
        func = _funcionario(admin.id)
        op = _operador(admin.id, func)
        _vincular(op, obra, PapelObra.APONTADOR)
        rdo = _rdo(obra, admin.id)
        _preencher(rdo, op)
        rid, opid, nome = rdo.id, op.id, func.nome

    _assinar_pela_rota(rid, opid)
    corpo = _cliente_de(opid).get(f'/rdo/{rid}').get_data(as_text=True)
    assert nome in corpo
    assert 'Assinado' in corpo


def test_pdf_do_rdo_assinado_e_gerado_com_a_assinatura():
    from models import RDOAssinatura
    from services.rdo_pdf_service import gerar_pdf_rdo

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

    _assinar_pela_rota(rid, opid)

    with app.app_context():
        rdo = db.session.get(RDO, rid)
        assinaturas = RDOAssinatura.query.filter_by(rdo_id=rid).all()
        assert len(assinaturas) == 1
        pdf = gerar_pdf_rdo(rdo)
        assert pdf, 'gerar_pdf_rdo devolveu vazio para RDO assinado'
        assert pdf[:4] == b'%PDF'


def test_pdf_do_rdo_sem_assinatura_continua_gerando():
    """Regressão: o bloco de assinatura manuscrita não pode sumir."""
    from services.rdo_pdf_service import gerar_pdf_rdo

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        rdo = _rdo(obra, admin.id)
        pdf = gerar_pdf_rdo(rdo)
        assert pdf and pdf[:4] == b'%PDF'


def test_hash_nao_depende_da_ordem_quando_as_linhas_EMPATAM_na_chave():
    """O irmão do teste acima, no caso que ele não cobria.

    Aquele usa funcionários distintos — a chave de ordenação já os
    separava sozinha. O problema estava nas linhas que EMPATAM na chave e
    diferem no resto: `sorted` é estável, então o desempate caía na ordem
    do SELECT, que o Postgres não garante. Dois equipamentos
    "Betoneira, qtd 1" com horas diferentes eram o caso mínimo.

    Sem a ordem total, o mesmo conteúdo gera dois hashes — e a
    verificação de integridade acusa adulteração num RDO intacto.
    """
    from models import RDOEquipamento
    from services.rdo_hash import calcular_hash, payload_canonico

    with app.app_context():
        admin = _admin()
        obra = _obra(admin.id)
        r1, r2 = _rdo(obra, admin.id), _rdo(obra, admin.id)
        # mesmas duas linhas, inseridas em ordens opostas
        for horas in (4.0, 6.0):
            db.session.add(RDOEquipamento(
                rdo_id=r1.id, admin_id=admin.id,
                nome_equipamento='Betoneira', quantidade=1,
                horas_uso=horas, estado_conservacao='bom'))
        for horas in (6.0, 4.0):
            db.session.add(RDOEquipamento(
                rdo_id=r2.id, admin_id=admin.id,
                nome_equipamento='Betoneira', quantidade=1,
                horas_uso=horas, estado_conservacao='bom'))
        db.session.commit()
        db.session.refresh(r1)
        db.session.refresh(r2)

        assert payload_canonico(r1)['equipamentos'] == \
            payload_canonico(r2)['equipamentos']

        # o cabeçalho difere (rdo_id, numero_rdo), então compara-se a
        # coleção; para o hash inteiro, o mesmo RDO lido duas vezes tem de
        # dar sempre o mesmo valor
        assert calcular_hash(r1) == calcular_hash(r1)


def test_ordem_total_cobre_todas_as_colecoes_do_payload():
    """Trava a correção: nenhuma coleção pode voltar a ordenar por prefixo.

    Sem isto, uma coleção nova entra com `key=` parcial e o defeito
    volta em silêncio — não há como notar até uma assinatura falhar.
    """
    import inspect

    from services import rdo_hash

    fonte = inspect.getsource(rdo_hash.payload_canonico)
    assert 'key=lambda' not in fonte, (
        'payload_canonico voltou a usar chave de ordenação parcial; '
        'use _ordem_total (chave total sobre a linha inteira)')
    assert fonte.count('_ordem_total(') == 6, (
        'toda coleção do payload precisa passar por _ordem_total')
