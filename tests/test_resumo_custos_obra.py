"""Task #70 — Testes para services.resumo_custos_obra (12 cenários +
snapshot estrutural dos gráficos)."""
import os
import sys
import unittest
import uuid
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db  # noqa: E402


class ResumoCustosObraBaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = app.app_context()
        cls.ctx.push()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.pop()

    def _criar_obra(self, nome='Obra Teste 70'):
        from datetime import date
        from models import Usuario, Obra
        admin = Usuario.query.first()
        if not admin:
            self.skipTest('Nenhum Usuario admin no banco')
        obra = Obra(
            nome=nome,
            admin_id=admin.id,
            data_inicio=date.today(),
            valor_contrato=Decimal('100000.00'),
            orcamento=Decimal('100000.00'),
            percentual_administracao=Decimal('10.00'),
        )
        db.session.add(obra)
        db.session.commit()
        return obra, admin

    def tearDown(self):
        db.session.rollback()


class TestResumoCustosObra(ResumoCustosObraBaseTest):

    # 1. Estrutura: 12 chaves de indicadores
    def test_01_resumo_obra_vazia_tem_12_indicadores(self):
        from services.resumo_custos_obra import calcular_resumo_obra
        obra, admin = self._criar_obra('Obra #01')
        r = calcular_resumo_obra(obra.id, admin_id=admin.id)
        chaves = {'total_proposta_orcada', 'valor_custo_orcado', 'total_realizado',
                  'total_a_realizar', 'custo_real_da_obra', 'verba_disponivel',
                  'faturamento_direto', 'valor_medido', 'valor_recebido',
                  'valor_a_receber', 'lucro_liquido', 'administracao'}
        self.assertTrue(chaves.issubset(set(r['indicadores'].keys())))

    def test_02_obra_vazia_zera_custo_e_mantem_contrato(self):
        from services.resumo_custos_obra import calcular_resumo_obra
        obra, admin = self._criar_obra('Obra #02')
        r = calcular_resumo_obra(obra.id, admin_id=admin.id)
        self.assertEqual(r['indicadores']['total_proposta_orcada'], 100000.0)
        self.assertEqual(r['indicadores']['valor_custo_orcado'], 0.0)
        self.assertEqual(r['indicadores']['total_realizado'], 0.0)

    def test_03_administracao_calcula_10pct_do_contrato(self):
        from services.resumo_custos_obra import calcular_resumo_obra
        obra, admin = self._criar_obra('Obra #03')
        r = calcular_resumo_obra(obra.id, admin_id=admin.id)
        self.assertAlmostEqual(r['indicadores']['administracao'], 10000.0, places=2)

    def test_04_criar_servico_custo_e_ver_soma_orcado(self):
        from models import ObraServicoCusto
        from services.resumo_custos_obra import calcular_resumo_obra
        obra, admin = self._criar_obra('Obra #04')
        svc = ObraServicoCusto(admin_id=admin.id, obra_id=obra.id,
                               nome='Alvenaria', valor_orcado=Decimal('25000.00'))
        db.session.add(svc)
        db.session.commit()
        r = calcular_resumo_obra(obra.id, admin_id=admin.id)
        self.assertEqual(r['indicadores']['valor_custo_orcado'], 25000.0)

    def test_05_equipe_planejada_alimenta_mao_obra_a_realizar(self):
        from models import ObraServicoCusto, ObraServicoEquipePlanejada
        from services.resumo_custos_obra import recalcular_servico, calcular_resumo_obra
        obra, admin = self._criar_obra('Obra #05')
        svc = ObraServicoCusto(admin_id=admin.id, obra_id=obra.id, nome='Pintura')
        db.session.add(svc)
        db.session.commit()
        db.session.add(ObraServicoEquipePlanejada(
            admin_id=admin.id, obra_servico_custo_id=svc.id,
            funcionario_nome='João',
            quantidade_dias=Decimal('10'), diaria=Decimal('200'),
            almoco_e_cafe=Decimal('20'), transporte=Decimal('10'),
        ))
        db.session.commit()
        recalcular_servico(svc.id)
        db.session.commit()
        db.session.refresh(svc)
        self.assertAlmostEqual(float(svc.mao_obra_a_realizar), 2300.0, places=2)
        r = calcular_resumo_obra(obra.id, admin_id=admin.id)
        self.assertGreaterEqual(r['indicadores']['total_a_realizar'], 2300.0)

    def test_06_cotacao_selecionada_sobrescreve_material_a_realizar(self):
        from models import (ObraServicoCusto, ObraServicoCotacaoInterna,
                            ObraServicoCotacaoInternaLinha)
        from services.resumo_custos_obra import recalcular_servico
        obra, admin = self._criar_obra('Obra #06')
        svc = ObraServicoCusto(admin_id=admin.id, obra_id=obra.id,
                               nome='Elétrica',
                               material_a_realizar=Decimal('100.00'))
        db.session.add(svc)
        db.session.commit()
        cot = ObraServicoCotacaoInterna(admin_id=admin.id,
                                        obra_servico_custo_id=svc.id,
                                        fornecedor_nome='Forn A', selecionada=True)
        db.session.add(cot)
        db.session.commit()
        db.session.add(ObraServicoCotacaoInternaLinha(
            admin_id=admin.id, cotacao_id=cot.id, descricao='Fio',
            quantidade=Decimal('10'), valor_unitario=Decimal('50'),
        ))
        db.session.commit()
        recalcular_servico(svc.id)
        db.session.commit()
        db.session.refresh(svc)
        self.assertEqual(float(svc.material_a_realizar), 500.0)

    def test_07_apenas_uma_cotacao_selecionada_por_servico(self):
        from models import ObraServicoCusto, ObraServicoCotacaoInterna
        from sqlalchemy.exc import IntegrityError
        obra, admin = self._criar_obra('Obra #07')
        svc = ObraServicoCusto(admin_id=admin.id, obra_id=obra.id, nome='Hidráulica')
        db.session.add(svc)
        db.session.commit()
        db.session.add_all([
            ObraServicoCotacaoInterna(admin_id=admin.id,
                                      obra_servico_custo_id=svc.id,
                                      fornecedor_nome='A', selecionada=True),
            ObraServicoCotacaoInterna(admin_id=admin.id,
                                      obra_servico_custo_id=svc.id,
                                      fornecedor_nome='B', selecionada=True),
        ])
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_08_grafico_barras_snapshot_estrutura(self):
        """Snapshot estrutural: todas as chaves do grafico_barras bem como
        tipos numéricos, incluindo 'real_projetado' = realizado + a_realizar."""
        from models import ObraServicoCusto
        from services.resumo_custos_obra import calcular_resumo_obra
        obra, admin = self._criar_obra('Obra #08')
        db.session.add(ObraServicoCusto(
            admin_id=admin.id, obra_id=obra.id, nome='S',
            valor_orcado=Decimal('10000'),
            realizado_material=Decimal('100'),
            realizado_mao_obra=Decimal('200'),
            realizado_outros=Decimal('300'),
            override_realizado_manual=True,
            material_a_realizar=Decimal('400'),
            mao_obra_a_realizar=Decimal('500'),
            outros_a_realizar=Decimal('600'),
        ))
        db.session.commit()
        r = calcular_resumo_obra(obra.id, admin_id=admin.id)
        gb = r['grafico_barras']
        self.assertEqual(set(gb.keys()), {'receita', 'custo', 'tem_dados_novos'})
        self.assertEqual(set(gb['receita'].keys()), {'contrato', 'medido', 'recebido'})
        self.assertEqual(set(gb['custo'].keys()),
                         {'orcado', 'realizado', 'a_realizar', 'real_projetado'})
        for k, v in gb['receita'].items():
            self.assertIsInstance(v, (int, float), f'receita.{k} deve ser numérico')
        for k, v in gb['custo'].items():
            self.assertIsInstance(v, (int, float), f'custo.{k} deve ser numérico')
        self.assertAlmostEqual(
            gb['custo']['real_projetado'],
            gb['custo']['realizado'] + gb['custo']['a_realizar'],
            places=2,
        )
        self.assertTrue(gb['tem_dados_novos'])

    def test_09_grafico_composicao_snapshot_2_aneis(self):
        """Snapshot estrutural dos 2 anéis: 3 categorias cada, cada categoria
        com chaves {categoria, valor, cor}."""
        from models import ObraServicoCusto
        from services.resumo_custos_obra import calcular_resumo_obra
        obra, admin = self._criar_obra('Obra #09')
        db.session.add(ObraServicoCusto(
            admin_id=admin.id, obra_id=obra.id, nome='X',
            override_realizado_manual=True,
            realizado_material=Decimal('10'),
            realizado_mao_obra=Decimal('20'),
            realizado_outros=Decimal('30'),
            material_a_realizar=Decimal('1'),
            mao_obra_a_realizar=Decimal('2'),
            outros_a_realizar=Decimal('3'),
        ))
        db.session.commit()
        r = calcular_resumo_obra(obra.id, admin_id=admin.id)
        gc = r['grafico_composicao']
        self.assertEqual(set(gc.keys()), {'realizado', 'a_realizar', 'tem_dados_novos'})
        self.assertEqual(len(gc['realizado']), 3)
        self.assertEqual(len(gc['a_realizar']), 3)
        cats_realizado = [c['categoria'] for c in gc['realizado']]
        cats_arealizar = [c['categoria'] for c in gc['a_realizar']]
        self.assertEqual(cats_realizado, ['Material', 'Mão de Obra', 'Outros'])
        self.assertEqual(cats_arealizar, ['Material', 'Mão de Obra', 'Outros'])
        for anel in ('realizado', 'a_realizar'):
            for c in gc[anel]:
                self.assertEqual(set(c.keys()), {'categoria', 'valor', 'cor'})
                self.assertIsInstance(c['valor'], (int, float))
                self.assertTrue(c['cor'].startswith('#'))

    def test_10_tem_dados_novos_false_em_obra_vazia(self):
        from services.resumo_custos_obra import calcular_resumo_obra
        obra, admin = self._criar_obra('Obra #10')
        r = calcular_resumo_obra(obra.id, admin_id=admin.id)
        self.assertFalse(r['tem_dados_novos'])

    def test_11_tem_dados_novos_true_apos_adicionar_servico(self):
        from models import ObraServicoCusto
        from services.resumo_custos_obra import calcular_resumo_obra
        obra, admin = self._criar_obra('Obra #11')
        db.session.add(ObraServicoCusto(
            admin_id=admin.id, obra_id=obra.id,
            nome='Serv', valor_orcado=Decimal('10')))
        db.session.commit()
        r = calcular_resumo_obra(obra.id, admin_id=admin.id)
        self.assertTrue(r['tem_dados_novos'])

    def test_12_custo_real_da_obra_soma_realizado_a_realizar_adm(self):
        from models import ObraServicoCusto
        from services.resumo_custos_obra import calcular_resumo_obra
        obra, admin = self._criar_obra('Obra #12')
        db.session.add(ObraServicoCusto(
            admin_id=admin.id, obra_id=obra.id, nome='S1',
            valor_orcado=Decimal('50000'),
            realizado_material=Decimal('5000'),
            realizado_mao_obra=Decimal('2000'),
            realizado_outros=Decimal('1000'),
            override_realizado_manual=True,
            material_a_realizar=Decimal('3000'),
            mao_obra_a_realizar=Decimal('4000'),
            outros_a_realizar=Decimal('1000'),
        ))
        db.session.commit()
        r = calcular_resumo_obra(obra.id, admin_id=admin.id)
        ind = r['indicadores']
        self.assertAlmostEqual(ind['total_realizado'], 8000.0, places=2)
        self.assertAlmostEqual(ind['total_a_realizar'], 8000.0, places=2)
        self.assertAlmostEqual(ind['administracao'], 10000.0, places=2)
        self.assertAlmostEqual(
            ind['custo_real_da_obra'],
            ind['total_realizado'] + ind['total_a_realizar']
            + ind['administracao'] + ind['faturamento_direto'],
            places=2,
        )


    def test_13_auto_recalc_via_listener_before_commit(self):
        """Listener de equipe_planejada deve agendar recálculo em before_commit
        e persistir mao_obra_a_realizar derivado das linhas."""
        from models import ObraServicoCusto, ObraServicoEquipePlanejada
        obra, admin = self._criar_obra('Obra #13')
        svc = ObraServicoCusto(
            admin_id=admin.id, obra_id=obra.id, nome='S',
            valor_orcado=Decimal('10000'),
        )
        db.session.add(svc)
        db.session.commit()

        # Insere duas linhas de equipe planejada e commita em um único ciclo
        db.session.add(ObraServicoEquipePlanejada(
            admin_id=admin.id,
            obra_servico_custo_id=svc.id,
            funcionario_nome='Pedro',
            diaria=Decimal('180'),
            almoco_e_cafe=Decimal('15'),
            transporte=Decimal('5'),
            quantidade_dias=Decimal('5'),
        ))
        db.session.add(ObraServicoEquipePlanejada(
            admin_id=admin.id,
            obra_servico_custo_id=svc.id,
            funcionario_nome='Maria',
            diaria=Decimal('130'),
            almoco_e_cafe=Decimal('15'),
            transporte=Decimal('5'),
            quantidade_dias=Decimal('4'),
        ))
        db.session.commit()

        db.session.refresh(svc)
        # (180+15+5)*5 + (130+15+5)*4 = 1000 + 600 = 1600
        self.assertAlmostEqual(float(svc.mao_obra_a_realizar or 0), 1600.0, places=2)

    def test_14_fallback_total_proposta_orcada_usa_proposta(self):
        """Quando obra.valor_contrato é 0/None, total_proposta_orcada deve
        cair para Proposta.valor_total vinculada."""
        from datetime import date
        from models import Obra, Usuario, Proposta
        from services.resumo_custos_obra import calcular_resumo_obra
        admin = Usuario.query.first()
        obra = Obra(
            nome='Obra #14 Fallback',
            admin_id=admin.id,
            data_inicio=date.today(),
            valor_contrato=Decimal('0'),
            orcamento=Decimal('0'),
            percentual_administracao=Decimal('0'),
        )
        db.session.add(obra)
        db.session.commit()

        prop = Proposta(
            admin_id=admin.id,
            obra_id=obra.id,
            numero=f'PROP-70-14-{uuid.uuid4().hex[:8]}',
            cliente_nome='Cliente X',
            valor_total=Decimal('77777.00'),
            status='aprovada',
        )
        db.session.add(prop)
        db.session.commit()

        r = calcular_resumo_obra(obra.id, admin_id=admin.id)
        self.assertAlmostEqual(
            r['indicadores']['total_proposta_orcada'], 77777.0, places=2,
        )


    def test_15_isolamento_multi_tenant_agregados(self):
        """Agregados de Valor Medido / Valor Recebido devem filtrar por
        admin_id — registros com obra_id=X mas admin_id=Y (outro tenant)
        NÃO podem contaminar os totais do tenant X."""
        from datetime import date
        from models import (
            Obra, Usuario, ItemMedicaoComercial, ContaReceber,
        )
        from services.resumo_custos_obra import calcular_resumo_obra

        admins = Usuario.query.limit(2).all()
        if len(admins) < 2:
            from werkzeug.security import generate_password_hash
            outro = Usuario(
                nome='Outro Tenant 70',
                email=f'outro70-{uuid.uuid4().hex[:8]}@example.test',
                username=f'outro70_{uuid.uuid4().hex[:6]}',
                password_hash=generate_password_hash('senha1234'),
                tipo_usuario='admin',
                ativo=True,
            )
            db.session.add(outro)
            db.session.commit()
            admins = Usuario.query.limit(2).all()
        tenant_a, tenant_b = admins[0], admins[1]

        obra = Obra(
            nome='Obra #15 Isolamento',
            admin_id=tenant_a.id,
            data_inicio=date.today(),
            valor_contrato=Decimal('100000'),
            orcamento=Decimal('100000'),
            percentual_administracao=Decimal('0'),
        )
        db.session.add(obra)
        db.session.commit()

        # Item legítimo do tenant A
        imc_a = ItemMedicaoComercial(
            admin_id=tenant_a.id,
            obra_id=obra.id,
            nome='Item A',
            valor_comercial=Decimal('1000'),
            valor_executado_acumulado=Decimal('1000'),
        )
        # Item inconsistente (mesmo obra_id, admin diferente)
        imc_b = ItemMedicaoComercial(
            admin_id=tenant_b.id,
            obra_id=obra.id,
            nome='Item B (leak)',
            valor_comercial=Decimal('9999'),
            valor_executado_acumulado=Decimal('9999'),
        )
        db.session.add_all([imc_a, imc_b])
        db.session.commit()

        cr_a = ContaReceber(
            admin_id=tenant_a.id, obra_id=obra.id,
            cliente_nome='Cliente A', descricao='Recebido A',
            valor_original=Decimal('500'), valor_recebido=Decimal('500'),
            data_emissao=date.today(), data_vencimento=date.today(),
        )
        cr_b = ContaReceber(
            admin_id=tenant_b.id, obra_id=obra.id,
            cliente_nome='Cliente B', descricao='Recebido B (leak)',
            valor_original=Decimal('7777'), valor_recebido=Decimal('7777'),
            data_emissao=date.today(), data_vencimento=date.today(),
        )
        db.session.add_all([cr_a, cr_b])
        db.session.commit()

        r = calcular_resumo_obra(obra.id, admin_id=tenant_a.id)
        ind = r['indicadores']
        # Somente o item do tenant_a deve entrar no total medido
        self.assertAlmostEqual(ind['valor_medido'], 1000.0, places=2)
        # Somente o recebimento do tenant_a deve entrar (sem entrada de obra)
        self.assertAlmostEqual(ind['valor_recebido'], 500.0, places=2)


    def test_16_override_manual_para_baixo_prevalece(self):
        """Override manual por serviço (realizado_* menor que agregado legado
        de GestaoCustoFilho) deve prevalecer quando há obra_servico_custo
        cadastrado — o snapshot por serviço é prioritário."""
        from datetime import date
        from models import (
            Obra, Usuario, ObraServicoCusto,
            GestaoCustoPai, GestaoCustoFilho,
        )
        from services.resumo_custos_obra import calcular_resumo_obra
        admin = Usuario.query.first()
        obra = Obra(
            nome='Obra #16 Override',
            admin_id=admin.id,
            data_inicio=date.today(),
            valor_contrato=Decimal('100000'),
            orcamento=Decimal('100000'),
            percentual_administracao=Decimal('0'),
        )
        db.session.add(obra)
        db.session.commit()

        # Legado: GestaoCustoFilho com R$ 10.000 de custo "real bruto"
        pai = GestaoCustoPai(
            admin_id=admin.id,
            tipo_categoria='MAO_DE_OBRA',
            entidade_nome='Pai legado',
            valor_total=Decimal('10000'),
        )
        db.session.add(pai)
        db.session.commit()
        filho = GestaoCustoFilho(
            pai_id=pai.id,
            obra_id=obra.id,
            admin_id=admin.id,
            data_referencia=date.today(),
            valor=Decimal('10000'),
            descricao='Alocação legado',
        )
        db.session.add(filho)
        db.session.commit()

        # Snapshot por serviço: override manual para R$ 3.000
        svc = ObraServicoCusto(
            admin_id=admin.id,
            obra_id=obra.id,
            nome='Serviço com override',
            valor_orcado=Decimal('20000'),
            realizado_material=Decimal('1000'),
            realizado_mao_obra=Decimal('1500'),
            realizado_outros=Decimal('500'),
        )
        db.session.add(svc)
        db.session.commit()

        r = calcular_resumo_obra(obra.id, admin_id=admin.id)
        # total_realizado = 3000 (snapshot), NÃO 10000 (legado)
        self.assertAlmostEqual(
            r['indicadores']['total_realizado'], 3000.0, places=2,
            msg='Override manual por serviço deve prevalecer sobre legado',
        )


if __name__ == '__main__':
    unittest.main()
