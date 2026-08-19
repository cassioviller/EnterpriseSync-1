#!/usr/bin/env python3
"""Tenant de PILOTO do ciclo de compras — lousa limpa, gente e cadastro. 2026-08-19

Uso:
    python scripts/seed_piloto_compras.py            # cria/recria
    python scripts/seed_piloto_compras.py --resumo   # só mostra o que existe

POR QUE ESTE SEED EXISTE, e por que NÃO é o do manual. O propósito dos dois é
oposto:

  `seed_manual_compras.py`  existe para FOTOGRAFAR telas. Precisa de requisições
                            paradas em cada estado, e por isso entrega um tenant
                            com a janela do anti-fracionamento já cheia e as flags
                            já ligadas.
  ESTE                      existe para EXERCER o rollout. Precisa do contrário:
                            cadastro completo, ZERO requisições e TODAS as flags
                            desligadas — porque ligar a cadeia É o ensaio.

🔬 O que o ensaio de 19/08 no tenant de demonstração mostrou, e que este seed
existe para não repetir: aquele tenant tinha 1260 obras, itens de almoxarifado e
faixas semeadas — e **um único usuário de login, com zero vínculos usuario_obra**.
As flags teriam ligado e o ciclo não rodaria, porque as três regras de segregação
que são a razão das fases existirem (solicitante ≠ aprovador; aprovador ≠ emissor
quando a faixa pede mais de uma assinatura; quem monta o lote ≠ quem o fecha)
**exigem que o tenant tenha pessoas**.

E o pior daquele caso: 📖 `papel_de_usuario_na_obra:144` devolve GESTOR ao ADMIN em
qualquer obra do tenant, então quem validasse com a conta de admin percorreria o
fluxo inteiro sozinho e concluiria que estava tudo certo.

O QUE ELE MONTA
  • cinco logins com papéis distintos, e vínculo de cada um com a obra piloto
  • uma obra PILOTO com três etapas, para o anti-fracionamento poder ser exercido
    por etapa — e não só no grupo de etapa NULA
  • uma obra HISTÓRICA, que existe por um motivo só: dar passado a um fornecedor
  • DOIS fornecedores de propósito — um CONHECIDO (tem pedido emitido) e um NOVO
    (zero pedidos). 📖 `_cond_fornecedor_novo` julga por "nenhum pedido emitido
    neste tenant", não por data: é isso que torna o passo 3b do runbook das
    alçadas exercível, e ele estava fora de escopo por falta deste par
  • catálogo de almoxarifado, banco e faixas de alçada
  • ZERO requisições e ZERO pedidos na obra piloto — janela limpa

O QUE ELE NÃO FAZ: ligar flag nenhuma. Sai com as cinco DESLIGADAS, e confere isso
no fim. Ligar é o rollout, e o rollout é o teste.

A REGRA QUE ELE SEGUE, aprendida três vezes em 18/08: dado construído direto no
modelo reproduz a FORMA e perde a REGRA. As faixas saem de
`garantir_faixas_do_tenant`, os itens de requisição nasceriam vinculados ao
catálogo, e o pedido histórico carimba o regime em vez de deixá-lo no default.
"""
import argparse
import os
import sys
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# NÃO importar `main`: ele carrega a pilha de reconhecimento facial
# (ponto_views → deepface → tensorflow), que aborta o processo no encerramento
# mesmo quando tudo deu certo. Este script não usa rota nenhuma.
from app import app, db
from models import (AlmoxarifadoCategoria, AlmoxarifadoItem, BancoEmpresa,
                    Cliente, ConfiguracaoEmpresa, Fornecedor, Obra,
                    ObraServicoCusto, PapelObra, PedidoCompra, PedidoCompraItem,
                    RequisicaoCompra, TipoUsuario, Usuario, UsuarioObra)

MARCA = 'piloto'
SENHA = 'Piloto@2026'

PESSOAS = [
    # (chave, nome, cargo, papel na obra piloto)
    ('admin',       'Regina Alencar',  'Administradora',      None),
    ('solicitante', 'Tiago Nunes',     'Encarregado de campo', PapelObra.COMPRADOR),
    ('gestor',      'Beatriz Lemos',   'Gerente de contrato',  PapelObra.GESTOR),
    ('comprador',   'Rafael Pinho',    'Comprador',            PapelObra.COMPRADOR),
    ('financeiro',  'Sônia Prado',     'Financeiro',           PapelObra.LEITOR),
]

