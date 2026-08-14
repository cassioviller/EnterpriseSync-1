"""O portal do cliente não esconde RDO em silêncio.

A lista era `limit(20)` fixo, sem paginação e sem aviso: na Baia (42 RDOs
de 22/06 a 11/08) o cliente via só de 17/07 pra frente, e o contador do hero
— alimentado por `rdos|length` — dizia "20", como se a obra tivesse começado
ali. Quem procurava o RDO de 07/07, que existe no JSON e no banco, concluía
que a importação não tinha entrado.

Agora: primeira página de RDOS_POR_PAGINA, contador com o TOTAL real, e um
"ver mais" que sobe o limite por `?rdos=`. O parâmetro vem da URL, então o
piso (RDOS_POR_PAGINA) e o teto (RDOS_LIMITE_MAX) são testados junto — cada
linha da lista carrega o thumbnail base64 da 1ª foto do RDO, e sem teto uma
obra longa viraria uma página inteira de uma vez.
"""
import os
import re
import secrets
import sys
import uuid
from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import Cliente, Obra, RDO, TipoUsuario, Usuario
from portal_obras_views import RDOS_LIMITE_MAX, RDOS_POR_PAGINA

pytestmark = pytest.mark.integration

TOTAL_RDOS = RDOS_POR_PAGINA + 17   # 37, como a obra da Baia no banco
DATA_BASE = date(2026, 6, 22)       # 1º RDO da Baia


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-portal-rdos-paginacao'
    yield


@pytest.fixture
def obra_com_rdos():
    """Obra publicada no portal com TOTAL_RDOS finalizados, um por dia."""
    with app.app_context():
        suf = uuid.uuid4().hex[:8]
        admin = Usuario(
            username=f'prp_{suf}', email=f'prp_{suf}@test.local',
            nome=f'Adm {suf}', password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2')
        db.session.add(admin)
        db.session.commit()

        cliente = Cliente(nome=f'Cliente {suf}', admin_id=admin.id)
        db.session.add(cliente)
        db.session.commit()

        obra = Obra(nome=f'Baias {suf}', codigo=f'B{suf[:6].upper()}',
                    data_inicio=DATA_BASE, admin_id=admin.id,
                    cliente_id=cliente.id, ativo=True, portal_ativo=True,
                    token_cliente=secrets.token_urlsafe(32))
        db.session.add(obra)
        db.session.commit()

        for i in range(TOTAL_RDOS):
            dia = DATA_BASE + timedelta(days=i)
            db.session.add(RDO(
                numero_rdo=f'RDO-{obra.id}-{dia:%Y%m%d}', obra_id=obra.id,
                admin_id=admin.id, criado_por_id=admin.id, data_relatorio=dia,
                local='Campo', status='Finalizado',
                comentario_geral=f'Dia {i + 1}'))
        db.session.commit()

        token = obra.token_cliente
        yield token

        for r in RDO.query.filter_by(obra_id=obra.id).all():
            db.session.delete(r)
        db.session.delete(obra)
        db.session.delete(cliente)
        db.session.delete(admin)
        db.session.commit()


def _datas(html):
    """Datas dos RDOs listados, na ordem em que a página as mostra."""
    return re.findall(r'class="rdo-data">([^<]+)<', html)


def _pagina(token, query=''):
    return app.test_client().get(f'/portal/obra/{token}{query}').get_data(as_text=True)


def test_primeira_pagina_mostra_o_bloco_inicial_e_o_total_real(obra_com_rdos):
    html = _pagina(obra_com_rdos)

    assert len(_datas(html)) == RDOS_POR_PAGINA
    # Contador da seção e métrica do hero: o TOTAL da obra, não o da página —
    # era daqui que saía o "20" que fazia o cliente achar que faltava RDO.
    assert f'section-counter">{TOTAL_RDOS}<' in html
    assert re.search(
        rf'hm-val">{TOTAL_RDOS}</span>\s*<span class="hm-lbl">Relat', html)
    # E o corte é declarado, não mudo.
    assert f'Mostrando os {RDOS_POR_PAGINA} mais recentes de {TOTAL_RDOS}' in html


def test_ver_mais_alcanca_o_rdo_mais_antigo(obra_com_rdos):
    html = _pagina(obra_com_rdos)
    mais_recentes = _datas(html)
    assert f'{DATA_BASE:%d/%m/%Y}' not in mais_recentes

    # O botão é um link puro (sem JS) para o próximo bloco, ancorado na seção.
    href = re.search(r'rdo-mais-btn"\s+href="([^"]+)"', html).group(1)
    assert href.endswith('#rdos')

    html2 = _pagina(obra_com_rdos, href.split(f'/portal/obra/{obra_com_rdos}')[1]
                    .replace('#rdos', ''))
    datas2 = _datas(html2)
    assert len(datas2) == min(RDOS_POR_PAGINA * 2, TOTAL_RDOS) == TOTAL_RDOS
    assert datas2[-1] == f'{DATA_BASE:%d/%m/%Y}'      # o 1º dia da obra aparece
    # E o botão some no fim (a classe segue no <style>; o que não existe mais
    # é a âncora).
    assert re.search(r'rdo-mais-btn"\s+href=', html2) is None


@pytest.mark.parametrize('query', ['?rdos=abc', '?rdos=-5', '?rdos=0', '?rdos='])
def test_limite_invalido_cai_no_bloco_inicial(obra_com_rdos, query):
    """`?rdos` vem da URL: lixo e valor abaixo do piso não podem quebrar a
    página nem devolver lista vazia ao cliente."""
    assert len(_datas(_pagina(obra_com_rdos, query))) == RDOS_POR_PAGINA


def test_limite_absurdo_para_no_teto(obra_com_rdos):
    """Teto do servidor: `?rdos=99999` não vira uma página sem fim."""
    html = _pagina(obra_com_rdos, '?rdos=99999')
    assert len(_datas(html)) == min(RDOS_LIMITE_MAX, TOTAL_RDOS) == TOTAL_RDOS
