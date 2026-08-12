"""Exportação do cronograma em PDF — a planilha de tarefas no papel timbrado.

Spec: `docs/superpowers/specs/2026-08-12-cronograma-pdf-layout-veks-design.md`.

Três camadas, e a do meio é a que importa:

1. **dados** (`montar_linhas_cronograma`) — numeração, ordem, marco,
   arquivada, isolamento entre o cronograma interno e a cópia-cliente;
2. **paridade com a tela** — o percentual de cada linha do PDF contra o
   percentual da célula correspondente na GRADE RENDERIZADA. A comparação é
   contra o HTML de verdade, e não contra as funções que o próprio PDF chama:
   comparar o PDF com `progresso_geral_cliente` provaria só que uma função é
   igual a si mesma. É este teste que trava a extração da fórmula para
   `utils/cronograma_engine`;
3. **arquivo e rota** — bytes de PDF válido, obra vazia, autorização.

NOTA de harness (mesma disciplina das suítes vizinhas de cronograma):
requests do test client ficam FORA de app_context aberto — Flask-Login
cacheia `g._login_user` e congela o primeiro usuário resolvido. Todo teste
captura IDs (int) dentro do contexto e só depois faz o request.
"""
import os
import re
import sys
import uuid
from contextlib import contextmanager
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: F401 — registra os blueprints
from app import app, db
from models import (Cliente, ConfiguracaoEmpresa, Obra, PapelObra,
                    TarefaCronograma, TipoUsuario, Usuario, UsuarioObra)

pytestmark = pytest.mark.integration

def _png_valido_b64() -> str:
    """PNG real em base64, gerado na hora pelo PIL.

    O blob "1x1 transparente" que estava aqui tinha o checksum do IDAT
    quebrado: `Image.open` engolia e o `ImageReader` da reportlab recusava, o
    que fazia o caminho da logo cair no fallback SEM falhar teste nenhum. A
    validação do timbre (`Image.verify`) é que expôs isso.
    """
    import base64
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (8, 4), (22, 41, 74)).save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('ascii')


PNG_MINIMO_B64 = _png_valido_b64()


@pytest.fixture(autouse=True)
def _config():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    if not app.secret_key:
        app.secret_key = 'test-cronograma-pdf'
    yield


def _suf() -> str:
    return uuid.uuid4().hex[:10]


def _http(user_id: int):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


@contextmanager
def _escopo_ligado(admin_id: int):
    """Liga `escopo_obra_ativo` e SEMPRE religa desligada ao sair.

    Recebe `admin_id` (int) e não o objeto: fora do app_context em que foi
    carregado ele está detached, e ler `.id` levantaria
    DetachedInstanceError — o teardown nunca rodaria e a flag ficaria ligada
    para as suítes seguintes. Mesma disciplina de
    `tests/test_cronograma_rbac_fase1.py`.
    """
    from scripts.flag_escopo_obra import definir_flag
    with app.app_context():
        definir_flag(admin_id, True)
    try:
        yield
    finally:
        with app.app_context():
            definir_flag(admin_id, False)


def _apontar(obra_id, admin_id, tarefa, pct):
    """RDO com apontamento na tarefa — o que faz o percentual SOBREVIVER.

    Sem isto a fixture seria inútil para o teste de paridade:
    `sincronizar_percentuais_obra` (que a tela e o PDF rodam antes de exibir)
    zera a folha sem apontamento — `utils/cronograma_engine.py:450`,
    `if ultimo is None: tarefa.percentual_concluido = 0.0`. Os dois lados
    ficariam em zero e a comparação passaria sem provar nada.
    """
    from models import RDO, RDOApontamentoCronograma

    rdo = RDO(numero_rdo=f'RDO-{uuid.uuid4().hex[:12]}',
              data_relatorio=date(2026, 7, 10), obra_id=obra_id,
              admin_id=admin_id)
    db.session.add(rdo)
    db.session.flush()
    db.session.add(RDOApontamentoCronograma(
        rdo_id=rdo.id, tarefa_cronograma_id=tarefa.id,
        quantidade_executada_dia=pct, quantidade_acumulada=pct,
        percentual_realizado=pct, admin_id=admin_id))
    db.session.flush()


def _tarefa(obra_id, admin_id, nome, *, ordem=0, pai_id=None, dur=5,
            inicio=date(2026, 7, 1), fim=date(2026, 7, 7), perc=0.0,
            cliente=False, marco=False, ativa=True):
    t = TarefaCronograma(
        obra_id=obra_id, admin_id=admin_id, nome_tarefa=nome, ordem=ordem,
        tarefa_pai_id=pai_id, duracao_dias=dur, data_inicio=inicio,
        data_fim=fim, percentual_concluido=perc, is_cliente=cliente,
        is_marco=marco, ativa=ativa,
    )
    db.session.add(t)
    db.session.flush()
    return t