CATALOGO = [
    ('PIL-CIM', 'Cimento CP-II-Z-32 — saco 50 kg', 'sc', Decimal('39.90')),
    ('PIL-VER', 'Vergalhão CA-50 10 mm — barra 12 m', 'br', Decimal('58.40')),
    ('PIL-CHP', 'Chapa compensada plastificada 18 mm', 'un', Decimal('132.00')),
    ('PIL-ARE', 'Areia média lavada — m³', 'm3', Decimal('115.00')),
]

# Três etapas: o anti-fracionamento acumula por (obra, etapa), e com etapas
# nomeadas dá para separar "três fatias na MESMA etapa" de "três fatias em
# etapas diferentes" — que é o contraste que o passo 3c precisa e que o grupo
# de etapa NULA não consegue mostrar.
ETAPAS = ['Fundação', 'Estrutura', 'Alvenaria']

FLAGS = ['escopo_obra_ativo', 'compras_governanca_ativa', 'recebimento_atesto_ativo',
         'financeiro_dois_fluxos_ativo', 'alcadas_avancadas_ativa']


def _pessoa(chave, nome, admin_id=None):
    from werkzeug.security import generate_password_hash
    username = f'{MARCA}_{chave}'
    u = Usuario.query.filter_by(username=username).first()
    if u:
        return u
    u = Usuario(
        username=username, email=f'{username}@piloto.local', nome=nome,
        password_hash=generate_password_hash(SENHA),
        tipo_usuario=TipoUsuario.ADMIN if chave == 'admin' else TipoUsuario.FUNCIONARIO,
        admin_id=admin_id, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.flush()
    return u


def _obra(admin_id, cliente_id, nome, codigo):
    o = Obra.query.filter_by(admin_id=admin_id, codigo=codigo).first()
    if o:
        return o
    o = Obra(nome=nome, codigo=codigo, data_inicio=date.today() - timedelta(days=60),
             admin_id=admin_id, cliente_id=cliente_id, ativo=True)
    db.session.add(o)
    db.session.flush()
    return o


def _limpar_trabalho(admin_id):
    """Apaga requisições e pedidos — o CADASTRO fica de pé.

    A ordem é a das chaves estrangeiras, e ela inclui a lição de 19/08:
    `almoxarifado_movimento.estoque_id` aponta de VOLTA para o estoque, e é a
    SAIDA pareada do atesto que carrega esse vínculo. Apagar o estoque com a
    SAIDA apontando estoura ForeignKeyViolation.
    """
    from sqlalchemy import text as _sql
    peds = [p.id for p in PedidoCompra.query.filter_by(admin_id=admin_id).all()]
    reqs = [r.id for r in RequisicaoCompra.query.filter_by(admin_id=admin_id).all()]

    def _x(sql, **kw):
        db.session.execute(_sql(sql), kw)

    if peds:
        _x("UPDATE almoxarifado_movimento SET estoque_id = NULL WHERE pedido_compra_id = ANY(:p)", p=peds)
        _x("""DELETE FROM almoxarifado_estoque WHERE entrada_movimento_id IN
              (SELECT id FROM almoxarifado_movimento WHERE pedido_compra_id = ANY(:p))""", p=peds)
        _x("""DELETE FROM recebimento_pedido_item WHERE recebimento_id IN
              (SELECT id FROM recebimento_pedido WHERE pedido_id = ANY(:p))""", p=peds)
        _x("DELETE FROM recebimento_pedido WHERE pedido_id = ANY(:p)", p=peds)
        _x("DELETE FROM almoxarifado_movimento WHERE pedido_compra_id = ANY(:p)", p=peds)
        _x("DELETE FROM nota_fiscal_pedido WHERE pedido_id = ANY(:p)", p=peds)
        _x("DELETE FROM adiantamento_fornecedor WHERE pedido_id = ANY(:p)", p=peds)
        _x("DELETE FROM conta_pagar WHERE pedido_compra_id = ANY(:p)", p=peds)
        _x("DELETE FROM pedido_compra_item WHERE pedido_id = ANY(:p)", p=peds)
    if reqs:
        _x("DELETE FROM requisicao_transicao WHERE requisicao_id = ANY(:r)", r=reqs)
        _x("DELETE FROM requisicao_compra_item WHERE requisicao_id = ANY(:r)", r=reqs)
    _x("DELETE FROM pedido_compra WHERE admin_id = :a", a=admin_id)
    _x("DELETE FROM requisicao_compra WHERE admin_id = :a", a=admin_id)
    db.session.commit()


def semear():
    admin = _pessoa('admin', 'Regina Alencar')
    db.session.commit()
    pessoas = {'admin': admin}
    for chave, nome, _cargo, _papel in PESSOAS[1:]:
        pessoas[chave] = _pessoa(chave, nome, admin_id=admin.id)
    db.session.commit()

    cli = Cliente.query.filter_by(admin_id=admin.id, nome='Incorporadora Horizonte').first()
    if not cli:
        cli = Cliente(nome='Incorporadora Horizonte', admin_id=admin.id)
        db.session.add(cli)
        db.session.commit()

    obra = _obra(admin.id, cli.id, 'Residencial Horizonte — Torre A', 'PIL-A')
    hist = _obra(admin.id, cli.id, 'Obra histórica (só dá passado ao fornecedor)', 'PIL-H')
    db.session.commit()

    for nome in ETAPAS:
        if not ObraServicoCusto.query.filter_by(admin_id=admin.id, obra_id=obra.id,
                                                nome=nome).first():
            db.session.add(ObraServicoCusto(admin_id=admin.id, obra_id=obra.id,
                                            nome=nome, valor_orcado=Decimal('50000.00')))
    db.session.commit()

    # Vínculos — o requisito que derrubou o ensaio de 19/08.
    for chave, _nome, _cargo, papel in PESSOAS[1:]:
        u = pessoas[chave]
        v = UsuarioObra.query.filter_by(usuario_id=u.id, obra_id=obra.id).first()
        if not v:
            v = UsuarioObra(usuario_id=u.id, obra_id=obra.id, admin_id=admin.id)
            db.session.add(v)
        v.papel, v.ativo = papel, True
    db.session.commit()

    if not BancoEmpresa.query.filter_by(admin_id=admin.id).first():
        db.session.add(BancoEmpresa(nome_banco='Banco do Brasil', agencia='4321-0',
                                    conta='98.765-4', admin_id=admin.id))
    cat = AlmoxarifadoCategoria.query.filter_by(admin_id=admin.id,
                                                nome='Materiais de obra').first()
    if not cat:
        cat = AlmoxarifadoCategoria(nome='Materiais de obra', admin_id=admin.id,
                                    tipo_controle_padrao='quantidade')
        db.session.add(cat)
        db.session.commit()
    for cod, nome, _un, _preco in CATALOGO:
        if not AlmoxarifadoItem.query.filter_by(admin_id=admin.id, codigo=cod).first():
            db.session.add(AlmoxarifadoItem(codigo=cod, nome=nome, categoria_id=cat.id,
                                            tipo_controle='quantidade', admin_id=admin.id))
    db.session.commit()

    conhecido = Fornecedor.query.filter_by(admin_id=admin.id, cnpj='11.222.333/0001-44').first()
    if not conhecido:
        conhecido = Fornecedor(nome='Depósito Central Materiais Ltda',
                               cnpj='11.222.333/0001-44', admin_id=admin.id, ativo=True)
        db.session.add(conhecido)
    novo = Fornecedor.query.filter_by(admin_id=admin.id, cnpj='55.666.777/0001-88').first()
    if not novo:
        novo = Fornecedor(nome='Metalúrgica Aurora (ainda sem histórico)',
                          cnpj='55.666.777/0001-88', admin_id=admin.id, ativo=True)
        db.session.add(novo)
    db.session.commit()

    _limpar_trabalho(admin.id)

    # O pedido que dá PASSADO ao fornecedor conhecido — na obra histórica, para
    # não pôr nada na janela do anti-fracionamento da obra piloto. O regime é
    # CARIMBADO, não deixado no default: `fluxo_do_pedido_novo` responde pelo
    # estado real das flags (todas OFF aqui), e é assim que a rota faz.
    from services.financeiro_compra import fluxo_do_pedido_novo
    from services.recebimento_pedido import regime_do_tenant
    p = PedidoCompra(
        numero='PC-HIST-0001', fornecedor_id=conhecido.id,
        data_compra=date.today() - timedelta(days=120), obra_id=hist.id,
        condicao_pagamento='a_vista', parcelas=1, valor_total=Decimal('1200.00'),
        tipo_compra='normal', processada_apos_aprovacao=False, admin_id=admin.id,
        responsavel_id=admin.id,
        exige_atesto=bool(regime_do_tenant(admin.id)),
        fluxo_pagamento=fluxo_do_pedido_novo(admin.id))
    db.session.add(p)
    db.session.flush()
    db.session.add(PedidoCompraItem(
        pedido_id=p.id, descricao='Material diverso (histórico)',
        quantidade=Decimal('10'), preco_unitario=Decimal('120.00'),
        subtotal=Decimal('1200.00'), admin_id=admin.id))
    db.session.commit()

    # Faixas pelo caminho que aplica a regra, não pelo construtor.
    from services.alcada_compras import garantir_faixas_do_tenant
    garantir_faixas_do_tenant(admin.id)
    db.session.commit()

    # As cinco flags DESLIGADAS — ligar é o rollout, e o rollout é o teste.
    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin.id).first()
    if cfg is None:
        cfg = ConfiguracaoEmpresa(admin_id=admin.id, nome_empresa='Construtora Piloto')
        db.session.add(cfg)
    for f in FLAGS:
        if hasattr(cfg, f):
            setattr(cfg, f, False)
    db.session.commit()

    return admin, obra, hist, pessoas, (conhecido, novo)


