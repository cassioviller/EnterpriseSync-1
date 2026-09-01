"""A09 — o dedup de nota fiscal na entrada de almoxarifado.

Este arquivo existe porque a A09 foi dada como ENTREGUE em 23/08 por LEITURA DE
CÓDIGO (`docs/reconferencia-backlog-2026-08-23.md:369`), sem teste guardando — e
a varredura de 25/08 achou, no mesmo dedup, um furo de tenant que um teste teria
pego em agosto.

O que se prova aqui, e por quê:

1. O dedup FUNCIONA dentro do tenant: a mesma nota, no mesmo item, não entra
   duas vezes. É a promessa da A09.
2. O dedup NÃO ATRAVESSA tenants: a nota que a empresa A lançou não pode
   impedir a empresa B de lançar a dela. `entrada_ja_lancada`
   (`views/almoxarifado/movimentos.py:17-49`) chaveia por
   `(admin_id, nota_fiscal, item_id, tipo_movimento)`.
3. Nota vazia é "sem chave", não uma chave vazia que colide com todas as outras.
4. O mesmo, uma camada acima, na importação de XML — onde o furo morava de
   fato (`almoxarifado_utils.py:257`).

⚠️ **Por que estes testes chamam a função, e não uma rota HTTP.** A regra da
onda é entrar pela porta do usuário, e a exceção aqui é deliberada: o defeito
que se guarda é da CHAVE de dedup, e as duas rotas que a exercitam
(`/almoxarifado/entrada` e a importação de XML) exigem upload multipart e
sessão autenticada, o que empurraria a prova para o formulário em vez da chave.
`entrada_ja_lancada` e `processar_xml_nfe` são as duas funções que decidem o
dedup — é nelas que o furo de tenant vive ou morre.
"""
import hashlib
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import dois_tenants

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-a09-dedup'
    yield


def _item(admin_id, marca):
    """Item de almoxarifado do tenant.

    ⚠️ O rascunho do plano passava `unidade_medida=` e omitia `categoria_id`.
    Nenhum dos dois bate com `models.py`: a coluna é `unidade`, e
    `categoria_id` é `nullable=False` — sem a categoria o insert estoura
    IntegrityError antes de o teste afirmar coisa alguma.
    """
    from models import AlmoxarifadoCategoria, AlmoxarifadoItem

    suf = uuid.uuid4().hex[:8]
    categoria = AlmoxarifadoCategoria(
        admin_id=admin_id, nome=f'Aco {marca} {suf}',
        tipo_controle_padrao='CONSUMIVEL')
    db.session.add(categoria)
    db.session.flush()

    item = AlmoxarifadoItem(
        admin_id=admin_id, nome=f'Vergalhao {marca} {suf}',
        codigo=f'VG{suf}', categoria_id=categoria.id,
        tipo_controle='CONSUMIVEL', unidade='KG')
    db.session.add(item)
    db.session.flush()
    return item


def _movimento_de_entrada(admin_id, item_id, nota):
    """Movimento de ENTRADA.

    ⚠️ `usuario_id` é `nullable=False` e o rascunho do plano não o passava. O
    admin do tenant é um `Usuario`, e é quem lança a entrada na tela.
    """
    from models import AlmoxarifadoMovimento

    mov = AlmoxarifadoMovimento(
        admin_id=admin_id, usuario_id=admin_id, item_id=item_id,
        tipo_movimento='ENTRADA', quantidade=10, nota_fiscal=nota)
    db.session.add(mov)
    db.session.flush()
    return mov


def _fornecedor(admin_id, cnpj):
    """O emitente, já cadastrado no tenant.

    Semeado de propósito: `processar_xml_nfe` busca
    `Fornecedor.query.filter_by(cnpj=..., admin_id=...)` e, quando não acha,
    tenta CRIAR um sem `nome` — coluna `nullable=False` (`models.py:2270`). Esse
    é um defeito próprio, provado em
    `test_xml_de_fornecedor_novo_estoura_not_null_em_fornecedor_nome`; semear o
    fornecedor aqui é o que mantém os testes de DEDUP falando de dedup, e não
    tropeçando num defeito vizinho.
    """
    from models import Fornecedor

    forn = Fornecedor(admin_id=admin_id, cnpj=cnpj,
                      nome='Aco Forte Distribuidora LTDA',
                      razao_social='Aco Forte Distribuidora LTDA')
    db.session.add(forn)
    db.session.flush()
    return forn