def _cenario(*, com_logo=False, papel=None, com_config=True):
    """admin V2 + obra + árvore de três níveis + marco + arquivada.

    Estrutura montada (a ordem visual esperada é esta, e é o que a numeração
    sequencial do PDF tem de reproduzir):

        1  OBRA (raiz, sem pai)
        2    Fundação            (pai)
        3      Escavação
        4      Radier
        5    Estrutura           (pai)
        6      Pilares
        7    Liberação do vidro  (marco)

    Mais uma tarefa arquivada, que não pode aparecer em lugar nenhum.
    """
    with app.app_context():
        suf = _suf()
        admin = Usuario(
            username=f'cpd_{suf}', email=f'cpd_{suf}@test.local',
            nome=f'Adm PDF {suf}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.ADMIN, ativo=True, versao_sistema='v2',
        )
        db.session.add(admin)
        db.session.commit()

        func = Usuario(
            username=f'cpf_{suf}', email=f'cpf_{suf}@test.local',
            nome=f'Fun PDF {suf}',
            password_hash=generate_password_hash('Senha@2026'),
            tipo_usuario=TipoUsuario.FUNCIONARIO, ativo=True,
            admin_id=admin.id,
        )
        db.session.add(func)

        if com_config:
            db.session.add(ConfiguracaoEmpresa(
                admin_id=admin.id, nome_empresa=f'Construtora {suf}',
                cnpj='42.547.087/0001-61',
                endereco='Rua Aparecida do Norte, 45 — São José dos Campos/SP',
                website='veksengenharia.com',
                logo_pdf_base64=(PNG_MINIMO_B64 if com_logo else None),
            ))

        cliente = Cliente(nome=f'Cliente PDF {suf}', admin_id=admin.id)
        db.session.add(cliente)
        db.session.flush()
        obra = Obra(nome=f'Obra PDF {suf}', codigo=f'PD-{suf[:8].upper()}',
                    admin_id=admin.id, cliente_id=cliente.id,
                    data_inicio=date(2026, 7, 1))
        db.session.add(obra)
        db.session.flush()

        raiz = _tarefa(obra.id, admin.id, 'OBRA', ordem=0, dur=40, perc=10.0)
        fund = _tarefa(obra.id, admin.id, 'Fundação', ordem=1, pai_id=raiz.id,
                       dur=20, perc=100.0)
        escav = _tarefa(obra.id, admin.id, 'Escavação', ordem=2, pai_id=fund.id,
                        dur=10, perc=100.0)
        radier = _tarefa(obra.id, admin.id, 'Radier', ordem=3, pai_id=fund.id,
                         dur=10, perc=100.0)
        estr = _tarefa(obra.id, admin.id, 'Estrutura', ordem=4, pai_id=raiz.id,
                       dur=20, perc=40.0)
        pilares = _tarefa(obra.id, admin.id, 'Pilares', ordem=5,
                          pai_id=estr.id, dur=20, perc=40.0)
        # Apontamentos de RDO nas FOLHAS, com valores distintos entre si: é o
        # que sobrevive ao sync e dá dentes ao teste de paridade. O 40,6 de
        # Pilares é deliberado — a tela trunca para 40 (`|int`) e é
        # exatamente esse caso que uma formatação arredondada quebraria.
        _apontar(obra.id, admin.id, escav, 100.0)
        _apontar(obra.id, admin.id, radier, 75.0)
        _apontar(obra.id, admin.id, pilares, 40.6)
        _tarefa(obra.id, admin.id, 'Liberação do vidro', ordem=6,
                pai_id=raiz.id, dur=0, marco=True, fim=None, perc=0.0)
        _tarefa(obra.id, admin.id, 'Etapa removida na reimportação', ordem=7,
                pai_id=raiz.id, ativa=False, perc=99.0)

        if papel is not None:
            db.session.add(UsuarioObra(usuario_id=func.id, obra_id=obra.id,
                                       papel=papel, admin_id=admin.id))
        db.session.commit()
        return {'admin_id': admin.id, 'user_id': func.id, 'obra_id': obra.id}