def resumo(admin):
    from services.alcada_compras import garantir_faixas_do_tenant  # noqa: F401
    from models import FaixaAlcada
    print(f'\n  tenant admin_id = {admin.id}   senha de todos: {SENHA}')
    print('  pessoas:')
    for chave, nome, cargo, papel in PESSOAS:
        u = Usuario.query.filter_by(username=f'{MARCA}_{chave}').first()
        pap = papel.value if papel else '—'
        print(f'    {chave:12s} {u.email:28s} {nome:18s} {cargo:20s} papel={pap}')
    print('  obras:')
    for o in Obra.query.filter_by(admin_id=admin.id).order_by(Obra.codigo).all():
        n_et = ObraServicoCusto.query.filter_by(obra_id=o.id).count()
        n_vi = UsuarioObra.query.filter_by(obra_id=o.id, ativo=True).count()
        print(f'    {o.codigo:6s} {o.nome[:44]:44s} etapas={n_et} vinculos={n_vi}')
    print('  fornecedores:')
    for f in Fornecedor.query.filter_by(admin_id=admin.id).all():
        n = PedidoCompra.query.filter_by(admin_id=admin.id, fornecedor_id=f.id).count()
        print(f'    {f.nome[:44]:44s} pedidos={n}  → {"CONHECIDO" if n else "NOVO"}')
    print(f'  faixas de alçada: {FaixaAlcada.query.filter_by(admin_id=admin.id).count()}')
    print(f'  requisições: {RequisicaoCompra.query.filter_by(admin_id=admin.id).count()} '
          f'(janela limpa)')
    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin.id).first()
    est = {f: bool(getattr(cfg, f, False)) for f in FLAGS}
    print(f'  flags: {"todas DESLIGADAS" if not any(est.values()) else est}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--resumo', action='store_true')
    args = ap.parse_args()
    with app.app_context():
        if args.resumo:
            u = Usuario.query.filter_by(username=f'{MARCA}_admin').first()
            if not u:
                raise SystemExit('cenário do piloto ainda não existe — rode sem --resumo')
            resumo(u)
            return 0
        admin, _obra, _hist, _p, _f = semear()
        print('[OK] cenário do PILOTO de compras semeado')
        resumo(admin)
    return 0


if __name__ == '__main__':
    sys.exit(main())
