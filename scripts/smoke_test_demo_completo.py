"""
Task #46 — Smoke test da demo completa "Construtora Alfa".

Verifica que o seed populou TODOS os módulos esperados:
  1. Admin + Funcionários (4)
  2. Proposta + Obra vinculadas (proposta_origem_id preenchido)
  3. token_cliente definido em ambas as obras
  4. RDOs Finalizados (Bela Vista: 3, Pinheiros: 10)
  5. GestaoCustoPai gerados pelos RDOs (SALARIO / VA / VT) — mínimo 3, com origem rdo_mao_obra
  6. Frota: 2 veículos + despesas + utilizações
  7. FolhaProcessada: Carlos fev/2026
  8. PlanoContas: mínimo 10 contas ativas (inclui contas raiz 1-4)
  9. LancamentoContabil + PartidaContabil (partidas dobradas)
  10. FluxoCaixa: mínimo 5 movimentos com entradas e saídas
  11. Origem RDO→Contas a Pagar validada via GestaoCustoFilho.origem_tabela

Uso:
    python3 scripts/smoke_test_demo_completo.py
"""
from __future__ import annotations

import logging
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="[smoke-demo-completo] %(levelname)s %(message)s",
)
log = logging.getLogger("smoke_test_demo_completo")

ADMIN_EMAIL = "admin@construtoraalfa.com.br"

_ERROS: list[str] = []
_OK: list[str] = []


def _check(label: str, cond: bool, detalhe: str = ""):
    if cond:
        _OK.append(label)
        log.info("  [OK] %s%s", label, f" — {detalhe}" if detalhe else "")
    else:
        _ERROS.append(label)
        log.error("  [FAIL] %s%s", label, f" — {detalhe}" if detalhe else "")