def _cenario_cliente():
    """Cenário com a CÓPIA-CLIENTE povoada, com percentuais diferentes do
    plano interno — para que uma troca de população apareça como número
    errado, e não como coincidência."""
    ctx = _cenario()
    with app.app_context():
        raiz = _tarefa(ctx['obra_id'], ctx['admin_id'], 'OBRA (cliente)',
                       ordem=0, dur=30, perc=5.0, cliente=True)
        _tarefa(ctx['obra_id'], ctx['admin_id'], 'Etapa 1 do cliente',
                ordem=1, pai_id=raiz.id, dur=15, perc=70.0, cliente=True)
        _tarefa(ctx['obra_id'], ctx['admin_id'], 'Etapa 2 do cliente',
                ordem=2, pai_id=raiz.id, dur=15, perc=30.0, cliente=True)
        db.session.commit()
    return ctx


def _dados(ctx, *, cliente=False):
    from services.cronograma_pdf import montar_linhas_cronograma
    with app.app_context():
        return montar_linhas_cronograma(ctx['obra_id'], ctx['admin_id'],
                                        cliente=cliente)


def _pdf(ctx, *, cliente=False):
    from services.cronograma_pdf import (exportar_cronograma_pdf,
                                         montar_linhas_cronograma,
                                         montar_marca_tenant)
    with app.app_context():
        dados = montar_linhas_cronograma(ctx['obra_id'], ctx['admin_id'],
                                         cliente=cliente)
        return exportar_cronograma_pdf(dados, montar_marca_tenant(
            ctx['admin_id']))


def _paginas(pdf: bytes) -> int:
    """Conta páginas pelos objetos do PDF.

    O repositório não tem `pypdf`, e a reportlab não usa object streams por
    padrão — os dicionários `/Type /Page` ficam legíveis nos bytes.
    `/Type /Pages` (o nó da árvore) é descontado.
    """
    return pdf.count(b'/Type /Page') - pdf.count(b'/Type /Pages')


# ═════════════════════════════════════════════════════════════════════════════
# 1. DADOS
# ═════════════════════════════════════════════════════════════════════════════

def test_numeracao_sequencial_na_ordem_visual_da_arvore():
    """A coluna `#` é 1..N na ordem do flatten, como a grade da tela.

    Não é EDT hierárquica (1, 1.1, 1.2): é o mesmo número que a coluna
    `Pred.` referencia.
    """
    dados = _dados(_cenario())
    nomes = [ln['nome'] for ln in dados['linhas']]
    assert nomes == ['OBRA', 'Fundação', 'Escavação', 'Radier',
                     'Estrutura', 'Pilares', 'Liberação do vidro']
    assert [ln['numero'] for ln in dados['linhas']] == [1, 2, 3, 4, 5, 6, 7]


def test_ordem_e_niveis_batem_com_ordenar_arvore_visual():
    """A fonte única da ordem visual é o motor — o PDF não reordena nada."""
    from utils.cronograma_engine import ordenar_arvore_visual

    ctx = _cenario()
    dados = _dados(ctx)
    with app.app_context():
        brutas = (TarefaCronograma.query
                  .filter_by(obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
                             is_cliente=False)
                  .filter(TarefaCronograma.ativa.is_(True))
                  .order_by(TarefaCronograma.ordem).all())
        esperadas, niveis = ordenar_arvore_visual(brutas, com_nivel=True)
        nomes_esperados = [t.nome_tarefa for t in esperadas]
        niveis_esperados = [niveis[t.id] for t in esperadas]

    assert [ln['nome'] for ln in dados['linhas']] == nomes_esperados
    assert [ln['nivel'] for ln in dados['linhas']] == niveis_esperados
    assert niveis_esperados == [0, 1, 2, 2, 1, 2, 1]


def test_pai_e_marco_sao_marcados():
    """`is_pai` alimenta o negrito; `is_marco`, o losango e o traço."""
    linhas = {ln['nome']: ln for ln in _dados(_cenario())['linhas']}
    assert linhas['OBRA']['is_pai'] is True
    assert linhas['Fundação']['is_pai'] is True
    assert linhas['Escavação']['is_pai'] is False
    assert linhas['Liberação do vidro']['is_marco'] is True
    assert linhas['Fundação']['is_marco'] is False


def test_marco_sai_sem_duracao_e_sem_percentual():
    """Decisão de layout do spec: no documento do cliente, marco não finge ter
    andamento parcial nem duração. A tela mostra o número; o papel, `—`."""
    from services.cronograma_pdf import _duracao, _percentual_celula
    linhas = {ln['nome']: ln for ln in _dados(_cenario())['linhas']}
    marco = linhas['Liberação do vidro']
    assert _duracao(marco) == '—'
    assert _percentual_celula(marco) == '—'
    # A linha comum mostra número, não travessão. O VALOR não é afirmado aqui
    # de propósito: `montar_linhas_cronograma` roda
    # `sincronizar_percentuais_obra` (como a tela faz), e o percentual da
    # folha passa a vir do RDO. Quem trava o arredondamento é
    # `test_percentual_da_celula_trunca_como_a_grade`, que não toca no banco.
    comum = linhas['Escavação']
    assert _duracao(comum) == '10d'
    assert _percentual_celula(comum).endswith('%')
    assert _percentual_celula(comum) != '—'


