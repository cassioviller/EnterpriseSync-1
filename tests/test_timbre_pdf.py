"""Timbre dos PDFs — o JSON de identidade importável pela tela (migration 286).

Cobre as três camadas de precedência (`services/timbre_pdf`):

  1. `PADRAO` — os tokens do kit oficial;
  2. os campos soltos de `ConfiguracaoEmpresa`, que a tela já preenchia;
  3. o JSON `timbre_pdf` importado.

E o que mais importa em torno disso: que o import seja **incremental** (um
arquivo só com cores não apaga a logo), que a validação recuse arquivo torto
com a lista COMPLETA de erros, e que a cor importada chegue de verdade ao
desenho do PDF.

NOTA de harness: requests do test client ficam FORA de app_context aberto —
Flask-Login cacheia `g._login_user` e congela o primeiro usuário resolvido.
"""
import base64
import json
import os
import sys
import uuid
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import ConfiguracaoEmpresa, TipoUsuario, Usuario
from services.timbre_pdf import (PADRAO, TimbreInvalido, carregar, exportar,
                                 importar, validar)

pytestmark = pytest.mark.integration

def _png_valido() -> bytes:
    """PNG real, gerado na hora pelo PIL.

    O blob base64 "1x1 transparente" que este arquivo usava antes tinha o
    checksum do IDAT quebrado: `Image.open` engolia, `Image.verify` (que a
    validação do timbre usa) recusava — e nos testes do cronograma ele passava
    silenciosamente, com a logo caindo no fallback sem ninguém notar. Gerar a
    imagem elimina a classe do problema.
    """
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (8, 4), (22, 41, 74)).save(buf, format='PNG')
    return buf.getvalue()


PNG_MINIMO = _png_valido()
PNG_MINIMO_B64 = base64.b64encode(PNG_MINIMO).decode('ascii')


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-timbre-pdf'
    yield


