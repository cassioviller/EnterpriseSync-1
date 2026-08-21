#!/usr/bin/env python3
"""Cenário determinístico para o manual visual do RDO — 2026-08-21.

Uso:
    .pythonlibs/bin/python scripts/seed_manual_rdo.py               # cria/recria
    .pythonlibs/bin/python scripts/seed_manual_rdo.py --resumo      # mostra os ids
    .pythonlibs/bin/python scripts/seed_manual_rdo.py --limpar-rdos # apaga os RDOs do tenant

Mesma regra do seed de compras: o cenário é DADO, não achado. Tudo no tenant
`manualrdo`, idempotente, e nenhum id fixo — quem precisa de id lê `resumo()`.

O QUE ELE MONTA. Um tenant com cronograma v2 ligado; três pessoas (admin,
encarregado APONTADOR, gestor GESTOR); uma obra com cronograma interno de duas
fases e quatro folhas — uma por quantidade (empresa), uma de terceiros com
quantidade, uma por percentual e um marco —, três funcionários operacionais,
um administrativo (para a tela do filtro) e um subempreiteiro.

📖 `services/cronograma_apontamento_service._modo_deduzido`: sem
`modo_apontamento`, quantidade > 0 E unidade não vazia ⇒ 'quantidade'; senão
'percentual'. A flag `rdo_percentual_livre` fica desligada (default).
"""
import argparse
import os
import sys
from datetime import date

os.environ.setdefault('SIGE_BOOT_DDL', '0')
os.environ.setdefault('SIGE_ENABLE_DEMO_SEED', 'false')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MARCA = 'manualrdo'
SENHA = 'Manual@2026'
PESSOAS = [
    ('admin',       f'{MARCA}_admin',       'Beatriz Campos', 'Administradora'),
    ('encarregado', f'{MARCA}_encarregado', 'Mateus Lira',    'Encarregado da obra'),
    ('gestor',      f'{MARCA}_gestor',      'Carla Nunes',    'Gestora da obra'),
]
OBRA_NOME = 'Galpão Logístico Vila Norte'
OBRA_CODIGO = 'MRDO-01'
FUNCOES = [('Montador', True), ('Soldador', True), ('Auxiliar Administrativo', False)]
FUNCIONARIOS = [  # (codigo, nome, funcao)
    ('MR01', 'Davi Montador', 'Montador'),
    ('MR02', 'Lucas Soldador', 'Soldador'),
    ('MR03', 'Pedro Ajudante', 'Montador'),
    ('MR04', 'Ana Escritório', 'Auxiliar Administrativo'),
]
SUBEMPREITEIRO = ('Abraão Fundações', 'Fundações')
# (chave, nome, pai, ordem, inicio, fim, quantidade, unidade, responsavel, marco)
TAREFAS = [
    ('fundacoes', 'Fundações',                                None,        0, date(2026, 8, 3),   date(2026, 12, 30), None,  None, 'empresa',   False),
    ('t_estacas', 'Estacas hélice contínua',                  'fundacoes', 1, date(2026, 8, 3),   date(2026, 12, 30), 120.0, 'un', 'terceiros', False),
    ('t_blocos',  'Blocos de coroamento',                     'fundacoes', 2, date(2026, 8, 10),  date(2026, 12, 30), 24.0,  'un', 'empresa',   False),
    ('estrutura', 'Estrutura metálica',                       None,        3, date(2026, 8, 17),  date(2026, 12, 30), None,  None, 'empresa',   False),
    ('t_pilares', 'Montagem de pilares',                      'estrutura', 4, date(2026, 8, 17),  date(2026, 12, 30), None,  None, 'empresa',   False),
    ('t_marco',   'Liberação da estrutura pela fiscalização', 'estrutura', 5, date(2026, 12, 30), date(2026, 12, 30), None,  None, 'empresa',   True),
]