def test_percentual_da_celula_trunca_como_a_grade():
    """40,6% aparece como 40 na tela (`|int`), e tem de aparecer 40 no papel.

    Arredondar aqui daria 41 — divergência pequena, do tipo que faz alguém
    conferir a soma três vezes. A raiz é a exceção: uma casa decimal, como
    `"%.1f"|format(progresso_geral_header)` na grade.
    """
    from services.cronograma_pdf import _percentual_celula
    assert _percentual_celula({'percentual': 40.6, 'is_raiz': False}) == '40%'
    assert _percentual_celula({'percentual': 40.6, 'is_raiz': True}) == '40.6%'
    assert _percentual_celula({'percentual': 0, 'is_raiz': False}) == '0%'
    assert _percentual_celula({'percentual': None, 'is_raiz': False}) == '0%'


def test_marco_por_duracao_zero_sem_flag_tambem_conta():
    """Duração zero é marco pelo spec M06 §4.2, mesmo sem `is_marco`.

    O PDF reusa `_is_marco_efetivo` do motor em vez de reimplementar a regra,
    justamente para não ficar atrás dela.
    """
    ctx = _cenario()
    with app.app_context():
        raiz = (TarefaCronograma.query
                .filter_by(obra_id=ctx['obra_id'], nome_tarefa='OBRA').first())
        _tarefa(ctx['obra_id'], ctx['admin_id'], 'Entrega sem flag', ordem=8,
                pai_id=raiz.id, dur=0, marco=False)
        db.session.commit()

    linhas = {ln['nome']: ln for ln in _dados(ctx)['linhas']}
    assert linhas['Entrega sem flag']['is_marco'] is True


def test_tarefa_arquivada_fica_fora():
    """Reimportação arquiva em vez de deletar (M05); o PDF não a mostra."""
    nomes = [ln['nome'] for ln in _dados(_cenario())['linhas']]
    assert 'Etapa removida na reimportação' not in nomes


def test_modo_cliente_le_a_copia_cliente_e_nao_vaza_o_plano_interno():
    ctx = _cenario_cliente()
    nomes = [ln['nome'] for ln in _dados(ctx, cliente=True)['linhas']]
    assert nomes == ['OBRA (cliente)', 'Etapa 1 do cliente',
                     'Etapa 2 do cliente']
    assert 'Fundação' not in nomes


def test_modo_interno_nao_puxa_a_copia_cliente():
    """O inverso do teste acima: as duas populações não se misturam."""
    ctx = _cenario_cliente()
    nomes = [ln['nome'] for ln in _dados(ctx, cliente=False)['linhas']]
    assert 'OBRA (cliente)' not in nomes
    assert 'Etapa 1 do cliente' not in nomes
    assert nomes[0] == 'OBRA'


def test_cabecalho_leva_periodo_cliente_e_progresso():
    dados = _dados(_cenario())
    obra = dados['obra']
    assert obra['data_inicio'] == date(2026, 7, 1)
    assert obra['data_fim'] == date(2026, 7, 7)
    assert obra['cliente'].startswith('Cliente PDF')
    assert isinstance(obra['progresso_geral'], float)
    assert obra['modo_cliente'] is False


def test_obra_sem_tarefa_devolve_linhas_vazias_e_nao_erro():
    ctx = _cenario()
    with app.app_context():
        TarefaCronograma.query.filter_by(obra_id=ctx['obra_id']).delete()
        db.session.commit()
    dados = _dados(ctx)
    assert dados['linhas'] == []
    assert dados['obra']['data_inicio'] is None


def test_obra_de_outro_tenant_nao_e_montada():
    """`montar_linhas_cronograma` filtra por tenant antes de qualquer leitura."""
    from services.cronograma_pdf import montar_linhas_cronograma

    a, b = _cenario(), _cenario()
    with app.app_context():
        with pytest.raises(ValueError):
            montar_linhas_cronograma(a['obra_id'], b['admin_id'])


# ═════════════════════════════════════════════════════════════════════════════
# 2. PARIDADE COM A TELA — o guarda central
# ═════════════════════════════════════════════════════════════════════════════

