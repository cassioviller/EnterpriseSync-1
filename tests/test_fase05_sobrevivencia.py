"""Fase 0.5 / Pacote 1 — o sistema falha alto em vez de falhar em silêncio.

Cada teste aqui trava um comportamento que, antes desta fase, degradava
silenciosamente:

  · sem `SESSION_SECRET`, produção subia com uma chave publicada no repo;
  · sem `DATABASE_URL`, subia com a connection string real embutida no código;
  · um 500 devolvia o traceback Python completo ao navegador;
  · escrita anônima não deixava rastro em lugar nenhum.

Os testes de boot rodam em SUBPROCESSO porque `app.py` executa a
configuração no import — não dá para reimportar com outro ambiente no mesmo
processo.
"""
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

pytestmark = pytest.mark.integration


def _codigo(nome_arquivo):
    """Fonte do arquivo SEM linhas de comentário.

    As correções desta fase deixam comentários explicando o que foi removido
    — e esses comentários citam justamente os trechos proibidos. Sem tirar os
    comentários, o teste acusaria a própria documentação da correção.
    """
    with open(os.path.join(RAIZ, nome_arquivo), encoding='utf-8') as fh:
        linhas = fh.read().split('\n')
    return '\n'.join(l for l in linhas if not l.lstrip().startswith('#'))


def _bootar(env_extra, remover=()):
    """Tenta importar `app` num subprocesso com o ambiente dado."""
    env = dict(os.environ)
    for k in remover:
        env.pop(k, None)
    env.update(env_extra)
    env['PYTHONPATH'] = RAIZ
    return subprocess.run(
        [sys.executable, '-c', 'import app'],
        cwd=RAIZ, env=env, capture_output=True, text=True, timeout=300)


# ---------------------------------------------------------------------------
# 1.2 — segredos fail-closed
# ---------------------------------------------------------------------------

def test_producao_sem_session_secret_nao_sobe():
    r = _bootar({'SIGE_ENV': 'production'}, remover=('SESSION_SECRET',))
    assert r.returncode != 0, 'app subiu em produção sem SESSION_SECRET'
    assert 'SESSION_SECRET' in r.stderr


def test_desenvolvimento_sem_session_secret_gera_chave_efemera():
    """Em dev o boot segue — mas com chave gerada, nunca com valor do repo."""
    r = _bootar({'SIGE_ENV': 'development'}, remover=('SESSION_SECRET',))
    assert r.returncode == 0, r.stderr[-2000:]
    assert 'dev-only-fallback-key-not-for-production' not in (r.stdout + r.stderr)


def test_sem_database_url_nao_sobe():
    r = _bootar({'SIGE_ENV': 'development'}, remover=('DATABASE_URL',))
    assert r.returncode != 0, 'app subiu sem DATABASE_URL'
    assert 'DATABASE_URL' in r.stderr


def test_nenhuma_credencial_default_no_codigo():
    """A connection string de produção não pode voltar como default."""
    import re

    with open(os.path.join(RAIZ, 'app.py'), encoding='utf-8') as fh:
        fonte = fh.read()
    # Qualquer postgres:// com usuário:senha embutidos é proibido no código.
    achados = re.findall(r'postgresql?://[^\s"\']*:[^\s"\'@/]+@', fonte)
    assert not achados, f'credencial embutida em app.py: {achados}'


def test_env_de_producao_e_explicito():
    """SIGE_ENV governa; a heurística REPL_ID é só fallback com aviso."""
    r = _bootar({'SIGE_ENV': 'production', 'SESSION_SECRET': 'x' * 40})
    assert 'PRODUÇÃO' in (r.stdout + r.stderr)
    r = _bootar({'SIGE_ENV': 'development'})
    assert 'DESENVOLVIMENTO' in (r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# 1.3 — observabilidade
# ---------------------------------------------------------------------------

def test_proxyfix_confia_no_x_forwarded_for():
    """Sem `x_for`, o IP do cliente nunca chegava à aplicação."""
    from app import app

    with app.test_request_context(
            '/', environ_base={'REMOTE_ADDR': '10.0.0.1'},
            headers={'X-Forwarded-For': '203.0.113.7'}):
        pass  # o contexto de teste não passa pelo middleware

    # Verificação estrutural: o middleware precisa estar configurado com x_for.
    mw = app.wsgi_app
    assert getattr(mw, 'x_for', 0) >= 1, (
        'ProxyFix sem x_for — request.remote_addr devolve o IP do proxy')


def test_errorhandler_nao_vaza_traceback_em_producao():
    """O handler global devolvia o traceback completo em HTML, sem checar ambiente."""
    fonte = _codigo('main.py')
    assert 'IS_PRODUCTION' in fonte, (
        'handle_exception precisa ramificar por ambiente')
    assert 'Copiar Erro Completo' not in fonte, (
        'o botão de copiar traceback ainda existe')
    # E HTTPException não pode mais virar 500.
    assert 'HTTPException' in fonte


def test_auditoria_registra_escrita_anonima(caplog):
    """Escrita sem usuário autenticado tem de aparecer no log, com IP."""
    import logging

    import main  # noqa: F401
    from app import app

    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    c = app.test_client()
    with caplog.at_level(logging.INFO, logger='sige.acesso'):
        c.post('/salvar-rdo-flexivel', data={'obra_id': '1'},
               environ_base={'REMOTE_ADDR': '203.0.113.7'})

    linhas = [r.message for r in caplog.records if r.name == 'sige.acesso']
    assert linhas, 'nenhuma linha de auditoria emitida para POST'
    assert any('ESCRITA-ANONIMA' in ln for ln in linhas), linhas
    assert any('ip=203.0.113.7' in ln for ln in linhas), linhas
    assert any('metodo=POST' in ln for ln in linhas), linhas


def test_auditoria_nao_loga_leitura(caplog):
    """GET fica com o access log do gunicorn; aqui só escrita."""
    import logging

    import main  # noqa: F401
    from app import app

    c = app.test_client()
    with caplog.at_level(logging.INFO, logger='sige.acesso'):
        c.get('/login')
    assert not [r for r in caplog.records if r.name == 'sige.acesso']


def test_nivel_de_log_e_configurado_em_um_lugar_so():
    """`main.py` tinha um basicConfig que era no-op e suprimia todo DEBUG."""
    fonte = _codigo('main.py')
    assert 'logging.basicConfig' not in fonte, (
        'basicConfig duplicado de volta em main.py — é no-op e engana')
    assert 'LOG_LEVEL' in fonte


# ---------------------------------------------------------------------------
# 3.2 — imports mortos
# ---------------------------------------------------------------------------

def test_import_de_modulo_inexistente_removido():
    assert 'import handlers.folha_handlers' not in _codigo('app.py')
