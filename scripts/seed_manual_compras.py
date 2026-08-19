#!/usr/bin/env python3
"""Cenário determinístico para o manual visual de compras — 2026-08-18.

Uso:
    python scripts/seed_manual_compras.py            # cria/recria o cenário
    python scripts/seed_manual_compras.py --resumo   # só mostra o que existe

POR QUE ESTE SCRIPT EXISTE. A captura de telas de 22/07
(`scripts/capturar_manual_ciclo.py`) fixa IDs no topo do arquivo —
`ORCAMENTO_ID = 132`, `OBRA_ID = 1276`, um token de portal. Eram IDs de um
tenant de teste de julho; nenhum existe hoje, e por isso aquele manual não pode
ser refeito. Um manual que não pode ser regerado é um manual que envelhece em
silêncio.

Aqui o cenário é DADO, não achado: o script cria tudo de que as 16 telas do
manual precisam e é idempotente — rodar duas vezes seguidas produz o mesmo
cenário, com os mesmos números de requisição. Ele apaga e refaz o trabalho do
tenant do manual; não toca em nenhum outro.

O QUE ELE MONTA. Um tenant com a governança de compras ligada, quatro pessoas
(solicitante, gestor, comprador, financeiro) e requisições paradas em CADA
estado que o manual precisa fotografar:

    RC-...-0001  RASCUNHO      → telas do ato 1 (preencher, itens, enviar)
    RC-...-0002  AGUARDANDO    → telas do ato 2 (aprovar / rejeitar)
    RC-...-0003  REJEITADA     → a volta pela correção (17/08)
    RC-...-0004  APROVADA      → emitir pedido (ato 3)
    RC-...-0005  CONVERTIDA    → pedido A: conta BLOQUEADA, tríade aberta
    RC-...-0006  CONVERTIDA    → pedido B: tríade fechada, botão de liberar
    RC-...-0007  CONVERTIDA    → pedido C: já liberado, conta pagável e no lote

Os três pedidos existem porque o ato 4 precisa dos três momentos, e nenhum
deles cabe na foto do outro: a conta que ainda NÃO pode ser paga (o painel da
tríade nomeando a perna que falta), a que está PRONTA para liberar (o botão) e
a que JÁ foi liberada (a baixa e o lote). Com um pedido só, duas dessas três
telas não teriam o que mostrar.

FLAGS, conforme a decisão D2 do plano: governança, recebimento/atesto e
financeiro em dois fluxos LIGADOS; alçadas avançadas DESLIGADAS — é como o
parque está hoje, e manual mostra o que a pessoa vai ver.
"""
import argparse
import os
import sys
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# NÃO importar `main`: ele registra os blueprints e, no caminho, carrega a
# pilha de reconhecimento facial (ponto_views → deepface → tensorflow), que
# aborta o processo no encerramento (SIGABRT, exit 134) mesmo quando tudo deu
# certo. Este script não usa rota nenhuma — só modelos e serviços —, e um exit
# code mentiroso arruinaria a regra de que falha aqui tem de ser visível.
from app import app, db
from models import (AlmoxarifadoCategoria, AlmoxarifadoItem, BancoEmpresa, Cliente,
                    ConfiguracaoEmpresa, EstadoRequisicao, Fornecedor, Obra,
                    PapelObra, PedidoCompra, PedidoCompraItem, RequisicaoCompra,
                    RequisicaoCompraItem, TipoUsuario, Usuario, UsuarioObra)

# --- identidade fixa do cenário -------------------------------------------
# Tudo é encontrado por estes valores, nunca por id. É o que torna o script
# idempotente e o cenário refazível daqui a três meses.
MARCA = 'manualcompras'
SENHA = 'Manual@2026'
ANO = 2026

PESSOAS = [
    # (chave, username, nome, cargo que o manual usa)
    ('admin',       f'{MARCA}_admin',       'Ana Ribeiro',      'Administradora'),
    ('solicitante', f'{MARCA}_solicitante', 'Marcos Tavares',   'Encarregado da obra'),
    ('gestor',      f'{MARCA}_gestor',      'Paula Machado',    'Gerente de contrato'),
    ('comprador',   f'{MARCA}_comprador',   'Diego Ferraz',     'Comprador'),
    ('financeiro',  f'{MARCA}_financeiro',  'Helena Souza',     'Financeiro'),
]