def _percentuais_da_grade(html: str) -> list:
    """O texto da célula de % REALIZADO de cada linha da grade renderizada.

    Devolve o texto como está — `'63.4'`, `'100'` —, sem converter para
    float: a comparação é entre o que a tela MOSTRA e o que o papel MOSTRA, e
    a diferença entre `40` e `40.6` é justamente o que interessa flagrar.

    A âncora é a classe de COR, e não `perc-text` sozinha, porque a coluna
    **Planejado** usa a mesma `perc-text`
    (`templates/obras/cronograma.html:368`, com `text-secondary`): sem o
    recorte, cada linha entraria duas vezes e a comparação seria contra a
    coluna errada. O Realizado é sempre uma das três cores de estado
    (`:397`), e isso funciona como canário — se o esquema de classes mudar,
    este teste falha alto em vez de comparar a coluna vizinha em silêncio.

    Linha de tarefa com `responsavel='terceiros'` renderiza checkbox em vez
    de percentual (`:375`) e não aparece aqui; a fixture não tem nenhuma.

    Ler o HTML — e não as funções que o PDF também chama — é o que faz deste
    um teste de paridade e não uma tautologia.
    """
    return re.findall(
        r'class="perc-text text-(?:success|warning|danger)"[^>]*>'
        r'([\d.]+)%</span>', html)


def test_percentual_de_cada_linha_bate_com_a_grade_da_tela():
    """O papel não pode dizer um número e a tela outro (cronograma interno).

    Comparação linha a linha do TEXTO EXIBIDO, contra o HTML renderizado —
    incluindo o arredondamento: a grade trunca as linhas comuns para inteiro e
    formata a raiz com uma casa decimal, e o PDF copia os dois. Se alguém
    mexer na regra de um dos lados — inclusive "arrumando" a linha-raiz —,
    este teste aponta qual linha divergiu.

    Os valores esperados na fixture, e por que cada um tem dentes: raiz em
    `64.0` (uma casa), Fundação em `87` (rollup de 100 e 75, truncado de
    87,5), Pilares em `40` (apontado 40,6 — o caso que uma formatação
    arredondada mandaria para 41).

    Só o modo interno: no modo cliente a exportação deliberadamente NÃO roda
    o sync que a tela roda, porque aquele sync destrói dado — ver
    `test_exportar_o_cronograma_cliente_nao_escreve_no_banco`.

    O marco fica fora da comparação: a tela mostra o número e o PDF mostra
    `—`, decisão de layout do spec, coberta por
    `test_marco_sai_sem_duracao_e_sem_percentual`.
    """
    ctx = _cenario_cliente()
    r = _http(ctx['admin_id']).get(f"/cronograma/obra/{ctx['obra_id']}")
    assert r.status_code == 200
    da_tela = _percentuais_da_grade(r.get_data(as_text=True))

    from services.cronograma_pdf import _percentual_celula
    linhas = _dados(ctx, cliente=False)['linhas']

    assert da_tela, 'a grade não renderizou percentual nenhum'
    assert len(da_tela) == len(linhas), (
        f'tela tem {len(da_tela)} linhas, PDF tem {len(linhas)}')
    # Guarda contra o teste virar vácuo: se o sync zerar tudo (folha sem
    # apontamento vira 0), a comparação passaria comparando zeros.
    assert any(t not in ('0', '0.0') for t in da_tela), (
        f'todos os percentuais vieram zerados: {da_tela}')

    for texto_tela, ln in zip(da_tela, linhas):
        if ln['is_marco']:
            continue
        do_papel = _percentual_celula(ln).rstrip('%')
        assert do_papel == texto_tela, (
            f"linha {ln['numero']} ({ln['nome']}): tela mostra "
            f"{texto_tela}%, papel mostra {do_papel}%")


