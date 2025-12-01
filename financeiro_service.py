"""
Service Layer - Módulo Financeiro v9.0
Lógica de negócio centralizada para operações financeiras
"""
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from sqlalchemy import and_, or_, func
from app import db
from models import (
    ContaPagar, ContaReceber, BancoEmpresa, PlanoContas,
    LancamentoContabil, PartidaContabil, Fornecedor, Obra,
    FluxoCaixaContabil
)
import logging

logger = logging.getLogger(__name__)


class FinanceiroService:
    """Service centralizado para operações financeiras"""
    
    # ==================== CONTAS A PAGAR ====================
    
    @staticmethod
    def criar_conta_pagar(admin_id: int, fornecedor_id: int, descricao: str,
                          valor: Decimal, data_vencimento: date,
                          obra_id: int = None, numero_documento: str = None,
                          conta_contabil_codigo: str = None) -> ContaPagar:
        """
        Cria uma nova conta a pagar
        
        Args:
            admin_id: ID do administrador
            fornecedor_id: ID do fornecedor
            descricao: Descrição da conta
            valor: Valor original
            data_vencimento: Data de vencimento
            obra_id: ID da obra (opcional)
            numero_documento: Número do documento (opcional)
            conta_contabil_codigo: Código da conta contábil (opcional)
        
        Returns:
            ContaPagar criada
        """
        try:
            conta = ContaPagar(
                admin_id=admin_id,
                fornecedor_id=fornecedor_id,
                obra_id=obra_id,
                numero_documento=numero_documento,
                descricao=descricao,
                valor_original=valor,
                valor_pago=Decimal('0'),
                saldo=valor,
                data_emissao=date.today(),
                data_vencimento=data_vencimento,
                status='PENDENTE',
                conta_contabil_codigo=conta_contabil_codigo
            )
            
            db.session.add(conta)
            db.session.commit()
            
            logger.info(f"✅ Conta a pagar criada: {conta.id} - R$ {valor}")
            return conta
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao criar conta a pagar: {str(e)}")
            raise
    
    @staticmethod
    def baixar_pagamento(conta_id: int, admin_id: int, valor_pago: Decimal, 
                        data_pagamento: date, forma_pagamento: str, 
                        banco_id: int = None) -> ContaPagar:
        """
        Registra pagamento de uma conta a pagar
        
        Args:
            conta_id: ID da conta
            admin_id: ID do administrador (SEGURANÇA MULTI-TENANT)
            valor_pago: Valor sendo pago
            data_pagamento: Data do pagamento
            forma_pagamento: Forma de pagamento (PIX, TED, BOLETO, DINHEIRO)
            banco_id: ID do banco (opcional)
        
        Returns:
            ContaPagar atualizada
        """
        try:
            # SEGURANÇA: Validar admin_id para isolamento multi-tenant
            conta = ContaPagar.query.filter_by(id=conta_id, admin_id=admin_id).first()
            if not conta:
                raise ValueError(f"Conta a pagar {conta_id} não encontrada ou sem permissão")
            
            # Atualizar valores
            conta.valor_pago += valor_pago
            conta.saldo = conta.valor_original - conta.valor_pago
            conta.data_pagamento = data_pagamento
            conta.forma_pagamento = forma_pagamento
            
            # Atualizar status
            if conta.saldo <= 0:
                conta.status = 'PAGO'
            elif conta.valor_pago > 0:
                conta.status = 'PARCIAL'
            
            # Atualizar saldo do banco se informado
            banco = None
            if banco_id:
                # SEGURANÇA: Validar que banco pertence ao mesmo admin
                banco = BancoEmpresa.query.filter_by(id=banco_id, admin_id=admin_id).first()
                if banco:
                    banco.saldo_atual -= valor_pago
                else:
                    logger.warning(f"⚠️ Banco {banco_id} não encontrado ou sem permissão para admin {admin_id}")
            
            db.session.commit()
            
            # ✅ NOVO: Criar lançamento contábil se conta tem vinculação contábil
            if conta.conta_contabil_codigo:
                try:
                    # Gerar numero sequencial
                    ultimo_numero = db.session.query(func.max(LancamentoContabil.numero)).filter_by(
                        admin_id=admin_id
                    ).scalar() or 0
                    proximo_numero = ultimo_numero + 1
                    
                    # Criar lançamento principal
                    lancamento = LancamentoContabil(
                        admin_id=admin_id,
                        data_lancamento=data_pagamento,
                        numero=proximo_numero,
                        historico=f"Pagamento - {conta.descricao}",
                        origem='FINANCEIRO_PAGAR',
                        origem_id=conta_id,
                        valor_total=Decimal(str(valor_pago))
                    )
                    db.session.add(lancamento)
                    db.session.flush()
                    
                    # PARTIDA 1: DÉBITO - Despesa (conta contábil vinculada)
                    partida_debito = PartidaContabil(
                        admin_id=admin_id,
                        lancamento_id=lancamento.id,
                        conta_codigo=conta.conta_contabil_codigo,
                        tipo_partida='DEBITO',
                        valor=Decimal(str(valor_pago)),
                        historico_complementar=f"Pagamento a {conta.fornecedor.razao_social if conta.fornecedor else 'Fornecedor'}",
                        sequencia=1
                    )
                    db.session.add(partida_debito)
                    
                    # PARTIDA 2: CRÉDITO - Caixa/Bancos (saída de dinheiro)
                    partida_credito = PartidaContabil(
                        admin_id=admin_id,
                        lancamento_id=lancamento.id,
                        conta_codigo='1.1.01.001',  # Caixa e Equivalentes
                        tipo_partida='CREDITO',
                        valor=Decimal(str(valor_pago)),
                        historico_complementar=f"Pgto via {banco.nome_banco if banco else 'Banco'}",
                        sequencia=2
                    )
                    db.session.add(partida_credito)
                    
                    db.session.commit()
                    logger.info(f"✅ Lançamento contábil pagamento criado: ID {lancamento.id} (#{proximo_numero}) - D: {conta.conta_contabil_codigo} / C: 1.1.01.001 - R$ {valor_pago}")
                    
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"❌ Erro ao criar lançamento contábil pagamento: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # Não interromper fluxo - pagamento já foi baixado
            
            logger.info(f"✅ Pagamento registrado: Conta {conta_id} - R$ {valor_pago}")
            return conta
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao registrar pagamento: {str(e)}")
            raise
    
    @staticmethod
    def listar_contas_pagar(admin_id: int, status: str = None, 
                           obra_id: int = None, vencidas: bool = False) -> List[ContaPagar]:
        """Lista contas a pagar com filtros"""
        query = ContaPagar.query.filter_by(admin_id=admin_id)
        
        if status:
            query = query.filter_by(status=status)
        
        if obra_id:
            query = query.filter_by(obra_id=obra_id)
        
        if vencidas:
            hoje = date.today()
            query = query.filter(
                and_(
                    ContaPagar.data_vencimento < hoje,
                    ContaPagar.status.in_(['PENDENTE', 'PARCIAL'])
                )
            )
        
        return query.order_by(ContaPagar.data_vencimento).all()
    
    @staticmethod
    def alertas_vencimento_pagar(admin_id: int, dias: int = 7) -> List[ContaPagar]:
        """Retorna contas a pagar que vencem nos próximos X dias"""
        data_limite = date.today() + timedelta(days=dias)
        
        return ContaPagar.query.filter(
            and_(
                ContaPagar.admin_id == admin_id,
                ContaPagar.status.in_(['PENDENTE', 'PARCIAL']),
                ContaPagar.data_vencimento <= data_limite,
                ContaPagar.data_vencimento >= date.today()
            )
        ).order_by(ContaPagar.data_vencimento).all()
    
    # ==================== CONTAS A RECEBER ====================
    
    @staticmethod
    def criar_conta_receber(admin_id: int, cliente_nome: str, descricao: str,
                           valor: Decimal, data_vencimento: date,
                           cliente_cpf_cnpj: str = None, obra_id: int = None,
                           numero_documento: str = None,
                           conta_contabil_codigo: str = None) -> ContaReceber:
        """Cria uma nova conta a receber"""
        try:
            conta = ContaReceber(
                admin_id=admin_id,
                cliente_nome=cliente_nome,
                cliente_cpf_cnpj=cliente_cpf_cnpj,
                obra_id=obra_id,
                numero_documento=numero_documento,
                descricao=descricao,
                valor_original=valor,
                valor_recebido=Decimal('0'),
                saldo=valor,
                data_emissao=date.today(),
                data_vencimento=data_vencimento,
                status='PENDENTE',
                conta_contabil_codigo=conta_contabil_codigo
            )
            
            db.session.add(conta)
            db.session.commit()
            
            logger.info(f"✅ Conta a receber criada: {conta.id} - R$ {valor}")
            return conta
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao criar conta a receber: {str(e)}")
            raise
    
    @staticmethod
    def baixar_recebimento(conta_id: int, admin_id: int, valor_recebido: Decimal, 
                          data_recebimento: date, forma_recebimento: str,
                          banco_id: int = None) -> ContaReceber:
        """Registra recebimento de uma conta a receber"""
        try:
            # SEGURANÇA: Validar admin_id para isolamento multi-tenant
            conta = ContaReceber.query.filter_by(id=conta_id, admin_id=admin_id).first()
            if not conta:
                raise ValueError(f"Conta a receber {conta_id} não encontrada ou sem permissão")
            
            # Atualizar valores
            conta.valor_recebido += valor_recebido
            conta.saldo = conta.valor_original - conta.valor_recebido
            conta.data_recebimento = data_recebimento
            conta.forma_recebimento = forma_recebimento
            
            # Atualizar status
            if conta.saldo <= 0:
                conta.status = 'RECEBIDO'
            elif conta.valor_recebido > 0:
                conta.status = 'PARCIAL'
            
            # Atualizar saldo do banco se informado
            banco = None
            if banco_id:
                # SEGURANÇA: Validar que banco pertence ao mesmo admin
                banco = BancoEmpresa.query.filter_by(id=banco_id, admin_id=admin_id).first()
                if banco:
                    banco.saldo_atual += valor_recebido
                else:
                    logger.warning(f"⚠️ Banco {banco_id} não encontrado ou sem permissão para admin {admin_id}")
            
            db.session.commit()
            
            # ✅ NOVO: Criar lançamento contábil se conta tem vinculação contábil
            if conta.conta_contabil_codigo:
                try:
                    # Gerar numero sequencial
                    ultimo_numero = db.session.query(func.max(LancamentoContabil.numero)).filter_by(
                        admin_id=admin_id
                    ).scalar() or 0
                    proximo_numero = ultimo_numero + 1
                    
                    # Criar lançamento principal
                    lancamento = LancamentoContabil(
                        admin_id=admin_id,
                        data_lancamento=data_recebimento,
                        numero=proximo_numero,
                        historico=f"Recebimento - {conta.descricao}",
                        origem='FINANCEIRO_RECEBER',
                        origem_id=conta_id,
                        valor_total=Decimal(str(valor_recebido))
                    )
                    db.session.add(lancamento)
                    db.session.flush()
                    
                    # PARTIDA 1: DÉBITO - Caixa/Bancos (entrada de dinheiro)
                    partida_debito = PartidaContabil(
                        admin_id=admin_id,
                        lancamento_id=lancamento.id,
                        conta_codigo='1.1.01.001',  # Caixa e Equivalentes
                        tipo_partida='DEBITO',
                        valor=Decimal(str(valor_recebido)),
                        historico_complementar=f"Receb. via {banco.nome_banco if banco else 'Banco'}",
                        sequencia=1
                    )
                    db.session.add(partida_debito)
                    
                    # PARTIDA 2: CRÉDITO - Receita (conta contábil vinculada)
                    partida_credito = PartidaContabil(
                        admin_id=admin_id,
                        lancamento_id=lancamento.id,
                        conta_codigo=conta.conta_contabil_codigo,
                        tipo_partida='CREDITO',
                        valor=Decimal(str(valor_recebido)),
                        historico_complementar=f"Recebimento de {conta.cliente_nome or 'Cliente'}",
                        sequencia=2
                    )
                    db.session.add(partida_credito)
                    
                    db.session.commit()
                    logger.info(f"✅ Lançamento contábil recebimento criado: ID {lancamento.id} (#{proximo_numero}) - D: 1.1.01.001 / C: {conta.conta_contabil_codigo} - R$ {valor_recebido}")
                    
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"❌ Erro ao criar lançamento contábil recebimento: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # Não interromper fluxo - recebimento já foi baixado
            
            logger.info(f"✅ Recebimento registrado: Conta {conta_id} - R$ {valor_recebido}")
            return conta
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao registrar recebimento: {str(e)}")
            raise
    
    @staticmethod
    def listar_contas_receber(admin_id: int, status: str = None,
                             obra_id: int = None, vencidas: bool = False) -> List[ContaReceber]:
        """Lista contas a receber com filtros"""
        query = ContaReceber.query.filter_by(admin_id=admin_id)
        
        if status:
            query = query.filter_by(status=status)
        
        if obra_id:
            query = query.filter_by(obra_id=obra_id)
        
        if vencidas:
            hoje = date.today()
            query = query.filter(
                and_(
                    ContaReceber.data_vencimento < hoje,
                    ContaReceber.status.in_(['PENDENTE', 'PARCIAL'])
                )
            )
        
        return query.order_by(ContaReceber.data_vencimento).all()
    
    # ==================== FLUXO DE CAIXA ====================
    
    @staticmethod
    def calcular_fluxo_caixa(admin_id: int, data_inicio: date, 
                            data_fim: date) -> Dict:
        """
        Calcula fluxo de caixa projetado
        
        Returns:
            Dict com:
                - saldo_inicial: Saldo dos bancos
                - entradas_previstas: Contas a receber no período
                - saidas_previstas: Contas a pagar no período
                - saldo_final_projetado: Projeção de saldo
                - detalhes: Lista de movimentações
        """
        try:
            # Saldo inicial (bancos ativos)
            bancos = BancoEmpresa.query.filter_by(
                admin_id=admin_id,
                ativo=True
            ).all()
            saldo_inicial = sum(b.saldo_atual for b in bancos)
            
            # Contas a receber (entradas)
            contas_receber = ContaReceber.query.filter(
                and_(
                    ContaReceber.admin_id == admin_id,
                    ContaReceber.data_vencimento >= data_inicio,
                    ContaReceber.data_vencimento <= data_fim,
                    ContaReceber.status.in_(['PENDENTE', 'PARCIAL'])
                )
            ).all()
            
            entradas_previstas = sum(c.saldo for c in contas_receber)
            
            # Contas a pagar (saídas)
            contas_pagar = ContaPagar.query.filter(
                and_(
                    ContaPagar.admin_id == admin_id,
                    ContaPagar.data_vencimento >= data_inicio,
                    ContaPagar.data_vencimento <= data_fim,
                    ContaPagar.status.in_(['PENDENTE', 'PARCIAL'])
                )
            ).all()
            
            saidas_previstas = sum(c.saldo for c in contas_pagar)
            
            # Projeção de saldo
            saldo_final = saldo_inicial + entradas_previstas - saidas_previstas
            
            # Detalhes por dia
            detalhes = []
            for conta in contas_receber:
                detalhes.append({
                    'data': conta.data_vencimento,
                    'tipo': 'ENTRADA',
                    'descricao': conta.descricao,
                    'valor': float(conta.saldo),
                    'origem': 'Conta a Receber'
                })
            
            for conta in contas_pagar:
                detalhes.append({
                    'data': conta.data_vencimento,
                    'tipo': 'SAIDA',
                    'descricao': conta.descricao,
                    'valor': float(conta.saldo),
                    'origem': 'Conta a Pagar'
                })
            
            # Ordenar por data
            detalhes.sort(key=lambda x: x['data'])
            
            return {
                'saldo_inicial': float(saldo_inicial),
                'entradas_previstas': float(entradas_previstas),
                'saidas_previstas': float(saidas_previstas),
                'saldo_final_projetado': float(saldo_final),
                'detalhes': detalhes,
                'alerta': saldo_final < 0
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular fluxo de caixa: {str(e)}")
            raise
    
    # ==================== DASHBOARD ====================
    
    @staticmethod
    def obter_kpis_financeiros(admin_id: int) -> Dict:
        """Retorna KPIs financeiros para dashboard"""
        try:
            hoje = date.today()
            
            # Contas a pagar
            total_pagar = db.session.query(
                func.sum(ContaPagar.saldo)
            ).filter(
                and_(
                    ContaPagar.admin_id == admin_id,
                    ContaPagar.status.in_(['PENDENTE', 'PARCIAL'])
                )
            ).scalar() or Decimal('0')
            
            vencidas_pagar = db.session.query(
                func.count(ContaPagar.id)
            ).filter(
                and_(
                    ContaPagar.admin_id == admin_id,
                    ContaPagar.status.in_(['PENDENTE', 'PARCIAL']),
                    ContaPagar.data_vencimento < hoje
                )
            ).scalar() or 0
            
            # Contas a receber
            total_receber = db.session.query(
                func.sum(ContaReceber.saldo)
            ).filter(
                and_(
                    ContaReceber.admin_id == admin_id,
                    ContaReceber.status.in_(['PENDENTE', 'PARCIAL'])
                )
            ).scalar() or Decimal('0')
            
            vencidas_receber = db.session.query(
                func.count(ContaReceber.id)
            ).filter(
                and_(
                    ContaReceber.admin_id == admin_id,
                    ContaReceber.status.in_(['PENDENTE', 'PARCIAL']),
                    ContaReceber.data_vencimento < hoje
                )
            ).scalar() or 0
            
            # Saldo bancário
            saldo_bancos = db.session.query(
                func.sum(BancoEmpresa.saldo_atual)
            ).filter(
                and_(
                    BancoEmpresa.admin_id == admin_id,
                    BancoEmpresa.ativo == True
                )
            ).scalar() or Decimal('0')
            
            return {
                'total_pagar': float(total_pagar),
                'vencidas_pagar': vencidas_pagar,
                'total_receber': float(total_receber),
                'vencidas_receber': vencidas_receber,
                'saldo_bancos': float(saldo_bancos),
                'saldo_liquido': float(saldo_bancos + total_receber - total_pagar),
                'total_entradas': float(total_receber),
                'total_saidas': float(total_pagar),
                'saldo_periodo': float(total_receber - total_pagar),
                'receitas_pendentes': float(total_receber)
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter KPIs: {str(e)}")
            raise
    
    # ==================== BANCOS ====================
    
    @staticmethod
    def criar_banco(admin_id: int, nome_banco: str, agencia: str,
                   conta: str, tipo_conta: str, saldo_inicial: Decimal = Decimal('0')) -> BancoEmpresa:
        """Cria conta bancária"""
        try:
            banco = BancoEmpresa(
                admin_id=admin_id,
                nome_banco=nome_banco,
                agencia=agencia,
                conta=conta,
                tipo_conta=tipo_conta,
                saldo_inicial=saldo_inicial,
                saldo_atual=saldo_inicial,
                ativo=True
            )
            
            db.session.add(banco)
            db.session.commit()
            
            logger.info(f"✅ Banco criado: {banco.id} - {nome_banco}")
            return banco
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao criar banco: {str(e)}")
            raise