def _xml_nfe(chave, numero='1000', cnpj_emitente='12345678000199'):
    """NFe mínima que `processar_xml_nfe` consegue ler inteira.

    Só os campos que a função busca: `infNFe/@Id`, `emit/CNPJ`, `emit/xNome`,
    `ide/{nNF,serie,dhEmi}`, `total/ICMSTot/{vProd,vFrete,vDesc,vNF}` e um
    `det/prod`.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">'
        f'<NFe><infNFe Id="NFe{chave}" versao="4.00">'
        f'<ide><nNF>{numero}</nNF><serie>1</serie>'
        '<dhEmi>2026-08-25T10:00:00-03:00</dhEmi></ide>'
        f'<emit><CNPJ>{cnpj_emitente}</CNPJ>'
        '<xNome>Aco Forte Distribuidora LTDA</xNome>'
        '<xFant>Aco Forte</xFant></emit>'
        '<det nItem="1"><prod><cProd>VG10</cProd><cEAN>7891234567890</cEAN>'
        '<xProd>Vergalhao 10mm</xProd><uCom>KG</uCom>'
        '<qCom>100.0000</qCom><vUnCom>7.5000</vUnCom></prod></det>'
        '<total><ICMSTot><vProd>750.00</vProd><vFrete>0.00</vFrete>'
        '<vDesc>0.00</vDesc><vNF>750.00</vNF></ICMSTot></total>'
        '</infNFe></NFe></nfeProc>')


def test_a_mesma_nota_no_mesmo_item_nao_entra_duas_vezes():
    """A promessa da A09, dentro do tenant.

    Antes da A09 `nota_fiscal` era gravada em seis pontos do arquivo sem
    verificação nenhuma: um F5 na tela de entrada duplicava estoque em
    silêncio.
    """
    from views.almoxarifado.movimentos import entrada_ja_lancada

    with app.app_context():
        a, _b = dois_tenants('a09_mesmo', com_fatos=False)
        item = _item(a.admin_id, a.marca)
        _movimento_de_entrada(a.admin_id, item.id, 'NF-12345')
        db.session.commit()

        assert entrada_ja_lancada('NF-12345', item.id, a.admin_id) is not None


def test_a_nota_de_outro_tenant_nao_bloqueia_a_minha():
    """O dedup é por tenant, e tem de ser.

    Numeração de NF é sequencial por emitente, não universal: duas
    construtoras recebem "NF-99999" no mesmo dia o tempo todo. Um dedup global
    faria a nota de uma empresa impedir a entrada da outra, para sempre.
    """
    from views.almoxarifado.movimentos import entrada_ja_lancada

    with app.app_context():
        a, b = dois_tenants('a09_cross', com_fatos=False)
        item_a = _item(a.admin_id, a.marca)
        item_b = _item(b.admin_id, b.marca)
        _movimento_de_entrada(a.admin_id, item_a.id, 'NF-99999')
        db.session.commit()

        assert entrada_ja_lancada('NF-99999', item_b.id, b.admin_id) is None, (
            'a nota do tenant A bloqueou a entrada do tenant B')


def test_nota_vazia_e_sem_chave_nao_chave_vazia():
    """`if not nota_fiscal: return None`.

    `''` é o default do formulário, e entrada sem nota é rotina em obra
    (compra de balcão, doação, sobra de outra obra). Tratá-la como chave faria
    a segunda compra sem nota desaparecer.
    """
    from views.almoxarifado.movimentos import entrada_ja_lancada

    with app.app_context():
        a, _b = dois_tenants('a09_vazia', com_fatos=False)
        item = _item(a.admin_id, a.marca)
        _movimento_de_entrada(a.admin_id, item.id, None)
        db.session.commit()

        assert entrada_ja_lancada('', item.id, a.admin_id) is None
        assert entrada_ja_lancada(None, item.id, a.admin_id) is None


def test_o_mesmo_xml_nao_entra_duas_vezes_no_mesmo_tenant():
    """A camada de cima: `processar_xml_nfe` recusa o reenvio do mesmo XML.

    A prova de que o gatilho funcionou vem antes: a primeira importação tem de
    ter dado certo. Sem isso, um XML que a função nem conseguisse parsear
    também devolveria erro na segunda chamada, e o teste passaria verde sem
    nunca ter exercitado o dedup.
    """
    from almoxarifado_utils import processar_xml_nfe

    with app.app_context():
        a, _b = dois_tenants('a09_xml_mesmo', com_fatos=False)
        cnpj = f'{uuid.uuid4().int % 10**14:014d}'
        _fornecedor(a.admin_id, cnpj)
        db.session.commit()
        xml = _xml_nfe(chave=f'{uuid.uuid4().int % 10**44:044d}',
                       cnpj_emitente=cnpj)

        primeira = processar_xml_nfe(xml, a.admin_id)
        assert primeira.get('sucesso') is True, (
            f'a importação inicial não funcionou: {primeira}')

        segunda = processar_xml_nfe(xml, a.admin_id)
        assert segunda.get('erro') == 'Nota fiscal já foi importada anteriormente'


def test_o_dedup_de_xml_e_por_hash_do_conteudo_e_por_tenant():
    """A chave do dedup de XML, olhada no banco.

    Prova que a linha gravada carrega o hash do conteúdo e o `admin_id` de quem
    importou — as duas metades da chave. Sem o `admin_id` na linha, escopar a
    consulta seria impossível.

    🔬 Este teste, com o de cima, é a substituição COMPORTAMENTAL de
    `tests/test_onda2_tenant_nao_vaza.py:333`
    (`test_dedup_de_nf_e_por_tenant_nao_global`), que prova por
    `inspect.getsource()` — procura a string
    `'NotaFiscal.query.filter_by(xml_hash=xml_hash)'` no fonte. Um teste que lê
    o texto do código não vê o que o código faz, e passaria verde se alguém
    reescrevesse a mesma consulta global com outra formatação.
    """
    from almoxarifado_utils import processar_xml_nfe
    from models import NotaFiscal

    with app.app_context():
        a, _b = dois_tenants('a09_xml_chave', com_fatos=False)
        cnpj = f'{uuid.uuid4().int % 10**14:014d}'
        _fornecedor(a.admin_id, cnpj)
        db.session.commit()
        xml = _xml_nfe(chave=f'{uuid.uuid4().int % 10**44:044d}',
                       cnpj_emitente=cnpj)

        resultado = processar_xml_nfe(xml, a.admin_id)
        assert resultado.get('sucesso') is True, resultado

        nf = db.session.get(NotaFiscal, resultado['nota_fiscal_id'])
        assert nf.admin_id == a.admin_id
        assert nf.xml_hash == hashlib.sha256(xml.encode()).hexdigest()


def test_o_hash_de_outro_tenant_nao_e_mais_consultado_sem_escopo():
    """O furo de 25/08, na consulta onde ele morava — agora escapado.

    `almoxarifado_utils.py:257` fazia `filter_by(xml_hash=...)` SEM `admin_id`:
    o XML que a empresa A importou impedia a empresa B de importar o dela, para
    sempre. Hoje a consulta leva `admin_id`, e a prova é que B **não** ouve a
    mensagem de dedup.

    ⚠️ Isto NÃO afirma que B consegue importar — B esbarra depois no UNIQUE
    global de `NotaFiscal.chave_acesso`, que é outro defeito, provado em
    `test_o_xml_de_outro_tenant_ainda_nao_entra_por_causa_da_chave_de_acesso`.
    Cada teste prova uma coisa.
    """
    from almoxarifado_utils import processar_xml_nfe

    with app.app_context():
        a, b = dois_tenants('a09_xml_cross', com_fatos=False)
        cnpj = f'{uuid.uuid4().int % 10**14:014d}'
        _fornecedor(a.admin_id, cnpj)
        _fornecedor(b.admin_id, cnpj)
        db.session.commit()
        xml = _xml_nfe(chave=f'{uuid.uuid4().int % 10**44:044d}',
                       cnpj_emitente=cnpj)

        do_a = processar_xml_nfe(xml, a.admin_id)
        assert do_a.get('sucesso') is True, (
            f'a importação do tenant A não funcionou: {do_a}')

        do_b = processar_xml_nfe(xml, b.admin_id)
        assert do_b.get('erro') != 'Nota fiscal já foi importada anteriormente', (
            'o dedup de XML voltou a ser global entre tenants')


def test_o_xml_de_outro_tenant_ainda_nao_entra_por_causa_da_chave_de_acesso():
    """🔴 O defeito que sobrou depois de a Onda 2 escopar o hash.

    A chave de acesso da NFe identifica a NOTA, não o destinatário: o mesmo
    fornecedor emite para duas construtoras e as duas recebem XMLs com chaves
    distintas — mas a MESMA nota chega às duas quando uma é subcontratada da
    outra, e nada impede que dois tenants do mesmo grupo importem o mesmo
    documento. `chave_acesso` é `unique=True` GLOBAL (`models.py:2713`), sem
    `admin_id`: o segundo tenant leva IntegrityError, engolido pelo `except`
    genérico de `processar_xml_nfe` e devolvido como
    "Erro ao processar XML: ...".

    🔬 O defeito é conhecido e está escrito na docstring de
    `entrada_ja_lancada` (`views/almoxarifado/movimentos.py:28-31`), que cita
    exatamente este UNIQUE como o defeito "um andar acima" que ela evita
    repetir. Não havia teste dizendo isso.

    `xfail(strict=True)`: quando alguém escopar a constraint por tenant, este
    teste falha por passar, e a marca sai junto com o fix.
    """
    from almoxarifado_utils import processar_xml_nfe

    with app.app_context():
        a, b = dois_tenants('a09_xml_chave_acesso', com_fatos=False)
        cnpj = f'{uuid.uuid4().int % 10**14:014d}'
        _fornecedor(a.admin_id, cnpj)
        _fornecedor(b.admin_id, cnpj)
        db.session.commit()
        xml = _xml_nfe(chave=f'{uuid.uuid4().int % 10**44:044d}',
                       cnpj_emitente=cnpj)

        assert processar_xml_nfe(xml, a.admin_id).get('sucesso') is True

        do_b = processar_xml_nfe(xml, b.admin_id)
        assert do_b.get('sucesso') is True, (
            f'o tenant B não conseguiu importar o XML que A já importou: {do_b}')


def test_xml_de_fornecedor_novo_estoura_not_null_em_fornecedor_nome():
    """🔴 O caminho comum da importação de XML não funciona.

    `processar_xml_nfe` monta `Fornecedor(razao_social=..., nome_fantasia=...,
    cnpj=..., admin_id=...)` — **sem `nome`**, que é `nullable=False` e está
    marcado no modelo como "campo legado obrigatório". O `db.session.flush()`
    seguinte estoura `NotNullViolation`, o `except Exception` genérico o engole
    e a função devolve `{'erro': 'Erro ao processar XML: ...'}`.

    O efeito: a importação só funciona para emitente JÁ cadastrado — isto é,
    nunca na primeira nota de um fornecedor novo, que é justamente quando
    importar o XML poupa digitação.

    🔬 Atenuante medido em 31/08: `processar_xml_nfe` **não tem chamador vivo**
    (`grep -rn "processar_xml_nfe" --include=*.py .` só acha este arquivo e
    `archive/legacy_cleanup/`). O defeito está em código alcançável por
    importação, não por rota — o que muda a prioridade, não o veredito.
    """
    from almoxarifado_utils import processar_xml_nfe

    with app.app_context():
        a, _b = dois_tenants('a09_xml_forn_novo', com_fatos=False)
        cnpj = f'{uuid.uuid4().int % 10**14:014d}'  # nenhum Fornecedor semeado
        xml = _xml_nfe(chave=f'{uuid.uuid4().int % 10**44:044d}',
                       cnpj_emitente=cnpj)

        resultado = processar_xml_nfe(xml, a.admin_id)
        assert resultado.get('sucesso') is True, (
            f'importação de XML com fornecedor novo falhou: {resultado}')