def test_exportar_o_cronograma_cliente_nao_escreve_no_banco():
    """Uma exportação não muta dado — e aqui a regra tem consequência séria.

    `sincronizar_percentuais_obra(cliente=True)` promete no docstring "apenas
    recalcula bottom-up dos pais", mas o laço do RDO roda igual: a cópia-
    cliente nunca tem apontamento (o RDO aponta só no plano interno), então
    cada folha recebe `0.0` e a função comita
    (`utils/cronograma_engine.py:551`). Se o serviço de PDF chamasse esse
    sync — como a tela chama, num GET —, baixar o cronograma do cliente
    APAGARIA o plano combinado com ele.

    Este teste é o guarda: percentual gravado antes e depois da exportação,
    byte a byte igual, e o PDF lendo os valores como estão (70/30 nas folhas,
    50 no pai por rollup em memória).
    """
    ctx = _cenario_cliente()
    with app.app_context():
        antes = {t.nome_tarefa: t.percentual_concluido
                 for t in TarefaCronograma.query.filter_by(
                     obra_id=ctx['obra_id'], is_cliente=True).all()}
    assert antes == {'OBRA (cliente)': 5.0, 'Etapa 1 do cliente': 70.0,
                     'Etapa 2 do cliente': 30.0}

    dados = _dados(ctx, cliente=True)
    assert _pdf(ctx, cliente=True)[:5] == b'%PDF-'

    with app.app_context():
        depois = {t.nome_tarefa: t.percentual_concluido
                  for t in TarefaCronograma.query.filter_by(
                      obra_id=ctx['obra_id'], is_cliente=True).all()}
    assert depois == antes, 'a exportação escreveu no banco'

    por_nome = {ln['nome']: ln['percentual'] for ln in dados['linhas']}
    assert por_nome['Etapa 1 do cliente'] == 70.0
    assert por_nome['Etapa 2 do cliente'] == 30.0
    # Raiz: progresso geral (média das folhas ponderada por duração) = 50.
    assert por_nome['OBRA (cliente)'] == 50.0


def test_rollup_dos_pais_no_modo_cliente_e_feito_em_memoria():
    """Pai intermediário agrega as filhas sem que nada disso vá ao banco."""
    ctx = _cenario_cliente()
    with app.app_context():
        raiz = (TarefaCronograma.query
                .filter_by(obra_id=ctx['obra_id'], is_cliente=True,
                           nome_tarefa='OBRA (cliente)').first())
        etapa = (TarefaCronograma.query
                 .filter_by(obra_id=ctx['obra_id'], is_cliente=True,
                            nome_tarefa='Etapa 1 do cliente').first())
        etapa.percentual_concluido = 0.0  # valor gravado, deliberadamente errado
        _tarefa(ctx['obra_id'], ctx['admin_id'], 'Serviço A', ordem=10,
                pai_id=etapa.id, dur=10, perc=90.0, cliente=True)
        _tarefa(ctx['obra_id'], ctx['admin_id'], 'Serviço B', ordem=11,
                pai_id=etapa.id, dur=10, perc=10.0, cliente=True)
        db.session.commit()
        assert raiz is not None

    por_nome = {ln['nome']: ln['percentual']
                for ln in _dados(ctx, cliente=True)['linhas']}
    # 90 e 10 com pesos iguais → o pai mostra 50, e não o 0 gravado.
    assert por_nome['Etapa 1 do cliente'] == 50.0

    with app.app_context():
        etapa = (TarefaCronograma.query
                 .filter_by(obra_id=ctx['obra_id'], is_cliente=True,
                            nome_tarefa='Etapa 1 do cliente').first())
        assert etapa.percentual_concluido == 0.0, (
            'o rollup do modo cliente gravou no banco')


@pytest.mark.parametrize('cliente', [False, True],
                         ids=['interno', 'cliente'])
def test_linha_raiz_sai_com_o_progresso_geral_nos_dois_modos(cliente):
    """A regra da linha-raiz vale nos dois modos — o referente é a GRADE.

    A grade (`templates/obras/cronograma.html:220` e `:397`) sobrescreve a
    linha sem pai com `progresso_geral_header` sempre que ele não é None, o
    que depois da p4 é sempre. O array das barras do Gantt só faz isso no
    modo interno, e essa discordância é da tela — o PDF é tabela e segue a
    tabela.
    """
    ctx = _cenario_cliente()
    dados = _dados(ctx, cliente=cliente)
    raiz = dados['linhas'][0]
    assert raiz['nivel'] == 0
    assert round(raiz['percentual'], 1) == round(
        dados['obra']['progresso_geral'], 1)


def test_progresso_geral_bate_com_o_card_da_tela():
    """O número da faixa de metadados é o mesmo do card "Progresso Geral"."""
    ctx = _cenario()
    r = _http(ctx['admin_id']).get(f"/cronograma/obra/{ctx['obra_id']}")
    html = r.get_data(as_text=True)
    m = re.search(r'id="statPercGeral"[^>]*>([\d.]+)%', html)
    assert m, 'card de progresso geral não encontrado na tela'
    assert round(_dados(ctx)['obra']['progresso_geral'], 1) == float(m.group(1))


def test_progresso_geral_cliente_e_a_media_ponderada_por_duracao():
    """A fórmula extraída para o motor, conferida por conta feita à mão.

    Folhas da cópia-cliente: 70% com peso 15 e 30% com peso 15 → 50,0. A raiz
    é pai (tem filhas na lista) e por isso não entra na média.
    """
    from utils.cronograma_engine import progresso_geral_cliente

    ctx = _cenario_cliente()
    with app.app_context():
        tarefas = (TarefaCronograma.query
                   .filter_by(obra_id=ctx['obra_id'], admin_id=ctx['admin_id'],
                              is_cliente=True)
                   .order_by(TarefaCronograma.ordem).all())
        assert progresso_geral_cliente(tarefas) == 50.0
        assert progresso_geral_cliente([]) == 0.0