def _pessoa(chave, username, nome, admin_id=None):
    """Encontra ou cria. NÃO reescreve a senha de quem já existe."""
    from werkzeug.security import generate_password_hash
    from app import db
    from models import TipoUsuario, Usuario
    u = Usuario.query.filter_by(username=username).first()
    if u:
        return u
    u = Usuario(username=username, email=f'{username}@dev.local', nome=nome,
                password_hash=generate_password_hash(SENHA),
                tipo_usuario=TipoUsuario.ADMIN if chave == 'admin' else TipoUsuario.FUNCIONARIO,
                admin_id=admin_id, ativo=True, versao_sistema='v2')
    db.session.add(u)
    db.session.flush()
    return u


def _flags(admin):
    from app import db
    from models import ConfiguracaoEmpresa
    from scripts.flag_cronograma_mpp import definir_flag
    definir_flag(admin.id, True)
    cfg = ConfiguracaoEmpresa.query.filter_by(admin_id=admin.id).first()
    if cfg is None:
        cfg = ConfiguracaoEmpresa(admin_id=admin.id, nome_empresa='Vila Norte Construções')
        db.session.add(cfg)
    cfg.cronograma_editor_v2 = True
    db.session.commit()


def _obra(admin):
    from app import db
    from models import Cliente, Obra
    cliente = Cliente.query.filter_by(admin_id=admin.id, nome='Logis Norte Ltda').first()
    if cliente is None:
        cliente = Cliente(admin_id=admin.id, nome='Logis Norte Ltda',
                          email=f'{MARCA}_cliente@dev.local', telefone='11999990000')
        db.session.add(cliente)
        db.session.flush()
    obra = Obra.query.filter_by(admin_id=admin.id, codigo=OBRA_CODIGO).first()
    if obra is None:
        obra = Obra(nome=OBRA_NOME, codigo=OBRA_CODIGO, admin_id=admin.id,
                    cliente_id=cliente.id, status='Em andamento',
                    data_inicio=date(2026, 8, 3), ativo=True)
        db.session.add(obra)
        db.session.flush()
    return obra


def _vinculos(admin, obra, pessoas):
    from app import db
    from models import PapelObra, UsuarioObra
    for chave, papel in (('encarregado', PapelObra.APONTADOR), ('gestor', PapelObra.GESTOR)):
        u = pessoas[chave]
        v = UsuarioObra.query.filter_by(usuario_id=u.id, obra_id=obra.id).first()
        if v is None:
            v = UsuarioObra(usuario_id=u.id, obra_id=obra.id, admin_id=admin.id)
            db.session.add(v)
        v.papel = papel
        v.ativo = True
    db.session.commit()


def _pessoal(admin):
    from app import db
    from models import Funcao, Funcionario
    funcoes = {}
    for nome, operacional in FUNCOES:
        f = Funcao.query.filter_by(admin_id=admin.id, nome=nome).first()
        if f is None:
            f = Funcao(nome=nome, admin_id=admin.id, salario_base=0.0)
            db.session.add(f)
            db.session.flush()
        f.operacional = operacional
        funcoes[nome] = f
    ids = {}
    for i, (codigo, nome, funcao) in enumerate(FUNCIONARIOS, start=1):
        fx = Funcionario.query.filter_by(admin_id=admin.id, codigo=codigo).first()
        if fx is None:
            fx = Funcionario(codigo=codigo, nome=nome, cpf=f'{admin.id:09d}{i:02d}',
                             data_admissao=date(2026, 8, 3), admin_id=admin.id,
                             funcao_id=funcoes[funcao].id, ativo=True, salario=3200.0)
            db.session.add(fx)
            db.session.flush()
        ids[nome] = fx.id
    db.session.commit()
    return ids


def _subempreiteiro(admin):
    from app import db
    from models import Subempreiteiro
    nome, esp = SUBEMPREITEIRO
    s = Subempreiteiro.query.filter_by(admin_id=admin.id, nome=nome).first()
    if s is None:
        s = Subempreiteiro(admin_id=admin.id, nome=nome, especialidade=esp, ativo=True)
        db.session.add(s)
        db.session.commit()
    return s


