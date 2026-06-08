#!/usr/bin/env python3
"""Conferência pós-deploy do Bloco 3 (BDI completo padrão TCU).

Roda contra o banco/código já deployados e valida o gate de deploy:

  1. Migração 189 registrada como `success` em migration_history.
  2. As 12 colunas de BDI existem (7 na empresa + 5 na proposta).
  3. A fórmula deployada confere (não-disrupção BDI=0 e exemplo TCU).
  4. resolver_aliquotas() roda sem erro contra um serviço real (se houver).

Uso (na máquina/ambiente de produção, com o venv do app):

    python scripts/conferir_deploy_bloco3.py

Saída: bloco PASS/FAIL por item + resumo. Exit code 0 = tudo verde, 1 = falha.
Apenas leitura — não altera dados.
"""
import os
import sys
from decimal import Decimal

# Permite rodar a partir da raiz do projeto.
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

RESULTADOS = []


def checar(cond, descricao, detalhe=''):
    RESULTADOS.append((bool(cond), descricao, detalhe))
    marca = 'PASS' if cond else 'FALHA'
    linha = f'  [{marca}] {descricao}'
    if detalhe:
        linha += f' — {detalhe}'
    print(linha)
    return bool(cond)


def main():
    from app import app, db
    from sqlalchemy import text
    from services.pricing import Aliquotas, precificar, resolver_aliquotas

    print('=' * 70)
    print('Conferência pós-deploy — Bloco 3 (BDI completo TCU)')
    print('=' * 70)

    with app.app_context():
        # ---- 1. Migração 189 = success -----------------------------------
        with db.engine.begin() as c:
            row = c.execute(text(
                "SELECT status FROM migration_history WHERE migration_number = 189"
            )).fetchone()
        checar(row is not None and row[0] == 'success',
               'Migração 189 registrada como success',
               f'status={row[0] if row else "AUSENTE"}')

        # ---- 2. Colunas de BDI presentes ---------------------------------
        with db.engine.begin() as c:
            n_emp = c.execute(text("""
                SELECT count(*) FROM information_schema.columns
                WHERE table_name = 'configuracao_empresa' AND column_name LIKE 'bdi%'
            """)).scalar()
            n_prop = c.execute(text("""
                SELECT count(*) FROM information_schema.columns
                WHERE table_name = 'propostas_comerciais' AND column_name LIKE 'bdi%'
            """)).scalar()
        checar(n_emp == 7, 'configuracao_empresa tem 7 colunas bdi*', f'encontradas={n_emp}')
        checar(n_prop == 5, 'propostas_comerciais tem 5 colunas bdi*', f'encontradas={n_prop}')

        # ---- 3. Fórmula deployada confere --------------------------------
        # Não-disrupção: BDI=0, T=15, L=5 → custo/(1-0,20) = 1250.
        r0 = precificar(Decimal('1000'), Aliquotas(t=Decimal('15'), l=Decimal('5')))
        checar(r0.preco == Decimal('1250'),
               'Não-disrupção: BDI=0 reduz à fórmula atual',
               f'preco={r0.preco:f} (esperado 1250)')

        # Exemplo TCU: ΣBDI=25, T=15, L=5 → preço 1562,50; lucro 78,125 (L×preço).
        rt = precificar(Decimal('1000'), Aliquotas(
            t=Decimal('15'), l=Decimal('5'), ac=Decimal('20'),
            s=Decimal('1'), r=Decimal('1'), g=Decimal('1'), df=Decimal('2')))
        checar(rt.preco == Decimal('1562.50'),
               'Exemplo TCU: preço 1562,50', f'preco={rt.preco}')
        checar(rt.lucro == Decimal('78.125'),
               'D2: lucro = L×preço (não preço−custo)', f'lucro={rt.lucro}')
        invariante = rt.custo_direto + rt.indiretos + rt.tributos + rt.lucro
        checar(invariante == rt.preco,
               'Invariante custo+indiretos+tributos+lucro = preço',
               f'soma={invariante}')

        # Guarda-corpo: T+L ≥ bloqueio default (90) → preço 0, status bloqueio.
        rb = precificar(Decimal('1000'), Aliquotas(t=Decimal('50'), l=Decimal('45')))
        checar(rb.status == 'bloqueio' and rb.preco == Decimal('0'),
               'Guarda-corpo bloqueia T+L ≥ 90%', f'status={rb.status}')

        # ---- 4. resolver_aliquotas() em serviço real ---------------------
        try:
            from models import Servico
            svc = Servico.query.first()
            if svc is None:
                checar(True, 'resolver_aliquotas (sem serviço no banco — skip)', 'skip')
            else:
                a = resolver_aliquotas(svc)
                ok = all(getattr(a, k) is not None for k in
                         ('t', 'l', 'ac', 's', 'r', 'g', 'df', 'tl_aviso', 'tl_bloqueio'))
                checar(ok, 'resolver_aliquotas roda em serviço real',
                       f'servico_id={svc.id} T={a.t} L={a.l} bloqueio={a.tl_bloqueio}')
        except Exception as e:
            checar(False, 'resolver_aliquotas roda em serviço real', repr(e))

    # ---- Resumo ----------------------------------------------------------
    total = len(RESULTADOS)
    falhas = sum(1 for ok, _, _ in RESULTADOS if not ok)
    print('=' * 70)
    print(f'RESULTADO: {total - falhas}/{total} verde' +
          (f' — {falhas} FALHA(S)' if falhas else ' — gate OK'))
    print('=' * 70)
    sys.exit(1 if falhas else 0)


if __name__ == '__main__':
    main()