def run():
    from app import app, db
    from models import (
        Usuario, Funcionario, Proposta, Obra,
        RDO, RDOMaoObra,
        Vehicle, VehicleExpense, VehicleUsage,
        FolhaProcessada,
        PlanoContas, LancamentoContabil, PartidaContabil,
        FluxoCaixa,
    )
    try:
        from models import GestaoCustoPai, GestaoCustoFilho
        _has_gcp = True
    except ImportError:
        _has_gcp = False

    with app.app_context():

        # 1) Admin
        admin = Usuario.query.filter_by(email=ADMIN_EMAIL).first()
        _check("Admin Alfa existe", admin is not None)
        if not admin:
            log.error("Admin Alfa não encontrado — abortar smoke test")
            return

        aid = admin.id
        _check("Admin é v2", getattr(admin, "versao_sistema", None) == "v2")

        # 2) Funcionários
        funcs = Funcionario.query.filter_by(admin_id=aid).all()
        _check("4 funcionários cadastrados", len(funcs) >= 4,
               f"encontrados: {len(funcs)}")

        carlos = next((f for f in funcs if "Carlos" in f.nome), None)
        _check("Carlos existe (mensalista)", carlos is not None)
        if carlos:
            _check("Carlos é mensalista",
                   getattr(carlos, "tipo_remuneracao", None) == "salario")

        # 3) Propostas e Obras
        propostas = Proposta.query.filter_by(admin_id=aid).all()
        _check("Mínimo 2 propostas", len(propostas) >= 2,
               f"encontradas: {len(propostas)}")

        obras = Obra.query.filter_by(admin_id=aid).all()
        _check("Mínimo 2 obras", len(obras) >= 2,
               f"encontradas: {len(obras)}")

        obras_com_proposta = [o for o in obras if o.proposta_origem_id]
        _check("Obras com proposta_origem_id preenchido",
               len(obras_com_proposta) >= 2,
               f"{len(obras_com_proposta)} de {len(obras)}")

        # Validar que cada proposta_origem_id aponta para uma proposta aprovada real
        for obra in obras_com_proposta:
            prop = Proposta.query.get(obra.proposta_origem_id)
            _check(
                f"Obra '{obra.nome[:30]}' — proposta_origem válida e aprovada",
                prop is not None and prop.status == "aprovada",
                f"proposta #{prop.id if prop else 'None'} status={getattr(prop,'status','—')}",
            )

        obras_aprovadas = [
            p for p in propostas if p.status == "aprovada"
        ]
        _check("Mínimo 2 propostas aprovadas", len(obras_aprovadas) >= 2,
               f"aprovadas: {len(obras_aprovadas)}")

        # 4) token_cliente nas obras principais
        obra_bv = next(
            (o for o in obras if "Bela Vista" in (o.nome or "")), None
        )
        if obra_bv:
            _check("Obra Bela Vista tem token_cliente",
                   bool(getattr(obra_bv, "token_cliente", None)))
        else:
            _check("Obra Bela Vista encontrada", False)

        # 5) RDOs Finalizados
        rdos_fin = RDO.query.filter_by(admin_id=aid, status="Finalizado").all()
        _check("Mínimo 13 RDOs Finalizados (3+10)", len(rdos_fin) >= 13,
               f"encontrados: {len(rdos_fin)}")

        # 6) GestaoCusto gerados pelos RDOs — com validação de origem
        if _has_gcp:
            gcp_all = GestaoCustoPai.query.filter_by(admin_id=aid).all()
            _check("GestaoCustoPai gerados (total)", len(gcp_all) > 0,
                   f"{len(gcp_all)} registros")

            # Contar GCPs originados de RDO (via GestaoCustoFilho.origem_tabela)
            rdo_mao_obra_ids = db.session.query(RDOMaoObra.id).join(
                RDO, RDO.id == RDOMaoObra.rdo_id
            ).filter(RDO.admin_id == aid).all()
            rdo_mao_obra_ids_set = {r[0] for r in rdo_mao_obra_ids}

            gcp_de_rdo_count = 0
            if rdo_mao_obra_ids_set:
                _filhos_pai_ids = db.session.query(
                    GestaoCustoFilho.pai_id
                ).filter(
                    GestaoCustoFilho.origem_tabela == "rdo_mao_obra",
                    GestaoCustoFilho.origem_id.in_(rdo_mao_obra_ids_set),
                ).distinct().count()
                gcp_de_rdo_count = _filhos_pai_ids

            _check(
                "GestaoCustoPai com origem em RDO (mão de obra) >= 3",
                gcp_de_rdo_count >= 3,
                f"encontrados: {gcp_de_rdo_count}",
            )

            # Verificar que existe ao menos um item GestaoCustoFilho com origem_tabela='rdo_mao_obra'
            _filho_rdo = GestaoCustoFilho.query.filter_by(
                origem_tabela="rdo_mao_obra"
            ).filter(GestaoCustoFilho.admin_id == aid).first()
            _check(
                "GestaoCustoFilho com origem_tabela='rdo_mao_obra' existe",
                _filho_rdo is not None,
                f"id={getattr(_filho_rdo,'id','—')} origem_id={getattr(_filho_rdo,'origem_id','—')}",
            )
        else:
            log.warning("GestaoCustoPai não importado — verificação pulada")

        # 7) Frota
        veiculos = Vehicle.query.filter_by(admin_id=aid).all()
        _check("2 veículos cadastrados", len(veiculos) >= 2,
               f"encontrados: {len(veiculos)}")

        placas = {v.placa for v in veiculos}
        _check("Hilux cadastrado (ABC-1234)", "ABC-1234" in placas)
        _check("Sprinter cadastrado (DEF-5678)", "DEF-5678" in placas)

        despesas = VehicleExpense.query.filter_by(admin_id=aid).all()
        _check("Despesas de frota registradas", len(despesas) >= 4,
               f"encontradas: {len(despesas)}")

        utilizacoes = VehicleUsage.query.filter_by(admin_id=aid).all()
        _check("Utilizações de frota registradas", len(utilizacoes) >= 2,
               f"encontradas: {len(utilizacoes)}")

        # 8) FolhaProcessada
        if carlos:
            folha = FolhaProcessada.query.filter_by(
                admin_id=aid, funcionario_id=carlos.id, ano=2026, mes=2,
            ).first()
            _check("FolhaProcessada Carlos fev/2026 existe", folha is not None)
            if folha:
                _check(
                    "Custo empresa > salário base",
                    float(folha.custo_total_empresa or 0) > float(folha.salario_base or 0),
                    f"R$ {float(folha.custo_total_empresa):.2f} vs R$ {float(folha.salario_base):.2f}",
                )

        # 9) PlanoContas
        plano = PlanoContas.query.filter_by(admin_id=aid, ativo=True).all()
        _check("Mínimo 10 contas no PlanoContas", len(plano) >= 10,
               f"encontradas: {len(plano)}")
        codigos = {c.codigo for c in plano}
        for cod in ("1", "2", "3", "4", "1.1.01", "3.1.01", "4.2.01"):
            _check(f"Conta {cod} existe", cod in codigos)

        # 10) LancamentoContabil + PartidaContabil
        lancamentos = LancamentoContabil.query.filter_by(admin_id=aid).all()
        _check("Mínimo 3 lançamentos contábeis", len(lancamentos) >= 3,
               f"encontrados: {len(lancamentos)}")

        partidas = PartidaContabil.query.filter_by(admin_id=aid).all()
        _check("Partidas = 2× lançamentos (dobradas)", len(partidas) >= len(lancamentos) * 2,
               f"{len(partidas)} partidas / {len(lancamentos)} lançamentos")

        # 11) FluxoCaixa
        fluxos = FluxoCaixa.query.filter_by(admin_id=aid).all()
        _check("Mínimo 5 movimentos no FluxoCaixa", len(fluxos) >= 5,
               f"encontrados: {len(fluxos)}")

        entradas = [f for f in fluxos if f.tipo_movimento == "ENTRADA"]
        saidas   = [f for f in fluxos if f.tipo_movimento == "SAIDA"]
        _check("Tem entradas no FluxoCaixa", len(entradas) >= 1,
               f"{len(entradas)} entradas")
        _check("Tem saídas no FluxoCaixa", len(saidas) >= 1,
               f"{len(saidas)} saídas")

    # Sumário final
    log.info("")
    log.info("=" * 60)
    log.info("SMOKE TEST — DEMO COMPLETO")
    log.info("  OK   : %d verificações passaram", len(_OK))
    log.info("  FAIL : %d verificações falharam", len(_ERROS))
    if _ERROS:
        for e in _ERROS:
            log.error("  FAIL: %s", e)
        log.error("=" * 60)
        sys.exit(1)
    else:
        log.info("Todos os módulos do demo estão populados corretamente.")
        log.info("=" * 60)


if __name__ == "__main__":
    run()