def _cronograma(admin, obra):
    from app import db
    from models import TarefaCronograma
    ids = {}
    for chave, nome, pai, ordem, ini, fim, qtd, un, resp, marco in TAREFAS:
        t = TarefaCronograma.query.filter_by(obra_id=obra.id, nome_tarefa=nome,
                                             is_cliente=False).first()
        if t is None:
            t = TarefaCronograma(obra_id=obra.id, admin_id=admin.id, nome_tarefa=nome,
                                 ordem=ordem, duracao_dias=max((fim - ini).days, 1),
                                 data_inicio=ini, data_fim=fim, is_cliente=False)
            db.session.add(t)
            db.session.flush()
        t.tarefa_pai_id = ids[pai] if pai else None
        t.quantidade_total = qtd
        t.unidade_medida = un
        t.responsavel = resp
        t.is_marco = marco
        t.ativa = True
        ids[chave] = t.id
    db.session.commit()
    return ids


def semear():
    from app import db
    from models import Usuario
    admin = _pessoa(*PESSOAS[0][:3])
    db.session.commit()
    pessoas = {'admin': admin}
    for chave, username, nome, _cargo in PESSOAS[1:]:
        pessoas[chave] = _pessoa(chave, username, nome, admin_id=admin.id)
    db.session.commit()
    _flags(admin)
    obra = _obra(admin)
    _vinculos(admin, obra, pessoas)
    _pessoal(admin)
    _subempreiteiro(admin)
    _cronograma(admin, obra)
    return db.session.get(Usuario, admin.id)


def limpar_rdos(admin_id):
    """Apaga os RDOs do tenant (filhos primeiro), para a captura começar do zero."""
    from app import db
    from models import (RDO, RDOApontamentoCronograma, RDOAssinatura, RDOFoto,
                        RDOServicoSubatividade, RDOSubempreitadaApontamento,
                        RDOTransicaoEstado, Obra)
    obra_ids = [o.id for o in Obra.query.filter_by(admin_id=admin_id).all()]
    rdos = RDO.query.filter(RDO.obra_id.in_(obra_ids)).all() if obra_ids else []
    for r in rdos:
        for modelo in (RDOSubempreitadaApontamento, RDOApontamentoCronograma,
                       RDOServicoSubatividade, RDOFoto, RDOAssinatura, RDOTransicaoEstado):
            modelo.query.filter_by(rdo_id=r.id).delete(synchronize_session=False)
        db.session.delete(r)          # mao_obra, equipamentos, ocorrencias: cascade no modelo
    db.session.commit()
    return len(rdos)


def resumo(admin):
    from models import Funcionario, Obra, Subempreiteiro, TarefaCronograma
    obra = Obra.query.filter_by(admin_id=admin.id, codigo=OBRA_CODIGO).one()

    def tarefa(nome):
        return TarefaCronograma.query.filter_by(obra_id=obra.id, nome_tarefa=nome).one().id

    def func(codigo):
        return Funcionario.query.filter_by(admin_id=admin.id, codigo=codigo).one().id

    return {
        'obra_id': obra.id,
        't_estacas': tarefa('Estacas hélice contínua'),
        't_blocos': tarefa('Blocos de coroamento'),
        't_pilares': tarefa('Montagem de pilares'),
        't_marco': tarefa('Liberação da estrutura pela fiscalização'),
        'f_davi': func('MR01'), 'f_pedro': func('MR03'),
        'sub_id': Subempreiteiro.query.filter_by(admin_id=admin.id).one().id,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--resumo', action='store_true')
    ap.add_argument('--limpar-rdos', action='store_true')
    args = ap.parse_args()
    import main as _main  # noqa: F401
    from app import app
    from models import Usuario
    with app.app_context():
        if args.resumo:
            admin = Usuario.query.filter_by(username=f'{MARCA}_admin').first()
            if admin is None:
                raise SystemExit('tenant manualrdo não existe — rode sem --resumo primeiro')
            for k, v in resumo(admin).items():
                print(f'{k:10s} {v}')
            return 0
        if args.limpar_rdos:
            admin = Usuario.query.filter_by(username=f'{MARCA}_admin').one()
            print(f'{limpar_rdos(admin.id)} RDO(s) apagado(s)')
            return 0
        admin = semear()
        print(f'tenant {MARCA} (admin {admin.id}) pronto')
        for k, v in resumo(admin).items():
            print(f'{k:10s} {v}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
