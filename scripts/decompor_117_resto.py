"""Decompõe o RESTANTE da verba do item 1.17 (Pacote complementar), além da
fundação (já feita em decompor_117_fundacao.py). O 1.17 lista 9 escopos, mas
aço/painelização, fechamentos e pintura stain JÁ são precificados nos itens
1.1, 1.5/1.6 e 1.8/1.15 — re-incluí-los contaria a proposta em dobro. Logo,
os escopos genuinamente NOVOS do 1.17 são:

  - Fundação ................. já feita (decompor_117_fundacao.py)
  - Infra Elétrica ........... contagem dos PROJETOS + SINAPI-SP 104473/104480
  - Infra Hidráulica ......... contagem dos PROJETOS + SINAPI-SP 104678
  - Isolamento (lã de rocha) . área do Memorial; preço de mercado 🧩
  - Forro PVC preto .......... área Memorial FORRO; SINAPI 96111  🧩

Cria os insumos + um serviço decomposto por escopo (idempotente) e imprime a
reconciliação com a verba 1.17 (mat R$52.322 + M.O. R$40.242 = R$92.564).
"""
from decimal import Decimal
from datetime import date
from app import app, db
from models import Usuario, Servico, Insumo, ComposicaoServico, PrecoBaseInsumo

CATEGORIA = 'Obra Baia REV10'

# serviço -> (unidade_servico, [ (insumo, tipo, un, preco, coef, obs) ])
SERVICOS = {
    # Firmado pela ANÁLISE DOS PROJETOS (DETALHE_ESTUDO_BAIAS, BLOCO 1 E 2, IMPLANTACAO):
    # 24 baias, cada uma com 1 ponto de luz no teto + 1 ponto água fria + 1 ponto esgoto
    # (bebedouro). NÃO há bloco de banheiros nas baias -> louças/metais do Memorial são
    # "NÃO INCLUSOS" / da cabana existente. Substitui a verba Vereda por contagem SINAPI-SP.
    'Infra Elétrica (1.17)': ('vb', [
        # 24 luz baias + ~20 luz pilares (infra, SINAPI 104473 R$203,40/pt) + 8 tomadas
        # (104480 ~R$155) + 8 refletores LED ext + 2 quadros/alimentador. ~mat 63% / M.O. 37%.
        ('Material infra elétrica',   'MATERIAL', 'vb', '11000.00', '1', '44 pts ilum+tomadas+refletor+quadro; SINAPI 104473/104480-SP (projetos)'),
        ('M.O. infra elétrica',       'MAO_OBRA', 'vb', '6400.00',  '1', 'instalação dos 44 pts+quadro; SINAPI-SP parcela M.O.'),
    ]),
    'Infra Hidráulica (1.17)': ('vb', [
        # 24 drenos/esgoto baias (104678 ~R$135/pt) + rede água fria aos 24 bebedouros
        # (~130m tubo + ramais + registros). Os 24 TERMINAIS de água fria estão no item 1.16.
        ('Material infra hidráulica', 'MATERIAL', 'vb', '6300.00', '1', '24 esgoto/dreno + rede AF ~130m; SINAPI 104678-SP (AF terminal=1.16)'),
        ('M.O. infra hidráulica',     'MAO_OBRA', 'vb', '4200.00', '1', 'instalação rede esgoto+água fria; SINAPI-SP parcela M.O.'),
    ]),
    'Isolamento lã de rocha (1.17)': ('m2', [
        # Painel lã de rocha 32kg/m³ 1200x600x50mm (0,72 m²/pç). Área = FORRO 196,14 m² (Memorial!E26).
        # Preço corrigido p/ mercado: pct 4,32 m² ~R$104 -> ~R$25/m² (antes R$48, 2x alto).
        ('Painel lã de rocha 32kg/m³ 50mm', 'MATERIAL', 'm2', '25.00', '196.142', 'mercado ~R$25/m² (pct 4,32m² @ ~R$104) 🧩'),
        ('M.O. instalação isolamento',      'MAO_OBRA', 'm2', '10.00', '196.142', 'estimado 🧩'),
    ]),
    'Forro PVC preto (1.17)': ('m2', [
        # Alinhado ao SINAPI 96111 (forro PVC) = R$66,39/m² all-in, ref 03/2026 não desonerado.
        ('Forro PVC preto (material)', 'MATERIAL', 'm2', '42.00', '196.142', 'SINAPI 96111 R$66,39/m² all-in 🧩'),
        ('M.O. instalação forro PVC',  'MAO_OBRA', 'm2', '24.00', '196.142', 'SINAPI 96111 (parcela M.O.) 🧩'),
    ]),
}

