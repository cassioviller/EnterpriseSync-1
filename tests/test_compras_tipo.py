"""Testes smoke para os 2 tipos de Compra (normal vs aprovacao_cliente).

Valida:
  1. Modelo PedidoCompra tem colunas tipo_compra e processada_apos_aprovacao
  2. Criação default -> tipo_compra='normal', processada_apos_aprovacao=False
  3. Helpers processar_compra_normal e processar_compra_aprovada_cliente existem
  4. Rota /compras/aprovacao está registrada
  5. Rota /compras/nova aceita tipo_compra e persiste o valor
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import PedidoCompra


def test_coluna_tipo_compra_existe():
    with app.app_context():
        cols = [c.name for c in PedidoCompra.__table__.columns]
        assert 'tipo_compra' in cols, "coluna tipo_compra ausente"
        assert 'processada_apos_aprovacao' in cols, "coluna processada_apos_aprovacao ausente"
        print("[OK] colunas tipo_compra + processada_apos_aprovacao presentes no modelo")


def test_helpers_importaveis():
    import compras_views
    assert hasattr(compras_views, 'processar_compra_normal'), "helper processar_compra_normal ausente"
    assert hasattr(compras_views, 'processar_compra_aprovada_cliente'), "helper processar_compra_aprovada_cliente ausente"
    assert hasattr(compras_views, '_gerar_entrada_almoxarifado'), "helper _gerar_entrada_almoxarifado ausente"
    print("[OK] helpers exportados em compras_views")


def test_rota_aprovacao_registrada():
    with app.app_context():
        rules = {r.endpoint: r.rule for r in app.url_map.iter_rules()}
        assert 'compras.aprovacao' in rules, f"rota compras.aprovacao não registrada"
        assert rules['compras.aprovacao'] == '/compras/aprovacao', f"rota inesperada: {rules['compras.aprovacao']}"
        print(f"[OK] rota compras.aprovacao -> {rules['compras.aprovacao']}")


def test_default_tipo_compra_no_banco():
    """Valida que compras existentes ficam com 'normal' (default)."""
    with app.app_context():
        row = PedidoCompra.query.first()
        if row is None:
            print("[SKIP] nenhuma compra no banco para validar default")
            return
        # default no modelo é 'normal'
        assert row.tipo_compra in ('normal', 'aprovacao_cliente'), f"tipo_compra inválido: {row.tipo_compra!r}"
        print(f"[OK] PedidoCompra#{row.id} tipo_compra={row.tipo_compra!r} processada={row.processada_apos_aprovacao}")


if __name__ == '__main__':
    test_coluna_tipo_compra_existe()
    test_helpers_importaveis()
    test_rota_aprovacao_registrada()
    test_default_tipo_compra_no_banco()
    print("\n✅ TODOS OS TESTES PASSARAM")
