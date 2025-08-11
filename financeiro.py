"""
Módulo de Gestão Financeira Avançada - SIGE v3.0
Sistema Integrado de Gestão Empresarial - Estruturas do Vale

Implementa funcionalidades avançadas de gestão financeira:
- Controle de receitas
- Fluxo de caixa
- Orçamentos vs. realizados  
- Centros de custo

Data: 07 de Julho de 2025
"""

from datetime import datetime, date, timedelta
from sqlalchemy import and_, func, text
import calendar
from models import *
from app import db

def gerar_numero_receita():
    """Gera próximo número de receita sequencial"""
    ultima_receita = db.session.query(Receita).order_by(Receita.id.desc()).first()
    if ultima_receita:
        ultimo_num = int(ultima_receita.numero_receita.replace('REC', ''))
        return f"REC{ultimo_num + 1:03d}"
    return "REC001"

def gerar_codigo_centro_custo():
    """Gera próximo código de centro de custo"""
    ultimo_centro = db.session.query(CentroCusto).order_by(CentroCusto.id.desc()).first()
    if ultimo_centro:
        ultimo_num = int(ultimo_centro.codigo.replace('CC', ''))
        return f"CC{ultimo_num + 1:03d}"
    return "CC001"

def calcular_fluxo_caixa_periodo(data_inicio, data_fim, obra_id=None, centro_custo_id=None):
    """
    Calcula fluxo de caixa consolidado para um período
    
    Returns:
        dict: {
            'total_entradas': float,
            'total_saidas': float,
            'saldo_periodo': float,
            'movimentos': list,
            'resumo_categorias': dict
        }
    """
    # Filtros base
    filtros = [
        FluxoCaixa.data_movimento >= data_inicio,
        FluxoCaixa.data_movimento <= data_fim
    ]
    
    if obra_id:
        filtros.append(FluxoCaixa.obra_id == obra_id)
    if centro_custo_id:
        filtros.append(FluxoCaixa.centro_custo_id == centro_custo_id)
    
    # Buscar movimentos do período
    movimentos = db.session.query(FluxoCaixa).filter(and_(*filtros)).order_by(FluxoCaixa.data_movimento.desc()).all()
    
    # Calcular totais
    total_entradas = sum(m.valor for m in movimentos if m.tipo_movimento == 'ENTRADA')
    total_saidas = sum(m.valor for m in movimentos if m.tipo_movimento == 'SAIDA')
    saldo_periodo = total_entradas - total_saidas
    
    # Resumo por categorias
    resumo_categorias = {}
    for movimento in movimentos:
        categoria = movimento.categoria
        tipo = movimento.tipo_movimento
        
        if categoria not in resumo_categorias:
            resumo_categorias[categoria] = {'entradas': 0, 'saidas': 0}
        
        if tipo == 'ENTRADA':
            resumo_categorias[categoria]['entradas'] += movimento.valor
        else:
            resumo_categorias[categoria]['saidas'] += movimento.valor
    
    return {
        'total_entradas': total_entradas,
        'total_saidas': total_saidas,
        'saldo_periodo': saldo_periodo,
        'movimentos': movimentos,
        'resumo_categorias': resumo_categorias,
        'quantidade_movimentos': len(movimentos)
    }

def sincronizar_fluxo_caixa():
    """
    Sincroniza automaticamente os dados do fluxo de caixa com base em:
    - Receitas
    - Custos de obra
    - Custos de veículos
    - Registro de alimentação
    """
    # Limpar fluxo de caixa existente (para reprocessamento)
    db.session.query(FluxoCaixa).delete()
    
    # 1. Receitas (ENTRADAS)
    receitas = db.session.query(Receita).filter(Receita.status == 'Recebido').all()
    for receita in receitas:
        movimento = FluxoCaixa(
            data_movimento=receita.data_recebimento or receita.data_receita,
            tipo_movimento='ENTRADA',
            categoria='receita',
            valor=receita.valor,
            descricao=f"Receita: {receita.descricao}",
            obra_id=receita.obra_id,
            centro_custo_id=receita.centro_custo_id,
            referencia_id=receita.id,
            referencia_tabela='receita',
            observacoes=receita.observacoes
        )
        db.session.add(movimento)
    
    # 2. Custos de obra (SAÍDAS)
    custos_obra = db.session.query(CustoObra).all()
    for custo in custos_obra:
        movimento = FluxoCaixa(
            data_movimento=custo.data,
            tipo_movimento='SAIDA',
            categoria='custo_obra',
            valor=custo.valor,
            descricao=f"Custo obra: {custo.descricao}",
            obra_id=custo.obra_id,
            centro_custo_id=custo.centro_custo_id,
            referencia_id=custo.id,
            referencia_tabela='custo_obra'
        )
        db.session.add(movimento)
    
    # 3. Custos de veículos (SAÍDAS)
    custos_veiculo = db.session.query(CustoVeiculo).all()
    for custo in custos_veiculo:
        movimento = FluxoCaixa(
            data_movimento=custo.data_custo,
            tipo_movimento='SAIDA',
            categoria='custo_veiculo',
            valor=custo.valor,
            descricao=f"Custo veículo: {custo.descricao or custo.tipo_custo}",
            obra_id=custo.obra_id,
            referencia_id=custo.id,
            referencia_tabela='custo_veiculo'
        )
        db.session.add(movimento)
    
    # 4. Alimentação (SAÍDAS)
    alimentacoes = db.session.query(RegistroAlimentacao).all()
    for alimentacao in alimentacoes:
        movimento = FluxoCaixa(
            data_movimento=alimentacao.data,
            tipo_movimento='SAIDA',
            categoria='alimentacao',
            valor=alimentacao.valor,
            descricao=f"Alimentação: {alimentacao.tipo}",
            obra_id=alimentacao.obra_id,
            referencia_id=alimentacao.id,
            referencia_tabela='registro_alimentacao'
        )
        db.session.add(movimento)
    
    # Commit das sincronizações
    db.session.commit()