VERBA_MAT = Decimal('52322')
VERBA_MO = Decimal('40242')
FUNDACAO_REAL = Decimal('121000')  # do decompor_117_fundacao.py (mat+M.O. ~R$121k)


def main():
    with app.app_context():
        u = Usuario.query.filter_by(tipo_usuario='ADMIN').first() or Usuario.query.first()
        aid = u.id

        resumo = []  # (nome_servico, mat, mo)
        for svc_nome, (un_svc, linhas) in SERVICOS.items():
            # upsert insumos + preço vigente
            ins_by_nome = {}
            for nome, tipo, un, preco, _coef, _obs in linhas:
                ins = Insumo.query.filter_by(admin_id=aid, nome=nome).first()
                if not ins:
                    ins = Insumo(admin_id=aid, nome=nome, tipo=tipo, unidade=un)
                    db.session.add(ins); db.session.flush()
                pb = PrecoBaseInsumo.query.filter_by(insumo_id=ins.id, vigencia_fim=None).first()
                if not pb:
                    db.session.add(PrecoBaseInsumo(admin_id=aid, insumo_id=ins.id,
                                   valor=Decimal(preco), vigencia_inicio=date(2026, 1, 1)))
                else:
                    pb.valor = Decimal(preco)  # atualiza p/ valor revisado (SINAPI/mercado)
                ins_by_nome[nome] = ins
            db.session.flush()

            # upsert serviço + composição
            svc = Servico.query.filter_by(admin_id=aid, nome=svc_nome).first()
            if not svc:
                svc = Servico(admin_id=aid, nome=svc_nome, categoria=CATEGORIA, unidade_medida=un_svc)
                db.session.add(svc); db.session.flush()
            for nome, tipo, un, preco, coef, obs in linhas:
                ins = ins_by_nome[nome]
                comp = ComposicaoServico.query.filter_by(servico_id=svc.id, insumo_id=ins.id).first()
                if not comp:
                    comp = ComposicaoServico(admin_id=aid, servico_id=svc.id, insumo_id=ins.id)
                    db.session.add(comp)
                comp.coeficiente = Decimal(coef); comp.unidade = un; comp.observacao = obs

            mat = sum(Decimal(p) * Decimal(c) for n, t, u_, p, c, o in linhas if t in ('MATERIAL', 'EQUIPAMENTO'))
            mo = sum(Decimal(p) * Decimal(c) for n, t, u_, p, c, o in linhas if t == 'MAO_OBRA')
            resumo.append((svc_nome, mat, mo))
        db.session.commit()

        # ---- reconciliação ----
        print('Serviços do RESTANTE do 1.17 criados:\n')
        print(f'{"Escopo":34}{"Material":>14}{"M.O.":>14}{"Total":>14}')
        print('-' * 76)
        tot_mat = tot_mo = Decimal('0')
        for nome, mat, mo in resumo:
            print(f'{nome:34}{float(mat):>14,.2f}{float(mo):>14,.2f}{float(mat+mo):>14,.2f}')
            tot_mat += mat; tot_mo += mo
        print('-' * 76)
        print(f'{"SUBTOTAL (sem fundação)":34}{float(tot_mat):>14,.2f}{float(tot_mo):>14,.2f}{float(tot_mat+tot_mo):>14,.2f}')
        print(f'{"+ Fundação (já decomposta)":34}{"":>14}{"":>14}{float(FUNDACAO_REAL):>14,.2f}')
        real_total = tot_mat + tot_mo + FUNDACAO_REAL
        print(f'{"= 1.17 REAL (escopos novos)":34}{"":>14}{"":>14}{float(real_total):>14,.2f}')
        print()
        verba = VERBA_MAT + VERBA_MO
        print(f'Verba 1.17 na proposta (custo): R$ {float(verba):,.2f}  (mat {float(VERBA_MAT):,.0f} + M.O. {float(VERBA_MO):,.0f})')
        print(f'Gap (real - verba):             R$ {float(real_total - verba):,.2f}  '
              f'({float((real_total/verba - 1) * 100):.0f}% acima)')
        print()
        print('Escopos do 1.17 NÃO recadastrados (já precificados em outros itens — não duplicar):')
        print('  - Aço engenheirado / painelização .... item 1.1')
        print('  - Fechamento interno/externo ......... itens 1.5 / 1.6')
        print('  - Pintura stain madeira .............. itens 1.8 / 1.15')
        print('NÃO inclusos (cliente): telha shingle, louças, metais, madeiras, pré-moldados, esquadrias.')


if __name__ == '__main__':
    main()