def _tenant(*, com_config=True, **campos):
    """admin V2 novo, com ou sem ConfiguracaoEmpresa. Devolve o admin_id."""
    with app.app_context():
        suf = uuid.uuid4().hex[:10]
        admin = Usuario(
            username=f'tim_{suf}', email=f'tim_{suf}@test.local',
            nome=f'Adm Timbre {suf}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.commit()
        if com_config:
            db.session.add(ConfiguracaoEmpresa(
                admin_id=admin.id,
                nome_empresa=campos.pop('nome_empresa', f'Construtora {suf}'),
                **campos))
            db.session.commit()
        return admin.id


def _http(user_id: int):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def _importar(admin_id, payload):
    with app.app_context():
        timbre = importar(admin_id, json.dumps(payload).encode('utf-8'))
        db.session.commit()
        return timbre


# ═════════════════════════════════════════════════════════════════════════════
# PRECEDÊNCIA
# ═════════════════════════════════════════════════════════════════════════════

def test_sem_configuracao_devolve_o_padrao_do_kit():
    admin_id = _tenant(com_config=False)
    with app.app_context():
        t = carregar(admin_id)
    assert t['cores'] == PADRAO['cores']
    assert t['empresa']['nome'] == 'Empresa'
    assert t['logo_base64'] == ''


def test_campos_soltos_da_tela_entram_sem_json_nenhum():
    """Camada 2: quem já usava a tela de Empresa não perde nada."""
    admin_id = _tenant(nome_empresa='Construtora Beta', cnpj='11.222.333/0001-44',
                       endereco='Rua A, 1\nCentro', website='beta.com.br',
                       logo_pdf_base64=PNG_MINIMO_B64)
    with app.app_context():
        t = carregar(admin_id)
    assert t['empresa']['nome'] == 'Construtora Beta'
    assert t['empresa']['cnpj'] == '11.222.333/0001-44'
    # A quebra de linha do endereço é achatada: no cabeçalho ele é uma linha só.
    assert t['empresa']['endereco'] == 'Rua A, 1 Centro'
    assert t['logo_base64'] == PNG_MINIMO_B64
    assert t['cores'] == PADRAO['cores'], 'sem JSON, as cores são as do kit'


def test_json_importado_sobrepoe_os_campos_soltos():
    admin_id = _tenant(nome_empresa='Nome Antigo', cnpj='00.000.000/0001-00')
    t = _importar(admin_id, {'versao': 1,
                             'empresa': {'nome': 'Nome Novo',
                                         'razao_social': 'Razão Ltda.'},
                             'cores': {'navy': '#004225'}})
    assert t['empresa']['nome'] == 'Nome Novo'
    assert t['empresa']['razao_social'] == 'Razão Ltda.'
    # O que o JSON não trouxe continua vindo da camada de baixo.
    assert t['empresa']['cnpj'] == '00.000.000/0001-00'
    assert t['cores']['navy'] == '#004225'
    assert t['cores']['laranja'] == PADRAO['cores']['laranja']


def test_import_e_incremental_e_nao_apaga_a_logo():
    """O caso que mais dói: importar só as cores não pode zerar a logo."""
    admin_id = _tenant()
    _importar(admin_id, {'logo_base64': PNG_MINIMO_B64,
                         'empresa': {'nome': 'Com Logo'}})
    t = _importar(admin_id, {'cores': {'navy': '#123456'}})
    assert t['logo_base64'] == PNG_MINIMO_B64
    assert t['empresa']['nome'] == 'Com Logo'
    assert t['cores']['navy'] == '#123456'


def test_import_cria_a_configuracao_quando_o_tenant_nao_tem():
    admin_id = _tenant(com_config=False)
    t = _importar(admin_id, {'cores': {'navy': '#111111'}})
    assert t['cores']['navy'] == '#111111'
    with app.app_context():
        assert ConfiguracaoEmpresa.query.filter_by(
            admin_id=admin_id).first() is not None


def test_timbre_guardado_que_nao_e_objeto_e_ignorado_sem_quebrar():
    """Coluna JSONB aceita lista e string; a leitura não pode estourar."""
    admin_id = _tenant()
    with app.app_context():
        config = ConfiguracaoEmpresa.query.filter_by(admin_id=admin_id).first()
        config.timbre_pdf = ['não', 'é', 'objeto']
        db.session.commit()
        t = carregar(admin_id)
    assert t['cores'] == PADRAO['cores']


# ═════════════════════════════════════════════════════════════════════════════
# VALIDAÇÃO
# ═════════════════════════════════════════════════════════════════════════════

def test_recusa_cor_fora_do_formato_hex():
    with pytest.raises(TimbreInvalido) as e:
        validar({'cores': {'navy': 'azul-marinho'}})
    assert 'cores.navy' in e.value.erros[0]


def test_recusa_cor_desconhecida_nomeando_as_aceitas():
    with pytest.raises(TimbreInvalido) as e:
        validar({'cores': {'roxo': '#112233'}})
    assert 'cor desconhecida' in e.value.erros[0]
    assert 'navy' in e.value.erros[0]


def test_recusa_logo_que_nao_e_base64():
    with pytest.raises(TimbreInvalido) as e:
        validar({'logo_base64': 'isto-nao-e-base64-!!!'})
    assert 'base64' in e.value.erros[0]


def test_recusa_base64_valido_que_nao_e_imagem():
    """Sem esta checagem, o erro só apareceria ao desenhar o PDF — depois de
    salvar, sair da tela e clicar em baixar."""
    lixo = base64.b64encode(b'nao sou uma imagem').decode()
    with pytest.raises(TimbreInvalido) as e:
        validar({'logo_base64': lixo})
    assert 'imagem' in e.value.erros[0]


def test_junta_todos_os_erros_de_uma_vez():
    """Quem editou o arquivo à mão quer a lista completa, não um por
    tentativa."""
    with pytest.raises(TimbreInvalido) as e:
        validar({'cores': {'navy': 'x', 'laranja': 'y'},
                 'empresa': {'nome': 123},
                 'logo_base64': '!!!'})
    assert len(e.value.erros) >= 4


def test_recusa_versao_futura():
    with pytest.raises(TimbreInvalido) as e:
        validar({'versao': 99})
    assert '99' in e.value.erros[0]


def test_recusa_arquivo_que_nao_e_objeto():
    with pytest.raises(TimbreInvalido):
        validar(['lista'])


def test_recusa_arquivo_grande_demais():
    admin_id = _tenant()
    with app.app_context():
        with pytest.raises(TimbreInvalido) as e:
            importar(admin_id, b'{' + b'x' * (5 * 1024 * 1024) + b'}')
    assert 'limite' in e.value.erros[0]


def test_recusa_json_malformado_dizendo_a_linha():
    admin_id = _tenant()
    with app.app_context():
        with pytest.raises(TimbreInvalido) as e:
            importar(admin_id, b'{"cores": }')
    assert 'JSON inválido' in e.value.erros[0]


def test_chave_desconhecida_no_bloco_empresa_e_ignorada():
    """Arquivo de uma versão futura, com campo novo, ainda importa."""
    limpo = validar({'empresa': {'nome': 'X', 'campo_do_futuro': 'y'}})
    assert limpo['empresa'] == {'nome': 'X'}


def test_valores_vazios_nao_sobrescrevem_o_que_a_tela_preencheu():
    """Exportar, apagar um valor no editor e reimportar não pode zerar o
    campo — senão o arquivo "limpo" viraria uma arma."""
    admin_id = _tenant(nome_empresa='Construtora Gama')
    t = _importar(admin_id, {'empresa': {'nome': '', 'website': ''}})
    assert t['empresa']['nome'] == 'Construtora Gama'


# ═════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═════════════════════════════════════════════════════════════════════════════

def test_export_tem_todas_as_chaves_para_servir_de_ponto_de_partida():
    admin_id = _tenant()
    with app.app_context():
        t = exportar(admin_id)
    assert set(t['cores']) == set(PADRAO['cores'])
    assert set(t['empresa']) == set(PADRAO['empresa'])
    assert t['versao'] == PADRAO['versao']


def test_export_sem_logo_fica_pequeno():
    admin_id = _tenant()
    _importar(admin_id, {'logo_base64': PNG_MINIMO_B64})
    with app.app_context():
        com = json.dumps(exportar(admin_id))
        sem = json.dumps(exportar(admin_id, com_logo=False))
    assert len(sem) < len(com)
    assert json.loads(sem)['logo_base64'] == ''


# ═════════════════════════════════════════════════════════════════════════════
# O TIMBRE CHEGA AO PDF
# ═════════════════════════════════════════════════════════════════════════════

def _pdf_de_teste(admin_id):
    from services.cronograma_pdf import (exportar_cronograma_pdf,
                                         montar_marca_tenant)
    linhas = [{'numero': 1, 'nivel': 0, 'nome': 'OBRA', 'duracao_dias': 10,
               'data_inicio': date(2026, 7, 1), 'data_fim': date(2026, 7, 10),
               'percentual': 50.0, 'is_pai': True, 'is_raiz': True,
               'is_marco': False}]
    dados = {'obra': {'nome': 'Obra Timbre', 'codigo': 'T1', 'cliente': 'C',
                      'data_inicio': date(2026, 7, 1),
                      'data_fim': date(2026, 7, 10),
                      'progresso_geral': 50.0, 'modo_cliente': False},
             'linhas': linhas}
    with app.app_context():
        return exportar_cronograma_pdf(dados, montar_marca_tenant(admin_id))


def test_marca_do_pdf_le_as_cores_do_timbre():
    admin_id = _tenant()
    _importar(admin_id, {'cores': {'navy': '#004225'}})
    from services.cronograma_pdf import montar_marca_tenant
    with app.app_context():
        marca = montar_marca_tenant(admin_id)
    assert marca['cores']['navy'] == '#004225'
    assert marca['cores']['laranja'] == PADRAO['cores']['laranja']


def test_trocar_a_cor_muda_o_pdf_gerado():
    """A prova de que a cor não para no meio do caminho: dois timbres
    diferentes produzem bytes diferentes."""
    admin_id = _tenant()
    antes = _pdf_de_teste(admin_id)
    _importar(admin_id, {'cores': {'navy': '#004225', 'laranja': '#7C3AED'}})
    depois = _pdf_de_teste(admin_id)
    assert antes[:5] == b'%PDF-' and depois[:5] == b'%PDF-'
    assert antes != depois


def test_cor_ausente_no_timbre_cai_no_token_do_kit():
    """`_cor` não pode estourar KeyError com um timbre salvo antes de a cor
    existir no schema."""
    from services.cronograma_pdf import PADRAO_CORES, _cor
    marca = {'cores': {'navy': '#004225'}}
    assert _cor(marca, 'navy') == '#004225'
    assert _cor(marca, 'fio') == PADRAO_CORES['fio']
    assert _cor({}, 'laranja') == PADRAO_CORES['laranja']


def test_razao_social_entra_no_cabecalho_quando_existe():
    admin_id = _tenant()
    _importar(admin_id, {'empresa': {'razao_social': 'Angelin Engenharia Ltda.'}})
    from services.cronograma_pdf import montar_marca_tenant
    with app.app_context():
        marca = montar_marca_tenant(admin_id)
    assert marca['razao_social'] == 'Angelin Engenharia Ltda.'
    assert _pdf_de_teste(admin_id)[:5] == b'%PDF-'


# ═════════════════════════════════════════════════════════════════════════════
# ROTAS DA TELA
# ═════════════════════════════════════════════════════════════════════════════

def test_rota_de_export_devolve_json_valido():
    admin_id = _tenant()
    r = _http(admin_id).get('/configuracoes/empresa/timbre/exportar.json')
    assert r.status_code == 200
    assert r.mimetype == 'application/json'
    assert 'attachment' in r.headers.get('Content-Disposition', '')
    corpo = json.loads(r.get_data(as_text=True))
    assert set(corpo['cores']) == set(PADRAO['cores'])


def test_rota_de_export_sem_logo():
    admin_id = _tenant()
    _importar(admin_id, {'logo_base64': PNG_MINIMO_B64})
    r = _http(admin_id).get(
        '/configuracoes/empresa/timbre/exportar.json?sem_logo=1')
    assert json.loads(r.get_data(as_text=True))['logo_base64'] == ''


def test_rota_de_import_grava_e_avisa():
    import io
    admin_id = _tenant()
    arquivo = json.dumps({'cores': {'navy': '#004225'}}).encode()
    r = _http(admin_id).post(
        '/configuracoes/empresa/timbre/importar',
        data={'timbre_json': (io.BytesIO(arquivo), 'timbre.json')},
        content_type='multipart/form-data', follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert carregar(admin_id)['cores']['navy'] == '#004225'


def test_rota_de_import_recusa_arquivo_torto_sem_gravar():
    import io
    admin_id = _tenant()
    _importar(admin_id, {'cores': {'navy': '#004225'}})
    r = _http(admin_id).post(
        '/configuracoes/empresa/timbre/importar',
        data={'timbre_json': (io.BytesIO(b'{"cores": {"navy": "verde"}}'),
                              'timbre.json')},
        content_type='multipart/form-data', follow_redirects=True)
    assert r.status_code == 200
    assert 'não foi aceito' in r.get_data(as_text=True)
    with app.app_context():
        assert carregar(admin_id)['cores']['navy'] == '#004225', \
            'o import recusado não pode ter mexido no que já estava lá'


def test_rota_de_import_sem_arquivo_avisa():
    admin_id = _tenant()
    r = _http(admin_id).post('/configuracoes/empresa/timbre/importar',
                             data={}, follow_redirects=True)
    assert r.status_code == 200
    assert 'Escolha um arquivo' in r.get_data(as_text=True)


def test_a_tela_de_empresa_mostra_o_cartao_do_timbre():
    admin_id = _tenant()
    html = _http(admin_id).get('/configuracoes/empresa').get_data(as_text=True)
    assert 'Timbre dos PDFs' in html
    assert '/configuracoes/empresa/timbre/exportar.json' in html
    assert '/configuracoes/empresa/timbre/importar' in html
    assert 'enctype="multipart/form-data"' in html