ITENS_CATALOGO = [
    ('CIM-CP2', 'Cimento CP-II-Z-32 — saco 50 kg', 'sc', Decimal('39.90')),
    ('VER-10',  'Vergalhão CA-50 10 mm — barra 12 m', 'br', Decimal('58.40')),
    ('CHP-18',  'Chapa compensada plastificada 18 mm', 'un', Decimal('132.00')),
    ('ARE-MED', 'Areia média lavada — m³', 'm3', Decimal('115.00')),
]


def _pessoa(chave, username, nome, admin_id=None):
    """Encontra ou cria. NÃO reescreve a senha de quem já existe."""
    from werkzeug.security import generate_password_hash
    u = Usuario.query.filter_by(username=username).first()
    if u:
        return u
    u = Usuario(
        username=username,
        email=f'{username}@dev.local',
        nome=nome,
        password_hash=generate_password_hash(SENHA),
        tipo_usuario=TipoUsuario.ADMIN if chave == 'admin' else TipoUsuario.FUNCIONARIO,
        admin_id=admin_id,
        ativo=True,
        versao_sistema='v2')
    db.session.add(u)
    db.session.flush()
    return u


def _limpar(admin_id):
    """Apaga o trabalho do cenário — requisições, pedidos e tudo que pende deles.

    Deixa em pé o que é cadastro (pessoas, obra, fornecedor, catálogo): são
    estáveis, aparecem em print e recriá-los mudaria os ids a cada rodada.

    A ORDEM É A DAS CHAVES ESTRANGEIRAS, levantada do banco e não de memória —
    📖 `recebimento_pedido_item` aponta para `pedido_compra_item` E para
    `almoxarifado_movimento`, e `almoxarifado_estoque` aponta para o movimento.
    Apagar o pedido antes dos netos estoura ForeignKeyViolation na SEGUNDA
    rodada, quando já existe recebimento — que foi exatamente como este script
    falhou ao ser escrito. Idempotência aqui não é elegância: é o que permite
    refazer o manual daqui a três meses.
    """
    from sqlalchemy import text as _sql

    peds = [p.id for p in PedidoCompra.query.filter_by(admin_id=admin_id).all()]
    reqs = [r.id for r in RequisicaoCompra.query.filter_by(admin_id=admin_id).all()]

    def _exec(sql, **kw):
        db.session.execute(_sql(sql), kw)

    if peds:
        # netos do recebimento, e o estoque que nasceu do movimento.
        #
        # 🔬 19/08 — A FK APONTA NOS DOIS SENTIDOS, e este bloco só conhecia um.
        # `almoxarifado_estoque.entrada_movimento_id` aponta para o movimento
        # (sabido), mas `almoxarifado_movimento.estoque_id` aponta de volta para
        # o estoque — e é a SAIDA pareada do atesto que carrega esse vínculo.
        # Apagar o estoque com a SAIDA ainda apontando estoura
        # ForeignKeyViolation. Isto NUNCA tinha aparecido porque os itens do
        # cenário eram texto livre, e 📖 `recebimento_pedido.py:304` não gera
        # movimento nenhum para item sem `almoxarifado_item_id`: a idempotência
        # deste caminho era ilusória. Apareceu na primeira rodada do
        # `runbook_fase1.py`, depois que os itens ganharam vínculo com o catálogo.
        _exec("""UPDATE almoxarifado_movimento SET estoque_id = NULL
                 WHERE pedido_compra_id = ANY(:p)""", p=peds)
        _exec("""DELETE FROM almoxarifado_estoque WHERE entrada_movimento_id IN
                 (SELECT id FROM almoxarifado_movimento WHERE pedido_compra_id = ANY(:p))""", p=peds)
        _exec("""DELETE FROM recebimento_pedido_item WHERE recebimento_id IN
                 (SELECT id FROM recebimento_pedido WHERE pedido_id = ANY(:p))""", p=peds)
        _exec("DELETE FROM recebimento_pedido WHERE pedido_id = ANY(:p)", p=peds)
        _exec("DELETE FROM almoxarifado_movimento WHERE pedido_compra_id = ANY(:p)", p=peds)
        _exec("DELETE FROM nota_fiscal_pedido WHERE pedido_id = ANY(:p)", p=peds)
        _exec("DELETE FROM adiantamento_fornecedor WHERE pedido_id = ANY(:p)", p=peds)
        _exec("""DELETE FROM despesa_escritorio_ocorrencia WHERE conta_pagar_id IN
                 (SELECT id FROM conta_pagar WHERE pedido_compra_id = ANY(:p))""", p=peds)
        _exec("DELETE FROM conta_pagar WHERE pedido_compra_id = ANY(:p)", p=peds)
        _exec("DELETE FROM pedido_compra_item WHERE pedido_id = ANY(:p)", p=peds)
        _exec("DELETE FROM pedido_compra WHERE id = ANY(:p)", p=peds)

    if reqs:
        _exec("DELETE FROM requisicao_transicao WHERE requisicao_id = ANY(:r)", r=reqs)
        _exec("DELETE FROM requisicao_compra_item WHERE requisicao_id = ANY(:r)", r=reqs)
        _exec("DELETE FROM requisicao_compra WHERE id = ANY(:r)", r=reqs)

    db.session.commit()


