"""Manual da ciência em PDF — o que a construtora manda ao cliente.

O manual afirma regras ao cliente: 72 h de senha temporária, mínimo de 8
caracteres, 10 erros bloqueiam. Se alguém mudar a constante e não o texto, o
documento passa a mentir para quem está do lado de fora — e ninguém percebe,
porque o PDF continua sendo gerado. Estes testes leem o texto do PDF e cobram
os números do código.
"""
import io
import re
import uuid

import pytest
from werkzeug.security import generate_password_hash

from app import app
from models import ObraSignatarioCliente, Usuario, TipoUsuario, db
from services.portal_signatario_auth import SENHA_MIN


def _sfx():
    """O banco de teste PERSISTE entre execuções — username fixo colide na
    segunda rodada."""
    return uuid.uuid4().hex[:8]


def _texto(pdf: bytes) -> str:
    """Texto do PDF, minúsculo e com os espaços normalizados."""
    pypdf = pytest.importorskip('pypdf')
    leitor = pypdf.PdfReader(io.BytesIO(pdf))
    bruto = '\n'.join((p.extract_text() or '') for p in leitor.pages)
    return re.sub(r'\s+', ' ', bruto).lower()


@pytest.fixture(scope='module')
def pdf():
    from services.manual_ciencia_pdf import gerar_manual_ciencia
    with app.app_context():
        return gerar_manual_ciencia()


def test_sai_um_pdf_valido(pdf):
    assert pdf[:5] == b'%PDF-'
    assert len(pdf) > 3000


def test_traz_as_cinco_secoes(pdf):
    t = _texto(pdf)
    for secao in ('primeiro acesso', 'dando ciência num relatório',
                  'o que fica registrado', 'se algo não sair como esperado',
                  'perguntas rápidas'):
        assert secao in t, f'seção ausente: {secao}'


def test_os_cinco_passos_da_ciencia_estao_la(pdf):
    t = _texto(pdf)
    for passo in ('abra o relatório do dia', 'leia até o fim',
                  'marque a caixa ao lado do seu nome',
                  'digite sua senha e confirme', 'baixe o seu recibo'):
        assert passo in t, f'passo ausente: {passo}'


def test_o_prazo_da_senha_temporaria_e_o_do_codigo(pdf):
    horas = ObraSignatarioCliente.HORAS_SENHA_TEMPORARIA
    assert f'{horas} horas' in _texto(pdf)


def test_o_minimo_da_senha_e_o_do_codigo(pdf):
    assert f'{SENHA_MIN} caracteres' in _texto(pdf)


def test_o_limite_de_erros_e_o_do_codigo(pdf):
    assert f'{ObraSignatarioCliente.MAX_FALHAS} erros' in _texto(pdf)


def test_diz_que_ciencia_nao_e_aprovacao(pdf):
    """A frase que separa 'tomei conhecimento' de 'concordo' — é o ponto do
    documento que mais custa caro se sumir."""
    assert 'não é aprovar nem concordar' in _texto(pdf)


def test_nomeia_a_secao_como_ciencia_dos_responsaveis(pdf):
    t = _texto(pdf)
    assert 'ciência dos responsáveis' in t
    assert 'ciência do cliente' not in t


def test_nao_leva_a_marca_da_construtora():
    """Mesma regra do portal e do recibo: material do lado do cliente não
    carrega o nome de quem executa a obra.

    Cadastra uma empresa com nome-sentinela e confere que ele NÃO sai no PDF.
    Hoje passa por construção (o gerador não recebe tenant nem consulta
    `ConfiguracaoEmpresa`); o teste existe para o dia em que alguém resolver
    "só colocar o timbre" aqui como nos outros documentos.
    """
    from models import ConfiguracaoEmpresa
    from services.manual_ciencia_pdf import gerar_manual_ciencia

    sentinela = 'Zorplex Construtora Sentinela'
    with app.app_context():
        suf = _sfx()
        admin = Usuario(
            username=f'man_marca_{suf}', email=f'man_marca_{suf}@teste.com',
            nome='Admin Marca', password_hash=generate_password_hash('x'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True)
        db.session.add(admin)
        db.session.flush()
        db.session.add(ConfiguracaoEmpresa(admin_id=admin.id,
                                           nome_empresa=sentinela))
        db.session.commit()

        t = _texto(gerar_manual_ciencia())

    assert sentinela.lower() not in t
    assert 'construtora sentinela' not in t


def test_a_rota_exige_login():
    """É rota da construtora, não do portal: sem sessão, não baixa."""
    c = app.test_client()
    r = c.get('/portal/manual-ciencia.pdf')
    assert r.status_code in (301, 302, 401), r.status_code
    if r.status_code in (301, 302):
        assert 'login' in r.headers.get('Location', '').lower()


def test_logado_baixa_como_anexo():
    with app.app_context():
        suf = _sfx()
        admin = Usuario(
            nome='Admin Manual', username=f'man_pdf_{suf}',
            email=f'man_pdf_{suf}@teste.com', tipo_usuario=TipoUsuario.ADMIN,
            ativo=True, password_hash=generate_password_hash('x'))
        db.session.add(admin)
        db.session.commit()
        aid = admin.id

    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(aid)
        sess['_fresh'] = True

    r = c.get('/portal/manual-ciencia.pdf')
    assert r.status_code == 200
    assert r.mimetype == 'application/pdf'
    disp = r.headers.get('Content-Disposition', '')
    assert 'attachment' in disp and '.pdf' in disp
    assert r.get_data()[:5] == b'%PDF-'