# ═════════════════════════════════════════════════════════════════════════════
# 3. ARQUIVO
# ═════════════════════════════════════════════════════════════════════════════

def test_pdf_e_um_pdf_de_verdade():
    pdf = _pdf(_cenario(com_logo=True))
    assert pdf[:5] == b'%PDF-'
    assert len(pdf) > 2000
    assert _paginas(pdf) == 1


def test_obra_vazia_gera_pdf_de_uma_pagina_com_aviso():
    """Sem tarefa, um PDF que DIZ isso — não 500, não arquivo de zero byte."""
    ctx = _cenario()
    with app.app_context():
        TarefaCronograma.query.filter_by(obra_id=ctx['obra_id']).delete()
        db.session.commit()
    pdf = _pdf(ctx)
    assert pdf[:5] == b'%PDF-'
    assert _paginas(pdf) == 1


def test_cronograma_longo_pagina_sozinho():
    """`LongTable(repeatRows=1)` quebra e repete o cabeçalho sem ajuda."""
    ctx = _cenario()
    with app.app_context():
        raiz = (TarefaCronograma.query
                .filter_by(obra_id=ctx['obra_id'], nome_tarefa='OBRA').first())
        for i in range(140):
            _tarefa(ctx['obra_id'], ctx['admin_id'],
                    f'Serviço de campo número {i} com nome longo o bastante '
                    f'para ocupar a coluna inteira', ordem=100 + i,
                    pai_id=raiz.id, dur=3, perc=float(i % 101))
        db.session.commit()
    pdf = _pdf(ctx)
    assert _paginas(pdf) >= 3


def test_marca_do_tenant_sai_do_cadastro():
    from services.cronograma_pdf import montar_marca_tenant
    ctx = _cenario(com_logo=True)
    with app.app_context():
        marca = montar_marca_tenant(ctx['admin_id'])
    assert marca['nome'].startswith('Construtora')
    assert marca['cnpj'] == '42.547.087/0001-61'
    assert marca['logo'] is not None


def test_tenant_sem_logo_gera_pdf_com_o_nome_em_texto():
    from services.cronograma_pdf import montar_marca_tenant
    ctx = _cenario(com_logo=False)
    with app.app_context():
        assert montar_marca_tenant(ctx['admin_id'])['logo'] is None
    assert _pdf(ctx)[:5] == b'%PDF-'


def test_tenant_sem_configuracao_nao_quebra():
    from services.cronograma_pdf import montar_marca_tenant
    ctx = _cenario(com_config=False)
    with app.app_context():
        marca = montar_marca_tenant(ctx['admin_id'])
    assert marca['nome'] == 'Empresa'
    assert marca['logo'] is None
    assert _pdf(ctx)[:5] == b'%PDF-'


def test_logo_com_base64_corrompido_degrada_em_vez_de_derrubar():
    """Cadastro com logo inválida não pode impedir o download do cronograma."""
    from services.cronograma_pdf import montar_marca_tenant
    ctx = _cenario(com_logo=True)
    with app.app_context():
        config = ConfiguracaoEmpresa.query.filter_by(
            admin_id=ctx['admin_id']).first()
        config.logo_pdf_base64 = 'isto-nao-e-base64-!!!'
        config.logo_base64 = None
        db.session.commit()
        assert montar_marca_tenant(ctx['admin_id'])['logo'] is None
    assert _pdf(ctx)[:5] == b'%PDF-'


def test_logo_base64_valido_mas_que_nao_e_imagem_nao_derruba():
    """Base64 decodifica, mas os bytes não são imagem — o canvas ignora."""
    from services.cronograma_pdf import exportar_cronograma_pdf
    ctx = _cenario()
    dados = _dados(ctx)
    with app.app_context():
        pdf = exportar_cronograma_pdf(dados, {
            'nome': 'Construtora X', 'cnpj': '', 'endereco': '',
            'website': '', 'logo': b'nao-sou-uma-imagem'})
    assert pdf[:5] == b'%PDF-'