def _requisicao(admin_id, obra_id, solicitante_id, seq, justificativa,
                itens, emergencial=False, dias=7):
    # 📖 O regime é CARIMBADO na linha, como `compras_views.requisicao_nova_post`
    # faz — nunca deixado no default da coluna. Requisição sem carimbo nasce
    # 'simples' em silêncio, e as quatro condições, o acumulado da janela e o
    # rito de emergência deixam de valer para ela.
    # 🔬 18/08: o teste-guarda `test_todo_ponto_que_cria_requisicao_carimba_o_
    # regime_alcada` pegou este arquivo no gate, apontando a linha exata. Era o
    # segundo lugar em que este seed construía o dado sem passar pelo caminho
    # que aplica a regra — o primeiro foram as flags, logo abaixo.
    from services.alcada_compras import regime_alcada_do_tenant
    r = RequisicaoCompra(
        regime_alcada=regime_alcada_do_tenant(admin_id),
        numero=f'RC-{ANO}-{seq:04d}',
        admin_id=admin_id,
        obra_id=obra_id,
        solicitante_id=solicitante_id,
        estado=EstadoRequisicao.RASCUNHO,
        justificativa=justificativa,
        data_necessidade=date(2026, 8, 18) + timedelta(days=dias),
        valor_estimado=Decimal('0'),
    )
    if hasattr(r, 'emergencial'):
        r.emergencial = emergencial
    db.session.add(r)
    db.session.flush()
    for cod, desc, un, preco, qtd in itens:
        # 🔬 19/08 — o VÍNCULO COM O CATÁLOGO, que faltava. Sem
        # `almoxarifado_item_id` o item é texto livre, e 📖
        # `services/recebimento_pedido.py:304` diz por escrito que "item de
        # texto livre não chega aqui": o atesto não gera ENTRADA nem SAIDA de
        # estoque. O cenário parecia completo e não exercia a perna de estoque
        # da Fase 1 — que é a razão daquela fase existir. Achado rodando
        # `scripts/runbook_fase1.py` pela primeira vez.
        catalogo = AlmoxarifadoItem.query.filter_by(
            admin_id=admin_id, codigo=cod).first()
        db.session.add(RequisicaoCompraItem(
            requisicao_id=r.id, admin_id=admin_id, descricao=desc,
            almoxarifado_item_id=catalogo.id if catalogo else None,
            unidade=un, quantidade=Decimal(str(qtd)), preco_estimado=preco))
    db.session.flush()
    from services.requisicao_compra import recalcular_valor
    recalcular_valor(r)
    db.session.flush()
    return r


