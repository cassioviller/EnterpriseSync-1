"""Decompõe a verba do item 1.17 (Pacote complementar) na parte de FUNDAÇÃO,
usando os dados reais da aba 'Fundação' da planilha REV10. Cria os insumos +
o serviço decomposto no catálogo (idempotente) e imprime a comparação com a
verba original.
"""
from decimal import Decimal
from app import app, db
from models import Usuario, Servico, Insumo, ComposicaoServico, PrecoBaseInsumo
from datetime import date

SVC = 'Fundação - sapatas, radier e aço (1.17)'
# nome -> (tipo, unidade, preco, coef_no_servico, obs)
LINHAS = [
    ('Escavação de estaca',        'MAO_OBRA',   'm',  '20.00',  '280',   'aba Fundação L62'),
    ('Concreto armado fundação',   'MATERIAL',   'm3', '480.00', '58.23', 'aba Fundação L63'),
    ('Bomba de concreto',          'EQUIPAMENTO','un', '1800.00','3',     'aba Fundação L64'),
    ('Aço CA-50 fundação',         'MATERIAL',   'kg', '5.50',   '2743',  'aba Fundação L65'),
    ('Madeira de forma',           'MATERIAL',   'vb', '9000.00','1',     'aba Fundação L66'),
    ('Miscelâneas fundação',       'MATERIAL',   'vb', '5500.00','1.5',   'aba Fundação L67'),
    ('Equipe fundação (dia)',      'MAO_OBRA',   'dia','1170.00','40',    'Enc+2Ped+MeioOf+Aj, 40 dias'),
    ('Visita técnica (Guilherme)', 'MAO_OBRA',   'vb', '2914.00','1',     'aba Fundação L39'),
]
VERBA_MAT = Decimal('52322'); VERBA_MO = Decimal('40242')


def main():
    with app.app_context():
        u = Usuario.query.filter_by(tipo_usuario='ADMIN').first() or Usuario.query.first()
        aid = u.id

        # upsert insumos + preço
        ins_by_nome = {}
        for nome, tipo, un, preco, _coef, _obs in LINHAS:
            ins = Insumo.query.filter_by(admin_id=aid, nome=nome).first()
            if not ins:
                ins = Insumo(admin_id=aid, nome=nome, tipo=tipo, unidade=un)
                db.session.add(ins); db.session.flush()
            if not PrecoBaseInsumo.query.filter_by(insumo_id=ins.id, vigencia_fim=None).first():
                db.session.add(PrecoBaseInsumo(admin_id=aid, insumo_id=ins.id,
                               valor=Decimal(preco), vigencia_inicio=date(2026, 1, 1)))
            ins_by_nome[nome] = ins
        db.session.flush()

        # upsert serviço + composição
        svc = Servico.query.filter_by(admin_id=aid, nome=SVC).first()
        if not svc:
            svc = Servico(admin_id=aid, nome=SVC, categoria='Obra Baia REV10', unidade_medida='vb')
            db.session.add(svc); db.session.flush()
        for nome, tipo, un, preco, coef, obs in LINHAS:
            ins = ins_by_nome[nome]
            comp = ComposicaoServico.query.filter_by(servico_id=svc.id, insumo_id=ins.id).first()
            if not comp:
                comp = ComposicaoServico(admin_id=aid, servico_id=svc.id, insumo_id=ins.id)
                db.session.add(comp)
            comp.coeficiente = Decimal(coef); comp.unidade = un; comp.observacao = obs
        db.session.commit()

        # comparação
        mat = sum(Decimal(p) * Decimal(c) for n, t, u_, p, c, o in LINHAS if t in ('MATERIAL', 'EQUIPAMENTO'))
        mo = sum(Decimal(p) * Decimal(c) for n, t, u_, p, c, o in LINHAS if t == 'MAO_OBRA')
        print(f'Serviço criado: "{SVC}"  ({len(LINHAS)} insumos)\n')
        print(f'{"":32} {"REAL (Fundação)":>16} {"VERBA 1.17":>14} {"gap":>14}')
        print(f'{"Material/insumos":32} {float(mat):>16,.2f} {float(VERBA_MAT):>14,.2f} {float(mat-VERBA_MAT):>14,.2f}')
        print(f'{"Mão de obra":32} {float(mo):>16,.2f} {float(VERBA_MO):>14,.2f} {float(mo-VERBA_MO):>14,.2f}')
        print(f'{"TOTAL (só fundação)":32} {float(mat+mo):>16,.2f} {float(VERBA_MAT+VERBA_MO):>14,.2f} {float((mat+mo)-(VERBA_MAT+VERBA_MO)):>14,.2f}')


if __name__ == '__main__':
    main()
