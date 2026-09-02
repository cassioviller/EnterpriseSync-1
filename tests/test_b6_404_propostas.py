"""B6.4 — lote a: `propostas_consolidated.py`, o 404 que está escrito e é engolido.

**Estado medido em 01/09: a Task B6.4 nunca foi executada.** 🔬 `grep -c 'except
HTTPException' propostas_consolidated.py` = **0**. O censo AST confirma o número
do plano (`rodada-b6:585-600`) na vírgula: **18** `first_or_404` tenant-scoped
**dentro** de `try` com `except Exception` que flasha/jsonifica; as outras 8
ocorrências do arquivo estão fora de qualquer try.

## O que a medição achou, e o plano não sabia

Este lote é diferente dos outros quatro da família. Nos lotes c, d e e o 404
**não estava escrito**: a rota consultava, não achava, e redirecionava. Aqui o
404 **está escrito** — `first_or_404()` o levanta — e o `except Exception` o
apanha e o converte em outra coisa. O resultado tem uma assinatura que nenhum
outro lote tem:

🔴 **Em quatro rotas o engolimento vira HTTP 500.** `alterar_status`,
`whatsapp_registrar`, `upload_arquivo` e `deletar_arquivo` respondem
`{"success": false, "message": "Erro ao alterar status: 404 Not Found: The
requested URL was not found on the server..."}` — **com status 500**. O texto
"404 Not Found" viaja, literalmente, dentro do corpo de um erro de servidor.
Uma recusa de isolamento entre empresas está sendo contada como falha da
aplicação por qualquer monitor que olhe a taxa de 5xx.

Nas outras catorze o mesmo 404 vira flash + 302: *"Erro ao gerar PDF: 404 Not
Found: The requested URL..."*.

🔬 A string `404 Not Found` aparece na resposta ao estranho em **17 das 18**
rotas, e em nenhuma das respostas ao dono: é a prova direta de que o 404 foi
escrito e engolido, e não de que nunca existiu. A décima oitava,
`salvar_observacao_validacao`, é a única que não ecoa o texto do werkzeug —
flasha *"Erro ao salvar observação de validação."* e pronto. Por isso a
precondição deste arquivo **não** é "o dono não vê a marca do 404": nessa rota a
marca não aparece para ninguém, e o teste passaria mesmo com o andaime quebrado.

## ⚠️ Para quem for executar a B6.4

Trocar o `except Exception` por `except HTTPException: raise` **não basta nas 4
rotas de fetch**. 📖 `error_handlers.py:48-53` não negocia JSON: um 404 que suba
até o handler global responde **HTML**, e os consumidores em
`detalhes_proposta.html` chamam `.json()` sem condição — o defeito trocaria de
forma em vez de sumir. O plano manda `jsonify` 404 explícito nessas quatro, e o
motivo é este.

## A forma dos testes

A mesma dos lotes c, d e e, com a divergência que o lote d introduziu e este
mantém: a afirmação sobre o **dado** mora em teste verde separado, nunca dentro
de um `xfail(strict=True)` que engoliria a falha dela junto com a do status.

A precondição afirma que **as respostas ao dono e ao estranho diferem** — não que
o dono teve sucesso. Sete das dezoito rotas param logo depois do lookup, numa
validação que uma proposta recém-criada e sem itens não satisfaz, e encená-la
aqui seria testar outra coisa. O par que exige a comparação de corpo é
`alterar_status`, onde as duas respostas são 500 sem flash e só a mensagem do
JSON as separa.
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra blueprints e handlers de evento
from app import app, db
from helpers_tenant import cliente_de, dois_tenants

pytestmark = pytest.mark.integration

INEXISTENTE = 999_999_999

RAZAO = ('B6.4 nunca executada (censo de 01/09) — o 404 de first_or_404 é '
         'engolido por except Exception e vira 302 (14 rotas) ou 500 (4)')

# O 404 que o código escreveu, visto de fora. Werkzeug o serializa assim, e é
# esta string que atravessa o `except Exception` até o flash ou o JSON.
MARCA_DO_404 = '404 Not Found'

# ---------------------------------------------------------------------------
# Os 18 sítios — censo AST conferido por comportamento em 01/09
# ---------------------------------------------------------------------------
# nome: (método, molde). {p} = proposta, {f} = arquivo, {t} = template.

ROTAS = {
    'visualizar': ('GET', '/propostas/{p}'),
    'salvar_observacao_validacao': ('POST', '/propostas/{p}/observacao-validacao'),
    'alterar_status': ('POST', '/propostas/{p}/status'),
    'gerar_pdf': ('GET', '/propostas/{p}/pdf'),
    'editar': ('GET', '/propostas/editar/{p}'),
    'criar_nova_versao': ('POST', '/propostas/{p}/nova-versao'),
    'enviar': ('POST', '/propostas/{p}/enviar'),
    'whatsapp_registrar': ('POST', '/propostas/{p}/whatsapp/registrar'),
    'atualizar': ('POST', '/propostas/editar/{p}'),
    'deletar': ('POST', '/propostas/deletar/{p}'),
    'editar_template': ('GET', '/propostas/templates/{t}/editar'),
    'atualizar_template': ('POST', '/propostas/templates/{t}/atualizar'),
    'marcar_padrao_template': ('POST', '/propostas/templates/{t}/marcar-padrao'),
    'aprovar': ('POST', '/propostas/aprovar/{p}'),
    'rejeitar': ('POST', '/propostas/rejeitar/{p}'),
    'upload_arquivo': ('POST', '/propostas/{p}/upload-arquivo'),
    'download_arquivo': ('GET', '/propostas/arquivo/{f}'),
    'deletar_arquivo': ('POST', '/propostas/arquivo/{f}/delete'),
}

NOMES = sorted(ROTAS)

# As quatro que respondem por fetch, e cujo engolimento vira 500 em vez de 302.
FETCH = ['alterar_status', 'deletar_arquivo', 'upload_arquivo',
         'whatsapp_registrar']


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-b6-404-propostas'
    yield


def _parque(prefixo):
    """A e B, com proposta + arquivo + template semeados **em A**.

    O alvo tem de EXISTIR em A: se a proposta não existisse em lugar nenhum, o
    caso "alheia" e o caso "inexistente" seriam o mesmo teste, e o 404 viria de
    não haver linha — não de haver linha de outra empresa.
    """
    from models import Proposta, PropostaArquivo, PropostaTemplate

    with app.app_context():
        a, b = dois_tenants(prefixo, com_fatos=False)
        proposta = Proposta(numero=f'P-{uuid.uuid4().hex[:8]}',
                            admin_id=a.admin_id, cliente_nome=f'Cliente {a.marca}')
        db.session.add(proposta)
        db.session.flush()
        arquivo = PropostaArquivo(
            admin_id=a.admin_id, proposta_id=proposta.id,
            nome_arquivo=f'{uuid.uuid4().hex[:8]}.pdf', nome_original='anexo.pdf',
            caminho_arquivo='/tmp/nao-existe.pdf')
        db.session.add(arquivo)
        template = PropostaTemplate(nome=f'Template {uuid.uuid4().hex[:6]}',
                                    admin_id=a.admin_id, categoria='geral')
        db.session.add(template)
        db.session.commit()
        return {
            'admin_a': a.admin_id, 'admin_b': b.admin_id,
            'proposta_id': proposta.id, 'arquivo_id': arquivo.id,
            'ids': {'p': proposta.id, 'f': arquivo.id, 't': template.id},
        }


def _bater(admin_id, nome, ids):
    """Dispara a rota e devolve (status, flashes, texto completo).

    Junta flash e corpo de propósito: nas 14 rotas de tela o 404 engolido sai no
    flash, nas 4 de fetch sai no JSON. É a mesma evidência em dois envelopes, e
    o teste não deve precisar saber em qual delas está.
    """
    metodo, molde = ROTAS[nome]
    cliente = cliente_de(admin_id)
    resposta = cliente.open(molde.format(**ids), method=metodo)
    with cliente.session_transaction() as sessao:
        avisos = [msg for _categoria, msg in sessao.get('_flashes', [])]
    texto = resposta.get_data(as_text=True) + ' '.join(avisos)
    return resposta.status_code, avisos, texto


def _ids_inexistentes(_ids):
    return {'p': INEXISTENTE, 'f': INEXISTENTE, 't': INEXISTENTE}


# ---------------------------------------------------------------------------
# 1. Precondição — o dono passa do lookup
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('nome', NOMES)
def test_o_dono_e_o_estranho_recebem_respostas_diferentes_precondicao(nome):
    """A guarda de tenant **faz alguma coisa** nesta rota.

    Sem esta afirmação, um `xfail` que estourasse no andaime — proposta semeada
    sem o campo que a rota exige, decorator barrando antes do lookup — contaria
    como defeito confirmado, e `xfail(strict=True)` não distingue os motivos.

    A afirmação é "as duas respostas diferem", e não "o dono teve sucesso": sete
    das dezoito rotas param logo depois do lookup, numa validação que uma
    proposta recém-criada e sem itens não satisfaz. Encená-la aqui seria testar
    outra coisa. E não é "o dono não vê a marca do 404" porque em
    `salvar_observacao_validacao` a marca não aparece para ninguém — ali a
    versão-marca passaria com o andaime quebrado.
    """
    parque = _parque(f'b6prop_pre_{nome[:10]}')

    dono = _bater(parque['admin_a'], nome, parque['ids'])
    estranho = _bater(parque['admin_b'], nome, parque['ids'])

    assert dono != estranho, (
        f'{nome} responde EXATAMENTE o mesmo ao dono e ao estranho '
        f'(status {dono[0]}, flash {dono[1]}) — ou a rota não chega ao lookup '
        f'de tenant, ou o andaime deste sítio está quebrado; de qualquer modo '
        f'os xfail abaixo mediriam isso, e não o 404 que falta')


# ---------------------------------------------------------------------------
# 2. O dado de A sobrevive à tentativa de B — verde, e fora de qualquer xfail
# ---------------------------------------------------------------------------

def test_a_proposta_alheia_nao_e_excluida():
    """🔴 `deletar` recusa de verdade, não só no status."""
    from models import Proposta

    parque = _parque('b6prop_del')
    _bater(parque['admin_b'], 'deletar', parque['ids'])

    with app.app_context():
        assert db.session.get(Proposta, parque['proposta_id']) is not None, (
            '🔴 a proposta de outra empresa foi excluída — isto é bem pior que '
            'o 404 que falta')


@pytest.mark.parametrize('nome', ['alterar_status', 'aprovar', 'rejeitar'])
def test_o_status_da_proposta_alheia_nao_muda(nome):
    """🔴 Aprovar/rejeitar proposta de outra empresa muda o que ela cobra."""
    from models import Proposta

    parque = _parque(f'b6prop_st_{nome[:8]}')
    with app.app_context():
        antes = db.session.get(Proposta, parque['proposta_id']).status

    _bater(parque['admin_b'], nome, parque['ids'])

    with app.app_context():
        depois = db.session.get(Proposta, parque['proposta_id']).status
    assert depois == antes, (
        f'🔴 B mudou o status da proposta de A por {nome}: {antes} → {depois}')


def test_o_arquivo_alheio_nao_e_excluido():
    from models import PropostaArquivo

    parque = _parque('b6prop_arq')
    _bater(parque['admin_b'], 'deletar_arquivo', parque['ids'])

    with app.app_context():
        assert db.session.get(PropostaArquivo, parque['arquivo_id']) is not None, (
            '🔴 o anexo da proposta de outra empresa foi excluído')


def test_nenhuma_versao_nasce_na_proposta_alheia():
    """`criar_nova_versao` clona a proposta. B não pode disparar o clone de A."""
    from models import Proposta

    parque = _parque('b6prop_ver')
    with app.app_context():
        antes = Proposta.query.filter_by(admin_id=parque['admin_a']).count()

    _bater(parque['admin_b'], 'criar_nova_versao', parque['ids'])

    with app.app_context():
        depois = Proposta.query.filter_by(admin_id=parque['admin_a']).count()
    assert depois == antes, (
        f'🔴 B criou {depois - antes} versão(ões) dentro do tenant de A')


# ---------------------------------------------------------------------------
# 3. Ausência de oráculo — verde hoje, e o fix tem de mantê-la assim
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('nome', NOMES)
def test_alheia_e_inexistente_respondem_o_mesmo(nome):
    """As duas recusas são indistinguíveis — status e flash.

    Verde hoje, e por um acidente feliz: o `except Exception` esmaga os dois
    casos na mesma mensagem. O fix é justamente o momento de perder isso, ao
    escrever "proposta de outra empresa" num ramo e "não existe" no outro.
    """
    parque = _parque(f'b6prop_orac_{nome[:9]}')

    s_alheia, aviso_alheia, _t = _bater(parque['admin_b'], nome, parque['ids'])
    s_inex, aviso_inex, _t2 = _bater(parque['admin_b'], nome,
                                     _ids_inexistentes(parque['ids']))

    assert s_alheia == s_inex, (
        f'{nome} distingue alheia ({s_alheia}) de inexistente ({s_inex}) no '
        f'status')
    assert aviso_alheia == aviso_inex, (
        f'{nome} distingue as duas no texto que o usuário lê: {aviso_alheia} × '
        f'{aviso_inex} — isto é um oráculo de enumeração')


# ---------------------------------------------------------------------------
# 4. O 404 que existe e não chega — xfail(strict=True), só sobre o status
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason=RAZAO)
@pytest.mark.parametrize('nome', NOMES)
def test_proposta_de_outro_tenant_da_404(nome):
    parque = _parque(f'b6prop_alh_{nome[:10]}')

    status, avisos, texto = _bater(parque['admin_b'], nome, parque['ids'])
    engoliu = MARCA_DO_404 in texto

    assert status == 404, (
        f'{nome} respondeu {status} para recurso de outra empresa; o 404 '
        f'{"foi engolido e reaparece no texto" if engoliu else "sumiu"}: '
        f'{avisos}')


@pytest.mark.xfail(strict=True, reason=RAZAO)
@pytest.mark.parametrize('nome', NOMES)
def test_recurso_inexistente_da_404(nome):
    parque = _parque(f'b6prop_inex_{nome[:9]}')

    status, avisos, texto = _bater(parque['admin_b'], nome,
                                   _ids_inexistentes(parque['ids']))
    engoliu = MARCA_DO_404 in texto

    assert status == 404, (
        f'{nome} respondeu {status} para recurso inexistente; o 404 '
        f'{"foi engolido e reaparece no texto" if engoliu else "sumiu"}: '
        f'{avisos}')


@pytest.mark.xfail(strict=True, reason=RAZAO)
@pytest.mark.parametrize('nome', FETCH)
def test_a_rota_de_fetch_nao_conta_recusa_como_erro_de_servidor(nome):
    """🔴 As quatro de fetch respondem **500**, não 302.

    Vale um teste próprio porque o custo é de outra natureza: 302 no lugar de
    404 é semântica errada; 500 é a aplicação declarando que ela própria
    falhou. Todo painel que acompanhe taxa de 5xx passa a contar recusa de
    isolamento entre empresas como incidente — e o dia em que houver um
    incidente de verdade, ele estará no meio deste ruído.
    """
    parque = _parque(f'b6prop_5xx_{nome[:9]}')

    status, _avisos, texto = _bater(parque['admin_b'], nome, parque['ids'])
    engoliu = MARCA_DO_404 in texto

    assert status < 500, (
        f'{nome} respondeu {status} para recurso de outra empresa, com o '
        f'{MARCA_DO_404} {"dentro do corpo" if engoliu else "ausente"}')