def semear():
    from services.requisicao_compra import transicionar

    admin = _pessoa(*PESSOAS[0][:3])
    db.session.commit()
    pessoas = {'admin': admin}
    for chave, username, nome, _cargo in PESSOAS[1:]:
        pessoas[chave] = _pessoa(chave, username, nome, admin_id=admin.id)
    db.session.commit()

    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin.id).first()
    if not cfg:
        cfg = ConfiguracaoEmpresa(admin_id=admin.id)
        db.session.add(cfg)
    cfg.nome_empresa = 'Construtora Alto da Serra Ltda'
    db.session.commit()

    # AS FLAGS SAEM PELOS SCRIPTS, não por atribuição de coluna — e a lição é
    # cara. A primeira versão deste seed gravava `compras_governanca_ativa =
    # True` direto no modelo, o que passou por cima do guarda de
    # 📖 `scripts/flag_compras_governanca.py:98-105`: ele RECUSA ligar a
    # governança num tenant com `escopo_obra_ativo` desligado, e a mensagem da
    # recusa diz por quê — "sem o escopo, ... só o ADMIN emite pedido".
    #
    # 🔬 18/08: com o escopo desligado o manual foi capturado num estado que a
    # ferramenta recusa, e o passo de emitir pedido saiu como ato do
    # administrador. A cadeia dos cinco elos está descrita em `models.py:4482`:
    # alcadas_avancadas → compras_governanca → escopo_obra. Ligar na ordem é a
    # regra; gravar coluna à mão é como se burla uma regra sem perceber.
    from scripts.flag_compras_governanca import definir_flag as _governanca
    from scripts.flag_escopo_obra import definir_flag as _escopo
    from scripts.flag_escopo_obra import escopo_ativo
    from scripts.flag_financeiro_dois_fluxos import definir_flag as _dois_fluxos
    from scripts.flag_recebimento_atesto import definir_flag as _recebimento

    _escopo(admin.id, True)              # base da cadeia
    db.session.commit()
    # A pré-condição do guarda, conferida AQUI e não deixada ao acaso da ordem:
    # `definir_flag` é a escrita, e o guarda mora no `main()` do script — chamar
    # a função direto o burlaria do mesmo jeito que gravar a coluna burlava.
    if not escopo_ativo(admin.id):
        raise SystemExit('escopo_obra_ativo não ligou — sem ele a governança de '
                         'compras não pode ser ligada (flag_compras_governanca:98)')
    _governanca(admin.id, True)
    _recebimento(admin.id, True)
    _dois_fluxos(admin.id, True)
    db.session.commit()

    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin.id).first()
    ESPERADO = {
        'escopo_obra_ativo': True,
        'compras_governanca_ativa': True,
        'recebimento_atesto_ativo': True,
        'financeiro_dois_fluxos_ativo': True,
        'alcadas_avancadas_ativa': False,   # decisão D2 do plano
    }
    for nome, valor in ESPERADO.items():
        if getattr(cfg, nome, None) != valor:
            raise SystemExit(
                f'flag {nome}: quis {valor}, ficou {getattr(cfg, nome, None)}')

    cliente = Cliente.query.filter_by(admin_id=admin.id, nome='Incorporadora Vale Norte').first()
    if not cliente:
        cliente = Cliente(nome='Incorporadora Vale Norte', admin_id=admin.id)
        db.session.add(cliente)
        db.session.commit()

    obra = Obra.query.filter_by(admin_id=admin.id, codigo='OB-MANUAL').first()
    if not obra:
        obra = Obra(nome='Residencial Alto da Serra — Bloco B', codigo='OB-MANUAL',
                    data_inicio=date(2026, 3, 2), admin_id=admin.id,
                    cliente_id=cliente.id, ativo=True)
        db.session.add(obra)
        db.session.commit()

    forn = Fornecedor.query.filter_by(admin_id=admin.id, cnpj='12.345.678/0001-90').first()
    if not forn:
        forn = Fornecedor(nome='Casa do Construtor Materiais Ltda',
                          cnpj='12.345.678/0001-90', admin_id=admin.id, ativo=True)
        db.session.add(forn)
        db.session.commit()

    # VÍNCULO COM A OBRA — sem isto o manual não pode ser fotografado, e a
    # razão é do sistema, não do script: 📖 `utils/autorizacao.py:213`
    # (`pode_comprar_na_obra`) devolve False quando `papel_na_obra` é None, e o
    # bloco "Emitir pedido de compra" simplesmente NÃO É RENDERIZADO. Quem não
    # está vinculado à obra não vê o botão e conclui que o sistema quebrou.
    # 🔬 18/08: foi assim que a primeira captura falhou.
    PAPEIS = {
        'solicitante': PapelObra.COMPRADOR,   # requisita (PAPEIS_QUE_REQUISITAM)
        'gestor': PapelObra.GESTOR,           # aprova e responde pela obra
        'comprador': PapelObra.COMPRADOR,     # emite o pedido (PAPEIS_QUE_COMPRAM)
        'financeiro': PapelObra.LEITOR,
    }
    for chave, papel in PAPEIS.items():
        u = pessoas[chave]
        vinculo = UsuarioObra.query.filter_by(usuario_id=u.id, obra_id=obra.id).first()
        if not vinculo:
            vinculo = UsuarioObra(usuario_id=u.id, obra_id=obra.id, admin_id=admin.id)
            db.session.add(vinculo)
        vinculo.papel = papel
        vinculo.ativo = True
    db.session.commit()

    # Um banco, porque 📖 `templates/financeiro/pagar_conta.html:80` esconde o
    # campo inteiro (`{% if bancos %}`) quando o tenant não tem nenhum: a tela
    # de baixa abre sem lugar de onde tirar o dinheiro.
    if not BancoEmpresa.query.filter_by(admin_id=admin.id).first():
        db.session.add(BancoEmpresa(nome_banco='Banco do Brasil',
                                    agencia='1234-5', conta='12.345-6',
                                    admin_id=admin.id))
        db.session.commit()

    cat = AlmoxarifadoCategoria.query.filter_by(admin_id=admin.id, nome='Materiais de obra').first()
    if not cat:
        cat = AlmoxarifadoCategoria(nome='Materiais de obra', admin_id=admin.id,
                                    tipo_controle_padrao='quantidade')
        db.session.add(cat)
        db.session.commit()
    for cod, nome, _un, _preco in ITENS_CATALOGO:
        if not AlmoxarifadoItem.query.filter_by(admin_id=admin.id, codigo=cod).first():
            db.session.add(AlmoxarifadoItem(
                codigo=cod, nome=nome, categoria_id=cat.id,
                tipo_controle='quantidade', admin_id=admin.id))
    db.session.commit()

    _limpar(admin.id)

    sol, ges, com = pessoas['solicitante'], pessoas['gestor'], pessoas['comprador']
    cim = ('CIM-CP2', ITENS_CATALOGO[0][1], 'sc', ITENS_CATALOGO[0][3], 120)
    ver = ('VER-10', ITENS_CATALOGO[1][1], 'br', ITENS_CATALOGO[1][3], 40)
    chp = ('CHP-18', ITENS_CATALOGO[2][1], 'un', ITENS_CATALOGO[2][3], 25)
    are = ('ARE-MED', ITENS_CATALOGO[3][1], 'm3', ITENS_CATALOGO[3][3], 18)

    r1 = _requisicao(admin.id, obra.id, sol.id, 1,
                     'Concretagem da laje do 3º pavimento na semana que vem.',
                     [cim, are])
    r2 = _requisicao(admin.id, obra.id, sol.id, 2,
                     'Armação dos pilares do bloco B — estoque zerado.', [ver])
    transicionar(r2, EstadoRequisicao.AGUARDANDO_APROVACAO, sol)

    r3 = _requisicao(admin.id, obra.id, sol.id, 3,
                     'Formas para a escada do bloco B.', [chp])
    transicionar(r3, EstadoRequisicao.AGUARDANDO_APROVACAO, sol)
    transicionar(r3, EstadoRequisicao.REJEITADA, ges,
                 motivo='25 chapas é pouco para a escada inteira. Refaça para 40 e reenvie.')

    r4 = _requisicao(admin.id, obra.id, sol.id, 4,
                     'Reposição de cimento para o contrapiso.', [cim])
    transicionar(r4, EstadoRequisicao.AGUARDANDO_APROVACAO, sol)
    transicionar(r4, EstadoRequisicao.APROVADA, ges, motivo='De acordo com o cronograma.')

    db.session.commit()

    # --- os dois pedidos do ato 4 -----------------------------------------
    from services.financeiro_compra import criar_obrigacao, lancar_nota
    from services.recebimento_pedido import registrar_recebimento

    def _converter(seq, justificativa, itens, numero_pedido):
        r = _requisicao(admin.id, obra.id, sol.id, seq, justificativa, itens)
        transicionar(r, EstadoRequisicao.AGUARDANDO_APROVACAO, sol)
        transicionar(r, EstadoRequisicao.APROVADA, ges, motivo='De acordo.')
        p = PedidoCompra(
            numero=numero_pedido, fornecedor_id=forn.id, data_compra=date(2026, 8, 12),
            obra_id=obra.id, condicao_pagamento='30_dias', parcelas=1,
            valor_total=r.valor_estimado, tipo_compra='normal',
            processada_apos_aprovacao=False, admin_id=admin.id,
            requisicao_id=r.id, responsavel_id=com.id,
            exige_atesto=True, fluxo_pagamento='faturado',
            data_vencimento_primeira_parcela=date(2026, 9, 11))
        db.session.add(p)
        db.session.flush()
        for _cod, desc, _un, preco, qtd in itens:
            db.session.add(PedidoCompraItem(
                pedido_id=p.id, descricao=desc, quantidade=Decimal(str(qtd)),
                preco_unitario=preco,
                subtotal=(Decimal(str(qtd)) * preco).quantize(Decimal('0.01')),
                admin_id=admin.id))
        db.session.flush()
        transicionar(r, EstadoRequisicao.CONVERTIDA, com)
        criar_obrigacao(p)
        db.session.commit()
        return r, p

    # Pedido A — tríade ABERTA: a conta nasce bloqueada e fica assim.
    _rA, pedA = _converter(5, 'Blocos e argamassa para a alvenaria do 2º pavimento.',
                           [are, cim], 'PC-2026-0101')

    # Pedido B — tríade FECHADA: recebido, atestado e com nota. Conta liberável.
    _rB, pedB = _converter(6, 'Vergalhão para a armação da laje do 4º pavimento.',
                           [ver], 'PC-2026-0102')
    itemB = PedidoCompraItem.query.filter_by(pedido_id=pedB.id).first()
    registrar_recebimento(pedB, usuario=pessoas['admin'], data=date(2026, 8, 14),
                          linhas=[(itemB.id, Decimal('40'))])
    db.session.commit()
    lancar_nota(pedB, numero='118422', serie='1',
                valor_total=pedB.valor_total, data_emissao=date(2026, 8, 14),
                data_vencimento=date(2026, 9, 13), usuario=pessoas['admin'])
    db.session.commit()

    # Pedido C — já LIBERADO. Existe porque o ato de liberar e o resultado dele
    # não cabem na mesma foto: no B o botão "Liberar para pagamento" está lá
    # para ser fotografado; no C a conta já passou por ele e é o que a tela de
    # contas a pagar e o lote precisam ter para mostrar alguma coisa.
    from services.financeiro_compra import liberar
    _rC, pedC = _converter(7, 'Compensado para as formas da laje do 4º pavimento.',
                           [chp], 'PC-2026-0103')
    itemC = PedidoCompraItem.query.filter_by(pedido_id=pedC.id).first()
    registrar_recebimento(pedC, usuario=pessoas['admin'], data=date(2026, 8, 15),
                          linhas=[(itemC.id, Decimal('25'))])
    db.session.commit()
    lancar_nota(pedC, numero='118455', serie='1',
                valor_total=pedC.valor_total, data_emissao=date(2026, 8, 15),
                data_vencimento=date(2026, 9, 14), usuario=pessoas['admin'])
    db.session.commit()
    liberar(pedC, usuario=pessoas['admin'])
    db.session.commit()

    return admin, obra, pessoas, (pedA, pedB, pedC)