def test_nome_com_e_comercial_nao_derruba_a_geracao():
    """"Silva & Filhos" e "Laje <2º pav>" são nomes reais, e o `Paragraph` da
    reportlab lê mini-XML: sem escape, o download vira 500."""
    ctx = _cenario()
    with app.app_context():
        obra = db.session.get(Obra, ctx['obra_id'])
        obra.nome = 'Obra Silva & Filhos <matriz>'
        cliente = db.session.get(Cliente, obra.cliente_id)
        cliente.nome = 'Construtora Alfa & Beta'
        tarefa = (TarefaCronograma.query
                  .filter_by(obra_id=ctx['obra_id'], nome_tarefa='Radier')
                  .first())
        tarefa.nome_tarefa = 'Radier <bloco A & B>'
        db.session.commit()
    assert _pdf(ctx)[:5] == b'%PDF-'

    r = _http(ctx['admin_id']).get(
        f"/cronograma/obra/{ctx['obra_id']}/export.pdf")
    assert r.status_code == 200
    assert r.get_data()[:5] == b'%PDF-'


def test_nome_do_arquivo_sanitiza_e_marca_o_modo_cliente():
    from services.cronograma_pdf import nome_arquivo
    base = {'nome': 'Obra Ângela / Bloco B', 'modo_cliente': False}
    assert nome_arquivo({'obra': base}, date(2026, 8, 12)) == \
        'Cronograma_Obra-Angela-Bloco-B_2026-08-12.pdf'
    cli = dict(base, modo_cliente=True)
    assert nome_arquivo({'obra': cli}, date(2026, 8, 12)).endswith(
        '_2026-08-12_cliente.pdf')


# ═════════════════════════════════════════════════════════════════════════════
# 4. ROTA E AUTORIZAÇÃO
# ═════════════════════════════════════════════════════════════════════════════

def test_rota_devolve_pdf_para_quem_pode_ver():
    ctx = _cenario(com_logo=True)
    r = _http(ctx['admin_id']).get(f"/cronograma/obra/{ctx['obra_id']}/export.pdf")
    assert r.status_code == 200
    assert r.mimetype == 'application/pdf'
    assert r.get_data()[:5] == b'%PDF-'
    assert 'attachment' in r.headers.get('Content-Disposition', '')
    assert 'Cronograma_' in r.headers.get('Content-Disposition', '')


def test_rota_no_modo_cliente_exporta_a_copia_cliente():
    """O `?cliente=1` da tela chega ao PDF — e o nome do arquivo diz isso."""
    ctx = _cenario_cliente()
    r = _http(ctx['admin_id']).get(
        f"/cronograma/obra/{ctx['obra_id']}/export.pdf?cliente=1")
    assert r.status_code == 200
    assert '_cliente.pdf' in r.headers.get('Content-Disposition', '')


def test_obra_de_outro_tenant_da_404():
    a, b = _cenario(), _cenario()
    r = _http(b['admin_id']).get(f"/cronograma/obra/{a['obra_id']}/export.pdf")
    assert r.status_code == 404


def test_escopo_desligado_preserva_o_comportamento_permissivo():
    """Sem a flag, funcionário do tenant continua baixando — como antes."""
    ctx = _cenario()
    r = _http(ctx['user_id']).get(f"/cronograma/obra/{ctx['obra_id']}/export.pdf")
    assert r.status_code == 200


def test_escopo_ligado_sem_vinculo_da_404():
    """404 e não 403: a existência de obra fora do alcance não vaza."""
    ctx = _cenario()
    with _escopo_ligado(ctx['admin_id']):
        r = _http(ctx['user_id']).get(
            f"/cronograma/obra/{ctx['obra_id']}/export.pdf")
    assert r.status_code == 404


def test_escopo_ligado_com_vinculo_de_leitor_baixa():
    """Exportar é LEITURA: LEITOR passa, ao contrário das rotas que mutam."""
    ctx = _cenario(papel=PapelObra.LEITOR)
    with _escopo_ligado(ctx['admin_id']):
        r = _http(ctx['user_id']).get(
            f"/cronograma/obra/{ctx['obra_id']}/export.pdf")
    assert r.status_code == 200


def test_botao_aparece_na_tela_e_preserva_o_modo():
    ctx = _cenario()
    c = _http(ctx['admin_id'])
    html = c.get(f"/cronograma/obra/{ctx['obra_id']}").get_data(as_text=True)
    assert 'Exportar PDF' in html
    assert f"/cronograma/obra/{ctx['obra_id']}/export.pdf" in html
    assert f"/cronograma/obra/{ctx['obra_id']}/export.pdf?cliente=1" not in html

    html_cli = c.get(
        f"/cronograma/obra/{ctx['obra_id']}?cliente=1").get_data(as_text=True)
    assert f"/cronograma/obra/{ctx['obra_id']}/export.pdf?cliente=1" in html_cli
