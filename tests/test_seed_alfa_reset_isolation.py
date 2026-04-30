"""Task #55 — regressão de isolamento multi-tenant no `seed_demo_alfa.py`.

Garante que `_reset_dataset()` NUNCA mexa em registros contábeis
(`partida_contabil`, `lancamento_contabil`) de OUTROS tenants. Cria um
tenant fixture com seu próprio plano de contas + lançamento + partida,
roda o reset do Alfa e verifica que nada do outro tenant foi tocado.
"""
import os
import sys
import uuid
import unittest
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402
from sqlalchemy import text  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from scripts.seed_demo_alfa import _reset_dataset  # noqa: E402


class TestResetAlfaPreservaOutrosTenants(unittest.TestCase):
    """Reset do tenant Alfa não pode tocar dados contábeis de terceiros."""

    @classmethod
    def setUpClass(cls):
        cls.ctx = app.app_context()
        cls.ctx.push()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.pop()

    def _suffix(self):
        return uuid.uuid4().hex[:10]

    def _ensure_alfa_admin_existe(self):
        """Garante que o admin Alfa exista para que `_reset_dataset()`
        execute o caminho real de reset (não apenas no-op).

        O test não precisa do dataset completo do seed — apenas do
        usuário admin com username `admin_alfa`, que é o que o
        `_reset_dataset()` localiza para mirar.
        """
        from models import Usuario, TipoUsuario

        existente = db.session.execute(text(
            "SELECT id FROM usuario WHERE username='admin_alfa'"
        )).scalar()
        if existente:
            return existente
        alfa = Usuario(
            username="admin_alfa",
            email="admin@construtoraalfa.com.br",
            nome="Admin Alfa (test fixture)",
            password_hash=generate_password_hash("Alfa@2026"),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema="v2",
        )
        db.session.add(alfa)
        db.session.flush()
        return alfa.id

    def test_reset_alfa_nao_remove_partida_de_outro_tenant(self):
        """Cria 2º tenant com plano_contas/lancamento/partida próprios.
        Garante que o admin Alfa existe para forçar o reset a EXECUTAR
        seu caminho completo (não no-op). Verifica COUNT preservado
        para o 2º tenant após o reset."""
        from models import Usuario, TipoUsuario

        # PRIMEIRO garante que o reset Alfa NÃO seja no-op.
        alfa_id = self._ensure_alfa_admin_existe()
        self.assertIsNotNone(alfa_id, "fixture admin Alfa não foi criado")

        s = self._suffix()
        outro = Usuario(
            username=f"outro_iso_{s}",
            email=f"outro_iso_{s}@test.local",
            nome=f"Outro Tenant Iso {s}",
            password_hash=generate_password_hash("Senha@2026"),
            tipo_usuario=TipoUsuario.ADMIN,
            ativo=True,
            versao_sistema="v2",
        )
        db.session.add(outro)
        db.session.flush()
        outro_id = outro.id

        # Plano de contas do OUTRO tenant — códigos únicos para evitar
        # colisão com o seed Alfa (o reset matcha por admin_id, então mesmo
        # códigos iguais não deveriam ser tocados — mas usamos códigos
        # únicos para isolamento total do experimento).
        codigo_a = f"9.9.{s[:3]}.001"
        codigo_b = f"9.9.{s[:3]}.002"
        db.session.execute(text(
            "INSERT INTO plano_contas (codigo, nome, tipo_conta, natureza, "
            "nivel, admin_id) VALUES "
            "(:c1, 'ATV TEST', 'ATIVO', 'DEVEDORA', 1, :a), "
            "(:c2, 'REC TEST', 'RECEITA', 'CREDORA', 1, :a)"
        ), {"c1": codigo_a, "c2": codigo_b, "a": outro_id})

        # Lancamento + partidas do OUTRO tenant
        lan_id = db.session.execute(text(
            "INSERT INTO lancamento_contabil "
            "(numero, data_lancamento, historico, valor_total, origem, admin_id) "
            "VALUES (9999, :d, 'TEST ISO', 100.00, 'TESTE', :a) "
            "RETURNING id"
        ), {"d": date.today(), "a": outro_id}).scalar()
        db.session.execute(text(
            "INSERT INTO partida_contabil "
            "(lancamento_id, conta_codigo, tipo_partida, valor, sequencia, admin_id) "
            "VALUES (:l, :c1, 'DEBITO', 100.00, 1, :a), "
            "(:l, :c2, 'CREDITO', 100.00, 2, :a)"
        ), {"l": lan_id, "c1": codigo_a, "c2": codigo_b, "a": outro_id})
        db.session.commit()

        # Snapshot ANTES
        before_partida = db.session.execute(text(
            "SELECT COUNT(*) FROM partida_contabil WHERE admin_id=:a"
        ), {"a": outro_id}).scalar()
        before_lan = db.session.execute(text(
            "SELECT COUNT(*) FROM lancamento_contabil WHERE admin_id=:a"
        ), {"a": outro_id}).scalar()
        before_plano = db.session.execute(text(
            "SELECT COUNT(*) FROM plano_contas WHERE admin_id=:a"
        ), {"a": outro_id}).scalar()
        self.assertEqual(before_partida, 2)
        self.assertEqual(before_lan, 1)
        self.assertEqual(before_plano, 2)

        # Roda reset do Alfa — pode ser no-op se Alfa não existe; o
        # importante é que nada do outro tenant seja afetado.
        try:
            _reset_dataset()
        except RuntimeError as e:
            # Se houver pollution cross-tenant pré-existente, o reset
            # aborta. Mesmo nesse caso, NADA do outro tenant pode ter
            # sido tocado (a pré-checagem rodou antes de qualquer DELETE).
            self.assertIn("cross-tenant", str(e).lower())

        # Snapshot DEPOIS — deve ser idêntico
        after_partida = db.session.execute(text(
            "SELECT COUNT(*) FROM partida_contabil WHERE admin_id=:a"
        ), {"a": outro_id}).scalar()
        after_lan = db.session.execute(text(
            "SELECT COUNT(*) FROM lancamento_contabil WHERE admin_id=:a"
        ), {"a": outro_id}).scalar()
        after_plano = db.session.execute(text(
            "SELECT COUNT(*) FROM plano_contas WHERE admin_id=:a"
        ), {"a": outro_id}).scalar()
        self.assertEqual(
            after_partida, before_partida,
            "reset Alfa apagou partida_contabil de outro tenant",
        )
        self.assertEqual(
            after_lan, before_lan,
            "reset Alfa apagou lancamento_contabil de outro tenant",
        )
        self.assertEqual(
            after_plano, before_plano,
            "reset Alfa apagou plano_contas de outro tenant",
        )

        # Cleanup do tenant fixture
        db.session.execute(text(
            "DELETE FROM partida_contabil WHERE admin_id=:a"
        ), {"a": outro_id})
        db.session.execute(text(
            "DELETE FROM lancamento_contabil WHERE admin_id=:a"
        ), {"a": outro_id})
        db.session.execute(text(
            "DELETE FROM plano_contas WHERE admin_id=:a"
        ), {"a": outro_id})
        db.session.execute(text(
            "DELETE FROM usuario WHERE id=:a"
        ), {"a": outro_id})
        db.session.commit()


if __name__ == "__main__":
    unittest.main()