def resumo(admin):
    print(f'\n  tenant admin_id = {admin.id}   senha de todos: {SENHA}')
    print('  pessoas:')
    for chave, username, nome, cargo in PESSOAS:
        u = Usuario.query.filter_by(username=username).first()
        print(f'    {chave:12s} {u.email:34s} {nome} — {cargo}')
    print('  requisições:')
    for r in RequisicaoCompra.query.filter_by(admin_id=admin.id).order_by(
            RequisicaoCompra.numero).all():
        print(f'    {r.numero}  {r.estado.name:22s} R$ {r.valor_estimado}  (id={r.id})')
    print('  pedidos:')
    from models import ContaPagar
    for p in PedidoCompra.query.filter_by(admin_id=admin.id).order_by(
            PedidoCompra.numero).all():
        c = ContaPagar.query.filter_by(pedido_compra_id=p.id).first()
        sit = c.situacao_liberacao if c else '(sem conta)'
        print(f'    {p.numero}  R$ {p.valor_total}  conta={sit}  (id={p.id})')
    print()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--resumo', action='store_true',
                    help='só mostra o cenário existente, sem recriar')
    args = ap.parse_args()
    with app.app_context():
        if args.resumo:
            adm = Usuario.query.filter_by(username=f'{MARCA}_admin').first()
            if not adm:
                print('cenário não existe — rode sem --resumo')
                sys.exit(1)
            resumo(adm)
        else:
            admin, _obra, _pessoas, _peds = semear()
            print('[OK] cenário do manual de compras semeado')
            resumo(admin)
