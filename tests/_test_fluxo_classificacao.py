"""
Teste direto (sem browser) da classificação da importação do Fluxo de Caixa.

Roda dentro do app-context, chama ImportacaoFluxoCaixa.processar() sobre a
planilha real e tabula:
  - contagem dos 4 buckets (entradas / saidas_auto / saidas_manual / ignorados)
  - distribuição de categoria_nome (qualidade do _classificar_categoria_nomeada)
  - quanto caiu em "Outras Saídas" / "Outros Recebimentos" (= não classificado)

NÃO grava nada — só processar(), não importar().

Uso:  python tests/_test_fluxo_classificacao.py
"""
import os
import sys
from collections import Counter
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

XLSX = os.environ.get(
    "PW_XLSX",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "1. FLUXO DE CAIXA_Veks Engenharia.xlsx"),
)


def _parse_date(s):
    if not s:
        return None
    y, m, d = (int(x) for x in s.split("-"))
    return date(y, m, d)


# Período de filtro (ISO yyyy-mm-dd). Default: jan→mar 2026.
DATA_INICIO = _parse_date(os.environ.get("PW_DATA_INICIO", "2026-01-01"))
DATA_FIM = _parse_date(os.environ.get("PW_DATA_FIM", "2026-03-31"))
AMOSTRA_N = int(os.environ.get("PW_AMOSTRA_N", "40"))


def _resolver_admin_id():
    """admin_id do tenant alfa (login admin_alfa)."""
    from models import Usuario
    u = (Usuario.query.filter_by(username="admin_alfa").first()
         or Usuario.query.filter_by(email="admin_alfa").first())
    if not u:
        # fallback: primeiro admin
        u = Usuario.query.filter(Usuario.tipo_usuario.isnot(None)).first()
    # admin_id é o próprio id do admin no multi-tenant
    return getattr(u, "admin_id", None) or u.id


def main():
    from app import app
    from services.importacao_excel import ImportacaoFluxoCaixa

    with app.app_context():
        admin_id = _resolver_admin_id()
        print(f"[i] admin_id={admin_id}  arquivo={os.path.basename(XLSX)}")
        print(f"[i] periodo filtro: {DATA_INICIO} -> {DATA_FIM}")

        res = ImportacaoFluxoCaixa().processar(
            XLSX, admin_id, data_inicio=DATA_INICIO, data_fim=DATA_FIM)

        entradas = res.get("entradas", [])
        saidas_auto = res.get("saidas_auto", [])
        saidas_manual = res.get("saidas_manual", [])
        ignorados = res.get("ignorados", [])
        transf = res.get("transferencias", [])

        print("\n=== BUCKETS ===")
        print(f"  entradas        : {len(entradas)}")
        print(f"  saidas_auto     : {len(saidas_auto)}")
        print(f"  saidas_manual   : {len(saidas_manual)}")
        print(f"  ignorados       : {len(ignorados)}")
        print(f"  transferencias  : {len(transf)}")
        print(f"  periodo         : {res.get('periodo_str')}")

        # distribuição categoria_nome
        todas_saidas = saidas_auto + saidas_manual
        dist_s = Counter(r.get("categoria_nome") or "(sem nome)" for r in todas_saidas)
        dist_e = Counter(r.get("categoria_nome") or "(sem nome)" for r in entradas)

        def _relatorio(titulo, dist, genericos):
            total = sum(dist.values())
            nao = sum(dist.get(g, 0) for g in genericos)
            print(f"\n=== CATEGORIAS — {titulo} ({total}) ===")
            for nome, n in dist.most_common():
                flag = "   <-- genérico" if nome in genericos else ""
                print(f"  {n:>4}  {nome}{flag}")
            if total:
                taxa = 100 * (total - nao) / total
                print(f"  -> classificação específica: "
                      f"{total - nao}/{total} = {taxa:.1f}%")

        _relatorio("SAÍDAS", dist_s, {"Outras Saídas", "(sem nome)"})
        _relatorio("ENTRADAS", dist_e, {"Outros Recebimentos", "(sem nome)"})

        # bancos detectados nas transferências
        com_banco = sum(1 for t in transf
                        if t.get("banco_origem_id") or t.get("banco_destino_id"))
        print(f"\n=== TRANSFERÊNCIAS ===")
        print(f"  {com_banco}/{len(transf)} com banco origem/destino detectado")

        # amostra de saídas que caíram em genérico (para inspeção)
        genericas = [r for r in todas_saidas
                     if (r.get("categoria_nome") in (None, "Outras Saídas"))]
        # Diagnóstico do piso: quantas genéricas têm descrição "opaca"
        # (vazia, "???"/"????", ou só números/pontuação) = irreclassificável por texto.
        def _opaca(r):
            d = (r.get("descricao") or "").strip()
            if not d:
                return True
            limpo = d.replace("?", "").replace(" ", "")
            if not limpo:
                return True
            # só dígitos, vírgulas, pontos, +, -, /  → sem palavra
            if all(c.isdigit() or c in ".,+-/ " for c in d):
                return True
            return False
        n_opaca = sum(1 for r in genericas if _opaca(r))
        n_texto = len(genericas) - n_opaca
        print(f"\n=== PISO DO GENÉRICO ===")
        print(f"  opacas (vazio/????/só números): {n_opaca}/{len(genericas)}")
        print(f"  com texto (ainda melhorável)  : {n_texto}/{len(genericas)}")

        if genericas:
            print(f"\n=== AMOSTRA 'Outras Saídas' com TEXTO (até {AMOSTRA_N}) ===")
            genericas = [r for r in genericas if not _opaca(r)]
            for r in genericas[:AMOSTRA_N]:
                d = (r.get("descricao") or "")[:60]
                f = (r.get("fornecedor") or "")[:25]
                print(f"  R$ {str(r.get('valor')):>11}  | {f:<25} | {d}")


if __name__ == "__main__":
    main()
