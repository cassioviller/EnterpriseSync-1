"""Validação dupla do orçamento Baia REV10.

Confronta, item a item (1.1–1.17), os totais da aba 'Proposta Comercial' contra:
  (a) a consistência interna da própria planilha (J deve ser H+I);
  (b) o 1.17 decomposto no catálogo do sistema (serviços 'Obra Baia REV10').

Revela o R$128k fantasma do item 1.3 (material Stain contado global em H mas
×161 m² em J) e recompõe o total com o 1.17 real decomposto.

Fonte dos valores: leitura direta da planilha (data_only) — ver scripts de
extração. Não altera a planilha.
"""
from decimal import Decimal
from app import app
from models import Servico, ComposicaoServico, PrecoBaseInsumo, Usuario

# cod, unidade, qtd, H(mat_tot planilha), I(mo_tot planilha), J(total planilha), obs/flag
ITENS = [
    ('1.1',  'vb',  1,      '331345.50', '153300.00', '484645.50', ''),
    ('1.2',  'm²',  1173,   '0.00',      '41055.00',  '41055.00',  ''),
    ('1.3',  'm²',  161,    '800.00',    '5635.00',   '134435.00', '🔴 J usa Stain ×161; H usa global'),
    ('1.4',  'un',  48,     '6000.00',   '16800.00',  '22800.00',  ''),
    ('1.5',  'm²',  900,    '0.00',      '40500.00',  '40500.00',  ''),
    ('1.6',  'm²',  660,    '0.00',      '29700.00',  '29700.00',  ''),
    ('1.7',  'vb',  900,    '0.00',      '40500.00',  '40500.00',  '⚠️ un=vb com qtd em m²'),
    ('1.8',  'm²',  660,    '800.00',    '19800.00',  '20600.00',  ''),
    ('1.9',  'vb',  32,     '0.00',      '18181.82',  '18181.82',  '⚠️ custo base 44, vende 32'),
    ('1.10', 'vb',  1,      '56544.00',  '15010.00',  '71554.00',  ''),
    ('1.11', 'm²',  40,     '0.00',      '9200.00',   '9200.00',   ''),
    ('1.12', 'un',  1,      '6910.00',   '6500.00',   '13410.00',  '⚠️ 12 pts vs 24 baias+pilares'),
    ('1.13', 'm²',  1173,   '0.00',      '99705.00',  '99705.00',  ''),
    ('1.14', 'un',  24,     '2400.00',   '10800.00',  '13200.00',  ''),
    ('1.15', 'un',  24,     '800.00',    '9600.00',   '10400.00',  ''),
    ('1.16', 'un',  24,     '867.10',    '2400.00',   '3267.10',   '⚠️ material contado 1×, não ×24'),
    # 1.17 entra à parte (decomposto do catálogo)
]
J27_PLANILHA = Decimal('1145717.42')
VERBA_117 = Decimal('92564.00')


def custo_117_decomposto(aid):
    """Soma o custo dos serviços decompostos do 1.17 no catálogo."""
    svcs = Servico.query.filter(Servico.admin_id == aid,
                                Servico.categoria == 'Obra Baia REV10',
                                Servico.nome.like('%1.17%')).all()
    total = Decimal('0'); detalhe = []
    for s in svcs:
        sub = Decimal('0')
        for comp in ComposicaoServico.query.filter_by(servico_id=s.id).all():
            preco = PrecoBaseInsumo.query.filter_by(insumo_id=comp.insumo_id, vigencia_fim=None).first()
            if preco:
                sub += Decimal(str(preco.valor)) * Decimal(str(comp.coeficiente))
        detalhe.append((s.nome, sub)); total += sub
    return total, sorted(detalhe)


def main():
    with app.app_context():
        u = Usuario.query.filter_by(tipo_usuario='ADMIN').first() or Usuario.query.first()
        aid = u.id

        print('=' * 92)
        print('VALIDAÇÃO DUPLA — Orçamento Baia REV10 (custo)')
        print('=' * 92)
        print(f'{"item":5}{"qtd":>7} {"H mat":>13}{"I M.O.":>13}{"J planilha":>14}{"H+I calc":>14}  status')
        print('-' * 92)

        soma_h = soma_i = soma_j = soma_hi = Decimal('0')
        divergencias = []
        for cod, un, qtd, h, i, j, flag in ITENS:
            H, I, J = Decimal(h), Decimal(i), Decimal(j)
            HI = H + I
            dif = J - HI
            status = 'OK' if abs(dif) < Decimal('0.5') else f'🔴 J-({"H+I"})={float(dif):,.0f}'
            if abs(dif) >= Decimal('0.5'):
                divergencias.append((cod, dif, flag))
            print(f'{cod:5}{qtd:>7} {float(H):>13,.2f}{float(I):>13,.2f}{float(J):>14,.2f}{float(HI):>14,.2f}  {status}{("  "+flag) if flag else ""}')
            soma_h += H; soma_i += I; soma_j += J; soma_hi += HI

        # 1.17
        print('-' * 92)
        c117, det117 = custo_117_decomposto(aid)
        print(f'{"1.17":5}{1:>7} {"— verba —":>13}{"":>13}{float(VERBA_117):>14,.2f}{float(c117):>14,.2f}  decomposto (catálogo)')
        for nome, sub in det117:
            print(f'        ↳ {nome:48} {float(sub):>12,.2f}')

        print('=' * 92)
        # totais
        soma_j_total = soma_j + VERBA_117       # como na planilha (com verba 1.17)
        soma_hi_total = soma_hi + VERBA_117     # consistente (H+I), ainda com verba 1.17
        soma_decomp = soma_hi + c117            # consistente + 1.17 decomposto

        print(f'{"TOTAL planilha (J27, com verba 1.17)":52} R$ {float(soma_j_total):>14,.2f}')
        print(f'{"  confere com J27 da planilha?":52}    {"SIM ✅" if abs(soma_j_total - J27_PLANILHA) < 1 else "NÃO ❌ "+str(float(soma_j_total - J27_PLANILHA))}')
        print(f'{"TOTAL consistente (ΣH+ΣI, corrige 1.3)":52} R$ {float(soma_hi_total):>14,.2f}')
        print(f'{"  → fantasma do 1.3 removido":52} R$ {float(soma_j_total - soma_hi_total):>14,.2f}')
        print(f'{"TOTAL validado (consistente + 1.17 decomposto)":52} R$ {float(soma_decomp):>14,.2f}')
        print()
        print('Divergências internas da planilha (J ≠ H+I):')
        for cod, dif, flag in divergencias:
            print(f'  {cod}: R$ {float(dif):>12,.2f}   {flag}')
        if not divergencias:
            print('  (nenhuma)')


if __name__ == '__main__':
    main()