def calcular_orcamento_vs_realizado(obra_id):
    """
    Compara orçamento planejado vs. custos/receitas realizados por obra
    
    Returns:
        dict: Análise completa do orçamento
    """
    obra = Obra.query.get(obra_id)
    if not obra:
        return None
    
    # Buscar orçamentos por categoria
    orcamentos = db.session.query(OrcamentoObra).filter_by(obra_id=obra_id).all()
    
    # Calcular custos reais por categoria
    custos_reais = db.session.query(
        CustoObra.tipo,
        func.sum(CustoObra.valor).label('total')
    ).filter_by(obra_id=obra_id).group_by(CustoObra.tipo).all()
    
    # Calcular receitas reais
    receitas_reais = db.session.query(
        func.sum(Receita.valor).label('total')
    ).filter_by(obra_id=obra_id, status='Recebido').scalar() or 0
    
    # Consolidar dados
    resultado = {
        'obra': obra,
        'orcamento_total_planejado': sum(orc.orcamento_planejado for orc in orcamentos),
        'custo_total_realizado': sum(custo.total for custo in custos_reais),
        'receita_total_planejada': sum(orc.receita_planejada for orc in orcamentos),
        'receita_total_realizada': receitas_reais,
        'categorias': []
    }
    
    # Análise por categoria
    custos_dict = {custo.tipo: custo.total for custo in custos_reais}
    
    for orcamento in orcamentos:
        categoria_data = {
            'categoria': orcamento.categoria,
            'orcamento_planejado': orcamento.orcamento_planejado,
            'custo_realizado': custos_dict.get(orcamento.categoria, 0),
            'receita_planejada': orcamento.receita_planejada,
            'receita_realizada': receitas_reais if orcamento.categoria == 'receita_principal' else 0,
            'desvio_custo': orcamento.desvio_custo,
            'desvio_receita': orcamento.desvio_receita
        }
        resultado['categorias'].append(categoria_data)
    
    # Calcular desvios gerais
    if resultado['orcamento_total_planejado'] > 0:
        resultado['desvio_custo_geral'] = (
            (resultado['custo_total_realizado'] - resultado['orcamento_total_planejado']) / 
            resultado['orcamento_total_planejado']
        ) * 100
    else:
        resultado['desvio_custo_geral'] = 0
    
    if resultado['receita_total_planejada'] > 0:
        resultado['desvio_receita_geral'] = (
            (resultado['receita_total_realizada'] - resultado['receita_total_planejada']) / 
            resultado['receita_total_planejada']
        ) * 100
    else:
        resultado['desvio_receita_geral'] = 0
    
    return resultado

def obter_kpis_financeiros(data_inicio=None, data_fim=None):
    """
    Calcula KPIs financeiros consolidados para dashboard
    
    Returns:
        dict: KPIs financeiros principais
    """
    if not data_inicio:
        data_inicio = date.today().replace(day=1)
    if not data_fim:
        data_fim = date.today()
    
    # Fluxo de caixa do período
    fluxo = calcular_fluxo_caixa_periodo(data_inicio, data_fim)
    
    # Receitas pendentes
    receitas_pendentes = db.session.query(
        func.sum(Receita.valor).label('total')
    ).filter(
        Receita.status == 'Pendente',
        Receita.data_receita <= data_fim
    ).scalar() or 0
    
    # Margem de lucro (receitas - custos totais)
    margem_lucro = fluxo['total_entradas'] - fluxo['total_saidas']
    
    # Obras com desvio orçamentário
    obras_com_desvio = []
    obras_ativas = db.session.query(Obra).filter(Obra.status.in_(['Em andamento', 'Pausada'])).all()
    
    for obra in obras_ativas:
        analise = calcular_orcamento_vs_realizado(obra.id)
        if analise and abs(analise['desvio_custo_geral']) > 10:  # Desvio > 10%
            obras_com_desvio.append({
                'obra': obra.nome,
                'desvio': analise['desvio_custo_geral']
            })
    
    return {
        'total_entradas': fluxo['total_entradas'],
        'total_saidas': fluxo['total_saidas'],
        'saldo_periodo': fluxo['saldo_periodo'],
        'receitas_pendentes': receitas_pendentes,
        'margem_lucro': margem_lucro,
        'obras_com_desvio': obras_com_desvio,
        'resumo_categorias': fluxo['resumo_categorias']
    }

def atualizar_orcamento_realizado(obra_id):
    """
    Atualiza automaticamente os valores realizados no orçamento
    baseado nos custos e receitas lançados
    """
    # Buscar orçamentos da obra
    orcamentos = db.session.query(OrcamentoObra).filter_by(obra_id=obra_id).all()
    
    # Calcular custos reais por categoria
    for orcamento in orcamentos:
        # Atualizar custo realizado
        custo_realizado = db.session.query(
            func.sum(CustoObra.valor).label('total')
        ).filter_by(
            obra_id=obra_id,
            tipo=orcamento.categoria
        ).scalar() or 0
        
        orcamento.custo_realizado = custo_realizado
        
        # Atualizar receita realizada (se aplicável)
        if orcamento.categoria == 'receita_principal':
            receita_realizada = db.session.query(
                func.sum(Receita.valor).label('total')
            ).filter_by(obra_id=obra_id, status='Recebido').scalar() or 0
            
            orcamento.receita_realizada = receita_realizada
        
        orcamento.data_atualizacao = datetime.utcnow()
    
    db.session.commit()