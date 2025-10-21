"""
Utilitários para o Módulo 7 - Sistema Contábil Completo
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import func, case
from models import (
    db, PlanoContas, CentroCustoContabil, LancamentoContabil, PartidaContabil, 
    BalanceteMensal, DREMensal, BalancoPatrimonial, FluxoCaixaContabil, 
    ProvisaoMensal, SpedContabil, AuditoriaContabil, Proposta, 
    NotaFiscal, MovimentacaoEstoque, FolhaPagamento
)

# ===============================================================
# == MÓDULO 7: FUNÇÕES UTILITÁRIAS CONTÁBEIS
# ===============================================================

def criar_plano_contas_padrao(admin_id):
    """Cria o plano de contas brasileiro completo para um novo admin."""
    if PlanoContas.query.filter_by(admin_id=admin_id).first():
        return # Já existe

    contas = [
        # 1. ATIVO
        ('1', 'ATIVO', 'ATIVO', 'DEVEDORA', 1, None, False),
        ('1.1', 'ATIVO CIRCULANTE', 'ATIVO', 'DEVEDORA', 2, '1', False),
        ('1.1.01', 'DISPONÍVEL', 'ATIVO', 'DEVEDORA', 3, '1.1', False),
        ('1.1.01.001', 'Caixa', 'ATIVO', 'DEVEDORA', 4, '1.1.01', True),
        ('1.1.01.002', 'Bancos Conta Movimento', 'ATIVO', 'DEVEDORA', 4, '1.1.01', True),
        ('1.1.01.003', 'Aplicações Financeiras', 'ATIVO', 'DEVEDORA', 4, '1.1.01', True),
        
        ('1.1.02', 'CONTAS A RECEBER', 'ATIVO', 'DEVEDORA', 3, '1.1', False),
        ('1.1.02.001', 'Clientes', 'ATIVO', 'DEVEDORA', 4, '1.1.02', True),
        ('1.1.02.002', 'Duplicatas a Receber', 'ATIVO', 'DEVEDORA', 4, '1.1.02', True),
        ('1.1.02.003', 'Provisão para Devedores Duvidosos', 'ATIVO', 'CREDORA', 4, '1.1.02', True),
        
        ('1.1.03', 'ESTOQUES', 'ATIVO', 'DEVEDORA', 3, '1.1', False),
        ('1.1.03.001', 'Estoque de Materiais', 'ATIVO', 'DEVEDORA', 4, '1.1.03', True),
        ('1.1.03.002', 'Estoque de Produtos Acabados', 'ATIVO', 'DEVEDORA', 4, '1.1.03', True),
        ('1.1.03.003', 'Estoque em Trânsito', 'ATIVO', 'DEVEDORA', 4, '1.1.03', True),
        
        ('1.1.04', 'IMPOSTOS A RECUPERAR', 'ATIVO', 'DEVEDORA', 3, '1.1', False),
        ('1.1.04.001', 'ICMS a Recuperar', 'ATIVO', 'DEVEDORA', 4, '1.1.04', True),
        ('1.1.04.002', 'IPI a Recuperar', 'ATIVO', 'DEVEDORA', 4, '1.1.04', True),
        ('1.1.04.003', 'PIS a Recuperar', 'ATIVO', 'DEVEDORA', 4, '1.1.04', True),
        ('1.1.04.004', 'COFINS a Recuperar', 'ATIVO', 'DEVEDORA', 4, '1.1.04', True),
        
        # 2. PASSIVO
        ('2', 'PASSIVO', 'PASSIVO', 'CREDORA', 1, None, False),
        ('2.1', 'PASSIVO CIRCULANTE', 'PASSIVO', 'CREDORA', 2, '2', False),
        ('2.1.01', 'FORNECEDORES', 'PASSIVO', 'CREDORA', 3, '2.1', False),
        ('2.1.01.001', 'Fornecedores Nacionais', 'PASSIVO', 'CREDORA', 4, '2.1.01', True),
        ('2.1.01.002', 'Fornecedores Estrangeiros', 'PASSIVO', 'CREDORA', 4, '2.1.01', True),
        
        ('2.1.02', 'OBRIGAÇÕES TRABALHISTAS', 'PASSIVO', 'CREDORA', 3, '2.1', False),
        ('2.1.02.001', 'Salários a Pagar', 'PASSIVO', 'CREDORA', 4, '2.1.02', True),
        ('2.1.02.002', 'Provisão para Férias', 'PASSIVO', 'CREDORA', 4, '2.1.02', True),
        ('2.1.02.003', 'Provisão para 13º Salário', 'PASSIVO', 'CREDORA', 4, '2.1.02', True),
        ('2.1.02.004', 'FGTS a Recolher', 'PASSIVO', 'CREDORA', 4, '2.1.02', True),
        
        ('2.1.03', 'OBRIGAÇÕES FISCAIS', 'PASSIVO', 'CREDORA', 3, '2.1', False),
        ('2.1.03.007', 'INSS a Recolher', 'PASSIVO', 'CREDORA', 4, '2.1.03', True),
        ('2.1.03.008', 'IRRF a Recolher', 'PASSIVO', 'CREDORA', 4, '2.1.03', True),
        ('2.1.03.009', 'ISS a Recolher', 'PASSIVO', 'CREDORA', 4, '2.1.03', True),
        
        # 3. PATRIMÔNIO LÍQUIDO
        ('3', 'PATRIMÔNIO LÍQUIDO', 'PATRIMONIO', 'CREDORA', 1, None, False),
        ('3.1', 'CAPITAL SOCIAL', 'PATRIMONIO', 'CREDORA', 2, '3', False),
        ('3.1.01', 'Capital Social Subscrito', 'PATRIMONIO', 'CREDORA', 3, '3.1', True),
        
        # 4. RECEITAS
        ('4', 'RECEITAS', 'RECEITA', 'CREDORA', 1, None, False),
        ('4.1', 'RECEITA BRUTA', 'RECEITA', 'CREDORA', 2, '4', False),
        ('4.1.02', 'RECEITA DE SERVIÇOS', 'RECEITA', 'CREDORA', 3, '4.1', False),
        ('4.1.02.001', 'Prestação de Serviços', 'RECEITA', 'CREDORA', 4, '4.1.02', True),
        ('4.1.02.002', 'Serviços de Construção', 'RECEITA', 'CREDORA', 4, '4.1.02', True),
        
        # 5. CUSTOS
        ('5', 'CUSTOS', 'DESPESA', 'DEVEDORA', 1, None, False),
        ('5.1', 'CUSTO DOS SERVIÇOS PRESTADOS', 'DESPESA', 'DEVEDORA', 2, '5', False),
        ('5.1.01', 'Materiais Diretos', 'DESPESA', 'DEVEDORA', 3, '5.1', True),
        ('5.1.02', 'Mão de Obra Direta', 'DESPESA', 'DEVEDORA', 3, '5.1', True),
        ('5.2', 'CUSTOS INDIRETOS', 'DESPESA', 'DEVEDORA', 2, '5', False),
        ('5.2.01', 'Materiais Indiretos', 'DESPESA', 'DEVEDORA', 3, '5.2', True),
        
        # 6. DESPESAS
        ('6', 'DESPESAS', 'DESPESA', 'DEVEDORA', 1, None, False),
        ('6.1', 'DESPESAS OPERACIONAIS', 'DESPESA', 'DEVEDORA', 2, '6', False),
        ('6.1.01', 'DESPESAS COM PESSOAL', 'DESPESA', 'DEVEDORA', 3, '6.1', False),
        ('6.1.01.001', 'Salários', 'DESPESA', 'DEVEDORA', 4, '6.1.01', True),
        ('6.1.01.002', 'Encargos Sociais', 'DESPESA', 'DEVEDORA', 4, '6.1.01', True),
        
        ('6.1.02', 'DESPESAS ADMINISTRATIVAS', 'DESPESA', 'DEVEDORA', 3, '6.1', False),
        ('6.1.02.001', 'Material de Escritório', 'DESPESA', 'DEVEDORA', 4, '6.1.02', True),
        ('6.1.02.002', 'Telefone', 'DESPESA', 'DEVEDORA', 4, '6.1.02', True),
        ('6.1.02.003', 'Energia Elétrica', 'DESPESA', 'DEVEDORA', 4, '6.1.02', True),
    ]

    for codigo, nome, tipo_conta, natureza, nivel, conta_pai_codigo, aceita_lancamento in contas:
        conta = PlanoContas(
            codigo=codigo, nome=nome, tipo_conta=tipo_conta, natureza=natureza,
            nivel=nivel, conta_pai_codigo=conta_pai_codigo, 
            aceita_lancamento=aceita_lancamento, admin_id=admin_id
        )
        db.session.add(conta)
    db.session.commit()

def get_next_lancamento_numero(admin_id):
    """Obtém o próximo número de lançamento sequencial."""
    last_lancamento = LancamentoContabil.query.filter_by(admin_id=admin_id).order_by(LancamentoContabil.numero.desc()).first()
    return (last_lancamento.numero + 1) if last_lancamento else 1

def criar_lancamento_automatico(data, historico, valor, origem, origem_id, admin_id, partidas):
    """Função central para criar lançamentos contábeis automáticos."""
    # Validação de partidas
    total_debitos = sum(p['valor'] for p in partidas if p['tipo'] == 'DEBITO')
    total_creditos = sum(p['valor'] for p in partidas if p['tipo'] == 'CREDITO')
    if abs(total_debitos - total_creditos) > 0.01:
        raise ValueError("Lançamento desbalanceado: débitos não são iguais aos créditos.")

    lancamento = LancamentoContabil(
        numero=get_next_lancamento_numero(admin_id),
        data_lancamento=data,
        historico=historico,
        valor_total=valor,
        origem=origem,
        origem_id=origem_id,
        admin_id=admin_id
    )
    db.session.add(lancamento)
    db.session.flush() # Para obter o ID do lançamento

    for i, p in enumerate(partidas):
        partida = PartidaContabil(
            lancamento_id=lancamento.id,
            sequencia=i + 1,
            conta_codigo=p['conta'],
            centro_custo_id=p.get('centro_custo_id'),
            tipo_partida=p['tipo'],
            valor=p['valor'],
            historico_complementar=p.get('historico_comp'),
            admin_id=admin_id
        )
        db.session.add(partida)
    
    db.session.commit()
    return lancamento

# --- Funções de Integração Automática ---

def contabilizar_proposta_aprovada(proposta_id):
    """Gera lançamentos contábeis quando uma proposta é aprovada."""
    proposta = Proposta.query.get(proposta_id)
    if not proposta or proposta.status != 'APROVADA':
        return

    # Cria centro de custo para a obra se não existir
    centro_custo = CentroCustoContabil.query.filter_by(obra_id=proposta.obra_id, admin_id=proposta.admin_id).first()
    if not centro_custo:
        centro_custo = CentroCustoContabil(
            codigo=f"OBRA_{proposta.obra.id}", 
            nome=proposta.obra.nome, 
            tipo='OBRA', 
            obra_id=proposta.obra_id, 
            admin_id=proposta.admin_id
        )
        db.session.add(centro_custo)
        db.session.flush()

    partidas = [
        {'tipo': 'DEBITO', 'conta': '1.1.02.001', 'valor': proposta.valor_total, 'centro_custo_id': centro_custo.id},
        {'tipo': 'CREDITO', 'conta': '4.1.02.002', 'valor': proposta.valor_total, 'centro_custo_id': centro_custo.id}
    ]

    criar_lancamento_automatico(
        data=proposta.data_aprovacao,
        historico=f"Aprovação da Proposta #{proposta.id} - Cliente: {proposta.cliente_nome}",
        valor=proposta.valor_total,
        origem='MODULO_1',
        origem_id=proposta.id,
        admin_id=proposta.admin_id,
        partidas=partidas
    )

def contabilizar_entrada_material(nota_fiscal_id):
    """Gera lançamentos contábeis para entrada de material via NF."""
    nota = NotaFiscal.query.get(nota_fiscal_id)
    if not nota:
        return

    partidas = [
        {'tipo': 'DEBITO', 'conta': '1.1.03.001', 'valor': nota.valor_produtos},
        {'tipo': 'CREDITO', 'conta': '2.1.01.001', 'valor': nota.valor_total}
    ]
    if nota.valor_icms and nota.valor_icms > 0:
        partidas.append({'tipo': 'DEBITO', 'conta': '1.1.04.001', 'valor': nota.valor_icms})

    criar_lancamento_automatico(
        data=nota.data_emissao,
        historico=f"Entrada NF #{nota.numero} - Fornecedor: {nota.fornecedor_nome}",
        valor=nota.valor_total,
        origem='MODULO_4',
        origem_id=nota.id,
        admin_id=nota.admin_id,
        partidas=partidas
    )

def contabilizar_folha_pagamento(admin_id, mes_referencia):
    """Gera o lançamento contábil consolidado da folha de pagamento."""
    folhas = FolhaPagamento.query.filter_by(admin_id=admin_id, mes_referencia=mes_referencia).all()
    if not folhas:
        return

    # Totalizadores
    total_salario_bruto = sum(f.salario_bruto or 0 for f in folhas)
    total_inss_func = sum(f.inss or 0 for f in folhas)
    total_irrf = sum(f.irrf or 0 for f in folhas)
    total_fgts = sum(f.fgts or 0 for f in folhas)
    total_liquido = sum(f.salario_liquido or 0 for f in folhas)
    inss_empresa = total_salario_bruto * Decimal('0.20') # Simplificado

    partidas = [
        {'tipo': 'DEBITO', 'conta': '6.1.01.001', 'valor': total_salario_bruto}, # Despesa com Salários
        {'tipo': 'DEBITO', 'conta': '6.1.01.002', 'valor': inss_empresa + total_fgts}, # Despesa com Encargos
        {'tipo': 'CREDITO', 'conta': '2.1.02.001', 'valor': total_liquido}, # Salários a Pagar
        {'tipo': 'CREDITO', 'conta': '2.1.03.007', 'valor': total_inss_func + inss_empresa}, # INSS a Recolher
        {'tipo': 'CREDITO', 'conta': '2.1.02.004', 'valor': total_fgts}, # FGTS a Recolher
        {'tipo': 'CREDITO', 'conta': '2.1.03.008', 'valor': total_irrf}  # IRRF a Recolher
    ]

    criar_lancamento_automatico(
        data=mes_referencia.replace(day=calendar.monthrange(mes_referencia.year, mes_referencia.month)[1]),
        historico=f"Folha de Pagamento ref. {mes_referencia.strftime('%m/%Y')}",
        valor=total_salario_bruto + inss_empresa + total_fgts,
        origem='MODULO_6',
        origem_id=0, # Representa o mês todo
        admin_id=admin_id,
        partidas=[p for p in partidas if p['valor'] > 0]
    )

# --- Funções de Geração de Relatórios ---

def calcular_saldo_conta(conta_codigo, admin_id, data_inicio=None, data_fim=None):
    """Calcula o saldo de uma conta em um período."""
    query = db.session.query(func.sum(
        case((PartidaContabil.tipo_partida == 'DEBITO', PartidaContabil.valor), else_=-PartidaContabil.valor)
    )).join(LancamentoContabil).filter(
        PartidaContabil.conta_codigo == conta_codigo,
        PartidaContabil.admin_id == admin_id
    )
    
    if data_fim:
        query = query.filter(LancamentoContabil.data_lancamento <= data_fim)
    if data_inicio:
        query = query.filter(LancamentoContabil.data_lancamento >= data_inicio)
    
    saldo = query.scalar() or Decimal('0.0')
    return saldo

def gerar_balancete_mensal(admin_id, mes_referencia):
    """Gera o balancete mensal para todas as contas."""
    # Obter todas as contas que aceitam lançamento
    contas = PlanoContas.query.filter_by(admin_id=admin_id, aceita_lancamento=True).all()
    
    primeiro_dia = mes_referencia.replace(day=1)
    ultimo_dia = date(mes_referencia.year, mes_referencia.month, 
                     calendar.monthrange(mes_referencia.year, mes_referencia.month)[1])
    
    for conta in contas:
        # Verificar se já existe balancete para esta conta/mês
        balancete_existente = BalanceteMensal.query.filter_by(
            conta_codigo=conta.codigo,
            mes_referencia=primeiro_dia,
            admin_id=admin_id
        ).first()
        
        if balancete_existente:
            continue
            
        # Calcular saldos
        saldo_anterior = calcular_saldo_conta(conta.codigo, admin_id, None, primeiro_dia - timedelta(days=1))
        saldo_atual = calcular_saldo_conta(conta.codigo, admin_id, None, ultimo_dia)
        
        # Calcular movimentação do mês
        debitos_mes = db.session.query(func.sum(PartidaContabil.valor)).join(LancamentoContabil).filter(
            PartidaContabil.conta_codigo == conta.codigo,
            PartidaContabil.admin_id == admin_id,
            PartidaContabil.tipo_partida == 'DEBITO',
            LancamentoContabil.data_lancamento >= primeiro_dia,
            LancamentoContabil.data_lancamento <= ultimo_dia
        ).scalar() or Decimal('0.0')
        
        creditos_mes = db.session.query(func.sum(PartidaContabil.valor)).join(LancamentoContabil).filter(
            PartidaContabil.conta_codigo == conta.codigo,
            PartidaContabil.admin_id == admin_id,
            PartidaContabil.tipo_partida == 'CREDITO',
            LancamentoContabil.data_lancamento >= primeiro_dia,
            LancamentoContabil.data_lancamento <= ultimo_dia
        ).scalar() or Decimal('0.0')
        
        balancete = BalanceteMensal(
            conta_codigo=conta.codigo,
            mes_referencia=primeiro_dia,
            saldo_anterior=saldo_anterior,
            debitos_mes=debitos_mes,
            creditos_mes=creditos_mes,
            saldo_atual=saldo_atual,
            admin_id=admin_id
        )
        db.session.add(balancete)
    
    db.session.commit()

def executar_auditoria_automatica(admin_id):
    """Executa verificações automáticas de auditoria."""
    alertas = []
    
    # Verificar se há lançamentos desbalanceados
    lancamentos_desbalanceados = db.session.query(LancamentoContabil).filter_by(admin_id=admin_id).all()
    
    for lancamento in lancamentos_desbalanceados:
        total_debitos = sum(p.valor for p in lancamento.partidas if p.tipo_partida == 'DEBITO')
        total_creditos = sum(p.valor for p in lancamento.partidas if p.tipo_partida == 'CREDITO')
        
        if abs(total_debitos - total_creditos) > 0.01:
            auditoria = AuditoriaContabil(
                tipo_verificacao='LANÇAMENTO_DESBALANCEADO',
                resultado='NAO_CONFORME',
                observacoes=f'Lançamento #{lancamento.numero} desbalanceado: D={total_debitos} C={total_creditos}',
                valor_divergencia=abs(total_debitos - total_creditos),
                admin_id=admin_id
            )
            db.session.add(auditoria)
            alertas.append(auditoria)
    
    db.session.commit()
    return alertas

def calcular_dre_mensal(admin_id: int, ano: int, mes: int):
    """
    Calcula DRE completo baseado na estrutura contábil brasileira
    
    Estrutura DRE (11 seções):
    1. RECEITA BRUTA (4.1.x)
    2. (-) DEDUÇÕES (4.2.x)
    3. = RECEITA LÍQUIDA
    4. (-) CMV/CPV (5.1.03.x)
    5. = LUCRO BRUTO
    6. (-) DESPESAS OPERACIONAIS (5.1.01, 5.1.02, 5.1.04, 5.1.05, 5.1.06)
    7. = EBITDA
    8. (+/-) RESULTADO FINANCEIRO (4.3.01 - 5.2.01)
    9. = RESULTADO ANTES IR/CSLL
    10. (-) PROVISÃO IR E CSLL (5.3.01, 5.3.02)
    11. = LUCRO LÍQUIDO
    
    Args:
        admin_id: ID do admin
        ano: Ano de referência
        mes: Mês de referência (1-12)
        
    Returns:
        dict: Dicionário com todos os valores do DRE
    """
    from sqlalchemy import and_
    from decimal import Decimal
    
    try:
        # Definir período do mês
        data_inicio = date(ano, mes, 1)
        if mes == 12:
            data_fim = date(ano + 1, 1, 1) - timedelta(days=1)
        else:
            data_fim = date(ano, mes + 1, 1) - timedelta(days=1)
        
        # Função auxiliar para calcular saldo de contas específicas
        def calcular_valor_contas(prefixos: list, tipo_esperado: str = None):
            """
            Calcula o total de valores para lista de prefixos de contas
            
            Args:
                prefixos: Lista de prefixos de contas (ex: ['4.1.01', '4.1.02'])
                tipo_esperado: 'CREDITO' para receitas, 'DEBITO' para despesas/custos
            """
            total = Decimal('0')
            
            for prefixo in prefixos:
                partidas = PartidaContabil.query.join(
                    LancamentoContabil,
                    PartidaContabil.lancamento_id == LancamentoContabil.id
                ).filter(
                    and_(
                        PartidaContabil.admin_id == admin_id,
                        PartidaContabil.conta_codigo.like(f'{prefixo}%'),
                        LancamentoContabil.data_lancamento >= data_inicio,
                        LancamentoContabil.data_lancamento <= data_fim
                    )
                ).all()
                
                for partida in partidas:
                    valor = Decimal(str(partida.valor))
                    
                    # Se tipo esperado for especificado, só conta se for o tipo correto
                    if tipo_esperado:
                        if partida.tipo_partida == tipo_esperado:
                            total += valor
                    else:
                        # Senão, credita positivo e debita negativo
                        if partida.tipo_partida == 'CREDITO':
                            total += valor
                        else:
                            total -= valor
            
            return total
        
        # 1. RECEITA BRUTA (contas 4.1.x - CREDITO)
        receita_bruta = calcular_valor_contas(['4.1.01', '4.1.02'], 'CREDITO')
        
        # 2. DEDUÇÕES E ABATIMENTOS (contas 4.2.x - DEBITO)
        deducoes = calcular_valor_contas(['4.2.01', '4.2.02'], 'DEBITO')
        
        # 3. RECEITA LÍQUIDA
        receita_liquida = receita_bruta - deducoes
        
        # 4. CMV/CPV (contas 5.1.03.x - DEBITO)
        cmv = calcular_valor_contas(['5.1.03'], 'DEBITO')
        
        # 5. LUCRO BRUTO
        lucro_bruto = receita_liquida - cmv
        
        # 6. DESPESAS OPERACIONAIS (contas 5.1.x - DEBITO, exceto 5.1.03)
        despesas_pessoal = calcular_valor_contas(['5.1.01'], 'DEBITO')
        despesas_materiais = calcular_valor_contas(['5.1.02'], 'DEBITO')
        despesas_administrativas = calcular_valor_contas(['5.1.04'], 'DEBITO')
        despesas_comerciais = calcular_valor_contas(['5.1.05'], 'DEBITO')
        outras_despesas = calcular_valor_contas(['5.1.06'], 'DEBITO')
        
        total_despesas_operacionais = (
            despesas_pessoal + despesas_materiais + despesas_administrativas + 
            despesas_comerciais + outras_despesas
        )
        
        # 7. EBITDA
        ebitda = lucro_bruto - total_despesas_operacionais
        
        # 8. RESULTADO FINANCEIRO
        receitas_financeiras = calcular_valor_contas(['4.3.01'], 'CREDITO')
        despesas_financeiras = calcular_valor_contas(['5.2.01'], 'DEBITO')
        resultado_financeiro = receitas_financeiras - despesas_financeiras
        
        # 9. RESULTADO ANTES IR/CSLL
        resultado_antes_ir = ebitda + resultado_financeiro
        
        # 10. PROVISÃO IR E CSLL (contas 5.3.x - DEBITO)
        provisao_ir = calcular_valor_contas(['5.3.01'], 'DEBITO')
        provisao_csll = calcular_valor_contas(['5.3.02'], 'DEBITO')
        total_provisoes = provisao_ir + provisao_csll
        
        # 11. LUCRO LÍQUIDO
        lucro_liquido = resultado_antes_ir - total_provisoes
        
        # Calcular percentuais (sobre receita líquida)
        def calcular_percentual(valor, base):
            if base and base != 0:
                return float((valor / base) * 100)
            return 0.0
        
        margem_bruta = calcular_percentual(lucro_bruto, receita_liquida)
        margem_ebitda = calcular_percentual(ebitda, receita_liquida)
        margem_liquida = calcular_percentual(lucro_liquido, receita_liquida)
        
        # Montar estrutura completa do DRE
        dre_data = {
            'mes': mes,
            'ano': ano,
            'mes_referencia': data_inicio,
            
            # Seção 1-3: Receitas
            'receita_bruta': float(receita_bruta),
            'deducoes': float(deducoes),
            'receita_liquida': float(receita_liquida),
            
            # Seção 4-5: CMV e Lucro Bruto
            'cmv': float(cmv),
            'lucro_bruto': float(lucro_bruto),
            
            # Seção 6: Despesas Operacionais (detalhadas)
            'despesas_operacionais': {
                'pessoal': float(despesas_pessoal),
                'materiais': float(despesas_materiais),
                'administrativas': float(despesas_administrativas),
                'comerciais': float(despesas_comerciais),
                'outras': float(outras_despesas),
                'total': float(total_despesas_operacionais)
            },
            
            # Seção 7: EBITDA
            'ebitda': float(ebitda),
            
            # Seção 8: Resultado Financeiro
            'resultado_financeiro': {
                'receitas': float(receitas_financeiras),
                'despesas': float(despesas_financeiras),
                'total': float(resultado_financeiro)
            },
            
            # Seção 9-11: Resultado Final
            'resultado_antes_ir': float(resultado_antes_ir),
            'provisao_ir_csll': {
                'ir': float(provisao_ir),
                'csll': float(provisao_csll),
                'total': float(total_provisoes)
            },
            'lucro_liquido': float(lucro_liquido),
            
            # Percentuais
            'percentuais': {
                'margem_bruta': margem_bruta,
                'margem_ebitda': margem_ebitda,
                'margem_liquida': margem_liquida
            }
        }
        
        print(f"✅ DRE {mes}/{ano} calculada: Receita Líquida={receita_liquida}, Lucro Líquido={lucro_liquido}")
        return dre_data
        
    except Exception as e:
        print(f"❌ Erro ao calcular DRE: {e}")
        import traceback
        traceback.print_exc()
        return None